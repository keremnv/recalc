from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

from benchmark.experiment_validity import invalid_reason
from benchmark.mismatch_census import (
    WorkbookViews,
    _scored_output_path,
    census_workbooks,
    discover_attempts,
    run_census,
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


def test_run_census_excludes_an_unreadable_output_instead_of_crashing(tmp_path: Path) -> None:
    """An agent can submit a file that is not a workbook at all.

    The official evaluator already scores those as "File is not a zip file"; the census
    must record them the way documented exclusions are recorded rather than ending the
    whole run, which is what stopped the first 297-task census.
    """

    data_root = tmp_path / "data" / "Financial_Model"
    (data_root / "inputs").mkdir(parents=True)
    (data_root / "goldens").mkdir(parents=True)
    _book(A1=1).save(data_root / "inputs" / "in.xlsx")
    _book(A1=2).save(data_root / "goldens" / "gold.xlsx")
    (data_root / "dataset.json").write_text(
        json.dumps(
            [
                {
                    "id": "00_00",
                    "spreadsheet_path": "inputs/in.xlsx",
                    "golden_response_path": "goldens/gold.xlsx",
                    "answer_position": "Sheet1!A1",
                    "instruction": "",
                }
            ]
        ),
        encoding="utf-8",
    )

    runs_root = tmp_path / "runs"
    run = runs_root / "corrupt-run"
    attempt = run / "Financial_Model-00_00"
    attempt.mkdir(parents=True)
    (attempt / "output.xlsx").write_bytes(b"this is not a zip file")
    (run / "official_scores.json").write_text(
        json.dumps(
            {
                "run_name": "corrupt-run",
                "tasks": {"Financial_Model:00_00": {"accuracy": 0.0}},
            }
        ),
        encoding="utf-8",
    )

    results, exclusions = run_census(runs_root=runs_root, data_root=tmp_path / "data")

    assert results == []
    assert len(exclusions) == 1
    assert exclusions[0]["task"] == "Financial_Model:00_00"
    assert "unreadable workbook" in exclusions[0]["reason"]


def test_scored_output_path_prefers_the_refreshed_submission_copy(tmp_path: Path) -> None:
    """The evaluator scores the LibreOffice-refreshed copy, so the census must diff that one.

    LibreOffice writes many formula cells with no cached value. Diffing the unrefreshed
    run-directory copy makes every such cell look like a mismatch even when its formula is
    byte-identical to the golden's, which is what put the census 63/122 out of agreement
    with the official scores.
    """

    run = tmp_path / "run"
    raw = run / "Debugging-01_08"
    raw.mkdir(parents=True)
    (raw / "output.xlsx").write_bytes(b"raw")

    assert _scored_output_path(run, "Debugging", "01_08") == raw / "output.xlsx"

    submission = run / "submission" / "outputs" / "Debugging"
    submission.mkdir(parents=True)
    (submission / "01_08_output.xlsx").write_bytes(b"refreshed")

    assert _scored_output_path(run, "Debugging", "01_08") == submission / "01_08_output.xlsx"
    assert _scored_output_path(run, "Debugging", "99_99") is None
