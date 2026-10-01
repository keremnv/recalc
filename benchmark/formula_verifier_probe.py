#!/usr/bin/env python3
"""Gated offline verifier: falsify candidate formulas with frozen checkers.

Phases:
  extract  — gold-blind substrate (no goldens, no candidate labels)
  evaluate — Phase A ORACLE paired verification (goldens as labels only)
  all      — extract, evaluate, Phase B only if the Phase A gate passes

No agents, OpenRouter, workbook writes, official scorer, classifiers, or LLMs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from fingerprint import a1_address, relative_fingerprint  # noqa: E402
from formula_completion_certs import load_grids  # noqa: E402
from formula_dependency_selection import build_graph, build_graph_from_grids  # noqa: E402
from formula_dependency_selection_probe import (  # noqa: E402
    _golden_path,
    _input_path,
    _load_slice,
    _task_list,
)
from formula_operational import build_view, collect_peers, parse_use_def_slots, reduction_of  # noqa: E402
from formula_operational_probe import classify_object  # noqa: E402
from formula_schema_probe import (  # noqa: E402
    GLM_OUT,
    ORACLE_CLASSES,
    SLICE_36,
    align_refs,
    parse_refs,
)
from formula_verifier import (  # noqa: E402
    DEFINITIONS,
    HARD_IDS,
    circular_workbook_meta,
    scc_stats,
    verify_formula,
)
from xlsx_metadata_repair import install  # noqa: E402

install()

OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-verifier-probe"
)
EMPTY_IDS = {"09_05:Ratio_Analysis !F31", "17_03:Assumptions!L104"}
EXTRA_CORRECT_CONTROLS = {
    "20_04:Revenue Driver!I19",
    "13_03:CF!K30",
    "13_03:CF!L30",
    "13_03:DCF!C12",
}
CYCLE_PAIR = {"09_05:Assumptions!K163", "09_05:Assumptions!L163"}
GLM_RUN = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/glm-5.3-flash-nonvisual-297-1"
)
GPT_RUN = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/gpt-5.6-sol-nonvisual-all-medium-1"
)
EDITS_CAP = 80


def _rate(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(n / d, 4)


def _parse_cell_id(cell_id: str) -> tuple[str, str, int, int]:
    from ranges import parse_a1_cell

    task_id, rest = cell_id.split(":", 1)
    sheet, addr = rest.split("!", 1)
    col, row = parse_a1_cell(addr)
    return task_id, sheet, col, row


def cmd_extract(views=None):
    slice_doc = _load_slice()
    score = json.loads((GLM_OUT / "score.json").read_text())
    by_id = {task["id"]: task for task in _task_list()}
    oracle_ids = [row["cell_id"] for row in score["oracle_where"]["cells"]]
    needed = sorted({cid.split(":", 1)[0] for cid in oracle_ids})
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    built = dict(views or {})
    payload: dict[str, Any] = {
        "extracted_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "direction_convention": "DATA_DEPENDENCE(S, C) = S → C",
        "definitions": DEFINITIONS,
        "oracle_ids": oracle_ids,
        "runtime_s": {},
        "tasks": {},
        "oracle_cells": {},
    }
    for item in slice_doc["tasks"]:
        task_id = item["id"]
        if task_id not in needed:
            continue
        task = by_id[task_id]
        source = _input_path(task)
        print(f"EXTRACT {task_id}", flush=True)
        t0 = time.perf_counter()
        if task_id not in built:
            built[task_id] = build_view(build_graph(source))
        view = built[task_id]
        circ = circular_workbook_meta(source)
        sccs = scc_stats(view)
        payload["tasks"][task_id] = {
            "graph": dict(view.graph.coverage),
            "circular": circ,
            "scc": {k: sccs[k] for k in ("n_nodes", "n_scc", "n_nontrivial_scc", "acyclic", "self_loop_n", "nontrivial_sample")},
        }
        payload["runtime_s"][task_id] = round(time.perf_counter() - t0, 3)
        print(
            f"  acyclic={sccs['acyclic']} nontrivial_scc={sccs['n_nontrivial_scc']} "
            f"iterate={circ.get('iterate')} t={payload['runtime_s'][task_id]}s",
            flush=True,
        )
        for cell_id in oracle_ids:
            if not cell_id.startswith(task_id + ":"):
                continue
            _tid, sheet, col, row = _parse_cell_id(cell_id)
            peers = collect_peers(view, sheet, col, row)
            payload["oracle_cells"][cell_id] = {
                "class": ORACLE_CLASSES.get(cell_id),
                "n_peers": peers["n_formula_peers"],
                "n_p1": peers["n_p1"],
                "n_p2": peers["n_p2"],
                "n_p3": peers["n_p3"],
                "peer_addresses": [p["address"] for p in peers["formula_peers"][:8]],
                "peer_formulas": [p["formula"] for p in peers["formula_peers"][:8]],
            }
        built[task_id]._scc_cache = sccs  # type: ignore[attr-defined]
    payload["runtime_s"]["all"] = round(time.perf_counter() - started, 3)
    dest = OUT / "verifier_extract.json"
    dest.write_text(json.dumps(payload) + "\n")
    print(f"EXTRACT {dest} runtime={payload['runtime_s']['all']}s", flush=True)
    return payload, built


def _label_for(cell_id: str, role: str, klass: str) -> str:
    if role == "gold":
        return "CORRECT"
    if klass == "CORRECT":
        return "CORRECT"
    if klass == "ALGEBRAIC_EQUIVALENT":
        return "EQUIVALENT_CORRECT"
    if klass == "EMPTY_GENERATION":
        return "EMPTY"
    return "WRONG"


def _pair_class(wrong_v: str, correct_v: str) -> str:
    wr, cr = wrong_v == "REJECT", correct_v == "REJECT"
    if wr and not cr:
        return "IDEAL"
    if wr and cr:
        return "BOTH_REJECTED"
    if (not wr) and cr:
        return "INVERTED"
    return "BOTH_SURVIVE"


def cmd_evaluate(extract: dict[str, Any], views=None) -> dict[str, Any]:
    glm_slice = json.loads(SLICE_36.read_text())
    gold_by = {
        cell["cell_id"]: cell.get("eval_golden_formula")
        for cell in glm_slice["cells"]
        if cell.get("eval_role") == "TRUE_TARGET"
    }
    score = json.loads((GLM_OUT / "score.json").read_text())
    pred_by = {row["cell_id"]: row.get("predicted") for row in score["oracle_where"]["cells"]}
    by_id = {task["id"]: task for task in _task_list()}
    needed = sorted({cid.split(":", 1)[0] for cid in extract["oracle_cells"]})
    built = dict(views or {})
    started = time.perf_counter()
    for task_id in needed:
        if task_id in built:
            continue
        print(f"EVAL-LOAD {task_id}", flush=True)
        built[task_id] = build_view(build_graph(_input_path(by_id[task_id])))
        built[task_id]._scc_cache = scc_stats(built[task_id])  # type: ignore[attr-defined]

    atomic: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    policies: list[dict[str, Any]] = []

    for cell_id, rec in extract["oracle_cells"].items():
        klass = rec["class"]
        task_id, sheet, col, row = _parse_cell_id(cell_id)
        view = built[task_id]
        sccs = getattr(view, "_scc_cache", None) or scc_stats(view)
        target = (sheet, col, row)
        pred = pred_by.get(cell_id)
        gold = gold_by.get(cell_id)
        aligned = align_refs(parse_refs(pred, sheet), parse_refs(gold, sheet))
        kind_pair = classify_object(pred, gold, aligned) if pred and gold else None
        items = []
        if pred:
            items.append(("model", pred, _label_for(cell_id, "model", klass)))
        if gold:
            items.append(("gold", gold, "CORRECT"))
        for role, formula, label in items:
            verified = verify_formula(view, target, formula, sccs=sccs)
            cand = {
                "target": cell_id,
                "role": role,
                "candidate_kind": verified["kind"] if role == "model" else (kind_pair or verified["kind"]),
                "object_kind_vs_gold": kind_pair,
                "candidate_formula": formula,
                "correctness_label": label,
                "class": klass,
                "n_peers": verified["n_peers"],
                "parsed": verified["parsed"],
            }
            candidates.append(cand)
            for row_out in verified["results"]:
                atomic.append({**cand, **row_out})
            for pol in verified["policies"]:
                policies.append({**cand, **pol})

    paired_targets = []
    by_target = defaultdict(dict)
    for cand in candidates:
        by_target[cand["target"]][cand["role"]] = cand
    for cell_id, roles in by_target.items():
        if "model" in roles and "gold" in roles and roles["model"]["correctness_label"] == "WRONG":
            paired_targets.append(cell_id)

    checker_ids = sorted({row["checker_id"] for row in atomic})
    per_checker = {}
    paired_tables = {}
    for cid in checker_ids:
        rows = [r for r in atomic if r["checker_id"] == cid]
        counts = {
            "wrong_rejected": 0,
            "wrong_passed": 0,
            "wrong_abstained": 0,
            "correct_rejected": 0,
            "correct_passed": 0,
            "correct_abstained": 0,
            "equivalent_correct_rejected": 0,
            "equivalent_correct_passed": 0,
            "equivalent_correct_abstained": 0,
        }
        for r in rows:
            lab = r["correctness_label"]
            v = r["verdict"].lower() + "d" if r["verdict"] != "PASS" else "passed"
            if r["verdict"] == "PASS":
                key_v = "passed"
            elif r["verdict"] == "REJECT":
                key_v = "rejected"
            else:
                key_v = "abstained"
            if lab == "WRONG":
                counts[f"wrong_{key_v}"] += 1
            elif lab == "CORRECT":
                counts[f"correct_{key_v}"] += 1
            elif lab == "EQUIVALENT_CORRECT":
                counts[f"equivalent_correct_{key_v}"] += 1
        n_wrong = counts["wrong_rejected"] + counts["wrong_passed"] + counts["wrong_abstained"]
        n_correct = (
            counts["correct_rejected"]
            + counts["correct_passed"]
            + counts["correct_abstained"]
            + counts["equivalent_correct_rejected"]
            + counts["equivalent_correct_passed"]
            + counts["equivalent_correct_abstained"]
        )
        n_rej = counts["wrong_rejected"] + counts["correct_rejected"] + counts["equivalent_correct_rejected"]
        pair_counts = Counter()
        pair_rows = []
        for cell_id in paired_targets:
            wr = next(
                (r for r in rows if r["target"] == cell_id and r["role"] == "model"),
                None,
            )
            cr = next(
                (r for r in rows if r["target"] == cell_id and r["role"] == "gold"),
                None,
            )
            if wr is None or cr is None:
                continue
            klass = _pair_class(wr["verdict"], cr["verdict"])
            pair_counts[klass] += 1
            pair_rows.append(
                {
                    "target": cell_id,
                    "wrong_verdict": wr["verdict"],
                    "correct_verdict": cr["verdict"],
                    "pair": klass,
                    "wrong_reason": wr.get("reason"),
                    "correct_reason": cr.get("reason"),
                    "support_count": wr.get("support_count"),
                }
            )
        per_checker[cid] = {
            **counts,
            "rejection_precision": _rate(counts["wrong_rejected"], n_rej),
            "wrong_rejection_recall": _rate(counts["wrong_rejected"], n_wrong),
            "correct_rejection_rate": _rate(
                counts["correct_rejected"] + counts["equivalent_correct_rejected"],
                n_correct,
            ),
            "paired": dict(pair_counts),
            "paired_ideal_rate": _rate(pair_counts["IDEAL"], len(pair_rows)),
            "n_paired": len(pair_rows),
        }
        paired_tables[cid] = pair_rows

    policy_summary = {}
    for name in ("H", "HE3", "HE5"):
        rows = [p for p in policies if p["policy"] == name]
        pair_counts = Counter()
        pair_rows = []
        correct_rej = 0
        n_correct = 0
        wrong_rej = 0
        n_wrong = 0
        for p in rows:
            if p["correctness_label"] == "WRONG":
                n_wrong += 1
                wrong_rej += int(p["verdict"] == "REJECT")
            if p["correctness_label"] in {"CORRECT", "EQUIVALENT_CORRECT"}:
                n_correct += 1
                correct_rej += int(p["verdict"] == "REJECT")
        for cell_id in paired_targets:
            wr = next((p for p in rows if p["target"] == cell_id and p["role"] == "model"), None)
            cr = next((p for p in rows if p["target"] == cell_id and p["role"] == "gold"), None)
            if wr and cr:
                klass = _pair_class(wr["verdict"], cr["verdict"])
                pair_counts[klass] += 1
                pair_rows.append(
                    {
                        "target": cell_id,
                        "wrong_verdict": wr["verdict"],
                        "correct_verdict": cr["verdict"],
                        "pair": klass,
                        "wrong_reject_ids": wr.get("reject_ids"),
                        "correct_reject_ids": cr.get("reject_ids"),
                    }
                )
        n_rej = wrong_rej + correct_rej
        policy_summary[name] = {
            "paired": dict(pair_counts),
            "paired_ideal_rate": _rate(pair_counts["IDEAL"], len(pair_rows)),
            "wrong_rejected": wrong_rej,
            "correct_rejected": correct_rej,
            "rejection_precision": _rate(wrong_rej, n_rej),
            "wrong_rejection_recall": _rate(wrong_rej, n_wrong),
            "correct_rejection_rate": _rate(correct_rej, n_correct),
            "pairs": pair_rows,
        }

    gate = _phase_a_gate(per_checker, paired_tables, policy_summary, extract)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_used": True,
        "golden_used_in_verification": False,
        "runtime_s": round(time.perf_counter() - started, 3),
        "n_candidates": len(candidates),
        "n_atomic": len(atomic),
        "n_paired_targets": len(paired_targets),
        "paired_targets": paired_targets,
        "empty_excluded": sorted(EMPTY_IDS),
        "candidates": [
            {k: c[k] for k in ("target", "role", "candidate_kind", "correctness_label", "candidate_formula", "class", "n_peers")}
            for c in candidates
        ],
        "per_checker": per_checker,
        "paired_tables": paired_tables,
        "policies": policy_summary,
        "circular_audit": {tid: t["circular"] | {"scc_acyclic": t["scc"]["acyclic"], "n_nontrivial_scc": t["scc"]["n_nontrivial_scc"]} for tid, t in extract["tasks"].items()},
        "gate": gate,
        "atomic": atomic,
    }
    dest = OUT / "evaluation.json"
    dest.write_text(json.dumps(report) + "\n")
    (OUT / "evaluation.md").write_text(_render(report, extract) + "\n")
    print(f"EVAL {dest} paired={len(paired_targets)} gate={gate['verdict']}", flush=True)
    return report


def _phase_a_gate(per_checker, paired_tables, policies, extract) -> dict[str, Any]:
    inverted_policies = [name for name, p in policies.items() if p["paired"].get("INVERTED")]
    correct_rej_policies = [name for name, p in policies.items() if p["correct_rejected"] > 0]
    family_hits = []
    for cid, stats in per_checker.items():
        if stats["paired"].get("IDEAL", 0) < 2:
            continue
        if (stats["correct_rejected"] + stats["equivalent_correct_rejected"]) > 0:
            continue
        ideal_targets = [r["target"] for r in paired_tables[cid] if r["pair"] == "IDEAL"]
        if len(set(ideal_targets)) < 2:
            continue
        family_hits.append({"checker_id": cid, "ideal_targets": sorted(set(ideal_targets))})
    cycle_only = False
    if family_hits:
        only_cycle = all(set(h["ideal_targets"]) <= CYCLE_PAIR for h in family_hits)
        hard_only = all(h["checker_id"].split("_")[0] in HARD_IDS or h["checker_id"] in HARD_IDS for h in family_hits)
        cycle_only = only_cycle and hard_only
    if policies["H"]["paired"].get("INVERTED") or policies["H"]["correct_rejected"] > 0:
        verdict = "UNSAFE"
        proceed_b = False
        note = "POLICY H rejected a correct/equivalent control or inverted."
    elif cycle_only:
        verdict = "ISOLATED_POSITIVE"
        proceed_b = False
        note = "Only K163/L163 cycle pair is IDEAL. Not a verifier architecture. No broad Phase B."
    elif family_hits:
        verdict = "PROMISING"
        proceed_b = True
        note = "At least one checker has >=2 IDEAL paired wins on >=2 targets with zero correct rejections."
    elif any(stats["paired"].get("INVERTED", 0) for stats in per_checker.values()):
        verdict = "UNSAFE"
        proceed_b = False
        note = "An atomic checker inverted (rejected gold while the wrong candidate survived)."
    else:
        verdict = "WEAK"
        proceed_b = False
        note = "Mostly ABSTAIN/BOTH_SURVIVE. Insufficient coverage."
    return {
        "verdict": verdict,
        "proceed_phase_b": proceed_b,
        "family_hits": family_hits,
        "inverted_policies": inverted_policies,
        "correct_rej_policies": correct_rej_policies,
        "note": note,
    }


def _render(report: dict[str, Any], extract: dict[str, Any]) -> str:
    g = report["gate"]
    lines = [
        "# Formula verifier — Phase A",
        "",
        f"Paired WRONG vs CORRECT targets: {report['n_paired_targets']}",
        f"Candidates: {report['n_candidates']}. Atomic rows: {report['n_atomic']}.",
        "",
        f"**{g['verdict']}** — {g['note']}",
        f"Proceed to Phase B: {g['proceed_phase_b']}",
        "",
        "## Circular-workbook audit",
        "",
        "| task | acyclic | nontrivial SCC | iterate |",
        "|------|:-------:|---------------:|:-------:|",
    ]
    for tid, rec in report["circular_audit"].items():
        lines.append(
            f"| {tid} | {rec['scc_acyclic']} | {rec['n_nontrivial_scc']} | {rec.get('iterate')} |"
        )
    lines += ["", "## Policies", ""]
    for name, p in report["policies"].items():
        lines.append(
            f"- POLICY {name}: paired={p['paired']} precision={p['rejection_precision']} "
            f"wrong_recall={p['wrong_rejection_recall']} correct_rej={p['correct_rejection_rate']}"
        )
        for row in p["pairs"]:
            if row["pair"] != "BOTH_SURVIVE":
                lines.append(
                    f"  - `{row['target']}` {row['pair']} W={row['wrong_verdict']} C={row['correct_verdict']} "
                    f"Wids={row.get('wrong_reject_ids')} Cids={row.get('correct_reject_ids')}"
                )
    lines += ["", "## Per-checker paired (non-BOTH_SURVIVE only)", ""]
    for cid, rows in report["paired_tables"].items():
        interesting = [r for r in rows if r["pair"] != "BOTH_SURVIVE"]
        if not interesting:
            continue
        stats = report["per_checker"][cid]
        lines.append(f"### {cid}  paired={stats['paired']} corr_rej={stats['correct_rejection_rate']}")
        for r in interesting:
            lines.append(
                f"- `{r['target']}` {r['pair']} W={r['wrong_verdict']} ({r['wrong_reason']}) "
                f"C={r['correct_verdict']} ({r['correct_reason']}) k_support={r['support_count']}"
            )
    lines += ["", "## Candidates", ""]
    for c in report["candidates"]:
        lines.append(
            f"- `{c['target']}` {c['role']} [{c['correctness_label']}] {c['candidate_kind']} "
            f"peers={c['n_peers']} `{c['candidate_formula']}`"
        )
    return "\n".join(lines)


def _formula_map(grids) -> dict[tuple[str, int, int], str]:
    return {(g.title, col, row): text for g in grids for (col, row), text in g.formulas.items()}


def _ref_box(formula: str, sheet: str, col: int, row: int):
    parsed = parse_use_def_slots(formula, sheet, col, row)
    if not parsed["slots"]:
        return None
    sheets = {slot["sheet"] for slot in parsed["slots"]}
    return (
        min(slot["c1"] for slot in parsed["slots"]),
        min(slot["r1"] for slot in parsed["slots"]),
        max(slot["c2"] for slot in parsed["slots"]),
        max(slot["r2"] for slot in parsed["slots"]),
        tuple(sorted(sheets)),
    )


def _label_historical(out_f: str, gold_f: str | None, sheet: str, col: int, row: int) -> str:
    if not gold_f:
        return "WRONG"
    fp_o = relative_fingerprint(out_f, col, row, sheet=sheet)
    fp_g = relative_fingerprint(gold_f, col, row, sheet=sheet)
    if not fp_o.opaque and not fp_g.opaque and fp_o.eq_id == fp_g.eq_id:
        return "CORRECT"
    r_o = reduction_of(out_f, parse_use_def_slots(out_f, sheet, col, row))
    r_g = reduction_of(gold_f, parse_use_def_slots(gold_f, sheet, col, row))
    if {r_o.get("operator"), r_g.get("operator")} <= {"SUM", "explicit_+"}:
        if _ref_box(out_f, sheet, col, row) == _ref_box(gold_f, sheet, col, row):
            return "EQUIVALENT_CORRECT"
    if fp_o.opaque or fp_g.opaque:
        return "AMBIGUOUS"
    return "WRONG"


def _policy_verdict(row: dict[str, Any], name: str) -> str:
    return next(p["verdict"] for p in row["policies"] if p["policy"] == name)


def _policy_reject_ids(row: dict[str, Any], name: str) -> list[str]:
    return list(next(p["reject_ids"] for p in row["policies"] if p["policy"] == name))


def _error_family(reject_ids: list[str], edit_kind: str) -> str:
    ids = set(reject_ids)
    if any(cid in {"A1", "A2", "A3", "A4"} for cid in ids):
        return "dependency_cycle"
    if "A5" in ids:
        return "invalid_reference"
    if any(cid.startswith(("D1", "D4")) for cid in ids):
        return "reduction_extent"
    if any(cid.startswith("C2") for cid in ids):
        return "literal_vs_reference"
    if any(cid.startswith(("B1", "B2", "B3", "C3")) for cid in ids):
        return "wrong_source_reference"
    if any(cid.startswith(("C1", "B5", "D2", "D3")) for cid in ids):
        return "formula_family_template"
    if edit_kind == "REGRESSION_EDIT":
        return "regression_edit"
    return "other"


def _pack_counts(counter: Counter) -> dict[str, Any]:
    n_rej = counter["wrong_rejected"] + counter["correct_rejected"]
    return {
        **dict(counter),
        "rejection_precision": _rate(counter["wrong_rejected"], n_rej),
        "wrong_rejection_recall": _rate(counter["wrong_rejected"], counter["n_wrong"]),
        "correct_rejection_rate": _rate(counter["correct_rejected"], counter["n_correct"]),
    }


def _summarize_phase_b(rows: list[dict[str, Any]], run_meta: dict[str, Any]) -> dict[str, Any]:
    evaluable = [r for r in rows if r["correctness_label"] in {"WRONG", "CORRECT", "EQUIVALENT_CORRECT"}]
    by_checker: dict[str, Counter] = defaultdict(Counter)
    by_policy: dict[str, Counter] = defaultdict(Counter)
    by_model: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    by_kind: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    wb: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    k10: dict[str, Counter] = defaultdict(Counter)
    families: dict[str, Counter] = defaultdict(Counter)
    for row in evaluable:
        lab = row["correctness_label"]
        model = row["model"]
        kind = row["edit_kind"]
        for res in row["results"]:
            cid = res["checker_id"]
            by_checker[cid]["n"] += 1
            by_checker[cid][res["verdict"]] += 1
            if lab == "WRONG":
                by_checker[cid]["n_wrong"] += 1
            else:
                by_checker[cid]["n_correct"] += 1
            if res["verdict"] == "REJECT":
                if lab == "WRONG":
                    by_checker[cid]["wrong_rejected"] += 1
                else:
                    by_checker[cid]["correct_rejected"] += 1
            if (
                res.get("checker_type") == "EMPIRICAL_EXACT"
                and res.get("k") == 3
                and (res.get("support_count") or 0) >= 10
            ):
                base = cid.rsplit("_", 1)[0] + "_k10"
                k10[base]["n"] += 1
                if lab == "WRONG":
                    k10[base]["n_wrong"] += 1
                else:
                    k10[base]["n_correct"] += 1
                if res["verdict"] == "REJECT":
                    k10[base]["REJECT"] += 1
                    if lab == "WRONG":
                        k10[base]["wrong_rejected"] += 1
                    else:
                        k10[base]["correct_rejected"] += 1
        h = _policy_verdict(row, "H")
        he3 = _policy_verdict(row, "HE3")
        emp = "REJECT" if he3 == "REJECT" and h != "REJECT" else ("PASS" if he3 == "PASS" else "ABSTAIN")
        for name, verdict in (("H", h), ("HE3", he3), ("HE5", _policy_verdict(row, "HE5")), ("EMPIRICAL_ONLY", emp)):
            by_policy[name]["n"] += 1
            by_policy[name][verdict] += 1
            by_model[model][name]["n"] += 1
            by_model[model][name][verdict] += 1
            by_kind[kind][name]["n"] += 1
            by_kind[kind][name][verdict] += 1
            if lab == "WRONG":
                by_policy[name]["n_wrong"] += 1
                by_model[model][name]["n_wrong"] += 1
                by_kind[kind][name]["n_wrong"] += 1
            else:
                by_policy[name]["n_correct"] += 1
                by_model[model][name]["n_correct"] += 1
                by_kind[kind][name]["n_correct"] += 1
            if verdict == "REJECT":
                if lab == "WRONG":
                    by_policy[name]["wrong_rejected"] += 1
                    by_model[model][name]["wrong_rejected"] += 1
                    by_kind[kind][name]["wrong_rejected"] += 1
                    wb[name]["wrong"][row["task_id"]] += 1
                else:
                    by_policy[name]["correct_rejected"] += 1
                    by_model[model][name]["correct_rejected"] += 1
                    by_kind[kind][name]["correct_rejected"] += 1
                    wb[name]["correct"][row["task_id"]] += 1
                fam = _error_family(_policy_reject_ids(row, "HE3" if name != "H" else "H"), kind)
                families[name][fam] += 1
    packed_c = {cid: _pack_counts(c) for cid, c in by_checker.items()}
    packed_p = {name: _pack_counts(c) for name, c in by_policy.items()}
    loo = {}
    for name in ("H", "HE3", "HE5", "EMPIRICAL_ONLY"):
        tasks = sorted({r["task_id"] for r in evaluable})
        loo[name] = []
        for held in tasks:
            wr = cr = 0
            for row in evaluable:
                if row["task_id"] == held:
                    continue
                if _policy_verdict(row, name if name != "EMPIRICAL_ONLY" else "HE3") != "REJECT":
                    continue
                if name == "EMPIRICAL_ONLY" and _policy_verdict(row, "H") == "REJECT":
                    continue
                if row["correctness_label"] == "WRONG":
                    wr += 1
                else:
                    cr += 1
            loo[name].append(
                {
                    "held_out": held,
                    "precision": _rate(wr, wr + cr),
                    "wrong_rejected": wr,
                    "correct_rejected": cr,
                }
            )
    examples = _phase_b_examples(evaluable)
    return {
        "run": run_meta,
        "n_rows": len(rows),
        "n_evaluable": len(evaluable),
        "n_ambiguous": sum(1 for r in rows if r["correctness_label"] == "AMBIGUOUS"),
        "label_counts": dict(Counter(r["correctness_label"] for r in rows)),
        "edit_kind_counts": dict(Counter(r["edit_kind"] for r in rows)),
        "per_checker": packed_c,
        "policies": packed_p,
        "per_model_policies": {
            model: {name: _pack_counts(c) for name, c in pols.items()}
            for model, pols in by_model.items()
        },
        "per_edit_kind_policies": {
            kind: {name: _pack_counts(c) for name, c in pols.items()}
            for kind, pols in by_kind.items()
        },
        "k10_empirical": {cid: _pack_counts(c) for cid, c in k10.items()},
        "error_families": {name: dict(c) for name, c in families.items()},
        "workbook_wrong_rejected": {name: dict(wb[name]["wrong"]) for name in wb},
        "workbook_correct_rejected": {name: dict(wb[name]["correct"]) for name in wb},
        "n_workbooks_wrong": {name: len(wb[name]["wrong"]) for name in wb},
        "n_workbooks_correct": {name: len(wb[name]["correct"]) for name in wb},
        "loo": loo,
        "examples": examples,
        "hard_vs_empirical": {
            "HARD": packed_p.get("H"),
            "EMPIRICAL_ONLY": packed_p.get("EMPIRICAL_ONLY"),
            "HE3": packed_p.get("HE3"),
            "HE5": packed_p.get("HE5"),
        },
        "emp_only_note": (
            "EMPIRICAL_ONLY counts HE3 rejections that POLICY H did not already fire. "
            "Any empirical rejection still fires HE3/HE5; they are not majority votes."
        ),
    }


def _phase_b_examples(evaluable: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {
        "true_rejection_H": [],
        "true_rejection_empirical_only": [],
        "false_rejection_H": [],
        "false_rejection_empirical": [],
        "safe_abstention_wrong": [],
        "missed_wrong": [],
    }
    for row in evaluable:
        h = _policy_verdict(row, "H")
        he3 = _policy_verdict(row, "HE3")
        lab = row["correctness_label"]
        rec = {
            "model": row["model"],
            "task_id": row["task_id"],
            "cell": row["cell"],
            "label": lab,
            "edit_kind": row["edit_kind"],
            "H": h,
            "HE3": he3,
            "reject_ids": sorted(set(_policy_reject_ids(row, "H") + _policy_reject_ids(row, "HE3"))),
            "formula": (row.get("candidate_formula") or "")[:160],
            "golden": (row.get("golden_formula") or "")[:160],
            "n_peers": row.get("n_peers"),
        }
        if lab == "WRONG" and h == "REJECT" and len(buckets["true_rejection_H"]) < 8:
            buckets["true_rejection_H"].append(rec)
        if lab == "WRONG" and h != "REJECT" and he3 == "REJECT" and len(buckets["true_rejection_empirical_only"]) < 8:
            buckets["true_rejection_empirical_only"].append(rec)
        if lab != "WRONG" and h == "REJECT" and len(buckets["false_rejection_H"]) < 8:
            buckets["false_rejection_H"].append(rec)
        if lab != "WRONG" and he3 == "REJECT" and len(buckets["false_rejection_empirical"]) < 8:
            buckets["false_rejection_empirical"].append(rec)
        if lab == "WRONG" and h == "ABSTAIN" and he3 == "ABSTAIN" and len(buckets["safe_abstention_wrong"]) < 8:
            buckets["safe_abstention_wrong"].append(rec)
        if lab == "WRONG" and h != "REJECT" and he3 != "REJECT" and len(buckets["missed_wrong"]) < 8:
            buckets["missed_wrong"].append(rec)
    return buckets


def _compact_verify_row(row: dict[str, Any]) -> dict[str, Any]:
    reject_ids = sorted(
        set(_policy_reject_ids(row, "H") + _policy_reject_ids(row, "HE3") + _policy_reject_ids(row, "HE5"))
    )
    rejecting = [
        {
            "checker_id": res["checker_id"],
            "verdict": res["verdict"],
            "reason": res.get("reason"),
            "support_count": res.get("support_count"),
            "k": res.get("k"),
        }
        for res in row["results"]
        if res["verdict"] == "REJECT"
    ]
    return {
        "model": row["model"],
        "task_id": row["task_id"],
        "cell": row["cell"],
        "label": row.get("correctness_label"),
        "edit_kind": row.get("edit_kind"),
        "n_peers": row.get("n_peers"),
        "H": _policy_verdict(row, "H"),
        "HE3": _policy_verdict(row, "HE3"),
        "HE5": _policy_verdict(row, "HE5"),
        "reject_ids": reject_ids,
        "rejecting": rejecting,
        "formula": (row.get("candidate_formula") or "")[:160],
        "golden": (row.get("golden_formula") or "")[:160],
    }


def cmd_phase_b(limit: int | None = None, stratum: str = "both") -> dict[str, Any]:
    by_id = {task["id"]: task for task in _task_list()}
    wanted = []
    if stratum in {"both", "glm"}:
        wanted.append(("glm-5.3-flash", GLM_RUN))
    if stratum in {"both", "gpt"} and GPT_RUN.is_dir():
        wanted.append(("gpt-5.6", GPT_RUN))
    started = time.perf_counter()
    verify_rows: list[dict[str, Any]] = []
    run_stats = {
        model: {
            "model": model,
            "run": run_root.name,
            "n_inspected": 0,
            "n_outputs": 0,
            "n_unreadable": 0,
            "n_formula_edits": 0,
            "n_truncated_tasks": 0,
            "n_no_formula_edits": 0,
        }
        for model, run_root in wanted
    }
    task_ids = sorted(
        {
            path.name.split("-", 1)[1]
            for _, run_root in wanted
            for path in run_root.iterdir()
            if path.is_dir() and path.name.startswith("Financial_Model-")
        }
    )
    if limit is not None:
        task_ids = task_ids[:limit]
    OUT.mkdir(parents=True, exist_ok=True)
    blind_path = OUT / "phase_b_verify.jsonl"
    if blind_path.exists():
        blind_path.unlink()
    n_graphs = 0
    for task_id in task_ids:
        task = by_id.get(task_id)
        if task is None:
            print(f"SKIP {task_id} missing dataset entry", flush=True)
            continue
        model_outputs = []
        for model_name, run_root in wanted:
            run_stats[model_name]["n_inspected"] += 1
            out_xlsx = run_root / f"Financial_Model-{task_id}" / "output.xlsx"
            if out_xlsx.is_file():
                run_stats[model_name]["n_outputs"] += 1
                model_outputs.append((model_name, out_xlsx))
        if not model_outputs:
            continue
        try:
            in_grids = load_grids(_input_path(task))
        except Exception as exc:
            print(f"SKIP {task_id} input {type(exc).__name__}", flush=True)
            continue
        in_f = _formula_map(in_grids)
        pending: list[tuple[str, list[tuple[str, int, int]], dict]] = []
        for model_name, out_xlsx in model_outputs:
            try:
                out_grids = load_grids(out_xlsx)
            except Exception as exc:
                run_stats[model_name]["n_unreadable"] += 1
                print(f"  SKIP {model_name} {task_id} output {type(exc).__name__}", flush=True)
                continue
            out_f = _formula_map(out_grids)
            changed = [key for key in sorted(out_f) if out_f.get(key) != in_f.get(key)]
            if not changed:
                run_stats[model_name]["n_no_formula_edits"] += 1
                continue
            n_changed = len(changed)
            if n_changed > EDITS_CAP:
                run_stats[model_name]["n_truncated_tasks"] += 1
                changed = changed[:EDITS_CAP]
            pending.append((model_name, changed, out_f))
            print(f"  {model_name} {task_id} formula_edits={n_changed}", flush=True)
        if not pending:
            continue
        t0 = time.perf_counter()
        view = build_view(build_graph_from_grids(in_grids))
        sccs = scc_stats(view)
        n_graphs += 1
        print(f"    graph {time.perf_counter()-t0:.1f}s acyclic={sccs['acyclic']}", flush=True)
        task_verify: list[dict[str, Any]] = []
        for model_name, changed, out_f in pending:
            for sheet, col, row in changed:
                cand = out_f[(sheet, col, row)]
                verified = verify_formula(view, (sheet, col, row), cand, sccs=sccs)
                rec = {
                    "model": model_name,
                    "task_id": task_id,
                    "cell": f"{sheet}!{a1_address(col, row)}",
                    "sheet": sheet,
                    "col": col,
                    "row": row,
                    "candidate_formula": cand,
                    "input_formula": in_f.get((sheet, col, row)),
                    "results": verified["results"],
                    "policies": verified["policies"],
                    "n_peers": verified.get("n_peers"),
                    "kind": verified.get("kind"),
                }
                task_verify.append(rec)
                run_stats[model_name]["n_formula_edits"] += 1
        with blind_path.open("a") as handle:
            for rec in task_verify:
                handle.write(
                    json.dumps(
                        {
                            "model": rec["model"],
                            "task_id": rec["task_id"],
                            "cell": rec["cell"],
                            "H": _policy_verdict(rec, "H"),
                            "HE3": _policy_verdict(rec, "HE3"),
                            "HE5": _policy_verdict(rec, "HE5"),
                            "n_peers": rec["n_peers"],
                            "kind": rec["kind"],
                        }
                    )
                    + "\n"
                )
        try:
            gold_f = _formula_map(load_grids(_golden_path(task)))
        except Exception as exc:
            print(f"  SKIP labels {task_id} {type(exc).__name__}", flush=True)
            gold_f = {}
        for rec in task_verify:
            key = (rec["sheet"], rec["col"], rec["row"])
            gold = gold_f.get(key)
            rec["golden_formula"] = gold
            if not gold_f:
                rec["correctness_label"] = "AMBIGUOUS"
            else:
                rec["correctness_label"] = _label_historical(rec["candidate_formula"], gold, *key)
            required = gold is not None and key not in in_f
            regression = gold is None or gold == rec["input_formula"]
            rec["edit_kind"] = (
                "REQUIRED_TARGET_EDIT"
                if required
                else ("REGRESSION_EDIT" if regression else "OTHER_EVALUABLE_EDIT")
            )
        verify_rows.extend(task_verify)
        print(f"    labeled {len(task_verify)} edits total_so_far={len(verify_rows)}", flush=True)
    summary = _summarize_phase_b(verify_rows, {"strata": list(run_stats.values()), "n_graphs": n_graphs})
    summary["runtime_s"] = round(time.perf_counter() - started, 3)
    summary["limit"] = limit
    summary["stratum"] = stratum
    compact_rows = [_compact_verify_row(r) for r in verify_rows]
    payload = {**summary, "rows": compact_rows}
    dest = OUT / "phase_b.json"
    dest.write_text(json.dumps(payload) + "\n")
    (OUT / "phase_b.md").write_text(_render_b(payload) + "\n")
    print(f"PHASE-B {dest} evaluable={summary['n_evaluable']} runtime={summary['runtime_s']}s", flush=True)
    return payload


def _render_b(payload: dict[str, Any]) -> str:
    lines = [
        "# Formula verifier — Phase B",
        "",
        str(payload.get("run")),
        f"evaluable={payload['n_evaluable']} ambiguous={payload['n_ambiguous']} labels={payload['label_counts']}",
        f"edit_kinds={payload.get('edit_kind_counts')} runtime_s={payload.get('runtime_s')}",
        "",
        "## Policies",
        "",
    ]
    for name, p in payload["policies"].items():
        lines.append(
            f"- {name}: n={p.get('n')} REJECT={p.get('REJECT', 0)} precision={p.get('rejection_precision')} "
            f"wrong_recall={p.get('wrong_rejection_recall')} correct_rej={p.get('correct_rejection_rate')} "
            f"wbs_wrong={payload.get('n_workbooks_wrong', {}).get(name)} "
            f"wbs_correct={payload.get('n_workbooks_correct', {}).get(name)}"
        )
    lines += ["", "## Hard vs empirical", ""]
    for name in ("H", "EMPIRICAL_ONLY", "HE3", "HE5"):
        p = (payload.get("hard_vs_empirical") or {}).get(name) or {}
        lines.append(
            f"- {name}: precision={p.get('rejection_precision')} recall={p.get('wrong_rejection_recall')} "
            f"corr_rej={p.get('correct_rejection_rate')} REJECT={p.get('REJECT', 0)}"
        )
    lines += ["", "## Hard checkers", ""]
    for cid in ("A1", "A2", "A3", "A4", "A5"):
        p = payload["per_checker"].get(cid)
        if not p:
            continue
        lines.append(
            f"- {cid}: precision={p.get('rejection_precision')} recall={p.get('wrong_rejection_recall')} "
            f"corr_rej={p.get('correct_rejection_rate')} REJECT={p.get('REJECT', 0)}"
        )
    interesting = [
        cid
        for cid, p in payload["per_checker"].items()
        if p.get("REJECT", 0) and cid not in HARD_IDS
    ]
    lines += ["", "## Empirical checkers with rejections", ""]
    for cid in sorted(interesting):
        p = payload["per_checker"][cid]
        lines.append(
            f"- {cid}: precision={p.get('rejection_precision')} recall={p.get('wrong_rejection_recall')} "
            f"corr_rej={p.get('correct_rejection_rate')} REJECT={p.get('REJECT', 0)}"
        )
    if payload.get("k10_empirical"):
        lines += ["", "## Empirical k>=10 slice (post-hoc on k=3 rows)", ""]
        for cid, p in sorted(payload["k10_empirical"].items()):
            lines.append(
                f"- {cid}: precision={p.get('rejection_precision')} corr_rej={p.get('correct_rejection_rate')} "
                f"REJECT={p.get('REJECT', 0)}"
            )
    lines += ["", "## Error families (rejected rows)", ""]
    for name, fam in (payload.get("error_families") or {}).items():
        lines.append(f"- {name}: {fam}")
    lines += ["", "## Examples", ""]
    for bucket, recs in (payload.get("examples") or {}).items():
        lines.append(f"### {bucket}")
        if not recs:
            lines.append("- (none)")
            continue
        for rec in recs[:5]:
            lines.append(
                f"- `{rec['task_id']}` `{rec['cell']}` {rec['label']} H={rec['H']} HE3={rec['HE3']} "
                f"ids={rec.get('reject_ids')} `{rec.get('formula')}`"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=("extract", "evaluate", "phase_b", "all"),
        nargs="?",
        default="all",
    )
    parser.add_argument("--limit", type=int, default=None, help="Phase B task cap")
    parser.add_argument("--stratum", choices=("both", "glm", "gpt"), default="both")
    args = parser.parse_args()
    extract = None
    views = None
    report = None
    if args.phase in ("extract", "all"):
        extract, views = cmd_extract()
    if args.phase in ("evaluate", "all"):
        if extract is None:
            extract = json.loads((OUT / "verifier_extract.json").read_text())
        report = cmd_evaluate(extract, views)
        if args.phase == "all" and not report["gate"]["proceed_phase_b"]:
            print(f"HARD STOP after Phase A: {report['gate']['verdict']}. Phase B not run.", flush=True)
            return
    if args.phase == "phase_b" or (
        args.phase == "all" and report and report["gate"]["proceed_phase_b"]
    ):
        cmd_phase_b(limit=args.limit, stratum=args.stratum)


if __name__ == "__main__":
    main()
