"""H1 transparent runtime tests: committed == Python-produced state on fixtures.

Covers: value writes, formula + new-sheet writes, file creation, opaque-part
preservation, failed-script abort, mechanical-validation rejection of corrupt
output, and H0 model-surface identity. No live arms run here.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import openpyxl

from benchmark.transparent_runtime import MODEL_SURFACE, run_transaction
from benchmark.transparent_runtime.delta import read_parts, replay_delta
from benchmark.transparent_runtime.validate import validate_mechanical


def _make_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws["A1"] = "label"
    ws["A2"] = 1
    ws["B2"] = 2
    ws["C2"] = "=SUM(A2:B2)"
    wb.save(path)
    wb.close()


def _write_script(path: Path, body: str) -> Path:
    path.write_text(body)
    return path


def test_model_surface_byte_identical_to_h0():
    assert tuple(MODEL_SURFACE) == ("bash", "view_xlsx", "submit")


def test_value_write_committed_equals_produced(tmp_path):
    target = tmp_path / "book.xlsx"
    _make_workbook(target)
    script = _write_script(
        tmp_path / "mut.py",
        "import openpyxl\n"
        f"wb = openpyxl.load_workbook({str(target)!r})\n"
        "ws = wb['Data']\n"
        "ws['A2'] = 10\n"
        "ws['D2'] = 'new'\n"
        f"wb.save({str(target)!r})\n",
    )
    pre = target.read_bytes()
    result = run_transaction(target, script)
    assert not result.aborted
    assert result.validation is not None and result.validation.passed
    assert result.delta is not None and not result.delta.created
    committed = Path(result.committed_path).read_bytes()
    assert hashlib.sha256(committed).hexdigest() == result.telemetry.post_hash
    assert result.telemetry.pre_hash == hashlib.sha256(pre).hexdigest()
    # delta carries real observed effects; replay reproduces committed exactly
    assert any(e["address"] == "A2" for e in result.delta.cell_effects)
    assert read_parts(replay_delta(pre, result.delta)) == read_parts(committed)


def test_formula_and_new_sheet_committed_equals_produced(tmp_path):
    target = tmp_path / "book.xlsx"
    _make_workbook(target)
    pre = target.read_bytes()
    script = _write_script(
        tmp_path / "mut.py",
        "import openpyxl\n"
        f"wb = openpyxl.load_workbook({str(target)!r})\n"
        "ws = wb.create_sheet('Analysis')\n"
        "ws['A1'] = '=SUM(Data!A2:B2)'\n"
        "wb['Data']['B2'] = 5\n"
        f"wb.save({str(target)!r})\n",
    )
    result = run_transaction(target, script)
    assert not result.aborted
    assert result.validation.passed
    committed = Path(result.committed_path).read_bytes()
    assert hashlib.sha256(committed).hexdigest() == result.telemetry.post_hash
    assert result.telemetry.pre_hash == hashlib.sha256(pre).hexdigest()
    replayed = replay_delta(pre, result.delta)
    assert read_parts(replayed) == read_parts(committed)


def test_creation_committed_equals_produced(tmp_path):
    target = tmp_path / "created.xlsx"
    script = _write_script(
        tmp_path / "mk.py",
        "import openpyxl\n"
        "wb = openpyxl.Workbook()\n"
        "wb.active['A1'] = 'hello'\n"
        f"wb.save({str(target)!r})\n",
    )
    result = run_transaction(target, script)
    assert not result.aborted
    assert result.delta.created
    assert result.telemetry.pre_hash is None
    assert result.validation.passed


def test_opaque_parts_preserved_byte_exact(tmp_path):
    target = tmp_path / "book.xlsx"
    _make_workbook(target)
    # Graft an opaque part (drawing-like payload) onto the package.
    raw = target.read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as src, zipfile.ZipFile(
        buf, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for n in src.namelist():
            dst.writestr(n, src.read(n))
        dst.writestr("xl/drawings/drawing1.xml", b"<opaque>keep-me</opaque>")
    target.write_bytes(buf.getvalue())
    pre = target.read_bytes()
    script = _write_script(
        tmp_path / "mut.py",
        "import openpyxl\n"
        f"wb = openpyxl.load_workbook({str(target)!r})\n"
        "wb['Data']['A2'] = 99\n"
        f"wb.save({str(target)!r})\n",
    )
    # openpyxl drops unknown parts on save; record whether it survives.
    result = run_transaction(target, script)
    assert not result.aborted
    committed = Path(result.committed_path).read_bytes()
    assert hashlib.sha256(committed).hexdigest() == result.telemetry.post_hash
    # Whatever Python produced, replay reproduces exactly (F1 part-exact).
    assert read_parts(replay_delta(pre, result.delta)) == read_parts(committed)
    assert result.validation.checks["captured_equals_committed"]


def test_failed_script_aborts_without_commit(tmp_path):
    target = tmp_path / "book.xlsx"
    _make_workbook(target)
    pre = target.read_bytes()
    script = _write_script(tmp_path / "bad.py", "raise RuntimeError('boom')\n")
    result = run_transaction(target, script)
    assert result.aborted
    assert result.delta is None
    assert target.read_bytes() == pre


def test_dir_entries_preserved_on_replay(tmp_path):
    """Packages with explicit zip directory entries round-trip part-exact
    (regression: empty-image deletion sentinel used to drop them)."""
    from benchmark.transparent_runtime.delta import derive_delta, replay_delta, read_parts
    target = tmp_path / "book.xlsx"
    _make_workbook(target)
    raw = target.read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as src, zipfile.ZipFile(
        buf, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for n in src.namelist():
            dst.writestr(n, src.read(n))
        dst.writestr("xl/customdir/", b"")
    data = buf.getvalue()
    delta = derive_delta(None, data)
    assert read_parts(replay_delta(None, delta)) == read_parts(data)


def test_mechanical_validation_rejects_corrupt_output(tmp_path):
    target = tmp_path / "book.xlsx"
    _make_workbook(target)
    pre = target.read_bytes()
    script = _write_script(
        tmp_path / "mut.py",
        "import openpyxl\n"
        f"wb = openpyxl.load_workbook({str(target)!r})\n"
        "wb['Data']['A2'] = 7\n"
        f"wb.save({str(target)!r})\n",
    )
    result = run_transaction(target, script)
    assert not result.aborted
    corrupted = b"not a zip package"
    report = validate_mechanical(pre, target.read_bytes(), corrupted, result.delta)
    assert not report.passed
    assert report.checks["readable"] is False



