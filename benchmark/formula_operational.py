"""Gold-blind operational dependence structure.

Edge direction is frozen as DATA_DEPENDENCE(S, C): precedent/source S →
dependent/consumer formula C. No goldens, labels, finance ontology, or
PRODUCES/PARAMETERIZES/MAPS_TO predicates.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from fingerprint import a1_address, relative_fingerprint
from formula_dependency_selection import (
    BFS_VISIT_CAP,
    CellKey,
    DependencyGraph,
    homologous_peers,
)
from librecalc_mcp.domain.formulas import formula_a1_shape
from ranges import parse_a1_cell

LEFT_RIGHT_WINDOWS = (2, 4, 8)
PEER_FAMILY_WINDOW = 8
COUNT_BINS = ((0, 0, "0"), (1, 1, "1"), (2, 4, "2-4"), (5, 20, "5-20"), (21, None, ">20"))

_REF = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:(?P<sheet>\$?'(?:[^']|'')+'|\$?[A-Za-z_][A-Za-z0-9_]*)[.!])?"
    r"(?P<start_col_abs>\$?)(?P<start_col>[A-Za-z]{1,3})"
    r"(?P<start_row_abs>\$?)(?P<start_row>[1-9][0-9]*)"
    r"(?:\s*:\s*"
    r"(?:(?P<end_sheet>\$?'(?:[^']|'')+'|\$?[A-Za-z_][A-Za-z0-9_]*)[.!])?"
    r"(?P<end_col_abs>\$?)(?P<end_col>[A-Za-z]{1,3})"
    r"(?P<end_row_abs>\$?)(?P<end_row>[1-9][0-9]*))?"
    r"(?![A-Za-z0-9_])"
)
_IDENT_BEFORE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*$")
_NUM_LIT = re.compile(r"(?<![A-Za-z0-9_.$])(\d+\.?\d*)(?![A-Za-z0-9_])")
_FUNC = re.compile(r"(?i)\b(SUM|AVERAGE|SUMPRODUCT|SUBTOTAL)\s*\(")

DEFINITIONS = {
    "golden_in_generation": False,
    "DATA_DEPENDENCE": (
        "If formula cell C references source cell/range S, the edge is S → C "
        "(precedent → dependent). Never the reverse."
    ),
    "DIRECT_PRECEDENT": "S occurs in C's supported explicit A1 references.",
    "DIRECT_DEPENDENT": "C directly references S.",
    "USE_DEF_SLOT": (
        "One explicit A1 operand in a formula and the precedent supplying it. "
        "Slots stay ordered; they are not flattened to a set."
    ),
    "DEPENDENCE_TEMPLATE": (
        "Repeated mechanical use-def slot signatures across structurally "
        "corresponding existing formulas. Not a semantic role."
    ),
    "DEPENDENCE_ORIENTATION": (
        "Dominant same-sheet vs cross-sheet destination among same-row formulas "
        "in a column window. Headers are not used to name historical/forecast."
    ),
    "DEPENDENCE_CYCLE_IF_ADDED": (
        "Adding candidate edge S → T would create a directed cycle in the "
        "existing data-dependence graph."
    ),
    "REDUCTION": (
        "Operator kind plus operand geometry: SUM / AVERAGE / explicit + / other, "
        "point vs contiguous range, adjacency, and whether operands are themselves "
        "reduction formulas. Leaf-like means graph/formula structure only."
    ),
    "not_used": (
        "Goldens, labels, S2 synonyms, PRODUCES/PARAMETERIZES/MAPS_TO, agents, "
        "and learned ranking are not used in the substrate."
    ),
}


def bin_count(n: int) -> str:
    for lo, hi, name in COUNT_BINS:
        if hi is None:
            if n >= lo:
                return name
        elif lo <= n <= hi:
            return name
    return ">20"


def _sheet_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    raw = raw.removeprefix("$")
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


def _blank_strings(formula: str) -> str:
    chars = list(formula)
    index = 0
    while index < len(chars):
        if chars[index] != '"':
            index += 1
            continue
        chars[index] = " "
        index += 1
        while index < len(chars):
            if chars[index] == '"':
                if index + 1 < len(chars) and chars[index + 1] == '"':
                    chars[index] = " "
                    chars[index + 1] = " "
                    index += 2
                    continue
                chars[index] = " "
                index += 1
                break
            chars[index] = " "
            index += 1
    return "".join(chars)


def enclosing_operator(source: str, start: int, end: int | None = None) -> dict[str, Any]:
    """Innermost arithmetic operator or function wrapping source[start:end]."""
    end = start if end is None else end
    arith = set("+-*/^&")

    def scan_op(begin: int, step: int, limit: int) -> str | None:
        depth = 0
        i = begin
        while 0 <= i < len(source) and i != limit:
            ch = source[i]
            if ch == (")" if step < 0 else "("):
                depth += 1
            elif ch == ("(" if step < 0 else ")"):
                if depth == 0:
                    return None
                depth -= 1
            elif depth == 0 and ch in arith:
                return ch
            i += step
        return None

    left_op = scan_op(start - 1, -1, -1)
    right_op = scan_op(end, 1, len(source))
    if left_op:
        return {"kind": "op", "func": None, "op": left_op}
    if right_op:
        return {"kind": "op", "func": None, "op": right_op}

    depth = 0
    i = start - 1
    while i >= 0:
        ch = source[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                prefix = source[:i]
                match = _IDENT_BEFORE.search(prefix)
                if match:
                    return {"kind": "func", "func": match.group(1).upper(), "op": None}
                return {"kind": "group", "func": None, "op": None}
            depth -= 1
        i -= 1
    return {"kind": "root", "func": None, "op": None}


def parse_use_def_slots(
    formula: str | None,
    origin_sheet: str,
    origin_col: int,
    origin_row: int,
) -> dict[str, Any]:
    if not formula:
        return {"slots": [], "parser_ok": True, "opaque": False, "literals": []}
    fp = relative_fingerprint(formula, origin_col, origin_row, sheet=origin_sheet)
    source = _blank_strings(formula)
    slots: list[dict[str, Any]] = []
    failed = False
    for match in _REF.finditer(source):
        if match.end() < len(source) and source[match.end()] == "(":
            continue
        try:
            c1 = _col_num(match.group("start_col"))
            r1 = int(match.group("start_row"))
        except (TypeError, ValueError):
            failed = True
            continue
        end_col = match.group("end_col")
        if end_col:
            c2 = _col_num(end_col)
            r2 = int(match.group("end_row"))
        else:
            c2, r2 = c1, r1
        host = _sheet_name(match.group("sheet") or match.group("end_sheet")) or origin_sheet
        is_range = (c1, r1) != (c2, r2)
        enc = enclosing_operator(source, match.start(), match.end())
        mask = (
            f"{'$' if match.group('start_col_abs') else 'C'}"
            f"{'$' if match.group('start_row_abs') else 'R'}"
        )
        if end_col:
            mask += (
                f":{'$' if match.group('end_col_abs') else 'C'}"
                f"{'$' if match.group('end_row_abs') else 'R'}"
            )
        slots.append(
            {
                "index": len(slots),
                "sheet": host,
                "c1": min(c1, c2),
                "r1": min(r1, r2),
                "c2": max(c1, c2),
                "r2": max(r1, r2),
                "start": a1_address(c1, r1),
                "end": None if not is_range else a1_address(c2, r2),
                "is_range": is_range,
                "cross_sheet": host != origin_sheet,
                "abs_mask": mask,
                "dcol": min(c1, c2) - origin_col,
                "drow": min(r1, r2) - origin_row,
                "enclosing": enc,
                "raw": match.group(0),
            }
        )
    # Keep numeric literals outside A1 matches (0.3 / 365 / 30). Row digits inside refs are dropped.
    ref_spans = [(m.start(), m.end()) for m in _REF.finditer(source)]
    kept = []
    for match in _NUM_LIT.finditer(source):
        if any(a <= match.start() and match.end() <= b for a, b in ref_spans):
            continue
        text = match.group(1)
        kept.append(float(text) if "." in text else int(text))
    return {
        "slots": slots,
        "parser_ok": not failed,
        "opaque": fp.opaque,
        "opaque_reason": fp.reason,
        "fingerprint": None if fp.opaque else fp.text,
        "eq_id": None if fp.opaque else fp.eq_id,
        "literals": kept,
        "shape": formula_a1_shape(formula),
    }


def _col_num(name: str) -> int:
    number = 0
    for character in name.upper():
        number = number * 26 + ord(character) - ord("A") + 1
    return number


def reduction_of(formula: str | None, parsed: dict[str, Any] | None = None) -> dict[str, Any]:
    if not formula:
        return {
            "operator": None,
            "operand_count": 0,
            "point_vs_range": None,
            "is_reduction": False,
            "contiguous": False,
            "adjacent": False,
            "row_span": 0,
            "col_span": 0,
            "has_literal": False,
        }
    parsed = parsed or parse_use_def_slots(formula, "S", 1, 1)
    slots = parsed["slots"]
    funcs = [m.group(1).upper() for m in _FUNC.finditer(formula)]
    body = formula.lstrip("=").lstrip("+")
    n_plus = body.count("+")
    n_star = body.count("*")
    has_if = bool(re.search(r"(?i)\bIF\s*\(", formula))
    if "SUM" in funcs:
        operator = "SUM"
    elif "AVERAGE" in funcs:
        operator = "AVERAGE"
    elif n_plus >= 1 and n_star == 0 and not has_if:
        operator = "explicit_+"
    else:
        operator = "other"
    has_range = any(slot["is_range"] for slot in slots)
    point_vs_range = "range" if has_range else ("point" if slots else None)
    rows = []
    cols = []
    for slot in slots:
        rows.extend([slot["r1"], slot["r2"]])
        cols.extend([slot["c1"], slot["c2"]])
    row_span = (max(rows) - min(rows) + 1) if rows else 0
    col_span = (max(cols) - min(cols) + 1) if cols else 0
    contiguous = False
    adjacent = False
    if has_range and len(slots) == 1:
        contiguous = True
        adjacent = True
    elif slots and all(not slot["is_range"] for slot in slots):
        same_col = len({slot["c1"] for slot in slots}) == 1
        same_row = len({slot["r1"] for slot in slots}) == 1
        if same_col:
            ordered = sorted({slot["r1"] for slot in slots})
            adjacent = len(ordered) >= 2 and ordered[-1] - ordered[0] + 1 == len(ordered)
            contiguous = adjacent
        elif same_row:
            ordered = sorted({slot["c1"] for slot in slots})
            adjacent = len(ordered) >= 2 and ordered[-1] - ordered[0] + 1 == len(ordered)
            contiguous = adjacent
    is_reduction = operator in {"SUM", "AVERAGE"} or (
        operator == "explicit_+" and (has_range or len(slots) >= 2)
    )
    return {
        "operator": operator,
        "operand_count": len(slots),
        "point_vs_range": point_vs_range,
        "is_reduction": is_reduction,
        "contiguous": contiguous,
        "adjacent": adjacent,
        "row_span": row_span,
        "col_span": col_span,
        "has_literal": bool(parsed["literals"]),
        "literals": parsed["literals"],
        "funcs": funcs,
        "shape": parsed.get("shape"),
    }


def source_kind(graph: DependencyGraph, key: CellKey) -> str:
    kind = graph.kind(key)
    if kind == "F":
        return "supported_formula"
    if kind == "O":
        return "opaque_formula"
    if kind == "V":
        return "value"
    return "blank"


@dataclass
class OperationalView:
    graph: DependencyGraph
    by_row: dict[tuple[str, int], list[int]] = field(default_factory=dict)
    dependents: dict[CellKey, list[CellKey]] = field(default_factory=dict)

    def kind(self, key: CellKey) -> str:
        return source_kind(self.graph, key)


def build_view(graph: DependencyGraph) -> OperationalView:
    by_row: dict[tuple[str, int], list[int]] = defaultdict(list)
    for sheet, col, row in graph.formulas:
        by_row[(sheet, row)].append(col)
    for cols in by_row.values():
        cols.sort()
    dependents: dict[CellKey, list[CellKey]] = defaultdict(list)
    for src, deps in graph.point_rev.items():
        seen: set[CellKey] = set()
        for dep, _slot in deps:
            if dep not in seen:
                seen.add(dep)
                dependents[src].append(dep)
    for src, dests in graph.formula_fwd.items():
        have = set(dependents.get(src, ()))
        for dep in dests:
            if dep not in have:
                dependents[src].append(dep)
    return OperationalView(graph=graph, by_row=dict(by_row), dependents=dict(dependents))


def direct_dependents(view: OperationalView, key: CellKey) -> list[CellKey]:
    return list(view.dependents.get(key, ()))


def direct_precedents(view: OperationalView, key: CellKey) -> list[CellKey]:
    node = view.graph.formulas.get(key)
    if node is None:
        return []
    out: list[CellKey] = []
    seen: set[CellKey] = set()
    for slot in node.slots:
        if slot.min_col == slot.max_col and slot.min_row == slot.max_row:
            cell = (slot.sheet, slot.min_col, slot.min_row)
            if cell not in seen:
                seen.add(cell)
                out.append(cell)
        else:
            # Keep range anchors only; do not explode large rectangles.
            for col, row in (
                (slot.min_col, slot.min_row),
                (slot.max_col, slot.max_row),
            ):
                cell = (slot.sheet, col, row)
                if cell not in seen:
                    seen.add(cell)
                    out.append(cell)
    return out


def edge_signature(
    view: OperationalView,
    source: CellKey,
    consumer: CellKey,
    slot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    s_sheet, s_col, s_row = source
    c_sheet, c_col, c_row = consumer
    node = view.graph.formulas.get(source)
    enc = None if slot is None else slot.get("enclosing")
    is_range = False if slot is None else bool(slot.get("is_range"))
    return {
        "point_vs_range": "range" if is_range else "point",
        "same_sheet": s_sheet == c_sheet,
        "source_sheet": s_sheet,
        "consumer_sheet": c_sheet,
        "dcol": s_col - c_col,
        "drow": s_row - c_row,
        "abs_mask": None if slot is None else slot.get("abs_mask"),
        "source_kind": view.kind(source),
        "source_eq_id": None if node is None else node.eq_id,
        "enclosing": enc,
        "n_prec_S": len(direct_precedents(view, source)),
        "n_dep_S": len(direct_dependents(view, source)),
        "n_prec_C": len(direct_precedents(view, consumer)),
        "n_dep_C": len(direct_dependents(view, consumer)),
    }


def _bfs(
    view: OperationalView,
    start: CellKey,
    *,
    goal: CellKey | None = None,
    cap: int = BFS_VISIT_CAP,
) -> dict[str, Any]:
    visited: set[CellKey] = set()
    parent: dict[CellKey, CellKey] = {}
    queue: deque[CellKey] = deque([start])
    found = False
    while queue and len(visited) < cap:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        if goal is not None and node == goal and node != start:
            found = True
            break
        for nxt in view.dependents.get(node, ()):
            if nxt not in visited and nxt not in parent:
                parent[nxt] = node
                queue.append(nxt)
        if goal is not None and start in view.dependents.get(node, ()):
            # ignore reverse
            pass
    capped = len(visited) >= cap and bool(queue)
    path = None
    if found and goal is not None:
        path = [goal]
        cur = goal
        while cur != start and cur in parent:
            cur = parent[cur]
            path.append(cur)
        path.reverse()
        if path[0] != start:
            path = None
            found = False
    return {
        "visited": visited,
        "n": len(visited),
        "found": found,
        "path": None if path is None else [_cell_id(p) for p in path],
        "capped": capped,
    }


def _cell_id(key: CellKey) -> str:
    return f"{key[0]}!{a1_address(key[1], key[2])}"


def cycle_if_added(view: OperationalView, source: CellKey, target: CellKey) -> dict[str, Any]:
    """Would DATA_DEPENDENCE(source, target) i.e. source → target create a cycle?"""
    c1 = source in view.dependents.get(target, ())
    if not c1:
        node = view.graph.formulas.get(source)
        if node is not None:
            t_sheet, t_col, t_row = target
            for slot in node.slots:
                if (
                    slot.sheet == t_sheet
                    and slot.min_col <= t_col <= slot.max_col
                    and slot.min_row <= t_row <= slot.max_row
                ):
                    c1 = True
                    break
    search = _bfs(view, target, goal=source)
    path = search["path"]
    if c1 and path is None:
        path = [_cell_id(target), _cell_id(source)]
    c2 = bool(search["found"] and path is not None and len(path) > 2)
    return {
        "C1_direct_downstream_conflict": c1,
        "C2_transitive_downstream_conflict": c2,
        "C3_cycle_if_added": c1 or c2 or bool(search["found"]),
        "shortest_T_to_S": path,
        "bfs_capped": search["capped"],
        "n_reached_from_T": search["n"],
    }


def same_row_peers(
    view: OperationalView, sheet: str, col: int, row: int
) -> dict[str, Any]:
    cols = view.by_row.get((sheet, row), [])
    left = [c for c in cols if c < col]
    right = [c for c in cols if c > col]
    left_col = left[-1] if left else None
    right_col = right[0] if right else None

    def pack(other: int | None, side: str) -> dict[str, Any] | None:
        if other is None:
            return None
        key = (sheet, other, row)
        node = view.graph.formulas[key]
        parsed = parse_use_def_slots(node.formula, sheet, other, row)
        return {
            "provenance": "P1",
            "side": side,
            "distance": abs(other - col),
            "key": key,
            "address": _cell_id(key),
            "formula": node.formula,
            "eq_id": node.eq_id,
            "fingerprint": node.fingerprint,
            "parsed": parsed,
            "reduction": reduction_of(node.formula, parsed),
        }

    return {
        "left": pack(left_col, "left"),
        "right": pack(right_col, "right"),
        "n_left": len(left),
        "n_right": len(right),
    }


def family_peers(view: OperationalView, sheet: str, col: int, row: int) -> list[dict[str, Any]]:
    cols = view.by_row.get((sheet, row), [])
    nearby = [c for c in cols if 0 < abs(c - col) <= PEER_FAMILY_WINDOW]
    by_eq: dict[str, list[int]] = defaultdict(list)
    for other in nearby:
        by_eq[view.graph.formulas[(sheet, other, row)].eq_id].append(other)
    out = []
    for eq_id, members in by_eq.items():
        if len(members) < 2 and len(nearby) < 2:
            continue
        for other in members:
            key = (sheet, other, row)
            node = view.graph.formulas[key]
            parsed = parse_use_def_slots(node.formula, sheet, other, row)
            out.append(
                {
                    "provenance": "P2",
                    "distance": abs(other - col),
                    "key": key,
                    "address": _cell_id(key),
                    "formula": node.formula,
                    "eq_id": eq_id,
                    "parsed": parsed,
                    "reduction": reduction_of(node.formula, parsed),
                    "family_n": len(members),
                }
            )
    out.sort(key=lambda item: item["distance"])
    return out


def consumer_peers(view: OperationalView, target: CellKey) -> list[dict[str, Any]]:
    graph = view.graph
    out: list[dict[str, Any]] = []
    seen: set[CellKey] = set()
    for formula_key, slot_index in graph.point_rev.get(target, ()):
        node = graph.formulas.get(formula_key)
        if node is None:
            continue
        for peer in homologous_peers(graph, target, node.eq_id, slot_index, formula_key):
            if peer in seen or graph.kind(peer) != "F":
                continue
            seen.add(peer)
            pnode = graph.formulas[peer]
            parsed = parse_use_def_slots(pnode.formula, peer[0], peer[1], peer[2])
            out.append(
                {
                    "provenance": "P3",
                    "key": peer,
                    "address": _cell_id(peer),
                    "formula": pnode.formula,
                    "eq_id": pnode.eq_id,
                    "via_consumer": _cell_id(formula_key),
                    "via_slot": slot_index,
                    "parsed": parsed,
                    "reduction": reduction_of(pnode.formula, parsed),
                }
            )
    return out


def collect_peers(view: OperationalView, sheet: str, col: int, row: int) -> dict[str, Any]:
    p1 = same_row_peers(view, sheet, col, row)
    p2 = family_peers(view, sheet, col, row)
    p3 = consumer_peers(view, (sheet, col, row))
    formula_peers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in (p1.get("left"), p1.get("right")):
        if item and item["address"] not in seen:
            seen.add(item["address"])
            formula_peers.append(item)
    for item in p2 + p3:
        if item["address"] not in seen:
            seen.add(item["address"])
            formula_peers.append(item)
    return {
        "P1": p1,
        "P2": p2,
        "P3": p3,
        "formula_peers": formula_peers,
        "n_p1": int(p1["left"] is not None) + int(p1["right"] is not None),
        "n_p2": len(p2),
        "n_p3": len(p3),
        "n_formula_peers": len(formula_peers),
    }


def _slot_orientation(slot: dict[str, Any], origin_sheet: str) -> str:
    if slot.get("cross_sheet"):
        return slot["sheet"]
    return "SAME_SHEET"


def orientation(
    view: OperationalView, sheet: str, col: int, row: int
) -> dict[str, Any]:
    cols = view.by_row.get((sheet, row), [])
    report: dict[str, Any] = {}
    for window in LEFT_RIGHT_WINDOWS:
        left_dirs: list[str] = []
        right_dirs: list[str] = []
        for other in cols:
            node = view.graph.formulas[(sheet, other, row)]
            parsed = parse_use_def_slots(node.formula, sheet, other, row)
            if not parsed["slots"]:
                continue
            dest = _slot_orientation(parsed["slots"][0], sheet)
            if col - window <= other < col:
                left_dirs.append(dest)
            elif col < other <= col + window:
                right_dirs.append(dest)
        left_mode = Counter(left_dirs).most_common(1)
        right_mode = Counter(right_dirs).most_common(1)
        left = None if not left_mode else left_mode[0][0]
        right = None if not right_mode else right_mode[0][0]
        report[f"w{window}"] = {
            "O1_left": left,
            "O2_right": right,
            "O3_change": bool(left and right and left != right),
            "n_left": len(left_dirs),
            "n_right": len(right_dirs),
            "left_dirs": dict(Counter(left_dirs)),
            "right_dirs": dict(Counter(right_dirs)),
        }
    return report


def candidate_orientation_match(
    orient: dict[str, Any], source_sheet: str, target_sheet: str
) -> dict[str, Any]:
    dest = "SAME_SHEET" if source_sheet == target_sheet else source_sheet
    out = {}
    for window in LEFT_RIGHT_WINDOWS:
        block = orient[f"w{window}"]
        out[f"w{window}"] = {
            "O4_matches_left": block["O1_left"] is not None and dest == block["O1_left"],
            "O5_matches_right": block["O2_right"] is not None and dest == block["O2_right"],
            "O6_crosses_change": bool(
                block["O3_change"]
                and (
                    (dest == block["O1_left"] and dest != block["O2_right"])
                    or (dest == block["O2_right"] and dest != block["O1_left"])
                )
            ),
            "candidate_dest": dest,
        }
    return out


def template_match(
    peer: dict[str, Any],
    cand_slot: dict[str, Any] | None,
    source: CellKey | None,
    target: CellKey,
    view: OperationalView,
) -> dict[str, Any]:
    empty = {
        "T1_same_source_row": False,
        "T2_same_source_col": False,
        "T3_same_source_sheet": False,
        "T4_same_point_range": False,
        "T5_same_vector": False,
        "T6_same_source_class": False,
        "T7_strict": False,
        "T7_partial_n": 0,
        "peer_address": peer.get("address"),
        "provenance": peer.get("provenance"),
        "matched_peer_slot": None,
    }
    if cand_slot is None or source is None:
        return empty
    pslots = (peer.get("parsed") or {}).get("slots") or []
    if not pslots:
        return empty
    chosen = None
    cand_enc = (cand_slot.get("enclosing") or {}).get("op") or (cand_slot.get("enclosing") or {}).get(
        "func"
    )
    for pslot in pslots:
        penc = (pslot.get("enclosing") or {}).get("op") or (pslot.get("enclosing") or {}).get("func")
        if cand_enc and penc == cand_enc:
            chosen = pslot
            break
    if chosen is None:
        idx = min(cand_slot.get("index", 0), len(pslots) - 1)
        chosen = pslots[idx]
    t1 = cand_slot["r1"] == chosen["r1"]
    t2 = cand_slot["c1"] == chosen["c1"] + (target[1] - peer["key"][1])
    t3 = cand_slot["sheet"] == chosen["sheet"]
    t4 = bool(cand_slot["is_range"]) == bool(chosen["is_range"])
    t5 = cand_slot["dcol"] == chosen["dcol"] and cand_slot["drow"] == chosen["drow"]
    src_node = view.graph.formulas.get(source)
    peer_src = (chosen["sheet"], chosen["c1"], chosen["r1"])
    peer_src_node = view.graph.formulas.get(peer_src)
    t6 = bool(
        src_node
        and peer_src_node
        and src_node.eq_id == peer_src_node.eq_id
    )
    cand_kind = view.kind(source)
    peer_kind = view.kind(peer_src)
    t_kind = cand_kind == peer_kind
    t_enc = (cand_slot.get("enclosing") or {}) == (chosen.get("enclosing") or {})
    strict = t3 and t4 and t5 and t_kind and t_enc
    partial = sum([t3, t4, t5, t_kind, t_enc])
    return {
        "T1_same_source_row": t1,
        "T2_same_source_col": t2,
        "T3_same_source_sheet": t3,
        "T4_same_point_range": t4,
        "T5_same_vector": t5,
        "T6_same_source_class": t6,
        "T7_strict": strict,
        "T7_partial_n": partial,
        "peer_address": peer.get("address"),
        "provenance": peer.get("provenance"),
        "matched_peer_slot": {
            "sheet": chosen["sheet"],
            "start": chosen["start"],
            "dcol": chosen["dcol"],
            "drow": chosen["drow"],
            "enclosing": chosen.get("enclosing"),
        },
    }


def aggregate_templates(matches: list[dict[str, Any]]) -> dict[str, Any]:
    if not matches:
        return {
            "n": 0,
            "n_strict": 0,
            "n_T1": 0,
            "n_T3": 0,
            "n_T5": 0,
            "n_vector_and_sheet": 0,
            "peer_conflict": False,
        }
    n_strict = sum(1 for m in matches if m["T7_strict"])
    n_t1 = sum(1 for m in matches if m["T1_same_source_row"])
    n_t3 = sum(1 for m in matches if m["T3_same_source_sheet"])
    n_t5 = sum(1 for m in matches if m["T5_same_vector"])
    n_vs = sum(1 for m in matches if m["T3_same_source_sheet"] and m["T5_same_vector"])
    sheets = {m["matched_peer_slot"]["sheet"] for m in matches if m.get("matched_peer_slot")}
    rows = {m["matched_peer_slot"]["drow"] for m in matches if m.get("matched_peer_slot")}
    return {
        "n": len(matches),
        "n_strict": n_strict,
        "n_T1": n_t1,
        "n_T3": n_t3,
        "n_T5": n_t5,
        "n_vector_and_sheet": n_vs,
        "peer_conflict": len(sheets) > 1 or len(rows) > 1,
    }


def source_profile(
    view: OperationalView, source: CellKey, peers: list[dict[str, Any]]
) -> dict[str, Any]:
    node = view.graph.formulas.get(source)
    n_prec = len(direct_precedents(view, source))
    n_dep = len(direct_dependents(view, source))
    down = _bfs(view, source)
    n_cross = sum(1 for dep in direct_dependents(view, source) if dep[0] != source[0])
    group_n = 0
    if node is not None:
        group_n = len(view.graph.by_eq.get(node.eq_id, ()))
    peer_use = 0
    for peer in peers:
        for slot in (peer.get("parsed") or {}).get("slots") or []:
            if slot["sheet"] == source[0] and slot["r1"] <= source[2] <= slot["r2"]:
                if slot["c1"] <= source[1] <= slot["c2"] or slot["drow"] == 0:
                    peer_use += 1
                    break
    return {
        "has_formula": node is not None,
        "n_direct_precedents": n_prec,
        "n_direct_dependents": n_dep,
        "n_transitive_descendants": down["n"],
        "descendants_capped": down["capped"],
        "n_cross_sheet_dependents": n_cross,
        "in_formula_group": group_n >= 2,
        "formula_group_n": group_n,
        "peer_use_count": peer_use,
        "bins": {
            "precedents": bin_count(n_prec),
            "dependents": bin_count(n_dep),
            "descendants": bin_count(down["n"]),
        },
        "kind": view.kind(source),
    }


def reduction_relations(
    cand: dict[str, Any],
    peer_reductions: list[dict[str, Any]],
    view: OperationalView,
    slots: list[dict[str, Any]],
) -> dict[str, Any]:
    r1 = bool(cand.get("contiguous") and cand.get("operator") in {"SUM", "AVERAGE", "explicit_+"})
    leaf = True
    sibling = False
    for slot in slots:
        if slot["is_range"]:
            continue
        key = (slot["sheet"], slot["c1"], slot["r1"])
        node = view.graph.formulas.get(key)
        if node is None:
            continue
        nested = reduction_of(node.formula)
        if nested.get("is_reduction"):
            leaf = False
            sibling = True
    if not slots:
        leaf = False
    peer_ops = [p.get("operator") for p in peer_reductions if p.get("operator")]
    peer_contig = [p.get("contiguous") for p in peer_reductions]
    r4 = bool(peer_ops) and all(op == cand.get("operator") for op in peer_ops)
    r5 = bool(peer_reductions) and any(
        p.get("row_span") == cand.get("row_span") and p.get("col_span") == cand.get("col_span")
        for p in peer_reductions
    )
    r6 = bool(peer_reductions) and any(
        p.get("is_reduction") == cand.get("is_reduction") for p in peer_reductions
    )
    return {
        "R1_reduces_contiguous_range": r1,
        "R2_reduces_sibling_aggregates": sibling,
        "R3_reduces_leaf_like": leaf and bool(slots) and not sibling,
        "R4_peer_reduction_shape_match": r4,
        "R5_range_boundary_match": r5,
        "R6_reduction_level_match": r6,
        "peer_ops": peer_ops,
        "peer_contiguous": peer_contig,
        "peer_conflict": len(set(peer_ops)) > 1 if peer_ops else False,
    }


def ancestor_of_peers(
    view: OperationalView, source: CellKey, peer_keys: list[CellKey]
) -> bool:
    """C4: source is already upstream of a formula-family peer (reaches that peer)."""
    if not peer_keys:
        return False
    down = _bfs(view, source)
    return any(peer in down["visited"] and peer != source for peer in peer_keys)


def descendant_of_peers(
    view: OperationalView, source: CellKey, peer_keys: list[CellKey], target: CellKey
) -> bool:
    """C5: source lies downstream of a peer or of T."""
    if source in view.dependents.get(target, ()):
        return True
    for peer in peer_keys:
        down = _bfs(view, peer, goal=source)
        if down["found"]:
            return True
    return False
