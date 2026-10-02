#!/usr/bin/env python3
"""Build mechanical Phase 12 ledgers from run records (no judgment calls).

Writes: raw_run, exposure, cost, censoring, sham JSONL under research/history/phase12/ledgers.
Behavioral + nuisance ledgers are hand-coded separately.
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNS = PROJECT_ROOT / "research/history/phase12" / "runs"
LEDGERS = PROJECT_ROOT / "research/history/phase12" / "ledgers"


def parse(dirname: str):
    for arm in ("CONTROL", "TREATMENT", "SHAM"):
        if dirname.endswith("_" + arm):
            stem = dirname[: -len(arm) - 1]
            for cat in ("Template", "Debugging", "Financial_Model"):
                if stem.startswith(cat + "_"):
                    return cat, stem[len(cat) + 1:], arm
    raise RuntimeError(dirname)


def main() -> None:
    pops = ["popA", "popB", "pilot", "pilot_ext"]
    LEDGERS.mkdir(parents=True, exist_ok=True)
    raw, exp, cost, cens, sham = [], [], [], [], []
    for pop in pops:
        for d in sorted((RUNS / pop).glob("*")):
            if not d.is_dir():
                continue
            cat, tid, arm = parse(d.name)
            task = f"{cat}:{tid}"
            rec = json.loads((d / "run_record.json").read_text())
            e = rec.get("efficiency", {})
            v = rec.get("verifier", {}) or {}
            rep = rec.get("repair", {}) or {}
            status = rec.get("status")
            raw.append({"pop": pop, "task_id": task, "arm": arm,
                        "status": status,
                        "output_produced": rec.get("output_produced"),
                        "template_hash": rec.get("template_hash"),
                        "model": rec.get("model"), "declared": rec.get("declared"),
                        "behavior": rec.get("behavior"), "efficiency": e,
                        "repair": rep, "verifier": v})
            exp.append({"pop": pop, "task_id": task, "arm": arm,
                        "status": status,
                        "submitted": status in ("SUBMITTED",
                                                "SUBMITTED_AFTER_REPAIR_WINDOW"),
                        "output_produced": rec.get("output_produced"),
                        "intervened": bool(v.get("intervened")),
                        "kind": v.get("kind"), "positive": v.get("positive"),
                        "families": v.get("families"),
                        "verifier_status": v.get("status"),
                        "verifier_wall_s": v.get("verifier_wall_s"),
                        "repair_opened": v.get("repair_opened"),
                        "repair_calls": rep.get("calls"),
                        "repair_cost": rep.get("cost")})
            cost.append({"pop": pop, "task_id": task, "arm": arm,
                         "status": status,
                         "api_calls": e.get("api_calls"),
                         "tokens": e.get("tokens"),
                         "cost_usd": e.get("cost_usd"),
                         "walltime_s": e.get("walltime_s"),
                         "python_execs": e.get("python_execs"),
                         "opens": e.get("opens"),
                         "lo_invocations": e.get("lo_invocations"),
                         "failures": e.get("failures"),
                         "retries": e.get("retries"),
                         "repair_calls": rep.get("calls"),
                         "repair_cost": rep.get("cost"),
                         "verifier_wall_s": v.get("verifier_wall_s")})
            if status not in ("SUBMITTED", "SUBMITTED_AFTER_REPAIR_WINDOW"):
                cens.append({"pop": pop, "task_id": task, "arm": arm,
                             "status": status,
                             "stage": "pre-submit",
                             "output_produced": rec.get("output_produced"),
                             "api_calls": e.get("api_calls"),
                             "cost_usd": e.get("cost_usd"),
                             "walltime_s": round(e.get("walltime_s", 0) or 0, 1)})
            if arm == "SHAM":
                exp_row = exp[-1]
                sham.append(exp_row)
    # Infra note: first attempt at popB FM:17_05 CONTROL died to DNS in
    # fetch_prices before any model call; rerun recorded as the run.
    cens.append({"pop": "popB", "task_id": "Financial_Model:17_05",
                 "arm": "CONTROL", "status": "RUNNER_CRASH_DNS",
                 "stage": "startup(pre-model-call)",
                 "note": "URLError Temporary failure in name resolution in "
                         "fetch_prices; attempt discarded, single fresh rerun "
                         "recorded as the run; no model behavior replaced."})
    for name, rows in (("raw_run", raw), ("exposure", exp), ("cost", cost),
                       ("censoring", cens), ("sham", sham)):
        with open(LEDGERS / f"{name}.jsonl", "w") as fp:
            for r in rows:
                fp.write(json.dumps(r) + "\n")
        print(name, len(rows))


if __name__ == "__main__":
    main()
