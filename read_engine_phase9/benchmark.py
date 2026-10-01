"""Phase-9 frozen representative full-command A/B/C runner."""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from read_engine_phase3 import benchmark as b3
from read_engine_phase8a import validation_runner as p8

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "overlay"
RUNS = HERE / "runs"
ARMS = ("PY", "H0", "H1")
SPEC_SHA = "68c786a73d3ea510ec1216247725dfb3e3ac10ad92d3cd171e3b1da49a03563a"
DECISION_SHA = "63210e6f1606e19131df5341da4a2fc0b33fc83487f8a3148220c14bda84704b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append(name: str, row: dict) -> None:
    with (HERE / name).open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def verify() -> tuple[dict, list[dict]]:
    if sha(HERE / "PREREGISTERED_SPEC.md") != SPEC_SHA:
        raise RuntimeError("Phase-9 preregistration changed")
    if sha(HERE / "ARCHITECTURE_DECISION.md") != DECISION_SHA:
        raise RuntimeError("Phase-9 architecture decision changed")
    population, changed = p8.verify()
    manifest = HERE / "implementation_identity.json"
    recorded = (HERE / "implementation_identity.sha256").read_text().split()[0]
    if sha(manifest) != recorded:
        raise RuntimeError("Phase-9 implementation manifest changed")
    pins = json.loads(manifest.read_text())
    for rel, digest in pins.items():
        if sha(ROOT / rel) != digest:
            raise RuntimeError(f"Phase-9 pinned implementation changed: {rel}")
    return population, changed


def command(row: dict, arm: str, base: Path) -> dict:
    original = p8.OVERLAY
    try:
        if arm == "H1":
            p8.OVERLAY = OVERLAY
        result = p8.command(row, "PY" if arm == "PY" else "H1", base)
    finally:
        p8.OVERLAY = original
    if arm != "PY":
        last = base / "runs/last_run.json"
        setup = {}
        if last.exists():
            run_dir = Path(json.loads(last.read_text())["run_dir"])
            if (run_dir / "setup.json").exists():
                setup = json.loads((run_dir / "setup.json").read_text())
        result["phase9_route"] = setup.get("fast_path") or (
            "DIRECT_RUNTIME" if setup.get("admitted") else "REFERENCE_RUNTIME")
        result["read_gate"] = setup.get("read_gate")
        result["runtime_installed"] = setup.get("runtime_installed")
        result["merged_certificate"] = setup.get("merged_certificate")
    return result


def classification(result: dict) -> str:
    if result.get("phase9_route") == "FAST_PATH_PROVEN_REFERENCE":
        return "REFERENCE_ONLY"
    return p8.classification(result)


def statuses(result: dict) -> list[str]:
    return p8.statuses(result)


def persist(row: dict, phase: str, rep: int, invocation: int,
            arm: str, result: dict, *, changed: bool) -> None:
    keep = {k: v for k, v in result.items()
            if k not in {"events", "stdout", "stderr", "capture_rows"}}
    append("changed_file_timings.jsonl" if changed else "raw_timings.jsonl",
           {"workload_id": row["workload_id"], "task": row["task"],
            "family": row["family"], "phase": phase, "rep": rep,
            "invocation": invocation, "arm": arm,
            "contact_class": classification(result) if arm != "PY" else None,
            "artifact_statuses": statuses(result) if arm != "PY" else [],
            **keep})


def correctness(row: dict, phase: str, rep: int, invocation: int,
                results: dict, *, changed: bool) -> bool:
    py, h0, h1 = (results[a] for a in ARMS)
    checks = {"PY_H0": b3.compare(py, h0), "PY_H1": b3.compare(py, h1),
              "H0_H1": b3.compare(h0, h1)}
    output_ok = all(c["classification"] in {"EXACT", "VOLATILE_ONLY_DIFFERENCE"}
                    for c in checks.values())
    class0, class1 = classification(h0), classification(h1)
    route = h1.get("phase9_route")
    proven_reference = (class0 == "REFERENCE_ONLY"
                        and h0.get("read_gate") != "A1_ADMIT"
                        and class1 == "REFERENCE_ONLY"
                        and route == "FAST_PATH_PROVEN_REFERENCE"
                        and h1.get("runtime_installed") is False
                        and statuses(h1) == [])
    direct_contact = class0 in {"DIRECT_CONTACT", "FALLBACK_AFTER_CONTACT"}
    direct_stable = (direct_contact and class1 == class0
                     and route == "DIRECT_RUNTIME"
                     and h1.get("runtime_installed") is True
                     and h0.get("certificate") == h1.get("merged_certificate")
                     and (h0.get("summary") or {}).get("reference_reasons")
                     == (h1.get("summary") or {}).get("reference_reasons"))
    expected = ["BUILT"] if invocation == 1 else ["REUSED"]
    witness = (statuses(h0) == statuses(h1) == expected if direct_contact
               else statuses(h0) == statuses(h1) == [])
    receipts = all(p8.capture_ok(results[a], changed=changed)
                   for a in ("H0", "H1"))
    exits = all(results[a]["exit_code"] == 0 and not results[a]["timed_out"]
                for a in ARMS)

    volatile_package_parts: list[str] = []
    effects_ok = None
    if changed:
        relations = {a: p8.package_relation(py, results[a])
                     for a in ("H0", "H1")}
        output_ok = all(v[0] for v in relations.values())
        volatile_package_parts = sorted(
            {part for value in relations.values() for part in value[1]})
        expected_rel = ("output.xlsx" if row["workload_id"].endswith("output_file")
                        else "input.xlsx")
        effects_ok = all(
            [x.get("rel") for x in (results[a].get("capture_rows") or [])]
            == [expected_rel] for a in ("H0", "H1"))
        stream_ok = all((py["stdout"], py["stderr"])
                        == (results[a]["stdout"], results[a]["stderr"])
                        for a in ("H0", "H1"))
        valid = (output_ok and exits and witness and proven_reference
                 and effects_ok and receipts and stream_ok)
        label = "CHANGED_FILE"
    else:
        valid = (output_ok and exits and witness and receipts
                 and (proven_reference or direct_stable))
        label = ("COLD" if invocation == 1 else
                 "VALID_REUSE" if direct_contact else "SECOND_INVOCATION")
    append("changed_file_correctness.jsonl" if changed else "raw_correctness.jsonl",
           {"workload_id": row["workload_id"], "phase": phase, "rep": rep,
            "invocation": invocation, "label": label,
            "checks": checks, "output_state_ok": output_ok,
            "H0_class": class0, "H1_class": class1,
            "H1_route": route, "fast_path_proven": proven_reference,
            "direct_stable": direct_stable, "witness_ok": witness,
            "capture_ok": receipts, "effects_ok": effects_ok,
            "volatile_package_parts": volatile_package_parts,
            "valid": valid})
    return valid


def gate() -> None:
    pop, changed = verify()
    for name in ("raw_correctness.jsonl", "raw_timings.jsonl",
                 "session_timings.jsonl", "changed_file_correctness.jsonl",
                 "changed_file_timings.jsonl"):
        path = HERE / name
        if path.exists() and path.stat().st_size:
            raise RuntimeError(f"Ledger already contains rows: {name}")
        path.touch(exist_ok=True)
    by_id = {r["workload_id"]: r for r in pop["workloads"]}
    for position, wid in enumerate(pop["secondary_ids"], 1):
        row = by_id[wid]
        base = RUNS / "gate/representative" / wid
        for invocation in (1, 2):
            results = {arm: command(row, arm, base / arm.lower()) for arm in ARMS}
            for arm in ARMS:
                persist(row, "gate", 0, invocation, arm, results[arm], changed=False)
            if not correctness(row, "gate", 0, invocation, results, changed=False):
                raise RuntimeError(f"Representative correctness gate failed: {wid} {invocation}")
        print(f"representative gate {position}/30 {wid}", flush=True)
    for position, row in enumerate(changed, 1):
        base = RUNS / "gate/changed" / row["workload_id"]
        results = {arm: command(row, arm, base / arm.lower()) for arm in ARMS}
        for arm in ARMS:
            persist(row, "gate", 0, 1, arm, results[arm], changed=True)
        if not correctness(row, "gate", 0, 1, results, changed=True):
            raise RuntimeError(f"Changed-file correctness gate failed: {row['workload_id']}")
        print(f"changed-file gate {position}/5 {row['workload_id']}", flush=True)
    (HERE / "correctness_gate.json").write_text(
        json.dumps({"status": "PASSED", "representative_count": 30,
                    "changed_count": 5}, sort_keys=True, indent=2) + "\n")


def score() -> None:
    pop, changed = verify()
    gate_record = HERE / "correctness_gate.json"
    if not gate_record.exists() or json.loads(gate_record.read_text()).get("status") != "PASSED":
        raise RuntimeError("Correctness gate absent")
    if any(json.loads(s).get("phase") == "scored"
           for s in (HERE / "raw_timings.jsonl").read_text().splitlines()):
        raise RuntimeError("Scored rows already exist")
    by_id = {r["workload_id"]: r for r in pop["workloads"]}
    ids = list(pop["secondary_ids"])
    random.Random(20261001).shuffle(ids)
    for position, wid in enumerate(ids, 1):
        row = by_id[wid]
        for arm in ARMS:
            command(row, arm, RUNS / "warmup/representative" / wid / arm.lower())
        for rep in range(1, 4):
            base = RUNS / "scored/representative" / wid / f"rep-{rep}"
            totals = {arm: 0 for arm in ARMS}
            for invocation in range(1, 6):
                shift = (position + rep + invocation) % len(ARMS)
                ordered = ARMS[shift:] + ARMS[:shift]
                results = {}
                for arm in ordered:
                    results[arm] = command(row, arm, base / arm.lower())
                    totals[arm] += results[arm]["wall_ns"]
                    persist(row, "scored", rep, invocation, arm,
                            results[arm], changed=False)
                if not correctness(row, "scored", rep, invocation,
                                   results, changed=False):
                    raise RuntimeError(
                        f"Scored representative correctness failure: {wid} {rep} {invocation}")
                if invocation in (1, 2, 3, 5):
                    append("session_timings.jsonl",
                           {"workload_id": wid, "task": row["task"], "rep": rep,
                            "N": invocation, "PY_ns": totals["PY"],
                            "H0_ns": totals["H0"], "H1_ns": totals["H1"],
                            "H1_class": classification(results["H1"]),
                            "H1_route": results["H1"].get("phase9_route")})
        print(f"representative scored {position}/30 {wid}", flush=True)
    for position, row in enumerate(changed, 1):
        for rep in range(1, 4):
            base = RUNS / "scored/changed" / row["workload_id"] / f"rep-{rep}"
            shift = (position + rep) % len(ARMS)
            ordered = ARMS[shift:] + ARMS[:shift]
            results = {}
            for arm in ordered:
                results[arm] = command(row, arm, base / arm.lower())
                persist(row, "scored", rep, 1, arm, results[arm], changed=True)
            if not correctness(row, "scored", rep, 1, results, changed=True):
                raise RuntimeError(
                    f"Scored changed-file correctness failure: {row['workload_id']} {rep}")
        print(f"changed-file scored {position}/5 {row['workload_id']}", flush=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in {"gate", "score"}:
        raise SystemExit("usage: python -m read_engine_phase9.benchmark gate|score")
    (gate if sys.argv[1] == "gate" else score)()
