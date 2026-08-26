from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

from benchmark.experiment_validity import invalid_reason
from benchmark.mismatch_census import (
    WorkbookViews,
    census_workbooks,
    discover_attempts,
)


def _book(**cells) -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    for address, value in cells.items():
        sheet[address] = value
    return workbook


def _views(values: Workbook, raw: Workbook | None = None) -> WorkbookViews:
    return WorkbookViews(values, raw or values)


def test_invalid_reason_is_exact_run_and_task() -> None:
    assert invalid_reason("glm-5.3-v4-five-high-1", "Template:01_04")
    assert invalid_reason("glm-5.3-v4-five-high-1", "Template:02_03") is None
    assert invalid_reason("other-run", "Template:01_04") is None


def test_census_classifies_a_missed_blank_direct_target() -> None:
    result = census_workbooks(
        run_name="r",
        task_key="Financial_Model:00_00",
        answer_position="Sheet1!A1",
        input_views=_views(_book(A1=None), _book(A1=None)),
        golden_views=_views(_book(A1=5), _book(A1="=B1")),
        output_views=_views(_book(A1=None), _book(A1=None)),
        stored_score={"accuracy": 0.0, "regression_accuracy": 1.0, "modification_accuracy": 0.0},
    )

    assert result.modification_total == 1
    assert result.modification_correct == 0
    assert len(result.mismatches) == 1
    miss = result.mismatches[0]
    assert miss.official_partition == "modification"
    assert miss.target_kind == "direct"
    assert miss.causal_class == "direct blank target: unchanged"


def test_census_classifies_unchanged_formula_as_downstream_cascade() -> None:
    result = census_workbooks(
        run_name="r",
        task_key="Financial_Model:00_00",
        answer_position="Sheet1!A1",
        input_views=_views(_book(A1=1), _book(A1="=B1")),
        golden_views=_views(_book(A1=2), _book(A1="=B1")),
        output_views=_views(_book(A1=1), _book(A1="=B1")),
        stored_score={"accuracy": 0.0, "regression_accuracy": 1.0, "modification_accuracy": 0.0},
    )

    miss = result.mismatches[0]
    assert miss.official_partition == "modification"
    assert miss.target_kind == "downstream"
    assert miss.causal_class == "downstream cascade at unchanged formula"


def test_census_classifies_a_regression_over_edit() -> None:
    result = census_workbooks(
        run_name="r",
        task_key="Financial_Model:00_00",
        answer_position="Sheet1!A1",
        input_views=_views(_book(A1=10), _book(A1=10)),
        golden_views=_views(_book(A1=10), _book(A1=10)),
        output_views=_views(_book(A1=99), _book(A1=99)),
        stored_score={"accuracy": 0.0, "regression_accuracy": 0.0, "modification_accuracy": 1.0},
    )

    miss = result.mismatches[0]
    assert miss.official_partition == "regression"
    assert miss.target_kind == "regression"
    assert miss.causal_class == "regression cell over-edited"


def test_census_replays_an_exact_attempt_with_no_mismatches() -> None:
    input_book = _book(A1=10, A2=None)
    golden_book = _book(A1=10, A2=5)
    result = census_workbooks(
        run_name="r",
        task_key="Financial_Model:00_00",
        answer_position="Sheet1!A1:A2",
        input_views=_views(input_book, input_book),
        golden_views=_views(golden_book, golden_book),
        output_views=_views(golden_book, golden_book),
        stored_score={"accuracy": 1.0, "regression_accuracy": 1.0, "modification_accuracy": 1.0},
    )

    assert result.official_exact is True
    assert result.mismatches == ()
    assert result.score_matches_stored is True


def test_discover_attempts_excludes_known_invalid_runs(tmp_path: Path) -> None:
    run = tmp_path / "glm-5.3-v4-five-high-1"
    run.mkdir()
    (run / "official_scores.json").write_text(
        json.dumps(
            {
                "run_name": "glm-5.3-v4-five-high-1",
                "tasks": {
                    "Template:01_04": {"accuracy": 0.0},
                    "Template:02_03": {"accuracy": 0.0},
                },
            }
        ),
        encoding="utf-8",
    )

    attempts, exclusions = discover_attempts(tmp_path, include_known_invalid=False)
    assert [task for _, _, task, _ in attempts] == ["Template:02_03"]
    assert exclusions == [
        {
            "run_name": "glm-5.3-v4-five-high-1",
            "task": "Template:01_04",
            "reason": (
                "pre-fix output discovery matched task id across categories and copied "
                "Financial_Model:01_04 into Template:01_04"
            ),
        }
    ]
