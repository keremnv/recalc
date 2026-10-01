#!/usr/bin/env python3
"""Post-hoc value-only rescoring of every stored Phase A variant.

The official comparator falls back to formula-text comparison whenever either
the gold cell or the output cell holds an Excel error string. A workbook that
propagates #VALUE! through formulas it never touched therefore earns credit for
those cells. This recomputes every stored Phase A variant with that fallback
disabled and reports the two numbers side by side.

The frozen Phase A results are not modified. This is a diagnostic.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_counterfactual as ccf
import end_to_end_composition_probe as old
import execution_unit_probe as P
import execution_unit_score as S


def run() -> dict:
    rows = []
    for xlsx in sorted(ccf.WORK.glob("*/*/*.xlsx")):
        task, variant = xlsx.parent.parent.name, xlsx.parent.name
        try:
            st = S.strict_score(task, xlsx)
        except Exception as exc:
            rows.append({"task": task, "variant": variant, "error": f"{type(exc).__name__}: {exc}"})
            continue
        rows.append({"task": task, "variant": variant,
                     "modification_official": st["modification"]["official_accuracy"],
                     "modification_value_only": st["modification"]["value_only_accuracy"],
                     "regression_official": st["regression"]["official_accuracy"],
                     "regression_value_only": st["regression"]["value_only_accuracy"],
                     "modification_cells_via_error_fallback": st["modification"]["correct_only_via_error_fallback"],
                     "regression_cells_via_error_fallback": st["regression"]["correct_only_via_error_fallback"]})
    good = [r for r in rows if "error" not in r]
    infl_mod = [r for r in good if r["modification_cells_via_error_fallback"]]
    infl_reg = [r for r in good if r["regression_cells_via_error_fallback"]]
    summary = {
        "variants_rescored": len(good), "variants_failed": len(rows) - len(good),
        "variants_with_inflated_modification": len(infl_mod),
        "variants_with_inflated_regression": len(infl_reg),
        "worst_modification_inflation": sorted(
            ({"task": r["task"], "variant": r["variant"],
              "official": r["modification_official"], "value_only": r["modification_value_only"],
              "gap": round((r["modification_official"] or 0) - (r["modification_value_only"] or 0), 6)}
             for r in good), key=lambda r: -r["gap"])[:12],
        "regression_below_one_by_value": sorted(
            ({"task": r["task"], "variant": r["variant"],
              "official": r["regression_official"], "value_only": r["regression_value_only"]}
             for r in good if (r["regression_value_only"] or 1) < 1.0),
            key=lambda r: r["value_only"])[:12],
    }
    out = {"summary": summary, "rows": rows}
    old.write(P.OUT / "phase_a_value_only_recheck.json", out)
    return out


if __name__ == "__main__":
    print(json.dumps(run()["summary"], indent=1))
