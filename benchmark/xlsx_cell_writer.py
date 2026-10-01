#!/usr/bin/env python3
"""Structure-preserving xlsx cell writer.

An openpyxl load/save round trip rewrites every part of the workbook and drops
others (calcChain, sharedStrings, worksheet rels, chart styling). On the
Financial_Model suite that changes recalculated values even when no cell is
edited, so benchmark deltas measured through it are not trustworthy.

This writer copies the source archive entry by entry and rewrites only the sheet
parts that actually receive an edit. With no edits the output is byte-identical
to the input, which is the neutrality property the harness gate checks.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

CELL_RE_TEMPLATE = r'<c r="{addr}"(?P<attrs>[^>]*?)(?:/>|>(?P<body>.*?)</c>)'
ROW_RE_TEMPLATE = r'<row[^>]*\sr="{row}"(?:\s[^>]*)?(?:/>|>.*?</row>)'


def column_index(address: str) -> int:
    letters = re.match(r"([A-Z]+)", address).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def row_index(address: str) -> int:
    return int(re.search(r"(\d+)$", address).group(1))


def sheet_parts(archive: zipfile.ZipFile) -> dict[str, str]:
    """Map sheet title to its archive path, via workbook.xml and its rels."""
    workbook = archive.read("xl/workbook.xml").decode("utf-8")
    rels = archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    target = {m.group(1): m.group(2) for m in re.finditer(r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', rels)}
    target.update({m.group(2): m.group(1) for m in re.finditer(r'<Relationship[^>]*Target="([^"]+)"[^>]*Id="([^"]+)"', rels)})
    out = {}
    for m in re.finditer(r"<sheet\b[^>]*/>", workbook):
        tag = m.group(0)
        name = re.search(r'name="([^"]*)"', tag)
        rid = re.search(r'r:id="([^"]+)"', tag)
        if not (name and rid) or rid.group(1) not in target:
            continue
        path = target[rid.group(1)]
        out[_unescape(name.group(1))] = "xl/" + path.lstrip("/").removeprefix("xl/")
    return out


def _unescape(text: str) -> str:
    for a, b in (("&quot;", '"'), ("&apos;", "'"), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")):
        text = text.replace(a, b)
    return text


class SharedMasterError(RuntimeError):
    """Overwriting the master of a live shared-formula group would orphan members."""


def _cell_xml(address: str, attrs: str, formula: str) -> str:
    # A formula cell carries no value type; drop t= and any cached value.
    attrs = re.sub(r'\st="[^"]*"', "", attrs).rstrip("/").rstrip()
    return f'<c r="{address}"{attrs}><f>{escape(formula.lstrip("="))}</f></c>'


def patch_sheet(xml: str, edits: dict[str, str]) -> str:
    for address in sorted(edits, key=lambda a: (row_index(a), column_index(a))):
        xml = _patch_cell(xml, address, edits[address])
    return xml


def _patch_cell(xml: str, address: str, formula: str) -> str:
    match = re.search(CELL_RE_TEMPLATE.format(addr=re.escape(address)), xml, re.DOTALL)
    if match:
        body = match.group("body") or ""
        shared = re.search(r'<f[^>]*t="shared"[^>]*\bref="([^"]+)"', body)
        if shared and shared.group(1) != f"{address}:{address}":
            raise SharedMasterError(f"{address} is the master of shared range {shared.group(1)}")
        return xml[:match.start()] + _cell_xml(address, match.group("attrs"), formula) + xml[match.end():]

    cell = _cell_xml(address, "", formula)
    row = row_index(address)
    row_match = re.search(ROW_RE_TEMPLATE.format(row=row), xml, re.DOTALL)
    if row_match:
        chunk = row_match.group(0)
        if chunk.endswith("/>"):
            patched = chunk[:-2].rstrip() + ">" + cell + "</row>"
        else:
            col = column_index(address)
            positions = [(column_index(m.group(1)), m.start()) for m in re.finditer(r'<c r="([A-Z]+\d+)"', chunk)]
            after = next((pos for c, pos in positions if c > col), None)
            patched = chunk[:after] + cell + chunk[after:] if after is not None else chunk[:chunk.rindex("</row>")] + cell + "</row>"
        return xml[:row_match.start()] + patched + xml[row_match.end():]

    new_row = f'<row r="{row}">{cell}</row>'
    rows = [(int(m.group(1)), m.start()) for m in re.finditer(r'<row[^>]*\sr="(\d+)"', xml)]
    after = next((pos for r, pos in rows if r > row), None)
    if after is not None:
        return xml[:after] + new_row + xml[after:]
    if "<sheetData/>" in xml:
        return xml.replace("<sheetData/>", f"<sheetData>{new_row}</sheetData>", 1)
    close = xml.index("</sheetData>")
    return xml[:close] + new_row + xml[close:]


def write_cells(source: Path, dest: Path, edits: list[dict]) -> dict:
    """Apply formula edits. edits: [{sheet, address, formula}]. Returns an audit."""
    source, dest = Path(source), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not edits:
        # Neutrality: writing nothing must change nothing, byte for byte.
        shutil.copyfile(source, dest)
        return {"applied": [], "rejected": [], "byte_identical_to_source": True, "rewritten_parts": []}

    with zipfile.ZipFile(source) as archive:
        parts = sheet_parts(archive)
        by_part: dict[str, dict[str, str]] = {}
        applied, rejected = [], []
        for edit in edits:
            part = parts.get(edit["sheet"])
            if part is None:
                rejected.append({**edit, "reason": "UNKNOWN_SHEET"})
                continue
            by_part.setdefault(part, {})[edit["address"]] = edit["formula"]
        patched: dict[str, bytes] = {}
        applied_parts: set[str] = set()
        for part, cells in by_part.items():
            xml = archive.read(part).decode("utf-8")
            for address, formula in sorted(cells.items(), key=lambda kv: (row_index(kv[0]), column_index(kv[0]))):
                try:
                    xml = _patch_cell(xml, address, formula)
                    applied.append({"sheet": next(k for k, v in parts.items() if v == part), "address": address, "formula": formula})
                    applied_parts.add(part)
                except SharedMasterError as exc:
                    rejected.append({"sheet": next(k for k, v in parts.items() if v == part), "address": address, "formula": formula, "reason": f"SHARED_FORMULA_MASTER: {exc}"})
            if part in applied_parts:
                patched[part] = xml.encode("utf-8")
        if not applied:
            # Every edit was refused; neutrality still applies, so copy rather
            # than re-zip a sheet whose bytes we did not actually change.
            shutil.copyfile(source, dest)
            return {"applied": [], "rejected": rejected, "byte_identical_to_source": True, "rewritten_parts": []}
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
            for item in archive.infolist():
                data = patched.get(item.filename)
                if data is None:
                    out.writestr(item, archive.read(item.filename))
                else:
                    out.writestr(item, data)
    return {"applied": applied, "rejected": rejected, "byte_identical_to_source": False, "rewritten_parts": sorted(patched)}
