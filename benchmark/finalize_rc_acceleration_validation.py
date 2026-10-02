"""Freeze final claim-validation artifacts without changing primary outcomes."""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/history/rc_acceleration_validation"


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def main():
    freeze = read("primary_freeze.json")
    for name, expected in freeze["hashes"].items():
        if sha(OUT / name) != expected:
            raise RuntimeError(f"Frozen primary file changed: {name}")
    spec = read("preregistered_spec.json")
    if sha(OUT / "preregistered_spec.json") != read("spec_hash.json")["sha256"]:
        raise RuntimeError("Spec hash mismatch")
    manifest = {r["workload_id"]: r for r in read("workload_manifest.json")["all_candidates"]}
    selected = set(spec["selected_eligible_ids"] + spec["selected_representative_ids"])
    for ident in selected:
        if sha(OUT / "workloads" / (ident + ".py")) != manifest[ident]["script_sha256"]:
            raise RuntimeError(f"Selected script changed: {ident}")
    raw = [json.loads(line) for line in (OUT / "raw_timings.jsonl").read_text().splitlines()]
    counts = collections.Counter((r["workload_id"], r["arm"], r["warmup"]) for r in raw)
    for ident in selected:
        for arm in ("CONTROL", "TREATMENT"):
            if counts[(ident, arm, True)] != 1 or counts[(ident, arm, False)] != 3:
                raise RuntimeError(f"Incomplete run schedule: {ident} {arm}")
    integrity = {
        "selected_union_workloads": len(selected), "raw_invocations": len(raw),
        "scheduled_invocations_expected": len(selected) * 8,
        "all_cache_locations_fresh": all(r["cache_fresh_before_start"] for r in raw),
        "all_workbook_bytes_unchanged": all(r["workbook_unchanged"] for r in raw),
        "timeouts": sum(r["timed_out"] for r in raw),
        "nonzero_exit_invocations": sum(r["exit_code"] != 0 for r in raw),
        "nonzero_exit_workloads": sorted({r["workload_id"] for r in raw if r["exit_code"] != 0}),
        "frozen_primary_hashes_verified": True,
        "selected_script_hashes_verified": True,
        "single_benchmark_worker": True,
    }
    (OUT / "measurement_integrity.json").write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n")
    names = [
        "research/reports/RC_ACCELERATION_CLAIM_VALIDATION_REPORT.md", "research/reports/FINAL_CLAIM_REGISTRY.md",
        "research/reports/RESEARCH_RECORD_FREEZE.md", "research/reports/CLAIM_BACKLOG.md", "research/reports/FINAL_PRESENTATION_HANDOFF.md",
    ]
    artifact_hashes = {p.name: sha(p) for p in sorted(OUT.iterdir())
                       if p.is_file() and p.name != "final_result_hash_manifest.json"}
    root_hashes = {name: sha(ROOT / name) for name in names}
    run_output_hashes = {}
    for r in raw:
        path = ROOT / r["run_dir"]
        run_output_hashes[r["run_dir"]] = {name: sha(path / name) for name in ("stdout.bin", "stderr.bin")}
    final = {"phase": "FINAL_RESULT_FROZEN", "product_rc_wheel_sha256": read("rc_identity.json")["wheel_sha256"],
             "preregistered_spec_sha256": sha(OUT / "preregistered_spec.json"),
             "primary_raw_sha256": sha(OUT / "raw_timings.jsonl"),
             "artifact_sha256": artifact_hashes, "root_report_sha256": root_hashes,
             "run_stdout_stderr_sha256": run_output_hashes,
             "research_stop": True}
    (OUT / "final_result_hash_manifest.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"artifact_count": len(artifact_hashes), "runs": len(raw),
                      "primary_raw_sha256": final["primary_raw_sha256"], "research_stop": True}))


if __name__ == "__main__":
    main()
