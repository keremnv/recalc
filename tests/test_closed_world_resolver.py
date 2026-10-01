"""Unit tests for closed-world resolver eligibility and scoring."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from closed_world_resolver import (  # noqa: E402
    KEEP_ALL_TOKEN,
    baseline_keep_all,
    classify_eligibility,
    classify_output,
    formula_synthesis_leakage,
    gold_compatible_ids,
    packet_callable,
    validate_resolution,
)


def _packet() -> dict:
    return {
        "obligation_id": "O1",
        "fields": {
            "locus": "Balance Sheet Schedules",
            "subject": "Accounts Receivable",
            "scope": ["for 2026E"],
            "source_relation": "percentage of Revenue",
            "occupancy_filter": None,
        },
        "locus": [{"sheet_id": "sheet:s00", "title": "Balance Sheet Schedules", "rules": ["exact_norm"]}],
        "subject": [
            {
                "id": "text:s00:r2:c1",
                "cell_id": "cell:s00:r2:c1",
                "row_id": "row:s00:r2",
                "col_id": "col:s00:c1",
                "sheet_id": "sheet:s00",
                "text": "Accounts Receivable",
                "rules": ["exact_norm"],
            },
            {
                "id": "text:s00:r3:c1",
                "cell_id": "cell:s00:r3:c1",
                "row_id": "row:s00:r3",
                "col_id": "col:s00:c1",
                "sheet_id": "sheet:s00",
                "text": "Total WC",
                "rules": ["jaccard"],
            },
        ],
        "scope": [
            {
                "id": "tcoord:s00:c:2",
                "cell_id": "cell:s00:r1:c2",
                "col_id": "col:s00:c2",
                "row_id": "row:s00:r1",
                "sheet_id": "sheet:s00",
                "axis": "column",
                "period": {"year": 2026},
            }
        ],
        "source": [
            {
                "id": "text:s00:r4:c1",
                "cell_id": "cell:s00:r4:c1",
                "row_id": "row:s00:r4",
                "col_id": "col:s00:c1",
                "sheet_id": "sheet:s00",
                "text": "Revenue",
                "rules": ["exact_norm"],
            }
        ],
        "target_cell_ids": ["cell:s00:r2:c2", "cell:s00:r3:c2"],
        "formula_class_facts": [],
        "dependency_facts": [],
        "counts": {},
    }


def test_invented_entity_is_invalid() -> None:
    packet = _packet()
    fake = {
        "locus": {"status": "RESOLVED", "candidate_ids": ["sheet:Tax Assumptions"], "evidence_ids": []},
        "subject": {"status": "UNRESOLVED", "candidate_ids": [], "evidence_ids": []},
        "scope": {"status": "UNRESOLVED", "candidate_ids": [], "evidence_ids": []},
        "source_relation_arguments": {"status": "UNRESOLVED", "candidate_ids": [], "evidence_ids": []},
        "target_region": {"status": "UNRESOLVED", "candidate_ids": [], "evidence_ids": []},
    }
    checked = validate_resolution(fake, packet)
    assert "sheet:Tax Assumptions" in checked["invalid"]
    assert checked["invalid_entity_reference"] is True
    assert checked["fields"]["locus"]["status"] == "UNRESOLVED"


def test_keep_all_token_expands() -> None:
    packet = _packet()
    payload = {
        "subject": {"status": "AMBIGUOUS", "candidate_ids": [KEEP_ALL_TOKEN], "evidence_ids": []},
    }
    checked = validate_resolution(payload, packet)
    assert set(checked["fields"]["subject"]["candidate_ids"]) == {
        "text:s00:r2:c1",
        "text:s00:r3:c1",
    }


def test_false_elimination_and_safe_reduction() -> None:
    gold = {"text:s00:r2:c1", "row:s00:r2"}
    dropped = classify_output(
        input_ids=["text:s00:r2:c1", "text:s00:r3:c1"],
        output_ids=["text:s00:r3:c1"],
        gold_ids=gold,
        coambiguous_ids={"text:s00:r2:c1"},
        status="RESOLVED",
        invalid=False,
    )
    assert dropped["false_elimination"] is True
    assert dropped["category"] == "WRONG_UNIQUE"
    kept = classify_output(
        input_ids=["text:s00:r2:c1", "text:s00:r3:c1"],
        output_ids=["text:s00:r2:c1"],
        gold_ids=gold,
        coambiguous_ids={"text:s00:r2:c1"},
        status="RESOLVED",
        invalid=False,
    )
    assert kept["false_elimination"] is False
    assert kept["safe_reduction"] is True
    assert kept["category"] == "CORRECT_UNIQUE"
    abstain = classify_output(
        input_ids=["text:s00:r2:c1", "text:s00:r3:c1"],
        output_ids=[],
        gold_ids=gold,
        coambiguous_ids={"text:s00:r2:c1"},
        status="UNRESOLVED",
        invalid=False,
    )
    assert abstain["false_elimination"] is False
    assert abstain["category"] == "UNRESOLVED_SAFE"


def test_keep_all_baseline_never_false_eliminates() -> None:
    packet = _packet()
    input_ids = {
        "locus": ["sheet:s00"],
        "subject": ["text:s00:r2:c1", "text:s00:r3:c1"],
        "scope": ["tcoord:s00:c:2"],
        "source_relation_arguments": ["text:s00:r4:c1"],
        "target_region": ["cell:s00:r2:c2", "cell:s00:r3:c2"],
    }
    checked = baseline_keep_all(packet, input_ids)
    gold = {"text:s00:r2:c1"}
    classified = classify_output(
        input_ids=input_ids["subject"],
        output_ids=checked["fields"]["subject"]["candidate_ids"],
        gold_ids=gold,
        coambiguous_ids=gold,
        status=checked["fields"]["subject"]["status"],
        invalid=False,
    )
    assert classified["false_elimination"] is False
    assert classified["safe_reduction"] is False
    assert classified["category"] == "NO_REDUCTION_SAFE"


def test_unparsed_scope_is_not_eligible() -> None:
    packet = _packet()
    ob = {
        "locus": {"text": "Balance Sheet Schedules"},
        "subject": {"text": "Accounts Receivable"},
        "scope": [{"text": "for the same timeframe"}],
        "source_relation": {"text": "percentage of Revenue"},
    }
    gold_ents = [
        {
            "sheet_id": "sheet:s00",
            "cell_id": "cell:s00:r2:c2",
            "row_id": "row:s00:r2",
            "col_id": "col:s00:c2",
        }
    ]
    elig = classify_eligibility(packet, ob, gold_ents, ref_cells={"cell:s00:r4:c2"})
    assert elig["scope"]["status"] == "TASK_SCOPE_UNPARSED"
    assert elig["subject"]["status"] == "ELIGIBLE"
    assert elig["target_region"]["status"] == "ELIGIBLE"
    assert packet_callable(elig) is True
    assert "text:s00:r2:c1" in elig["subject"]["gold_ids"]


def test_upstream_missing_when_gold_absent() -> None:
    packet = _packet()
    ob = {
        "locus": {"text": "Balance Sheet Schedules"},
        "subject": {"text": "Accounts Receivable"},
        "scope": [{"text": "for 2026E"}],
        "source_relation": None,
    }
    gold_ents = [
        {
            "sheet_id": "sheet:s00",
            "cell_id": "cell:s00:r9:c9",
            "row_id": "row:s00:r9",
            "col_id": "col:s00:c9",
        }
    ]
    elig = classify_eligibility(packet, ob, gold_ents)
    assert elig["subject"]["status"] == "UPSTREAM_MISSING"
    assert elig["target_region"]["status"] == "UPSTREAM_MISSING"
    assert elig["locus"]["status"] == "ELIGIBLE"


def test_formula_leak_detector() -> None:
    assert formula_synthesis_leakage("maybe =C22-C48 later") is True
    assert formula_synthesis_leakage("no formulas here") is False


def test_gold_compatible_source_uses_refs() -> None:
    packet = _packet()
    gold_ents = [
        {
            "sheet_id": "sheet:s00",
            "cell_id": "cell:s00:r2:c2",
            "row_id": "row:s00:r2",
            "col_id": "col:s00:c2",
        }
    ]
    ids = gold_compatible_ids(packet, "source_relation_arguments", gold_ents, ref_cells={"cell:s00:r4:c2"})
    assert "text:s00:r4:c1" in ids
