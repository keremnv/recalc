import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
import staged_synthesis_probe as sp


def test_gold_parser_preserves_nested_pairing_and_precedence():
    ast = sp.gold_ast("=C62*C63+C64*C65")
    assert ast == (
        "ADD",
        (("MUL", (("REF", "C62"), ("REF", "C63"))),
         ("MUL", (("REF", "C64"), ("REF", "C65")))),
    )


def test_f1_sketch_contains_no_workbook_reference():
    ast, err = sp.normalize_ast(
        {"op": "DIV", "args": [
            {"op": "MUL", "args": [
                {"op": "REF_HOLE", "name": "ARG1", "type": "SCALAR"},
                {"op": "REF_HOLE", "name": "ARG2", "type": "SCALAR"},
            ]},
            {"op": "CONST", "value": 12},
        ]},
        "F1",
    )
    assert err is None
    assert sp.ast_holes(ast) == ["ARG1", "ARG2"]
    assert not sp.collect_refs(ast)


def test_f2_rejects_entity_outside_persisted_operand_set():
    ast, err = sp.normalize_ast(
        {"op": "ADD", "args": [
            {"op": "REF", "id": "cell:a"},
            {"op": "REF", "id": "cell:b"},
        ]},
        "F2",
        {"cell:a"},
    )
    assert ast is None and err == "INVALID_ENTITY_ID"


def test_abstract_model_structure_matches_gold_structure():
    gold = sp.gold_ast("=C66*C67/12")
    model, err = sp.normalize_ast(
        {"op": "DIV", "args": [
            {"op": "MUL", "args": [
                {"op": "REF", "id": "cell:a"},
                {"op": "REF", "id": "cell:b"},
            ]},
            {"op": "CONST", "value": 12},
        ]},
        "F2",
        {"cell:a", "cell:b"},
    )
    assert err is None
    assert sp.abstract(model) == sp.abstract(gold)
