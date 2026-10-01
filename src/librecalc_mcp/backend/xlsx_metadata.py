"""Metadata-only tolerance for malformed OOXML package properties.

Some valid spreadsheet grids ship with an unbound XML prefix in ``docProps/core.xml``.
LibreOffice opens them, but openpyxl rejects the package before reading any cells. This module
repairs only malformed metadata parts in a temporary copy; workbook content is never rewritten.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NAMESPACES = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcmitype": "http://purl.org/dc/dcmitype/",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "vt": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
}

_PREFIX = re.compile(r"<\s*/?\s*([A-Za-z_][\w.-]*):|\s([A-Za-z_][\w.-]*):[\w.-]+\s*=")
_ROOT = re.compile(r"<\s*([A-Za-z_][\w.:-]*)((?:\s[^<>]*?)?)(/?)>", re.DOTALL)


def repair_part(xml: str) -> str | None:
    """Bind known prefixes used outside their declaration scope."""

    used = {match.group(1) or match.group(2) for match in _PREFIX.finditer(xml)} - {
        None,
        "xmlns",
        "xml",
    }
    root = _ROOT.search(xml)
    if root is None:
        return None
    declared = set(re.findall(r"xmlns:([\w.-]+)\s*=", root.group(0)))
    missing = sorted(prefix for prefix in used if prefix not in declared and prefix in NAMESPACES)
    if not missing:
        return None
    additions = "".join(f' xmlns:{prefix}="{NAMESPACES[prefix]}"' for prefix in missing)
    start, end = root.span()
    repaired_root = f"<{root.group(1)}{root.group(2)}{additions}{root.group(3)}>"
    return xml[:start] + repaired_root + xml[end:]


def repair_docprops(path: Path, out_dir: Path) -> Path | None:
    """Return a repaired package copy, or ``None`` when metadata-only repair is impossible."""

    repairs: dict[str, str] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.startswith("docProps/") or not name.endswith(".xml"):
                continue
            raw = archive.read(name)
            try:
                ET.fromstring(raw)
                continue
            except ET.ParseError:
                pass
            fixed = repair_part(raw.decode("utf-8", "replace"))
            if fixed is None:
                return None
            try:
                ET.fromstring(fixed)
            except ET.ParseError:
                return None
            repairs[name] = fixed
        if not repairs:
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / path.name
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
            for item in archive.infolist():
                data = archive.read(item.filename)
                if item.filename in repairs:
                    data = repairs[item.filename].encode("utf-8")
                output.writestr(item, data)
    return target


__all__ = ["repair_docprops", "repair_part"]
