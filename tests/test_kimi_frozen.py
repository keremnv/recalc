from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).parents[1] / "benchmark/run_kimi_frozen.py"
    spec = importlib.util.spec_from_file_location("run_kimi_frozen", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_runner_splits_debugging_from_compute() -> None:
    frozen = _module()
    compute, debugging = frozen._group(
        [
            {"category": "Template", "id": "03_02"},
            {"category": "Financial_Model", "id": "04_01"},
            {"category": "Debugging", "id": "06_02"},
        ]
    )
    assert compute == ["Template:03_02", "Financial_Model:04_01"]
    assert debugging == ["Debugging:06_02"]


def _write_slice(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "tasks": [
                    {"category": "Template", "id": "01_05"},
                    {"category": "Debugging", "id": "06_02"},
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_frozen_main_scores_once_after_inner_groups_disable_score(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frozen = _module()
    slice_path = _write_slice(tmp_path / "slice.json")
    commands: list[list[str]] = []

    def fake_call(command, cwd=None):
        commands.append([str(part) for part in command])
        return 0

    monkeypatch.setattr(frozen.subprocess, "call", fake_call)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_kimi_frozen.py", "--slice", str(slice_path), "--run-name", "kimi-pack"],
    )

    assert frozen.main() == 0
    assert len(commands) == 3
    assert all("--no-score" in command for command in commands[:2])
    assert all(
        command[command.index("--reasoning-effort") + 1] == "low" for command in commands[:2]
    )
    assert commands[-1][1] == str(frozen.SCORER)
    assert "--write-ledger" in commands[-1]
    assert "--no-score" not in commands[-1]


def test_frozen_forwards_reasoning_effort(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frozen = _module()
    slice_path = _write_slice(tmp_path / "slice.json")
    commands: list[list[str]] = []
    monkeypatch.setattr(
        frozen.subprocess,
        "call",
        lambda command, cwd=None: commands.append([str(part) for part in command]) or 0,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_kimi_frozen.py",
            "--slice",
            str(slice_path),
            "--run-name",
            "sol-pack",
            "--model",
            "openai/gpt-5.6-sol",
            "--reasoning-effort",
            "medium",
            "--no-score",
        ],
    )

    assert frozen.main() == 0
    assert commands
    assert all(command[command.index("--reasoning-effort") + 1] == "medium" for command in commands)
    assert all("--model" in command and "openai/gpt-5.6-sol" in command for command in commands)


def test_frozen_no_score_skips_official_pack(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frozen = _module()
    slice_path = _write_slice(tmp_path / "slice.json")
    commands: list[list[str]] = []
    monkeypatch.setattr(
        frozen.subprocess,
        "call",
        lambda command, cwd=None: commands.append([str(part) for part in command]) or 0,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_kimi_frozen.py",
            "--slice",
            str(slice_path),
            "--run-name",
            "kimi-pack",
            "--no-score",
        ],
    )

    assert frozen.main() == 0
    assert commands
    assert all(str(frozen.SCORER) not in command for command in commands)


def test_frozen_debug_ablation_changes_only_debugging_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frozen = _module()
    slice_path = _write_slice(tmp_path / "slice.json")
    commands: list[list[str]] = []
    monkeypatch.setattr(
        frozen.subprocess,
        "call",
        lambda command, cwd=None: commands.append([str(part) for part in command]) or 0,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_kimi_frozen.py",
            "--slice",
            str(slice_path),
            "--run-name",
            "debug-two-pass",
            "--debug-execution",
            "semantic-program-v1",
            "--debug-repair-passes",
            "2",
            "--no-score",
        ],
    )

    assert frozen.main() == 0
    compute, debugging = commands
    assert compute[compute.index("--execution") + 1] == "formula-blocks-v1"
    assert compute[compute.index("--repair-passes") + 1] == "1"
    assert debugging[debugging.index("--execution") + 1] == "semantic-program-v1"
    assert debugging[debugging.index("--repair-passes") + 1] == "2"
