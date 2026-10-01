"""Phase-8A deterministic semantic gate; never a performance benchmark."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from librecalc_agent._frozen.eligibility import classify
from read_engine_phase7.fixture_probe import CASES as ORIGINAL, make_workbook
from read_engine_phase8a.certificate import certify

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
VENV = Path("/tmp/librecalc-hygiene-rc-v55taghk/venv/bin/python")
OBSERVER = ROOT / "read_engine_phase6/observer"
OVERLAY = HERE / "overlay"

# All bodies run against Phase-7's two-merge workbook. Expected route is
# reference unless the new positive proof certifies the *entire* source.
ADDED = [
    ("parenthesized_terminal", "print((ws.cell(2,2)).value)"),
    ("safe_comprehension", "print([ws.cell(2,c).value for c in [1,2]])"),
    ("safe_repeated", "print(ws.cell(2,2).value, ws.cell(6,5).data_type)"),
    ("dunder_getattribute", "f=ws.__getattribute__('cell')\nx=f(2,2)\nprint(type(x).__name__)"),
    ("dunder_getitem", "print(type(ws.__getitem__('B2')).__name__)"),
    ("operator_attrgetter", "import operator\nf=operator.attrgetter('cell')(ws)\nprint(type(f(2,2)).__name__)"),
    ("dynamic_getattr_method", "f=getattr(ws,'cell')\nprint(type(f(2,2)).__name__)"),
    ("method_in_tuple", "methods=(ws.cell,)\nprint(type(methods[0](2,2)).__name__)"),
    ("method_in_list", "methods=[ws.cell]\nprint(type(methods[0](2,2)).__name__)"),
    ("method_in_dict", "methods={'a':ws.cell}\nprint(type(methods['a'](2,2)).__name__)"),
    ("worksheet_alias", "ws2=ws\nprint(type(ws2.cell(2,2)).__name__)"),
    ("nested_worksheet_alias", "ws2=ws\nws3=ws2\nprint(type(ws3.cell(2,2)).__name__)"),
    ("dynamic_coordinate", "coord='B2'\nprint(type(ws[coord]).__name__)"),
    ("nested_workbook_subscript", "print(type(wb['Main']['B2']).__name__)"),
    ("helper_return_method", "def helper(x):\n return x.cell\nf=helper(ws)\nprint(type(f(2,2)).__name__)"),
    ("helper_cell_arg", "def helper(x):\n return type(x).__name__\nprint(helper(ws.cell(2,2)))"),
    ("lambda_cell", "f=lambda: ws.cell(2,2)\nprint(type(f()).__name__)"),
    ("generator_cell", "g=(ws.cell(2,2) for x in [1])\nprint(type(next(g)).__name__)"),
    ("walrus_cell", "print(type((x:=ws.cell(2,2))).__name__)"),
    ("ternary_cell", "print(type(ws.cell(2,2) if True else None).__name__)"),
    ("conditional_escape", "if True:\n x=ws.cell(2,2)\nelse:\n x=None\nprint(type(x).__name__)"),
    ("loop_escape", "for n in [1]:\n x=ws.cell(2,2)\nprint(type(x).__name__)"),
    ("eval_cell", "print(type(eval('ws.cell(2,2)')).__name__)"),
    ("exec_cell", "exec('x=ws.cell(2,2)')\nprint(type(x).__name__)"),
    ("dynamic_attribute_name", "name='cell'\nprint(type(getattr(ws,name)(2,2)).__name__)"),
    ("rebind_cell", "ws.cell=lambda row,column: 'rebound'\nprint(ws.cell(2,2))"),
    ("zero_literal_indirect", "print(type(ws.__getattribute__('cell')(2,2)).__name__)"),
    ("zero_cell_production", "print(wb.sheetnames)"),
    ("hash_cell", "print(isinstance(hash(ws.cell(2,2)),int))"),
    ("bool_cell", "print(bool(ws.cell(2,2)))"),
    ("str_cell", "print(str(ws.cell(2,2)))"),
    ("parent_identity_again", "print(ws.cell(2,2).parent is ws)"),
]


def source_for(body: str) -> str:
    return "import openpyxl\nwb=openpyxl.load_workbook('input.xlsx')\nws=wb['Main']\n" + body + "\n"


def command(source: str, workbook: Path, base: Path, arm: str) -> dict:
    work = base / arm.lower() / "work"
    work.mkdir(parents=True)
    shutil.copyfile(workbook, work / "input.xlsx")
    script = work / "workload.py"
    script.write_text(source)
    env = {k: v for k, v in os.environ.items() if k not in {
        "PYTHONPATH", "LIBRECALC_CONFIG", "LIBRECALC_RUN_CONTEXT",
        "READ_ENGINE_PHASE3_CONTEXT", "READ_ENGINE_PHASE6_CONTEXT"}
        and not k.startswith("CANDIDATE_A_")}
    env["XDG_CACHE_HOME"] = str((base / arm.lower() / "xdg").resolve())
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if arm == "PY":
        argv = [str(VENV), str(script.resolve())]
    else:
        selected = ROOT if arm == "H0" else OVERLAY
        argv = [str(OBSERVER), str(VENV), str(script.resolve()), str(work.resolve()),
                str((base / arm.lower() / "cache").resolve()),
                str((base / arm.lower() / "runs").resolve()), str(selected.resolve())]
    proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, timeout=180)
    events: list[dict] = []
    setup: dict = {}
    receipt: dict = {}
    if arm != "PY":
        last = base / arm.lower() / "runs/last_run.json"
        if last.exists():
            run = Path(json.loads(last.read_text())["run_dir"])
            if (run / "runtime_events.jsonl").exists():
                events = [json.loads(x) for x in (run / "runtime_events.jsonl").read_text().splitlines()]
            if (run / "setup.json").exists():
                setup = json.loads((run / "setup.json").read_text())
            if (run / "observer_receipt.json").exists():
                receipt = json.loads((run / "observer_receipt.json").read_text())
    return {"exit_code": proc.returncode, "stdout": proc.stdout.decode(errors="replace"),
            "stderr": proc.stderr.decode(errors="replace"),
            "events": {name: sum(e.get("event") == name for e in events) for name in
                       ("merged_child_contact", "merged_child_direct", "merged_child_reference",
                        "reference_parse", "direct_served_load")},
            "reference_reasons": [e.get("reason") for e in events if e.get("event") == "reference_parse"],
            "certificate": setup.get("merged_certificate"),
            "artifact_status": [x.get("status") for x in setup.get("artifacts", {}).values()],
            "capture_helper_exit": receipt.get("capture_helper_exit")}


def run_case(name: str, body: str, old_class: str | None, covered_count: int,
             workbook: Path, root: Path) -> dict:
    source = source_for(body)
    admission = classify(source)
    certificate = certify(source, admission)
    base = root / name
    shutil.rmtree(base, ignore_errors=True)
    results = {arm: command(source, workbook, base, arm) for arm in ("PY", "H0", "H1")}
    py, h0, h1 = (results[a] for a in ("PY", "H0", "H1"))
    observed_direct = h1["events"]["merged_child_direct"]
    should_direct = certificate["certified"]
    no_false_direct = observed_direct == 0 if not should_direct else True
    if old_class == "UNSUPPORTED/UNPROVEN" or name == "parent_identity_again":
        exactness = "KNOWN_PARENT_IDENTITY_LIMIT"
        output_gate = (h0["exit_code"], h0["stdout"]) == (h1["exit_code"], h1["stdout"])
    else:
        exactness = "EXACT" if (py["exit_code"], py["stdout"], py["stderr"]) == \
            (h1["exit_code"], h1["stdout"], h1["stderr"]) else "DIFFERENCE"
        output_gate = exactness == "EXACT"
    # Rejected sources may never create a proxy, so no merged event is expected.
    route_gate = (no_false_direct and (not should_direct or
                  (covered_count == 0 or observed_direct == covered_count)))
    passed = output_gate and route_gate and h1["capture_helper_exit"] == 0
    return {"case": name, "source": source, "old_classification": old_class,
            "admission": admission["decision"], "certificate": certificate,
            "expected_route": "DIRECT_CERTIFIED" if should_direct else "REFERENCE_OR_NO_CELL",
            "actual_route": "DIRECT" if observed_direct else ("REFERENCE" if h1["events"]["reference_parse"] else "NO_MERGED_CONTACT"),
            "exactness": exactness, "zero_false_positive_direct": no_false_direct,
            "passed": passed, "results": results}


def main() -> None:
    out = HERE / "certificate_matrix.jsonl"
    if out.exists():
        raise RuntimeError("Phase-8A matrix already exists")
    fixture = HERE / "certificate_fixtures/oracle.xlsx"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    make_workbook(fixture)
    cases = [(n, b, c, k) for n, b, c, k in ORIGINAL]
    cases.extend((n, b, None,
                  2 if n in {"safe_comprehension", "safe_repeated"} else 1)
                 for n, b in ADDED)
    with out.open("w") as stream:
        for pos, (name, body, old_class, count) in enumerate(cases, 1):
            row = run_case(name, body, old_class, count, fixture,
                           HERE / "certificate_fixtures/runs")
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()
            print(f"{pos}/{len(cases)} {name}: {row['certificate']['certified']} "
                  f"{row['exactness']} passed={row['passed']}", flush=True)
            if not row["passed"]:
                raise RuntimeError(f"Semantic fixture failed: {name}")


if __name__ == "__main__":
    main()
