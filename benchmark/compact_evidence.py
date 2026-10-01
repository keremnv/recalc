"""Lossless compact encoding of synthesis evidence.

This module changes only the representation of already-materialized facts.
It does not retrieve, rank, summarize, or add inferred roles.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

ENCODING_NAME = "columnar_dict_v1"
LEGEND = {
    "encoding": ENCODING_NAME,
    "how_to_read": (
        "Column-major lossless tables. columns[j] names field j. If dicts has that "
        "name, values[j][i] indexes dicts[column]; else values[j][i] is the raw "
        "value. Row i is values[*][i]. entity_ids is the full working set, including "
        "IDs with no table row. Same facts as row-oriented evidence; no omitted, "
        "summarized, ranked, or handle-only records."
    ),
}


def digest(value: Any) -> str:
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compact_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def byte_size(value: Any) -> int:
    return len(compact_dumps(value).encode())


def _freeze(value: Any) -> str:
    return dumps(value)


def encode_column(values: list[Any]) -> tuple[list[Any], list[Any] | None]:
    """Return (payload, dictionary-or-None). Dictionary is used only when smaller."""
    index: dict[str, int] = {}
    uniques: list[Any] = []
    codes: list[int] = []
    for value in values:
        key = _freeze(value)
        if key not in index:
            index[key] = len(uniques)
            uniques.append(value)
        codes.append(index[key])
    if len(uniques) >= len(values):
        return values, None
    raw_len = len(compact_dumps(values).encode())
    dict_len = len(compact_dumps({"d": uniques, "c": codes}).encode())
    if dict_len < raw_len:
        return codes, uniques
    return values, None


def encode_table(table: dict[str, Any]) -> dict[str, Any]:
    columns = list(table.get("columns") or [])
    rows = list(table.get("rows") or [])
    values: list[list[Any]] = []
    dicts: dict[str, list[Any]] = {}
    for j, column in enumerate(columns):
        column_values = [row[j] if j < len(row) else None for row in rows]
        payload, dictionary = encode_column(column_values)
        values.append(payload)
        if dictionary is not None:
            dicts[column] = dictionary
    encoded: dict[str, Any] = {"columns": columns, "values": values}
    if dicts:
        encoded["dicts"] = dicts
    return encoded


def decode_table(table: dict[str, Any]) -> dict[str, Any]:
    columns = list(table.get("columns") or [])
    values = list(table.get("values") or [])
    dicts = table.get("dicts") or {}
    if "rows" in table and "values" not in table:
        return {"columns": columns, "rows": [list(row) for row in table.get("rows") or []]}
    n_rows = len(values[0]) if values else 0
    decoded_columns: list[list[Any]] = []
    for j, column in enumerate(columns):
        series = list(values[j]) if j < len(values) else [None] * n_rows
        dictionary = dicts.get(column)
        if dictionary is None:
            decoded_columns.append(series)
            continue
        decoded_columns.append([dictionary[code] for code in series])
    rows = [[decoded_columns[j][i] for j in range(len(columns))] for i in range(n_rows)]
    return {"columns": columns, "rows": rows}


def encode_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    encoded = {
        "encoding": ENCODING_NAME,
        "legend": LEGEND,
        "entity_ids": list(evidence.get("entity_ids") or []),
        "entities": {name: encode_table(table) for name, table in (evidence.get("entities") or {}).items()},
        "relations": {name: encode_table(table) for name, table in (evidence.get("relations") or {}).items()},
    }
    return encoded


def is_compact(evidence: dict[str, Any]) -> bool:
    return evidence.get("encoding") == ENCODING_NAME


def decode_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if not is_compact(evidence):
        return {
            "entity_ids": list(evidence.get("entity_ids") or []),
            "entities": {name: {"columns": list(table.get("columns") or []), "rows": [list(row) for row in table.get("rows") or []]} for name, table in (evidence.get("entities") or {}).items()},
            "relations": {name: {"columns": list(table.get("columns") or []), "rows": [list(row) for row in table.get("rows") or []]} for name, table in (evidence.get("relations") or {}).items()},
        }
    return {
        "entity_ids": list(evidence.get("entity_ids") or []),
        "entities": {name: decode_table(table) for name, table in (evidence.get("entities") or {}).items()},
        "relations": {name: decode_table(table) for name, table in (evidence.get("relations") or {}).items()},
    }


def _row_record(namespace: str, table: str, columns: list[str], row: list[Any]) -> tuple[Any, ...]:
    mapping = {columns[i]: (row[i] if i < len(row) else None) for i in range(len(columns))}
    return (namespace, table, tuple(sorted(mapping.items(), key=lambda item: item[0])))


def canonical_facts(evidence: dict[str, Any]) -> dict[str, Any]:
    """Layout-independent factual projection used for CONTROL/TREATMENT equality."""
    decoded = decode_evidence(evidence)
    tables: dict[str, Any] = {}
    records: list[tuple[Any, ...]] = []
    for namespace in ("entities", "relations"):
        for name in sorted((decoded.get(namespace) or {})):
            table = decoded[namespace][name]
            columns = list(table.get("columns") or [])
            row_records = [_row_record(namespace, name, columns, row) for row in table.get("rows") or []]
            tables[f"{namespace}.{name}"] = {
                "column_set": tuple(sorted(columns)),
                "row_count": len(row_records),
                "rows": tuple(sorted(row_records)),
            }
            records.extend(row_records)
    return {
        "entity_ids": tuple(decoded.get("entity_ids") or []),
        "entity_id_set": tuple(sorted(set(decoded.get("entity_ids") or []))),
        "tables": tables,
        "records": tuple(sorted(records)),
        "record_count": len(records),
    }


def canonical_hash(evidence: dict[str, Any]) -> str:
    return digest(canonical_facts(evidence))


def factual_diff(control: dict[str, Any], treatment: dict[str, Any]) -> dict[str, Any]:
    left = canonical_facts(control)
    right = canonical_facts(treatment)
    mismatches: dict[str, Any] = {}
    if left["entity_id_set"] != right["entity_id_set"]:
        mismatches["entity_ids"] = {
            "only_control": sorted(set(left["entity_id_set"]) - set(right["entity_id_set"])),
            "only_treatment": sorted(set(right["entity_id_set"]) - set(left["entity_id_set"])),
        }
    if left["entity_ids"] != right["entity_ids"]:
        mismatches["entity_id_order"] = True
    left_tables = set(left["tables"])
    right_tables = set(right["tables"])
    if left_tables != right_tables:
        mismatches["tables"] = {"only_control": sorted(left_tables - right_tables), "only_treatment": sorted(right_tables - left_tables)}
    for name in sorted(left_tables & right_tables):
        if left["tables"][name] != right["tables"][name]:
            left_rows = set(left["tables"][name]["rows"])
            right_rows = set(right["tables"][name]["rows"])
            mismatches[name] = {
                "column_set_equal": left["tables"][name]["column_set"] == right["tables"][name]["column_set"],
                "only_control_rows": len(left_rows - right_rows),
                "only_treatment_rows": len(right_rows - left_rows),
                "control_row_count": left["tables"][name]["row_count"],
                "treatment_row_count": right["tables"][name]["row_count"],
            }
    return {
        "equal": not mismatches,
        "control_canonical_sha256": digest(left),
        "treatment_canonical_sha256": digest(right),
        "mismatches": mismatches,
    }


def cell_fact(evidence: dict[str, Any], cell_id: str) -> dict[str, Any] | None:
    decoded = decode_evidence(evidence)
    table = (decoded.get("entities") or {}).get("cells") or {}
    columns = table.get("columns") or []
    for row in table.get("rows") or []:
        mapping = {columns[i]: row[i] if i < len(row) else None for i in range(len(columns))}
        if mapping.get("cell_id") == cell_id:
            return mapping
    return None
