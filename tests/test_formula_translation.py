from librecalc_mcp.domain.formulas import (
    formula_a1_references,
    formula_a1_shape,
    normalize_formula_argument_separators,
    translate_a1_formula,
)


def test_formula_a1_references_supports_excel_and_calc_syntax() -> None:
    assert formula_a1_references(
        "=G4/G5+SUM(H5:H7)+$'Consolidated P&L'.H9+Forecast!$E$50+\"A1\"+LOG10(B2)"
    ) == [
        (None, "G4", None),
        (None, "G5", None),
        (None, "H5", "H7"),
        ("Consolidated P&L", "H9", None),
        ("Forecast", "E50", None),
        (None, "B2", None),
    ]


def test_translate_a1_formula_respects_absolute_references() -> None:
    assert (
        translate_a1_formula("=A2-B$3+$C4+$D$5", column_offset=2, row_offset=1)
        == "=C3-D$3+$C5+$D$5"
    )


def test_translate_a1_formula_handles_ranges_sheet_names_and_strings() -> None:
    formula = '=SUM(\'FY25 Model\'.A1:B$2)+IF(C3="A1",D4,LOG10(E5))'

    assert translate_a1_formula(formula, column_offset=1, row_offset=2) == (
        '=SUM(\'FY25 Model\'.B3:C$2)+IF(D5="A1",E6,LOG10(F7))'
    )


def test_translate_a1_formula_accepts_excel_sheet_separator() -> None:
    assert translate_a1_formula("='Debt Schedule'!C8", column_offset=3, row_offset=4) == (
        "='Debt Schedule'!F12"
    )


def test_formula_a1_shape_preserves_structure_sheet_names_strings_and_functions() -> None:
    assert formula_a1_shape("='3-month Term SOFR'!P27+LOG10(A1)+\"B2\"") == (
        "='3-month Term SOFR'!<REF>+LOG10(<REF>)+\"B2\""
    )


def test_normalize_formula_argument_separators_preserves_literals_and_arrays() -> None:
    formula = '=IF(C5="Last, First",SUM(\'A,B\'.A1,B1),IRR({1,-2,-3}))'

    assert normalize_formula_argument_separators(formula) == (
        '=IF(C5="Last, First";SUM(\'A,B\'.A1;B1);IRR({1,-2,-3}))'
    )
