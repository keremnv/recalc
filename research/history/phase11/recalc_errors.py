#!/usr/bin/env python3
"""Phase-11 recalc substudy: true formula-error delta via LibreOffice.

For each (input, output) workbook pair in the reachability matrix: patch
fullCalcOnLoad into a scratch copy, recalc with headless soffice, read back
error-valued cells with openpyxl data_only. Emits RECALC_ERROR_DELTA.jsonl.

Deterministic replay of stored artifacts; no product code touched.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ERRORS = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!",
          "#VALUE!", "#GETTING_DATA", "#SPILL!", "#CALC!", "#FIELD!"}


def patch_full_calc(src: Path, dst: Path) -> bool:
    try:
        zin = zipfile.ZipFile(src, "r")
        xml = zin.read("xl/workbook.xml").decode()
    except Exception:
        return False
    if "fullCalcOnLoad" not in xml:
        # Prefer patching an existing calcPr element (duplicates are invalid).
        xml2, n = re.subn(r"<calcPr\b", '<calcPr fullCalcOnLoad="1"',
                          xml, count=1)
        if not n:
            xml2, n = re.subn(r"<workbookPr([^/]*)/>",
                              r'<workbookPr\1/><calcPr fullCalcOnLoad="1"/>',
                              xml, count=1)
        if not n:
            # No workbookPr element: append calcPr before the closing tag
            # (valid position: calcPr follows sheets in the schema).
            if "</workbook>" not in xml:
                return False
            xml2 = xml.replace("</workbook>",
                               '<calcPr fullCalcOnLoad="1"/></workbook>')
        xml = xml2
    try:
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = xml.encode() if item.filename == "xl/workbook.xml" else zin.read(item.filename)
                zout.writestr(item, data)
    except Exception:
        return False
    finally:
        zin.close()
    return True


def recalc(src: Path, outdir: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["soffice", "--headless", "--convert-to", "xlsx:Calc MS Excel 2007 XML",
             str(src), "--outdir", str(outdir)],
            capture_output=True, timeout=180)
    except Exception:
        return None
    cand = outdir / (src.stem + ".xlsx")
    return cand if cand.is_file() else None


def error_cells(path: Path) -> dict:
    import openpyxl
    out = {}
    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception:
        return out
    try:
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    v = cell.value
                    if isinstance(v, str) and v in ERRORS:
                        r = getattr(cell, "row", None)
                        c = getattr(cell, "column", None)
                        if r is None:
                            continue
                        from openpyxl.utils import get_column_letter
                        try:
                            coord = f"{ws.title}!{get_column_letter(c)}{r}"
                        except Exception:
                            continue
                        out[coord] = v
    finally:
        wb.close()
    return out


def main() -> None:
    rows = [json.loads(l) for l in open(ROOT / "research/history/phase11" / "DERIVATION_REACHABILITY_MATRIX.jsonl")]
    pairs = {}
    for r in rows:
        if r["candidate"] != "ERR-NEW-ERROR-DELTA" or not r["has_output"] or not r["has_input"]:
            continue
        pairs[r["rep"]] = r
    print(f"pairs: {len(pairs)}", file=sys.stderr)
    # recover paths from mine index
    sys.path.insert(0, str(ROOT / "research/history/phase11"))
    from mine import index_reps
    by_rep = {r["rep"]: r for r in index_reps()}
    out_rows = []
    with tempfile.TemporaryDirectory(prefix="p11-recalc-") as tmp:
        tmp = Path(tmp)
        for i, (rep, mrow) in enumerate(sorted(pairs.items())):
            idx = by_rep.get(rep, {})
            if not idx.get("input") or not idx.get("output"):
                continue
            res: dict = {"rep": rep, "task": mrow["task"], "family": mrow.get("family"),
                         "input_errors": {}, "output_errors": {}, "new": [], "gone": [],
                         "ok": False}
            try:
                wdir = tmp / f"p{i}"
                wdir.mkdir()
                pi = wdir / "in.xlsx"
                po = wdir / "out.xlsx"
                if not patch_full_calc(Path(idx["input"]), pi):
                    out_rows.append(res)
                    continue
                if not patch_full_calc(Path(idx["output"]), po):
                    out_rows.append(res)
                    continue
                (wdir / "ri").mkdir(exist_ok=True)
                ri = recalc(pi, wdir / "ri")
                (wdir / "ro").mkdir(exist_ok=True)
                ro = recalc(po, wdir / "ro")
                if ri is None or ro is None:
                    out_rows.append(res)
                    continue
                ie = error_cells(ri)
                oe = error_cells(ro)
                res.update({"input_errors": ie, "output_errors": oe,
                            "new": sorted(set(oe) - set(ie)),
                            "gone": sorted(set(ie) - set(oe)), "ok": True})
            except Exception as exc:
                res["error"] = f"{type(exc).__name__}: {exc}"
            out_rows.append(res)
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{len(pairs)}", file=sys.stderr)
    with open(ROOT / "research/history/phase11" / "RECALC_ERROR_DELTA.jsonl", "w") as f:
        for r in out_rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    ok = sum(1 for r in out_rows if r["ok"])
    new = sum(len(r["new"]) for r in out_rows)
    print(f"recalced ok: {ok}/{len(out_rows)}, runs with new errors: "
          f"{sum(1 for r in out_rows if r['new'])}, total new error cells: {new}")


if __name__ == "__main__":
    main()
