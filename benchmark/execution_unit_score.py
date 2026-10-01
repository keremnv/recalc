#!/usr/bin/env python3
"""Score the Phase B arms.

B0 actuates the seed cell alone. B1 actuates the identical seed proposal plus
the unit's other authorised members. Both arms are written with the same neutral
archive-level writer, recalculated by the same subprocess call the evaluation
harness uses, and scored by the same official comparison, so the arms differ in
exactly one thing: whether the coordinated members were solved too.

No gold content is ever written into a variant here. Gold appears only in the
diagnostics that ask, after the fact, whether a proposal was right.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import composition_counterfactual as ccf
import end_to_end_composition_probe as old
import execution_unit_probe as P
from xlsx_cell_writer import write_cells

WORK = P.OUT / "variants"
NON_MODEL = {"TRUNCATED_NO_CONTENT", "MODEL_ACCESS_FAILURE", "SESSION_RESOURCE_LIMIT"}


def build(task: str, name: str, edits: list[dict]) -> Path:
    inp, _ = cc.workbook_paths(task)
    dest_dir = WORK / task / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{task}_output.xlsx"
    audit = write_cells(inp, dest, edits)
    old.write(dest_dir / "audit.json", {"variant": name, "edits": edits, "audit": audit})
    return dest


def gold_formula(task: str, cell: cc.Cell) -> str | None:
    e = ccf.gold_edit(task, cell)
    return e["golden_payload"] if e else None


def edit_list(task: str, cells: list[tuple[cc.Cell, str]]) -> list[dict]:
    out = []
    for cell, formula in cells:
        out.append({"sheet": cell[0], "address": cc.a1(cell[1], cell[2]), "formula": formula})
    return out


def strict_score(task: str, path: Path) -> dict:
    """The official score, split by which comparison path earned each cell.

    The official comparator contains an error-value fallback: if either the gold
    cell or the output cell holds an Excel error string, that cell is compared by
    FORMULA TEXT instead of value. A workbook that propagates #VALUE! through
    untouched formulas therefore scores those cells correct, because their
    formula text never changed. Leaving a cell blank fails; breaking it passes.

    The frozen official number is never altered. This reports it next to a
    value-only number, so an inflated score cannot be read as workbook
    correctness.
    """
    import openpyxl
    sys.path.insert(0, str(cc.EVAL_DIR))
    from evaluation import (classify_cells_by_modification, parse_answer_position,
                            _find_sheet, _has_excel_error, _compare_cells, compare_cell_formula)
    inp, gold = cc.workbook_paths(task)
    wi = openpyxl.load_workbook(inp, data_only=True)
    wg = openpyxl.load_workbook(gold, data_only=True)
    wo = openpyxl.load_workbook(path, data_only=True)
    wif = openpyxl.load_workbook(inp, data_only=False)
    wgf = openpyxl.load_workbook(gold, data_only=False)
    wof = openpyxl.load_workbook(path, data_only=False)
    acc = {k: {"total": 0, "official_correct": 0, "value_correct": 0,
               "took_error_fallback": 0, "correct_only_via_error_fallback": 0}
           for k in ("regression", "modification")}
    for rng in parse_answer_position(cc.dataset()[task]["answer_position"]):
        sn, cr = (rng.split("!", 1) if "!" in rng else (wg.sheetnames[0], rng))
        sn, cr = sn.strip("'").strip(), cr.strip("'").strip()
        try:
            regs, mods = classify_cells_by_modification(wi, wg, sn, cr, False, False,
                                                        wb_input_formula=wif, wb_answer_formula=wgf)
        except Exception:
            continue
        wa, wu = _find_sheet(wg, sn), _find_sheet(wo, sn)
        waf, wuf = _find_sheet(wgf, sn), _find_sheet(wof, sn)
        if wu is None:
            continue
        for label, cells in (("regression", regs), ("modification", mods)):
            a = acc[label]
            for n in cells:
                a["total"] += 1
                ca, co = wa[n], wu[n]
                by_value = _compare_cells(ca, co, False, False)
                fallback = _has_excel_error(ca) or _has_excel_error(co)
                official = compare_cell_formula(waf[n], wuf[n]) if fallback else by_value
                a["official_correct"] += bool(official)
                a["value_correct"] += bool(by_value)
                a["took_error_fallback"] += bool(fallback)
                a["correct_only_via_error_fallback"] += bool(official and not by_value)
    for wb in (wi, wg, wo, wif, wgf, wof):
        wb.close()
    for a in acc.values():
        a["official_accuracy"] = round(a["official_correct"] / a["total"], 6) if a["total"] else None
        a["value_only_accuracy"] = round(a["value_correct"] / a["total"], 6) if a["total"] else None
    return acc


def correct_S(task: str, path: Path) -> tuple[set, dict]:
    """Which scorer modification cells this workbook gets right, by value.

    The comparison is the evaluator's: population S is compared by value, not by
    formula text, so a cell can be right here with a formula the gold never had.
    """
    import openpyxl
    mod, _, _ = cc.population_S(task)
    _, gold = cc.workbook_paths(task)
    wg = openpyxl.load_workbook(gold, data_only=True)
    wv = openpyxl.load_workbook(path, data_only=True)
    ok, detail = set(), {}
    for c in mod:
        try:
            g = wg[c[0]].cell(row=c[1], column=c[2]).value
            v = wv[c[0]].cell(row=c[1], column=c[2]).value
        except Exception:
            continue
        same = _value_equal(g, v)
        detail[f"{c[0]}!{cc.a1(c[1], c[2])}"] = {"gold": _j(g), "got": _j(v), "correct": same}
        if same:
            ok.add(c)
    wg.close(); wv.close()
    return ok, detail


def _j(v):
    return v if isinstance(v, (int, float, str, bool)) or v is None else str(v)


def _value_equal(a, b) -> bool:
    """The evaluator's own value semantics, not a stricter reimplementation.

    `compare_cell_value` uses a 1% relative tolerance and treats a set of
    "not meaningful" placeholders (#DIV/0!, #N/A, N/M, an em dash, ...) as
    mutually equivalent. Judging value correctness by any other rule would
    report a different population from the one the scorer credits.
    """
    sys.path.insert(0, str(cc.EVAL_DIR))
    from evaluation import compare_cell_value
    return bool(compare_cell_value(a, b))


def provenance(task: str, cell: cc.Cell, written: set[cc.Cell], g_off) -> str:
    """Where a newly correct scorer cell's credit came from."""
    if cell in written:
        return "DIRECTLY_EDITED_CELL"
    pre = g_off.get(cell) or set()
    if pre & written:
        return "RECALCULATED_DEPENDENT_DIRECT"
    seen, stack = set(), [cell]
    while stack:
        x = stack.pop()
        for u in (g_off.get(x) or set()):
            if u in written:
                return "RECALCULATED_DEPENDENT_TRANSITIVE"
            if u not in seen:
                seen.add(u); stack.append(u)
    return "UNEXPLAINED_BY_INPUT_SIDE_GRAPH"


def retrieval_conditioning(rec: dict) -> dict:
    """Was the evidence the unit needed actually in the seed session's reach?

    Retrieval is frozen for this experiment, so this only conditions results; it
    never changes what was run.
    """
    sess_path = P.OUT / f"sessions/{rec['unit']['task']}__{rec['unit']['seed_cell_id'].replace(':', '_')}.json"
    if not sess_path.exists():
        return {"available": False}
    s = old.load(sess_path)
    ws = set(s.get("working_set_ids") or [])
    calls = s.get("calls") or []
    return {"available": True,
            "working_set_size": len(ws),
            "sql_calls": len([c for c in calls if c.get("action") or c.get("sql")]),
            "result_too_large_firings": sum((c.get("result") or {}).get("status") == "RESULT_TOO_LARGE" for c in calls),
            "session_resource_limited": bool(s.get("session_resource_limited")),
            "retrieval_input_tokens": s.get("retrieval_input_tokens"),
            "synthesis_input_tokens": s.get("synthesis_input_tokens")}


def unit_records() -> list[dict]:
    return [old.load(p) for p in sorted((P.OUT / "units").glob("*.json"))]


def score_units() -> dict:
    rows, by_task = [], {}
    for rec in unit_records():
        u = rec["unit"]
        by_task.setdefault(u["task"], []).append(rec)
    results = []
    for task, recs in sorted(by_task.items()):
        variants = {}
        for rec in recs:
            u = rec["unit"]
            tag = u["seed"].replace("!", "_").replace(" ", "_")
            seed = tuple(u["seed_cell"])
            if not rec.get("seed_formula"):
                continue
            b0 = [(seed, rec["seed_formula"])]
            b1 = list(b0) + [(tuple(c), rec["member_formulas"].get(f"{c[0]}!{cc.a1(c[1], c[2])}"))
                             for c in rec["member_cells"]]
            b1 = [(c, f) for c, f in b1 if f]
            variants[f"{tag}__B0"] = edit_list(task, b0)
            variants[f"{tag}__B1"] = edit_list(task, b1)
        if not variants:
            results.extend(no_proposal_row(rec) for rec in recs)
            continue
        paths = {n: build(task, n, e) for n, e in variants.items()}
        ccf.recalculate(WORK / task)
        scored = {n: ccf.score(task, p) for n, p in paths.items()}
        s_ok = {n: correct_S(task, p) for n, p in paths.items()}
        strict = {n: strict_score(task, p) for n, p in paths.items()}
        g_off = cc.graph_input_plus_offset(task)[0]
        for rec in recs:
            u = rec["unit"]
            tag = u["seed"].replace("!", "_").replace(" ", "_")
            seed = tuple(u["seed_cell"])
            if not rec.get("seed_formula"):
                results.append(no_proposal_row(rec))
                continue
            b0, b1 = scored.get(f"{tag}__B0"), scored.get(f"{tag}__B1")
            n_written = len([c for c in rec["member_cells"]
                             if rec["member_formulas"].get(f"{c[0]}!{cc.a1(c[1], c[2])}")])
            seed_gold = gold_formula(task, seed)
            row = {
                "task": task, "seed": u["seed"], "regime": u["phase_a_regime"],
                "phase_a": {"n_U": u["phase_a_n_U"], "isolated_gain": u["phase_a_isolated_gain"],
                            "closure_gain": u["phase_a_closure_gain"], "cone": u["cone"]},
                "seed_status": rec["seed_status"], "seed_failure_class": rec.get("seed_failure_class"),
                "seed_parsed_status": rec.get("seed_parsed_status"),
                "seed_formula": rec.get("seed_formula"), "seed_gold_formula": seed_gold,
                "seed_formula_text_correct": _same(rec.get("seed_formula"), seed_gold),
                "closure_status": rec["closure_status"],
                "n_members": len(rec["member_cells"]), "n_members_with_proposal": n_written,
                "members": rec["members"],
                "member_text_correct": {m: _same(rec["member_formulas"].get(m),
                                                 gold_formula(task, P.parse_addr(m)))
                                        for m in rec["members"]},
                "member_in_gold_edit_set": {m: gold_formula(task, P.parse_addr(m)) is not None
                                            for m in rec["members"]},
                "B0": b0, "B1": b1,
                "B0_strict": strict.get(f"{tag}__B0"), "B1_strict": strict.get(f"{tag}__B1"),
                "arms_identical_by_construction": n_written == 0,
                "delta_modification": _delta(b1, b0, "modification_accuracy"),
                "delta_regression": _delta(b1, b0, "regression_accuracy"),
                "delta_modification_value_only": _dstrict(strict.get(f"{tag}__B1"),
                                                          strict.get(f"{tag}__B0"), "modification"),
                "delta_regression_value_only": _dstrict(strict.get(f"{tag}__B1"),
                                                        strict.get(f"{tag}__B0"), "regression"),
            }
            not_gold = [m for m in rec["members"]
                        if not row["member_in_gold_edit_set"][m]
                        and rec["member_formulas"].get(m)]
            row["members_written_outside_gold_edit_set"] = not_gold
            row["overreach"] = overreach(row, not_gold)
            ok0, det0 = s_ok.get(f"{tag}__B0", (set(), {}))
            ok1, det1 = s_ok.get(f"{tag}__B1", (set(), {}))
            written1 = {seed} | {tuple(c) for c in rec["member_cells"]
                                 if rec["member_formulas"].get(f"{c[0]}!{cc.a1(c[1], c[2])}")}
            newly = sorted(ok1 - ok0)
            lost = sorted(ok0 - ok1)
            row["scorer_cells"] = {
                "S_correct_B0": len(ok0), "S_correct_B1": len(ok1),
                "newly_correct_in_B1": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in newly],
                "lost_in_B1": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in lost],
                "provenance": {f"{c[0]}!{cc.a1(c[1], c[2])}": provenance(task, c, written1, g_off)
                               for c in newly},
            }
            row["seed_value_correct"] = det1.get(u["seed"], det0.get(u["seed"], {})).get("correct")
            row["seed_in_scorer_population_S"] = u["seed"] in det0 or u["seed"] in det1
            row["retrieval"] = retrieval_conditioning(rec)
            finalise(row, rec)
            results.append(row)
    return {"units": results}


def finalise(row: dict, rec: dict) -> dict:
    """Derived fields that depend only on stored scores, never on a recalculation."""
    task = rec["unit"]["task"]
    row["seed_formula_text_correct"] = _same(row.get("seed_formula"), row.get("seed_gold_formula"))
    row["member_text_correct"] = {m: _same(rec["member_formulas"].get(m),
                                           gold_formula(task, P.parse_addr(m)))
                                  for m in rec["members"]}
    row["member_in_gold_edit_set"] = {m: gold_formula(task, P.parse_addr(m)) is not None
                                      for m in rec["members"]}
    row["members_written_outside_gold_edit_set"] = [
        m for m in rec["members"]
        if not row["member_in_gold_edit_set"][m] and rec["member_formulas"].get(m)]
    row["overreach"] = overreach(row, row["members_written_outside_gold_edit_set"])
    row["earliest_loss"] = taxonomy(row)
    return row


def no_proposal_row(rec: dict) -> dict:
    """A unit whose seed returned no formula still belongs in the population."""
    u = rec["unit"]
    row = {"task": u["task"], "seed": u["seed"], "regime": u["phase_a_regime"],
           "phase_a": {"n_U": u["phase_a_n_U"], "isolated_gain": u["phase_a_isolated_gain"],
                       "closure_gain": u["phase_a_closure_gain"], "cone": u["cone"]},
           "seed_status": rec["seed_status"], "seed_failure_class": rec.get("seed_failure_class"),
           "seed_parsed_status": rec.get("seed_parsed_status"),
           "seed_formula": None,
           "seed_gold_formula": gold_formula(u["task"], tuple(u["seed_cell"])),
           "seed_formula_text_correct": None, "closure_status": rec["closure_status"],
           "n_members": 0, "n_members_with_proposal": 0, "members": [],
           "member_text_correct": {}, "member_in_gold_edit_set": {},
           "B0": None, "B1": None, "B0_strict": None, "B1_strict": None,
           "arms_identical_by_construction": True,
           "delta_modification": None, "delta_regression": None,
           "delta_modification_value_only": None, "delta_regression_value_only": None,
           "scorer_cells": None, "seed_value_correct": None,
           "seed_in_scorer_population_S": None,
           "retrieval": retrieval_conditioning(rec),
           "not_scored_reason": "the seed returned no formula, so neither arm writes anything"}
    return finalise(row, rec)


def _same(a, b):
    """Formula-text equality under the evaluator's own normalisation.

    `compare_cell_formula` ignores `$` absolute markers, case, and the legacy
    `=+` prefix. Judging text correctness more strictly than the scorer would
    report a lower number than the benchmark itself would credit, which is the
    same mistake as judging values more strictly than `compare_cell_value`.
    """
    if a is None or b is None:
        return None

    def norm(f):
        f = old.synth_tools._canonical_formula(f) or ""
        f = f.replace("$", "")
        return "=" + f[2:] if f.startswith("=+") else f

    return norm(a) == norm(b)


def _dstrict(s1, s0, label):
    if not s1 or not s0:
        return None
    a, b = s1[label]["value_only_accuracy"], s0[label]["value_only_accuracy"]
    return None if a is None or b is None else round(a - b, 6)


def _delta(b1, b0, key):
    if not b1 or not b0 or b1.get(key) is None or b0.get(key) is None:
        return None
    return round(b1[key] - b0[key], 6)


def taxonomy(row) -> str:
    """Earliest loss, using the spec's Phase B classes.

    F5A FORMULA_SYNTHESIS_FAILURE      target and evidence right, formula wrong
    F5B COMPOSITION_CLOSURE_INCOMPLETE formula right, required coordinated
                                       authorised edits absent
    F5C CLOSURE_OVERREACH              closure grouped edits that were not
                                       required, and execution suffered

    Non-model failure classes are never folded into these; they are their own
    outcome, because a truncated or refused call is not a wrong answer.
    """
    gained = (row["delta_modification_value_only"] or 0) > 0
    suffix = "_BUT_GAINED" if gained else ""
    if row["seed_failure_class"] in NON_MODEL:
        return f"NON_MODEL_{row['seed_failure_class']}"
    if row["seed_status"] != "PROPOSAL_RETURNED" or row["seed_parsed_status"] != "PROPOSED":
        return "F4_NO_PROPOSAL"
    if row["seed_formula_text_correct"] is False:
        return "F5A_FORMULA_SYNTHESIS_FAILURE" + suffix
    if row["overreach"] and not row["overreach"]["outweighed_by_gain"]:
        return "F5C_CLOSURE_OVERREACH"
    missing = (row["closure_status"] == "CLOSURE_EMPTY" and row["phase_a"]["n_U"] > 0)
    unsolved = row["n_members"] > row["n_members_with_proposal"]
    wrong_member = any(v is False for v in row["member_text_correct"].values())
    if missing or unsolved or wrong_member:
        return "F5B_COMPOSITION_CLOSURE_INCOMPLETE" + suffix
    if row["n_members"] == 0:
        return "NO_COORDINATION_AVAILABLE"
    if gained:
        return "GAIN_WITH_REGRESSION_COST" if row["overreach"] else "GAIN"
    if (row["delta_modification"] or 0) > 0:
        # The official number moved only through the error-value formula fallback.
        return "GAIN_OFFICIAL_ONLY_NOT_BY_VALUE"
    return "COORDINATION_WITHOUT_GAIN"


def overreach(row, members_not_in_gold) -> dict | None:
    """Closure grouped edits that were not required, and it cost something.

    Damage alone is not overreach. A unit that gains modification credit by value
    while nudging regression is coordination working, and calling that overreach
    would hide the result the experiment exists to measure. Overreach is damage
    that buys nothing.
    """
    harmed = (row["delta_regression"] or 0) < 0 or (row["delta_modification_value_only"] or 0) < 0
    if not harmed:
        return None
    rec = {"members_written_outside_gold_edit_set": members_not_in_gold,
           "delta_regression": row["delta_regression"],
           "delta_modification_value_only": row["delta_modification_value_only"]}
    rec["outweighed_by_gain"] = (row["delta_modification_value_only"] or 0) > 0
    return rec


def refinalise(recompute_cells: bool = False) -> dict:
    """Recompute derived fields from stored scores, without recalculating anything.

    With `recompute_cells`, the per-cell scorer analysis is rebuilt from the
    variant workbooks already on disk. No workbook is rewritten or recalculated,
    so the arms stay exactly as they were executed.
    """
    stored = {(r["task"], r["seed"]): r for r in old.load(P.OUT / "phase_b_scores.json")["units"]}
    out = []
    for rec in unit_records():
        u = rec["unit"]
        row = stored.get((u["task"], u["seed"]))
        if row is None:
            out.append(no_proposal_row(rec))
            continue
        if recompute_cells and row.get("scorer_cells"):
            task, tag = u["task"], u["seed"].replace("!", "_").replace(" ", "_")
            seed = tuple(u["seed_cell"])
            p0 = WORK / task / f"{tag}__B0" / f"{task}_output.xlsx"
            p1 = WORK / task / f"{tag}__B1" / f"{task}_output.xlsx"
            if p0.exists() and p1.exists():
                ok0, det0 = correct_S(task, p0)
                ok1, det1 = correct_S(task, p1)
                g_off = cc.graph_input_plus_offset(task)[0]
                written1 = {seed} | {tuple(c) for c in rec["member_cells"]
                                     if rec["member_formulas"].get(f"{c[0]}!{cc.a1(c[1], c[2])}")}
                newly, lost = sorted(ok1 - ok0), sorted(ok0 - ok1)
                row["scorer_cells"] = {
                    "S_correct_B0": len(ok0), "S_correct_B1": len(ok1),
                    "newly_correct_in_B1": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in newly],
                    "lost_in_B1": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in lost],
                    "provenance": {f"{c[0]}!{cc.a1(c[1], c[2])}": provenance(task, c, written1, g_off)
                                   for c in newly}}
                row["seed_value_correct"] = det1.get(u["seed"], det0.get(u["seed"], {})).get("correct")
        out.append(finalise(row, rec))
    return {"units": out}


if __name__ == "__main__":
    out = refinalise("--cells" in sys.argv) if "--finalise" in sys.argv else score_units()
    old.write(P.OUT / "phase_b_scores.json", out)
    for r in out["units"]:
        print(json.dumps({k: r[k] for k in ("task", "seed", "regime", "closure_status",
                                            "n_members", "n_members_with_proposal",
                                            "seed_formula_text_correct",
                                            "delta_modification", "earliest_loss")}), flush=True)
