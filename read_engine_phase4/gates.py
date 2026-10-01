"""Pre-scoring Phase-4 freshness, corruption and child-trust probes."""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import zlib
from pathlib import Path

from read_engine_phase4 import parent_artifact


def _artifact_status(result: dict) -> list[str]:
    summary = result.get("summary") or {}
    return sorted(x.get("status") for x in summary.get("artifacts", {}).values())


def _child_served(result: dict) -> bool:
    return any(x.get("event") == "direct_served_load" for x in result.get("events", []))


def _repack(original: bytes, header_updates: dict | None = None,
            semantic_raw: bytes | None = None) -> bytes:
    hlen = struct.unpack(">I", original[8:12])[0]
    header = json.loads(original[12:12 + hlen])
    offset = 12 + hlen
    clen = struct.unpack(">Q", original[offset:offset + 8])[0]
    compressed = original[offset + 8:offset + 8 + clen]
    if semantic_raw is not None:
        compressed = zlib.compress(semantic_raw, level=1)
        header["payload_sha256"] = hashlib.sha256(semantic_raw).hexdigest()
    header.update(header_updates or {})
    h = json.dumps(header, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    body = original[:8] + struct.pack(">I", len(h)) + h + struct.pack(">Q", len(compressed)) + compressed
    return body + hashlib.sha256(body).digest()


def _replace_artifact(artifact: Path, sidecar: Path, blob: bytes) -> None:
    artifact.write_bytes(blob)
    meta = json.loads(sidecar.read_text())
    meta["artifact_bytes"] = len(blob)
    meta["artifact_sha256"] = hashlib.sha256(blob).hexdigest()
    sidecar.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def run(pop: dict, append) -> bool:
    # Frozen source generations: first two distinct hashes in primary order.
    from read_engine_phase4 import benchmark as b4
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    selected = []
    for wid in pop["primary_ids"]:
        row = by_id[wid]
        if row["source_workbook_sha256"] not in {x["source_workbook_sha256"] for x in selected}:
            selected.append(row)
        if len(selected) == 2:
            break
    if len(selected) != 2:
        raise RuntimeError("Two distinct preregistered source generations unavailable")
    ok = True
    for idx, row in enumerate(selected):
        other = selected[1 - idx]
        base = b4.HERE / "runs/invalidation" / f"source-{idx}"
        source_sha = row["source_workbook_sha256"]
        artifact, sidecar = parent_artifact.paths(base / "persistent-cache", source_sha)

        def probe(case: str, expected_status: str, require_served: bool = True,
                  source_row: dict | None = None) -> dict:
            nonlocal ok
            result = b4.command(source_row or row, "H1", base)
            statuses = _artifact_status(result)
            served = _child_served(result)
            passed = (statuses == [expected_status] and served == require_served
                      and result["summary"] is not None)
            append({"kind": "invalidation", "case": case, "workload_id": row["workload_id"],
                    "source_sha256": (source_row or row)["source_workbook_sha256"],
                    "statuses": statuses, "child_direct_served": served,
                    "reference_reasons": (result.get("summary") or {}).get("reference_reasons"),
                    "exit_code": result["exit_code"], "passed": passed})
            ok &= passed
            return result

        probe("missing_artifact", "BUILT")
        probe("valid_warm", "REUSED")
        original = artifact.read_bytes()
        original_sidecar = sidecar.read_bytes()

        artifact.unlink()
        probe("missing_artifact_after_build", "BUILT")
        artifact.write_bytes(original[:max(1, len(original) // 3)])
        probe("truncated_artifact", "BUILT")
        changed = bytearray(original)
        changed[len(changed) // 2] ^= 1
        artifact.write_bytes(changed)
        probe("modified_artifact_byte", "BUILT")

        for key, value in (("format_version", "JSONZ_MEMORY_V0"),
                           ("decoder_sha256", "0" * 64),
                           ("contract_version", "PHASE1_NARROW_V0")):
            _replace_artifact(artifact, sidecar, _repack(original, {key: value}))
            probe(f"{key}_mismatch", "BUILT")

        # Integrity-consistent but semantically invalid payload: parent is only
        # a candidate gate; frozen child must reject before any direct serving.
        _replace_artifact(artifact, sidecar, _repack(original, semantic_raw=b'{"bad":true,"sheets":[]}'))
        semantic = probe("semantic_payload_rejected_by_child", "REUSE_REJECTED", False)
        reasons = (semantic.get("summary") or {}).get("reference_reasons") or []
        semantic_ok = reasons == ["runtime_failure"]
        append({"kind": "child_semantic_rejection", "workload_id": row["workload_id"],
                "passed": semantic_ok, "reference_reasons": reasons})
        ok &= semantic_ok

        artifact.write_bytes(original)
        sidecar.write_bytes(original_sidecar)
        probe("valid_restored_artifact", "REUSED")

        changed_row = {**row, "source_workbook_path": other["source_workbook_path"],
                       "source_workbook_sha256": other["source_workbook_sha256"],
                       "staged_workbook_sha256": other["staged_workbook_sha256"]}
        probe("same_path_different_source_bytes", "BUILT", source_row=changed_row)
        probe("original_source_bytes_restored", "REUSED")
    return ok
