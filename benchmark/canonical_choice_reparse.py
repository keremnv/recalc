#!/usr/bin/env python3
"""Re-derive A1 outcomes from the retained raw responses, after two repairs.

Raw-response retention exists exactly for this. Two A1 answers were charged to
the model by the harness rather than by the model's own content:

    defect 10  a well-formed decision returned inside a single-key envelope,
               {"answer": "{...}"}, read as though the envelope were the answer
    defect 11  the A0 response schema returned to the A1 protocol: a formula
               with no declared decision, which is a real answer but not the one
               this arm asked for, and was being lumped into INVALID_OUTPUT

Neither repair calls the model, and neither invents content. The as-run records
are left untouched; this writes a parallel file, and the report shows both, so
the repair is visible rather than retroactive.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical_choice as cch
import canonical_choice_select as sel
import end_to_end_composition_probe as old


def run() -> dict:
    # Keyed by task as well as canonical: two tasks in this population share the
    # address "Ratio Analysis!C19", and keying on the address alone silently
    # resolved one of them against the other's candidate set.
    units = {(u["task"], u["canonical_member"]): u
             for u in old.load(sel.OUT / "units.json")["units"]}
    rows, changed = [], 0
    for p in sorted((sel.OUT / "choices").glob("*.json")):
        d = json.loads(p.read_text())
        task, _, rest = p.stem.partition("__")
        unit = next((u for (t, _c), u in units.items()
                     if t == task and rest == u["canonical_member"].replace("!", "_").replace(" ", "_")),
                    None)
        if unit is None:
            raise RuntimeError(f"no frozen unit matches {p.name}")
        outcome, cid, formula = cch.classify(d.get("parsed"), unit["candidates"])
        if d.get("failure_class"):          # non-model failures stay as they were
            outcome, cid, formula = d["outcome"], d["candidate_id"], d["formula"]
        row = {"task": unit["task"], "canonical_member": unit["canonical_member"],
               "as_run_outcome": d["outcome"], "as_run_formula": d["formula"],
               "reparsed_outcome": outcome, "reparsed_candidate_id": cid,
               "reparsed_formula": formula,
               "changed": outcome != d["outcome"]}
        changed += bool(row["changed"])
        rows.append(row)
    out = {"defects": ["10 single-key JSON envelope read as the answer",
                       "11 A0 response schema returned to the A1 protocol"],
           "model_calls_added": 0, "rows_changed": changed, "rows": rows}
    old.write(sel.OUT / "choices_reparsed.json", out)
    return out


if __name__ == "__main__":
    o = run()
    print(json.dumps({"rows_changed": o["rows_changed"]}))
    for r in o["rows"]:
        if r["changed"]:
            print(json.dumps(r))
