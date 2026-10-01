from __future__ import annotations

import json
from pathlib import Path

from benchmark.pattern_catalog import load_cases, load_surface, validate
from benchmark.pattern_census import value_shape

CATALOG = Path(__file__).resolve().parents[1] / "benchmark" / "pattern-catalog"


def test_catalog_validates() -> None:
    assert validate() == []


def test_every_established_pattern_has_cases_on_disk() -> None:
    cases = {item["id"] for item in load_cases()}
    for pattern in load_surface()["patterns"]:
        if pattern["status"] != "established":
            continue
        assert pattern["establishing_cases"], pattern["id"]
        assert set(pattern["establishing_cases"]) <= cases, pattern["id"]


def test_no_case_opened_a_golden() -> None:
    for case in load_cases():
        assert case["facts"]["opened_golden"] is False


def test_census_file_matches_surface_run() -> None:
    surface = load_surface()
    path = CATALOG / "census" / f"{surface['census']['run']}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["scored"] == 297
    assert payload["exact"] == 24
    assert payload["autopsy"] == surface["census"]["autopsy"]


def test_value_shape_sign_flip_and_formula_text() -> None:
    assert value_shape("Modification error at Sheet!D24: answer=-11.7, output=11.7") == "sign_flip"
    assert (
        value_shape(
            "Regression error at Ex 1 - LBO!C36: "
            "answer=='Ex 10 - Balance Sheet'!D8:D8/C7, "
            "output=='Ex 10 - Balance Sheet'!D8/C7"
        )
        == "formula_text"
    )


def test_briefing_names_the_grid() -> None:
    text = (CATALOG / "BRIEFING.md").read_text(encoding="utf-8")
    for token in (
        # Mechanism collapse (surface.yaml's `mechanisms` block), not the raw pattern ids --
        # the briefing groups by mechanism now, which is the point of the collapse.
        "identity-choice",
        "run-boundary",
        "representative-selection",
        "error-token-policy",
        # The gate result the briefing exists to report, and the golden-safety invariant.
        "d-02-05-d7",
        "agent_scan",
        "Do not open goldens",
    ):
        assert token in text
