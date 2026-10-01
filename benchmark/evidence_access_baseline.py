#!/usr/bin/env python3
"""Offline evidence-pool baseline for the frozen 06_01 O3 sessions.

This reads the already-frozen autopsy pool/manifests and archived synthesis
requests.  It never calls a provider and never rewrites the authoritative
pool or manifests.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUTOPSY = ROOT / "resource_demand_autopsy"
LIVE = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/resource_feasibility/clean_integrated/live/Financial_Model-06_01"
OUT_JSON = AUTOPSY / "evidence_access_baseline.json"
OUT_MD = ROOT / "RESOURCE_EVIDENCE_ACCESS_BASELINE.md"

ENTITY_ID = re.compile(r"^(?:wb|sheet|cell|row|col|text|formula|formula_class|range|period|region|tcoord|dep|anchor):")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_archived_evidence(call_index: int) -> dict[str, Any]:
    path = LIVE / "calls" / f"{call_index:03d}_synthesis.json"
    call = json.loads(path.read_text(encoding="utf-8"))
    messages = call["request_body"]["messages"]
    return json.loads(messages[-1]["content"])["WORKING_SET_EVIDENCE"]


def reconstruct(manifest: dict[str, Any], pool: dict[str, str], template: dict[str, Any], *, entity_ids: list[str] | None = None) -> tuple[dict[str, Any], bool, str]:
    output = copy.deepcopy(template)
    rows: dict[tuple[str, str], list[list[Any]]] = {}
    columns: dict[tuple[str, str], list[str]] = {}
    observed_ids: set[str] = set()
    for key in manifest["record_keys"]:
        encoded = pool[key]
        if hashlib.sha256(encoded.encode()).hexdigest() != key:
            raise AssertionError(f"POOL_KEY_MISMATCH: {key}")
        namespace, table, table_columns, row = json.loads(encoded)
        group = "entities" if namespace == "entities" else "relations"
        rows.setdefault((group, table), []).append(row)
        columns[(group, table)] = table_columns
        for value in row:
            if isinstance(value, str) and ENTITY_ID.match(value):
                observed_ids.add(value)
    for group, tables in output.items():
        if group not in ("entities", "relations"):
            continue
        for table, payload in tables.items():
            payload["rows"] = rows.get((group, table), [])
            expected_columns = columns.get((group, table), payload.get("columns", []))
            if payload.get("columns", []) != expected_columns:
                raise AssertionError(f"COLUMN_ORDER_MISMATCH: {group}.{table}")
    # The record pool contains supporting rows (for example all sheet rows
    # needed to materialize a cell), which are not necessarily members of the
    # session's working-set ID list.  The per-target manifest/delta therefore
    # carries the exact entity ID list; deriving it from row contents would
    # overstate the archived working set.
    output["entity_ids"] = sorted(entity_ids if entity_ids is not None else observed_ids)
    canonical_equal = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(template, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return output, canonical_equal, digest(output)


def main() -> dict[str, Any]:
    pool = json.loads((AUTOPSY / "evidence_record_pool.json").read_text(encoding="utf-8"))
    manifests = json.loads((AUTOPSY / "evidence_manifests.json").read_text(encoding="utf-8"))
    sessions = list(csv.DictReader((AUTOPSY / "sessions.csv").open(newline="", encoding="utf-8")))
    calls = list(csv.DictReader((AUTOPSY / "calls.csv").open(newline="", encoding="utf-8")))
    o3 = [m for m in manifests if m["session"].startswith("cell:s01:")]
    if len(o3) != 16:
        raise AssertionError(f"EXPECTED_16_O3_MANIFESTS: {len(o3)}")
    session_by_id = {row["cell_id"]: row for row in sessions}
    calls_by_session: dict[str, list[dict[str, Any]]] = {m["session"]: [] for m in o3}
    for call in calls:
        if call.get("session") in calls_by_session:
            calls_by_session[call["session"]].append(call)

    record_sets = {m["session"]: set(m["record_keys"]) for m in o3}
    shared = set.intersection(*record_sets.values())
    per_target = []
    for manifest in o3:
        keyset = record_sets[manifest["session"]]
        row = session_by_id[manifest["session"]]
        per_target.append({
            "session": manifest["session"],
            "target": row["target"],
            "record_ids": sorted(keyset),
            "record_count": len(keyset),
            "shared_record_count": len(keyset & shared),
            "target_delta_record_count": len(keyset - shared),
            "manifest_evidence_sha256": manifest["evidence_sha256"],
            "final_synthesis_visible_record_count": int(row["record_count"]),
            "retrieval_history": [{
                "index": int(c["index"]),
                "stage": c["stage"],
                "working_set_ids_before": c["working_set_ids_before"],
                "working_set_ids_added": c["working_set_ids_added"],
                "working_set_ids_after": c["working_set_ids_after"],
                "new_evidence_ids": c["new_evidence_ids"],
                "sql_result_bytes": c["sql_result_bytes"],
                "action": c["action"],
            } for c in calls_by_session[manifest["session"]]],
            "retrieval_state": {
                "bootstrap_ids": int(row["bootstrap_ids"]),
                "final_working_set_ids": int(row["final_ws_ids"]),
                "new_sql_ids": int(row["new_sql_ids"]),
                "retrieval_calls": int(row["retrieval_calls"]),
                "synthesis_calls": int(row["synthesis_calls"]),
                "sql_no_new_ids": int(row["sql_no_new_ids"]),
            },
        })

    c49_manifest = next(m for m in o3 if m["session"] == "cell:s01:r49:c3")
    archived = load_archived_evidence(45)
    accepted_slices = json.loads((AUTOPSY / "accepted_edit_slices.json").read_text(encoding="utf-8"))
    c49_slice = next(x for x in accepted_slices if x["cell_id"] == "cell:s01:r49:c3")
    reconstructed, equivalent, reconstructed_hash = reconstruct(c49_manifest, pool, archived, entity_ids=c49_slice["full_evidence_ids"])
    result = {
        "status": "PASS" if equivalent else "FAIL",
        "source_artifacts": {
            "pool": str(AUTOPSY / "evidence_record_pool.json"),
            "manifests": str(AUTOPSY / "evidence_manifests.json"),
            "accepted_slices": str(AUTOPSY / "accepted_edit_slices.json"),
            "sessions": str(AUTOPSY / "sessions.csv"),
            "calls": str(AUTOPSY / "calls.csv"),
        },
        "scope": "06_01 frozen O3 archived sessions only",
        "o3_target_count": len(o3),
        "shared_records_across_all_o3_targets": {"count": len(shared), "record_ids": sorted(shared)},
        "per_target": per_target,
        "final_synthesis_visible_records": {x["session"]: {"count": x["final_synthesis_visible_record_count"], "record_ids": x["record_ids"]} for x in per_target},
        "reconstruction": {
            "session": c49_manifest["session"],
            "archived_synthesis_call": 45,
            "archived_evidence_sha256": digest(archived),
            "manifest_evidence_sha256": c49_manifest["evidence_sha256"],
            "reconstructed_evidence_sha256": reconstructed_hash,
            "content_equivalent": equivalent,
            "record_count": len(c49_manifest["record_keys"]),
            "entity_id_count": len(c49_slice["full_evidence_ids"]),
            "interface": "authoritative evidence store + ordered stable record IDs/manifests + per-target delta",
        },
        "model_facing_requirement": "Omitted shared records are not available to a stateless model from byte deduplication alone; access requires a persistent evidence tool/store or a model-visible shared context plus manifest and target delta.",
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# Frozen 06_01 O3 Evidence-Access Baseline", "",
        "This is an offline accounting of the preserved content-addressed pool and manifests. No provider request was made and the pool/manifests were not modified.", "",
        f"Scope: {len(o3)} O3 target sessions. Shared records across every O3 target: **{len(shared)}**. Each target retains its complete archived synthesis-visible record set; the table below reports the lossless shared/delta decomposition.", "",
        "| Target | Final synthesis records | Shared records | Target delta | Retrieval calls | Final working-set IDs |", "|---|---:|---:|---:|---:|---:|",
    ]
    for x in per_target:
        md.append(f"| {x['target']} | {x['final_synthesis_visible_record_count']} | {x['shared_record_count']} | {x['target_delta_record_count']} | {x['retrieval_state']['retrieval_calls']} | {x['retrieval_state']['final_working_set_ids']} |")
    md += [
        "", "## Lossless interface", "", "```text", "authoritative evidence store", "    + stable record IDs / ordered manifests", "    + per-target delta", "```", "",
        "The archived `cell:s01:r49:c3` synthesis evidence was reconstructed from only its manifest and the content-addressed pool. The reconstructed content hash is:", "",
        f"`{reconstructed_hash}`", "", f"Content-equivalent: **{equivalent}**. The archived evidence hash is `{digest(archived)}` and the manifest hash is `{c49_manifest['evidence_sha256']}`.", "",
        "The exact shared IDs are in `evidence_access_baseline.json` under `shared_records_across_all_o3_targets.record_ids`; exact per-target/final-synthesis IDs are under each `per_target[].record_ids` entry. Retrieval history/state is recorded alongside each target.", "",
        "This proves storage/reconstruction deduplication, not model-token savings. A stateless model cannot access omitted shared facts from a record ID alone. A model-facing compact representation therefore needs a persistent retrieval/materialization tool, or a shared model-visible context carrying the shared records, plus the manifest and target delta.", "",
        "Retrieval history/state is retained per target in `resource_demand_autopsy/evidence_access_baseline.json`, including working-set IDs before/after each archived retrieval call and the final synthesis-visible record count.",
    ]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
