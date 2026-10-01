"""Zero-model O6 occurrence/output-role contrast.

The previous population/member artifact is treated as frozen input.  This
script does not parse member sets, call a planner, widen authority, or write a
workbook.  Gold is loaded only after candidate relations have been derived and
is used for measurement.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict, deque
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
FROZEN_PATH = ROOT / "population_member_relation_contrast.json"
SPINE_PATH = ROOT / (
    "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/"
    "workbook-grounding-probe/spines/05_01.json"
)
AUTHORITY_PATH = ROOT / "authority_loss_by_obligation.csv"
LIVE_RESULT = ROOT / (
    "benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/"
    "resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge/"
    "Financial_Model-05_01/result.json"
)
WORKBOOK_PATH = ROOT / (
    "benchmark-data/SpreadsheetBench-2/data/Financial_Model/spreadsheet/"
    "05_Project AIF/05_01_AIF_input.xlsx"
)
TASK = "Financial_Model:05_01"
OBLIGATION_ID = "O6"


def parse_rc(identifier: str) -> tuple[int, int]:
    match = re.search(r":r(\d+):c(\d+)$", identifier)
    if not match:
        raise ValueError(f"not a cell identifier: {identifier}")
    return int(match.group(1)), int(match.group(2))


def cell_id(sheet_id: str, row: int, col: int) -> str:
    return f"cell:{sheet_id.removeprefix('sheet:')}:r{row}:c{col}"


def formula_id(sheet_id: str, row: int, col: int) -> str:
    return f"formula:{sheet_id.removeprefix('sheet:')}:r{row}:c{col}"


def column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def address(row: int, col: int) -> str:
    return f"{column_name(col)}{row}"


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def json_text(value, **kwargs) -> str:
    return json.dumps(value, default=str, **kwargs)


def load_gold() -> set[str]:
    csv.field_size_limit(100_000_000)
    with AUTHORITY_PATH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["task"] == TASK and row["obligation_id"] == OBLIGATION_ID:
                return set(json.loads(row["gold_target_cells"]))
    raise AssertionError("O6 evaluator gold is not archived")


def target_id_map(spine: dict, targets: set[str]) -> dict[str, str]:
    result = {}
    for target in targets:
        title, target_address = target.rsplit("!", 1)
        match = re.match(r"([A-Z]+)(\d+)$", target_address)
        if not match:
            raise ValueError(target)
        letters, row_text = match.groups()
        col = 0
        for char in letters:
            col = col * 26 + ord(char) - 64
        result[target] = cell_id(
            f"sheet:s{spine['title_to_index'][title]:02d}", int(row_text), col
        )
    return result


def frozen_members() -> tuple[dict, list[dict], list[dict]]:
    frozen = json.loads(FROZEN_PATH.read_text())
    case = next(
        item
        for item in frozen["cases"]
        if item["task"] == TASK and item["obligation_id"] == OBLIGATION_ID
    )
    occurrences = case["workbook_occurrences"]
    included = [
        item
        for item in occurrences
        if item.get("population_relation_survives")
        and item["member_identity"] in {"second", "third"}
    ]
    excluded = [
        item for item in occurrences if item["member_identity"] == "first"
    ]
    assert {item["address"] for item in included} == {"G16", "G17", "F22", "H22"}
    assert {item["address"] for item in excluded} == {"G15", "D22"}
    return case, included, excluded


def build_indices(spine: dict) -> dict:
    text_by_cell = {item["cell_id"]: item for item in spine["text_anchors"]}
    formula_by_cell = {}
    formula_by_id = {}
    for item in spine["formulas"]:
        row, col = parse_rc(item["id"])
        formula_by_cell[item["cell_id"]] = item | {"row": row, "col": col}
        formula_by_id[item["id"]] = item | {"row": row, "col": col}
    occupied_by_cell = {item["id"]: item for item in spine["occupied"]}
    rows = {(item["sheet_id"], item["row"]): item for item in spine["rows"]}
    cols = {(item["sheet_id"], item["col"]): item for item in spine["cols"]}
    point_out = defaultdict(list)
    point_in = defaultdict(list)
    for item in spine["point_deps"]:
        point_out[item["source_id"]].append(item)
        point_in[item["consumer_id"]].append(item)
    return {
        "text_by_cell": text_by_cell,
        "formula_by_cell": formula_by_cell,
        "formula_by_id": formula_by_id,
        "occupied_by_cell": occupied_by_cell,
        "rows": rows,
        "cols": cols,
        "point_out": point_out,
        "point_in": point_in,
    }


def load_raw_styles():
    workbook = load_workbook(WORKBOOK_PATH, read_only=False, data_only=False)
    return workbook["Dashboard"]


def raw_cell_evidence(sheet, row: int, col: int) -> dict:
    cell = sheet.cell(row, col)
    return {
        "value": cell.value,
        "number_format": cell.number_format,
        "style_id": cell.style_id,
    }


def node_evidence(node: str, spine: dict, indices: dict, raw_sheet, packet_target_ids: set[str], gold_ids: set[str]) -> dict:
    row, col = parse_rc(node)
    text = indices["text_by_cell"].get(node)
    formula = indices["formula_by_cell"].get(node)
    occupied = indices["occupied_by_cell"].get(node)
    same_row_labels = [
        item["text"]
        for item in spine["text_anchors"]
        if item["sheet_id"] == "sheet:s00" and item["row"] == row
    ]
    prior_column_labels = [
        item["text"]
        for item in spine["text_anchors"]
        if item["sheet_id"] == "sheet:s00"
        and item["col"] == col
        and item["row"] < row
    ]
    return {
        "cell_id": node,
        "address": address(row, col),
        "row": row,
        "col": col,
        "text": text.get("text") if text else None,
        "formula": formula.get("formula") if formula else None,
        "fingerprint": formula.get("fingerprint") if formula else None,
        "formula_class_id": formula.get("class_id") if formula else None,
        "spine_occupancy_kind": occupied.get("kind") if occupied else "absent",
        "same_row_text_labels": same_row_labels,
        "prior_same_column_text_labels": prior_column_labels[-3:],
        "raw_workbook": raw_cell_evidence(raw_sheet, row, col),
        "current_packet_target": node in packet_target_ids,
        "gold_target_measurement": node in gold_ids,
        "incoming_point_dependency_count": len(indices["point_in"].get(node, [])),
        "outgoing_point_dependency_count": len(indices["point_out"].get(node, [])),
    }


def direct_closure(start: str, point_out: dict) -> dict[str, list[str]]:
    queue = deque([start])
    paths = {start: [start]}
    while queue:
        current = queue.popleft()
        for edge in point_out.get(current, []):
            consumer = edge["consumer_id"]
            if consumer not in paths:
                paths[consumer] = paths[current] + [consumer]
                queue.append(consumer)
    return {node: path for node, path in paths.items() if node != start}


def address_for_cell(spine: dict, node: str) -> str:
    sheet_id = node.split(":", 2)[1]
    row, col = parse_rc(node)
    title = next(sheet["title"] for sheet in spine["sheets"] if sheet["id"] == f"sheet:{sheet_id}")
    return f"{title}!{address(row, col)}"


def direct_candidate(name: str, starts: list[dict], indices: dict, spine: dict, raw_sheet, packet_target_ids: set[str], gold_ids: set[str]) -> dict:
    records = []
    for start in starts:
        closure = direct_closure(start["cell_id"], indices["point_out"])
        for endpoint, path in closure.items():
            records.append({
                "candidate": name,
                "start": start["cell_id"],
                "start_address": start["address"],
                "member_identity": start["member_identity"],
                "path": [address_for_cell(spine, item) for item in path],
                "relation_sequence": ["point_dependency"] * (len(path) - 1),
                "endpoint": endpoint,
                "endpoint_display": address_for_cell(spine, endpoint),
                "deterministic": True,
                "lexical_dependency": False,
                "dependency_direction": "source_to_consumer",
                "endpoint_role_evidence": node_evidence(endpoint, spine, indices, raw_sheet, packet_target_ids, gold_ids),
                "is_gold": endpoint in gold_ids,
                "false_endpoint": endpoint not in gold_ids,
            })
    return {
        "name": name,
        "records": records,
        "unique_endpoints": sorted({record["endpoint"] for record in records}),
    }


def adjacent_candidate(starts: list[dict], indices: dict, spine: dict, raw_sheet, packet_target_ids: set[str], gold_ids: set[str]) -> dict:
    records = []
    for start in starts:
        row, col = parse_rc(start["cell_id"])
        neighbor = cell_id("sheet:s00", row, col + 1)
        closure = direct_closure(neighbor, indices["point_out"])
        for endpoint, path in closure.items():
            full_path = [start["cell_id"]] + path
            records.append({
                "candidate": "adjacent_value_then_dependency_closure",
                "start": start["cell_id"],
                "start_address": start["address"],
                "member_identity": start["member_identity"],
                "path": [address_for_cell(spine, item) for item in full_path],
                "relation_sequence": ["same_row_right_neighbor"]
                + ["point_dependency"]
                + ["point_dependency"] * (len(path) - 2),
                "endpoint": endpoint,
                "endpoint_display": address_for_cell(spine, endpoint),
                "deterministic": True,
                "lexical_dependency": False,
                "dependency_direction": "source_to_consumer",
                "endpoint_role_evidence": node_evidence(endpoint, spine, indices, raw_sheet, packet_target_ids, gold_ids),
                "is_gold": endpoint in gold_ids,
                "false_endpoint": endpoint not in gold_ids,
            })
    return {
        "name": "adjacent_value_then_dependency_closure",
        "records": records,
        "unique_endpoints": sorted({record["endpoint"] for record in records}),
    }


def copied_header_path(start: dict, indices: dict, spine: dict, raw_sheet, packet_target_ids: set[str], gold_ids: set[str], accepted: bool) -> dict:
    result = {
        "start": start["cell_id"],
        "start_address": start["address"],
        "member_identity": start["member_identity"],
        "accepted_start": accepted,
        "deterministic": True,
        "lexical_dependency": False,
        "relation_sequence": [],
        "intermediate_nodes": [],
        "endpoints": [],
        "reason": None,
    }
    if start["row"] != 22 or start["col"] not in {4, 6, 8}:
        result["deterministic"] = True
        result["reason"] = "no_output_header_copy_dependency_from_this_occurrence"
        return result

    source_address = address(start["row"], start["col"])
    copy_edges = [
        edge
        for edge in indices["point_out"].get(start["cell_id"], [])
        if edge["consumer_id"].startswith("cell:s00:")
        and parse_rc(edge["consumer_id"])[1] == start["col"]
        and indices["formula_by_cell"].get(edge["consumer_id"], {}).get("formula", "").replace(" ", "")
        == f"={source_address}"
    ]
    if not copy_edges:
        result["reason"] = "no_exact_header_copy_dependency"
        return result
    copy_cell = copy_edges[0]["consumer_id"]
    copy_row, copy_col = parse_rc(copy_cell)
    result["relation_sequence"].append("point_dependency_header_copy")
    result["intermediate_nodes"].append(address_for_cell(spine, copy_cell))

    month_headers = [
        item
        for item in spine["text_anchors"]
        if item["sheet_id"] == "sheet:s00"
        and item["col"] == copy_col
        and item["row"] > copy_row
        and normalize(item["text"]) == "month"
        and any(
            sibling["sheet_id"] == "sheet:s00"
            and sibling["row"] == item["row"]
            and sibling["col"] == item["col"] + 1
            and normalize(sibling["text"]) == "numbers"
            for sibling in spine["text_anchors"]
        )
    ]
    if not month_headers:
        result["reason"] = "no_month_numbers_repeated_header_pair"
        return result
    month = min(month_headers, key=lambda item: item["row"])
    month_cell = month["cell_id"]
    numbers_cell = cell_id("sheet:s00", month["row"], month["col"] + 1)
    result["month_header"] = address_for_cell(spine, month_cell)
    result["numbers_header"] = address_for_cell(spine, numbers_cell)
    result["intermediate_nodes"].extend([result["month_header"], result["numbers_header"]])
    result["relation_sequence"].extend([
        "same_column_month_header",
        "right_neighbor_numbers_header",
        "contiguous_formula_bearing_month_rows",
    ])

    formula_rows = sorted(
        row
        for item in indices["formula_by_cell"].values()
        if item["sheet_id"] == "sheet:s00"
        and item["col"] == month["col"]
        and item["row"] > month["row"]
        for row in [item["row"]]
    )
    if formula_rows:
        contiguous_rows = [formula_rows[0]]
        for row in formula_rows[1:]:
            if row != contiguous_rows[-1] + 1:
                break
            contiguous_rows.append(row)
    else:
        contiguous_rows = []
    result["source_formula_rows"] = contiguous_rows
    for row in contiguous_rows:
        endpoint = cell_id("sheet:s00", row, month["col"] + 1)
        result["endpoints"].append({
            "endpoint": endpoint,
            "endpoint_display": address_for_cell(spine, endpoint),
            "endpoint_role_evidence": node_evidence(endpoint, spine, indices, raw_sheet, packet_target_ids, gold_ids),
            "is_gold": endpoint in gold_ids,
            "false_endpoint": endpoint not in gold_ids,
        })
    return result


def regions_for_targets(spine: dict, target_ids: set[str]) -> list[dict]:
    result = []
    target_coords = {parse_rc(target) for target in target_ids}
    for region in spine["regions"]:
        if region.get("sheet_id") != "sheet:s00":
            continue
        if region.get("row") is not None and any(
            row == region["row"] and col in region.get("cols", [])
            for row, col in target_coords
        ):
            result.append(region)
    return result


def case_result():
    frozen, included, excluded = frozen_members()
    spine = json.loads(SPINE_PATH.read_text())
    indices = build_indices(spine)
    result = json.loads(LIVE_RESULT.read_text())
    packet = result["edit_plan"]["packets"][OBLIGATION_ID]
    packet_target_ids = set(packet["target_cell_ids"])
    gold_display = load_gold()
    gold_id_map = target_id_map(spine, gold_display)
    gold_ids = set(gold_id_map.values())
    raw_sheet = load_raw_styles()

    direct = direct_candidate(
        "direct_point_dependency_closure",
        included,
        indices,
        spine,
        raw_sheet,
        packet_target_ids,
        gold_ids,
    )
    adjacent = adjacent_candidate(
        included,
        indices,
        spine,
        raw_sheet,
        packet_target_ids,
        gold_ids,
    )
    copied_paths = [
        copied_header_path(
            start,
            indices,
            spine,
            raw_sheet,
            packet_target_ids,
            gold_ids,
            accepted=start in included,
        )
        for start in included + excluded
    ]
    accepted_paths = [path for path in copied_paths if path["accepted_start"]]
    accepted_endpoints = {
        endpoint["endpoint"]
        for path in accepted_paths
        for endpoint in path["endpoints"]
    }
    counterfactual_excluded_endpoints = {
        endpoint["endpoint"]
        for path in copied_paths
        if not path["accepted_start"]
        for endpoint in path["endpoints"]
    }
    intermediate_nodes = {
        node
        for path in accepted_paths
        for node in path["intermediate_nodes"]
    }
    endpoint_reverse_dependencies = {
        endpoint: [
            {
                "source": address_for_cell(spine, edge["source_id"]),
                "consumer": address_for_cell(spine, edge["consumer_id"]),
                "type": edge["type"],
            }
            for edge in indices["point_out"].get(endpoint, [])
        ]
        for endpoint in accepted_endpoints
    }
    gold_target_diagnostics = [
        {
            "target": target,
            "cell_id": gold_id_map[target],
            "accepted_relation_endpoint": gold_id_map[target] in accepted_endpoints,
            "current_packet_target": gold_id_map[target] in packet_target_ids,
            "archived_authority_contains_target": False,
        }
        for target in sorted(gold_display)
    ]
    accepted_records = [
        {
            "candidate": "header_copy_month_numbers_formula_extent",
            "start": path["start"],
            "start_address": path["start_address"],
            "member_identity": path["member_identity"],
            "path": [path["start_address"]] + path["intermediate_nodes"] + [endpoint["endpoint_display"] for endpoint in path["endpoints"]],
            "relation_sequence": path["relation_sequence"],
            "endpoint": endpoint["endpoint"],
            "endpoint_display": endpoint["endpoint_display"],
            "deterministic": path["deterministic"],
            "lexical_dependency": path["lexical_dependency"],
            "dependency_direction": "source_to_consumer_for_header_copy_then_structural_output_role",
            "endpoint_role_evidence": endpoint["endpoint_role_evidence"],
            "is_gold": endpoint["is_gold"],
            "false_endpoint": endpoint["false_endpoint"],
        }
        for path in accepted_paths
        for endpoint in path["endpoints"]
    ]
    included_with_endpoints = {
        path["start"] for path in accepted_paths if path["endpoints"]
    }
    target_overlap = accepted_endpoints & gold_ids
    all_dependency_endpoints = set(direct["unique_endpoints"])
    return {
        "experiment": {
            "name": "output_role_occurrence_contrast",
            "mode": "zero-model evaluator-side static only",
            "model_calls": 0,
            "workbook_writes": 0,
            "runtime_grounding_changed": False,
            "planner_ab_launched": False,
            "gold_used_for_derivation": False,
        },
        "task": TASK,
        "obligation_id": OBLIGATION_ID,
        "task_ir": {
            "locus": frozen["obligation"]["locus"],
            "subject": frozen["obligation"]["subject"],
            "subject_interval": frozen["obligation"]["subject_interval"],
            "required_change": frozen["obligation"]["required_change"],
            "scope": frozen["obligation"]["scope"],
            "provenance": frozen["obligation"]["provenance"],
        },
        "frozen_member_relation": {
            "included": [item["address"] for item in included],
            "excluded": [item["address"] for item in excluded],
            "source_artifact": str(FROZEN_PATH),
        },
        "current_packet": {
            "target_count": len(packet_target_ids),
            "target_addresses": [address_for_cell(spine, node) for node in sorted(packet_target_ids)],
            "dependency_fact_count": len(packet["dependency_facts"]),
            "formula_class_fact_count": len(packet["formula_class_facts"]),
        },
        "gold": {
            "targets": sorted(gold_display),
            "count": len(gold_ids),
            "diagnostics": gold_target_diagnostics,
        },
        "candidate_relations": {
            "direct_point_dependency_closure": direct,
            "adjacent_value_then_dependency_closure": adjacent,
            "header_copy_month_numbers_formula_extent": {
                "paths": copied_paths,
                "accepted_endpoint_records": accepted_records,
                "accepted_endpoints": sorted(accepted_endpoints),
                "counterfactual_excluded_endpoints": sorted(counterfactual_excluded_endpoints),
                "intermediate_nodes": sorted(intermediate_nodes),
            },
        },
        "compiled_structure_audit": {
            "member_occurrence_ids": [item["cell_id"] for item in included + excluded],
            "header_copy_edges": [
                {
                    "source": address_for_cell(spine, edge["source_id"]),
                    "consumer": address_for_cell(spine, edge["consumer_id"]),
                    "type": edge["type"],
                }
                for edge in spine["point_deps"]
                if edge["source_id"] in {"cell:s00:r22:c4", "cell:s00:r22:c6", "cell:s00:r22:c8"}
                and edge["consumer_id"].startswith("cell:s00:")
            ],
            "formula_lineage": [
                {
                    "cell": address_for_cell(spine, item["cell_id"]),
                    "formula": item["formula"],
                    "fingerprint": item["fingerprint"],
                    "class_id": item["class_id"],
                }
                for item in indices["formula_by_cell"].values()
                if item["sheet_id"] == "sheet:s00"
                and item["col"] in {4, 6, 8}
                and item["row"] in range(40, 46)
            ],
            "regions_touching_accepted_targets": regions_for_targets(spine, accepted_endpoints),
            "accepted_endpoint_reverse_dependencies": endpoint_reverse_dependencies,
            "accepted_endpoint_occupancy": {
                address_for_cell(spine, endpoint): node_evidence(endpoint, spine, indices, raw_sheet, packet_target_ids, gold_ids)
                for endpoint in sorted(accepted_endpoints)
            },
            "gold_targets_are_spine_occupied": {
                target: indices["occupied_by_cell"].get(gold_id_map[target], {}).get("kind") not in {
                    None,
                    "blank",
                }
                for target in sorted(gold_display)
            },
            "gold_targets_have_spine_formulas": {
                target: bool(indices["formula_by_cell"].get(gold_id_map[target]))
                for target in sorted(gold_display)
            },
        },
        "metrics": {
            "included_member_occurrence_path_coverage": {
                "numerator": len(included_with_endpoints),
                "denominator": len(included),
                "value": len(included_with_endpoints) / len(included),
            },
            "included_member_endpoint_recall": len(target_overlap) / len(gold_ids),
            "target_cell_recall": len(target_overlap) / len(gold_ids),
            "target_precision": len(target_overlap) / len(accepted_endpoints),
            "false_endpoint_count": len(accepted_endpoints - gold_ids),
            "intermediate_non_target_downstream_false_positives": len(all_dependency_endpoints - gold_ids),
            "direct_dependency_endpoint_count": len(all_dependency_endpoints),
            "adjacent_dependency_endpoint_count": len(adjacent["unique_endpoints"]),
            "excluded_member_leakage": len(accepted_endpoints & counterfactual_excluded_endpoints),
            "counterfactual_excluded_member_endpoint_count": len(counterfactual_excluded_endpoints),
            "repeated_occurrence_confusion": len(
                accepted_endpoints
                & {
                    item["cell_id"]
                    for item in included
                    if item["address"] in {"G16", "G17"}
                }
            ),
            "one_relation_covers_all_required_outputs": accepted_endpoints == gold_ids,
            "accepted_endpoint_count": len(accepted_endpoints),
            "accepted_endpoints_in_current_packet": len(accepted_endpoints & packet_target_ids),
            "gold_targets_in_current_packet": len(gold_ids & packet_target_ids),
        },
        "interpretation": {
            "lineage_narrows_correct_occurrence_path": bool(accepted_endpoints),
            "final_role_is_deterministically_recoverable": accepted_endpoints == gold_ids,
            "relation_already_explicit_in_spine": False,
            "relation_components_already_latent": [
                "F22/H22 point dependencies to F40/H40",
                "Month/Numbers repeated headers",
                "formula-bearing Month-column row extents",
                "stable cell IDs and source-to-consumer direction",
            ],
            "new_derived_component": "header copy + Month/Numbers role + per-member formula-bearing row extent",
            "output_role_relation_status": "OUTPUT_ROLE_RELATION_EARNED_FOR_PLANNER_PROBE",
            "planner_only_ab_earned": True,
            "smallest_next_experiment": "planner-only O6 A/B with frozen member relation and the static header-copy/Month-Numbers relation as the only treatment change",
        },
    }


def csv_rows(data: dict) -> list[dict]:
    rows = []
    candidates = data["candidate_relations"]
    for name in ["direct_point_dependency_closure", "adjacent_value_then_dependency_closure"]:
        for record in candidates[name]["records"]:
            rows.append({
                "record_kind": "candidate_endpoint",
                "candidate": name,
                "start": record["start_address"],
                "member_identity": record["member_identity"],
                "path": json.dumps(record["path"]),
                "relation_sequence": json.dumps(record["relation_sequence"]),
                "endpoint": record["endpoint_display"],
                "endpoint_role_evidence": json_text(record["endpoint_role_evidence"], sort_keys=True),
                "deterministic": record["deterministic"],
                "dependency_direction": record["dependency_direction"],
                "current_packet_target": record["endpoint_role_evidence"]["current_packet_target"],
                "gold_measurement_only": True,
                "gold_endpoint": record["is_gold"],
                "false_endpoint": record["false_endpoint"],
                "blocked_by_member_restriction": False,
            })
    role = candidates["header_copy_month_numbers_formula_extent"]
    for record in role["accepted_endpoint_records"]:
        rows.append({
            "record_kind": "accepted_endpoint",
            "candidate": "header_copy_month_numbers_formula_extent",
            "start": record["start_address"],
            "member_identity": record["member_identity"],
            "path": json.dumps(record["path"]),
            "relation_sequence": json.dumps(record["relation_sequence"]),
            "endpoint": record["endpoint_display"],
            "endpoint_role_evidence": json_text(record["endpoint_role_evidence"], sort_keys=True),
            "deterministic": record["deterministic"],
            "dependency_direction": record["dependency_direction"],
            "current_packet_target": record["endpoint_role_evidence"]["current_packet_target"],
            "gold_measurement_only": True,
            "gold_endpoint": record["is_gold"],
            "false_endpoint": record["false_endpoint"],
            "blocked_by_member_restriction": False,
        })
    for path in role["paths"]:
        if path["accepted_start"]:
            continue
        for endpoint in path["endpoints"]:
            rows.append({
                "record_kind": "counterfactual_excluded_endpoint",
                "candidate": "header_copy_month_numbers_formula_extent",
                "start": path["start_address"],
                "member_identity": path["member_identity"],
                "path": json.dumps([path["start_address"]] + path["intermediate_nodes"] + [endpoint["endpoint_display"]]),
                "relation_sequence": json.dumps(path["relation_sequence"]),
                "endpoint": endpoint["endpoint_display"],
                "endpoint_role_evidence": json_text(endpoint["endpoint_role_evidence"], sort_keys=True),
                "deterministic": path["deterministic"],
                "dependency_direction": "source_to_consumer_for_header_copy_then_structural_output_role",
                "current_packet_target": endpoint["endpoint_role_evidence"]["current_packet_target"],
                "gold_measurement_only": True,
                "gold_endpoint": endpoint["is_gold"],
                "false_endpoint": endpoint["false_endpoint"],
                "blocked_by_member_restriction": True,
            })
    for key, value in data["metrics"].items():
        rows.append({
            "record_kind": "summary_metric",
            "candidate": key,
            "start": "",
            "member_identity": "",
            "path": "",
            "relation_sequence": "",
            "endpoint": "",
            "endpoint_role_evidence": "",
            "deterministic": "",
            "dependency_direction": "",
            "current_packet_target": "",
            "gold_measurement_only": True,
            "gold_endpoint": "",
            "false_endpoint": "",
            "blocked_by_member_restriction": "",
            "metric_value": json_text(value, sort_keys=True),
        })
    return rows


def write_outputs(destination: Path, data: dict):
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "output_role_occurrence_contrast.json").write_text(
        json_text(data, indent=2, sort_keys=True) + "\n"
    )
    rows = csv_rows(data)
    fields = sorted({field for row in rows for field in row})
    with (destination / "output_role_occurrence_contrast.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = case_result()
    write_outputs(args.output, data)
    print(json.dumps(data["metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
