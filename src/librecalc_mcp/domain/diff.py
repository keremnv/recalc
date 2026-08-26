"""Semantic diff between two workbook observations.

Separates exact direct changes (labels, constant inputs, formula expressions, formula
errors) from bounded evidence of downstream recalculation. Emitting every downstream
inequality once produced a 198,664-byte comparison that the agent harness truncated;
the same content now bounds representatives per sheet while keeping complete counts.
"""

from __future__ import annotations

import math
from typing import Any

from librecalc_mcp.domain.grid import A1_RANGE, a1_sort_key, column_label, column_number

_DOWNSTREAM_VALUE_GLOBAL_LIMIT = 80

_DOWNSTREAM_VALUE_PER_SHEET_LIMIT = 8

_DIFF_ABSOLUTE_TOLERANCE = 1e-12

_DIFF_RELATIVE_TOLERANCE = 1e-9


def _mapping_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_keys = set(before)
    after_keys = set(after)
    return {
        "added": {key: after[key] for key in sorted(after_keys - before_keys)},
        "removed": {key: before[key] for key in sorted(before_keys - after_keys)},
        "changed": {
            key: {"before": before[key], "after": after[key]}
            for key in sorted(before_keys & after_keys)
            if before[key] != after[key]
        },
    }

def _values_equivalent(before: Any, after: Any) -> bool:
    if (
        isinstance(before, (int, float))
        and not isinstance(before, bool)
        and isinstance(after, (int, float))
        and not isinstance(after, bool)
    ):
        return math.isclose(
            before,
            after,
            rel_tol=_DIFF_RELATIVE_TOLERANCE,
            abs_tol=_DIFF_ABSOLUTE_TOLERANCE,
        )
    return before == after

def _address_bounding_range(addresses: list[str]) -> str | None:
    parsed = []
    for address in addresses:
        match = A1_RANGE.fullmatch(address.upper())
        if match is None:
            continue
        column, row, _, _ = match.groups()
        parsed.append((column_number(column), int(row)))
    if not parsed:
        return None
    min_column = min(column for column, _ in parsed)
    max_column = max(column for column, _ in parsed)
    min_row = min(row for _, row in parsed)
    max_row = max(row for _, row in parsed)
    start = f"{column_label(min_column)}{min_row}"
    end = f"{column_label(max_column)}{max_row}"
    return start if start == end else f"{start}:{end}"

def _evenly_spaced_keys(values: dict[str, Any], limit: int) -> list[str]:
    keys = sorted(values, key=a1_sort_key)
    if len(keys) <= limit:
        return keys
    if limit == 1:
        return keys[:1]
    indexes = [index * (len(keys) - 1) // (limit - 1) for index in range(limit)]
    return [keys[index] for index in indexes]

def _downstream_value_summary(
    changes_by_sheet: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sampled_by_sheet = {
        sheet: _evenly_spaced_keys(changes, _DOWNSTREAM_VALUE_PER_SHEET_LIMIT)
        for sheet, changes in sorted(changes_by_sheet.items())
    }
    selected: list[dict[str, Any]] = []
    for offset in range(_DOWNSTREAM_VALUE_PER_SHEET_LIMIT):
        for sheet, addresses in sampled_by_sheet.items():
            if len(selected) >= _DOWNSTREAM_VALUE_GLOBAL_LIMIT:
                break
            if offset < len(addresses):
                address = addresses[offset]
                selected.append(
                    {
                        "sheet": sheet,
                        "address": address,
                        **changes_by_sheet[sheet][address],
                    }
                )
    total = sum(len(changes) for changes in changes_by_sheet.values())
    return {
        "count": total,
        "by_sheet": {
            sheet: {
                "count": len(changes),
                "affected_range": _address_bounding_range(list(changes)),
            }
            for sheet, changes in sorted(changes_by_sheet.items())
        },
        "representatives": selected,
        "representatives_returned": len(selected),
        "omitted": total - len(selected),
        "note": (
            "Values whose formulas were unchanged, after tight numeric-equivalence filtering. "
            "Counts and affected ranges are complete; representatives are bounded and spatially "
            "sampled. Direct formula/input edits and formula-error transitions remain complete."
        ),
    }

def _candidate_gaps(sheet: dict[str, Any]) -> dict[str, str]:
    return dict(sheet.get("inferred_table", {}).get("candidate_gaps", {}))

def semantic_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare two semantic snapshots without depending on a Calc backend."""
    before_sheets = {sheet["name"]: sheet for sheet in before.get("sheets", [])}
    after_sheets = {sheet["name"]: sheet for sheet in after.get("sheets", [])}
    common_sheets = sorted(set(before_sheets) & set(after_sheets))
    summary = {
        "sheets_added": len(set(after_sheets) - set(before_sheets)),
        "sheets_removed": len(set(before_sheets) - set(after_sheets)),
        "labels_changed": 0,
        "inputs_added": 0,
        "inputs_removed": 0,
        "inputs_changed": 0,
        "formulas_added": 0,
        "formulas_removed": 0,
        "formulas_changed": 0,
        "formula_values_changed": 0,
        "formula_errors_added": 0,
        "formula_errors_removed": 0,
        "formula_errors_changed": 0,
        "candidate_gaps_resolved": 0,
        "candidate_gaps_new": 0,
        "candidate_gaps_remaining": 0,
    }
    sheet_changes: dict[str, Any] = {}
    downstream_values_by_sheet: dict[str, dict[str, Any]] = {}
    for name in common_sheets:
        before_sheet = before_sheets[name]
        after_sheet = after_sheets[name]
        label_delta = _mapping_delta(before_sheet.get("labels", {}), after_sheet.get("labels", {}))
        input_delta = _mapping_delta(before_sheet.get("inputs", {}), after_sheet.get("inputs", {}))

        before_formulas = before_sheet.get("formulas", {})
        after_formulas = after_sheet.get("formulas", {})
        before_expressions = {
            address: details.get("expression") for address, details in before_formulas.items()
        }
        after_expressions = {
            address: details.get("expression") for address, details in after_formulas.items()
        }
        formula_delta = _mapping_delta(before_expressions, after_expressions)
        formula_error_delta = _mapping_delta(
            before_sheet.get("formula_errors", {}),
            after_sheet.get("formula_errors", {}),
        )
        formula_values_changed = {
            address: {
                "expression": after_formulas[address].get("expression"),
                "before": before_formulas[address].get("value"),
                "after": after_formulas[address].get("value"),
            }
            for address in sorted(set(before_formulas) & set(after_formulas))
            if before_formulas[address].get("expression")
            == after_formulas[address].get("expression")
            and not _values_equivalent(
                before_formulas[address].get("value"),
                after_formulas[address].get("value"),
            )
        }
        if formula_values_changed:
            downstream_values_by_sheet[name] = formula_values_changed

        before_gaps = _candidate_gaps(before_sheet)
        after_gaps = _candidate_gaps(after_sheet)
        resolved_gaps = {key: before_gaps[key] for key in sorted(set(before_gaps) - set(after_gaps))}
        new_gaps = {key: after_gaps[key] for key in sorted(set(after_gaps) - set(before_gaps))}
        remaining_gaps = {
            key: after_gaps[key] for key in sorted(set(before_gaps) & set(after_gaps))
        }

        summary["labels_changed"] += sum(len(values) for values in label_delta.values())
        summary["inputs_added"] += len(input_delta["added"])
        summary["inputs_removed"] += len(input_delta["removed"])
        summary["inputs_changed"] += len(input_delta["changed"])
        summary["formulas_added"] += len(formula_delta["added"])
        summary["formulas_removed"] += len(formula_delta["removed"])
        summary["formulas_changed"] += len(formula_delta["changed"])
        summary["formula_values_changed"] += len(formula_values_changed)
        summary["formula_errors_added"] += len(formula_error_delta["added"])
        summary["formula_errors_removed"] += len(formula_error_delta["removed"])
        summary["formula_errors_changed"] += len(formula_error_delta["changed"])
        summary["candidate_gaps_resolved"] += len(resolved_gaps)
        summary["candidate_gaps_new"] += len(new_gaps)
        summary["candidate_gaps_remaining"] += len(remaining_gaps)

        used_range = {
            "before": before_sheet.get("used_range"),
            "after": after_sheet.get("used_range"),
        }
        has_changes = any(
            (
                used_range["before"] != used_range["after"],
                *(bool(values) for values in label_delta.values()),
                *(bool(values) for values in input_delta.values()),
                *(bool(values) for values in formula_delta.values()),
                bool(formula_values_changed),
                *(bool(values) for values in formula_error_delta.values()),
                bool(resolved_gaps),
                bool(new_gaps),
            )
        )
        if has_changes:
            change: dict[str, Any] = {}
            if used_range["before"] != used_range["after"]:
                change["used_range"] = used_range
            if any(label_delta.values()):
                change["labels"] = label_delta
            if any(input_delta.values()):
                change["inputs"] = input_delta
            if any(formula_delta.values()):
                change["formulas"] = formula_delta
            if any(formula_error_delta.values()):
                change["formula_errors"] = formula_error_delta
            if resolved_gaps or new_gaps:
                change["candidate_gaps"] = {
                    "resolved": resolved_gaps,
                    "new": new_gaps,
                    "note": "Heuristic structural gaps, not validation failures.",
                }
            if change:
                sheet_changes[name] = change

    return {
        "observation": "semantic-diff-v1",
        "before": before.get("title"),
        "after": after.get("title"),
        "sheets_added": sorted(set(after_sheets) - set(before_sheets)),
        "sheets_removed": sorted(set(before_sheets) - set(after_sheets)),
        "summary": summary,
        "downstream_formula_values": _downstream_value_summary(downstream_values_by_sheet),
        "sheet_changes": sheet_changes,
    }
