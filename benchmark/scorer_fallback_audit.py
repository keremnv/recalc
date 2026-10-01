#!/usr/bin/env python3
"""Which side of the comparison held the error, when the scorer fell back.

The error-value fallback is defensible when the *gold* cell is itself an error:
comparing formula text is then a reasonable way to accept a matching answer.
It is not defensible when only the *output* holds the error, because there the
fallback credits a broken workbook for formulas it never touched.

This splits the fallback firings by side so the defect is not overstated.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import end_to_end_composition_probe as old
import execution_unit_probe as P


def audit(task: str, path: Path) -> dict:
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
    acc = {k: {"total": 0, "gold_is_error": 0, "output_only_is_error": 0,
               "credited_because_output_only_is_error": 0}
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
                ga, go = _has_excel_error(ca), _has_excel_error(co)
                if ga:
                    a["gold_is_error"] += 1
                elif go:
                    a["output_only_is_error"] += 1
                    if compare_cell_formula(waf[n], wuf[n]) and not _compare_cells(ca, co, False, False):
                        a["credited_because_output_only_is_error"] += 1
    for wb in (wi, wg, wo, wif, wgf, wof):
        wb.close()
    return acc


if __name__ == "__main__":
    out = {}
    for xlsx in sorted(P.OUT.glob("variants/*/*/*.xlsx")):
        task, variant = xlsx.parent.parent.name, xlsx.parent.name
        out[f"{task}/{variant}"] = audit(task, xlsx)
        print(json.dumps({f"{task}/{variant}": out[f"{task}/{variant}"]}), flush=True)
    old.write(P.OUT / "scorer_fallback_audit.json", out)
