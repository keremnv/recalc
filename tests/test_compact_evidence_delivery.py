import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import compact_evidence as encoding  # noqa: E402
import matched_compiled_treatment as treatment  # noqa: E402
from experiment_config import AUTHORITATIVE_EXPERIMENT_CONFIG  # noqa: E402


def sample_evidence():
    return {
        "entity_ids": ["cell:s01:r47:c3", "cell:s01:r48:c3", "sheet:s01", "wb:0"],
        "entities": {
            "cells": {
                "columns": ["cell_id", "display_value", "kind", "raw_value", "sheet_id"],
                "rows": [
                    ["cell:s01:r47:c3", "0.11", "numeric", "0.11", "sheet:s01"],
                    ["cell:s01:r48:c3", "0.25", "numeric", "0.25", "sheet:s01"],
                    ["cell:s01:r49:c3", None, "blank", None, "sheet:s01"],
                    ["cell:s01:r49:c4", None, "blank", None, "sheet:s01"],
                ],
            },
            "sheets": {
                "columns": ["name", "sheet_id"],
                "rows": [["DCF", "sheet:s01"]],
            },
        },
        "relations": {
            "point_references": {"columns": ["formula_id", "referenced_cell_id"], "rows": []},
        },
    }


def test_authoritative_live_reasoning_is_high_not_max():
    assert AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning == "high"
    assert AUTHORITATIVE_EXPERIMENT_CONFIG.model == "z-ai/glm-5.3-flash"
    body = treatment.request_body("system", "user")
    assert body["reasoning"] == {"effort": "high"}
    assert body["model"] == "z-ai/glm-5.3-flash"
    with pytest.raises(RuntimeError, match="REQUEST_CONFIGURATION_OVERRIDE_REJECTED"):
        treatment.configure_runtime(reasoning="max")


def test_compact_encoding_is_lossless_and_smaller():
    evidence = sample_evidence()
    compact = encoding.encode_evidence(evidence)
    assert compact["encoding"] == "columnar_dict_v1"
    assert "legend" in compact
    assert encoding.factual_diff(evidence, compact)["equal"]
    assert encoding.canonical_hash(evidence) == encoding.canonical_hash(compact)
    decoded = encoding.decode_evidence(compact)
    assert encoding.cell_fact(decoded, "cell:s01:r47:c3")["raw_value"] == "0.11"
    assert encoding.cell_fact(compact, "cell:s01:r48:c3")["display_value"] == "0.25"


def test_canonicalizer_detects_omitted_and_added_facts():
    evidence = sample_evidence()
    compact = encoding.encode_evidence(evidence)
    omitted = encoding.decode_evidence(compact)
    omitted["entities"]["cells"]["rows"] = omitted["entities"]["cells"]["rows"][:-1]
    added = encoding.decode_evidence(compact)
    added["entities"]["cells"]["rows"].append(["cell:s01:r51:c3", "0.15", "numeric", "0.15", "sheet:s01"])
    assert not encoding.factual_diff(evidence, omitted)["equal"]
    assert not encoding.factual_diff(evidence, added)["equal"]
    mutated = encoding.decode_evidence(compact)
    for row in mutated["entities"]["cells"]["rows"]:
        if row[0] == "cell:s01:r47:c3":
            row[3] = "0.12"
    assert not encoding.factual_diff(evidence, mutated)["equal"]


def test_repetitive_tables_shrink_under_columnar_dictionary_encoding():
    rows = [[f"cell:s01:r{i}:c3", None, "blank", None, "sheet:s01"] for i in range(1, 401)]
    evidence = {
        "entity_ids": [row[0] for row in rows] + ["sheet:s01"],
        "entities": {"cells": {"columns": ["cell_id", "display_value", "kind", "raw_value", "sheet_id"], "rows": rows}},
        "relations": {},
    }
    compact = encoding.encode_evidence(evidence)
    assert encoding.factual_diff(evidence, compact)["equal"]
    assert encoding.byte_size(compact) < encoding.byte_size(evidence)


def test_empty_tables_and_entity_ids_without_rows_are_preserved():
    evidence = sample_evidence()
    compact = encoding.encode_evidence(evidence)
    decoded = encoding.decode_evidence(compact)
    assert decoded["relations"]["point_references"]["rows"] == []
    assert "wb:0" in decoded["entity_ids"]
    assert encoding.canonical_facts(evidence)["entity_id_set"] == encoding.canonical_facts(compact)["entity_id_set"]
