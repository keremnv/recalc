from __future__ import annotations

import re

_A1_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<column_absolute>\$?)(?P<column>[A-Za-z]{1,3})"
    r"(?P<row_absolute>\$?)(?P<row>[1-9][0-9]*)(?![A-Za-z0-9_])"
)
_FORMULA_A1_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:(?P<sheet>\$?'(?:[^']|'')+'|\$?[A-Za-z_][A-Za-z0-9_]*)[.!])?"
    r"(?P<start>\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)"
    r"(?:\s*:\s*"
    r"(?:(?P<end_sheet>\$?'(?:[^']|'')+'|\$?[A-Za-z_][A-Za-z0-9_]*)[.!])?"
    r"(?P<end>\$?[A-Za-z]{1,3}\$?[1-9][0-9]*))?"
    r"(?![A-Za-z0-9_])"
)


def _column_number(name: str) -> int:
    number = 0
    for character in name.upper():
        number = number * 26 + ord(character) - ord("A") + 1
    return number


def _column_name(number: int) -> str:
    if number < 1:
        raise ValueError("Formula translation moved a reference before column A")
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _translate_unquoted(segment: str, column_offset: int, row_offset: int) -> str:
    def replace(match: re.Match[str]) -> str:
        # LOG10 and a few other functions look like cell references lexically.
        if match.end() < len(segment) and segment[match.end()] == "(":
            return match.group(0)
        column = match.group("column")
        row = int(match.group("row"))
        if not match.group("column_absolute"):
            column = _column_name(_column_number(column) + column_offset)
        if not match.group("row_absolute"):
            row += row_offset
            if row < 1:
                raise ValueError("Formula translation moved a reference before row 1")
        return (
            f"{match.group('column_absolute')}{column}"
            f"{match.group('row_absolute')}{row}"
        )

    return _A1_REFERENCE.sub(replace, segment)


def _shape_unquoted(segment: str) -> str:
    def replace(match: re.Match[str]) -> str:
        # LOG10 and a few other functions look like cell references lexically.
        if match.end() < len(segment) and segment[match.end()] == "(":
            return match.group(0)
        return "<REF>"

    return _A1_REFERENCE.sub(replace, segment)


def translate_a1_formula(formula: str, *, column_offset: int, row_offset: int) -> str:
    """Translate relative A1 references as Calc autofill would.

    Double-quoted string literals and single-quoted sheet identifiers are copied verbatim.
    """
    translated: list[str] = []
    start = 0
    index = 0
    while index < len(formula):
        quote = formula[index]
        if quote not in {'"', "'"}:
            index += 1
            continue
        translated.append(_translate_unquoted(formula[start:index], column_offset, row_offset))
        end = index + 1
        while end < len(formula):
            if formula[end] == quote:
                if end + 1 < len(formula) and formula[end + 1] == quote:
                    end += 2
                    continue
                end += 1
                break
            end += 1
        translated.append(formula[index:end])
        start = end
        index = end
    translated.append(_translate_unquoted(formula[start:], column_offset, row_offset))
    return "".join(translated)


def formula_a1_shape(formula: str) -> str:
    """Replace A1 references with placeholders while preserving formula structure."""
    shaped: list[str] = []
    start = 0
    index = 0
    while index < len(formula):
        quote = formula[index]
        if quote not in {'"', "'"}:
            index += 1
            continue
        shaped.append(_shape_unquoted(formula[start:index]))
        end = index + 1
        while end < len(formula):
            if formula[end] == quote:
                if end + 1 < len(formula) and formula[end + 1] == quote:
                    end += 2
                    continue
                end += 1
                break
            end += 1
        shaped.append(formula[index:end])
        start = end
        index = end
    shaped.append(_shape_unquoted(formula[start:]))
    return "".join(shaped)


def _sheet_name(reference: str | None) -> str | None:
    if reference is None:
        return None
    reference = reference.removeprefix("$")
    if reference.startswith("'") and reference.endswith("'"):
        return reference[1:-1].replace("''", "'")
    return reference


def formula_a1_references(formula: str) -> list[tuple[str | None, str, str | None]]:
    """Return explicit A1 cell/range references from an Excel or Calc formula.

    Each tuple is ``(sheet, start, end)``. ``sheet`` is ``None`` for a same-sheet
    reference and ``end`` is ``None`` for a single cell. Double-quoted string
    literals are ignored. This is a lexical dependency aid, not a full formula
    evaluator; named ranges and structured references are intentionally omitted.
    """
    unquoted: list[str] = []
    index = 0
    while index < len(formula):
        if formula[index] != '"':
            unquoted.append(formula[index])
            index += 1
            continue
        unquoted.append(" ")
        index += 1
        while index < len(formula):
            if formula[index] == '"':
                if index + 1 < len(formula) and formula[index + 1] == '"':
                    index += 2
                    continue
                index += 1
                break
            index += 1

    source = "".join(unquoted)
    references = []
    for match in _FORMULA_A1_REFERENCE.finditer(source):
        if match.end() < len(source) and source[match.end()] == "(":
            continue
        sheet = _sheet_name(match.group("sheet"))
        end_sheet = _sheet_name(match.group("end_sheet"))
        if end_sheet is not None and sheet is not None and end_sheet != sheet:
            continue
        start = match.group("start").replace("$", "").upper()
        end = match.group("end")
        references.append((sheet or end_sheet, start, end.replace("$", "").upper() if end else None))
    return references


def normalize_formula_argument_separators(formula: str) -> str:
    """Normalize Excel-style function-argument commas to Calc semicolons.

    Commas in quoted strings, quoted sheet names, and array constants are
    preserved. LibreOffice's UNO Formula property accepts comma-separated
    formulas inconsistently; IF formulas can silently gain an invalid fourth
    argument during XLSX export unless function arguments use semicolons.
    """
    normalized: list[str] = []
    quote: str | None = None
    parentheses = 0
    braces = 0
    index = 0
    while index < len(formula):
        character = formula[index]
        if quote is not None:
            normalized.append(character)
            if character == quote:
                if index + 1 < len(formula) and formula[index + 1] == quote:
                    normalized.append(formula[index + 1])
                    index += 1
                else:
                    quote = None
        elif character in {'"', "'"}:
            quote = character
            normalized.append(character)
        elif character == "(":
            parentheses += 1
            normalized.append(character)
        elif character == ")":
            parentheses = max(0, parentheses - 1)
            normalized.append(character)
        elif character == "{":
            braces += 1
            normalized.append(character)
        elif character == "}":
            braces = max(0, braces - 1)
            normalized.append(character)
        elif character == "," and parentheses and not braces:
            normalized.append(";")
        else:
            normalized.append(character)
        index += 1
    return "".join(normalized)
