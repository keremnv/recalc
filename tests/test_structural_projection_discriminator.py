from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))

import structural_projection_discriminator as probe  # noqa: E402


def test_json_extract_strips_fences_only() -> None:
    parsed, ok = probe.extract_json('```json\n{"sheet":"A","ranges":[],"evidence":[]}\n```')
    assert ok is True
    assert parsed["sheet"] == "A"
    parsed, ok = probe.extract_json("not json {")
    assert ok is False
    assert parsed is None
    parsed, ok = probe.extract_json('prefix {"sheet":"A"} suffix')
    assert ok is False


def test_o7_freeze_is_gold_blind_and_isolated(tmp_path: Path) -> None:
    probe.activate_family("spark")
    frozen = probe.freeze_o7(tmp_path)
    control = frozen["payloads"]["CONTROL"]["user"]
    treatment = frozen["payloads"]["TREATMENT"]["user"]
    block = frozen["compiled_block"]
    assert "calc_query" not in control
    assert "calc_query" not in treatment
    assert block not in control
    assert block in treatment
    assert control == probe.render_user(frozen["packet"], None)
    assert treatment == probe.render_user(frozen["packet"], block)
    assert frozen["canonical_diff"]["raw_facts_equal"] is True
    assert frozen["canonical_diff"]["gold_used_in_payloads"] is False
    assert frozen["source"]["gold_loaded"] is False
    assert "O29:DI31" not in block
    lowered = block.casefold()
    assert "should edit" not in lowered
    assert "intended cells" not in lowered
    assert "correct" not in lowered
    assert "gold" not in lowered
    runs = {run["parent"]["text"]: run["member_cells"][0] + ":" + run["member_cells"][-1] for run in frozen["runs"]}
    assert runs["Portfolio Building MoM"] == "B11:B13"
    assert runs["Portfolio Building Cumulative"] == "B17:B19"
    assert runs["Ticket Size per Portfolio"] == "B23:B25"
    assert runs["Total Fund Raised"] == "B29:B31"
    assert frozen["axis"]["start"]["address"]
    assert frozen["axis"]["end"]["address"]
    assert frozen["axis"]["start"]["label"] == "Apr-25"
    assert frozen["axis"]["end"]["label"] == "Jun-33"
    assert frozen["payloads"]["CONTROL"]["request_body"]["model"] == probe.DECLARED_MODEL
    assert frozen["spec"]["model"]["request_model"] == probe.REQUEST_MODEL
    assert "reasoning" not in frozen["payloads"]["CONTROL"]["request_body"]
    assert frozen["payloads"]["CONTROL"]["request_body"]["temperature"] == 0
    assert frozen["spec"]["no_calc_query"] is True
    gold_path = str(tmp_path)
    assert "gold_target" not in json.dumps(frozen["packet"])
    assert probe.AUTHORITY_PATH.exists()  # gold exists on disk but was not loaded into payloads
    assert "Workings Cost Sheet!O29" not in control
    assert "Workings Cost Sheet!O29" not in treatment


def test_sheet_id_aliases_canonicalize_to_the_packet_sheet() -> None:
    spine = {
        "sheets": [{"title": "Workings Cost Sheet", "id": "sheet:s04"}],
        "title_to_index": {"Workings Cost Sheet": 4},
    }
    parsed = {"sheet": "s04", "ranges": [{"start": "O29", "end": "O29"}]}
    cells, meta = probe.predicted_cell_ids(parsed, "Workings Cost Sheet", spine)
    assert cells == {"cell:s04:r29:c15"}
    assert meta["rows"] == [29]
    assert probe.pair_order(1) == ["CONTROL", "TREATMENT"]
    assert probe.pair_order(2) == ["TREATMENT", "CONTROL"]
    assert probe.pair_order(3) == ["CONTROL", "TREATMENT"]
    assert probe.pair_order(4) == ["TREATMENT", "CONTROL"]


def test_o7_verdict_rules() -> None:
    def pair(**kwargs):
        base = {
            "usable": True,
            "control_exact": False,
            "treatment_exact": True,
            "strict_treatment_improvement": True,
            "strict_control_reversal": False,
            "precision_collapse": False,
            "control_f1": 0.1,
            "treatment_f1": 1.0,
        }
        base.update(kwargs)
        return base

    assert probe.verdict_o7([pair(repeat=i) for i in range(1, 5)]) == "STRUCTURAL_PROJECTION_CASHES_OUT"
    saturated = [pair(repeat=i, control_exact=True, treatment_exact=True, strict_treatment_improvement=False) for i in range(1, 5)]
    assert probe.verdict_o7(saturated) == "NO_HEADROOM_ON_O7"
    none = [pair(repeat=i, treatment_exact=False, strict_treatment_improvement=False, treatment_f1=0.1) for i in range(1, 5)]
    assert probe.verdict_o7(none) == "STRUCTURAL_PROJECTION_NO_GAIN"
    mixed = [
        pair(repeat=1),
        pair(repeat=2, treatment_exact=False, strict_treatment_improvement=False, strict_control_reversal=True, control_exact=True, treatment_f1=0.1, control_f1=1.0),
        pair(repeat=3),
        pair(repeat=4),
    ]
    assert probe.verdict_o7(mixed) == "STRUCTURAL_PROJECTION_MIXED"
    assert probe.verdict_o7([pair(repeat=1, usable=False) for _ in range(4)]) == "PROVIDER_CENSORED"


def test_glm_identity_uses_authoritative_reasoning_high() -> None:
    probe.activate_family("glm")
    try:
        body = probe.request_body("sys", "user")
        assert body["model"] == "z-ai/glm-5.3-flash"
        assert body["reasoning"] == {"effort": "high"}
        assert body["temperature"] == 0
        assert body["top_p"] == 1
        assert body["provider"] == {"allow_fallbacks": True, "require_parameters": True}
        assert probe.REQUEST_MODEL == "openrouter/z-ai/glm-5.3-flash"
    finally:
        probe.activate_family("spark")
    assert probe.DECLARED_MODEL == "meta/muse-spark-1.3-contributor"
    assert "reasoning" not in probe.request_body("sys", "user")

