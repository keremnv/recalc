"""Deterministic syntax mutations of one positively proved terminal read."""
from __future__ import annotations

import json
from pathlib import Path

from librecalc_agent._frozen.eligibility import classify
from read_engine_phase8a.certificate import certify

PREFIX = "import openpyxl\nwb=openpyxl.load_workbook('input.xlsx')\nws=wb['Main']\n"
MUTATIONS = [
    ("base_terminal", "print(ws.cell(2,2).value)", True),
    ("parenthesized", "print((ws.cell(2,2)).value)", True),
    ("safe_list_comp", "print([ws.cell(2,c).value for c in [1,2]])", True),
    ("object_assignment", "x=ws.cell(2,2)\nprint(x.value)", False),
    ("method_alias", "f=ws.cell\nprint(f(2,2).value)", False),
    ("dunder_method", "f=ws.__getattribute__('cell')\nprint(f(2,2).value)", False),
    ("dunder_subscript", "print(ws.__getitem__('B2').value)", False),
    ("literal_subscript", "print(ws['B2'].value)", False),
    ("helper_call", "def helper(x): return x.value\nprint(helper(ws.cell(2,2)))", False),
    ("list_storage", "xs=[ws.cell(2,2)]\nprint(xs[0].value)", False),
    ("dynamic_getattr", "name='cell'\nprint(getattr(ws,name)(2,2).value)", False),
    ("ternary_object", "print((ws.cell(2,2) if True else None).value)", False),
    ("walrus_object", "print((x:=ws.cell(2,2)).value)", False),
    ("generator_object", "print(next(ws.cell(2,2) for x in [1]).value)", False),
    ("no_cell", "print(wb.sheetnames)", False),
]


def main() -> None:
    out = Path(__file__).with_name("mutations.jsonl")
    with out.open("w") as stream:
        for name, body, expected in MUTATIONS:
            source = PREFIX + body + "\n"
            admission = classify(source)
            certificate = certify(source, admission)
            row = {"case": name, "admission": admission["decision"],
                   "certified": certificate["certified"], "expected": expected,
                   "reason": certificate["reason"], "passed": certificate["certified"] == expected}
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            if not row["passed"]:
                raise RuntimeError(f"mutation expectation failed: {name}")


if __name__ == "__main__":
    main()
