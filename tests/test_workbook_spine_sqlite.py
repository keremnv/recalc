from __future__ import annotations

import json
from pathlib import Path

from benchmark.workbook_spine_sqlite import (
    ReadOnlySqlite,
    build_database,
    canonical_cell_id,
    canonical_formula_id,
    database_id_inventory,
)


def _tiny_spine() -> dict:
    return {
        "workbook_id": "wb:test",
        "path": "test.xlsx",
        "readable": True,
        "title_to_index": {"Sheet1": 0},
        "sheets": [{"id": "sheet:s00", "index": 0, "title": "Sheet1", "title_norm": "sheet1", "visibility": "visible", "bounds": {"min_row": 1, "min_col": 1, "max_row": 3, "max_col": 3}}],
        "occupied": [
            {"id": "cell:s00:r1:c1", "sheet_id": "sheet:s00", "row": 1, "col": 1, "address": "A1", "kind": "numeric", "payload": 1},
            {"id": "cell:s00:r1:c2", "sheet_id": "sheet:s00", "row": 1, "col": 2, "address": "B1", "kind": "formula", "payload": "=A1"},
        ],
        "rows": [{"id": "row:s00:r1", "sheet_id": "sheet:s00", "row": 1, "n_text": 0, "n_formula": 1, "n_value": 1, "n_blank": 0}],
        "cols": [{"id": "col:s00:c1", "sheet_id": "sheet:s00", "col": 1, "n_text": 0, "n_formula": 0, "n_value": 1, "periods": []}],
        "text_anchors": [], "formulas": [{"id": "formula:s00:r1:c2", "cell_id": "cell:s00:r1:c2", "formula": "=A1", "fingerprint": "A1", "class_id": "formula_class:test", "opaque": False}],
        "point_deps": [{"consumer_formula_id": "formula:s00:r1:c2", "source_id": "cell:s00:r1:c1", "cross_sheet": False, "type": "POINT_REFERENCE"}],
        "range_deps": [], "formula_classes": [{"id": "formula_class:test", "n": 1}], "class_members": {"formula_class:test": ["formula:s00:r1:c2"]},
        "periods": [], "regions": [], "merges": [], "hidden_rows": [], "hidden_cols": [], "s1_cell_ids": [], "stats": {},
    }


def test_ids_normalize_to_existing_spine_namespace() -> None:
    assert canonical_cell_id("cell:sheet:s03:r41:c8") == "cell:s03:r41:c8"
    assert canonical_formula_id("formula:sheet:s03:r41:c8") == "formula:s03:r41:c8"


def test_sqlite_is_read_only_and_never_silently_truncates(tmp_path: Path) -> None:
    spine = tmp_path / "spine.json"
    temporal = tmp_path / "temporal.json"
    database = tmp_path / "spine.sqlite"
    spine.write_text(json.dumps(_tiny_spine()), encoding="utf-8")
    temporal.write_text(json.dumps({"coordinates": []}), encoding="utf-8")
    build_database(spine, temporal, database)
    inventory = database_id_inventory(database)
    assert "cell:s00:r1:c1" in inventory
    assert "formula:s00:r1:c2" in inventory
    assert "formula_class:test" in inventory
    executor = ReadOnlySqlite(database, max_rows=1)
    assert executor.execute("SELECT COUNT(*) AS n FROM cells")["status"] == "OK"
    assert executor.execute("SELECT * FROM cells")["status"] == "RESULT_TOO_LARGE"
    assert executor.execute("UPDATE cells SET kind='x'")["status"] == "SQL_REJECTED"
    assert executor.execute("SELECT 1; SELECT 2")["status"] == "SQL_ERROR"


def test_compiled_scalar_values_survive_to_sql_evidence_and_target(tmp_path: Path) -> None:
    import openpyxl
    import matched_compiled_treatment as treatment
    from workbook_grounding_spine import compile_spine

    workbook = openpyxl.Workbook()
    values = [0, False, 35, 0.12]
    for i, value in enumerate(values, 1):
        workbook.active.cell(i, 1, value)
    workbook.active['B1'] = '=A1+A3'
    source = tmp_path / 'input.xlsx'
    workbook.save(source)
    workbook.close()
    compiled = compile_spine(source, workbook_key='test')
    spine, temporal, db = (tmp_path / name for name in ('spine.json', 'temporal.json', 'world.sqlite'))
    spine.write_text(json.dumps(compiled))
    temporal.write_text(json.dumps({'coordinates': []}))
    build_database(spine, temporal, db)
    ids = {f'cell:s00:r{i}:c1' for i in range(1, 5)}
    evidence = treatment.materialize(db, ids)['entities']['cells']
    rows = {r['cell_id']: r for r in (dict(zip(evidence['columns'], row)) for row in evidence['rows'])}
    for i, value in enumerate(values, 1):
        cid = f'cell:s00:r{i}:c1'
        assert rows[cid]['raw_value'] == str(value)
        target = treatment.target_from_id(compiled, cid, 'test', 'O1')
        assert target['current_input_content'] == value
        assert type(target['current_input_content']) is type(value)
        assert target['current_input_kind'] == 'value'


def test_legacy_numeric_record_without_payload_is_not_a_blank_target() -> None:
    import matched_compiled_treatment as treatment

    spine = _tiny_spine()
    spine['occupied'][0].pop('payload')
    target = treatment.target_from_id(spine, 'cell:s00:r1:c1', 'test', 'O1')
    assert target['current_input_kind'] == 'value'
    assert target['current_input_content'] is None  # do not invent the absent literal
