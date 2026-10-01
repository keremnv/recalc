"""Deterministic task-conditioned retrieval over a workbook grounding spine.

Goldens are evaluator-side labels only. Retrieval never sees them.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from formula_schema import jaccard, normalize_text, parse_period, tokens
from workbook_grounding_spine import (
    JACCARD_MIN,
    RETRIEVAL_RULES,
    cell_id,
    col_id,
    compact_text,
    id_in_spine,
    parse_cell_id,
    row_id,
    sheet_id,
    title_initials,
    tokens_of,
)

ALL_SCOPE = re.compile(r"\b(all|each|every|entire)\b", re.I)
YEAR_TOKEN = re.compile(r"(?:fy|fye|cy)?\s*'?((?:19|20)\d{2}|\d{2})[a-z]?", re.I)
MONTH_YEAR = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*-?\s*(\d{2,4})",
    re.I,
)
SOURCE_ARG = re.compile(
    r"\b(?:using|from|based on|percentage of|as a percentage of|linked to|"
    r"by applying|by growing|by summing)\s+(.+)$",
    re.I,
)
LOCUS_BODY = re.compile(
    r"(?:in|on)\s+the\s+(.+?)(?:\s+(?:sheet|tab|section)\b|$)",
    re.I,
)


def field_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, dict) and "text" in node:
        return str(node.get("text") or "")
    if isinstance(node, list):
        return " ".join(field_text(item) for item in node)
    return str(node)


def lexical_hit(query: str, target: str) -> dict[str, Any] | None:
    q = (query or "").strip()
    t = (target or "").strip()
    if not q or not t:
        return None
    qn, tn = normalize_text(q), normalize_text(t)
    qc, tc = compact_text(q), compact_text(t)
    rules = []
    if qn == tn:
        rules.append("exact_norm")
    if qc and qc == tc:
        rules.append("compact")
    if len(qn) >= 4 and (qn in tn or tn in qn):
        rules.append("substring")
    qt, tt = tokens_of(q), tokens_of(t)
    jac = 0.0
    if qt and tt:
        jac = len(qt & tt) / len(qt | tt)
        if jac + 1e-12 >= JACCARD_MIN:
            rules.append("jaccard")
        if qt <= tt:
            rules.append("token_subset")
        for a in qt:
            for b in tt:
                if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
                    rules.append("token_prefix")
                    break
    if not rules:
        return None
    return {"rules": rules, "jaccard": round(jac, 4)}


def sheet_hit(query: str, sheet: dict[str, Any]) -> dict[str, Any] | None:
    title = sheet["title"]
    hit = lexical_hit(query, title)
    qn = normalize_text(query)
    qc = compact_text(query)
    extra = []
    if qc and qc == sheet.get("title_compact"):
        extra.append("compact_title")
    initials = sheet.get("initials") or title_initials(title)
    if qn in initials or compact_text(query) in initials:
        extra.append("initials")
    if hit or extra:
        rules = list((hit or {}).get("rules") or []) + extra
        return {"sheet_id": sheet["id"], "title": title, "rules": sorted(set(rules))}
    return None


def locus_queries(obligation: dict[str, Any]) -> list[str]:
    raw = field_text(obligation.get("locus"))
    if not raw:
        return []
    queries = [raw]
    m = LOCUS_BODY.search(raw)
    if m:
        queries.append(m.group(1).strip())
    return queries


def subject_queries(obligation: dict[str, Any]) -> list[str]:
    out = []
    sub = field_text(obligation.get("subject"))
    if sub:
        out.append(sub)
        # split compound lists on commas / and
        for part in re.split(r"\s*,\s*|\s+and\s+", sub):
            part = part.strip(" .;")
            if part and part not in out and len(tokens_of(part)) >= 1:
                out.append(part)
    interval = obligation.get("subject_interval") or {}
    if isinstance(interval, dict):
        for key in ("from", "to"):
            text = field_text(interval.get(key))
            if text:
                out.append(text)
    return [q for q in out if q]


def source_queries(obligation: dict[str, Any]) -> list[str]:
    raw = field_text(obligation.get("source_relation"))
    if not raw:
        return []
    out = [raw]
    m = SOURCE_ARG.search(raw)
    if m:
        arg = m.group(1).strip(" .;")
        if arg:
            out.append(arg)
            for part in re.split(r"\s*,\s*|\s+and\s+", arg):
                part = re.sub(r"^(the|a|an)\s+", "", part.strip(), flags=re.I)
                if part:
                    out.append(part)
    return out


def _expand_year(token: str) -> int | None:
    digits = re.sub(r"\D", "", token)
    if len(digits) == 4:
        year = int(digits)
        return year if 1990 <= year <= 2100 else None
    if len(digits) == 2:
        return 2000 + int(digits)
    return None


def parse_scope_spec(obligation: dict[str, Any]) -> dict[str, Any]:
    texts = []
    scope = obligation.get("scope") or []
    if isinstance(scope, list):
        texts = [field_text(item) for item in scope]
    else:
        texts = [field_text(scope)]
    blob = " ".join(texts)
    all_flag = bool(ALL_SCOPE.search(blob))
    years: set[int] = set()
    months: list[tuple[int, int]] = []
    found = list(YEAR_TOKEN.finditer(blob))
    vals = []
    for match in found:
        year = _expand_year(match.group(1))
        if year:
            vals.append(year)
    if len(vals) >= 2:
        lo, hi = min(vals), max(vals)
        if hi - lo <= 40:
            years.update(range(lo, hi + 1))
        else:
            years.update(vals)
    else:
        years.update(vals)
    for match in MONTH_YEAR.finditer(blob):
        period = parse_period(match.group(0).replace("-", " "))
        if period and "year" in period:
            years.add(period["year"])
            if "month" in period:
                months.append((period["year"], period["month"]))
    return {"all": all_flag, "years": sorted(years), "months": months, "raw": texts}


def retrieve_locus(spine: dict[str, Any], obligation: dict[str, Any]) -> list[dict[str, Any]]:
    hits = []
    seen = set()
    for query in locus_queries(obligation):
        for sheet in spine.get("sheets") or []:
            rec = sheet_hit(query, sheet)
            if rec and rec["sheet_id"] not in seen:
                seen.add(rec["sheet_id"])
                hits.append(rec)
    return hits


def retrieve_text(
    spine: dict[str, Any],
    queries: list[str],
    *,
    sheet_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    hits = []
    seen = set()
    for query in queries:
        for anchor in spine.get("text_anchors") or []:
            if sheet_ids and anchor["sheet_id"] not in sheet_ids:
                continue
            rel = lexical_hit(query, anchor["text"])
            if not rel:
                continue
            if anchor["id"] in seen:
                continue
            seen.add(anchor["id"])
            hits.append(
                {
                    "id": anchor["id"],
                    "cell_id": anchor["cell_id"],
                    "row_id": anchor["row_id"],
                    "col_id": anchor["col_id"],
                    "sheet_id": anchor["sheet_id"],
                    "text": anchor["text"],
                    "address": anchor["address"],
                    "query": query,
                    "rules": rel["rules"],
                    "neighbor_left": anchor.get("neighbor_left"),
                    "neighbor_right": anchor.get("neighbor_right"),
                }
            )
    return hits


def retrieve_scope(
    spine: dict[str, Any],
    obligation: dict[str, Any],
    *,
    sheet_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    spec = parse_scope_spec(obligation)
    hits = []
    for period in spine.get("periods") or []:
        if sheet_ids and period["sheet_id"] not in sheet_ids:
            continue
        p = period.get("period") or {}
        ok = False
        if spec["all"]:
            ok = True
        if spec["years"] and p.get("year") in spec["years"]:
            ok = True
        if spec["months"] and (p.get("year"), p.get("month")) in spec["months"]:
            ok = True
        if not spec["all"] and not spec["years"] and not spec["months"]:
            # no explicit period: do not match everything
            continue
        if ok:
            hits.append(
                {
                    "id": period["id"],
                    "cell_id": period["cell_id"],
                    "col_id": period["col_id"],
                    "row_id": period["row_id"],
                    "sheet_id": period["sheet_id"],
                    "period_key": period.get("period_key"),
                    "header_text": period.get("header_text"),
                    "address": period.get("address"),
                    "axis": period.get("axis") or "column",
                    "period": p,
                    "encoding_class": period.get("encoding_class"),
                }
            )
    return hits


def occupancy_keep(kind: str, filter_text: str | None) -> bool:
    if not filter_text:
        return True
    n = normalize_text(filter_text)
    if "not hardcoded" in n or "not hard coded" in n:
        return kind in {"blank", "formula", "error"}
    return True


def _sheet_index(sid: str) -> int:
    return int(sid.rsplit("s", 1)[1])


def compose_targets(
    spine: dict[str, Any],
    *,
    locus_ids: set[str],
    subject_hits: list[dict[str, Any]],
    scope_hits: list[dict[str, Any]],
    occupancy_text: str | None,
    strict_scope: bool = False,
) -> list[str]:
    if not locus_ids:
        return []
    rows = {h["row_id"] for h in subject_hits if h.get("row_id")}
    col_axis = [h for h in scope_hits if (h.get("axis") or "column") != "row"]
    row_axis = [h for h in scope_hits if h.get("axis") == "row"]
    cols = {h["col_id"] for h in col_axis if h.get("col_id")}
    scope_rows = {h["row_id"] for h in row_axis if h.get("row_id")}
    occupied = {(rec["sheet_id"], rec["row"], rec["col"]): rec["kind"] for rec in spine.get("occupied") or []}
    out: list[str] = []
    seen: set[str] = set()

    def _add(sid: str, row: int, col: int) -> None:
        s_i = _sheet_index(sid)
        eid = cell_id(s_i, row, col)
        if eid in seen or not id_in_spine(spine, eid):
            return
        kind = occupied.get((sid, row, col), "blank")
        if not occupancy_keep(kind, occupancy_text):
            return
        seen.add(eid)
        out.append(eid)

    if rows and cols:
        for sid in locus_ids:
            s_i = _sheet_index(sid)
            for rid in rows:
                if not rid.startswith(f"row:s{s_i:02d}:"):
                    continue
                row = int(rid.rsplit("r", 1)[1])
                for cid in cols:
                    if not cid.startswith(f"col:s{s_i:02d}:"):
                        continue
                    col = int(cid.rsplit("c", 1)[1])
                    _add(sid, row, col)
        return out
    if scope_rows:
        subject_cols = {h["col_id"] for h in subject_hits if h.get("col_id")}
        for sid in locus_ids:
            s_i = _sheet_index(sid)
            for rid in scope_rows:
                if not rid.startswith(f"row:s{s_i:02d}:"):
                    continue
                row = int(rid.rsplit("r", 1)[1])
                if subject_cols:
                    for cid in subject_cols:
                        if not cid.startswith(f"col:s{s_i:02d}:"):
                            continue
                        col = int(cid.rsplit("c", 1)[1])
                        _add(sid, row, col)
                elif rows and rid in rows:
                    for rec in spine.get("occupied") or []:
                        if rec["sheet_id"] == sid and rec["row"] == row:
                            _add(sid, rec["row"], rec["col"])
        return out
    if strict_scope:
        return []
    if rows:
        for rec in spine.get("occupied") or []:
            if rec["sheet_id"] not in locus_ids:
                continue
            s_i = _sheet_index(rec["sheet_id"])
            if row_id(s_i, rec["row"]) not in rows:
                continue
            _add(rec["sheet_id"], rec["row"], rec["col"])
    return out


def project_obligation(
    spine: dict[str, Any],
    obligation: dict[str, Any],
    *,
    ablation: set[str] | None = None,
    strict_scope: bool = False,
) -> dict[str, Any]:
    ablation = ablation or set()
    locus = retrieve_locus(spine, obligation)
    locus_ids = {h["sheet_id"] for h in locus}
    subject = retrieve_text(
        spine,
        subject_queries(obligation),
        sheet_ids=locus_ids or None,
    )
    if "NO_LABEL_CONTEXT" in ablation:
        for hit in subject:
            hit.pop("neighbor_left", None)
            hit.pop("neighbor_right", None)
    source = retrieve_text(
        spine,
        source_queries(obligation),
        sheet_ids=None,
    )
    scope = [] if "NO_PERIOD_FACTS" in ablation else retrieve_scope(
        spine, obligation, sheet_ids=locus_ids or None
    )
    occ = field_text(obligation.get("occupancy_filter")) or None
    targets = compose_targets(
        spine,
        locus_ids=locus_ids,
        subject_hits=subject,
        scope_hits=scope,
        occupancy_text=occ,
        strict_scope=strict_scope,
    )
    class_facts = []
    dep_facts = []
    if "NO_FORMULA_CLASS" not in ablation:
        row_ids = {h["row_id"] for h in subject}
        for form in spine.get("formulas") or []:
            m = re.match(r"cell:s(\d+):r(\d+):c(\d+)", form["cell_id"])
            if not m:
                continue
            rid = row_id(int(m.group(1)), int(m.group(2)))
            if rid in row_ids:
                class_facts.append(
                    {
                        "formula_id": form["id"],
                        "class_id": form["class_id"],
                        "opaque": form["opaque"],
                        "cell_id": form["cell_id"],
                    }
                )
                if len(class_facts) >= 80:
                    break
    if "NO_DEPENDENCY_FACTS" not in ablation:
        cand = {h["cell_id"] for h in subject} | {h["cell_id"] for h in source} | set(targets[:200])
        for dep in spine.get("point_deps") or []:
            if dep.get("consumer_id") in cand or dep.get("source_id") in cand:
                dep_facts.append(
                    {
                        "type": "POINT_REFERENCE",
                        "source_id": dep.get("source_id"),
                        "consumer_id": dep.get("consumer_id"),
                        "cross_sheet": dep.get("cross_sheet"),
                    }
                )
                if len(dep_facts) >= 80:
                    break
    packet = {
        "obligation_id": obligation.get("id"),
        "fields": {
            "locus": field_text(obligation.get("locus")) or None,
            "subject": field_text(obligation.get("subject")) or None,
            "scope": [field_text(x) for x in (obligation.get("scope") or [])],
            "source_relation": field_text(obligation.get("source_relation")) or None,
            "occupancy_filter": occ,
            "required_change": field_text(obligation.get("required_change")) or None,
        },
        "locus": locus,
        "subject": subject,
        "scope": scope,
        "source": source,
        "target_cell_ids": targets,
        "formula_class_facts": class_facts,
        "dependency_facts": dep_facts,
        "counts": {
            "n_sheets_universe": len(spine.get("sheets") or []),
            "n_locus": len(locus),
            "n_text_universe": len(spine.get("text_anchors") or []),
            "n_subject": len(subject),
            "n_period_universe": len(spine.get("periods") or []),
            "n_scope": len(scope),
            "n_source": len(source),
            "n_occupied_universe": len(spine.get("occupied") or []),
            "n_target": len(targets),
            "n_s1": len(spine.get("s1_cell_ids") or []),
        },
        "ablation": sorted(ablation),
    }
    return packet


def render_packet(packet: dict[str, Any], *, max_targets: int = 80) -> str:
    slim = {
        "obligation_id": packet["obligation_id"],
        "fields": packet["fields"],
        "locus_candidates": packet["locus"],
        "subject_candidates": [
            {k: h[k] for k in ("id", "cell_id", "row_id", "sheet_id", "text", "address", "rules") if k in h}
            for h in packet["subject"][:80]
        ],
        "scope_candidates": packet["scope"][:80],
        "source_candidates": [
            {k: h[k] for k in ("id", "cell_id", "row_id", "sheet_id", "text", "address") if k in h}
            for h in packet["source"][:40]
        ],
        "target_cell_ids": packet["target_cell_ids"][:max_targets],
        "target_truncated": max(0, len(packet["target_cell_ids"]) - max_targets),
        "formula_class_facts": packet["formula_class_facts"][:40],
        "dependency_facts": packet["dependency_facts"][:40],
        "counts": packet["counts"],
    }
    return json.dumps(slim, ensure_ascii=False, indent=2)


def token_estimate(text: str) -> int:
    return max(1, len(text) // 4)


# --- evaluator-side gold association (never passed to resolver) ---

def gold_entities(spine: dict[str, Any], change: dict[str, Any]) -> dict[str, str | None]:
    title = change["sheet"]
    s_i = (spine.get("title_to_index") or {}).get(title)
    if s_i is None:
        return {"sheet_id": None, "cell_id": None, "row_id": None, "col_id": None}
    return {
        "sheet_id": sheet_id(s_i),
        "cell_id": cell_id(s_i, change["row"], change["col"]),
        "row_id": row_id(s_i, change["row"]),
        "col_id": col_id(s_i, change["col"]),
        "in_spine": id_in_spine(spine, cell_id(s_i, change["row"], change["col"])),
    }


def row_labels(spine: dict[str, Any], sheet_id_s: str, row: int) -> list[str]:
    return [
        a["text"]
        for a in spine.get("text_anchors") or []
        if a["sheet_id"] == sheet_id_s and a["row"] == row
    ]


def associate_gold(
    spine: dict[str, Any],
    obligations: list[dict[str, Any]],
    packets: list[dict[str, Any]],
    change: dict[str, Any],
) -> dict[str, Any]:
    ents = gold_entities(spine, change)
    labels = row_labels(spine, ents["sheet_id"], change["row"]) if ents["sheet_id"] else []
    matched = []
    for ob, packet in zip(obligations, packets):
        reasons = []
        if ents["sheet_id"] and ents["sheet_id"] in {h["sheet_id"] for h in packet["locus"]}:
            reasons.append("locus_sheet")
        subj = subject_queries(ob)
        if any(lexical_hit(q, lab) for q in subj for lab in labels):
            reasons.append("subject_label")
        if reasons:
            matched.append({"obligation_id": ob.get("id"), "reasons": reasons})
    return {
        "entities": ents,
        "labels": labels[:6],
        "matched_obligations": matched,
        "explainable": bool(matched),
    }


RESOLVER_PROMPT = """\
You bind a lifted task obligation to workbook entity IDs from the supplied grounding packet.

You may ONLY return entity IDs that appear in the packet. Do not invent sheets, rows, cells, formulas, or relations.

Returning multiple candidates is preferable to selecting one without sufficient evidence.
UNRESOLVED is preferable to inventing an entity.
Do not use finance knowledge to invent relationships absent from the packet.
Do not synthesize formulas.

Output JSON only:
{
  "locus": {"status": "RESOLVED|AMBIGUOUS|UNRESOLVED", "candidate_ids": ["..."]},
  "subject": {"status": "...", "candidate_ids": ["..."]},
  "subject_interval": {"status": "...", "candidate_ids": ["..."]},
  "scope": {"status": "...", "candidate_ids": ["..."]},
  "source_relation_arguments": {"status": "...", "candidate_ids": ["..."]},
  "target_region": {"status": "...", "candidate_ids": ["..."]}
}

Status:
- RESOLVED: exactly one candidate is justified
- AMBIGUOUS: more than one packet candidate remains justified
- UNRESOLVED: no packet candidate is justified

candidate_ids must be a subset of IDs in the packet.
"""


def packet_id_universe(packet: dict[str, Any]) -> set[str]:
    ids = set()
    for hit in packet.get("locus") or []:
        ids.add(hit["sheet_id"])
    for key in ("subject", "scope", "source"):
        for hit in packet.get(key) or []:
            for field in ("id", "cell_id", "row_id", "col_id", "sheet_id"):
                if hit.get(field):
                    ids.add(hit[field])
    ids.update(packet.get("target_cell_ids") or [])
    for fact in packet.get("formula_class_facts") or []:
        ids.update([fact.get("formula_id"), fact.get("class_id"), fact.get("cell_id")])
    for fact in packet.get("dependency_facts") or []:
        ids.update([fact.get("source_id"), fact.get("consumer_id")])
    return {i for i in ids if i}


def validate_resolution(payload: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    allowed = packet_id_universe(packet)
    invalid = []
    cleaned = {}
    for field in ("locus", "subject", "subject_interval", "scope", "source_relation_arguments", "target_region"):
        node = payload.get(field) if isinstance(payload, dict) else None
        if not isinstance(node, dict):
            cleaned[field] = {"status": "UNRESOLVED", "candidate_ids": []}
            continue
        ids = [i for i in (node.get("candidate_ids") or []) if isinstance(i, str)]
        bad = [i for i in ids if i not in allowed]
        invalid.extend(bad)
        kept = [i for i in ids if i in allowed]
        status = node.get("status") or "UNRESOLVED"
        if status not in {"RESOLVED", "AMBIGUOUS", "UNRESOLVED"}:
            status = "UNRESOLVED"
        if bad and not kept:
            status = "UNRESOLVED"
        if status == "RESOLVED" and len(kept) > 1:
            status = "AMBIGUOUS"
        if status == "RESOLVED" and len(kept) == 0:
            status = "UNRESOLVED"
        cleaned[field] = {"status": status, "candidate_ids": kept, "invalid_ids": bad}
    return {"fields": cleaned, "invalid": invalid}
