from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "benchmark/score_openrouter_run.py"
    spec = importlib.util.spec_from_file_location("score_openrouter_run", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_outputs_copies_present_workbooks_and_skips_missing(tmp_path: Path) -> None:
    scorer = _module()
    run_root = tmp_path / "run"
    (run_root / "Template-01_05").mkdir(parents=True)
    (run_root / "Template-01_05" / "output.xlsx").write_bytes(b"xlsx")
    (run_root / "Template-01_06").mkdir()
    staging = tmp_path / "outputs"
    staged = scorer._stage_outputs(
        run_root,
        [{"category": "Template", "id": "01_05"}, {"category": "Template", "id": "01_06"}],
        staging,
    )
    assert staged == 1
    assert (staging / "Template/01_05_output.xlsx").read_bytes() == b"xlsx"
    assert not (staging / "Template/01_06_output.xlsx").exists()


def test_attempted_tasks_are_nonvisual_task_directories_only(tmp_path: Path) -> None:
    scorer = _module()
    run_root = tmp_path / "run"
    (run_root / "Template-01_05").mkdir(parents=True)
    (run_root / "Visualization-Task 1411527").mkdir()
    (run_root / "submission").mkdir()
    (run_root / "ledger.jsonl").write_text("{}\n", encoding="utf-8")
    assert scorer._attempted_tasks(run_root) == [{"category": "Template", "id": "01_05"}]


def test_score_run_writes_submission_pack_including_missing_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    scorer = _module()
    run_root = tmp_path / "kimi-run"
    (run_root / "Template-01_05").mkdir(parents=True)
    (run_root / "Template-01_05" / "output.xlsx").write_bytes(b"xlsx")
    (run_root / "Template-01_06").mkdir()
    official_json = tmp_path / "kimi-run_Template__regression.json"
    official_json.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(scorer, "_refresh_outputs", lambda path: None)
    monkeypatch.setattr(
        scorer,
        "_evaluate_category",
        lambda **kwargs: {
            "scores": [
                {
                    "id": "01_05",
                    "accuracy": 1.0,
                    "regression_accuracy": 1.0,
                    "modification_accuracy": 1.0,
                    "error_message": "",
                },
                {
                    "id": "01_06",
                    "accuracy": 0.0,
                    "regression_accuracy": 0.0,
                    "modification_accuracy": 0.0,
                    "error_message": "output file not exist",
                },
            ]
        },
    )
    monkeypatch.setattr(scorer, "_official_result_path", lambda model, category: official_json)

    assert scorer.score_run(run_root, write_ledger=False) == 0
    pack = json.loads((run_root / "official_scores.json").read_text(encoding="utf-8"))
    assert pack["evaluation_runtime"] == scorer.OFFICIAL_RUNTIME
    assert pack["exact"] == 1
    assert pack["scored"] == 2
    assert pack["missing_outputs"] == 1
    assert pack["tasks"]["Template:01_06"]["error_message"] == "output file not exist"
    assert (run_root / "submission/outputs/Template/01_05_output.xlsx").is_file()
    assert not (run_root / "submission/outputs/Template/01_06_output.xlsx").exists()
    assert (run_root / "submission/results" / official_json.name).is_file()
