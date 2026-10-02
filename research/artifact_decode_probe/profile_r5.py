"""R5 decode profiler + sheet-touch census (measurement only, product untouched).

profile: build/ensure artifacts for the 7-book subset, then phase-time
  artifact.decode on real bytes (untimed reference + timed duplicate of
  _book with per-sub-phase accumulators). Writes CURRENT_DECODE_PROFILE.jsonl.
touch: in-process real-runtime driver with a MemoryBook.cell touch counter;
  execs each subset workload script against the proxy. Writes SHEET_TOUCH_CENSUS.jsonl.
canon: canonical MemoryBook state dump (shared by parity checks later).
"""
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
R1 = HERE.parent / "execution_surface_census"
CLEAN = R1 / "_staging" / "staged" / "clean"
CACHE = HERE / "_staging" / "cache"

sys.path.insert(0, str(ROOT / "src"))

SUBSET = [
    "Debugging_10_07__6dd8f6d3a4dd",
    "Debugging_10_07__e3a79d24091a",
    "Debugging_10_10__c7eca76e6646",
    "Financial_Model_08_01__2ea507d758dc",
    "Financial_Model_08_02__4ca3ae46295d",
    "Financial_Model_08_02__625ec1db4acb",
    "Financial_Model_08_03__e48ea186deeb",
]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ensure_artifact(wid):
    from recalc_agent.read_engine import artifact
    src = CLEAN / "A" / wid
    books = sorted(src.glob("*.xlsx"))
    assert len(books) == 1, (wid, books)
    digest = sha_file(books[0])
    path, status, _ = artifact.ensure(books[0], CACHE / wid, digest)
    return path, digest, books[0]


def timed_decode_stages(data, expected_source_sha):
    """Duplicate of artifact.decode with per-stage timers (product untouched)."""
    import hashlib as hl
    import json as js
    import struct
    import zlib
    from recalc_agent.read_engine import _identity as ident
    from recalc_agent.read_engine import artifact as art
    t = {}
    t0 = time.perf_counter()
    assert len(data) >= 52 and data[:8] == ident.MAGIC
    t["magic"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    assert hl.sha256(data[:-32]).digest() == data[-32:]
    t["blob_sha256"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    hlen = struct.unpack(">I", data[8:12])[0]
    header = js.loads(data[12:12 + hlen])
    assert set(header) == set(ident.identity(expected_source_sha)) | {"sheet_count", "payload_sha256"}
    assert all(header[k] == v for k, v in ident.identity(expected_source_sha).items())
    t["header_parse_validate"] = time.perf_counter() - t0
    offset = 12 + hlen
    clen = struct.unpack(">Q", data[offset:offset + 8])[0]
    t0 = time.perf_counter()
    dec = zlib.decompressobj()
    raw = dec.decompress(data[offset + 8:offset + 8 + clen], art.MAX_UNCOMPRESSED + 1)
    t["zlib_decompress"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    assert dec.eof and not dec.unused_data and not dec.unconsumed_tail
    assert ident.sha_bytes(raw) == header["payload_sha256"]
    t["payload_sha256"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    obj = js.loads(raw)
    t["json_loads"] = time.perf_counter() - t0
    return raw, obj, header, t


def timed_book(obj):
    """Duplicate of artifact._book with per-sub-phase accumulators."""
    import time as tm
    from recalc_agent.read_engine import artifact as art
    from recalc_agent.read_engine.direct import MemoryBook, SheetInfo, _value_from_json
    from recalc_agent.read_engine.artifact import _check_typed, canonical, COORD, MAX_CELLS, MAX_SHEETS
    acc = {"sheet_validate": 0.0, "cell_validate": 0.0, "typed_reencode": 0.0,
           "typed_reparse": 0.0, "dict_alloc": 0.0}
    sheets, seen, count = [], set(), 0
    for entry in obj["sheets"]:
        t0 = tm.perf_counter()
        name, bounds, merged, cells = entry["name"], entry["bounds"], entry["merged"], entry["cells"]
        seen.add(name)
        ranges = [tuple(item) for item in merged]
        acc["sheet_validate"] += tm.perf_counter() - t0
        store = {}
        for item in cells:
            coord, dtype, typed = item
            t0 = tm.perf_counter()
            assert COORD.fullmatch(coord) and coord not in store
            _check_typed(typed)
            acc["cell_validate"] += tm.perf_counter() - t0
            t0 = tm.perf_counter()
            s = canonical(typed).decode()
            acc["typed_reencode"] += tm.perf_counter() - t0
            t0 = tm.perf_counter()
            value = _value_from_json(s)
            acc["typed_reparse"] += tm.perf_counter() - t0
            t0 = tm.perf_counter()
            store[coord] = (value, dtype)
            acc["dict_alloc"] += tm.perf_counter() - t0
            count += 1
        sheets.append(SheetInfo(name, *bounds, ranges, store))
    return MemoryBook(sheets), acc, count


def canon_book(book):
    sheets = []
    for name in book.sheetnames:
        info = book._sheets[name]
        cells = sorted((c, repr(v), d) for c, (v, d) in info.cells.items())
        sheets.append({"name": name,
                       "bounds": [info.min_row, info.min_col, info.max_row, info.max_col],
                       "merged": sorted(info.merged),
                       "cells": cells})
    return {"sheets": sheets}


def cmd_profile():
    from recalc_agent.read_engine import artifact
    rows = []
    for wid in SUBSET:
        apath, digest, src = ensure_artifact(wid)
        data = apath.read_bytes()
        # Untimed reference decodes (product code).
        ref = []
        for _ in range(5):
            t0 = time.perf_counter()
            book0 = artifact.decode(data, digest)
            ref.append(time.perf_counter() - t0)
        # Timed duplicate.
        stages_all, acc_all = [], []
        for _ in range(5):
            raw, obj, header, st = timed_decode_stages(data, digest)
            book1, acc, count = timed_book(obj)
            stages_all.append(st)
            acc_all.append(acc)
        assert canon_book(book0) == canon_book(book1), wid
        ncells = sum(len(book0._sheets[n].cells) for n in book0.sheetnames)
        stages = {k: statistics.median(s[k] for s in stages_all) for k in stages_all[0]}
        accm = {k: statistics.median(a[k] for a in acc_all) for k in acc_all[0]}
        stages["timed_book_subtotal"] = sum(accm.values())
        timed_total = sum(stages_all[0][k] for k in ("magic", "blob_sha256", "header_parse_validate",
                                                     "zlib_decompress", "payload_sha256", "json_loads"))
        rows.append({
            "workload": wid,
            "script_sha256": sha_file(CLEAN / "A" / wid / "workload.py"),
            "workbook_sha256": digest,
            "artifact_sha256": sha_file(apath),
            "artifact_bytes": len(data),
            "payload_bytes": len(raw),
            "n_sheets": len(book0.sheetnames),
            "n_cells": ncells,
            "ref_decode_s_median": statistics.median(ref),
            "stages_s_median": {k: round(v, 6) for k, v in stages.items()},
            "book_subphases_s_median": {k: round(v, 6) for k, v in accm.items()},
            "instrumented_total_s_median": round(timed_total + sum(accm.values()), 6),
        })
        print("%s: ref=%.4f json=%.4f reenc=%.4f reparse=%.4f valid=%.4f n=%d" % (
            wid, statistics.median(ref), stages["json_loads"],
            accm["typed_reencode"], accm["typed_reparse"],
            accm["cell_validate"], ncells), flush=True)
    with open(HERE / "CURRENT_DECODE_PROFILE.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def cmd_touch():
    import os
    from recalc_agent.read_engine import artifact
    from recalc_agent.read_engine import direct as D
    from recalc_agent.read_engine import runtime as R
    rows = []
    for wid in SUBSET:
        apath, digest, _ = ensure_artifact(wid)
        run = HERE / "_staging" / "touchruns" / wid
        if run.exists():
            import shutil
            shutil.rmtree(run)
        import shutil
        shutil.copytree(CLEAN / "A" / wid, run)
        book_path = str((run / sorted(p.name for p in run.glob("*.xlsx"))[0]).resolve())
        touches = {}
        orig_cell = D.MemoryBook.cell
        def counting_cell(self, sheet, coord, _o=orig_cell, _t=touches):
            _t.setdefault(sheet.name, {}).setdefault(coord, 0)
            _t[sheet.name][coord] += 1
            return _o(self, sheet, coord)
        D.MemoryBook.cell = counting_cell
        ctx = {"admitted": True,
               "workbooks": {book_path: {"status": "REUSED", "source_sha256": digest,
                                         "artifact_path": str(apath)}},
               "runtime_state": str(run / "runtime_state.json")}
        rt = R.Runtime(ctx, time.perf_counter_ns())
        rt.install()
        try:
            src = (run / "workload.py").read_text()
            old = os.getcwd()
            os.chdir(run)
            try:
                exec(compile(src, "workload.py", "exec"), {"__name__": "__main__"})
            finally:
                os.chdir(old)
        finally:
            D.MemoryBook.cell = orig_cell
            import openpyxl
            openpyxl.load_workbook = rt.original
        rt.finish()
        for p in list(rt.proxies):
            try:
                p.close()
            except Exception:
                pass
        book = artifact.decode(apath.read_bytes(), digest)
        total_cells = sum(len(book._sheets[n].cells) for n in book.sheetnames)
        per_sheet = {}
        touched_mass = 0
        for name in book.sheetnames:
            n = len(book._sheets[name].cells)
            t = touches.get(name, {})
            per_sheet[name] = {"cells_in_artifact": n,
                               "distinct_coords_read": len(t),
                               "read_events": sum(t.values())}
            if t:
                touched_mass += n
        order = [n for n in book.sheetnames if n in touches]
        rows.append({
            "workload": wid,
            "n_sheets": len(book.sheetnames),
            "sheets_touched": sorted(touches),
            "first_access_order": order,
            "total_artifact_cells": total_cells,
            "touched_sheet_cell_mass": touched_mass,
            "touched_mass_fraction": (touched_mass / total_cells) if total_cells else 0,
            "per_sheet": per_sheet,
            "route": json.loads((run / "runtime_state.json").read_text())["route"],
        })
        print("%s: touched %d/%d sheets mass_frac=%.3f" % (
            wid, len(touches), len(book.sheetnames),
            rows[-1]["touched_mass_fraction"]), flush=True)
    with open(HERE / "SHEET_TOUCH_CENSUS.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=["profile", "touch"], required=True)
    args = ap.parse_args()
    if args.step == "profile":
        cmd_profile()
    else:
        cmd_touch()
