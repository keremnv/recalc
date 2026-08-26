"""The five Financial_Model tasks that openpyxl refuses to open at all."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from benchmark.xlsx_metadata_repair import _repair_part, repair

# The exact shape shipped in 06_01..06_05: dc: is bound locally on <dc:language>, goes out
# of scope, and is then reused by <dc:creator> where nothing binds it.
UNBOUND = (
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
    'metadata/core-properties">'
    '<dc:language xmlns:dc="http://purl.org/dc/elements/1.1/">en-US</dc:language>'
    "<dc:creator>Aptura</dc:creator></cp:coreProperties>"
)


def test_unbound_prefix_is_rejected_before_repair() -> None:
    with pytest.raises(ET.ParseError):
        ET.fromstring(UNBOUND)


def test_repair_binds_the_prefix_and_preserves_content() -> None:
    fixed = _repair_part(UNBOUND)
    assert fixed is not None
    root = ET.fromstring(fixed)
    creator = root.find("{http://purl.org/dc/elements/1.1/}creator")
    assert creator is not None and creator.text == "Aptura"


def test_wellformed_part_is_left_alone() -> None:
    assert _repair_part('<a xmlns:b="urn:x"><b:c/></a>') is None


def test_repair_rewrites_only_the_broken_part(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("docProps/core.xml", UNBOUND)
        archive.writestr("xl/worksheets/sheet1.xml", "<sheetData/>")
    target = repair(source, tmp_path / "out")
    assert target is not None
    with zipfile.ZipFile(target) as archive:
        ET.fromstring(archive.read("docProps/core.xml"))
        assert archive.read("xl/worksheets/sheet1.xml") == b"<sheetData/>"
