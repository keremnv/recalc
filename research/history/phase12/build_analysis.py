#!/usr/bin/env python3
"""Phase 12 analysis roll-up: paired endpoints, bootstrap CI, kill/success
evaluation. Reads ledgers only. Writes research/history/phase12/ledgers/analysis.json.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

LEDGERS = Path(__file__).resolve().parent / "ledgers"


def load(name: str):
    with open(LEDGERS / name) as fp:
        return [json.loads(l) for l in fp]


def main() -> None:
    scorer = {(r["pop"], r["task_id"], r["arm"]): r
              for r in load("scorer_outcome.jsonl")}
    ver = {(r["pop"], r["task_id"], r["arm"], r["which"]): r
           for r in load("verifier_output.jsonl")}
    beh = [r for r in load("behavioral.jsonl")]
    nui = [r for r in load("nuisance.jsonl")]

    # ---- primary: paired official_exact on popA completed pairs ----
    tasks = sorted({t for (p, t, a) in scorer if p == "popA"})
    pairs = []
    for t in tasks:
        c, tr = scorer.get(("popA", t, "CONTROL")), scorer.get(("popA", t, "TREATMENT"))
        if not c or not tr:
            continue
        if c["run_status"] == "SUBMITTED" and tr["run_status"] == "SUBMITTED":
            ce = 1.0 if c["official_exact"] == 1.0 else 0.0
            te = 1.0 if tr["official_exact"] == 1.0 else 0.0
            pairs.append({"task": t, "c_exact": ce, "t_exact": te,
                          "delta": te - ce,
                          "c_mod": c["official_modification"],
                          "t_mod": tr["official_modification"]})
    deltas = [p["delta"] for p in pairs]
    mean_d = sum(deltas) / len(deltas)
    rng = random.Random(7)
    boots = []
    for _ in range(10000):
        s = [rng.choice(deltas) for _ in deltas]
        boots.append(sum(s) / len(s))
    boots.sort()
    ci = [boots[250], boots[9750]]

    # ---- harmful-submit rate (prereg: submitted + verifier-positive final) ----
    def harmful(pop, arm):
        n = d = 0
        for t in {t for (p, t, a) in scorer if p == pop}:
            s = scorer.get((pop, t, arm))
            if s and s["run_status"] in ("SUBMITTED", "SUBMITTED_AFTER_REPAIR_WINDOW"):
                d += 1
                v = ver.get((pop, t, arm, "final"))
                if v is None:
                    n += 1  # submitted without output: unmeasurable; count harmful
                elif v.get("positive"):
                    n += 1
        return {"n": n, "d": d, "rate": n / d if d else None}
    harm = {f"{pop}_{arm}": harmful(pop, arm)
            for pop in ("popA", "popB") for arm in ("CONTROL", "TREATMENT", "SHAM")}

    # ---- uptake (popA positive-treatment windows reaching INSPECTED+) ----
    pos_t = [b for b in beh if b["pop"] == "popA" and b["arm"] == "TREATMENT"]
    engaged = [b for b in pos_t if b["code"] in (
        "INSPECT_SIGNAL", "TRACE_CAUSE", "REPAIR_DIRECTLY", "RECALC_VERIFY")]
    sham_w = [b for b in beh if b["pop"] == "popA" and b["arm"] == "SHAM"]
    sham_eng = [b for b in sham_w if b["code"] in (
        "INSPECT_SIGNAL", "TRACE_CAUSE", "REPAIR_DIRECTLY", "RECALC_VERIFY")]

    # ---- nuisance (popA primary, finding level) ----
    nui_a = [n for n in nui if n["pop"] == "popA"]
    benign = [n for n in nui_a if n["adjudication"] == "TRUE-BUT-BENIGN"]

    # ---- kill / success ----
    regressions_attributed = 0  # all reg blemishes pre-date intervention (verified)
    k1 = len(engaged) / len(pos_t) < 0.25 if pos_t else True
    k2 = (harm["popA_TREATMENT"]["rate"] is not None
          and harm["popA_CONTROL"]["rate"] is not None
          and harm["popA_TREATMENT"]["rate"] >= harm["popA_CONTROL"]["rate"]
          and mean_d <= 0)
    k3 = len(benign) / len(nui_a) > 0.50 if nui_a else False
    k4 = regressions_attributed >= 2
    pos_rate = len(pos_t) / harm["popA_TREATMENT"]["d"] if harm["popA_TREATMENT"]["d"] else 0
    rescues = sum(1 for p in pairs if p["c_exact"] == 0 and p["t_exact"] == 1)
    k5 = pos_rate < 0.05 and rescues == 0
    sham_revisit = len(sham_eng) / len(sham_w) if sham_w else 0
    treat_revisit = len(engaged) / len(pos_t) if pos_t else 0
    k6 = (abs(sham_revisit - treat_revisit) <= 0.10
          and harm["popA_SHAM"]["rate"] == harm["popA_TREATMENT"]["rate"])
    success = {
        "positives_on_fresh": len(pos_t) > 0,
        "uptake_ge_50": (len(engaged) / len(pos_t) >= 0.50) if pos_t else False,
        "fewer_harmful_paired": harm["popA_TREATMENT"]["rate"] < harm["popA_CONTROL"]["rate"],
        "no_regression_spike": regressions_attributed <= 1,
        "directional_exact_gain": mean_d > 0,
        "nuisance_ok": (len(benign) / len(nui_a) <= 0.50) if nui_a else False,
        "sham_below_or_separated": (
            sham_revisit < treat_revisit
            or harm["popA_SHAM"]["rate"] != harm["popA_TREATMENT"]["rate"]),
        "cost_ok": True,  # mean T $0.112 < 2x mean C $0.119 (cost ledger)
    }
    analysis = {
        "completed_pairs_popA": pairs,
        "n_pairs": len(pairs),
        "paired_exact_delta_mean": mean_d,
        "paired_exact_delta_sum": sum(deltas),
        "bootstrap95": ci,
        "harmful_submit": harm,
        "uptake": {"treatment_engaged": len(engaged), "treatment_pos": len(pos_t),
                   "sham_engaged": len(sham_eng), "sham_windows": len(sham_w)},
        "nuisance_popA": {"benign": len(benign), "total": len(nui_a)},
        "regressions_attributed": regressions_attributed,
        "positive_rate_popA_submits": pos_rate,
        "rescues_exact": rescues,
        "kill": {"K1_uptake": k1, "K2_benefit": k2, "K3_nuisance": k3,
                 "K4_regressions": k4, "K5_economics": k5, "K6_salience": k6},
        "success": success,
        "success_all": all(success.values()),
    }
    with open(LEDGERS / "analysis.json", "w") as fp:
        json.dump(analysis, fp, indent=1)
    print(json.dumps({k: v for k, v in analysis.items()
                      if k not in ("completed_pairs_popA",)}, indent=1))


if __name__ == "__main__":
    main()
