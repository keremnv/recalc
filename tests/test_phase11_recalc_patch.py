"""Unit tests for phase11 recalc patch helper (no LibreOffice needed)."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase11"))

from recalc_errors import patch_full_calc


def _wb(tmp_path, body):
    p = tmp_path / "in.xlsx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("xl/workbook.xml", body)
    return p


def test_patches_existing_calcpr(tmp_path):
    src = _wb(tmp_path, '<workbook><sheets/><calcPr calcId="1"/></workbook>')
    dst = tmp_path / "out.xlsx"
    assert patch_full_calc(src, dst)
    xml = zipfile.ZipFile(dst).read("xl/workbook.xml").decode()
    assert xml.count("<calcPr") == 1
    assert 'fullCalcOnLoad="1"' in xml
    assert "\\" not in xml


def test_inserts_after_workbookpr(tmp_path):
    src = _wb(tmp_path, '<workbook><workbookPr/><sheets/></workbook>')
    dst = tmp_path / "out.xlsx"
    assert patch_full_calc(src, dst)
    xml = zipfile.ZipFile(dst).read("xl/workbook.xml").decode()
    assert '<calcPr fullCalcOnLoad="1"/>' in xml


def test_appends_without_workbookpr(tmp_path):
    src = _wb(tmp_path, '<workbook><sheets/></workbook>')
    dst = tmp_path / "out.xlsx"
    assert patch_full_calc(src, dst)
    xml = zipfile.ZipFile(dst).read("xl/workbook.xml").decode()
    assert xml.count("<calcPr") == 1
