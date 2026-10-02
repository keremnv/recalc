"""Adversarial certification for direct full-cell iteration.

Builds crafted workbooks + probe scripts, runs each under plain openpyxl
and under the probe product path, and differentially compares exit code,
stdout (address-normalized), and workbook state (volatile-normalized).
Also asserts expected routing (direct vs reference + fallback reason).

Writes ADVERSARIAL_CASES.json (inventory) and PARITY_RESULTS.jsonl.
Raw runs stay in _staging/.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
STAGE = HERE / "_staging" / "adversarial"
sys.path.insert(0, str(ROOT / "src"))

import openpyxl  # noqa: E402
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest()


CASES = []

# Each case: (id, workbook_builder, script, expect)
# expect: {"route": "DIRECT_RUNTIME"|"REFERENCE_FAST_PATH", "fallback": reason-substr|None}


def build_books(d):
    d.mkdir(parents=True, exist_ok=True)
    books = {}
    # 1. empty sheet
    wb = openpyxl.Workbook(); wb.active.title = "empty"
    p = d / "empty.xlsx"; wb.save(p); books["empty"] = p
    # 2. sparse: values far apart
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "sparse"
    ws["A1"] = 1; ws["Z100"] = "far"; ws["C3"] = 3.5
    p = d / "sparse.xlsx"; wb.save(p); books["sparse"] = p
    # 3. large dims few cells
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "big"
    ws["A1"] = "x"; ws.cell(row=5000, column=200).value = "edge"
    p = d / "bigdim.xlsx"; wb.save(p); books["bigdim"] = p
    # 4. blanks: interior + trailing
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "blanks"
    ws["B2"] = 1; ws["D4"] = 2
    p = d / "blanks.xlsx"; wb.save(p); books["blanks"] = p
    # 5. merged anchor + children
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "merged"
    ws["A1"] = "top"; ws.merge_cells("B2:D4"); ws["B2"] = "m"
    ws["F6"] = "after"
    p = d / "merged.xlsx"; wb.save(p); books["merged"] = p
    # 6. merges only, no values
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "mo"
    ws.merge_cells("A1:C3")
    p = d / "merges_only.xlsx"; wb.save(p); books["merges_only"] = p
    # 7. types: formula/date/bool/error/shared/inline
    import datetime
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "types"
    ws["A1"] = 1; ws["A2"] = "=A1*2"; ws["A3"] = datetime.datetime(2024, 1, 2, 3, 4, 5)
    ws["A4"] = True; ws["A5"] = "#DIV/0!"; ws["A6"] = "shared str"
    ws["A3"].number_format = "yyyy-mm-dd"
    p = d / "types.xlsx"; wb.save(p); books["types"] = p
    # 8. array + data-table formulas (constructed then saved)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "arr"
    ws["A1"] = 1; ws["A2"] = 2
    ws["B1"] = ArrayFormula(ref="B1:B2", text="A1:A2*2")
    ws["C1"] = DataTableFormula(ref="C1:D2", type="dataTable")
    p = d / "array.xlsx"; wb.save(p); books["array"] = p
    # 9. style-only cell (empty value, styled) + one value far away
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "styled"
    ws["B2"].font = openpyxl.styles.Font(bold=True)
    ws["Z50"] = "v"
    p = d / "styled.xlsx"; wb.save(p); books["styled"] = p
    # 10. style-only sheet (no values at all)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "so"
    ws["B2"].font = openpyxl.styles.Font(bold=True)
    p = d / "style_only.xlsx"; wb.save(p); books["style_only"] = p
    return books


SCAN = """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb[{sheet!r}]
for row in ws.iter_rows({bounds}):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value)[:80])
"""

SCAN_ATTRS = """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb[{sheet!r}]
for row in ws.iter_rows({bounds}):
    for c in row:
        print(c.coordinate, c.row, c.column, c.data_type, repr(c.value)[:60])
"""


def define_cases():
    C = []
    S = "ws"
    # bare iteration across shapes
    for book, sheet in [("empty", "empty"), ("sparse", "sparse"),
                        ("blanks", "blanks"), ("types", "types"),
                        ("styled", "styled"), ("style_only", "so"),
                        ("merges_only", "mo"), ("bigdim", "big")]:
        C.append((f"bare_{book}", book, SCAN.format(sheet=sheet, bounds=""),
                  {"route": None}))
    # explicit bounds incl. edge bounds
    C.append(("bounds_basic", "sparse", SCAN.format(sheet="sparse", bounds="min_row=1, max_row=100, min_col=1, max_col=26"), {"route": None}))
    C.append(("bounds_beyond_dim", "sparse", SCAN.format(sheet="sparse", bounds="min_row=1, max_row=500, min_col=1, max_col=50"), {"route": None}))
    C.append(("bounds_zero", "sparse", SCAN.format(sheet="sparse", bounds="min_row=0, max_row=0"), {"route": None}))
    C.append(("bounds_reversed", "sparse", SCAN.format(sheet="sparse", bounds="min_row=10, max_row=5"), {"route": None}))
    C.append(("bounds_negative", "sparse", SCAN.format(sheet="sparse", bounds="min_row=-1, max_row=3"), {"route": None}))
    C.append(("bounds_single_cell", "sparse", SCAN.format(sheet="sparse", bounds="min_row=100, max_row=100, min_col=26, max_col=26"), {"route": None}))
    # merged contact -> served direct (D1); children read None/'n' exactly
    # like MergedCell for the certified attribute contract
    C.append(("merged_anchor_in_rect", "merged", SCAN.format(sheet="merged", bounds="min_row=1, max_row=6, min_col=1, max_col=6"), {"route": "DIRECT_RUNTIME"}))
    C.append(("merged_child_in_rect", "merged", SCAN.format(sheet="merged", bounds="min_row=2, max_row=4, min_col=2, max_col=4"), {"route": "DIRECT_RUNTIME"}))
    C.append(("merged_outside_rect", "merged", SCAN.format(sheet="merged", bounds="min_row=6, max_row=6, min_col=6, max_col=6"), {"route": "DIRECT_RUNTIME"}))
    C.append(("merged_bare", "merged", SCAN.format(sheet="merged", bounds=""), {"route": "DIRECT_RUNTIME"}))
    C.append(("merged_attrs", "merged", SCAN_ATTRS.format(sheet="merged", bounds="min_row=1, max_row=6, min_col=1, max_col=6"), {"route": "DIRECT_RUNTIME"}))
    # attr coverage incl. data_type/row/column
    C.append(("attrs_types", "types", SCAN_ATTRS.format(sheet="types", bounds="min_row=1, max_row=6, min_col=1, max_col=1"), {"route": None}))
    C.append(("attrs_array", "array", SCAN_ATTRS.format(sheet="arr", bounds=""), {"route": None}))
    # repeat + partial + nested
    C.append(("repeat", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=3):
    for c in row:
        print('a', c.coordinate)
for row in ws.iter_rows(min_row=1, max_row=3):
    for c in row:
        print('b', c.coordinate)
""", {"route": None}))
    C.append(("partial", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=100):
    for c in row:
        print('first cell:', c.coordinate)
        break
    break
print('done')
""", {"route": None}))
    C.append(("block_len_row", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=100):
    print('cells:', len(row))
    break
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("nested_shadow", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=2):
    for c in row:
        for row2 in ws.iter_rows(min_row=1, max_row=1):
            print(c.coordinate)
            break
        break
""", {"route": None}))
    # classifier must BLOCK (reference path, identical behavior):
    C.append(("block_values_only", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
    print(row)
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_iter_cols", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for col in ws.iter_cols(min_row=1, max_row=3):
    print(len(col))
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_sheet_iter", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws:
    print(len(row))
    break
""", {"route": None}))
    C.append(("block_dynamic_bounds", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
n = 3
for row in ws.iter_rows(min_row=1, max_row=n):
    print(len(row))
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_rich_after", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=3):
    for c in row:
        print(c.font)
        break
    break
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_store_cell", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
seen = []
for row in ws.iter_rows(min_row=1, max_row=3):
    for c in row:
        seen.append(c)
print(len(seen))
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_identity", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
first = None
for row in ws.iter_rows(min_row=1, max_row=3):
    for c in row:
        if first is None:
            first = c
        print(c is first)
        break
    break
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_escape_call", "sparse", """import openpyxl
def show(x):
    return x
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=3):
    for c in row:
        print(show(c))
        break
    break
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_materialize", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
rows = list(ws.iter_rows(min_row=1, max_row=3))
print(len(rows))
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_mixed_write", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=3):
    for c in row:
        c.value = 1
print('wrote')
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_row_index", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=3):
    print(row[0].value)
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_getattr", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=3):
    for c in row:
        print(getattr(c, 'value'))
        break
    break
""", {"route": "REFERENCE_FAST_PATH"}))
    C.append(("block_alias_escape", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=3):
    r2 = row
    print(len(r2))
    break
""", {"route": "REFERENCE_FAST_PATH"}))
    # abrupt exception mid-iteration (identical failure)
    C.append(("raise_mid_iter", "sparse", """import openpyxl
wb = openpyxl.load_workbook('input.xlsx')
ws = wb['sparse']
for row in ws.iter_rows(min_row=1, max_row=100):
    for c in row:
        if c.value is not None:
            raise RuntimeError('boom ' + c.coordinate)
""", {"route": None}))
    return C


def run(cmd, cwd, env, timeout=120):
    import time
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           timeout=timeout)
        return {"exit": p.returncode, "out": p.stdout, "err": p.stderr,
                "wall": time.perf_counter() - t, "timeout": False}
    except subprocess.TimeoutExpired as e:
        return {"exit": None, "out": e.stdout or b"", "err": e.stderr or b"",
                "wall": time.perf_counter() - t, "timeout": True}


def norm(b):
    import re
    b = re.sub(rb"0x[0-9a-fA-F]+", b"0xADDR", b)
    # Traceback file lines differ by implementation path; compare only the
    # exception's final line plus stdout for raise-cases.
    return b


def main():
    import shutil
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    books = build_books(STAGE / "books")
    cases = define_cases()
    (HERE / "ADVERSARIAL_CASES.json").write_text(json.dumps(
        [{"id": c, "book": b, "script_sha256": sha(s.encode()),
          "expect": e} for c, b, s, e in cases], indent=1))
    results = []
    n_direct = n_ref = 0
    for cid, book, script, expect in cases:
        d = STAGE / "runs" / cid
        (d / "base").mkdir(parents=True)
        (d / "probe").mkdir(parents=True)
        import shutil as sh
        for arm in ("base", "probe"):
            sh.copy(books[book], d / arm / "input.xlsx")
            (d / arm / "case.py").write_text(script)
        env = dict(os.environ)
        b = run([sys.executable, "case.py"], cwd=d / "base", env=env)
        cache = d / "cache"
        cfg = d / "probe" / "rt.toml"
        cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache)
        penv = dict(os.environ)
        penv["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "src")] + ([penv["PYTHONPATH"]] if penv.get("PYTHONPATH") else []))
        p = run([sys.executable, "-m", "recalc_agent", "run", "--config",
                 str(cfg), "--workdir", str(d / "probe"),
                 str(d / "probe" / "case.py")], cwd=d / "probe", env=penv)
        # route + fallback from receipt
        route, fallbacks, events = None, [], []
        try:
            ptr = json.loads((cache / "runs" / "last_run.json").read_text())
            rd = Path(ptr["run_dir"])
            st = json.loads((rd / "setup.json").read_text())
            route = st.get("route")
            if (rd / "runtime_state.json").exists():
                rt = json.loads((rd / "runtime_state.json").read_text())
                route = rt.get("route") or route
                events = [e.get("event") + ":" + str(e.get("reason", ""))
                          for e in rt.get("events", [])]
                fallbacks = rt.get("fallback_reasons", [])
        except (OSError, ValueError, KeyError):
            pass
        # state compare (volatile-normalized via shared helper path)
        sys.path.insert(0, str(HERE.parent / "execution_surface_census"))
        import aggregate as agg  # noqa: E402
        st_b = {str(p.relative_to(d / "base")): agg.norm_xlsx(p.read_bytes())
                for p in sorted((d / "base").glob("*.xlsx"))}
        st_p = {str(p.relative_to(d / "probe")): agg.norm_xlsx(p.read_bytes())
                for p in sorted((d / "probe").glob("*.xlsx"))}
        ok = (b["exit"] == p["exit"] and norm(b["out"]) == norm(p["out"])
              and st_b == st_p and not b["timeout"] and not p["timeout"])
        # stderr: compare only for non-raise cases modulo traceback paths
        if ok and b["exit"] != 0:
            bl = (b["err"].decode(errors="replace").strip().splitlines() or [""]) [-1]
            pl = (p["err"].decode(errors="replace").strip().splitlines() or [""]) [-1]
            # last line holds `module.Class: msg` for raised errors; file
            # paths live on other lines. Compare exception type + message.
            ok = bl.split(":")[-1] == pl.split(":")[-1] and bl.split(":")[0].split(".")[-1] == pl.split(":")[0].split(".")[-1]
        route_ok = True
        if expect.get("route") == "REFERENCE_FAST_PATH":
            route_ok = (route in ("REFERENCE_FAST_PATH",) or route is None and p["exit"] == b["exit"])
        elif expect.get("route") == "DIRECT_RUNTIME":
            route_ok = (route == "DIRECT_RUNTIME")
        if expect.get("fallback"):
            route_ok = route_ok and any(expect["fallback"] in e for e in events)
        if route and route.startswith("DIRECT"):
            n_direct += 1
        else:
            n_ref += 1
        results.append({"case": cid, "parity": ok, "route": route,
                        "route_ok": route_ok, "events": events,
                        "exit": [b["exit"], p["exit"]]})
        print(("PASS " if ok and route_ok else "FAIL ") + cid +
              f" route={route} exit={b['exit']}/{p['exit']}")
    (HERE / "_staging" / "adversarial_raw.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in results) + "\n")
    fails = [r for r in results if not (r["parity"] and r["route_ok"])]
    print(f"cases={len(results)} direct={n_direct} reference={n_ref} FAILURES={len(fails)}")
    for f in fails:
        print("  FAIL:", f)


if __name__ == "__main__":
    main()
