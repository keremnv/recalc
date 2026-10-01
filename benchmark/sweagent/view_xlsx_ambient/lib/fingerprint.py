"""Conservative location-relative formula fingerprints.

Supported A1 geometry is rewritten as C[Δ]R[Δ] (or $abs). Anything the lexer cannot
faithfully canonicalize becomes an opaque singleton identity: hash(formula + sheet +
address). Identical unsupported text at two cells is not an equivalence class.
Opaque identities never collide with a canonical fingerprint. False structural
equivalence is forbidden; refusing to canonicalize is allowed.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_A1 = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:(?P<sheet>\$?'(?:[^']|'')+'|\$?[A-Za-z_][A-Za-z0-9_]*)[.!])?"
    r"(?P<start_col_abs>\$?)(?P<start_col>[A-Za-z]{1,3})"
    r"(?P<start_row_abs>\$?)(?P<start_row>[1-9][0-9]*)"
    r"(?:\s*:\s*"
    r"(?:(?P<end_sheet>\$?'(?:[^']|'')+'|\$?[A-Za-z_][A-Za-z0-9_]*)[.!])?"
    r"(?P<end_col_abs>\$?)(?P<end_col>[A-Za-z]{1,3})"
    r"(?P<end_row_abs>\$?)(?P<end_row>[1-9][0-9]*))?"
    r"(?![A-Za-z0-9_])"
)
_STRUCTURED = re.compile(
    r"(?:[A-Za-z_][\w.]*\[|#This|#All|#Data|#Headers|#Totals|\[@)"
)
_THREE_D = re.compile(
    r"(?:'(?:[^']|'')+'\s*:\s*'(?:[^']|'')+'|[A-Za-z_][\w.]*\s*:\s*[A-Za-z_][\w.]*)\s*!"
)
_EXTERNAL = re.compile(r"\[\d+\]")
_DYNAMIC = re.compile(r"(?i)(?<![A-Za-z0-9_])(INDIRECT|OFFSET)\s*\(")
_R1C1 = re.compile(
    r"(?i)(?<![A-Za-z0-9_])R(?:\[-?\d+\]|\d+)C(?:\[-?\d+\]|\d+)(?![A-Za-z0-9_])"
)
_IDENT = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_.]*)(?![A-Za-z0-9_])")
_ALLOWED_IDENTS = frozenset(
    {
        "TRUE",
        "FALSE",
        "NULL",
        "T",
        "F",
    }
)
_OPAQUE_PREFIX = "OPAQUE:"


@dataclass(frozen=True)
class Fingerprint:
    text: str
    opaque: bool
    reason: str | None = None

    @property
    def eq_id(self) -> str:
        return hashlib.sha1(self.text.encode("utf-8")).hexdigest()[:10]


def column_number(name: str) -> int:
    number = 0
    for character in name.upper():
        number = number * 26 + ord(character) - ord("A") + 1
    return number


def column_letter(number: int) -> str:
    if number < 1:
        raise ValueError("column out of range")
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def a1_address(col: int, row: int) -> str:
    return f"{column_letter(col)}{row}"


def formula_text(value: object) -> str | None:
    if isinstance(value, str) and value.startswith("="):
        return value
    text = getattr(value, "text", None)
    if isinstance(text, str) and text.startswith("="):
        return text
    return None


def _quote_spans(formula: str) -> list[tuple[int, int, str]]:
    """Return (start, end, kind) for double-quoted strings and single-quoted sheets."""
    spans: list[tuple[int, int, str]] = []
    index = 0
    while index < len(formula):
        quote = formula[index]
        if quote not in {'"', "'"}:
            index += 1
            continue
        end = index + 1
        while end < len(formula):
            if formula[end] == quote:
                if end + 1 < len(formula) and formula[end + 1] == quote:
                    end += 2
                    continue
                end += 1
                break
            end += 1
        kind = "string" if quote == '"' else "sheet"
        spans.append((index, end, kind))
        index = end
    return spans


def _unquoted_segments(formula: str) -> list[str]:
    spans = _quote_spans(formula)
    if not spans:
        return [formula]
    parts: list[str] = []
    start = 0
    for begin, end, _kind in spans:
        parts.append(formula[start:begin])
        start = end
    parts.append(formula[start:])
    return parts


def _quoted_sheet_bodies(formula: str) -> list[str]:
    return [formula[begin + 1 : end - 1] for begin, end, kind in _quote_spans(formula) if kind == "sheet"]


def _coordinate(col_abs: str, col: str, row_abs: str, row: str, origin_col: int, origin_row: int) -> str:
    c = column_number(col)
    r = int(row)
    if col_abs:
        col_part = f"${col.upper()}"
    else:
        col_part = f"C[{c - origin_col}]"
    if row_abs:
        row_part = f"${r}"
    else:
        row_part = f"R[{r - origin_row}]"
    return col_part + row_part


def _canonicalize_segment(segment: str, origin_col: int, origin_row: int) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.end() < len(segment) and segment[match.end()] == "(":
            return match.group(0)
        start = _coordinate(
            match.group("start_col_abs") or "",
            match.group("start_col"),
            match.group("start_row_abs") or "",
            match.group("start_row"),
            origin_col,
            origin_row,
        )
        sheet = match.group("sheet") or ""
        end_col = match.group("end_col")
        if not end_col:
            return f"{sheet}{start}" if sheet else start
        end = _coordinate(
            match.group("end_col_abs") or "",
            end_col,
            match.group("end_row_abs") or "",
            match.group("end_row"),
            origin_col,
            origin_row,
        )
        end_sheet = match.group("end_sheet") or ""
        if end_sheet:
            return f"{sheet}{start}:{end_sheet}{end}"
        return f"{sheet}{start}:{end}"

    return _A1.sub(replace, segment)


def _unsupported_reason(formula: str) -> str | None:
    if _STRUCTURED.search(formula):
        return "structured_ref"
    if _THREE_D.search(formula):
        return "three_d"
    if _EXTERNAL.search(formula):
        return "external"
    if _DYNAMIC.search(formula):
        return "dynamic_ref"
    if _R1C1.search(formula):
        return "r1c1"
    for body in _quoted_sheet_bodies(formula):
        if ":" in body.replace("''", ""):
            return "three_d"
    for segment in _unquoted_segments(formula):
        if _has_named_range(segment):
            return "named_range"
        if _has_three_d_unquoted(segment):
            return "three_d"
    return None


def _has_three_d_unquoted(segment: str) -> bool:
    for match in _A1.finditer(segment):
        start_sheet = match.group("sheet")
        end_sheet = match.group("end_sheet")
        if start_sheet and end_sheet and start_sheet.removeprefix("$") != end_sheet.removeprefix("$"):
            return True
    return False


def _has_named_range(segment: str) -> bool:
    stripped = segment
    # Blank out A1 references (except function-like LOG10) before hunting leftover names.
    pieces: list[str] = []
    start = 0
    for match in _A1.finditer(segment):
        if match.end() < len(segment) and segment[match.end()] == "(":
            continue
        pieces.append(segment[start : match.start()])
        pieces.append(" ")
        start = match.end()
    pieces.append(segment[start:])
    stripped = "".join(pieces)
    for match in _IDENT.finditer(stripped):
        ident = match.group(1)
        after = match.end()
        if after < len(stripped) and stripped[after] == "(":
            continue
        if ident.upper() in _ALLOWED_IDENTS:
            continue
        return True
    return False


def opaque_fingerprint(
    formula: str,
    reason: str,
    *,
    sheet: str,
    col: int,
    row: int,
) -> Fingerprint:
    """Singleton identity. Same raw text at two addresses is not equivalence."""
    location = f"{sheet}!{a1_address(col, row)}"
    digest = hashlib.sha1(f"{formula}\n{location}".encode("utf-8")).hexdigest()
    return Fingerprint(text=f"{_OPAQUE_PREFIX}{digest}", opaque=True, reason=reason)


def relative_fingerprint(
    formula: str,
    origin_col: int,
    origin_row: int,
    *,
    sheet: str = "",
) -> Fingerprint:
    """Location-relative identity, or an opaque singleton that cannot false-merge."""
    reason = _unsupported_reason(formula)
    if reason:
        return opaque_fingerprint(
            formula, reason, sheet=sheet, col=origin_col, row=origin_row
        )
    try:
        spans = _quote_spans(formula)
        if not spans:
            text = _canonicalize_segment(formula, origin_col, origin_row)
        else:
            parts: list[str] = []
            start = 0
            for begin, end, _kind in spans:
                parts.append(_canonicalize_segment(formula[start:begin], origin_col, origin_row))
                parts.append(formula[begin:end])
                start = end
            parts.append(_canonicalize_segment(formula[start:], origin_col, origin_row))
            text = "".join(parts)
    except Exception:
        return opaque_fingerprint(
            formula, "unparsed", sheet=sheet, col=origin_col, row=origin_row
        )
    return Fingerprint(text=text, opaque=False, reason=None)
