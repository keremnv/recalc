from __future__ import annotations

import json

from benchmark.paired_autopsy import _inspect_mentions, _view_xlsx_covers, autopsy_trajectory


def test_inspect_names_a_selected_error_and_records_its_rank() -> None:
    payload = {
        "formula_errors": {
            "cell_count": 520,
            "selected_count": 4,
            "selected_cells": [
                {"sheet": "Other", "address": "A1"},
                {"sheet": "Cover", "address": "G10", "formula": "=$DCF.E22"},
            ],
        },
        "sheets": [{"name": "Cover", "used_range": "A1:L12"}],
    }
    facts = _inspect_mentions(json.dumps(payload), "Cover", "G10")

    assert facts["named"] is True
    assert facts["rank"] == 2
    assert facts["selected_count"] == 2
    assert facts["extent_only"] is False


def test_used_range_alone_is_extent_not_a_name() -> None:
    payload = {
        "formula_errors": {"selected_cells": []},
        "sheets": [{"name": "Cover", "used_range": "A1:L12"}],
    }
    facts = _inspect_mentions(json.dumps(payload), "Cover", "G10")

    assert facts["named"] is False
    assert facts["extent_only"] is True


def test_view_xlsx_row_dump_is_a_read_of_that_cell() -> None:
    observation = (
        "Sheet: Cover\n"
        "Row 9: ['Active Case']\n"
        "Row 10: ['Implied Upside', None, None, None, '=DCF!E22']\n"
        "Sheet: DCF\n"
        "Row 10: ['other']\n"
    )

    assert _view_xlsx_covers(observation, "Cover", "G10") is True
    assert _view_xlsx_covers(observation, "Cover", "G11") is False
    assert _view_xlsx_covers(observation, "Revenue Build", "G10") is False


def test_autopsy_sorts_named_read_unwritten_after_compare() -> None:
    inspect = json.dumps(
        {
            "formula_errors": {
                "cell_count": 20,
                "selected_cells": [{"sheet": "Cover", "address": "G10"}],
            }
        }
    )
    steps = [
        {"action": "calc_inspect x.xlsx", "observation": inspect},
        {
            "action": (
                "calc_read_ranges x.xlsx "
                "%5B%7B%22sheet%22%3A%22Cover%22%2C%22range%22%3A%22A1%3AL12%22%7D%5D"
            ),
            "observation": json.dumps(
                {"ranges": [{"sheet": "Cover", "range": "A1:L12", "cells": [{"address": "A1"}]}]}
            ),
        },
        {"action": "calc_fill_formulas x.xlsx y.xlsx %5B%7B%22sheet%22%3A%22Other%22%2C%22range%22%3A%22A1%22%2C%22formula%22%3A%22%3D1%22%7D%5D"},
        {"action": "calc_compare x.xlsx y.xlsx", "observation": "Cover G10 still an error"},
        {"action": "submit"},
    ]
    result = autopsy_trajectory(steps, "Cover!G10")

    assert result["named"] is True
    assert result["read"] is True
    assert result["written"] is False
    assert result["after_compare"] is True
    assert result["bucket"] == "read_unwritten"


def test_percent_encoded_spaces_in_ranges_json_still_parse() -> None:
    action = (
        "calc_read_ranges x.xlsx "
        "%5B%7B%22range%22%3A%20%22A1%3AL12%22%2C%20%22sheet%22%3A%20%22Cover%22%7D%5D"
    )
    from benchmark.paired_autopsy import _read_action_covers

    assert _read_action_covers(action, "Cover", "G10") is True


def test_boundary_continuation_is_a_name() -> None:
    payload = {
        "boundary_continuations": {
            "candidates": [
                {
                    "sheet": "Working Capital Schedule",
                    "address": "M3",
                    "inferred_formula": "=EOMONTH(L3,12)",
                }
            ],
            "note": "Not requirements.",
        }
    }
    facts = _inspect_mentions(json.dumps(payload), "Working Capital Schedule", "M3")

    assert facts["named"] is True
    assert facts["named_sources"] == ["boundary_continuations"]


def test_failed_oversize_read_is_not_a_shown_read() -> None:
    from benchmark.paired_autopsy import _read_action_covers, _read_covers, autopsy_trajectory

    action = "calc_read x.xlsx LBO B60:K140"
    failed = json.dumps({"ok": False, "error": "covers 810 cells"})
    assert _read_action_covers(action, "LBO", "H107") is True
    assert _read_covers(action, failed, "LBO", "H107") is False

    steps = [
        {"action": "calc_inspect x.xlsx", "observation": "{}"},
        {"action": action, "observation": failed},
        {"action": "submit"},
    ]
    result = autopsy_trajectory(steps, "LBO!H107")
    assert result["read_attempted"] is True
    assert result["read"] is False
    assert result["bucket"] == "unnamed"
