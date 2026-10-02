"""Static, evaluator-side population/member relation contrast.

This experiment deliberately stops before runtime grounding, planning, authority
expansion, scheduling, synthesis, or workbook I/O.  It reads archived Task IR,
the archived lexical shadow, compiled workbook spines, archived packet counts,
and evaluator gold only for measurement.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPINE_DIR = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/workbook-grounding-probe/spines"
)
LINEAGE_PATH = ROOT / "research/history/authority_frontier_probe/obligation_lineage.csv"
SHADOW_PATH = ROOT / "research/history/authority_frontier_probe/scope_label_shadow.json"
AUTHORITY_PATH = ROOT / "research/history/loose_evidence/authority_loss_by_obligation.csv"
LIVE_DIR = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/"
    "resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge"
)

CASES = [
    ("Financial_Model:05_01", "O7"),
    ("Financial_Model:05_01", "O6"),
    ("Financial_Model:01_01", "O5"),
]
ORDINALS = ("first", "second", "third")


def normalize(value: str) -> str:
    value = value.casefold().replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def semantic_tokens(value: str) -> tuple[str, ...]:
    """Compare labels while treating a simple trailing plural as equivalent."""
    tokens = []
    for token in normalize(value).split():
        if len(token) > 3 and token.endswith("s"):
            token = token[:-1]
        tokens.append(token)
    return tuple(tokens)


def column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def address(row: int, col: int) -> str:
    return f"{column_name(col)}{row}"


def parse_rc(identifier: str) -> tuple[int, int]:
    match = re.search(r":r(\d+):c(\d+)$", identifier)
    if not match:
        raise ValueError(f"not a cell-like identifier: {identifier}")
    return int(match.group(1)), int(match.group(2))


def cell_id(sheet_id: str, row: int, col: int) -> str:
    return f"cell:{sheet_id.removeprefix('sheet:')}:r{row}:c{col}"


def compact(value):
    if isinstance(value, list):
        return [compact(v) for v in value]
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items()}
    return value


def load_json(path: Path):
    return json.loads(path.read_text())


def load_inputs():
    csv.field_size_limit(100_000_000)
    lineage = {}
    with LINEAGE_PATH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            lineage[(row["task"], row["obligation_id"])] = row
    shadows = {
        (row["task"], row["obligation_id"]): row
        for row in load_json(SHADOW_PATH)
    }
    gold = {}
    with AUTHORITY_PATH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["row_type"] != "OBLIGATION":
                continue
            cells = []
            if row["gold_target_cells"]:
                cells = json.loads(row["gold_target_cells"])
            gold[(row["task"], row["obligation_id"])] = {
                "cells": cells,
                "count": int(row["gold_target_count"] or 0),
                "authority_cells": json.loads(row["expanded_authority_cells"] or "[]"),
                "authority_count": int(row["authority_count"] or 0),
            }
    return lineage, shadows, gold


def packet_cell_ids(task: str, obligation_id: str) -> set[str]:
    path = LIVE_DIR / task.replace(":", "-") / "result.json"
    if not path.exists():
        return set()
    result = load_json(path)
    packet = result.get("edit_plan", {}).get("packets", {}).get(obligation_id, {})
    found = set()

    def walk(value):
        if isinstance(value, str) and value.startswith("cell:"):
            found.add(value)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(packet)
    return found


def packet_target_ids(task: str, obligation_id: str) -> set[str]:
    path = LIVE_DIR / task.replace(":", "-") / "result.json"
    if not path.exists():
        return set()
    result = load_json(path)
    packet = result.get("edit_plan", {}).get("packets", {}).get(obligation_id, {})
    return set(packet.get("target_cell_ids", []))


def target_id_map(spine: dict, targets: list[str]) -> dict[str, str]:
    title_to_index = spine["title_to_index"]
    result = {}
    for target in targets:
        title, target_address = target.rsplit("!", 1)
        row, col = re.match(r"([A-Z]+)(\d+)$", target_address).groups()
        col_number = 0
        for char in row:
            col_number = col_number * 26 + ord(char) - 64
        result[target] = cell_id(
            f"sheet:s{title_to_index[title]:02d}", int(col), col_number
        )
    return result


def gold_ids(spine: dict, gold_record: dict | None, field: str = "cells") -> set[str]:
    if not gold_record:
        return set()
    result = target_id_map(spine, gold_record[field])
    return set(result.values())


def parse_population(obligation: dict) -> dict:
    spans = [("scope", span["text"]) for span in obligation.get("scope", [])]
    for field, text in spans:
        value = normalize(text)
        if "tranche" in value:
            members = [ordinal for ordinal in ORDINALS if ordinal in value]
            if "all three" in value:
                members = list(ORDINALS)
                quantifier = "all"
            else:
                quantifier = "explicit_set"
            return {
                "introducing_field": field,
                "introducing_span": text,
                "population_label": "tranche",
                "quantifier": quantifier,
                "allowed_members": members,
                "excluded_members": [],
                "member_interval": None,
            }
        match = re.search(r"for each (.+?) line items?$", value)
        if match:
            label = match.group(1).strip()
            return {
                "introducing_field": field,
                "introducing_span": text,
                "population_label": label,
                "quantifier": "each",
                "allowed_members": [],
                "excluded_members": [],
                "member_interval": None,
            }
    return {
        "introducing_field": None,
        "introducing_span": None,
        "population_label": None,
        "quantifier": None,
        "allowed_members": [],
        "excluded_members": [],
        "member_interval": None,
    }


def add_interval_context(population: dict, obligation: dict) -> dict:
    interval = obligation.get("subject_interval")
    if interval:
        population["member_interval"] = {
            "from": interval.get("from", {}).get("text"),
            "to": interval.get("to", {}).get("text"),
            "introducing_field": "subject_interval",
        }
    if population["population_label"] == "tranche" and population["allowed_members"]:
        observed = set(ORDINALS)
        population["excluded_members"] = sorted(
            observed - set(population["allowed_members"]),
            key=ORDINALS.index,
        )
    return population


def parse_member(text: str) -> str | None:
    match = re.match(r"\s*(first|second|third)\s+tranche\b", text.casefold())
    return match.group(1) if match else None


def anchors_by_cell(spine: dict) -> dict[str, dict]:
    return {anchor["cell_id"]: anchor for anchor in spine["text_anchors"]}


def build_member_runs(anchors: list[dict]) -> list[dict]:
    members = [anchor for anchor in anchors if parse_member(anchor["text"])]
    runs = []
    by_column = defaultdict(list)
    by_row = defaultdict(list)
    for anchor in members:
        by_column[(anchor["sheet_id"], anchor["col"])].append(anchor)
        by_row[(anchor["sheet_id"], anchor["row"])].append(anchor)

    def append_run(group, orientation):
        group = sorted(group, key=lambda item: item["col"] if orientation == "horizontal" else item["row"])
        if len(group) > 3:
            windows = [group[index : index + 3] for index in range(len(group) - 2)]
        else:
            windows = [group]
        for window in windows:
            append_one_run(window, orientation)

    def append_one_run(group, orientation):
        if len(group) != 3 or {parse_member(item["text"]) for item in group} != set(ORDINALS):
            return
        coordinates = [(item["row"], item["col"]) for item in group]
        if orientation == "vertical" and [r for r, _ in coordinates] != list(range(coordinates[0][0], coordinates[0][0] + 3)):
            return
        if orientation == "horizontal":
            cols = [c for _, c in coordinates]
            if not (cols[1] - cols[0] == cols[2] - cols[1] and cols[1] - cols[0] in (1, 2)):
                return
        run_id = f"{group[0]['sheet_id']}:{orientation}:" + ":".join(
            address(item["row"], item["col"]) for item in group
        )
        runs.append({
            "run_id": run_id,
            "orientation": orientation,
            "anchor_ids": [item["id"] for item in group],
            "cell_ids": [item["cell_id"] for item in group],
            "sheet_id": group[0]["sheet_id"],
            "start_row": min(item["row"] for item in group),
            "end_row": max(item["row"] for item in group),
            "start_col": min(item["col"] for item in group),
            "end_col": max(item["col"] for item in group),
        })

    for group in by_column.values():
        append_run(group, "vertical")
    for group in by_row.values():
        append_run(group, "horizontal")
    return runs


def row4_axis_columns(spine: dict, sheet_id: str) -> list[int]:
    period_cols = [
        period["col"]
        for period in spine["periods"]
        if period["sheet_id"] == sheet_id and period["row"] == 4
    ]
    formula_cols = []
    for formula in spine["formulas"]:
        if formula["sheet_id"] != sheet_id:
            continue
        row, col = parse_rc(formula["id"])
        if row == 4:
            formula_cols.append(col)
    if not period_cols:
        return []
    start = min(period_cols)
    end = max([col for col in formula_cols if col >= start] + period_cols)
    return list(range(start, end + 1))


def sheet_title_map(spine: dict) -> dict[str, str]:
    return {sheet["id"]: sheet["title"] for sheet in spine["sheets"]}


def locus_sheet_ids(spine: dict, locus: str) -> set[str]:
    wanted = semantic_tokens(locus)
    return {
        sheet["id"]
        for sheet in spine["sheets"]
        if semantic_tokens(sheet["title"]) == wanted
    }


def shadow_occurrences(shadow: dict, spine: dict) -> list[dict]:
    anchors = anchors_by_cell(spine)
    result = []
    for hit in shadow.get("extra_scope_label_hits", []):
        anchor = anchors.get(hit["cell_id"], {})
        result.append({
            "cell_id": hit["cell_id"],
            "anchor_id": hit["id"],
            "sheet_id": hit["sheet_id"],
            "address": hit["address"],
            "text": hit["text"],
            "rules": hit.get("rules", []),
            "member_identity": parse_member(hit["text"]),
            "row": anchor.get("row"),
            "col": anchor.get("col"),
        })
    return result


def workbook_occurrences(spine: dict, population: dict, locus_ids: set[str]) -> list[dict]:
    label = semantic_tokens(population["population_label"] or "")
    result = []
    for anchor in spine["text_anchors"]:
        if anchor["sheet_id"] not in locus_ids:
            continue
        member = parse_member(anchor["text"])
        if label == ("tranche",):
            if member is None:
                continue
        elif label and not all(
            token in semantic_tokens(anchor["text"]) for token in label
        ):
            # Population labels are allowed to be a multiword span; the
            # lexical shadow remains the source of control-case occurrences.
            continue
        result.append({
            "cell_id": anchor["cell_id"],
            "anchor_id": anchor["id"],
            "sheet_id": anchor["sheet_id"],
            "address": anchor["address"],
            "text": anchor["text"],
            "member_identity": member,
            "row": anchor["row"],
            "col": anchor["col"],
        })
    return result


def occurrence_context(occurrence: dict, runs: list[dict], anchors: dict[str, dict]) -> dict:
    run = next((run for run in runs if occurrence["cell_id"] in run["cell_ids"]), None)
    if run:
        context = {
            "run_id": run["run_id"],
            "orientation": run["orientation"],
            "member_run_extent": [run["start_row"], run["end_row"]],
            "member_run_columns": [run["start_col"], run["end_col"]],
            "parent_context_anchor": None,
        }
        if run["orientation"] == "vertical":
            parent_row = run["start_row"] - 2
            parent = next(
                (
                    item
                    for item in anchors.values()
                    if item.get("sheet_id") == occurrence["sheet_id"]
                    and item.get("row") == parent_row
                    and item.get("col") == run["start_col"]
                ),
                None,
            )
            if parent:
                context["parent_context_anchor"] = {
                    "cell_id": parent["cell_id"],
                    "address": parent["address"],
                    "text": parent["text"],
                }
        return context
    return {
        "run_id": None,
        "orientation": None,
        "member_run_extent": None,
        "member_run_columns": None,
        "parent_context_anchor": None,
    }


def packet_contains(occurrence: dict, packet_ids: set[str]) -> bool:
    return occurrence["cell_id"] in packet_ids


def target_ids_for_o7(spine: dict, selected: list[dict]) -> set[str]:
    if not selected:
        return set()
    sheet_id = selected[0]["sheet_id"]
    columns = row4_axis_columns(spine, sheet_id)
    return {
        cell_id(sheet_id, occurrence["row"], col)
        for occurrence in selected
        for col in columns
    }


def o7_role_selected(occurrences: list[dict], runs: list[dict], obligation: dict) -> list[dict]:
    subject_tokens = semantic_tokens(obligation["subject"]["text"])
    selected = []
    for run in runs:
        if run["orientation"] != "vertical":
            continue
        if not all(cell in {item["cell_id"] for item in occurrences} for cell in run["cell_ids"]):
            continue
        if semantic_tokens(run.get("parent_text", "")) == subject_tokens:
            selected.extend(item for item in occurrences if item["cell_id"] in run["cell_ids"])
    return selected


def derive_case(task: str, obligation_id: str, lineage_row: dict, shadow: dict, gold_record: dict | None) -> dict:
    obligation = json.loads(lineage_row["raw_obligation"])
    spine = load_json(SPINE_DIR / f"{task.split(':', 1)[1]}.json")
    titles = sheet_title_map(spine)
    population = add_interval_context(parse_population(obligation), obligation)
    locus_ids = locus_sheet_ids(spine, obligation.get("locus", {}).get("text", ""))
    anchors = anchors_by_cell(spine)
    runs = build_member_runs(spine["text_anchors"])
    for run in runs:
        if run["orientation"] == "vertical":
            parent_row = run["start_row"] - 2
            parent = next(
                (
                    anchor
                    for anchor in spine["text_anchors"]
                    if anchor["sheet_id"] == run["sheet_id"]
                    and anchor["row"] == parent_row
                    and anchor["col"] == run["start_col"]
                ),
                None,
            )
            run["parent_text"] = parent["text"] if parent else None

    shadow_rows = shadow_occurrences(shadow, spine)
    all_occurrences = workbook_occurrences(spine, population, locus_ids)
    for occurrence in all_occurrences:
        occurrence["sheet_title"] = titles[occurrence["sheet_id"]]
        occurrence["repeated_block_context"] = occurrence_context(occurrence, runs, anchors)
        occurrence["spine_fact_present"] = True
        occurrence["planner_packet_contains_occurrence"] = packet_contains(
            occurrence, packet_cell_ids(task, obligation_id)
        )

    allowed = set(population["allowed_members"])
    excluded = set(population["excluded_members"])
    member_survivors = [
        item
        for item in all_occurrences
        if population["population_label"] != "tranche"
        or item["member_identity"] in allowed
    ]
    excluded_survivors = [
        item for item in member_survivors if item["member_identity"] in excluded
    ]

    role_selected = []
    target_ids = set()
    role_status = "UNRESOLVED"
    relation_uses_gold = False
    if task == "Financial_Model:05_01" and obligation_id == "O7":
        role_selected = o7_role_selected(member_survivors, runs, obligation)
        target_ids = target_ids_for_o7(spine, role_selected)
        role_status = "DERIVED_FROM_SUBJECT_PARENT_AND_MEMBER_RUN"
    elif task == "Financial_Model:05_01" and obligation_id == "O6":
        role_status = "UNRESOLVED_OUTPUT_ROLE"
    elif task == "Financial_Model:01_01" and obligation_id == "O5":
        role_status = "UNRESOLVED_LINE_ITEM_ROLE"

    selected_ids = {row["cell_id"] for row in role_selected}
    gold_cell_ids = gold_ids(spine, gold_record)
    authority_cell_ids = gold_ids(spine, gold_record, "authority_cells")
    packet_target_cell_ids = packet_target_ids(task, obligation_id)
    gold_target_map = (
        target_id_map(spine, gold_record["cells"]) if gold_record else {}
    )
    existing_metrics = json.loads(lineage_row["metrics"])
    before_target_count = existing_metrics["temporal_and_percentage_fix"]["target_candidates"]

    for row in shadow_rows:
        row["sheet_title"] = titles[row["sheet_id"]]
        row["population_relation_survives"] = row["cell_id"] in {
            item["cell_id"] for item in member_survivors
        }
        row["role_relation_survives"] = row["cell_id"] in selected_ids
        row["false_positive_class"] = None
        if row["cell_id"] not in selected_ids:
            if row["cell_id"] in gold_cell_ids:
                row["false_positive_class"] = "not_gold_target_occurrence"
            elif row["member_identity"] in excluded:
                row["false_positive_class"] = "excluded_member"
            elif row["sheet_id"] not in locus_ids:
                row["false_positive_class"] = "wrong_locus_or_repeated_semantic_block"
            elif task == "Financial_Model:05_01" and obligation_id == "O7":
                row["false_positive_class"] = "wrong_repeated_block"
            else:
                row["false_positive_class"] = "population_label_not_target_role"

    occurrence_map = {row["cell_id"]: row for row in shadow_rows}
    for occurrence in all_occurrences:
        row = occurrence_map.setdefault(
            occurrence["cell_id"],
            {
                "cell_id": occurrence["cell_id"],
                "anchor_id": occurrence["anchor_id"],
                "sheet_id": occurrence["sheet_id"],
                "address": occurrence["address"],
                "text": occurrence["text"],
                "rules": [],
                "member_identity": occurrence["member_identity"],
                "row": occurrence["row"],
                "col": occurrence["col"],
                "sheet_title": occurrence["sheet_title"],
            },
        )
        row.update({
            "population_relation_survives": occurrence["cell_id"]
            in {item["cell_id"] for item in member_survivors},
            "role_relation_survives": occurrence["cell_id"] in selected_ids,
            "repeated_block_context": occurrence["repeated_block_context"],
            "spine_fact_present": occurrence["spine_fact_present"],
            "planner_packet_contains_occurrence": occurrence[
                "planner_packet_contains_occurrence"
            ],
        })
        if "false_positive_class" not in row:
            row["false_positive_class"] = None

    all_occurrence_rows = sorted(occurrence_map.values(), key=lambda row: (row["sheet_id"], row["row"], row["col"]))
    allowed_observed = [
        item for item in all_occurrences
        if population["population_label"] != "tranche"
        or item["member_identity"] in allowed
    ]
    role_gold_overlap = target_ids & gold_cell_ids
    included_precision = (
        len([item for item in member_survivors if item["member_identity"] in allowed])
        / len(member_survivors)
        if member_survivors and population["population_label"] == "tranche"
        else None
    )
    member_recall = (
        len([item for item in member_survivors if item["member_identity"] in allowed])
        / len(allowed_observed)
        if population["population_label"] == "tranche" and allowed_observed
        else None
    )
    if task == "Financial_Model:05_01" and obligation_id == "O7":
        # Gold is used here only as an evaluator-side measurement.  The
        # selected rows themselves were derived from Task IR subject + spine
        # parent anchor + ordinal run, above.
        gold_member_rows = {
            re.sub(r":c\d+$", ":c2", item)
            for item in gold_cell_ids
        }
        selected_member_rows = {
            re.sub(r":c\d+$", ":c2", item)
            for item in selected_ids
        }
        occurrence_precision = (
            len(selected_member_rows & gold_member_rows) / len(selected_member_rows)
            if selected_member_rows
            else None
        )
        gold_block_recall = len(role_gold_overlap) / len(gold_cell_ids) if gold_cell_ids else None
    elif task == "Financial_Model:05_01" and obligation_id == "O6":
        # The member set preserves both Dashboard runs, but this experiment
        # intentionally does not infer which output role/column is intended.
        occurrence_precision = None
        gold_block_recall = None
    else:
        occurrence_precision = None
        gold_block_recall = None

    point_deps = [
        dep for dep in spine["point_deps"]
        if dep.get("source_id") in {item["cell_id"] for item in all_occurrences}
        or dep.get("consumer_id") in {item["cell_id"] for item in all_occurrences}
    ]
    if task == "Financial_Model:05_01" and obligation_id == "O6":
        point_deps = [
            dep for dep in spine["point_deps"]
            if dep.get("source_id") in {"cell:s00:r22:c6", "cell:s00:r22:c8"}
            or dep.get("consumer_id") in {"cell:s00:r40:c6", "cell:s00:r40:c8"}
        ]

    return {
        "task": task,
        "obligation_id": obligation_id,
        "obligation": obligation,
        "population": population,
        "locus_sheet_ids": sorted(locus_ids),
        "locus_sheet_titles": [titles[sheet_id] for sheet_id in sorted(locus_ids)],
        "deterministic_relation": {
            "provenance": "introducing Task IR scope span; no field union",
            "population_label": "normalized population label must match",
            "member_identity": "leading ordinal + tranche label from a text anchor",
            "restriction": "explicit allowed set; observed member domain minus allowed set is excluded",
            "occurrence_identity": "cell ID plus same-row/same-column ordinal run; never lexical-label union",
            "role_filter": "O7 only: vertical run's two-row-prior same-column anchor matches subject after simple plural normalization",
            "target_expansion": "O7 only: selected member rows crossed with existing row-4 period-axis extent",
        },
        "lexical_shadow": {
            "hit_count": len(shadow_rows),
            "occurrences": shadow_rows,
        },
        "workbook_occurrences": all_occurrence_rows,
        "member_relation_survivor_count": len(member_survivors),
        "member_relation_survivor_ids": [item["cell_id"] for item in member_survivors],
        "excluded_member_survivor_count": len(excluded_survivors),
        "role_relation_survivor_count": len(role_selected),
        "role_relation_survivor_ids": [item["cell_id"] for item in role_selected],
        "candidate_target_population": sorted(target_ids),
        "candidate_target_population_status": role_status,
        "existing_packet_target_candidate_count": before_target_count,
        "gold_target_cells": sorted(gold_cell_ids),
        "gold_target_count": len(gold_cell_ids) if gold_record else None,
        "archived_authority_count": len(authority_cell_ids),
        "archived_authority_gold_overlap": len(authority_cell_ids & gold_cell_ids),
        "gold_target_diagnostics": [
            {
                "target": target,
                "relation_candidate": target_id in target_ids,
                "archived_packet_target": target_id in packet_target_cell_ids,
                "archived_authority_contains_target": target_id in authority_cell_ids,
            }
            for target, target_id in sorted(gold_target_map.items())
        ],
        "metrics": {
            "member_recall": member_recall,
            "included_member_precision": included_precision,
            "excluded_member_false_positives": len(excluded_survivors),
            "repeated_block_occurrence_precision": occurrence_precision,
            "repeated_occurrence_identity_preserved": len({
                item["cell_id"] for item in all_occurrences
            }) == len(all_occurrences),
            "gold_target_block_recall": gold_block_recall,
            "lexical_shadow_hits": len(shadow_rows),
            "member_restriction_survivors": len(member_survivors),
            "role_filtered_survivors": len(role_selected),
            "wrong_locus_shadow_hits_rejected": len([
                item for item in shadow_rows if item["sheet_id"] not in locus_ids
            ]),
            "gold_candidate_intersection": len(role_gold_overlap),
        },
        "latent_facts": {
            "task_ir_population_span_present": bool(population["introducing_span"]),
            "task_ir_allowed_set_structured": False,
            "task_ir_interval_present": bool(population["member_interval"]),
            "spine_population_occurrences_present": bool(all_occurrences),
            "spine_member_labels_present": any(
                item["member_identity"] is not None for item in all_occurrences
            ),
            "spine_repeated_runs_present": bool(runs),
            "spine_output_occurrence_dependency_present": bool(point_deps),
            "occurrence_dependencies": compact(point_deps),
            "planner_packet_contains_any_member_occurrence": any(
                item["planner_packet_contains_occurrence"] for item in all_occurrences
            ),
            "required_relation_status": (
                "new_derived_restriction_and_occurrence_relation"
                if population["population_label"] == "tranche"
                else "new_derived_locus_and_population_occurrence_relation"
            ),
            "relation_uses_evaluator_gold": relation_uses_gold,
        },
    }


def csv_rows(cases: list[dict]) -> list[dict]:
    rows = []
    for case in cases:
        for occurrence in case["workbook_occurrences"]:
            shadow = next(
                (
                    item
                    for item in case["lexical_shadow"]["occurrences"]
                    if item["cell_id"] == occurrence["cell_id"]
                ),
                {},
            )
            rows.append({
                "record_kind": "occurrence",
                "task": case["task"],
                "obligation_id": case["obligation_id"],
                "introducing_field": case["population"]["introducing_field"],
                "introducing_span": case["population"]["introducing_span"],
                "population_label": case["population"]["population_label"],
                "allowed_members": json.dumps(case["population"]["allowed_members"]),
                "excluded_members": json.dumps(case["population"]["excluded_members"]),
                "member_identity": occurrence["member_identity"],
                "workbook_occurrence": occurrence["cell_id"],
                "sheet_title": occurrence["sheet_title"],
                "address": occurrence["address"],
                "text": occurrence["text"],
                "repeated_block_context": json.dumps(occurrence.get("repeated_block_context"), sort_keys=True),
                "lexical_shadow_hit": occurrence["cell_id"] in {item["cell_id"] for item in case["lexical_shadow"]["occurrences"]},
                "lexical_shadow_rules": json.dumps(shadow.get("rules", [])),
                "population_relation_survives": occurrence.get("population_relation_survives", False),
                "role_relation_survives": occurrence.get("role_relation_survives", False),
                "planner_packet_contains_occurrence": occurrence.get("planner_packet_contains_occurrence", False),
                "false_positive_class": shadow.get("false_positive_class"),
                "candidate_target_population_status": case["candidate_target_population_status"],
                "evidence": "text anchor in compiled spine; provenance retained as scope",
            })
        for target in case["gold_target_diagnostics"]:
            rows.append({
                "record_kind": "gold_target",
                "task": case["task"],
                "obligation_id": case["obligation_id"],
                "introducing_field": case["population"]["introducing_field"],
                "introducing_span": case["population"]["introducing_span"],
                "population_label": case["population"]["population_label"],
                "allowed_members": json.dumps(case["population"]["allowed_members"]),
                "excluded_members": json.dumps(case["population"]["excluded_members"]),
                "member_identity": "",
                "workbook_occurrence": target["target"],
                "sheet_title": "",
                "address": "",
                "text": "",
                "repeated_block_context": "",
                "lexical_shadow_hit": "",
                "lexical_shadow_rules": "",
                "population_relation_survives": target["relation_candidate"],
                "role_relation_survives": target["relation_candidate"],
                "planner_packet_contains_occurrence": target["archived_packet_target"],
                "false_positive_class": (
                    None if target["relation_candidate"] else "missed_by_static_relation"
                ),
                "candidate_target_population_status": case["candidate_target_population_status"],
                "evidence": json.dumps({
                    "archived_authority_contains_target": target[
                        "archived_authority_contains_target"
                    ],
                    "archived_packet_target": target["archived_packet_target"],
                    "relation_candidate": target["relation_candidate"],
                }, sort_keys=True),
            })
        rows.append({
            "record_kind": "case_summary",
            "task": case["task"],
            "obligation_id": case["obligation_id"],
            "introducing_field": case["population"]["introducing_field"],
            "introducing_span": case["population"]["introducing_span"],
            "population_label": case["population"]["population_label"],
            "allowed_members": json.dumps(case["population"]["allowed_members"]),
            "excluded_members": json.dumps(case["population"]["excluded_members"]),
            "member_identity": "",
            "workbook_occurrence": "",
            "sheet_title": "; ".join(case["locus_sheet_titles"]),
            "address": "",
            "text": "",
            "repeated_block_context": "",
            "lexical_shadow_hit": "",
            "lexical_shadow_rules": "",
            "population_relation_survives": case["metrics"]["member_restriction_survivors"],
            "role_relation_survives": case["metrics"]["role_filtered_survivors"],
            "planner_packet_contains_occurrence": "",
            "false_positive_class": "",
            "candidate_target_population_status": case["candidate_target_population_status"],
            "evidence": json.dumps({
                "archived_authority_count": case["archived_authority_count"],
                "archived_authority_gold_overlap": case[
                    "archived_authority_gold_overlap"
                ],
                "metrics": case["metrics"],
            }, sort_keys=True),
        })
    return rows


def write_outputs(destination: Path, cases: list[dict]):
    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": {
            "name": "population_member_relation_contrast",
            "mode": "zero-model evaluator-side static only",
            "model_calls": 0,
            "workbook_writes": 0,
            "authority_widening": False,
            "runtime_grounding_changed": False,
            "cases": [f"{task} {obligation_id}" for task, obligation_id in CASES],
        },
        "cases": cases,
    }
    (destination / "population_member_relation_contrast.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    rows = csv_rows(cases)
    fields = sorted({field for row in rows for field in row})
    with (destination / "population_member_relation_contrast.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lineage, shadows, gold = load_inputs()
    cases = []
    for task, obligation_id in CASES:
        key = (task, obligation_id)
        cases.append(
            derive_case(
                task,
                obligation_id,
                lineage[key],
                shadows[key],
                gold.get(key),
            )
        )
    write_outputs(args.output, cases)
    print(json.dumps({
        f"{case['task']} {case['obligation_id']}": case["metrics"]
        for case in cases
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
