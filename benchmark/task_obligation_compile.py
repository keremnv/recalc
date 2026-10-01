"""Deterministic TASK → V1 obligation compilation evaluation.

Oracle construction and scoring use only task text plus the frozen V1
schema / requirement ledger from task-obligation-shape-probe. No workbook,
golden, formula, or LLM judge.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "benchmark"))
sys.path.insert(0, str(_ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(_ROOT / "src"))

from task_obligation_shape import family_of, weak_clauses  # noqa: E402

# Frozen requirement ledger copied from task-obligation-shape-probe
# DISCOVERY_COUNTEREXAMPLES (families → F_* only). Do not add ontology fields.
LEDGER_BY_FAMILY = {
    "01": [
        "F_LOCUS",
        "F_SUBJECT",
        "F_SCOPE",
        "F_SOURCE_RELATION",
        "F_RESULT_PROPERTY",
        "F_THEN",
        "F_CONDITION",
    ],
    "11": ["F_REQUIRED_CHANGE"],
    "13": ["F_REQUIRED_CHANGE"],
    "15": ["F_SUBJECT_INTERVAL", "F_OCCUPANCY_FILTER"],
    "17": ["F_CONDITION"],
}

V1_FIELDS = [
    "locus",
    "subject",
    "subject_interval",
    "required_change",
    "scope",
    "source_relation",
    "condition",
    "result_property",
    "then_after",
    "occupancy_filter",
]
SCALAR_FIELDS = [
    "locus",
    "subject",
    "required_change",
    "source_relation",
    "condition",
    "result_property",
    "occupancy_filter",
]
CONSTRAINT_FIELDS = [
    "scope",
    "source_relation",
    "condition",
    "result_property",
    "occupancy_filter",
    "subject_interval",
]
FIELD_TO_REQ = {
    "locus": "F_LOCUS",
    "subject": "F_SUBJECT",
    "subject_interval": "F_SUBJECT_INTERVAL",
    "required_change": "F_REQUIRED_CHANGE",
    "scope": "F_SCOPE",
    "source_relation": "F_SOURCE_RELATION",
    "condition": "F_CONDITION",
    "result_property": "F_RESULT_PROPERTY",
    "then_after": "F_THEN",
    "occupancy_filter": "F_OCCUPANCY_FILTER",
}

BOILERPLATE_PREFIXES = (
    "complete the financial model based on the provided assumptions",
    "ensure the existing structure, layout, and formatting of the model are preserved",
)

STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "for",
    "in",
    "on",
    "at",
    "by",
    "as",
    "with",
    "from",
    "that",
    "this",
    "their",
    "its",
    "is",
    "are",
    "be",
    "all",
    "each",
}

CHANGE_FAMILIES = {
    "calculate": "calculate",
    "compute": "calculate",
    "derive": "calculate",
    "link": "link",
    "reference": "link",
    "hardcode": "set",
    "set": "set",
    "define": "set",
    "populate": "populate",
    "fill": "populate",
    "create": "create",
    "insert": "create",
    "add": "add_check",
    "validate": "add_check",
    "apply": "apply",
    "distribute": "apply",
    "convert": "convert",
    "show": "create",
}

# Frozen before any parser output. Linguistic variation only — no finance synonyms.
NORMALIZATION_TABLE = {
    "dashes": ["-", "–", "—", "−"],
    "quotes": ['"', "“", "”", "'", "’"],
    "whitespace": "collapse",
    "case": "casefold",
    "locus_prefix": "drop leading 'in/on the' and trailing sheet/tab/section",
}

PARSER_PROMPT = """\
You compile a spreadsheet-editing TASK INSTRUCTION into clause-level obligations.

You receive only the task text. You have never seen a workbook, sheet index,
cell address, golden answer, formula, or prior agent trace. Do not invent any
of those.

NATURAL UNIT
A CLAUSE_OBLIGATION is one requested transformation plus the constraints
licensed by that same task clause. A task is a conjunction of such
obligations. When the text states an ordering or dependency (then / from that
/ after), record it with then_after.

OUTPUT
Return JSON only of the form {"obligations": [...]}.
Each obligation must use this shape:

{
  "id": "O1",
  "provenance": [{"text": "<exact substring of the task>"}],
  "locus": {"text": "<exact task substring>"} | null,
  "subject": {"text": "<exact task substring>"} | null,
  "subject_interval": {
    "from": {"text": "<exact substring>"},
    "to": {"text": "<exact substring>"}
  } | null,
  "required_change": {"text": "<exact task substring>"} | null,
  "scope": [{"text": "<exact task substring>"}],
  "source_relation": {"text": "<exact task substring>"} | null,
  "condition": {"text": "<exact task substring>"} | null,
  "result_property": {"text": "<exact task substring>"} | null,
  "then_after": ["<obligation id>"],
  "occupancy_filter": {"text": "<exact task substring>"} | null
}

FIELD MEANINGS
- provenance: the clause span(s) this obligation comes from.
- locus: named sheet, tab, or section where the transformation is requested.
- subject: named line item, metric, or object of the clause (not a cell address).
- subject_interval: ordered from–to span of subjects when the task names a
  range of line items (not a year/date range).
- required_change: the requested state change as written (calculate, link,
  reference, set, hardcode, populate, create, add, check, convert, …).
- scope: quantifier or period boundary as written (all / each / through /
  enumerated years / historical vs forecast text).
- source_relation: explicit using / from / based on / by applying / as a
  percentage of / as the sum of correspondence. If the task does not name a
  source correspondence, this must be null.
- condition: when / where guard stated in the clause.
- result_property: required output property (display NM/NA, nil, same as last
  historical, percentage-of, chart encoding).
- then_after: ids of obligations that this one follows when the text is explicit.
- occupancy_filter: constraint over existing cell kind (for example, only cells
  that are not hardcoded).

RULES
1. Every populated semantic field must be an exact substring of the task.
   Copy the task's wording. Do not paraphrase into workbook language.
2. Absent information is null or []. Do not guess.
3. Do not resolve ambiguity with invented workbook knowledge.
4. Multiple requested transformations stay separate obligations.
5. Do not emit an obligation for generic openers that only say to complete a
   model from assumptions, or to preserve structure / layout / formatting,
   unless that sentence also names a specific transformation.
6. Do not convert generic preservation language into a freeze-all-unmentioned-
   cells constraint unless the task explicitly says that.
7. Do not emit cell addresses, formulas, row numbers, or sheet names that are
   not written in the task.
8. If several then-clauses share a leading "In the … sheet/tab/section", that
   locus applies to each of those clauses.
9. Keep compound subjects that are one transformation together
   (for example a list of metrics being calculated the same way).
10. Number obligations O1, O2, … in reading order.

Return JSON only. No commentary.
"""

PARSER_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TASK_OBLIGATION_SHAPE_V1_parse",
    "type": "object",
    "required": ["obligations"],
    "additionalProperties": False,
    "properties": {
        "obligations": {
            "type": "array",
            "items": {"$ref": "#/$defs/obligation"},
        }
    },
    "$defs": {
        "span": {
            "type": "object",
            "required": ["text"],
            "additionalProperties": False,
            "properties": {"text": {"type": "string"}},
        },
        "obligation": {
            "type": "object",
            "required": [
                "id",
                "provenance",
                "locus",
                "subject",
                "subject_interval",
                "required_change",
                "scope",
                "source_relation",
                "condition",
                "result_property",
                "then_after",
                "occupancy_filter",
            ],
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string"},
                "provenance": {"type": "array", "items": {"$ref": "#/$defs/span"}},
                "locus": {"anyOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]},
                "subject": {"anyOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]},
                "subject_interval": {
                    "anyOf": [
                        {
                            "type": "object",
                            "required": ["from", "to"],
                            "additionalProperties": False,
                            "properties": {
                                "from": {"$ref": "#/$defs/span"},
                                "to": {"$ref": "#/$defs/span"},
                            },
                        },
                        {"type": "null"},
                    ]
                },
                "required_change": {"anyOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]},
                "scope": {"type": "array", "items": {"$ref": "#/$defs/span"}},
                "source_relation": {"anyOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]},
                "condition": {"anyOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]},
                "result_property": {"anyOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]},
                "then_after": {"type": "array", "items": {"type": "string"}},
                "occupancy_filter": {"anyOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]},
            },
        },
    },
}

_CHANGE = re.compile(
    r"\b(?:calculate\s*\(\s*or\s*reference\s+where\s+required\s*\)|calculate\s+or\s+reference|"
    r"reference\s+where\s+required|fill in|hardcode|populate|reference|calculate|"
    r"compute|derive|link|create|insert|validate|convert|distribute|define|"
    r"apply|add|set|show)\b",
    re.I,
)
_LOCUS = re.compile(
    r"\b(?:in|on)\s+the\s+(?P<body>.+?)\s+(?:sheet|tab|section)\b|"
    r"\b(?:in|on)\s+the\s+(?P<body2>Balance Sheet|Cash Flow Statement|Dashboard|"
    r"Income Statement)\b|"
    r"\bAt the end of the tab\b",
    re.I,
)
_INTERVAL = re.compile(
    r"\bfrom\s+(?P<frm>(?:PBT|bed capacity)[^,]{0,40}?)\s+to\s+"
    r"(?P<to>(?:EPS(?: Growth \(\%\))?|EBITDA\s*%))",
    re.I,
)
_SCOPE = [
    re.compile(p, re.I)
    for p in [
        r"for all (?:forecast )?periods",
        r"for all years(?: from \d{4}\s*[-–—]\s*\d{4})?",
        r"for all (?:months|quarters|line items)",
        r"for each [A-Za-z0-9 &/'%-]+",
        r"for the forecast(?:ed)? (?:period|years)",
        r"for the same timeframe",
        r"for the terminal year",
        r"for FY\d{2}[A-Za-z]?\s*[-–—]\s*FY\d{2}[A-Za-z]?",
        r"for 20\d{2}[A-Za-z]?\s*[-–—]\s*20\d{2}[A-Za-z]?",
        r"for \d{4}[A-Za-z]?\s*[-–—]\s*\d{4}[A-Za-z]?",
        r"for (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-?\d{2}\s+to\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-?\d{2}",
        r"from 20\d{2}[A-Za-z]?\s+to\s+20\d{2}[A-Za-z]?",
        r"from FY\d{2}[A-Za-z]?\s*[-–—]\s*FY\d{2}[A-Za-z]?",
        r"from \dQFY\d{2}\s+to\s+\dQFY\d{2}",
        r"from \dQFY\d{2} onwards",
        r"across all periods",
        r"\bmonthly\b",
        r"for all 5 years",
        r"for 20\d{2}\s*[-–—]\s*20\d{2}",
    ]
]
_SOURCE = [
    re.compile(p, re.I)
    for p in [
        r"using .+?(?=\s*,\s*then\b|\s+then\b|\s+displaying\b|\s+where\b|\s+when\b|$)",
        r"based on .+?(?=\s*,\s*then\b|\s+then\b|$)",
        r"by applying .+?(?=\s+for\s|\s*,\s*then\b|\s+then\b|$)",
        r"by growing .+?(?=\s*,\s*then\b|\s+then\b|$)",
        r"by summing .+?(?=\s*,\s*then\b|\s+then\b|$)",
        r"by allocating .+?(?=\s*,\s*then\b|\s+then\b|$)",
        r"by dividing .+?(?=\s*,\s*then\b|\s+then\b|$)",
        r"as a percentage of [^.,]+",
        r"as the sum of [^.,]+",
        r"assuming .+?(?=\s+with\s|\s+where\s|\s+when\s|$)",
        r"from another tab",
        r"from the [^.,]+?(?:sheet|tab|section)",
        r"from (?:Key Assumptions|WACC|Asset Schedule|Working Capital|DCF|quarterly data)[^.,]*",
        r"to their respective sensitivity tables",
        r"to the sensitivity table",
        r"to Interest Expense in the Income Statement",
        r"as [^.,]*multiplied by [^.,]+",
        r"at \d+\s+Payable Days",
        r"adjusted for [^)]+\)",
        r"using a roll-forward approach[^.,]*",
        r"linked to [^.,]+",
    ]
]
_CONDITION = [
    re.compile(p, re.I)
    for p in [
        r"where required",
        r"where [^.,)]+",
        r"when [^.,]+",
        r"recognizing tax only in profitable periods",
        r"if [^.,]+",
    ]
]
_RESULT = [
    re.compile(p, re.I)
    for p in [
        r'displaying\s+["“]?NM["”]?[^.,]*',
        r'displaying\s+["“]?NA["”]?[^.,]*',
        r"\bnil tax\b",
        r"the same (?:value )?as the last (?:actual year(?:’s)?(?: value)?|historical year of data)",
        r"as a percentage of [^.,]+",
        r"showing [^.,]+(?:as columns|as a line)[^.,]*",
        r"with a line for [^.,]+",
    ]
]
_OCCUPANCY = re.compile(r"(?:that are )?not hardcoded", re.I)
_ABBR_END = re.compile(r"\b(?:Adj|Inc|Ltd|No|vs|al|Est)\.$", re.I)
_THEN_HEAD = re.compile(r"^(?:Then,?\s+|From that,\s+|after\s+)", re.I)
_AND_CHANGE = re.compile(
    r"(?:,|\s)+and\s+(?=(?:calculate|compute|convert|create|link|hardcode|add|set|define|apply|populate|reference)\b)",
    re.I,
)
_CELL_ADDR = re.compile(r"(?<![A-Za-z])\$?[A-Z]{1,3}\$?[1-9][0-9]{0,3}(?![0-9A-Za-z])")
_FORMULA = re.compile(r"(?<![A-Za-z])=[A-Z(]")
_SHEET_BANG = re.compile(r"[A-Za-z][A-Za-z0-9 _&./-]{1,40}![A-Z]{1,3}\d+")
_PERIOD_TOKEN = re.compile(
    r"^(?:20\d{2}|FY\d{2}|\dQFY\d{2}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
    re.I,
)

KNOWN_SPEC_CHECKS = [
    {
        "id": "K6",
        "task": "04_05",
        "label": "04_05 K6",
        "must_preserve": ["growing from 2013", "total growth rates", "forecast revenue"],
        "must_not_invent": ["K12", "K27"],
    },
    {
        "id": "K163",
        "task": "09_05",
        "label": "09_05 K163/L163",
        "must_preserve": ["Other Long-Term Assets", "2014F", "2018F"],
        "must_not_invent": ["K163", "L163", "K164", "K18"],
    },
    {
        "id": "D10",
        "task": "14_05",
        "label": "14_05 D10",
        "must_preserve": ["income tax", "effective tax rate", "Tax-DCF", "marginal tax rate"],
        "must_not_invent": ["D10"],
    },
    {
        "id": "H41",
        "task": "20_04",
        "label": "20_04 H41",
        "must_preserve": ["days-based linkage", "Income Statement expenses", "Other Current Liabilities"],
        "must_not_invent": ["H41", "H30", "H42"],
    },
    {
        "id": "J31",
        "task": "14_05",
        "label": "14_05 J31",
        "must_preserve": ["Total Revenue", "all products", "all periods"],
        "must_not_invent": ["J31", "J7", "SUM("],
    },
    {
        "id": "J46",
        "task": "08_01",
        "label": "08_01 J46",
        "must_preserve": ["Inventory", "Payables", "Receivables", "70% bills discounting", "Aug-23"],
        "must_not_invent": ["J46"],
    },
    {
        "id": "AF66",
        "task": "08_01",
        "label": "08_01 AF66/AG66",
        "must_preserve": ["30%", "nil tax", "PBT is negative"],
        "must_not_invent": ["AF66", "AG66", "$C$8", "C8"],
    },
    {
        "id": "K104",
        "task": "17_03",
        "label": "17_03 K104",
        "must_preserve": ["percentage of Revenue", "Other Long-Term Assets"],
        "must_not_invent": ["K104", "/365", "365"],
    },
    {
        "id": "Y39",
        "task": "15_04",
        "label": "15_04 Y39/Y40",
        "must_preserve": ["PBT", "EPS Growth", "not hardcoded"],
        "must_not_invent": ["Y39", "Y40"],
    },
]


def text_node(text: str | None) -> dict[str, str] | None:
    if not text:
        return None
    cleaned = text.strip(" ,;.")
    if not cleaned:
        return None
    return {"text": cleaned}


def normalize(text: str | None) -> str:
    if not text:
        return ""
    out = text.casefold()
    for dash in ("–", "—", "−"):
        out = out.replace(dash, "-")
    for quote in ("“", "”", "’", "'"):
        out = out.replace(quote, '"')
    out = re.sub(r"\s+", " ", out).strip()
    return out


def normalize_locus(text: str | None) -> str:
    out = normalize(text)
    out = re.sub(r"^(?:in|on)\s+the\s+", "", out)
    out = re.sub(r"\s+(?:sheet|tab|section)$", "", out)
    return out


def tokens(text: str | None) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9%]+", normalize(text)) if tok not in STOPWORDS}


def span_in_task(span_text: str, task: str) -> dict[str, Any]:
    exact = span_text in task
    if exact:
        return {"exact": True, "normalized": True}
    return {"exact": False, "normalized": normalize(span_text) in normalize(task)}


def is_boilerplate(text: str) -> bool:
    n = normalize(text)
    if n.startswith("complete the") and "financial model based on the provided assumptions" in n:
        return True
    if n.startswith("ensure the existing structure, layout, and formatting of the model are"):
        return True
    return False


def _first_match(patterns: list[re.Pattern[str]], text: str) -> str | None:
    hits = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            hits.append(match.group(0))
    if not hits:
        return None
    hits.sort(key=len, reverse=True)
    return hits[0].strip()


def _all_matches(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    found: list[str] = []
    occupied: list[tuple[int, int]] = []
    candidates: list[tuple[int, int, str]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            candidates.append((match.start(), match.end(), match.group(0).strip()))
    candidates.sort(key=lambda row: (row[0], -(row[1] - row[0])))
    for start, end, value in candidates:
        if any(start < o_end and end > o_start for o_start, o_end in occupied):
            continue
        occupied.append((start, end))
        if value and value not in found:
            found.append(value)
    return found


def _clause_pieces(instruction: str) -> list[dict[str, Any]]:
    raw = weak_clauses(instruction)
    merged: list[dict[str, Any]] = []
    for clause in raw:
        text = clause["exact_source_span"]["text"].strip()
        if merged and _ABBR_END.search(merged[-1]["exact_source_span"]["text"].rstrip()):
            prev = merged[-1]
            joined = (prev["exact_source_span"]["text"].rstrip() + " " + text).strip()
            prev["exact_source_span"] = {"text": joined}
            prev["relation_spans"] = prev.get("relation_spans") or clause.get("relation_spans") or []
            continue
        merged.append(
            {
                "exact_source_span": {"text": text},
                "relation_spans": list(clause.get("relation_spans") or []),
                "predicate_span": clause.get("predicate_span"),
            }
        )
    expanded: list[dict[str, Any]] = []
    for clause in merged:
        text = clause["exact_source_span"]["text"]
        parts = _AND_CHANGE.split(text)
        if len(parts) == 1:
            expanded.append(clause)
            continue
        for i, part in enumerate(parts):
            piece = part.strip(" ,;")
            if not piece:
                continue
            rel = []
            if i == 0:
                rel = list(clause.get("relation_spans") or [])
            expanded.append({"exact_source_span": {"text": piece}, "relation_spans": rel})
    return expanded


def _extract_locus(text: str) -> str | None:
    match = _LOCUS.search(text)
    if not match:
        return None
    body = match.groupdict().get("body") or match.groupdict().get("body2")
    if body or "end of the tab" in match.group(0).casefold():
        return match.group(0)
    return None


def _extract_change(text: str) -> str | None:
    match = _CHANGE.search(text)
    if not match:
        return None
    word = match.group(0)
    if normalize(word) == "note":
        return None
    return word


def _extract_interval(text: str) -> dict[str, Any] | None:
    match = _INTERVAL.search(text)
    if not match:
        return None
    return {
        "from": {"text": match.group("frm").strip()},
        "to": {"text": match.group("to").strip()},
    }


def _extract_subject(text: str, change: str | None) -> str | None:
    work = text
    locus = _LOCUS.search(work)
    if locus:
        work = work[locus.end() :].lstrip(" ,")
    work = _THEN_HEAD.sub("", work).strip()
    if change:
        idx = normalize(work).find(normalize(change))
        if idx >= 0:
            work = work[idx + len(change) :].strip(" ,")
    cuts: list[int] = []
    for pattern in _SCOPE + _SOURCE + _CONDITION + _RESULT + [_OCCUPANCY, _INTERVAL]:
        match = pattern.search(work)
        if match:
            cuts.append(match.start())
    end = min(cuts) if cuts else len(work)
    subject = work[:end].strip(" ,;:")
    subject = re.sub(r"^(?:the|a|an)\s+", "", subject, flags=re.I)
    if not subject or is_boilerplate(subject):
        return None
    if len(subject) > 220:
        subject = subject[:220].rsplit(" ", 1)[0]
    return subject or None


def _inherit_ok(text: str) -> bool:
    if _LOCUS.search(text):
        return False
    if re.match(r"^(?:Then,?\s+)?(?:in|on)\s+the\s+", text, re.I):
        return False
    return True


def obligation_from_clause(
    text: str,
    *,
    oid: str,
    prev_id: str | None,
    inherited_locus: str | None,
    then_link: bool,
) -> dict[str, Any]:
    work = text.strip(" ,;")
    work = re.sub(r"\s+and$", "", work).strip()
    leading_then = bool(re.match(r"^(?:Then,|From that,|after\b)", work, re.I))
    after_ref = None
    after_match = re.match(
        r"^after\s+(?P<body>referencing\s+.+?)\s*,\s*",
        work,
        re.I,
    )
    if after_match:
        after_ref = after_match.group("body").strip()
        work = work[after_match.end() :].strip()
    change = _extract_change(work)
    locus = _extract_locus(text) or (_extract_locus(work))
    if locus is None and inherited_locus and _inherit_ok(text):
        locus = inherited_locus
    scope = _all_matches(_SCOPE, work)
    source = _first_match(_SOURCE, work)
    condition = _first_match(_CONDITION, work)
    result = _first_match(_RESULT, work)
    occupancy = None
    occ = _OCCUPANCY.search(work)
    if occ:
        occupancy = occ.group(0)
    interval = _extract_interval(work)
    subject = _extract_subject(work, change)
    then_after: list[str] = []
    if then_link and prev_id:
        then_after.append(prev_id)
    elif leading_then and prev_id:
        then_after.append(prev_id)
    note = re.search(r"note that\s+(.+)$", work, re.I)
    if note and result is None:
        result = note.group(0).strip()
    return {
        "id": oid,
        "provenance": [{"text": text.strip()}],
        "locus": text_node(locus),
        "subject": text_node(subject),
        "subject_interval": interval,
        "required_change": text_node(change),
        "scope": [{"text": item} for item in scope],
        "source_relation": text_node(source),
        "condition": text_node(condition),
        "result_property": text_node(result),
        "then_after": then_after,
        "occupancy_filter": text_node(occupancy),
        "oracle_note_after_referencing": after_ref,
    }


def build_ungrounded_oracle(instruction: str) -> list[dict[str, Any]]:
    """Task-text-only V1 obligations. No addresses, formulas, or workbook facts."""
    obligations: list[dict[str, Any]] = []
    prev_id = None
    inherited_locus = None
    n = 0
    for clause in _clause_pieces(instruction):
        text = clause["exact_source_span"]["text"].strip()
        if is_boilerplate(text):
            continue
        n += 1
        oid = f"O{n}"
        then_link = bool(clause.get("relation_spans"))
        rec = obligation_from_clause(
            text,
            oid=oid,
            prev_id=prev_id,
            inherited_locus=inherited_locus,
            then_link=then_link,
        )
        rec.pop("oracle_note_after_referencing", None)
        if rec["locus"]:
            inherited_locus = rec["locus"]["text"]
        obligations.append(rec)
        prev_id = oid
    return obligations


def ledger_requirements_for_family(family: str) -> list[str]:
    return list(LEDGER_BY_FAMILY.get(family, []))


def populated_requirements(obligations: list[dict[str, Any]]) -> list[str]:
    present: list[str] = []
    for field, req in FIELD_TO_REQ.items():
        if any(_field_populated(ob, field) for ob in obligations):
            if req not in present:
                present.append(req)
    return present


def critical_requirements(task_id: str, obligations: list[dict[str, Any]]) -> list[str]:
    family = family_of(task_id)
    ledger = ledger_requirements_for_family(family)
    populated = populated_requirements(obligations)
    if ledger:
        return [req for req in ledger if req in populated] or populated
    return populated


def _field_populated(ob: dict[str, Any], field: str) -> bool:
    value = ob.get(field)
    if value is None:
        return False
    if field == "then_after":
        return bool(value)
    if field == "scope":
        return bool(value)
    if field == "subject_interval":
        return bool(value)
    if isinstance(value, dict):
        return bool(value.get("text"))
    if isinstance(value, list):
        return bool(value)
    return bool(value)


def field_texts(ob: dict[str, Any], field: str) -> list[str]:
    value = ob.get(field)
    if value is None:
        return []
    if field == "then_after":
        return [str(item) for item in value]
    if field == "subject_interval" and isinstance(value, dict):
        texts = []
        for key in ("from", "to"):
            node = value.get(key) or {}
            if isinstance(node, dict) and node.get("text"):
                texts.append(node["text"])
            elif isinstance(node, str):
                texts.append(node)
        return texts
    if isinstance(value, dict) and "text" in value:
        return [value["text"]] if value["text"] else []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict) and item.get("text"):
                out.append(item["text"])
            elif isinstance(item, str):
                out.append(item)
        return out
    if isinstance(value, str):
        return [value]
    return []


def concat_texts(ob: dict[str, Any], fields: list[str]) -> str:
    parts = []
    for field in fields:
        parts.extend(field_texts(ob, field))
    return " ".join(parts)


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def containment(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def locus_overlap(a: str, b: str) -> float:
    na, nb = normalize_locus(a), normalize_locus(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    return containment(a, b)


def match_score(oracle: dict[str, Any], pred: dict[str, Any]) -> float:
    return (
        0.40 * jaccard(concat_texts(oracle, ["provenance"]), concat_texts(pred, ["provenance"]))
        + 0.20 * locus_overlap(concat_texts(oracle, ["locus"]), concat_texts(pred, ["locus"]))
        + 0.20 * containment(concat_texts(oracle, ["subject"]), concat_texts(pred, ["subject"]))
        + 0.10 * jaccard(concat_texts(oracle, ["required_change"]), concat_texts(pred, ["required_change"]))
        + 0.10 * jaccard(concat_texts(oracle, ["scope"]), concat_texts(pred, ["scope"]))
    )


MATCH_THRESHOLD = 0.18


def match_obligations(
    oracle: list[dict[str, Any]],
    pred: list[dict[str, Any]],
) -> dict[str, Any]:
    pairs: list[tuple[float, int, int]] = []
    for i, o_row in enumerate(oracle):
        for j, p_row in enumerate(pred):
            score = match_score(o_row, p_row)
            pairs.append((score, i, j))
    pairs.sort(reverse=True)
    used_o: set[int] = set()
    used_p: set[int] = set()
    matching: list[dict[str, Any]] = []
    for score, i, j in pairs:
        if i in used_o or j in used_p:
            continue
        if score < MATCH_THRESHOLD:
            continue
        used_o.add(i)
        used_p.add(j)
        matching.append(
            {
                "oracle_id": oracle[i]["id"],
                "pred_id": pred[j].get("id") or f"P{j+1}",
                "oracle_index": i,
                "pred_index": j,
                "score": round(score, 4),
            }
        )
    unmatched_oracle = [oracle[i]["id"] for i in range(len(oracle)) if i not in used_o]
    unmatched_pred = [(pred[j].get("id") or f"P{j+1}") for j in range(len(pred)) if j not in used_p]
    merged = []
    split = []
    unmatched_o_set = set(unmatched_oracle)
    unmatched_p_set = set(unmatched_pred)
    if unmatched_p_set:
        for i, o_row in enumerate(oracle):
            covering = [
                (match_score(o_row, pred[j]), pred[j].get("id") or f"P{j+1}", j)
                for j in range(len(pred))
                if match_score(o_row, pred[j]) >= 0.35
            ]
            covering.sort(reverse=True)
            pred_ids = [row[1] for row in covering]
            if len(pred_ids) >= 2 and any(pid in unmatched_p_set for pid in pred_ids):
                split.append({"oracle_id": o_row["id"], "pred_ids": pred_ids[:2]})
    if unmatched_o_set:
        for j, p_row in enumerate(pred):
            covering = []
            for i, o_row in enumerate(oracle):
                subj_hit = texts_overlap(field_texts(o_row, "subject"), field_texts(p_row, "subject"))
                prov_hit = containment(
                    concat_texts(o_row, ["provenance"]),
                    concat_texts(p_row, ["provenance"]),
                ) >= 0.7
                if subj_hit or prov_hit:
                    covering.append(o_row["id"])
            distinct = []
            for oid in covering:
                if oid not in distinct:
                    distinct.append(oid)
            if len(distinct) >= 2 and any(oid in unmatched_o_set for oid in distinct):
                merged.append(
                    {
                        "pred_id": p_row.get("id") or f"P{j+1}",
                        "oracle_ids": distinct[:3],
                    }
                )
    return {
        "pairs": matching,
        "unmatched_oracle": unmatched_oracle,
        "unmatched_pred": unmatched_pred,
        "merged_candidates": merged,
        "split_candidates": split,
    }


def change_family(text: str | None) -> str | None:
    if not text:
        return None
    n = normalize(text)
    for key, family in CHANGE_FAMILIES.items():
        if key in n:
            return family
    return None


def texts_overlap(a: list[str], b: list[str], *, field: str | None = None) -> bool:
    if not a or not b:
        return False
    for left in a:
        for right in b:
            if field == "locus":
                if locus_overlap(left, right) >= 0.5:
                    return True
            elif containment(left, right) >= 0.5 or jaccard(left, right) >= 0.4:
                return True
    return False


def _pred_blob(pred: dict[str, Any]) -> str:
    return concat_texts(pred, ["provenance", "locus", "subject", "required_change", *CONSTRAINT_FIELDS])


def collect_spans(ob: dict[str, Any]) -> list[tuple[str, str]]:
    rows = []
    for field in ["provenance", *V1_FIELDS]:
        if field == "then_after":
            continue
        for text in field_texts(ob, field):
            rows.append((field, text))
    return rows


def extract_json_object(raw: str) -> dict[str, Any] | None:
    """Read one JSON object out of a model response.

    The span from the first '{' to the last '}' is tried first, which is what
    this reader has always done. When that span is not valid JSON the response
    is not necessarily malformed: a model that emits a valid answer and then
    repeats it verbatim produces a span covering both objects. That case was
    discarding correct answers across every probe that shares this function, and
    on one Edit Plan task it suppressed a real end-to-end success (07_03 scored
    0.0 with the discarded answer and 0.75 with it).

    So a second pass decodes every top-level object and returns one only when
    the repeats agree. Objects that disagree stay unparseable, because choosing
    between two different answers would be a semantic repair rather than a parse.
    """
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        payload = _single_repeated_object(text)
    return payload if isinstance(payload, dict) else None


def _single_repeated_object(text: str) -> dict[str, Any] | None:
    """The one object a response carries, when it emitted it more than once."""
    decoder = json.JSONDecoder()
    found: list[Any] = []
    i = 0
    while True:
        start = text.find("{", i)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
        except ValueError:
            i = start + 1
            continue
        if isinstance(obj, dict):
            found.append(obj)
        i = end
    if not found or any(x != found[0] for x in found):
        return None
    return found[0]


def normalize_prediction(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    rows = payload.get("obligations")
    if not isinstance(rows, list):
        return []
    out = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        rec = {field: row.get(field) for field in ["id", *V1_FIELDS, "provenance"]}
        rec["id"] = rec.get("id") or f"O{i}"
        if rec.get("scope") is None:
            rec["scope"] = []
        if rec.get("then_after") is None:
            rec["then_after"] = []
        if rec.get("provenance") is None:
            rec["provenance"] = []
        out.append(rec)
    return out


def workbook_like_inventions(pred: list[dict[str, Any]], task: str) -> list[str]:
    blob = json.dumps(pred, ensure_ascii=False)
    task_n = normalize(task)
    hits: list[str] = []
    for match in _CELL_ADDR.finditer(blob):
        token = match.group(0)
        if re.fullmatch(r"O\d+", token):
            continue
        if token in task or normalize(token) in task_n:
            continue
        if re.match(r"^FY\d", token, re.I):
            continue
        hits.append(token)
    for match in _SHEET_BANG.finditer(blob):
        token = match.group(0)
        if token not in task:
            hits.append(token)
    for match in _FORMULA.finditer(blob):
        hits.append(match.group(0))
    if re.search(r"(?<![0-9])365(?![0-9])", blob) and "365" not in task:
        hits.append("365")
    # unique preserve order
    seen = set()
    out = []
    for item in hits:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def unsupported_field_inferences(pred: dict[str, Any], task: str) -> list[dict[str, str]]:
    rows = []
    for field, text in collect_spans(pred):
        if field == "provenance":
            continue
        status = span_in_task(text, task)
        extra = tokens(text) - tokens(task)
        extra -= {"null", "oid", "o1", "o2", "o3"}
        if status["normalized"] or containment(text, task) >= 0.85:
            continue
        if extra:
            rows.append({"field": field, "text": text, "extra_tokens": " ".join(sorted(extra)[:12])})
    return rows


def is_boilerplate_obligation(ob: dict[str, Any]) -> bool:
    blob = concat_texts(ob, ["provenance", "subject", "required_change"])
    return is_boilerplate(blob)


def complexity_record(task_id: str, instruction: str, oracle: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(oracle)
    if n <= 1:
        bucket = "1"
    elif n <= 3:
        bucket = "2-3"
    elif n <= 6:
        bucket = "4-6"
    else:
        bucket = ">=7"
    then_edges = sum(len(ob.get("then_after") or []) for ob in oracle)
    loci = {normalize(t) for ob in oracle for t in field_texts(ob, "locus") if t}
    subjects = {normalize(t) for ob in oracle for t in field_texts(ob, "subject") if t}
    populated = sum(1 for ob in oracle for field in V1_FIELDS if _field_populated(ob, field))
    longest = max((len(concat_texts(ob, ["provenance"])) for ob in oracle), default=0)
    return {
        "task": task_id,
        "task_characters": len(instruction),
        "task_tokens_est": max(1, len(instruction.split())),
        "n_oracle_obligations": n,
        "n_populated_constraint_fields": populated,
        "n_then_edges": then_edges,
        "n_loci": len(loci),
        "n_subjects": len(subjects),
        "longest_clause_characters": longest,
        "obligation_bucket": bucket,
        "composition": "explicit_THEN" if then_edges else "no_THEN",
    }


def score_task(
    *,
    task_id: str,
    instruction: str,
    oracle: list[dict[str, Any]],
    pred: list[dict[str, Any]],
    parse_valid: bool,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    ambiguous: list[str] = []
    if not parse_valid:
        errors.append({"code": "OMITTED_CLAUSE", "detail": "invalid or missing JSON parse"})
        matching = {
            "pairs": [],
            "unmatched_oracle": [ob["id"] for ob in oracle],
            "unmatched_pred": [],
            "merged_candidates": [],
            "split_candidates": [],
        }
        pred = []
    else:
        matching = match_obligations(oracle, pred)

    o_by = {ob["id"]: ob for ob in oracle}
    p_by = {ob.get("id"): ob for ob in pred}
    pair_by_o = {row["oracle_id"]: row for row in matching["pairs"]}
    pair_by_p = {row["pred_id"]: row for row in matching["pairs"]}

    for oid in matching["unmatched_oracle"]:
        errors.append({"code": "OMITTED_CLAUSE", "detail": oid})
    for pid in matching["unmatched_pred"]:
        prow = p_by.get(pid) or {}
        if is_boilerplate_obligation(prow):
            errors.append({"code": "SPURIOUS_OBLIGATION", "detail": f"boilerplate:{pid}"})
        else:
            errors.append({"code": "SPURIOUS_OBLIGATION", "detail": pid})
    for row in matching["merged_candidates"]:
        errors.append(
            {
                "code": "MERGED_OBLIGATIONS",
                "detail": f"{row['pred_id']} <- {','.join(row['oracle_ids'])}",
            }
        )
    for row in matching["split_candidates"]:
        if len(row["pred_ids"]) >= 2 and any(pid in matching["unmatched_pred"] for pid in row["pred_ids"]):
            errors.append(
                {
                    "code": "SPLIT_OBLIGATION",
                    "detail": f"{row['oracle_id']} -> {','.join(row['pred_ids'])}",
                }
            )

    field_counts = {
        field: {"tp": 0, "fp": 0, "fn": 0} for field in V1_FIELDS
    }
    for pair in matching["pairs"]:
        o_row = o_by[pair["oracle_id"]]
        p_row = pred[pair["pred_index"]]
        for field in V1_FIELDS:
            if field == "then_after":
                continue
            o_txt = field_texts(o_row, field)
            p_txt = field_texts(p_row, field)
            o_on = bool(o_txt)
            p_on = bool(p_txt)
            if o_on and p_on and texts_overlap(o_txt, p_txt, field=field):
                field_counts[field]["tp"] += 1
            elif o_on and not p_on:
                field_counts[field]["fn"] += 1
                errors.append(
                    {
                        "code": "OMITTED_CONSTRAINT",
                        "detail": f"{pair['oracle_id']}.{field}",
                    }
                )
            elif o_on and p_on and not texts_overlap(o_txt, p_txt, field=field):
                field_counts[field]["fn"] += 1
                field_counts[field]["fp"] += 1
                if field == "required_change":
                    if change_family(" ".join(o_txt)) != change_family(" ".join(p_txt)):
                        errors.append(
                            {
                                "code": "REQUIRED_CHANGE_CONFUSION",
                                "detail": f"{pair['oracle_id']}:{o_txt} vs {p_txt}",
                            }
                        )
                    else:
                        ambiguous.append(f"{pair['oracle_id']}.{field}")
                elif field == "scope":
                    o_all = any("all" in normalize(t) for t in o_txt)
                    p_all = any("all" in normalize(t) for t in p_txt)
                    if p_all and not o_all:
                        errors.append(
                            {
                                "code": "OVERGENERALIZED_SCOPE",
                                "detail": pair["oracle_id"],
                            }
                        )
                    elif o_all and not p_all:
                        errors.append(
                            {
                                "code": "UNDERGENERALIZED_SCOPE",
                                "detail": pair["oracle_id"],
                            }
                        )
                    else:
                        errors.append(
                            {
                                "code": "OMITTED_CONSTRAINT",
                                "detail": f"{pair['oracle_id']}.{field}_mismatch",
                            }
                        )
                else:
                    errors.append(
                        {
                            "code": "OMITTED_CONSTRAINT",
                            "detail": f"{pair['oracle_id']}.{field}_mismatch",
                        }
                    )
            elif p_on and not o_on:
                field_counts[field]["fp"] += 1

        o_fam = change_family(concat_texts(o_row, ["required_change"]))
        p_fam = change_family(concat_texts(p_row, ["required_change"]))
        if o_fam and p_fam and o_fam != p_fam:
            if not any(e["code"] == "REQUIRED_CHANGE_CONFUSION" and pair["oracle_id"] in e["detail"] for e in errors):
                errors.append(
                    {
                        "code": "REQUIRED_CHANGE_CONFUSION",
                        "detail": f"{pair['oracle_id']}:{o_fam}->{p_fam}",
                    }
                )

    # Attachment: oracle constraint appears on a different matched prediction.
    for field in CONSTRAINT_FIELDS:
        for o_row in oracle:
            o_txt = field_texts(o_row, field)
            if not o_txt:
                continue
            pair = pair_by_o.get(o_row["id"])
            if not pair:
                continue
            home = pred[pair["pred_index"]]
            if texts_overlap(o_txt, field_texts(home, field), field=field):
                continue
            for other in matching["pairs"]:
                if other["oracle_id"] == o_row["id"]:
                    continue
                other_pred = pred[other["pred_index"]]
                blob = _pred_blob(other_pred) + " " + concat_texts(other_pred, [field])
                if any(containment(t, blob) >= 0.8 for t in o_txt):
                    errors.append(
                        {
                            "code": "WRONG_ATTACHMENT",
                            "detail": f"{field} of {o_row['id']} on {other['pred_id']}",
                        }
                    )
                    break

    # Composition: then_after edges.
    id_map = {row["oracle_id"]: row["pred_id"] for row in matching["pairs"]}
    then_tp = then_fn = then_fp = 0
    for o_row in oracle:
        targets = o_row.get("then_after") or []
        pair = pair_by_o.get(o_row["id"])
        pred_targets = []
        if pair:
            pred_targets = list(pred[pair["pred_index"]].get("then_after") or [])
        if not targets and not pred_targets:
            continue
        if targets and pair:
            expected = [id_map[t] for t in targets if t in id_map]
            if expected and any(item in pred_targets for item in expected):
                then_tp += 1
            else:
                then_fn += 1
                errors.append(
                    {
                        "code": "COMPOSITION_ERROR",
                        "detail": f"{o_row['id']}.then_after {targets} -> {pred_targets}",
                    }
                )
        elif targets and not pair:
            then_fn += 1
        elif pred_targets and not targets:
            then_fp += 1
    field_counts["then_after"]["tp"] = then_tp
    field_counts["then_after"]["fn"] = then_fn
    field_counts["then_after"]["fp"] = then_fp

    inventions = []
    for p_row in pred:
        inventions.extend(unsupported_field_inferences(p_row, instruction))
        for field, text in collect_spans(p_row):
            status = span_in_task(text, instruction)
            if field == "then_after":
                continue
            if not status["normalized"] and containment(text, instruction) < 0.85:
                extra = tokens(text) - tokens(instruction)
                if extra:
                    errors.append(
                        {
                            "code": "PROVENANCE_ERROR",
                            "detail": f"{p_row.get('id')}.{field}",
                        }
                    )
    wb_hits = workbook_like_inventions(pred, instruction)
    if inventions or wb_hits:
        errors.append(
            {
                "code": "UNSUPPORTED_INFERENCE",
                "detail": "; ".join(
                    [f"{row['field']}:{row['text'][:80]}" for row in inventions[:6]]
                    + [f"wb:{h}" for h in wb_hits[:6]]
                ),
            }
        )

    # Span validity
    exact_n = norm_n = total_spans = 0
    for p_row in pred:
        for field, text in collect_spans(p_row):
            if field == "then_after":
                continue
            total_spans += 1
            status = span_in_task(text, instruction)
            if status["exact"]:
                exact_n += 1
                norm_n += 1
            elif status["normalized"]:
                norm_n += 1

    reqs = critical_requirements(task_id, oracle)
    preserved_reqs = []
    for req in reqs:
        field = {v: k for k, v in FIELD_TO_REQ.items()}[req]
        ok = True
        if field == "then_after":
            ok = not any(e["code"] == "COMPOSITION_ERROR" for e in errors)
        else:
            for o_row in oracle:
                if not _field_populated(o_row, field):
                    continue
                pair = pair_by_o.get(o_row["id"])
                if not pair:
                    ok = False
                    break
                p_row = pred[pair["pred_index"]]
                if not texts_overlap(field_texts(o_row, field), field_texts(p_row, field), field=field):
                    ok = False
                    break
        if ok:
            preserved_reqs.append(req)

    material_fail_codes = {
        "OMITTED_CLAUSE",
        "SPURIOUS_OBLIGATION",
        "MERGED_OBLIGATIONS",
        "WRONG_ATTACHMENT",
        "COMPOSITION_ERROR",
        "UNSUPPORTED_INFERENCE",
        "REQUIRED_CHANGE_CONFUSION",
        "OVERGENERALIZED_SCOPE",
        "UNDERGENERALIZED_SCOPE",
    }
    material = [e for e in errors if e["code"] in material_fail_codes]
    # Omitted constraint on a critical field also fails spec preservation.
    for e in errors:
        if e["code"] == "OMITTED_CONSTRAINT":
            for req in reqs:
                fname = {v: k for k, v in FIELD_TO_REQ.items()}[req]
                if f".{fname}" in e["detail"] or f".{fname}_" in e["detail"]:
                    material.append(e)
                    break
    task_spec = parse_valid and not material and set(preserved_reqs) == set(reqs)

    loss_codes = {
        "OMITTED_CLAUSE",
        "OMITTED_CONSTRAINT",
        "MERGED_OBLIGATIONS",
        "COMPOSITION_ERROR",
        "UNDERGENERALIZED_SCOPE",
    }
    invention_codes = {
        "SPURIOUS_OBLIGATION",
        "UNSUPPORTED_INFERENCE",
        "OVERGENERALIZED_SCOPE",
    }
    boilerplate_n = sum(1 for p_row in pred if is_boilerplate_obligation(p_row))

    return {
        "task": task_id,
        "parse_valid": parse_valid,
        "n_oracle": len(oracle),
        "n_pred": len(pred),
        "matching": matching,
        "errors": errors,
        "error_counts": dict(Counter(e["code"] for e in errors)),
        "field_counts": field_counts,
        "critical_requirements": reqs,
        "preserved_requirements": preserved_reqs,
        "critical_requirement_recall": (
            round(len(preserved_reqs) / len(reqs), 4) if reqs else 1.0
        ),
        "all_critical_requirements_preserved": set(preserved_reqs) == set(reqs) and bool(reqs or parse_valid),
        "task_spec_preserved": bool(task_spec),
        "evaluation_ambiguous": ambiguous,
        "loss_n": sum(1 for e in errors if e["code"] in loss_codes),
        "invention_n": sum(1 for e in errors if e["code"] in invention_codes),
        "boilerplate_as_obligation": boilerplate_n > 0,
        "workbook_like_hits": wb_hits,
        "span_exact": exact_n,
        "span_normalized": norm_n,
        "span_total": total_spans,
        "complexity": complexity_record(task_id, instruction, oracle),
    }


def pr(counts: dict[str, int]) -> dict[str, float | None]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    return {
        "precision": None if prec is None else round(prec, 4),
        "recall": None if rec is None else round(rec, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def aggregate_scores(rows: list[dict[str, Any]], split: str | None = None) -> dict[str, Any]:
    picked = [row for row in rows if split is None or row.get("split") == split]
    evaluable = [row for row in picked if row.get("evaluable", True)]
    n = len(evaluable) or 1
    preserved = sum(1 for row in evaluable if row["task_spec_preserved"])
    field_sum = {field: Counter() for field in V1_FIELDS}
    for row in evaluable:
        for field, counts in row["field_counts"].items():
            field_sum[field].update(counts)
    error_sum: Counter[str] = Counter()
    for row in evaluable:
        error_sum.update(row["error_counts"])
    crit_num = sum(len(row["preserved_requirements"]) for row in evaluable)
    crit_den = sum(len(row["critical_requirements"]) for row in evaluable) or 1
    return {
        "split": split or "overall",
        "n_tasks": len(picked),
        "n_evaluable": len(evaluable),
        "TASK_SPEC_PRESERVATION_RATE": round(preserved / len(evaluable), 4) if evaluable else None,
        "n_spec_preserved": preserved,
        "CRITICAL_REQUIREMENT_RECALL": round(crit_num / crit_den, 4),
        "ALL_CRITICAL_REQUIREMENTS_PRESERVED_RATE": round(
            sum(1 for row in evaluable if row["all_critical_requirements_preserved"]) / len(evaluable),
            4,
        )
        if evaluable
        else None,
        "error_counts": dict(error_sum),
        "field_pr": {field: pr(dict(field_sum[field])) for field in V1_FIELDS},
        "loss_tasks": sum(1 for row in evaluable if row["loss_n"] > 0),
        "invention_tasks": sum(1 for row in evaluable if row["invention_n"] > 0),
        "boilerplate_as_obligation_rate": round(
            sum(1 for row in evaluable if row["boilerplate_as_obligation"]) / len(evaluable),
            4,
        )
        if evaluable
        else None,
        "workbook_inference_tasks": sum(1 for row in evaluable if row.get("workbook_like_hits")),
        "span_exact_rate": round(
            sum(row["span_exact"] for row in evaluable) / max(1, sum(row["span_total"] for row in evaluable)),
            4,
        ),
        "span_normalized_rate": round(
            sum(row["span_normalized"] for row in evaluable) / max(1, sum(row["span_total"] for row in evaluable)),
            4,
        ),
        "evaluation_ambiguous_tasks": sum(1 for row in evaluable if row.get("evaluation_ambiguous")),
    }


def compare_models(glm_rows: list[dict[str, Any]], gpt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    g = {row["task"]: row for row in glm_rows}
    p = {row["task"]: row for row in gpt_rows}
    out = []
    for task in sorted(set(g) & set(p)):
        a, b = g[task], p[task]
        if a["task_spec_preserved"] and b["task_spec_preserved"]:
            cat = "BOTH_PRESERVE"
        elif b["task_spec_preserved"] and not a["task_spec_preserved"]:
            cat = "GPT_ONLY_PRESERVES"
        elif a["task_spec_preserved"] and not b["task_spec_preserved"]:
            cat = "GLM_ONLY_PRESERVES"
        else:
            a_codes = set(a["error_counts"])
            b_codes = set(b["error_counts"])
            cat = "BOTH_FAIL_SAME_REQUIREMENT" if a_codes == b_codes else "BOTH_FAIL_DIFFERENTLY"
        out.append(
            {
                "task": task,
                "category": cat,
                "glm_spec": a["task_spec_preserved"],
                "gpt_spec": b["task_spec_preserved"],
                "glm_errors": a["error_counts"],
                "gpt_errors": b["error_counts"],
                "glm_crit_recall": a["critical_requirement_recall"],
                "gpt_crit_recall": b["critical_requirement_recall"],
            }
        )
    return out


def known_case_analysis(task_id: str, instruction: str, pred: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blob = json.dumps(pred, ensure_ascii=False)
    blob_n = normalize(blob)
    out = []
    for check in KNOWN_SPEC_CHECKS:
        if check["task"] != task_id:
            continue
        missing = [item for item in check["must_preserve"] if normalize(item) not in blob_n]
        invented = [
            item
            for item in check["must_not_invent"]
            if item.lower() in blob.lower() and item not in instruction
        ]
        out.append(
            {
                "id": check["id"],
                "label": check["label"],
                "preserved": not missing,
                "missing": missing,
                "invented": invented,
                "ok": not missing and not invented,
            }
        )
    return out


def gate_verdict(
    *,
    held: dict[str, Any],
    glm_held: dict[str, Any],
    gpt_held: dict[str, Any],
    glm_overall: dict[str, Any],
    gpt_overall: dict[str, Any],
    comparison: list[dict[str, Any]],
    n_ambiguous: int,
    n_evaluable: int,
) -> dict[str, str]:
    if n_evaluable == 0 or n_ambiguous > 0.4 * max(n_evaluable, 1):
        return {
            "gate": "INVALID_EVALUATION",
            "conclusion": "Oracle obligations cannot be scored deterministically enough to support the claims.",
        }
    held_rate = held.get("TASK_SPEC_PRESERVATION_RATE") or 0
    held_crit = held.get("CRITICAL_REQUIREMENT_RECALL") or 0
    invention = (glm_held.get("invention_tasks") or 0) + (gpt_held.get("invention_tasks") or 0)
    gpt_better = (gpt_overall.get("TASK_SPEC_PRESERVATION_RATE") or 0) - (
        glm_overall.get("TASK_SPEC_PRESERVATION_RATE") or 0
    )
    cats = Counter(row["category"] for row in comparison)
    both_fail = cats["BOTH_FAIL_SAME_REQUIREMENT"] + cats["BOTH_FAIL_DIFFERENTLY"]
    if held_rate >= 0.75 and held_crit >= 0.8 and invention <= max(2, 0.15 * (held.get("n_evaluable") or 1)):
        return {
            "gate": "STRONG",
            "conclusion": (
                "Task text can be compiled into the frozen obligation representation "
                "with little specification loss."
            ),
        }
    if both_fail >= 0.5 * max(len(comparison), 1) and gpt_better < 0.15:
        if held_rate < 0.35:
            return {
                "gate": "WEAK",
                "conclusion": (
                    "Both models frequently omit or invent obligations; critical "
                    "distinctions are not reliably preserved."
                ),
            }
        return {
            "gate": "PARTIAL / REPRESENTATION-USABILITY",
            "conclusion": (
                "Both models repeatedly misparse the same V1 distinctions despite "
                "clear task text."
            ),
        }
    if gpt_better >= 0.15 or held_rate >= 0.4:
        return {
            "gate": "PARTIAL / MODEL_LIMITED",
            "conclusion": (
                "The task IR is viable, but compilation quality is a model "
                "capability / decomposition problem."
            ),
        }
    return {
        "gate": "WEAK",
        "conclusion": (
            "Both models frequently omit or invent obligations; do not proceed "
            "directly to agent use."
        ),
    }


SCHEMA_NAME = "TASK_OBLIGATION_SHAPE_V1"
