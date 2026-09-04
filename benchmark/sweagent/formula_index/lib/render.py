"""Render index queries under the control observation cap."""
from __future__ import annotations

from fingerprint import a1_address
from workbook import EquivalenceClass

OBSERVATION_LIMIT = 10_000


def _class_identity_lines(record: EquivalenceClass, *, formula_limit: int | None = None) -> str:
    formula = record.exemplar_formula
    if formula_limit is not None and len(formula) > formula_limit:
        formula = formula[: formula_limit - 1] + "…"
    source = f"{record.exemplar_sheet}!{a1_address(record.exemplar_col, record.exemplar_row)}"
    extra = " opaque=true" if record.opaque else ""
    reason = f" reason={record.reason}" if record.reason else ""
    return (
        f"eq {record.eq_id} n={record.n} sheets={record.sheets}{extra}{reason}\n"
        f"  source {source} {formula}\n"
    )


def _class_full(record: EquivalenceClass) -> str:
    members = record.member_text()
    body = _class_identity_lines(record)
    if members:
        body += f"  members {members}\n"
    return body


def render_classes(
    *,
    kind: str,
    header_fields: list[str],
    records: list[EquivalenceClass],
    limit: int = OBSERVATION_LIMIT,
) -> str:
    header_core = " ".join(header_fields)
    if not records:
        text = f"formula_index {kind} {header_core} classes=0 truncated=false omitted_geometry=0\n"
        return text[:limit] if len(text) > limit else text

    def wrap(body: str, truncated: bool, omitted: int, lookup_ids: list[str]) -> str:
        flags = [
            f"formula_index {kind} {header_core} classes={len(records)}",
            f"truncated={'true' if truncated else 'false'}",
            f"omitted_geometry={omitted}",
        ]
        if lookup_ids:
            flags.append("lookup_ids=" + ",".join(lookup_ids))
        return " ".join(flags) + "\n" + body

    full_body = "".join(_class_full(record) for record in records)
    full = wrap(full_body, False, 0, [])
    if len(full) <= limit:
        return full

    # Drop member geometry from the tail until the payload fits, keeping every eq_id.
    included_members = len(records) - 1
    while included_members >= 0:
        parts: list[str] = []
        omitted_ids: list[str] = []
        for index, record in enumerate(records):
            if index < included_members:
                parts.append(_class_full(record))
            else:
                parts.append(_class_identity_lines(record))
                omitted_ids.append(record.eq_id)
        text = wrap("".join(parts), True, len(omitted_ids), omitted_ids)
        if len(text) <= limit:
            return text
        included_members -= 1

    # Identities only; shorten formulas if still over cap.
    for formula_limit in (200, 80, 24, 0):
        parts = [_class_identity_lines(record, formula_limit=formula_limit or 8) for record in records]
        omitted_ids = [record.eq_id for record in records]
        text = wrap("".join(parts), True, len(omitted_ids), omitted_ids)
        if len(text) <= limit:
            return text

    # Last resort: eq_id lines only. Still every class identity.
    compact = "".join(
        f"eq {record.eq_id} n={record.n} sheets={record.sheets}\n" for record in records
    )
    omitted_ids = [record.eq_id for record in records]
    text = wrap(compact, True, len(omitted_ids), omitted_ids)
    if len(text) <= limit:
        return text
    return text[:limit]
