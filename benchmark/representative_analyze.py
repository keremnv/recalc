#!/usr/bin/env python3
"""Representative checkpoint: capability + deterministic-work economics.

Reads reps/*/ records (economics half needs no scores) and, when present,
capability_scores.json (capability half). Writes economics.json and
capability_summary.json. No model calls; pure accounting.

Deterministic-work credit rules (spec):
- Invisible machinery is credited only for measured deterministic work.
- Shared fixed costs are charged before claiming from-zero value.
- Token/cost deltas are stochastic and NEVER attributed to mechanisms.
- Censoring is reported separately; it is not capability loss.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "representative_architecture_checkpoint"
REPS = OUT / "reps"


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def slots() -> list[dict]:
    out = []
    for d in sorted(REPS.iterdir()):
        rr = d / "run_record.json"
        if not rr.exists():
            continue
        rec = json.loads(rr.read_text())
        rec["_dir"] = d
        out.append(rec)
    return out


def tt(r: dict) -> dict:
    """timing_totals with zero defaults (RUNNER_ERROR records lack them)."""
    return defaultdict(float, r.get("timing_totals") or {})


def economics(recs: list[dict]) -> dict:
    h0 = [r for r in recs if r["arm"] == "H0"]
    h1 = [r for r in recs if r["arm"] == "H1"]
    rep = {"n_h0": len(h0), "n_h1": len(h1)}

    # ---- substrate (H1, timed) ----
    init_s, refresh_s, rebuilds, refresh_calls = [], [], 0, 0
    init_bytes = []
    for r in h1:
        for s in load_jsonl(r["_dir"] / "substrate.jsonl"):
            if s.get("phase") == "initial":
                init_s.append(s.get("total_s", 0.0))
                init_bytes.append(s.get("db_bytes", 0))
            else:
                refresh_s.append(s.get("total_s", 0.0))
                refresh_calls += 1
                rebuilds += sum(1 for x in s.get("refreshes", [])
                                if x.get("rebuilt"))
    rep["substrate"] = {
        "initial_build_s_total": round(sum(init_s), 4),
        "initial_build_s_mean": round(mean(init_s), 4) if init_s else 0.0,
        "initial_db_bytes_mean": int(mean(init_bytes)) if init_bytes else 0,
        "refresh_s_total": round(sum(refresh_s), 4),
        "refresh_calls": refresh_calls,
        "rebuilds_after_initial": rebuilds,
        "subslot_substrate_total_s": round(sum(
            tt(r)["SUBSTRATE_TOTAL_S"] for r in h1), 4),
    }

    # ---- Candidate A contact (H1) + H0 counterfactuals ----
    accel_load, accel_op, fallbacks, fb_reasons = 0, 0, 0, Counter()
    accel_load_dur, h0_elig, h0_elig_dur, h0_rej, h0_rej_reasons = (
        [], [], [], [], Counter())
    a_ops = Counter()
    for r in recs:
        for row in load_jsonl(r["_dir"] / "candidate_a.jsonl"):
            st, op = row.get("status"), row.get("operation")
            if st == "ACCELERATED" and op == "load_workbook":
                accel_load += 1
                if row.get("duration_ns") is not None:
                    accel_load_dur.append(row["duration_ns"] / 1e9)
            elif st == "ACCELERATED":
                accel_op += 1
                a_ops[op] += 1
            elif st in ("PREDECLARED_FALLBACK", "RUNTIME_FALLBACK",
                        "FAIL_CLOSED"):
                fallbacks += 1
                fb_reasons[row.get("fallback_reason") or st] += 1
            elif st == "H0_COUNTERFACTUAL_ELIGIBLE":
                h0_elig.append(row)
                if row.get("duration_ns") is not None:
                    h0_elig_dur.append(row["duration_ns"] / 1e9)
            elif st == "H0_COUNTERFACTUAL_REJECTED":
                h0_rej.append(row)
                h0_rej_reasons[row.get("fallback_reason") or "?"] += 1
    elig_unit = mean(h0_elig_dur) if h0_elig_dur else 0.0
    rep["candidate_a"] = {
        "h1_accelerated_loads_parses_avoided": accel_load,
        "h1_accelerated_fast_path_s_total": round(sum(accel_load_dur), 4),
        "h1_accelerated_ops_nonload": accel_op,
        "h1_accelerated_ops_by_op": dict(a_ops),
        "h1_fallbacks": fallbacks,
        "h1_fallback_reasons": dict(fb_reasons),
        "h0_eligible_loads": len(h0_elig),
        "h0_eligible_unit_s_mean": round(elig_unit, 4),
        "h0_rejected_loads": len(h0_rej),
        "h0_reject_reasons": dict(h0_rej_reasons),
        # Avoided-parse valuation: H1 accelerated loads x H0 unit parse cost.
        "avoided_parse_s_estimate": round(accel_load * elig_unit, 4),
    }

    # ---- capture (H1, timed) ----
    cap_s, mutations, rtf, valf = 0.0, 0, 0, 0
    for r in h1:
        cap_s += tt(r)["CAPTURE_TOTAL_S"]
        t = r.get("h1_telemetry") or {}
        mutations += t.get("mutations", 0)
        rtf += t.get("runtime_failures", 0)
        valf += t.get("validation_failed", 0)
    # fidelity_primary.jsonl is cumulative across voided+valid runs. Voided
    # slots always precede their replacements, so for each (task,run) group
    # keep the LAST k records where k = the valid slot's mutation count.
    fidelity = load_jsonl(OUT / "fidelity_primary.jsonl")
    valid_mut = {(r["task_id"], r["run_id"]): (r.get("h1_telemetry") or {})
                 .get("mutations", 0) for r in h1}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for rec in fidelity:
        groups[(rec.get("task_id"), rec.get("run_id"))].append(rec)
    fidelity_valid = []
    for key, grp in groups.items():
        k = valid_mut.get(key, 0)
        fidelity_valid.extend(grp[len(grp) - k:] if k else [])
    rep["capture"] = {
        "capture_s_total": round(cap_s, 4),
        "capture_s_mean": round(cap_s / len(h1), 4) if h1 else 0.0,
        "mutations": mutations,
        "runtime_failures": rtf,
        "validation_failed": valf,
        "fidelity_records_raw": len(fidelity),
        "fidelity_records_valid": len(fidelity_valid),
    }

    # ---- helpers (both arms; shim rows only: python_pid present) ----
    help_stat: dict[str, dict] = {}
    for arm in ("H0", "H1"):
        calls, dur_by, slots_used, slots_n = 0, defaultdict(list), 0, 0
        for r in [x for x in recs if x["arm"] == arm]:
            slots_n += 1
            rows = [h for h in load_jsonl(r["_dir"] / "helpers.jsonl")
                    if h.get("event") == "helper_backend"
                    and "python_pid" in h]
            if rows:
                slots_used += 1
            calls += len(rows)
            for h in rows:
                dur_by[h.get("helper")].append(
                    h.get("duration_ns", 0) / 1e9)
        help_stat[arm] = {
            "slots_with_helper_use": slots_used, "slots_total": slots_n,
            "calls": calls,
            "mean_call_s_by_helper": {
                k: round(mean(v), 4) for k, v in dur_by.items()},
            "total_backend_s": round(
                sum(x for v in dur_by.values() for x in v), 4),
        }
    rep["helpers"] = help_stat

    # ---- shared-fixed vs marginal; from-zero ledger (H1 totals) ----
    h1_tool = sum(tt(r)["TOOL_TOTAL_S"] for r in h1)
    rep["ledger_h1_seconds"] = {
        "tool_total": round(h1_tool, 3),
        "substrate_initial_fixed": round(sum(init_s), 3),
        "substrate_refresh_marginal": round(sum(refresh_s), 3),
        "capture_marginal": round(cap_s, 3),
        "helper_backend_marginal": help_stat["H1"]["total_backend_s"],
    }

    # ---- spend: valid slots only (_spend.json includes voided runs) ----
    rep["spend_valid_slots_usd"] = round(sum(
        (r.get("efficiency") or {}).get("cost_usd", 0.0) for r in recs), 4)
    try:
        rep["spend_metered_total_usd"] = float(json.loads(
            (OUT / "_spend.json").read_text()).get("total_usd", 0.0))
    except (OSError, ValueError):
        rep["spend_metered_total_usd"] = None

    # ---- censoring (reported, never capability) ----
    rep["censoring"] = {
        arm: dict(Counter(r.get("censoring", "?") for r in rs))
        for arm, rs in (("H0", h0), ("H1", h1))}
    rep["run_status"] = {
        arm: dict(Counter(r.get("status", "?") for r in rs))
        for arm, rs in (("H0", h0), ("H1", h1))}
    return rep


def capability() -> dict | None:
    cp = OUT / "capability_scores.json"
    if not cp.exists():
        return None
    rows = json.load(open(cp))
    by = {(c["task_id"], c["arm"]): c for c in rows}
    tasks = sorted({c["task_id"] for c in rows})
    comp = {"tasks": len(tasks), "pairs": []}
    for t in tasks:
        a, b = by.get((t, "H0")), by.get((t, "H1"))
        if a is None or b is None:
            continue
        comp["pairs"].append({
            "task_id": t,
            "H0_completed": bool(a["output_produced"]),
            "H1_completed": bool(b["output_produced"]),
            "H0_mod": a["official_modification"],
            "H1_mod": b["official_modification"],
            "H0_reg": a["official_regression"],
            "H1_reg": b["official_regression"],
            "H0_status": a["run_status"], "H1_status": b["run_status"],
        })
    for arm in ("H0", "H1"):
        sub = [c for c in rows if c["arm"] == arm]
        done = [c for c in sub if c["output_produced"]]
        comp[arm] = {
            "n": len(sub),
            "completed": len(done),
            "mods": [c["official_modification"] for c in done
                     if c["official_modification"] is not None],
            "regs": [c["official_regression"] for c in done
                     if c["official_regression"] is not None],
        }
        for k in ("mods", "regs"):
            v = comp[arm][k]
            comp[arm][k + "_mean"] = round(mean(v), 4) if v else None
    disc = json.load(open(OUT / "capability_discordances.json")) \
        if (OUT / "capability_discordances.json").exists() else []
    comp["n_discordant"] = len(disc)
    return comp


def main() -> None:
    recs = slots()
    econ = economics(recs)
    json.dump(econ, open(OUT / "economics.json", "w"), indent=1)
    cap = capability()
    if cap is not None:
        json.dump(cap, open(OUT / "capability_summary.json", "w"), indent=1)
    print(f"economics over {len(recs)} slots; "
          f"capability: {'yes' if cap else 'scores pending'}")


if __name__ == "__main__":
    main()
