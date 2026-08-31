"""Commit-check behaviour, including the measured limit of intent-relative checking."""

from __future__ import annotations

from librecalc_mcp.domain.commit_checks import (
    changed_cells,
    declared_targets,
    error_kind,
    expand_range,
    new_formula_errors,
    report,
    unextended_continuations,
    unrequested_writes,
)


def test_expand_range_covers_rectangles_and_single_cells() -> None:
    assert expand_range("S", "B2") == {("S", "B2")}
    assert expand_range("S", "A1:B2") == {("S", "A1"), ("S", "A2"), ("S", "B1"), ("S", "B2")}
    assert len(expand_range("S", "A1:Z10")) == 260


def test_declared_targets_reads_the_agents_own_requests_and_skips_junk() -> None:
    targets = declared_targets(
        [
            {"sheet": "S", "range": "A1:A2", "formula": "=1"},
            {"sheet": "S", "cell": "C3"},
            {"sheet": "S", "range": "not-a-range"},
            {"range": "A1"},
            "nonsense",  # type: ignore[list-item]
        ]
    )
    assert targets == {("S", "A1"), ("S", "A2"), ("S", "C3")}


def test_a_recalculated_formula_is_not_a_write() -> None:
    before = {("S", "A1"): (1, "=B1"), ("S", "B1"): (1, None)}
    after = {("S", "A1"): (99, "=B1"), ("S", "B1"): (99, None)}

    # A1 keeps its formula and only its cached value moved: recalculation, not a write.
    assert changed_cells(before, after) == {("S", "B1")}


def test_new_formula_errors_reports_only_errors_the_input_did_not_have() -> None:
    before = {("S", "A1"): ("#REF!", "=#REF!"), ("S", "A2"): (1, "=B2")}
    after = {("S", "A1"): ("#REF!", "=#REF!"), ("S", "A2"): ("#DIV/0!", "=B2/0")}

    findings = new_formula_errors(before, after)

    assert [(f.sheet, f.address) for f in findings] == [("S", "A2")]
    assert error_kind(before[("S", "A1")]) == "#REF!"
    assert error_kind((None, None)) is None


def test_unextended_continuation_fires_only_while_the_cell_is_still_blank() -> None:
    continuations = [{"sheet": "WCS", "address": "M3", "formula": "=EOMONTH(L3,12)"}]

    assert len(unextended_continuations({}, continuations)) == 1
    assert unextended_continuations({("WCS", "M3"): (None, "=EOMONTH(L3,12)")}, continuations) == []


def test_declared_overfills_are_invisible_to_the_unrequested_write_check() -> None:
    """The measured Template result: the agent declared the cells it should not have written.

    This is why intent-relative checking cannot be the overfill guard.
    """
    before = {("S", "C23"): (None, None)}
    after = {("S", "C23"): (5, None)}
    declared = {("S", "C23")}

    assert unrequested_writes(before, after, declared) == []
    # It still catches mutation the agent never named.
    assert len(unrequested_writes(before, after, set())) == 1


def test_report_groups_findings_by_check() -> None:
    before = {("S", "A1"): (None, None)}
    after = {("S", "A1"): (1, None)}

    payload = report(unrequested_writes(before, after, set()))

    assert payload["schema"] == "commit-checks-v1"
    assert payload["finding_count"] == 1
    assert payload["checks"]["unrequested_write"][0]["address"] == "A1"
