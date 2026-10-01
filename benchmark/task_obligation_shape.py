"""Mechanical primitives for task-obligation shape discovery.

This module extracts task-text spans, input/golden cell deltas, and
schema-free edit clusters. It does not assign finance semantics or expose
golden-derived fields as a runtime representation.
"""
from __future__ import annotations

import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from fingerprint import a1_address, formula_text, relative_fingerprint
from librecalc_mcp.domain.formulas import formula_a1_references
from xlsx_metadata_repair import install

install()
import openpyxl  # noqa: E402

SPLIT_SEED = 20260907
N_DISCOVERY = 10
N_VALIDATION = 5
N_HELD_OUT = 5
FAMILY_IDS = [f"{i:02d}" for i in range(1, 21)]

DEFINITIONS = {
    "golden_in_runtime_representation": False,
    "split_unit": "project family (first two digits of task id)",
    "cached_value": "Not a semantic edit when formula text is unchanged.",
    "clause_carrier": (
        "Schema-less spans with exact task-text provenance. No spreadsheet "
        "role labels at extraction time."
    ),
}

_THEN = re.compile(r"\s+then\s+", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")
_LEADING_VERB = re.compile(
    r"^\s*(?P<pred>Complete|Ensure|calculate|Calculate|link|Link|hardcode|"
    r"Hardcode|reference|Reference|create|Create|populate|Populate|compute|"
    r"Compute|derive|Derive|apply|Apply|add|Add|set|Set|insert|Insert|"
    r"distribute|Distribute|convert|Convert|define|Define|showing|show|"
    r"note|Note|using)"
)
_PREP = re.compile(
    r"\s+(?P<mod>(?:for|from|using|based on|linked to|from|according to|"
    r"where|when|across|between|assuming|with|without|except|only|after|"
    r"before|through|over|by|as)\b.+)$",
    re.I,
)


def family_of(task_id: str) -> str:
    return task_id.split("_", 1)[0]


def make_family_split(seed: int = SPLIT_SEED) -> dict[str, Any]:
    """Deterministic family split. Persist before golden ontology inspection."""
    families = list(FAMILY_IDS)
    rng = random.Random(seed)
    rng.shuffle(families)
    discovery = families[:N_DISCOVERY]
    validation = families[N_DISCOVERY : N_DISCOVERY + N_VALIDATION]
    held_out = families[N_DISCOVERY + N_VALIDATION :]
    return {
        "seed": seed,
        "rule": (
            f"sorted family ids {FAMILY_IDS[0]}-{FAMILY_IDS[-1]}, "
            f"shuffle Random({seed}), take {N_DISCOVERY}/{N_VALIDATION}/{N_HELD_OUT}"
        ),
        "discovery_families": sorted(discovery),
        "validation_families": sorted(validation),
        "held_out_families": sorted(held_out),
        "discovery_order": discovery,
        "validation_order": validation,
        "held_out_order": held_out,
        "n_families": {
            "discovery": len(discovery),
            "validation": len(validation),
            "held_out": len(held_out),
        },
    }


def split_of_task(task_id: str, split: dict[str, Any]) -> str:
    fam = family_of(task_id)
    if fam in split["discovery_families"]:
        return "discovery"
    if fam in split["validation_families"]:
        return "validation"
    if fam in split["held_out_families"]:
        return "held_out"
    return "unassigned"


def _kind(value: object) -> str:
    text = formula_text(value)
    if text:
        return "formula"
    if value is None:
        return "blank"
    if isinstance(value, str) and not value.strip():
        return "blank"
    return "value"


def _payload(value: object) -> str | None:
    text = formula_text(value)
    if text:
        return text
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return str(value)


def _change_kind(in_kind: str, gold_kind: str) -> str:
    if in_kind == gold_kind == "value":
        return "value→value_changed"
    if in_kind == gold_kind == "formula":
        return "formula→formula"
    return f"{in_kind}→{gold_kind}"


def _ref_keys(formula: str | None, sheet: str) -> set[str]:
    if not formula:
        return set()
    keys: set[str] = set()
    for host, start, end in formula_a1_references(formula):
        loc = host or sheet
        keys.add(f"{loc}!{start}" + (f":{end}" if end else ""))
    return keys


def load_cell_map(path: Path) -> tuple[dict[tuple[str, int, int], dict[str, Any]], dict[str, int]]:
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    cells: dict[tuple[str, int, int], dict[str, Any]] = {}
    charts = 0
    try:
        for sheet in workbook.worksheets:
            charts += len(getattr(sheet, "_charts", ()) or ())
            for cell in sheet._cells.values():
                col, row = int(cell.column), int(cell.row)
                value = cell.value
                kind = _kind(value)
                if kind == "blank":
                    continue
                rec = {"kind": kind, "payload": _payload(value)}
                if kind == "formula":
                    fp = relative_fingerprint(rec["payload"], col, row, sheet=sheet.title)
                    rec["eq_id"] = None if fp.opaque else fp.eq_id
                    rec["opaque"] = fp.opaque
                cells[(sheet.title, col, row)] = rec
    finally:
        workbook.close()
    return cells, {"n_charts": charts}


def golden_delta(
    task_id: str,
    input_path: Path,
    golden_path: Path,
) -> dict[str, Any]:
    in_cells, in_meta = load_cell_map(input_path)
    gold_cells, gold_meta = load_cell_map(golden_path)
    keys = set(in_cells) | set(gold_cells)
    changes: list[dict[str, Any]] = []
    for key in sorted(keys):
        sheet, col, row = key
        left = in_cells.get(key)
        right = gold_cells.get(key)
        in_kind = left["kind"] if left else "blank"
        gold_kind = right["kind"] if right else "blank"
        in_pay = left["payload"] if left else None
        gold_pay = right["payload"] if right else None
        if in_kind == gold_kind and in_pay == gold_pay:
            continue
        in_fp = (left or {}).get("eq_id")
        gold_fp = (right or {}).get("eq_id")
        refs_in = _ref_keys(in_pay if in_kind == "formula" else None, sheet)
        refs_gold = _ref_keys(gold_pay if gold_kind == "formula" else None, sheet)
        changes.append(
            {
                "task": task_id,
                "sheet": sheet,
                "col": col,
                "row": row,
                "address": a1_address(col, row),
                "input_kind": in_kind,
                "golden_kind": gold_kind,
                "change_kind": _change_kind(in_kind, gold_kind),
                "input_payload": in_pay,
                "golden_payload": gold_pay,
                "input_formula_fingerprint": in_fp,
                "golden_formula_fingerprint": gold_fp,
                "refs_added": sorted(refs_gold - refs_in),
                "refs_removed": sorted(refs_in - refs_gold),
            }
        )
    return {
        "task": task_id,
        "n_changes": len(changes),
        "n_charts_input": in_meta["n_charts"],
        "n_charts_golden": gold_meta["n_charts"],
        "chart_delta": gold_meta["n_charts"] - in_meta["n_charts"],
        "change_kind_counts": _count([c["change_kind"] for c in changes]),
        "sheet_counts": _count([c["sheet"] for c in changes]),
        "changes": changes,
    }


def _count(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out


def _runs(cells: list[dict[str, Any]], axis: str) -> list[list[int]]:
    """Contiguous runs along row (horizontal) or column (vertical)."""
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        if axis == "horizontal":
            groups[(cell["sheet"], cell["row"], cell["change_kind"])].append(cell)
        else:
            groups[(cell["sheet"], cell["col"], cell["change_kind"])].append(cell)
    clusters: list[list[int]] = []
    for _key, members in groups.items():
        coord = "col" if axis == "horizontal" else "row"
        ordered = sorted(members, key=lambda c: c[coord])
        run = [ordered[0]["_i"]]
        prev = ordered[0][coord]
        for cell in ordered[1:]:
            if cell[coord] == prev + 1:
                run.append(cell["_i"])
                prev = cell[coord]
            else:
                if len(run) >= 2:
                    clusters.append(run)
                run = [cell["_i"]]
                prev = cell[coord]
        if len(run) >= 2:
            clusters.append(run)
    return clusters


def _rectangles(cells: list[dict[str, Any]]) -> list[list[int]]:
    by_sheet_kind: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        by_sheet_kind[(cell["sheet"], cell["change_kind"])].append(cell)
    clusters: list[list[int]] = []
    for members in by_sheet_kind.values():
        remaining = {(c["col"], c["row"]): c for c in members}
        seen: set[tuple[int, int]] = set()
        for origin in members:
            key = (origin["col"], origin["row"])
            if key in seen:
                continue
            stack = [key]
            comp = []
            while stack:
                cur = stack.pop()
                if cur in seen or cur not in remaining:
                    continue
                seen.add(cur)
                comp.append(remaining[cur]["_i"])
                c, r = cur
                for nxt in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
                    if nxt in remaining and nxt not in seen:
                        stack.append(nxt)
            if len(comp) >= 2:
                clusters.append(comp)
    return clusters


def cluster_changes(changes: list[dict[str, Any]]) -> dict[str, Any]:
    tagged = []
    for i, cell in enumerate(changes):
        tagged.append({**cell, "_i": i})
    by_sheet: dict[str, list[int]] = defaultdict(list)
    by_kind: dict[str, list[int]] = defaultdict(list)
    by_fp: dict[str, list[int]] = defaultdict(list)
    by_transition: dict[str, list[int]] = defaultdict(list)
    for cell in tagged:
        by_sheet[cell["sheet"]].append(cell["_i"])
        by_kind[cell["change_kind"]].append(cell["_i"])
        fp = cell.get("golden_formula_fingerprint")
        if fp:
            by_fp[fp].append(cell["_i"])
        added = ",".join(cell.get("refs_added") or [])
        by_transition[f"{cell['change_kind']}|{added[:80]}"].append(cell["_i"])
    return {
        "same_sheet": {k: v for k, v in by_sheet.items() if len(v) >= 1},
        "same_change_kind": {k: v for k, v in by_kind.items()},
        "contiguous_horizontal": _runs(tagged, "horizontal"),
        "contiguous_vertical": _runs(tagged, "vertical"),
        "rectangle_components": _rectangles(tagged),
        "same_golden_fingerprint": {k: v for k, v in by_fp.items() if len(v) >= 2},
        "same_source_transition": {k: v for k, v in by_transition.items() if len(v) >= 2},
        "n_horizontal_runs": len(_runs(tagged, "horizontal")),
        "n_vertical_runs": len(_runs(tagged, "vertical")),
        "n_rectangles": len(_rectangles(tagged)),
        "n_fingerprint_families": sum(1 for v in by_fp.values() if len(v) >= 2),
    }


def _span(text: str, start: int, end: int) -> dict[str, Any]:
    return {"text": text[start:end], "start": start, "end": end}


def _find_span(text: str, fragment: str, origin: int = 0) -> dict[str, Any] | None:
    idx = text.find(fragment, origin)
    if idx < 0:
        idx = text.find(fragment)
    if idx < 0:
        return None
    return _span(text, idx, idx + len(fragment))


def weak_clauses(instruction: str) -> list[dict[str, Any]]:
    """Schema-less clause carrier with exact source spans."""
    parts: list[tuple[str, str | None]] = []
    cursor = 0
    paragraphs = instruction.split("\n")
    rebuilt = []
    for para in paragraphs:
        if rebuilt:
            rebuilt.append("\n")
        rebuilt.append(para)
    # Split sentences then explicit THEN.
    sentences: list[str] = []
    for para in instruction.split("\n"):
        para = para.strip()
        if not para:
            continue
        chunks = [para] if len(para) < 40 else _SENTENCE.split(para)
        for chunk in chunks:
            chunk = chunk.strip()
            if chunk:
                sentences.append(chunk)
    clauses: list[dict[str, Any]] = []
    search_from = 0
    cid = 0
    prev_id = None
    for sentence in sentences:
        then_parts = _THEN.split(sentence)
        for ti, piece in enumerate(then_parts):
            piece = piece.strip(" ;")
            if not piece:
                continue
            span = _find_span(instruction, piece, search_from) or _find_span(instruction, piece)
            if span is None:
                continue
            search_from = span["start"]
            verb = _LEADING_VERB.match(piece)
            pred = None
            if verb:
                pred = _span(
                    instruction,
                    span["start"] + verb.start("pred"),
                    span["start"] + verb.end("pred"),
                )
            remainder = piece[verb.end() :].strip() if verb else piece
            modifiers = []
            arguments = []
            prep = _PREP.search(remainder)
            if prep:
                arg = remainder[: prep.start()].strip(" ,")
                mod = prep.group("mod").strip(" ,")
                if arg:
                    arguments.append(_find_span(instruction, arg, span["start"]) or {"text": arg})
                if mod:
                    modifiers.append(_find_span(instruction, mod, span["start"]) or {"text": mod})
            elif remainder:
                arguments.append(_find_span(instruction, remainder, span["start"]) or {"text": remainder})
            cid += 1
            clause_id = f"C{cid}"
            relations = []
            if ti > 0 and prev_id:
                relations.append({"rel": "THEN", "from": prev_id, "to": clause_id, "text": "then"})
            clauses.append(
                {
                    "id": clause_id,
                    "exact_source_span": span,
                    "predicate_span": pred,
                    "argument_spans": [s for s in arguments if s],
                    "modifier_spans": [s for s in modifiers if s],
                    "relation_spans": relations,
                }
            )
            prev_id = clause_id
    return clauses


def mentioned_sheet_spans(instruction: str) -> list[dict[str, Any]]:
    found = []
    for match in re.finditer(
        r"(?:in|on)\s+the\s+(.+?)\s+(?:sheet|tab|section)\b",
        instruction,
        flags=re.I,
    ):
        found.append(_span(instruction, match.start(1), match.end(1)))
    return found


def explicit_preservation_spans(instruction: str) -> list[dict[str, Any]]:
    found = []
    for match in re.finditer(
        r"Ensure the existing structure, layout, and formatting of the model are preserved[^.]*",
        instruction,
        flags=re.I,
    ):
        found.append(_span(instruction, match.start(), match.end()))
    for match in re.finditer(
        r"\b(leave (?:the )?rest unchanged|do not (?:modify|change|edit)|only modify|except)\b",
        instruction,
        flags=re.I,
    ):
        found.append(_span(instruction, match.start(), match.end()))
    return found


def quantifier_spans(instruction: str) -> list[dict[str, Any]]:
    found = []
    pattern = re.compile(
        r"\b(all|entire|remaining|each|every|only|except|through|to|from)\b",
        re.I,
    )
    for match in pattern.finditer(instruction):
        found.append(_span(instruction, match.start(), match.end()))
    return found


def relation_spans(instruction: str) -> list[dict[str, Any]]:
    found = []
    pattern = re.compile(
        r"\b(using|based on|linked to|from|according to|same as|copy|extend|"
        r"carry forward|by growing|by summing|by dividing|by applying|"
        r"by allocating|roll-forward|reference)\b",
        re.I,
    )
    for match in pattern.finditer(instruction):
        found.append(_span(instruction, match.start(), match.end()))
    return found


def near_numeric(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    try:
        fa, fb = float(left), float(right)
    except (TypeError, ValueError):
        return False
    scale = max(1.0, abs(fa), abs(fb))
    return abs(fa - fb) <= 1e-8 * scale or abs(fa - fb) < 1e-6


def is_error_token(text: str | None) -> bool:
    if not text:
        return False
    compact = text.strip().lstrip("=").upper()
    return compact in {"#N/A", "#NA", "N/A", "#VALUE!", "#REF!", "#DIV/0!"}


def is_semantic_change(row: dict[str, Any]) -> bool:
    """Drop cached-float noise and error-token formula wrappers."""
    if near_numeric(row.get("input_payload"), row.get("golden_payload")):
        return False
    if is_error_token(row.get("input_payload")) and is_error_token(row.get("golden_payload")):
        return False
    return True


def ground_sheets(instruction: str, sheet_titles: list[str]) -> list[dict[str, Any]]:
    """Perfect-oracle sheet grounding: exact then casefold containment."""
    hits = []
    lower_instr = instruction.casefold()
    for title in sheet_titles:
        if title.casefold() in lower_instr:
            idx = lower_instr.find(title.casefold())
            hits.append(
                {
                    "sheet": title,
                    "span": _span(instruction, idx, idx + len(title)),
                    "how": "casefold_substring",
                }
            )
            continue
        compact_title = re.sub(r"[\s_]+", " ", title).strip().casefold()
        compact_instr = re.sub(r"[\s_]+", " ", instruction).casefold()
        if compact_title and compact_title in compact_instr:
            hits.append({"sheet": title, "span": None, "how": "normalized_substring"})
    return hits
