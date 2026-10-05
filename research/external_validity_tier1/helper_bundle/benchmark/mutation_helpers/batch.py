"""Optional explicit-map batch mutation helpers (Stage: batch-write A/B).

Pure syntax compression: exact map in -> exact writes out. No inference of
targets, content, direction, or relationships. Effects are ordinary openpyxl
writes, captured by the transparent runtime exactly like hand-authored code.
Every call is logged (keys + value/formula types) for telemetry.
"""
from __future__ import annotations

import json
import os


def _log(call: dict) -> None:
    log = os.environ.get("AB_HELPER_LOG")
    if log:
        with open(log, "a") as fh:
            fh.write(json.dumps(call) + "\n")


def _parse_addr(key: str, default_sheet: str | None = None) -> tuple[str | None, str]:
    if "!" in key:
        sheet, addr = key.split("!", 1)
        return sheet, addr
    return default_sheet, key


def _apply(workbook: str | None, mapping: dict, helper: str) -> dict:
    import openpyxl
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError(f"{helper} requires a non-empty address->content mapping")
    if not workbook:
        raise ValueError(f"{helper} requires an explicit workbook path; refusing to guess a file")
    wb = openpyxl.load_workbook(workbook)
    written = []
    types = {}
    try:
        for key, content in mapping.items():
            sheet, addr = _parse_addr(str(key))
            if sheet is None:
                sheet = wb.active.title if wb.active is not None else wb.sheetnames[0]
            if sheet not in wb.sheetnames:
                raise KeyError(f"sheet not found: {sheet}")
            ws = wb[sheet]
            ws[addr] = content
            written.append(f"{sheet}!{addr}")
            types[f"{sheet}!{addr}"] = (
                "formula" if isinstance(content, str) and content.startswith("=") else "value")
        wb.save(workbook)
    finally:
        wb.close()
    _log({"helper": helper, "workbook": str(workbook).split("/")[-1],
          "n_writes": len(written), "addresses": written, "types": types})
    return {"writes": written, "types": types}


def write_cells(mapping: dict, workbook: str | None = None) -> dict:
    """Write exactly the supplied address->content map. No inference."""
    return _apply(workbook, mapping, "write_cells")


def write_formulas(mapping: dict, workbook: str | None = None) -> dict:
    """Write exactly the supplied address->formula map. No interpretation."""
    return _apply(workbook, mapping, "write_formulas")
