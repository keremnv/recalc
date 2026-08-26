from __future__ import annotations

import importlib.util
from pathlib import Path


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
