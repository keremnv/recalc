"""Unit tests for ungrounded TASK → V1 obligation compilation evaluation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))

from task_obligation_compile import (  # noqa: E402
    PARSER_PROMPT,
    PARSER_SCHEMA,
    build_ungrounded_oracle,
    concat_texts,
    extract_json_object,
    is_boilerplate,
    match_obligations,
    normalize,
    normalize_prediction,
    score_task,
    span_in_task,
    workbook_like_inventions,
)
from task_obligation_compile_probe import GLM_MODEL, GPT_MODEL, MODELS  # noqa: E402
from task_obligation_shape import family_of  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model/dataset.json"
SHAPE = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-shape-probe/family_split.json"
)


def _instruction(task_id: str) -> str:
    by = {row["id"]: row["instruction"] for row in json.loads(DATA.read_text())}
    return by[task_id]


def _blob(obs: list[dict]) -> str:
    return " ".join(concat_texts(ob, ["provenance", "locus", "subject", "required_change", "scope", "source_relation", "condition", "result_property", "occupancy_filter"]) for ob in obs)


def test_frozen_prompt_has_no_benchmark_examples() -> None:
    lowered = PARSER_PROMPT.casefold()
    assert "spreadsheetbench" not in lowered
    assert "01_03" not in PARSER_PROMPT
    assert "working capital schedule" not in lowered
    assert "k104" not in lowered
    assert "financial_model" not in lowered
    assert "obligations" in PARSER_SCHEMA["required"]
    assert MODELS["glm"]["id"] == GLM_MODEL == "z-ai/glm-5.3-flash"
    assert MODELS["gpt"]["id"] == GPT_MODEL == "openai/gpt-5.6-sol"
    assert MODELS["glm"]["reasoning"] == "low"
    assert MODELS["gpt"]["reasoning"] == "medium"
    assert MODELS["glm"]["temperature"] == 0.0


def test_family_split_matches_frozen_probe() -> None:
    split = json.loads(SHAPE.read_text())
    assert split["discovery_families"] == ["01", "03", "06", "10", "11", "12", "13", "15", "17", "18"]
    assert split["validation_families"] == ["02", "04", "05", "09", "16"]
    assert split["held_out_families"] == ["07", "08", "14", "19", "20"]
    assert family_of("20_04") == "20"


def test_oracle_skips_boilerplate_and_is_task_text_only() -> None:
    text = _instruction("01_03")
    obs = build_ungrounded_oracle(text)
    assert obs
    assert not any(is_boilerplate(concat_texts(ob, ["provenance"])) for ob in obs)
    dump = json.dumps(obs)
    assert "Working Capital!M22" not in dump
    assert "K27" not in dump
    assert "=" not in dump or all("=" not in concat_texts(ob, ["source_relation"]) for ob in obs)


def test_oracle_01_03_keeps_three_wc_transformations_and_scopes() -> None:
    obs = build_ungrounded_oracle(_instruction("01_03"))
    blob = _blob(obs)
    recv = [ob for ob in obs if "Receivables" in concat_texts(ob, ["subject"])]
    total = [ob for ob in obs if "Total Working Capital" in concat_texts(ob, ["subject"])]
    current = [ob for ob in obs if "Current Assets" in concat_texts(ob, ["subject"])]
    assert recv and current and total
    assert any("Working Capital" in concat_texts(ob, ["locus"]) for ob in recv)
    assert any("2026E" in concat_texts(ob, ["scope"]) for ob in recv)
    assert any("all years" in concat_texts(ob, ["scope"]) for ob in total)
    assert "Revenue and Receivable Days" in blob
    assert total[0]["then_after"]
    assert current[0]["then_after"]


def test_oracle_known_spec_spans() -> None:
    cases = {
        "04_05": ["growing from 2013", "total growth rates", "forecast revenue"],
        "09_05": ["Other Long-Term Assets", "2014F"],
        "14_05": ["Total Revenue", "all products", "effective tax rate"],
        "20_04": ["days-based linkage", "Other Current Liabilities"],
        "08_01": ["30%", "nil tax", "PBT is negative", "70% bills discounting"],
        "17_03": ["percentage of Revenue", "Other Long-Term Assets"],
        "15_04": ["PBT", "EPS Growth", "not hardcoded"],
    }
    for task_id, needles in cases.items():
        blob = normalize(_blob(build_ungrounded_oracle(_instruction(task_id))))
        for needle in needles:
            assert normalize(needle) in blob, f"{task_id} missing {needle}"


def test_oracle_does_not_invent_workbook_targets() -> None:
    for task_id, banned in {
        "04_05": ["K12", "K27"],
        "09_05": ["K163", "L163"],
        "20_04": ["H41", "H30"],
        "14_05": ["J31", "SUM("],
        "08_01": ["AF66", "$C$8"],
        "17_03": ["K104", "365"],
        "15_04": ["Y39"],
    }.items():
        dump = json.dumps(build_ungrounded_oracle(_instruction(task_id)))
        for token in banned:
            assert token not in dump, f"{task_id} invented {token}"


def test_20_04_adj_fcff_not_split_on_abbreviation() -> None:
    obs = build_ungrounded_oracle(_instruction("20_04"))
    blob = _blob(obs)
    assert "Adj. FCFF" in blob or "adj. fcff" in normalize(blob)
    assert not any(concat_texts(ob, ["provenance"]).rstrip().endswith("Adj.") for ob in obs)


def test_matching_is_order_independent() -> None:
    oracle = build_ungrounded_oracle(_instruction("01_03"))
    reversed_pred = list(reversed(oracle))
    for i, row in enumerate(reversed_pred):
        row = dict(row)
        row["id"] = f"P{i+1}"
        reversed_pred[i] = row
    matched = match_obligations(oracle, reversed_pred)
    assert len(matched["pairs"]) == len(oracle)
    assert not matched["unmatched_oracle"]


def test_merged_and_omitted_errors() -> None:
    text = _instruction("01_03")
    oracle = build_ungrounded_oracle(text)
    merged = {
        "id": "P1",
        "provenance": [{"text": concat_texts(oracle[0], ["provenance"]) + " " + concat_texts(oracle[1], ["provenance"])}],
        "locus": oracle[0]["locus"],
        "subject": {"text": "Receivables Current Assets Total Working Capital"},
        "subject_interval": None,
        "required_change": oracle[0]["required_change"],
        "scope": oracle[0]["scope"] + oracle[2]["scope"] if len(oracle) > 2 else oracle[0]["scope"],
        "source_relation": None,
        "condition": None,
        "result_property": None,
        "then_after": [],
        "occupancy_filter": None,
    }
    scored = score_task(
        task_id="01_03",
        instruction=text,
        oracle=oracle,
        pred=[merged],
        parse_valid=True,
    )
    codes = {e["code"] for e in scored["errors"]}
    assert "OMITTED_CLAUSE" in codes
    assert scored["task_spec_preserved"] is False


def test_unsupported_inference_and_boilerplate_promotion() -> None:
    text = _instruction("09_05")
    oracle = build_ungrounded_oracle(text)
    pred = json.loads(json.dumps(oracle))
    pred.append(
        {
            "id": "PX",
            "provenance": [{"text": "Complete the financial model based on the provided assumptions."}],
            "locus": None,
            "subject": {"text": "complete the model"},
            "subject_interval": None,
            "required_change": {"text": "Complete"},
            "scope": [],
            "source_relation": {"text": "using Assumptions!K163"},
            "condition": None,
            "result_property": None,
            "then_after": [],
            "occupancy_filter": None,
        }
    )
    scored = score_task(
        task_id="09_05",
        instruction=text,
        oracle=oracle,
        pred=pred,
        parse_valid=True,
    )
    codes = {e["code"] for e in scored["errors"]}
    assert "SPURIOUS_OBLIGATION" in codes
    assert scored["boilerplate_as_obligation"] is True
    hits = workbook_like_inventions(pred, text)
    assert any("K163" in h or "Assumptions!K163" in h for h in hits)
    assert "O1" not in workbook_like_inventions(oracle, text)


def test_span_normalization_allows_dash_variants() -> None:
    task = "calculate Receivables for 2026E–2030E"
    assert span_in_task("2026E–2030E", task)["exact"] is True
    assert span_in_task("2026E-2030E", task)["normalized"] is True


def test_oracle_skips_aif_boilerplate_variant() -> None:
    obs = build_ungrounded_oracle(_instruction("05_01"))
    blob = " ".join(concat_texts(ob, ["provenance"]) for ob in obs)
    assert "Complete the AIF" not in blob
    assert "retained throughout the process" not in blob
    assert any("IRR" in concat_texts(ob, ["subject"]) or "IRR" in concat_texts(ob, ["provenance"]) for ob in obs)


def test_identity_parse_preserves_spec() -> None:
    text = _instruction("01_03")
    oracle = build_ungrounded_oracle(text)
    scored = score_task(
        task_id="01_03",
        instruction=text,
        oracle=oracle,
        pred=json.loads(json.dumps(oracle)),
        parse_valid=True,
    )
    assert scored["task_spec_preserved"] is True
    assert scored["workbook_like_hits"] == []
    assert scored["all_critical_requirements_preserved"] is True


def test_json_extractor_handles_fences() -> None:
    payload = extract_json_object('Sure.\n```json\n{"obligations": [{"id": "O1", "scope": []}]}\n```\n')
    assert payload and len(normalize_prediction(payload)) == 1
