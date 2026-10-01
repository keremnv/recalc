#!/usr/bin/env python3
"""Phase A driver for the composition-closure probe. No model calls.

Selection is declared before any scoring and is stratified on two mechanical,
input-side covariates computed without touching the evaluator's answers:

    |U(t)|        upstream authorized edits the target depends on
    |D(t) cap S|  scorer cells whose value the target can reach

Stratifying on those covers the isolated-sufficient and composition-dependent
regimes by construction. It is not selection on outcome: neither quantity is a
score, and both are available to a runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import composition_counterfactual as cf
import end_to_end_composition_probe as old

OUT = cf.OUT
TASKS = ["07_03", "08_03", "08_04", "08_05", "14_05", "15_04", "17_03", "09_05"]
MANDATORY = {"07_03": ("Cashflow (Monthly)", 8, 4), "08_03": ("Income Statement", 69, 3)}
TARGETS_PER_TASK = 4
SAMPLE_PER_TASK = 30  # bounded, evenly spaced over F in address order


def seeds_of(task: str, t: cc.Cell, E_by_cell: dict) -> set[cc.Cell]:
    """Direct precedents of the gold formula for t.

    At runtime this comes from the model's own proposal; using gold here makes
    the closure an upper bound on what a correct proposal would expose, and the
    report says so rather than pretending the seed is free.
    """
    from integrated_hybrid_synthesis_probe import eval_tools as et
    import re
    e = E_by_cell.get(t)
    if not e or e.get("golden_kind") != "formula":
        return set()
    try:
        refs = et._ref_records(e["golden_payload"], t[0], t[1], t[2])
    except Exception:
        return set()
    out: set[cc.Cell] = set()
    led: list = []
    for ref in refs.get("points", []) + refs.get("ranges", []):
        m1 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", ref.get("start") or "")
        if not m1:
            continue
        r1, c1 = int(m1.group(2)), cc.col_index(m1.group(1))
        if ref.get("is_range"):
            m2 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", ref.get("end") or ref["start"])
            if not m2:
                continue
            r2, c2 = int(m2.group(2)), cc.col_index(m2.group(1))
            out |= cc._expand(ref["sheet"], min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2), led)
        else:
            out.add((ref["sheet"], r1, c1))
    return out


def analyse(task: str) -> dict:
    E = cc.population_E(task)
    F = cc.population_F(E)
    S, R, meta = cc.population_S(task)
    Ec = {(e["sheet"], e["row"], e["col"]) for e in E}
    Fc = {(e["sheet"], e["row"], e["col"]) for e in F}
    E_by_cell = {(e["sheet"], e["row"], e["col"]): e for e in E}
    g_in, led_in = cc.graph_input(task)
    g_off, led_off = cc.graph_input_plus_offset(task)
    succ = cc.successors(g_off)
    # Per-target reachability is the expensive part, so examine a bounded,
    # evenly spaced sample of F in address order rather than all of it. The
    # sample is deterministic and independent of any score.
    ordered = sorted(Fc)
    idx = sorted({round(k * (len(ordered) - 1) / max(1, SAMPLE_PER_TASK - 1)) for k in range(SAMPLE_PER_TASK)}) if ordered else []
    sample = [ordered[i] for i in idx]
    for m in ([MANDATORY[task]] if task in MANDATORY else []):
        if m in Fc and m not in sample:
            sample.append(m)
    rows = []
    for t in sample:
        seeds = seeds_of(task, t, E_by_cell)
        u_static = set()
        u_offset = set()
        for s in seeds:
            u_static |= cc.ancestors_within(s, g_in, Ec)
            u_offset |= cc.ancestors_within(s, g_off, Ec)
        u_static |= (seeds & Ec)
        u_offset |= (seeds & Ec)
        u_static.discard(t)
        u_offset.discard(t)
        cone = cc.descendants_within(t, succ, S, is_succ=True)
        rows.append({"cell": t, "address": f"{t[0]}!{cc.a1(t[1], t[2])}",
                     "edit_type": E_by_cell[t]["edit_type"], "in_S": t in S,
                     "n_seeds": len(seeds), "U_static": sorted(u_static), "U_offset": sorted(u_offset),
                     "n_U_static": len(u_static), "n_U_offset": len(u_offset),
                     "cone": len(cone), "cone_fraction": round(len(cone) / len(S), 6) if S else 0.0})
    return {"task": task, "E": E, "F_cells": sorted(Fc), "S": sorted(S),
            "sampled_targets": len(rows), "F_total": len(Fc),
            "counts": {"E": len(Ec), "F": len(Fc), "S": len(S), "regression_cells": len(R),
                       "E_and_S": len(Ec & S), "E_not_S": len(Ec - S), "S_not_E": len(S - Ec),
                       "edit_types": dict(Counter(e["edit_type"] for e in E))},
            "answer_position_ranges": meta["answer_position_ranges"],
            "ledger": {"input_graph": led_in, "offset": [x for x in led_off if x not in led_in]},
            "targets": rows}


def select():
    analyses, selection = {}, []
    for task in TASKS:
        try:
            a = analyse(task)
        except Exception as exc:
            selection.append({"task": task, "skipped": f"{type(exc).__name__}: {exc}"})
            continue
        analyses[task] = a
        old.write(OUT / f"analysis/{task}.json", a)
        rows = a["targets"]
        chosen: list[dict] = []
        if task in MANDATORY:
            m = next((r for r in rows if tuple(r["cell"]) == MANDATORY[task]), None)
            if m:
                chosen.append({**m, "why": "mandatory diagnostic"})
        # One target per (needs upstream?, has downstream reach?) quadrant, in
        # deterministic address order. Both covariates are input-side.
        for need_u in (True, False):
            for has_cone in (True, False):
                if len(chosen) >= TARGETS_PER_TASK:
                    break
                pick = next((r for r in rows
                             if (r["n_U_offset"] > 0) == need_u and (r["cone"] > 0) == has_cone
                             and r["in_S"] and all(tuple(r["cell"]) != tuple(c["cell"]) for c in chosen)), None)
                if pick:
                    chosen.append({**pick, "why": f"quadrant U{'+' if need_u else '0'}/D{'+' if has_cone else '0'}"})
        for r in chosen:
            selection.append({"task": task, **{k: r[k] for k in
                              ("address", "cell", "edit_type", "n_U_static", "n_U_offset", "cone", "cone_fraction", "in_S", "why")}})
    payload = {"tasks": TASKS, "targets_per_task": TARGETS_PER_TASK,
               "stratification": "deterministic address order within (|U|>0, |cone|>0) quadrants, mandatory diagnostics first",
               "selected": selection,
               "sha256": hashlib.sha256(json.dumps(selection, sort_keys=True, default=str).encode()).hexdigest()}
    old.write(OUT / "selection.json", payload)
    print(json.dumps({"n": len(selection), "by_task": dict(Counter(s["task"] for s in selection))}))
    for s in selection:
        if "skipped" in s:
            print("  SKIP", s["task"], s["skipped"])
        else:
            print(f"  {s['task']} {s['address']:34} U_static={s['n_U_static']:3} U_off={s['n_U_offset']:3} cone={s['cone']:5} ({s['cone_fraction']:.3f}) {s['why']}")


def operation_of(task: str, E: list[dict]) -> dict:
    """A deterministic stand-in for 'the same Edit Plan operation'.

    Built only from components already earned: the sheet, and the relative
    fingerprint of the gold formula. No finance ontology and no new semantic
    role is introduced; two cells share an operation when they write the same
    program shape on the same sheet.
    """
    synth = old.synth_tools
    out = {}
    for e in E:
        if e.get("golden_kind") != "formula":
            continue
        try:
            fp = synth.relative_fingerprint(e["golden_payload"], e["col"], e["row"], sheet=e["sheet"])
            eq = None if fp.opaque else fp.eq_id
        except Exception:
            eq = None
        out[(e["sheet"], e["row"], e["col"])] = (e["sheet"], eq)
    return out


def closure_rules(task: str) -> dict:
    """C0..C5 for every sampled target. C2, C3, C5 are evaluator-side ceilings."""
    a = old.load(OUT / f"analysis/{task}.json")
    E = a["E"]
    Ec = {(e["sheet"], e["row"], e["col"]) for e in E}
    E_by_cell = {(e["sheet"], e["row"], e["col"]): e for e in E}
    g_off, _ = cc.graph_input_plus_offset(task)
    g_gold, led_gold = cc.graph_gold(task)
    g_union = {k: set(v) for k, v in g_off.items()}
    for k, v in g_gold.items():
        g_union.setdefault(k, set()).update(v)
    succ_union = cc.successors(g_union)
    ops = operation_of(task, E)
    by_op = defaultdict(set)
    for cell, op in ops.items():
        if op[1] is not None:
            by_op[op].add(cell)
    out = {}
    for r in a["targets"]:
        t = tuple(r["cell"])
        seeds = seeds_of(task, t, E_by_cell)
        c1 = {tuple(x) for x in r["U_offset"]}
        c2 = set()
        for sd in seeds:
            c2 |= cc.ancestors_within(sd, g_union, Ec)
        c2 |= (seeds & Ec)
        c2.discard(t)
        op = ops.get(t)
        c3 = (by_op.get(op, set()) - {t}) if op and op[1] is not None else set()
        connected = cc.ancestors_within(t, g_union, Ec) | cc.descendants_within(t, succ_union, Ec, is_succ=True) | c2
        c4 = c3 & connected
        c5 = connected - {t}
        out[r["address"]] = {"C0": [], "C1": sorted(c1), "C2": sorted(c2), "C3": sorted(c3),
                             "C4": sorted(c4), "C5": sorted(c5),
                             "sizes": {k: len(v) for k, v in
                                       (("C0", []), ("C1", c1), ("C2", c2), ("C3", c3), ("C4", c4), ("C5", c5))}}
    return {"task": task, "rules": out, "gold_graph_ledger": led_gold[:200], "n_gold_ledger": len(led_gold)}


def rules():
    for task in TASKS:
        if not (OUT / f"analysis/{task}.json").exists() or (OUT / f"rules/{task}.json").exists():
            continue
        r = closure_rules(task)
        old.write(OUT / f"rules/{task}.json", r)
        print(task, {k: v["sizes"] for k, v in list(r["rules"].items())[:3]}, flush=True)


def _tuple(c):
    return tuple(c) if not isinstance(c, tuple) else c


def counterfactual():
    """Score W0, W1, closure and full variants. Gold edits are harness-only."""
    sel = old.load(OUT / "selection.json")["selected"]
    by_task = defaultdict(list)
    for s in sel:
        if "skipped" not in s:
            by_task[s["task"]].append(s)
    for task, targets in sorted(by_task.items()):
        if (OUT / f"counterfactual/{task}.json").exists():
            continue
        a = old.load(OUT / f"analysis/{task}.json")
        rows = {tuple(r["cell"]): r for r in a["targets"]}
        Ec = {tuple(c) for c in a["F_cells"]} | {(e["sheet"], e["row"], e["col"]) for e in a["E"]}
        variants = {"W0_none": set(), "WFULL": Ec}
        probes = []
        for s in targets:
            t = _tuple(s["cell"])
            probes.append(t)
            r = rows[t]
            variants[f"W1__{r['address']}"] = {t}
            u = {tuple(x) for x in r["U_offset"]}
            if u:
                variants[f"WC1__{r['address']}"] = {t} | u
                variants[f"WCONLY__{r['address']}"] = u
        res = cf.run_variants(task, variants, probes)
        old.write(OUT / f"counterfactual/{task}.json",
                  {"task": task, "variants": {k: sorted(v) for k, v in variants.items()}, "scores": res})
        base = res["W0_none"]["modification_accuracy"]
        for s in targets:
            r = rows[_tuple(s["cell"])]
            w1 = res[f"W1__{r['address']}"]["modification_accuracy"]
            wc = res.get(f"WC1__{r['address']}", {}).get("modification_accuracy")
            print(f"{task} {r['address']:34} isolated={w1 - base:+.6f} closure={(wc - w1) if wc is not None else float('nan'):+.6f} "
                  f"U={r['n_U_offset']:3} cone={r['cone']:5}", flush=True)


def minimal():
    """Backward elimination over a closure that helped, to a local fixpoint."""
    out = {}
    for path in sorted((OUT / "counterfactual").glob("*.json")):
        task = path.stem
        cfd = old.load(path)
        a = old.load(OUT / f"analysis/{task}.json")
        rows = {tuple(r["cell"]): r for r in a["targets"]}
        for key, sc in cfd["scores"].items():
            if not key.startswith("WC1__"):
                continue
            addr = key[len("WC1__"):]
            t = next((c for c, r in rows.items() if r["address"] == addr), None)
            if t is None:
                continue
            w1 = cfd["scores"][f"W1__{addr}"]
            improved = (sc["probe_cells"][addr]["correct"] and not w1["probe_cells"][addr]["correct"]) or \
                       (sc["modification_accuracy"] or 0) > (w1["modification_accuracy"] or 0) + 1e-9
            if not improved:
                continue
            members = [tuple(x) for x in rows[t]["U_offset"]]
            keep = list(members)
            trial = 0
            for e in members:
                cand = [x for x in keep if x != e]
                name = f"MIN__{addr}__drop{trial}"
                res = cf.run_variants(task, {name: {t} | set(cand)}, [t])[name]
                trial += 1
                still = res["probe_cells"][addr]["correct"] and \
                    (res["modification_accuracy"] or 0) >= (sc["modification_accuracy"] or 0) - 1e-9
                if still:
                    keep = cand
            out[f"{task}::{addr}"] = {"task": task, "target": addr, "closure_size": len(members),
                                      "minimal_size": len(keep),
                                      "minimal_members": [f"{s}!{cc.a1(r, c)}" for s, r, c in keep],
                                      "removed": [f"{s}!{cc.a1(r, c)}" for s, r, c in members if x_not_in(keep, (s, r, c))]}
            print(json.dumps(out[f"{task}::{addr}"]), flush=True)
    old.write(OUT / "minimal_sufficient.json", out)


def x_not_in(keep, c):
    return all(tuple(k) != tuple(c) for k in keep)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["select", "counterfactual", "minimal", "rules"])
    a = p.parse_args()
    {"select": select, "counterfactual": counterfactual, "minimal": minimal, "rules": rules}[a.command]()
