"""Paired planner-only O6 output-role integration probe.

The archived O6 fragment is the frozen control context.  The treatment adds
only the five endpoints from the already accepted evaluator-side
header-copy/Month-Numbers/formula-extent relation and its input-side path
provenance.  This script makes exactly one sequential Edit Plan request per
condition and performs deterministic expansion only; it never invokes
retrieval, synthesis, scheduling, writing, LibreOffice, or scoring.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import fm_resource_feasibility as feasibility  # noqa: E402
import matched_compiled_treatment as m  # noqa: E402


TASK = "Financial_Model:05_01"
OBLIGATION_ID = "O6"
ARCHIVE = ROOT / (
    "benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/"
    "resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge/"
    "Financial_Model-05_01/result.json"
)
ROLE_CONTRAST = ROOT / "output_role_occurrence_contrast.json"
AUTHORITY_CENSUS = ROOT / "authority_loss_by_obligation.csv"
DATABASE = m.DATABASES / "Financial_Model-05_01.sqlite"
SHEET_NAMES: dict[str, str] = {}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_archived_context() -> tuple[dict[str, Any], dict[str, Any]]:
    archived = read_json(ARCHIVE)
    fragment = next(
        item for item in archived["edit_plan"]["fragments"] if item["obligation_id"] == OBLIGATION_ID
    )
    context = copy.deepcopy(fragment["context"])
    obligation = next(
        item for item in archived["compiler"]["obligations"] if item["id"] == OBLIGATION_ID
    )
    if fragment["status"] != "PROVIDER_TIMEOUT":
        raise AssertionError("The archived O6 control fragment is not the frozen pre-intervention fragment")
    if context["GENERATED_TASK_IR"]["obligations"] != [obligation]:
        raise AssertionError("Archived O6 context and compiler obligation differ")
    if context["GROUNDING"][OBLIGATION_ID]["targets"]["candidate_count"] != 24:
        raise AssertionError("Frozen O6 control packet no longer has 24 target candidates")
    return context, obligation


def role_provenance() -> tuple[list[str], dict[str, Any], set[str], set[str]]:
    """Load accepted relation records, dropping evaluator-only annotations."""
    contrast = read_json(ROLE_CONTRAST)
    relation = contrast["candidate_relations"]["header_copy_month_numbers_formula_extent"]
    records = relation["accepted_endpoint_records"]
    if len(records) != 5:
        raise AssertionError("Accepted output relation must contain exactly five endpoints")

    endpoint_ids = [record["endpoint"] for record in records]
    if len(set(endpoint_ids)) != 5:
        raise AssertionError("Accepted output relation endpoints are not unique")
    if any(record["member_identity"] not in {"second", "third"} for record in records):
        raise AssertionError("Treatment relation contains a non-included member")
    if any(record["start_address"] not in {"F22", "H22"} for record in records):
        raise AssertionError("Treatment relation does not preserve the accepted row-22 occurrences")

    # Only input-side relation facts are serialized.  In particular, the
    # accepted static artifact's is_gold/false_endpoint and
    # gold_target_measurement fields are never copied into the model context.
    provenance = []
    path_ids: set[str] = set()
    for record in records:
        path_ids.add(record["start"])
        path_ids.add(record["endpoint"])
        path_cell_ids = []
        for node in record["path"]:
            display = node if "!" in node else f"Dashboard!{node}"
            sheet, cell = display.rsplit("!", 1)
            letters = "".join(char for char in cell if char.isalpha())
            row = "".join(char for char in cell if char.isdigit())
            sheet_id = "s00" if sheet == "Dashboard" else None
            if sheet_id is not None:
                node_id = f"cell:{sheet_id}:r{int(row)}:c{_column_number(letters)}"
                path_cell_ids.append(node_id)
                path_ids.add(node_id)
        provenance.append(
            {
                "starting_member_occurrence": record["start_address"],
                "starting_member_cell_id": record["start"],
                "member_identity": record["member_identity"],
                "endpoint": record["endpoint_display"],
                "endpoint_cell_id": record["endpoint"],
                "path": record["path"],
                "path_cell_ids": path_cell_ids,
                "relation_sequence": record["relation_sequence"],
                "dependency_direction": record["dependency_direction"],
                "role_definition": {
                    "source_header": "Month",
                    "output_header": "Numbers",
                    "extent": "contiguous formula-bearing source-column rows",
                    "target_form": "corresponding output-column cells",
                },
            }
        )

        # The accepted paths use a bare Dashboard address for the start and
        # sheet-qualified addresses thereafter.  Endpoint/start IDs are the
        # only identities the planner needs to cite; path labels remain
        # provenance text and are not lexical aliases.

    counterfactual_first = set(relation["counterfactual_excluded_endpoints"])
    rejected_direct = {
        record["endpoint"]
        for record in contrast["candidate_relations"]["direct_point_dependency_closure"]["records"]
    }
    ticket_derived = {
        record["endpoint"]
        for record in contrast["candidate_relations"]["adjacent_value_then_dependency_closure"]["records"]
        if record["start_address"] in {"G16", "G17"}
    }
    evidence = {
        "relation_name": "header_copy_month_numbers_formula_extent",
        "selection_basis": "deterministic relation from frozen member occurrences and workbook structure",
        "provenance": provenance,
        "candidate_endpoint_ids": endpoint_ids,
        "candidate_endpoint_count": len(endpoint_ids),
    }
    return endpoint_ids, evidence, counterfactual_first, rejected_direct | ticket_derived


def _column_number(letters: str) -> int:
    result = 0
    for char in letters.upper():
        result = result * 26 + ord(char) - 64
    return result


def single_cell_regions(cell_ids: list[str]) -> list[dict[str, Any]]:
    result = []
    for cid in sorted(cell_ids):
        _, sheet, row, col = cid.split(":")
        result.append(
            {
                "kind": "RECTANGLE",
                "sheet_id": f"sheet:{sheet}",
                "r1": int(row[1:]),
                "c1": int(col[1:]),
                "r2": int(row[1:]),
                "c2": int(col[1:]),
            }
        )
    return result


def build_contexts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    control, obligation = load_archived_context()
    endpoint_ids, evidence, counterfactual_first, rejected_dependency = role_provenance()
    control_ground = control["GROUNDING"][OBLIGATION_ID]
    current_ids = set(control_ground["targets"]["foreground_cell_ids"])
    current_candidate_count = int(control_ground["targets"]["candidate_count"])
    if current_candidate_count != 24:
        raise AssertionError("Unexpected frozen O6 candidate count")
    if current_ids & set(endpoint_ids):
        raise AssertionError("A proposed treatment endpoint is already in the frozen control foreground")

    treatment = copy.deepcopy(control)
    treatment_ground = treatment["GROUNDING"][OBLIGATION_ID]
    treatment_targets = treatment_ground["targets"]
    treatment_targets["candidate_count"] = current_candidate_count + len(endpoint_ids)
    # Preserve every control foreground candidate and append only the accepted
    # endpoints.  The eight original tail candidates remain represented by the
    # same remainder handle and are not removed from the complete packet.
    treatment_targets["foreground_cell_ids"] = list(
        control_ground["targets"]["foreground_cell_ids"]
    ) + endpoint_ids
    treatment_targets["omitted_count"] = max(
        0, treatment_targets["candidate_count"] - len(treatment_targets["foreground_cell_ids"])
    )
    treatment_targets["region_summaries"] = list(control_ground["targets"]["region_summaries"]) + single_cell_regions(endpoint_ids)
    treatment_targets["region_summary_count"] = len(treatment_targets["region_summaries"])
    treatment_ground["output_role_evidence"] = evidence

    if treatment["RAW_TASK"] != control["RAW_TASK"]:
        raise AssertionError("Raw task changed between arms")
    if treatment["GENERATED_TASK_IR"] != control["GENERATED_TASK_IR"]:
        raise AssertionError("Task IR changed between arms")
    return control, treatment, {
        "endpoint_ids": endpoint_ids,
        "output_role_evidence": evidence,
        "counterfactual_first_endpoint_ids": sorted(counterfactual_first),
        "rejected_dependency_endpoint_ids": sorted(rejected_dependency),
        "obligation": obligation,
    }


def diff_values(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}" if path else key
            if key not in before or key not in after:
                result.append({"path": child, "before": before.get(key), "after": after.get(key)})
            else:
                result.extend(diff_values(before[key], after[key], child))
        return result
    if isinstance(before, list):
        if before == after:
            return []
        common = 0
        while common < min(len(before), len(after)) and before[common] == after[common]:
            common += 1
        if before[:common] == after[:common] and (len(before) != len(after)):
            return [
                {
                    "path": path,
                    "kind": "append_or_extend",
                    "before_length": len(before),
                    "after_length": len(after),
                    "appended": after[common:],
                }
            ]
        return [{"path": path, "before": before, "after": after}]
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def context_delta(control: dict[str, Any], treatment: dict[str, Any], endpoint_ids: list[str]) -> dict[str, Any]:
    differences = diff_values(control, treatment)
    allowed_prefixes = {
        "GROUNDING.O6.output_role_evidence",
        "GROUNDING.O6.targets.candidate_count",
        "GROUNDING.O6.targets.foreground_cell_ids",
        "GROUNDING.O6.targets.omitted_count",
        "GROUNDING.O6.targets.region_summaries",
        "GROUNDING.O6.targets.region_summary_count",
    }
    unexpected = [
        item
        for item in differences
        if not any(item["path"] == prefix or item["path"].startswith(prefix + ".") for prefix in allowed_prefixes)
    ]
    if unexpected:
        raise AssertionError(f"Unexpected treatment context changes: {unexpected[:2]}")
    return {
        "control_context_sha256": digest(control),
        "treatment_context_sha256": digest(treatment),
        "new_endpoint_ids": endpoint_ids,
        "changed_paths": differences,
        "unexpected_changes": unexpected,
        "non_output_role_context_equal": not unexpected,
        "control_target_candidate_count": control["GROUNDING"][OBLIGATION_ID]["targets"]["candidate_count"],
        "treatment_target_candidate_count": treatment["GROUNDING"][OBLIGATION_ID]["targets"]["candidate_count"],
    }


def state() -> dict[str, Any]:
    return {
        "task_id": TASK,
        "model": feasibility.MODEL,
        "provider": "openrouter",
        "reasoning": feasibility.REASONING,
        "top_p": feasibility.TOP_P,
        "temperature": feasibility.TEMPERATURE,
        "max_model_calls": 1,
        "max_cost_usd": feasibility.NATURAL_COST_CEILING,
        "frontend_mode": "sharded_projected",
        "model_call_count": 0,
        "provider_cost_usd": 0.0,
        "failure_ledger": [],
    }


def call_pair(output: Path, contexts: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    old_runtime = m.configure_runtime(
        max_model_calls=1,
        max_cost_usd=feasibility.NATURAL_COST_CEILING,
        frontend_mode="sharded_projected",
    )
    calls: dict[str, dict[str, Any]] = {}
    try:
        for condition in ("CONTROL", "TREATMENT"):
            task_dir = output / condition.lower()
            task_state = state()
            user = json.dumps(contexts[condition], ensure_ascii=False, separators=(",", ":"))
            call = m.call_or_stub(
                task_dir,
                TASK,
                "edit_plan",
                m.EDIT_PLAN_PROMPT,
                user,
                task_state,
                stub=False,
            )
            calls[condition] = {"call": call, "state": task_state, "user_payload": user}
            write_json(task_dir / "raw_request.json", call.get("request_body"))
            write_json(task_dir / "raw_response.json", call.get("raw_response_body"))
    finally:
        m.restore_runtime(old_runtime)
    return calls


def load_gold() -> set[str]:
    csv.field_size_limit(100_000_000)
    with AUTHORITY_CENSUS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["task"] == TASK and row["obligation_id"] == OBLIGATION_ID:
                # The evaluator file uses canonical compiled cell IDs for the
                # expanded authority column.  Gold target cells are supplied
                # as Dashboard addresses in this experiment's frozen contract.
                target_addresses = json.loads(row["gold_target_cells"])
                mapping = {"G43": "cell:s00:r43:c7", "I43": "cell:s00:r43:c9", "G44": "cell:s00:r44:c7", "I44": "cell:s00:r44:c9", "G45": "cell:s00:r45:c7"}
                return {mapping[address.rsplit("!", 1)[1]] for address in target_addresses}
    raise AssertionError("O6 evaluator gold not found")


def expand(call: dict[str, Any]) -> dict[str, Any]:
    parsed = call.get("parsed_response")
    result: dict[str, Any] = {
        "provider_failure_class": call.get("failure_class"),
        "parse_valid": isinstance(parsed, dict),
        "parsed_plan": parsed,
        "status": "NO_PARSED_PLAN",
        "cell_ids": [],
        "operations": [],
        "provenance": {},
        "expansion_error": None,
    }
    if not isinstance(parsed, dict):
        return result
    world = m.World(DATABASE)
    try:
        try:
            expanded = m.expand_edit_plan(parsed, world, {OBLIGATION_ID}, id_contract="V2")
            result.update(
                {
                    "status": expanded["status"],
                    "cell_ids": expanded.get("cell_ids", []),
                    "operations": expanded.get("operations", []),
                    "provenance": expanded.get("provenance", {}),
                }
            )
        except m.PlanError as exc:
            result["status"] = exc.category
            result["expansion_error"] = str(exc)
    finally:
        world.close()
    return result


def address(cid: str) -> str:
    _, sheet, row, col = cid.split(":")
    n = int(col[1:])
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{SHEET_NAMES.get(sheet, sheet)}!{letters}{int(row[1:])}"


def plan_operation_summary(plan: Any) -> list[dict[str, Any]]:
    if not isinstance(plan, dict):
        return []
    return [
        {
            "operation_id": op.get("operation_id"),
            "obligation_id": op.get("obligation_id"),
            "operation_kind": op.get("operation_kind"),
            "target_set": op.get("target_set"),
            "occupancy_filter": op.get("occupancy_filter"),
            "source_relation": op.get("source_relation"),
        }
        for op in plan.get("operations", [])
        if isinstance(op, dict)
    ]


def quality(expanded: dict[str, Any], gold: set[str]) -> dict[str, Any]:
    authority = set(expanded.get("cell_ids", []))
    overlap = authority & gold
    return {
        "authority_count": len(authority),
        "gold_count": len(gold),
        "recall": len(overlap) / len(gold) if gold else None,
        "precision": len(overlap) / len(authority) if authority else None,
        "true_positive_cells": sorted(address(cid) for cid in overlap),
        "false_positive_cells": sorted(address(cid) for cid in authority - gold),
        "false_negative_cells": sorted(address(cid) for cid in gold - authority),
    }


def source_relation_use(plan: Any, role_evidence: dict[str, Any]) -> dict[str, Any]:
    cited: set[str] = set()
    if isinstance(plan, dict):
        for operation in plan.get("operations", []):
            for eid in (operation.get("source_relation") or {}).get("entity_ids", []):
                cited.add(eid)
    endpoints = set(role_evidence["candidate_endpoint_ids"])
    starts = {item["starting_member_cell_id"] for item in role_evidence["provenance"]}
    path_ids = endpoints | starts | {
        path_id
        for item in role_evidence["provenance"]
        for path_id in item.get("path_cell_ids", [])
    }
    return {
        "source_relation_entity_ids": sorted(cited),
        "cited_new_output_endpoints": sorted(cited & endpoints),
        "cited_output_path_start_ids": sorted(cited & starts),
        "cited_role_path_ids": sorted(cited & path_ids),
        "uses_new_role_evidence": bool(cited & path_ids),
    }


def provider_status(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_attempted": bool(call.get("request_body")),
        "provider_success": call.get("failure_class") is None and call.get("raw_response_body") is not None,
        "failure_class": call.get("failure_class"),
        "finish_reason": call.get("finish_reason"),
        "parse_valid": isinstance(call.get("parsed_response"), dict),
        "raw_response_retained": call.get("raw_response_body") is not None,
        "model_call_count": call.get("call_index_within_task"),
        "provider_cost_usd": call.get("provider_cost_usd", 0.0),
    }


def request_delta(calls: dict[str, dict[str, Any]]) -> dict[str, Any]:
    control = calls["CONTROL"]["call"].get("request_body") or {}
    treatment = calls["TREATMENT"]["call"].get("request_body") or {}
    shared_keys = ("model", "temperature", "top_p", "reasoning", "provider", "max_tokens")
    config_equal = all(control.get(key) == treatment.get(key) for key in shared_keys)
    control_messages = control.get("messages") or []
    treatment_messages = treatment.get("messages") or []
    system_equal = bool(control_messages and treatment_messages and control_messages[0] == treatment_messages[0])
    control_user = control_messages[1].get("content", "") if len(control_messages) > 1 else ""
    treatment_user = treatment_messages[1].get("content", "") if len(treatment_messages) > 1 else ""
    return {
        "request_body_shared_config_equal": config_equal,
        "shared_config_keys": list(shared_keys),
        "system_prompt_equal": system_equal,
        "user_content_changed": control_user != treatment_user,
        "changed_request_components": ["messages[1].content"] if control_user != treatment_user else [],
        "control_request_sha256": calls["CONTROL"]["call"].get("request_sha256"),
        "treatment_request_sha256": calls["TREATMENT"]["call"].get("request_sha256"),
        "control_user_payload_sha256": calls["CONTROL"]["call"].get("user_payload_sha256"),
        "treatment_user_payload_sha256": calls["TREATMENT"]["call"].get("user_payload_sha256"),
        "non_user_request_components_equal": config_equal and system_equal,
    }


def verdict(
    statuses: dict[str, dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    safety: dict[str, Any],
) -> str:
    if any(not statuses[c]["provider_success"] for c in ("CONTROL", "TREATMENT")):
        return "PROVIDER_CENSORED"
    control = metrics["CONTROL"]
    treatment = metrics["TREATMENT"]
    if safety["treatment_first_tranche_leakage"] or safety["treatment_ticket_occurrence_leakage"]:
        return "OUTPUT_ROLE_PROJECTION_INTERFERENCE"
    control_precision = control["precision"] if control["precision"] is not None else 0.0
    treatment_precision = treatment["precision"] if treatment["precision"] is not None else 0.0
    improves = (
        (treatment["recall"] or 0.0) > (control["recall"] or 0.0)
        and treatment_precision >= control_precision
    ) or (
        (treatment["recall"] or 0.0) >= (control["recall"] or 0.0)
        and treatment_precision > control_precision
    )
    if improves:
        return "OUTPUT_ROLE_INTEGRATION_CASHES_OUT"
    return "OUTPUT_ROLE_EVIDENCE_NOT_USED"


def markdown_report(report: dict[str, Any]) -> str:
    q = report["quality"]
    safety = report["safety"]
    artifacts = report["artifacts"]
    lines = [
        "# Output-role planner live probe",
        "",
        f"Date: {report['date']}",
        "Mode: paired planner-only A/B; no retrieval, synthesis, scheduling, writes, LibreOffice, or scoring",
        f"Verdict: **`{report['causal_verdict']}`**",
        "",
        "## Result",
        "",
        "The control and treatment used the archived O6 planner context. Treatment added only the five accepted output-role endpoints and their deterministic path provenance. The paired provider status, parse status, and expanded authority are reported separately below.",
        "",
        "## Exact evidence delta",
        "",
        f"- Control context SHA-256: `{report['context_delta']['control_context_sha256']}`",
        f"- Treatment context SHA-256: `{report['context_delta']['treatment_context_sha256']}`",
        f"- New endpoint IDs: `{json.dumps(report['context_delta']['new_endpoint_ids'])}`",
        f"- Non-output-role context equal: `{report['context_delta']['non_output_role_context_equal']}`",
        f"- Target candidates: `{report['context_delta']['control_target_candidate_count']} → {report['context_delta']['treatment_target_candidate_count']}`",
        "",
        f"The complete context delta is in `{artifacts['context_diff']}`; the request-body comparison is in `{artifacts['request_diff']}`. The only request component changed is `messages[1].content`.",
        "",
        "## Frozen model calls",
        "",
        f"Model: `{report['freeze']['model']}`; reasoning `{report['freeze']['reasoning']}`; temperature `{report['freeze']['temperature']}`; top-p `{report['freeze']['top_p']}`; max tokens `{report['freeze']['max_tokens']}`.",
        f"Prompt SHA-256: `{report['freeze']['prompt_sha256']}`.",
        "",
        "| arm | provider attempted | provider success | failure | parse valid | finish | call count | cost USD |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for condition in ("CONTROL", "TREATMENT"):
        s = report["provider"][condition]
        lines.append(
            f"| {condition} | {s['provider_attempted']} | {s['provider_success']} | `{s['failure_class']}` | {s['parse_valid']} | `{s['finish_reason']}` | {s['model_call_count']} | {s['provider_cost_usd']} |"
        )
    lines.extend(["", f"Raw request/response ledgers are retained in `{artifacts['request_response']}` and each arm's `raw_request.json`, `raw_response.json`, and `calls/001_edit_plan.json`.", ""])

    lines.extend(["## Returned plans and expanded authority", ""])
    for condition in ("CONTROL", "TREATMENT"):
        lines.append(f"### {condition}")
        lines.append("")
        lines.append("Returned operations:")
        lines.append("```json")
        lines.append(json.dumps(report["returned_plan_summaries"][condition], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
        lines.append(f"Expansion status: `{report['expanded_authority'][condition]['status']}`")
        lines.append(f"Expanded operation count: `{len(report['expanded_authority'][condition]['operations'])}`")
        lines.append(f"Expanded target forms: `{json.dumps([op.get('target_set') for op in report['returned_plan_summaries'][condition]], ensure_ascii=False)}`")
        lines.append(f"Authority ({len(report['expanded_authority'][condition]['cells'])} cells): `{json.dumps(report['expanded_authority'][condition]['cells'])}`")
        lines.append("")

    lines.extend([
        "## Authority comparison",
        "",
        f"Gold target cells: `{json.dumps(report['gold_targets'])}`",
        "",
        "| arm | authority | recall | precision | FP count | FN count |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for condition in ("CONTROL", "TREATMENT"):
        x = q[condition]
        lines.append(
            f"| {condition} | {x['authority_count']} | {x['recall']} | {x['precision']} | {len(x['false_positive_cells'])} | {len(x['false_negative_cells'])} |"
        )
    lines.extend([
        "",
        f"- Control-only cells: `{json.dumps(report['authority_delta']['control_only_cells'])}`",
        f"- Treatment-only cells: `{json.dumps(report['authority_delta']['treatment_only_cells'])}`",
        f"- Shared cells: `{json.dumps(report['authority_delta']['shared_cells'])}`",
        f"- CONTROL false positives: `{json.dumps(q['CONTROL']['false_positive_cells'])}`",
        f"- CONTROL false negatives: `{json.dumps(q['CONTROL']['false_negative_cells'])}`",
        f"- TREATMENT false positives: `{json.dumps(q['TREATMENT']['false_positive_cells'])}`",
        f"- TREATMENT false negatives: `{json.dumps(q['TREATMENT']['false_negative_cells'])}`",
        f"- The same comparison is machine-readable in `{artifacts['authority_json']}` / `{artifacts['authority_csv']}`.",
        "",
        "## Safety and role-evidence checks",
        "",
        f"- First-Tranche counterfactual endpoints in treatment authority: `{json.dumps(safety['treatment_first_tranche_leakage'])}`",
        f"- Ticket Size-derived endpoints in treatment authority: `{json.dumps(safety['treatment_ticket_occurrence_leakage'])}`",
        f"- Rejected direct/adjacent dependency endpoints in treatment authority: `{json.dumps(safety['treatment_rejected_dependency_leakage'])}`",
        f"- Output endpoints introduced: `{json.dumps(safety['treatment_output_endpoint_intersection'])}`",
        f"- Treatment source-relation use: `{report['source_relation_use']['TREATMENT']['uses_new_role_evidence']}`",
        f"- Treatment cited new endpoints: `{json.dumps(report['source_relation_use']['TREATMENT']['cited_new_output_endpoints'])}`",
        "",
        "The member restriction was held fixed. No First-Tranche path was added, and G16/G17 were not aliased to the F22/H22 row-22 occurrence. Dependency-connected cells were not exposed as treatment targets beyond the five accepted endpoints.",
        "",
        "## Causal interpretation",
        "",
        f"`{report['causal_verdict']}`. This result, if provider-successful, establishes only whether this deterministic composition is planner-useful for `Financial_Model:05_01 O6`; it does not establish a general output-role ontology or justify runtime integration across the benchmark.",
        "",
        "## Smallest next experiment",
        "",
        report["smallest_next_experiment"],
        "",
        "## Artifacts",
        "",
        f"- `{artifacts['authority_json']}` / `{artifacts['authority_csv']}`",
        f"- `{artifacts['request_response']}`",
        f"- `{artifacts['request_diff']}`",
        f"- `{artifacts['context_diff']}`",
        f"- `{artifacts['live_dir']}/`",
    ])
    return "\n".join(lines) + "\n"


def saved_calls(output: Path, contexts: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    calls: dict[str, dict[str, Any]] = {}
    for condition in ("CONTROL", "TREATMENT"):
        task_dir = output / condition.lower()
        call = read_json(task_dir / "calls/001_edit_plan.json")
        calls[condition] = {
            "call": call,
            "state": read_json(task_dir / "state.json"),
            "user_payload": json.dumps(contexts[condition], ensure_ascii=False, separators=(",", ":")),
        }
    return calls


def artifact_names(prefix: str, output: Path) -> dict[str, str]:
    return {
        "report": f"{prefix.upper()}_LIVE_PROBE_REPORT.md",
        "authority_json": f"{prefix}_authority_comparison.json",
        "authority_csv": f"{prefix}_authority_comparison.csv",
        "request_response": f"{prefix}_request_response_ledger.json",
        "request_diff": f"{prefix}_request_diff.json",
        "context_diff": f"{prefix}_context_diff.json",
        "live_dir": output.name,
    }


def run(output: Path, *, reuse_calls: bool = False, artifact_prefix: str = "output_role_planner") -> dict[str, Any]:
    if not ARCHIVE.is_file() or not ROLE_CONTRAST.is_file() or not DATABASE.is_file():
        raise FileNotFoundError("Frozen O6 archive, output-role contrast, and compiled database are required")
    control_context, treatment_context, static = build_contexts()
    artifacts = artifact_names(artifact_prefix, output)
    SHEET_NAMES.clear()
    SHEET_NAMES.update({row[2].removeprefix("sheet:"): row[0] for row in control_context["SHEETS"]["rows"]})
    delta = context_delta(control_context, treatment_context, static["endpoint_ids"])
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "control_context.json", control_context)
    write_json(output / "treatment_context.json", treatment_context)
    write_json(output / "context_diff.json", delta)

    # The archived request proves the prompt/config contract.  No model call
    # is made until both contexts and their mechanical diff are persisted.
    archived = read_json(ARCHIVE)
    archived_fragment = next(x for x in archived["edit_plan"]["fragments"] if x["obligation_id"] == OBLIGATION_ID)
    archived_request = archived_fragment["call"]["request_body"]
    if archived_request["messages"][0]["content"] != m.EDIT_PLAN_PROMPT:
        raise AssertionError("Current Edit Plan prompt differs from archived O6 prompt")
    for key in ("model", "temperature", "top_p", "reasoning", "provider", "max_tokens"):
        expected = {
            "model": feasibility.MODEL,
            "temperature": feasibility.TEMPERATURE,
            "top_p": feasibility.TOP_P,
            "reasoning": {"effort": feasibility.REASONING},
            "provider": feasibility.PROVIDER_POLICY,
            "max_tokens": feasibility.MAX_OUTPUT_TOKENS,
        }[key]
        if archived_request.get(key) != expected:
            raise AssertionError(f"Archived model configuration differs at {key}")

    contexts = {"CONTROL": control_context, "TREATMENT": treatment_context}
    if reuse_calls:
        calls = saved_calls(output, contexts)
    else:
        calls = call_pair(output, contexts)
    # Gold is loaded only after both model inputs were persisted and both calls
    # have been attempted; it is measurement-only and never enters a request.
    gold = load_gold()
    expanded = {condition: expand(calls[condition]["call"]) for condition in ("CONTROL", "TREATMENT")}
    metrics = {condition: quality(expanded[condition], gold) for condition in ("CONTROL", "TREATMENT")}

    control_authority = set(expanded["CONTROL"]["cell_ids"])
    treatment_authority = set(expanded["TREATMENT"]["cell_ids"])
    first = set(static["counterfactual_first_endpoint_ids"])
    rejected = set(static["rejected_dependency_endpoint_ids"])
    ticket = {
        record["endpoint"]
        for record in read_json(ROLE_CONTRAST)["candidate_relations"]["adjacent_value_then_dependency_closure"]["records"]
        if record["start_address"] in {"G16", "G17"}
    }
    output_endpoints = set(static["endpoint_ids"])
    safety = {
        "control_first_tranche_leakage": sorted(address(cid) for cid in control_authority & first),
        "treatment_first_tranche_leakage": sorted(address(cid) for cid in treatment_authority & first),
        "control_ticket_occurrence_leakage": sorted(address(cid) for cid in control_authority & ticket),
        "treatment_ticket_occurrence_leakage": sorted(address(cid) for cid in treatment_authority & ticket),
        "control_rejected_dependency_leakage": sorted(address(cid) for cid in control_authority & rejected),
        "treatment_rejected_dependency_leakage": sorted(address(cid) for cid in treatment_authority & rejected),
        "treatment_output_endpoint_intersection": sorted(address(cid) for cid in treatment_authority & output_endpoints),
    }
    statuses = {condition: provider_status(calls[condition]["call"]) for condition in ("CONTROL", "TREATMENT")}
    source_use = {
        condition: source_relation_use(calls[condition]["call"].get("parsed_response"), static["output_role_evidence"])
        for condition in ("CONTROL", "TREATMENT")
    }
    expanded_authority = {
        condition: {
            "status": expanded[condition]["status"],
            "cells": sorted(address(cid) for cid in set(expanded[condition]["cell_ids"])),
            "cell_ids": sorted(set(expanded[condition]["cell_ids"])),
            "operations": expanded[condition]["operations"],
            "provenance": expanded[condition]["provenance"],
            "expansion_error": expanded[condition]["expansion_error"],
        }
        for condition in ("CONTROL", "TREATMENT")
    }
    comparison_rows = []
    for condition in ("CONTROL", "TREATMENT"):
        x = metrics[condition]
        comparison_rows.append(
            {
                "task": TASK,
                "obligation_id": OBLIGATION_ID,
                "condition": condition,
                "provider_success": statuses[condition]["provider_success"],
                "parse_valid": statuses[condition]["parse_valid"],
                "expansion_status": expanded[condition]["status"],
                "authority_count": x["authority_count"],
                "gold_count": x["gold_count"],
                "recall": x["recall"],
                "precision": x["precision"],
                "false_positive_count": len(x["false_positive_cells"]),
                "false_negative_count": len(x["false_negative_cells"]),
                "false_positive_cells": x["false_positive_cells"],
                "false_negative_cells": x["false_negative_cells"],
                "operation_count": len(expanded[condition]["operations"]),
                "operation_target_forms": [op.get("target_set") for op in expanded[condition]["operations"]],
            }
        )
    authority_delta = {
        "control_only_cells": sorted(address(cid) for cid in control_authority - treatment_authority),
        "treatment_only_cells": sorted(address(cid) for cid in treatment_authority - control_authority),
        "shared_cells": sorted(address(cid) for cid in control_authority & treatment_authority),
    }
    causal_verdict = verdict(statuses, metrics, safety)
    if causal_verdict == "PROVIDER_CENSORED":
        next_experiment = "Do not interpret the treatment authority causally and do not integrate runtime grounding. Repeat this identical two-arm O6 probe only as a fresh paired run after provider health supports two bounded calls; never retry one arm asymmetrically."
    elif causal_verdict == "OUTPUT_ROLE_INTEGRATION_CASHES_OUT":
        next_experiment = "Keep runtime grounding unchanged and run the smallest static cross-task test of this exact structural family before considering runtime integration."
    else:
        next_experiment = "Keep runtime grounding unchanged and isolate the model-selection or evidence-projection failure with static analysis before any further live probe."
    report = {
        "experiment": "output_role_planner_live_probe",
        "date": "2026-09-14",
        "task": TASK,
        "obligation_id": OBLIGATION_ID,
        "model_calls": 2,
        "downstream_calls": {"retrieval": 0, "synthesis": 0},
        "scheduler": "frozen",
        "workbook_writes": 0,
        "libreoffice_runs": 0,
        "scoring_runs": 0,
        "conditions": {
            "CONTROL": "archived repaired O6 planner context before output-role intervention",
            "TREATMENT": "identical context plus five accepted endpoints and minimum path provenance",
        },
        "artifacts": artifacts,
        "freeze": {
            "model": feasibility.MODEL,
            "provider": "openrouter",
            "reasoning": feasibility.REASONING,
            "temperature": feasibility.TEMPERATURE,
            "top_p": feasibility.TOP_P,
            "max_tokens": feasibility.MAX_OUTPUT_TOKENS,
            "prompt_sha256": digest(m.EDIT_PLAN_PROMPT),
            "schema_sha256": digest(m.EDIT_PLAN_SCHEMA),
            "control_task_ir_sha256": digest(control_context["GENERATED_TASK_IR"]),
            "treatment_task_ir_sha256": digest(treatment_context["GENERATED_TASK_IR"]),
            "member_relation": "frozen",
            "temporal_evidence": "frozen",
            "retrieval_synthesis_scheduler_writes": "not invoked",
        },
        "context_delta": delta,
        "provider": statuses,
        "parse_validity": {condition: statuses[condition]["parse_valid"] for condition in ("CONTROL", "TREATMENT")},
        "returned_plans": {condition: calls[condition]["call"].get("parsed_response") for condition in ("CONTROL", "TREATMENT")},
        "returned_plan_summaries": {condition: plan_operation_summary(calls[condition]["call"].get("parsed_response")) for condition in ("CONTROL", "TREATMENT")},
        "expanded_authority": expanded_authority,
        "gold_targets": sorted(address(cid) for cid in gold),
        "quality": metrics,
        "authority_delta": authority_delta,
        "safety": safety,
        "source_relation_use": source_use,
        "raw_ledger_paths": {
            "CONTROL": f"{output.name}/control/calls/001_edit_plan.json",
            "TREATMENT": f"{output.name}/treatment/calls/001_edit_plan.json",
        },
        "request_delta": request_delta(calls),
        "causal_verdict": causal_verdict,
        "smallest_next_experiment": next_experiment,
    }
    write_json(ROOT / artifacts["authority_json"], {"rows": comparison_rows, "authority_delta": authority_delta, "safety": safety})
    with (ROOT / artifacts["authority_csv"]).open("w", newline="", encoding="utf-8") as handle:
        fields = sorted({key for row in comparison_rows for key in row})
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in comparison_rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    ledger = {
        "CONTROL": {
            "request_body": calls["CONTROL"]["call"].get("request_body"),
            "raw_response_body": calls["CONTROL"]["call"].get("raw_response_body"),
            "raw_response_text": calls["CONTROL"]["call"].get("raw_response_text"),
            "request_sha256": calls["CONTROL"]["call"].get("request_sha256"),
            "user_payload_sha256": calls["CONTROL"]["call"].get("user_payload_sha256"),
            "status": statuses["CONTROL"],
        },
        "TREATMENT": {
            "request_body": calls["TREATMENT"]["call"].get("request_body"),
            "raw_response_body": calls["TREATMENT"]["call"].get("raw_response_body"),
            "raw_response_text": calls["TREATMENT"]["call"].get("raw_response_text"),
            "request_sha256": calls["TREATMENT"]["call"].get("request_sha256"),
            "user_payload_sha256": calls["TREATMENT"]["call"].get("user_payload_sha256"),
            "status": statuses["TREATMENT"],
        },
    }
    write_json(ROOT / artifacts["request_response"], ledger)
    write_json(ROOT / artifacts["request_diff"], report["request_delta"])
    write_json(ROOT / artifacts["context_diff"], delta)
    (ROOT / artifacts["report"]).write_text(markdown_report(report), encoding="utf-8")
    write_json(output / "report.json", report)
    print(json.dumps({key: report[key] for key in ("provider", "quality", "authority_delta", "safety", "source_relation_use", "causal_verdict")}, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output_role_planner_live_probe")
    parser.add_argument("--from-saved", action="store_true", help="Regenerate artifacts from the two persisted calls without making provider requests")
    parser.add_argument("--artifact-prefix", default="output_role_planner", help="Prefix for root report/comparison artifacts")
    args = parser.parse_args()
    run(args.output, reuse_calls=args.from_saved, artifact_prefix=args.artifact_prefix)
