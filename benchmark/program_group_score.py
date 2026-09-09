#!/usr/bin/env python3
"""Score the Phase C arms.

Three variants per unit, written with the same neutral archive-level writer,
recalculated by the same subprocess and scored by the same official comparison:

    SEED_ONLY   the seed proposal alone, the common starting point
    P0          seed plus every member solved independently
    P1          seed plus one canonical program translated across each group

P0 - SEED_ONLY measures what coordination buys under per-cell synthesis.
P1 - P0 measures the treatment: execution policy inside the group.

Gold is read only to judge answers after the fact, never to build a variant.
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
import execution_unit_score as S
import program_group as pg
import program_group_preflight as pf
import program_group_probe as C

WORK = C.OUT / "variants"


def addr(c):
    return f"{c[0]}!{cc.a1(c[1], c[2])}"


def build(task, name, edits):
    dest_dir = WORK / task / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{task}_output.xlsx"
    inp, _ = cc.workbook_paths(task)
    from xlsx_cell_writer import write_cells
    audit = write_cells(inp, dest, edits)
    old.write(dest_dir / "audit.json", {"variant": name, "edits": edits, "audit": audit})
    return dest


def edits_from(task, mapping: dict[str, str | None]) -> list[dict]:
    out = []
    for a, f in sorted(mapping.items()):
        if not f:
            continue
        cell = P.parse_addr(a)
        out.append({"sheet": cell[0], "address": cc.a1(cell[1], cell[2]), "formula": f})
    return out


def member_rows(task, rec, gold) -> list[dict]:
    rows = []
    for a in rec["members"]:
        cell = P.parse_addr(a)
        g = gold.get(cell)
        p0, p1 = rec["P0_formulas"].get(a), rec["P1_formulas"].get(a)
        in_group = a in rec["members_in_a_group"]
        rows.append({
            "member": a, "in_program_group": in_group,
            "in_gold_edit_set": g is not None, "gold_formula": g,
            "P0_formula": p0, "P1_formula": p1,
            "P0_outcome": rec["P0_outcomes"].get(a),
            "P0_exact": S._same(p0, g), "P1_exact": S._same(p1, g),
            "P0_fingerprint": (pg.formula_a1_shape(p0) == pg.formula_a1_shape(g))
                              if (p0 and g) else None,
            "P1_fingerprint": (pg.formula_a1_shape(p1) == pg.formula_a1_shape(g))
                              if (p1 and g) else None,
        })
    return rows


def program_consistency(rec) -> dict:
    """Do the arm's formulas for a group actually instantiate one program?"""
    out = {}
    for g in rec["program_groups"]:
        members = g["members"]
        canon = g["canonical_member"]

        def consistent(mapping):
            src = mapping.get(canon)
            if not src:
                return None
            for m in members:
                f = mapping.get(m)
                if not f:
                    return False
                try:
                    t = pg.translate(src, P.parse_addr(canon), P.parse_addr(m))
                except Exception:
                    return False
                if pg.canonical(t) != pg.canonical(f):
                    return False
            return True

        out[canon] = {"P0_program_consistent": consistent(rec["P0_formulas"]),
                      "P1_program_consistent": consistent(rec["P1_formulas"])}
    return out


def program_regime(task: str, group: dict, gold: dict, shapes: set[str]) -> dict:
    """Existing vs novel program, evaluator-side, plus the mechanical counterpart.

    Evaluator-side asks whether the gold program's *shape* already occurs
    somewhere in the input workbook. The mechanical label never sees gold: an
    eligible group has an input homologue by construction, so the harness can
    say a program is recoverable without knowing what it is. The labels are
    compared, never merged, and neither is shown to the model.
    """
    canon = P.parse_addr(group["canonical_member"])
    g = gold.get(canon)
    evaluator = None
    if g:
        evaluator = "EXISTING_PROGRAM" if pg.formula_a1_shape(g) in shapes else "NOVEL_PROGRAM"
    return {"evaluator_side": evaluator,
            "mechanical": "RECOVERABLE_EXISTING_PROGRAM",
            "witness_shape": group["witness"]["shape"],
            "gold_canonical_shape": pg.formula_a1_shape(g) if g else None,
            "witness_shape_matches_gold": (pg.formula_a1_shape(g) == group["witness"]["shape"])
                                          if g else None}


def score_units() -> dict:
    by_task = {}
    for p in sorted((C.OUT / "units").glob("*.json")):
        rec = old.load(p)
        by_task.setdefault(rec["unit"]["task"], []).append(rec)
    results = []
    for task, recs in sorted(by_task.items()):
        gold = pf.gold_map(task)
        shapes = {pg.formula_a1_shape(f) for f in pg.input_formulas(task).values()}
        variants, tags = {}, {}
        for rec in recs:
            u = rec["unit"]
            tag = u["seed"].replace("!", "_").replace(" ", "_")
            tags[u["seed"]] = tag
            if not rec.get("seed_formula"):
                continue
            seed_edit = {u["seed"]: rec["seed_formula"]}
            variants[f"{tag}__SEED"] = edits_from(task, seed_edit)
            variants[f"{tag}__P0"] = edits_from(task, {**seed_edit, **rec["P0_formulas"]})
            variants[f"{tag}__P1"] = edits_from(task, {**seed_edit, **rec["P1_formulas"]})
        if not variants:
            continue
        paths = {n: build(task, n, e) for n, e in variants.items()}
        ccf.recalculate(WORK / task)
        scored = {n: ccf.score(task, p) for n, p in paths.items()}
        strict = {n: S.strict_score(task, p) for n, p in paths.items()}
        cells = {n: S.correct_S(task, p) for n, p in paths.items()}
        g_off = cc.graph_input_plus_offset(task)[0]
        for rec in recs:
            u = rec["unit"]
            tag = tags[u["seed"]]
            row = {"task": task, "seed": u["seed"], "origin": u["origin"],
                   "seed_formula": rec.get("seed_formula"),
                   "seed_outcome": rec.get("seed_outcome"),
                   "closure_status": rec["closure_status"],
                   "n_members": len(rec["members"]),
                   "n_groups": len(rec["program_groups"]),
                   "members_in_a_group": rec["members_in_a_group"],
                   "members_not_in_any_group": rec["members_not_in_any_group"],
                   "group_refusals": rec["group_refusals"],
                   "P0_model_calls": rec["P0_model_calls"],
                   "P1_model_calls": rec["P1_model_calls"],
                   "members": member_rows(task, rec, gold),
                   "program_consistency": program_consistency(rec),
                   "program_regimes": {g["canonical_member"]: program_regime(task, g, gold, shapes)
                                       for g in rec["program_groups"]},
                   "program_groups": rec["program_groups"]}
            for arm in ("SEED", "P0", "P1"):
                key = f"{tag}__{arm}"
                row[arm] = scored.get(key)
                row[f"{arm}_strict"] = strict.get(key)
                ok = cells.get(key, (set(), {}))[0]
                row[f"{arm}_S_correct"] = len(ok)
            base, a0, a1 = (cells.get(f"{tag}__{x}", (set(), {}))[0] for x in ("SEED", "P0", "P1"))
            written = {P.parse_addr(a) for a, f in rec["P1_formulas"].items() if f}
            row["P1_newly_correct_vs_P0"] = sorted(addr(c) for c in a1 - a0)
            row["P1_lost_vs_P0"] = sorted(addr(c) for c in a0 - a1)
            row["P1_provenance_vs_seed"] = {addr(c): S.provenance(task, c, written, g_off)
                                            for c in sorted(a1 - base)}
            row["delta_modification_P1_vs_P0"] = S._delta(row["P1"], row["P0"], "modification_accuracy")
            row["delta_regression_P1_vs_P0"] = S._delta(row["P1"], row["P0"], "regression_accuracy")
            row["delta_modification_P0_vs_seed"] = S._delta(row["P0"], row["SEED"], "modification_accuracy")
            row["delta_modification_P1_vs_seed"] = S._delta(row["P1"], row["SEED"], "modification_accuracy")
            row["delta_modification_value_only_P1_vs_P0"] = S._dstrict(
                row.get("P1_strict"), row.get("P0_strict"), "modification")
            row["delta_regression_value_only_P1_vs_P0"] = S._dstrict(
                row.get("P1_strict"), row.get("P0_strict"), "regression")
            row["delta_modification_value_only_P1_vs_seed"] = S._dstrict(
                row.get("P1_strict"), row.get("SEED_strict"), "modification")
            results.append(row)
    out = {"units": results}
    old.write(C.OUT / "phase_c_scores.json", out)
    return out


if __name__ == "__main__":
    out = score_units()
    for r in out["units"]:
        print(json.dumps({k: r[k] for k in (
            "task", "seed", "n_members", "n_groups", "P0_model_calls", "P1_model_calls",
            "delta_modification_P1_vs_P0", "delta_modification_value_only_P1_vs_P0")}), flush=True)
