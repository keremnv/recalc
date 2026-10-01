"""Deterministic, candidate-side population and output-role relations.

This module contains only relations earned by the zero-model contrasts.  It
does not inspect evaluator gold and it never grants Edit Plan authority.
Stable cell identities and the introducing Task IR field are retained on every
derived record so lexical evidence cannot silently become a target alias.
"""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Iterable

from formula_schema import normalize_text
from workbook_grounding_spine import cell_id, id_in_spine, parse_cell_id


ORDINALS = ("first", "second", "third")
_ORDINAL = re.compile(r"\b(first|second|third)\b", re.I)
_ORDINAL_LABEL = re.compile(r"\b(first|second|third)\s+([a-z][a-z0-9_-]*)\b", re.I)
_ALL_THREE = re.compile(r"\b(?:all|every|each)\s+(?:three|3)\s+([a-z][a-z0-9_-]*)\b", re.I)
_MEMBER_LIST = re.compile(
    r"\b(?:first|second|third)(?:\s*(?:,|and)\s*(?:first|second|third))*\s+([a-z][a-z0-9_-]*)\b",
    re.I,
)


def _field_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("text") or "")
    if isinstance(value, list):
        return " ".join(_field_text(item) for item in value)
    return str(value)


def _singular_token(value: str) -> str:
    token = normalize_text(value).strip()
    # A deliberately conservative stem used only to compare the explicit
    # Task IR label with an anchor label.  It is not a semantic ontology.
    return token[:-1] if len(token) > 3 and token.endswith("s") else token


def _tokens(value: str) -> list[str]:
    return [_singular_token(x) for x in re.findall(r"[a-z0-9]+", normalize_text(value))]


def _label_matches(text: str, label: str) -> bool:
    wanted = [_singular_token(x) for x in _tokens(label) if x]
    actual = _tokens(text)
    return bool(wanted) and all(token in actual for token in wanted)


def _iter_spans(obligation: dict[str, Any]) -> Iterable[dict[str, str]]:
    """Yield all textual Task IR spans with stable field provenance."""
    fields = (
        "locus", "subject", "subject_interval", "required_change", "scope",
        "source_relation", "condition", "result_property", "then_after",
        "occupancy_filter",
    )
    for field in fields:
        value = obligation.get(field)
        if isinstance(value, list):
            for index, item in enumerate(value):
                text = _field_text(item)
                if text:
                    yield {"field": field, "path": f"{field}[{index}]", "text": text}
        elif isinstance(value, dict) and field == "subject_interval":
            for bound in ("from", "to"):
                text = _field_text(value.get(bound))
                if text:
                    yield {"field": field, "path": f"{field}.{bound}", "text": text}
        else:
            text = _field_text(value)
            if text:
                yield {"field": field, "path": field, "text": text}


def _population_specs(obligation: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for span in _iter_spans(obligation):
        text = span["text"]
        norm = normalize_text(text)
        all_match = _ALL_THREE.search(norm)
        if all_match:
            label = _singular_token(all_match.group(1))
            specs.append({
                "population_label": label,
                "quantifier": "all",
                "allowed_members": list(ORDINALS),
                "member_interval": None,
                "introducing_field": span["field"],
                "introducing_path": span["path"],
                "introducing_span": text,
            })
            continue
        # Parse an explicit ordinal/member list only when all members in the
        # phrase share the same trailing label.  The pattern intentionally
        # does not infer membership from a bare scope word or a label match.
        member_list = _MEMBER_LIST.search(norm)
        if not member_list:
            continue
        label = _singular_token(member_list.group(1))
        allowed = _ORDINAL.findall(member_list.group(0))
        # A lone ordinal is commonly an ordinary qualifier (for example,
        # "the first table"), not a population/member restriction.  The
        # earned relation requires an explicit multi-member set; all-three is
        # handled separately above.
        if len(set(allowed)) < 2:
            continue
        specs.append({
            "population_label": label,
            "quantifier": "explicit_set",
            "allowed_members": [x for x in ORDINALS if x in set(allowed)],
            "member_interval": None,
            "introducing_field": span["field"],
            "introducing_path": span["path"],
            "introducing_span": text,
        })
    # A phrase can be repeated across fields.  Keep provenance stable while
    # avoiding duplicate candidate populations.
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for spec in specs:
        key = (
            spec["population_label"], tuple(spec["allowed_members"]),
            spec["introducing_field"], spec["introducing_path"],
        )
        if key not in seen:
            seen.add(key)
            result.append(spec)
    return result


def _anchor_member(anchor: dict[str, Any], label: str) -> str | None:
    match = _ORDINAL_LABEL.search(normalize_text(anchor.get("text") or ""))
    if not match or _singular_token(match.group(2)) != _singular_token(label):
        return None
    return match.group(1).casefold()


def _member_runs(occurrences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_column: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    by_row: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for item in occurrences:
        by_column[(item["sheet_id"], item["population_label"], item["col"])].append(item)
        by_row[(item["sheet_id"], item["row"], item["population_label"])].append(item)
    runs: list[dict[str, Any]] = []

    def add(group: list[dict[str, Any]], orientation: str) -> None:
        group = sorted(group, key=lambda x: x["col"] if orientation == "horizontal" else x["row"])
        windows = [group[i:i + 3] for i in range(max(1, len(group) - 2))] if len(group) >= 3 else [group]
        for window in windows:
            if len(window) != 3 or {x["member_identity"] for x in window} != set(ORDINALS):
                continue
            if orientation == "vertical":
                rows = [x["row"] for x in window]
                if rows != list(range(rows[0], rows[0] + 3)):
                    continue
            else:
                cols = [x["col"] for x in window]
                if not (cols[1] - cols[0] == cols[2] - cols[1] and cols[1] - cols[0] in (1, 2)):
                    continue
            run_id = f"{window[0]['sheet_id']}:{orientation}:" + ":".join(x["cell_id"] for x in window)
            runs.append({
                "run_id": run_id,
                "orientation": orientation,
                "cell_ids": [x["cell_id"] for x in window],
                "member_identities": [x["member_identity"] for x in window],
                "sheet_id": window[0]["sheet_id"],
                "start_row": min(x["row"] for x in window),
                "end_row": max(x["row"] for x in window),
                "start_col": min(x["col"] for x in window),
                "end_col": max(x["col"] for x in window),
            })

    for group in by_column.values():
        add(group, "vertical")
    # Horizontal runs are defined over the same population label on a row.
    for group in by_row.values():
        add(group, "horizontal")
    return sorted(runs, key=lambda x: x["run_id"])


def derive_population_member_relation(
    obligation: dict[str, Any],
    spine: dict[str, Any],
    *,
    locus_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Derive explicit member inclusion/exclusion without target aliasing."""
    specs = _population_specs(obligation)
    if locus_ids is None:
        locus_ids = {x["sheet_id"] for x in spine.get("sheets") or []}
    all_occurrences: list[dict[str, Any]] = []
    for spec in specs:
        for anchor in spine.get("text_anchors") or []:
            if anchor.get("sheet_id") not in locus_ids:
                continue
            member = _anchor_member(anchor, spec["population_label"])
            if member is None:
                continue
            all_occurrences.append({
                "cell_id": anchor["cell_id"],
                "anchor_id": anchor.get("id"),
                "sheet_id": anchor["sheet_id"],
                "address": anchor.get("address"),
                "text": anchor.get("text"),
                "row": anchor.get("row"),
                "col": anchor.get("col"),
                "population_label": spec["population_label"],
                "member_identity": member,
                "introducing_field": spec["introducing_field"],
                "introducing_path": spec["introducing_path"],
                "introducing_span": spec["introducing_span"],
                "population_quantifier": spec["quantifier"],
            })
    # Deduplicate by stable occurrence plus population.  An occurrence can be
    # supported by more than one explicit span; provenance is retained below.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in all_occurrences:
        key = (item["cell_id"], item["population_label"])
        if key not in unique:
            unique[key] = item
        else:
            prior = unique[key]
            prior.setdefault("provenance", []).append({
                "field": item["introducing_field"],
                "path": item["introducing_path"],
                "span": item["introducing_span"],
            })
    occurrences = list(unique.values())
    runs = _member_runs(occurrences)
    run_by_cell: dict[str, list[str]] = defaultdict(list)
    for run in runs:
        for cid in run["cell_ids"]:
            run_by_cell[cid].append(run["run_id"])
    for item in occurrences:
        item["repeated_block_context"] = {
            "run_ids": sorted(run_by_cell.get(item["cell_id"], [])),
            "occurrence_identity": item["cell_id"],
        }

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    normalized_specs: list[dict[str, Any]] = []
    for spec in specs:
        members = [x for x in occurrences if x["population_label"] == spec["population_label"]]
        observed = {x["member_identity"] for x in members}
        allowed = set(spec["allowed_members"])
        excluded_members = [x for x in ORDINALS if x in observed and x not in allowed]
        spec_record = dict(spec)
        spec_record.update({
            "observed_members": [x for x in ORDINALS if x in observed],
            "excluded_members": excluded_members,
            "occurrence_count": len(members),
        })
        normalized_specs.append(spec_record)
        for item in members:
            if item["member_identity"] in allowed:
                included.append(item)
            else:
                excluded.append(item)
    included = sorted({x["cell_id"]: x for x in included}.values(), key=lambda x: x["cell_id"])
    excluded = sorted({x["cell_id"]: x for x in excluded}.values(), key=lambda x: x["cell_id"])
    return {
        "active": bool(specs),
        "specifications": normalized_specs,
        "population_labels": sorted({x["population_label"] for x in specs}),
        "allowed_members": sorted({x["member_identity"] for x in included}, key=ORDINALS.index),
        "excluded_members": sorted({x["member_identity"] for x in excluded}, key=ORDINALS.index),
        "occurrences": sorted(occurrences, key=lambda x: x["cell_id"]),
        "included_occurrences": included,
        "excluded_occurrences": excluded,
        "repeated_block_runs": runs,
        "candidate_target_ids": [],
    }


def _formula_index(spine: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for formula in spine.get("formulas") or []:
        parsed = parse_cell_id(formula.get("cell_id") or "")
        if parsed is None:
            continue
        _, row, col = parsed
        result[formula["cell_id"]] = formula | {"row": row, "col": col}
    return result


def _point_out(spine: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in spine.get("point_deps") or []:
        result[edge.get("source_id")].append(edge)
    for edges in result.values():
        edges.sort(key=lambda x: (x.get("consumer_id") or "", x.get("type") or ""))
    return result


def _anchor_index(spine: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for anchor in spine.get("text_anchors") or []:
        result[(anchor.get("sheet_id"), anchor.get("col"))].append(anchor)
    return result


def derive_output_role_relation(
    spine: dict[str, Any],
    member_relation: dict[str, Any],
) -> dict[str, Any]:
    """Apply the accepted copied-header/Month/Numbers structural relation."""
    formulas = _formula_index(spine)
    point_out = _point_out(spine)
    anchors = _anchor_index(spine)
    endpoint_ids: set[str] = set()
    activations: list[dict[str, Any]] = []
    for start in member_relation.get("included_occurrences") or []:
        record: dict[str, Any] = {
            "start_cell_id": start["cell_id"],
            "start_address": start.get("address"),
            "member_identity": start.get("member_identity"),
            "population_label": start.get("population_label"),
            "introducing_field": start.get("introducing_field"),
            "introducing_path": start.get("introducing_path"),
            "occurrence_identity": start["cell_id"],
            "repeated_block_context": start.get("repeated_block_context") or {},
            "deterministic": True,
            "relation_sequence": [],
            "intermediate_nodes": [],
            "endpoints": [],
            "reason": None,
        }
        parsed_start = parse_cell_id(start["cell_id"])
        if parsed_start is None:
            record["reason"] = "invalid_start_identity"
            activations.append(record)
            continue
        start_sheet, start_row, start_col = parsed_start
        start_address = start.get("address") or _a1(start_row, start_col)
        copy_edges = []
        for edge in point_out.get(start["cell_id"], []):
            consumer = edge.get("consumer_id")
            parsed_consumer = parse_cell_id(consumer or "")
            if parsed_consumer is None or parsed_consumer[0] != start_sheet or parsed_consumer[2] != start_col:
                continue
            formula = formulas.get(consumer, {}).get("formula", "")
            if re.sub(r"\s+", "", formula).casefold() == ("=" + start_address).replace(" ", "").casefold():
                copy_edges.append((edge, parsed_consumer))
        if not copy_edges:
            record["reason"] = "no_exact_header_copy_dependency"
            activations.append(record)
            continue
        edge, parsed_copy = copy_edges[0]
        copy_id = edge["consumer_id"]
        copy_sheet, copy_row, copy_col = parsed_copy
        record["relation_sequence"].append("point_dependency_copied_header")
        record["intermediate_nodes"].append(copy_id)
        month_headers = [
            a for a in anchors.get((f"sheet:s{copy_sheet:02d}", copy_col), [])
            if a.get("row", 0) > copy_row and normalize_text(a.get("text") or "") == "month"
            and any(
                right.get("sheet_id") == a.get("sheet_id")
                and right.get("row") == a.get("row")
                and right.get("col") == a.get("col", 0) + 1
                and normalize_text(right.get("text") or "") == "numbers"
                for right in spine.get("text_anchors") or []
            )
        ]
        if not month_headers:
            record["reason"] = "no_month_numbers_repeated_header_pair"
            activations.append(record)
            continue
        month = min(month_headers, key=lambda x: (x.get("row", 0), x.get("cell_id", "")))
        month_id = month["cell_id"]
        numbers_id = next(
            right["cell_id"] for right in spine.get("text_anchors") or []
            if right.get("sheet_id") == month.get("sheet_id")
            and right.get("row") == month.get("row")
            and right.get("col") == month.get("col", 0) + 1
            and normalize_text(right.get("text") or "") == "numbers"
        )
        record["relation_sequence"].extend([
            "same_column_month_header", "right_neighbor_numbers_header",
            "contiguous_formula_bearing_month_extent",
        ])
        record["intermediate_nodes"].extend([month_id, numbers_id])
        formula_rows = sorted(
            f["row"] for f in formulas.values()
            if f.get("sheet_id") == month.get("sheet_id")
            and f.get("col") == month.get("col")
            and f.get("row", 0) > month.get("row", 0)
        )
        contiguous: list[int] = []
        for row in formula_rows:
            if not contiguous or row == contiguous[-1] + 1:
                contiguous.append(row)
            else:
                break
        record["source_formula_rows"] = contiguous
        for row in contiguous:
            endpoint = cell_id(copy_sheet, row, month["col"] + 1)
            if not id_in_spine(spine, endpoint):
                continue
            endpoint_ids.add(endpoint)
            record["endpoints"].append({
                "cell_id": endpoint,
                "address": _a1(row, month["col"] + 1),
                "sheet_id": f"sheet:s{copy_sheet:02d}",
                "role_evidence": {
                    "source_occurrence": start["cell_id"],
                    "copied_header": copy_id,
                    "month_header": month_id,
                    "numbers_header": numbers_id,
                    "same_column": month.get("col"),
                    "right_neighbor_column": month.get("col", 0) + 1,
                    "formula_bearing_rows": contiguous,
                },
            })
        if record["endpoints"]:
            record["reason"] = "structural_output_role_witnessed"
        else:
            record["reason"] = "no_formula_bearing_month_extent_in_spine"
        activations.append(record)
    result = {
        "active": bool(activations),
        "relation_name": "member_occurrence_to_month_numbers_formula_extent",
        "relation_definition": (
            "allowed member occurrence -> exact same-column copied-header point dependency "
            "-> same-column Month header -> right-neighbor Numbers header -> contiguous "
            "formula-bearing Month extent -> corresponding Numbers cells"
        ),
        "activations": sorted(activations, key=lambda x: x["start_cell_id"]),
        "candidate_endpoint_ids": sorted(endpoint_ids),
        "candidate_target_ids": sorted(endpoint_ids),
        "endpoint_count": len(endpoint_ids),
        "excluded_occurrence_ids": sorted(x["cell_id"] for x in member_relation.get("excluded_occurrences") or []),
        "uses_gold": False,
    }
    return result


def _a1(row: int, col: int) -> str:
    result = ""
    value = col
    while value:
        value, rem = divmod(value - 1, 26)
        result = chr(65 + rem) + result
    return f"{result}{row}"
