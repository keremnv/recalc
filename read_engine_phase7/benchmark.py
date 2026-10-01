"""Same-run PY / frozen Phase-6 H2 / certified merged-child route."""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from read_engine_phase3 import benchmark as b3
from read_engine_phase6 import benchmark as b6

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "overlay"
SPEC_SHA = "338cb6ab6d91a0005b492461b1de425ee3efd04ceec29d09869c7a550d3dd121"
REVIEW_SHA = "d8898c2fc0d0b910e86829d792a05da82e165e3702fb7c950051d8fa85029d54"
ARMS = ("PY", "H0", "H1")
TARGETS = {"Debugging_01_06__7b42a0f86b41": 6,
           "Debugging_05_02__9e6b464d2158": 8,
           "Financial_Model_08_03__59b98508fd79": 38}
ITERATION = "Financial_Model_15_03__472e28fbd6e0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append(name: str, row: dict) -> None:
    with (HERE / name).open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def verify() -> dict:
    if sha(HERE / "PREREGISTERED_SPEC.md") != SPEC_SHA:
        raise RuntimeError("Phase-7 preregistration changed")
    if sha(HERE / "MERGED_CELL_SEMANTIC_REVIEW.md") != REVIEW_SHA:
        raise RuntimeError("Phase-7 semantic review changed")
    pop = b6.verify()
    identity = json.loads((HERE / "implementation_identity.json").read_text())
    for name, digest in identity.items():
        if sha(HERE / name) != digest:
            raise RuntimeError(f"Phase-7 implementation changed: {name}")
    return pop


def command(row: dict, arm: str, base: Path) -> dict:
    if arm == "PY":
        result = b6.command(row, "PY", base)
    else:
        original = b6.ROOT
        try:
            b6.ROOT = original if arm == "H0" else OVERLAY
            result = b6.command(row, "H2", base)
        finally:
            b6.ROOT = original
    if arm == "PY":
        result["merged"] = None
        return result
    counts = {event: sum(e.get("event") == event for e in result["events"])
              for event in ("merged_child_contact", "merged_child_direct", "merged_child_reference")}
    result["merged"] = counts
    if arm == "H1":
        last = base / "runs/last_run.json"
        if last.exists():
            run_dir = Path(json.loads(last.read_text())["run_dir"])
            setup = json.loads((run_dir / "setup.json").read_text())
            result["summary"]["merged_certificate"] = setup["merged_certificate"]
    return result


def persist(row: dict, arm: str, phase: str, rep: int, invocation: int, result: dict) -> None:
    keep = {k: v for k, v in result.items() if k not in {"events", "stdout", "stderr"}}
    append("raw_timings.jsonl", {"workload_id": row["workload_id"], "task": row["task"],
           "family": row["family"], "arm": arm, "phase": phase, "rep": rep,
           "invocation": invocation, **keep})


def confirm(row: dict, phase: str, rep: int, invocation: int, results: dict) -> bool:
    py, h0, h1 = (results[a] for a in ARMS)
    checks = {"PY_H0": b3.compare(py, h0), "PY_H1": b3.compare(py, h1),
              "H0_H1": b3.compare(h0, h1)}
    warm = invocation > 1
    summaries = (h0.get("summary") or {}, h1.get("summary") or {})
    artifacts = [[v.get("status") for v in s.get("artifacts", {}).values()] for s in summaries]
    witness = (all(v == (["REUSED"] if warm else ["BUILT"]) for v in artifacts)
               and all(s.get("direct_served_loads", 0) > 0 for s in summaries)
               and all(s.get("observer_receipt", {}).get("capture_helper_exit") == 0 for s in summaries)
               and all(s.get("capture_failures") == 0 for s in summaries))
    target = row["workload_id"] in TARGETS
    expected_h0 = ["proxy_operation_escape"] if target or row["workload_id"] == ITERATION else []
    expected_h1 = ["proxy_operation_escape"] if row["workload_id"] == ITERATION else []
    fallback = (h0["summary"].get("reference_reasons") == expected_h0
                and h1["summary"].get("reference_reasons") == expected_h1)
    merged = h1["merged"] or {}
    if target:
        contact = TARGETS[row["workload_id"]]
        merged_ok = (h1["summary"].get("merged_certificate", {}).get("certified") is True
                     and merged.get("merged_child_contact") == contact
                     and merged.get("merged_child_direct") == contact
                     and merged.get("merged_child_reference") == 0)
    else:
        merged_ok = merged.get("merged_child_direct") == 0
    exact = all(c["classification"] == "EXACT" for c in checks.values())
    valid = (exact and witness and fallback and merged_ok
             and all(x["exit_code"] == 0 and not x["timed_out"] for x in results.values()))
    append("raw_correctness.jsonl", {"kind": "script_three_arm", "workload_id": row["workload_id"],
           "phase": phase, "rep": rep, "invocation": invocation,
           "regime": "WARM" if warm else "COLD", "checks": checks,
           "artifact_statuses": artifacts, "fallback_ok": fallback,
           "expected_h0_reasons": expected_h0, "expected_h1_reasons": expected_h1,
           "H0_reasons": h0["summary"].get("reference_reasons"),
           "H1_reasons": h1["summary"].get("reference_reasons"),
           "H1_merged": merged, "merged_ok": merged_ok, "witness_ok": witness,
           "valid": valid})
    return valid


def run_gate(pop: dict) -> bool:
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    for position, wid in enumerate(pop["primary_ids"], 1):
        row = by_id[wid]
        base = HERE / "runs/gate" / wid
        results = {arm: command(row, arm, base / arm.lower()) for arm in ARMS}
        for arm in ARMS:
            persist(row, arm, "gate", 0, 1, results[arm])
        if not confirm(row, "gate", 0, 1, results):
            print(f"STOP: cold gate {wid}", flush=True)
            return False
        for arm in ("H0", "H1"):
            results[arm] = command(row, arm, base / arm.lower())
            persist(row, arm, "gate", 0, 2, results[arm])
        if not confirm(row, "gate", 0, 2, results):
            print(f"STOP: warm gate {wid}", flush=True)
            return False
        print(f"gate {position}/22 {wid}", flush=True)
    return True


def run_scored(pop: dict) -> bool:
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    order = list(pop["primary_ids"])
    random.Random(20261107).shuffle(order)
    for position, wid in enumerate(order, 1):
        row = by_id[wid]
        for arm in ARMS:
            command(row, arm, HERE / "runs/warmup" / wid / arm.lower())
        for rep in range(1, 4):
            base = HERE / "runs/scored" / wid / f"rep-{rep}"
            totals = {arm: 0 for arm in ARMS}
            for invocation in range(1, 6):
                shift = (position + rep + invocation) % 3
                arm_order = ARMS[shift:] + ARMS[:shift]
                results = {}
                for arm in arm_order:
                    results[arm] = command(row, arm, base / arm.lower())
                    persist(row, arm, "scored", rep, invocation, results[arm])
                    totals[arm] += results[arm]["wall_ns"]
                if not confirm(row, "scored", rep, invocation, results):
                    print(f"STOP: scored gate {wid} rep={rep} invocation={invocation}", flush=True)
                    return False
                if invocation in (1, 2, 3, 5):
                    append("session_timings.jsonl", {"workload_id": wid, "task": row["task"],
                           "rep": rep, "N": invocation,
                           "PY_ns": totals["PY"], "H0_ns": totals["H0"],
                           "H1_ns": totals["H1"], "all_warm_reused": True})
        print(f"scored {position}/22 {wid}", flush=True)
    return True


def main() -> None:
    pop = verify()
    for name in ("raw_correctness.jsonl", "raw_timings.jsonl", "session_timings.jsonl"):
        if (HERE / name).exists():
            raise RuntimeError(f"Ledger already exists: {name}")
        (HERE / name).write_text("")
    from read_engine_phase7 import lifecycle_gate
    if not lifecycle_gate.run(pop, lambda row: append("raw_correctness.jsonl", row)):
        print("STOP: lifecycle gate", flush=True)
        return
    if not run_gate(pop):
        return
    run_scored(pop)


if __name__ == "__main__":
    main()
