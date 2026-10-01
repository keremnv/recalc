"""Deterministic model-facing projection for the compiled Edit Plan frontend.

The workbook grounding spine remains complete and persistent.  This module only
constructs a bounded representation for a particular Edit Plan request.  Every
omitted candidate is represented by a stable remainder handle and remains
available in the authoritative packet/world used by deterministic expansion.
"""
from __future__ import annotations

from collections import defaultdict
import json
from typing import Any, Iterable

import edit_plan_probe


RULE_WEIGHT = {
    "exact_norm": 100,
    "compact": 80,
    "token_subset": 70,
    "substring": 60,
    "jaccard": 50,
    "token_prefix": 40,
}


def _rank(hit: dict[str, Any]) -> tuple[int, int, int]:
    """Rank only by already-recorded mechanical match evidence."""
    rules = [str(x) for x in hit.get("rules") or []]
    weights = sorted((RULE_WEIGHT.get(x, 0) for x in rules), reverse=True)
    return (weights[0] if weights else 0, sum(weights), len(rules))


def _stable_key(hit: Any) -> str:
    return json.dumps(hit, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _foreground(items: Iterable[dict[str, Any]], limit: int) -> tuple[list[dict[str, Any]], int]:
    values = [dict(x) for x in items]
    values.sort(key=lambda x: (-_rank(x)[0], -_rank(x)[1], -_rank(x)[2], _stable_key(x)))
    if len(values) <= limit:
        return values, 0
    # Preserve all candidates tied at the boundary only when they fit in the
    # bounded foreground.  The omitted tail is never silently promoted to a
    # hidden authoritative top-k list.
    cut = max(0, limit)
    if cut and cut < len(values):
        boundary = _rank(values[cut - 1])
        while cut < len(values) and _rank(values[cut]) == boundary and cut < limit + 8:
            cut += 1
    return values[:cut], len(values) - cut


def _candidate_view(hit: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id", "cell_id", "row_id", "col_id", "sheet_id", "text", "title",
        "address", "period_key", "header_text", "axis", "period", "encoding_class",
        "query", "rules", "neighbor_left", "neighbor_right", "formula_id",
        "class_id", "opaque", "source_id", "consumer_id", "cross_sheet",
    )
    return {k: hit[k] for k in keep if k in hit}


def _regions(target_ids: list[str], limit: int = 96) -> list[dict[str, Any]]:
    if not target_ids:
        return []
    try:
        regions = edit_plan_probe.rectangle_cover(set(target_ids))
    except Exception:
        regions = []
    # The rectangle cover is a lossless mechanical summary.  A bounded view is
    # merely a prompt-size guard; the complete IDs remain in the packet/world.
    return regions[:limit]


def project_packet(
    obligation: dict[str, Any],
    packet: dict[str, Any],
    *,
    foreground_limit: int = 8,
    target_foreground_limit: int = 16,
    region_limit: int = 128,
) -> dict[str, Any]:
    """Create a compact, ambiguity-preserving view of one complete packet."""
    result: dict[str, Any] = {
        "obligation_id": obligation.get("id"),
        "fields": {k: obligation.get(k) for k in (
            "id", "locus", "subject", "subject_interval", "required_change", "scope",
            "source_relation", "condition", "result_property", "then_after", "occupancy_filter",
        )},
        "complete_world_packet": {
            "candidate_counts": packet.get("counts") or {},
            "remainder_namespace": f"grounding:{obligation.get('id')}",
        },
    }
    for field in ("locus", "subject", "scope", "source"):
        foreground, omitted = _foreground(packet.get(field) or [], foreground_limit)
        result[field] = {
            "foreground": [_candidate_view(x) for x in foreground],
            "candidate_count": len(packet.get(field) or []),
            "omitted_count": omitted,
            "remainder_handle": f"grounding:{obligation.get('id')}:{field}:tail" if omitted else None,
            "selection_basis": "mechanical match evidence only",
        }
    target_ids = sorted(set(packet.get("target_cell_ids") or []))
    target_foreground = target_ids[:target_foreground_limit]
    result["targets"] = {
        "candidate_count": len(target_ids),
        "foreground_cell_ids": target_foreground,
        "omitted_count": max(0, len(target_ids) - len(target_foreground)),
        "remainder_handle": f"grounding:{obligation.get('id')}:targets:tail" if len(target_ids) > len(target_foreground) else None,
        "region_summaries": _regions(target_ids, region_limit),
        "region_summary_count": len(_regions(target_ids, region_limit)),
        "selection_basis": "deterministic rectangle/run summary over complete candidate IDs",
    }
    member = packet.get("population_member_evidence") or {}
    result["population_member_evidence"] = {
        "active": bool(member.get("active")),
        "specifications": member.get("specifications") or [],
        "allowed_members": member.get("allowed_members") or [],
        "excluded_members": member.get("excluded_members") or [],
        "occurrence_count": len(member.get("occurrences") or []),
        "included_occurrences": member.get("included_occurrences") or [],
        "excluded_occurrences": member.get("excluded_occurrences") or [],
        "repeated_block_runs": member.get("repeated_block_runs") or [],
        "selection_basis": "explicit ordinal/member relation with Task IR field provenance",
    }
    role = packet.get("output_role_evidence") or {}
    result["output_role_evidence"] = {
        "active": bool(role.get("active")),
        "relation_name": role.get("relation_name"),
        "relation_definition": role.get("relation_definition"),
        "candidate_endpoint_ids": role.get("candidate_endpoint_ids") or [],
        "endpoint_count": role.get("endpoint_count", 0),
        "activations": role.get("activations") or [],
        "excluded_occurrence_ids": role.get("excluded_occurrence_ids") or [],
        "uses_gold": bool(role.get("uses_gold")),
        "selection_basis": "accepted deterministic structural witnesses; evidence/candidates only",
    }
    for field, limit in (("formula_class_facts", foreground_limit), ("dependency_facts", foreground_limit)):
        foreground, omitted = _foreground(packet.get(field) or [], limit)
        result[field] = {
            "foreground": [_candidate_view(x) for x in foreground],
            "candidate_count": len(packet.get(field) or []),
            "omitted_count": omitted,
            "remainder_handle": f"grounding:{obligation.get('id')}:{field}:tail" if omitted else None,
        }
    return result


def projection_context(
    task: dict[str, Any],
    compiler: dict[str, Any],
    projected_packets: dict[str, dict[str, Any]],
    sheets: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    return {
        "RAW_TASK": compiler["raw_task"],
        "GENERATED_TASK_IR": {"obligations": compiler.get("obligations", [])},
        "SHEETS": sheets,
        "GROUNDING": projected_packets,
        "NOTE": (
            "This is a deterministic obligation-scoped projection of a complete closed-world "
            "grounding packet. Foreground candidates and region summaries are evidence, not a "
            "whitelist. Omitted candidates remain in the authoritative world under the shown "
            "remainder_handle. Use only stable workbook identities and the exact Edit Plan schema."
        ),
        "EXACT_JSON_SCHEMA": schema,
    }


def operation_id_map(operations: list[dict[str, Any]], prefix: str) -> dict[str, str]:
    return {str(op["operation_id"]): f"{prefix}::{op['operation_id']}" for op in operations}


def rename_operations(operations: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    mapping = operation_id_map(operations, prefix)
    out = []
    for original in operations:
        op = json.loads(json.dumps(original, ensure_ascii=False))
        op["operation_id"] = mapping[str(original["operation_id"])]
        sequencing = op.get("sequencing") or {}
        if sequencing.get("after"):
            sequencing["after"] = [mapping.get(str(x), str(x)) for x in sequencing["after"]]
        out.append(op)
    return out


def fragment_conflicts(expansions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    conflicts = []
    for expansion in expansions:
        for op in expansion.get("operations") or []:
            for cid in op.get("cell_ids") or []:
                previous = seen.get(cid)
                current = {"operation_id": op.get("operation_id"), "operation_kind": op.get("operation_kind"), "obligation_id": op.get("obligation_id")}
                if previous and previous.get("operation_kind") != current.get("operation_kind"):
                    conflicts.append({"cell_id": cid, "previous": previous, "current": current, "failure_class": "PLAN_FRAGMENT_CONFLICT"})
                else:
                    seen[cid] = previous or current
    return conflicts
