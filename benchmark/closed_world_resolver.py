"""Closed-world obligation resolver: eligibility, baselines, and scoring.

Does not compile workbooks, retrieve candidates, or parse tasks.
Goldens are evaluator-side only.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from workbook_grounding import (
    associate_gold,
    field_text,
    gold_entities,
    packet_id_universe,
    parse_scope_spec,
)
from workbook_grounding_spine import parse_cell_id

LAYERS = (
    "locus",
    "subject",
    "scope",
    "source_relation_arguments",
    "target_region",
)
LAYER_TO_R = {
    "locus": "R0",
    "subject": "R1",
    "scope": "R2",
    "source_relation_arguments": "R3",
    "target_region": "R4",
}
KEEP_ALL_TOKEN = "KEEP_ALL"
STATUSES = {"RESOLVED", "AMBIGUOUS", "UNRESOLVED"}
BUCKETS = ("1", "2", "3-5", "6-10", "11-50", ">50")

FORMULA_LEAK = re.compile(
    r"(?:=[A-Z]{1,3}\d+|=SUM\s*\(|EOMONTH\s*\(|EDATE\s*\(|"
    r"VLOOKUP\s*\(|XLOOKUP\s*\(|INDEX\s*\(|MATCH\s*\(|"
    r"/\s*365|\*\s*365)",
    re.I,
)

RESOLVER_PROMPT = """\
You are binding a task specification to entities in a closed workbook world.

Every entity you may return already exists in the candidate packet.
Never invent workbook facts.
Never create a cell, row, sheet, formula, source relation, workbook label, or entity ID.

Preserve multiple candidates whenever supplied evidence does not justify choosing one.
Returning AMBIGUOUS is preferable to choosing a candidate without sufficient evidence.
Returning UNRESOLVED is preferable to inventing a relationship.
Do not synthesize formulas or reason from finance conventions not present in the packet.
Your job is to eliminate candidates only when the supplied task constraints and workbook facts justify elimination.

You bind one ORACLE obligation to packet entity IDs. The packet already contains mechanically retrieved locus, subject, scope, source, occupancy-relevant, and composed-target candidates plus the workbook facts that were compiled into this packet. Use only those facts.

Output JSON only, no markdown, no formula, no free-form rationale:

{
  "locus": {"status": "RESOLVED|AMBIGUOUS|UNRESOLVED", "candidate_ids": ["..."], "evidence_ids": ["..."]},
  "subject": {"status": "RESOLVED|AMBIGUOUS|UNRESOLVED", "candidate_ids": ["..."], "evidence_ids": ["..."]},
  "subject_interval": {"status": "RESOLVED|AMBIGUOUS|UNRESOLVED", "candidate_ids": ["..."], "evidence_ids": ["..."]},
  "scope": {"status": "RESOLVED|AMBIGUOUS|UNRESOLVED", "candidate_ids": ["..."], "evidence_ids": ["..."]},
  "source_relation_arguments": {"status": "RESOLVED|AMBIGUOUS|UNRESOLVED", "candidate_ids": ["..."], "evidence_ids": ["..."]},
  "target_region": {"status": "RESOLVED|AMBIGUOUS|UNRESOLVED", "candidate_ids": ["..."], "evidence_ids": ["..."]}
}

Status:
- RESOLVED: exactly one candidate is justified by packet evidence.
- AMBIGUOUS: multiple candidates remain materially plausible. This is a valid successful outcome.
- UNRESOLVED: the packet does not provide enough evidence to bind the task phrase reliably.

Rules:
- candidate_ids must be a subset of IDs listed in the packet for that field.
- evidence_ids must be packet entity/fact IDs that support the narrowing. Every evidence ID must exist in the packet.
- Return IDs exactly as listed (sheet_id, text-anchor id, period id, or cell_id).
- If you retain every supplied candidate for a field, set candidate_ids to ["KEEP_ALL"]. Do not use KEEP_ALL if you eliminated any candidate.
- If a field has no candidates or does not apply, return status UNRESOLVED and empty lists.
- Do not mention Excel formulas. Do not compute values.
"""

RESOLVER_SCHEMA = {
    "fields": list(LAYERS) + ["subject_interval"],
    "status": sorted(STATUSES),
    "required_keys": ["status", "candidate_ids", "evidence_ids"],
    "keep_all_token": KEEP_ALL_TOKEN,
}

COMPATIBILITY_RULES = {
    "locus": "Gold sheet_id of associated semantic changes that appear among packet locus sheet_ids.",
    "subject": (
        "Packet subject hits (text-anchor id, cell_id, row_id) whose row_id equals "
        "the gold row of an associated semantic change."
    ),
    "scope": (
        "Packet scope hits whose col_id equals the gold column (column-axis) or whose "
        "row_id equals the gold row (row-axis). Unparsed task scopes are not scored."
    ),
    "source_relation_arguments": (
        "Packet source hits on rows of gold-formula refs_added cells, or on the gold row "
        "when the source argument names the same line. Scored only when source_relation is present."
    ),
    "target_region": "Gold cell_id of associated semantic changes present in packet target_cell_ids.",
    "premature": (
        "Unique output while mechanically co-compatible input IDs remain: "
        "locus/subject/source hits sharing the gold hit match-rule set; "
        "scope hits covering a multi-period task spec; "
        "target sets with more than one composed cell."
    ),
}


def layer_input_ids(packet: dict[str, Any], layer: str) -> list[str]:
    if layer == "locus":
        return [h["sheet_id"] for h in packet.get("locus") or [] if h.get("sheet_id")]
    if layer == "subject":
        return [h["id"] for h in packet.get("subject") or [] if h.get("id")]
    if layer == "scope":
        return [h["id"] for h in packet.get("scope") or [] if h.get("id")]
    if layer == "source_relation_arguments":
        return [h["id"] for h in packet.get("source") or [] if h.get("id")]
    if layer == "target_region":
        return list(packet.get("target_cell_ids") or [])
    return []


def _hit_ids(hit: dict[str, Any]) -> set[str]:
    return {hit[k] for k in ("id", "cell_id", "row_id", "col_id", "sheet_id") if hit.get(k)}


def gold_compatible_ids(
    packet: dict[str, Any],
    layer: str,
    gold_ents: list[dict[str, Any]],
    *,
    ref_cells: set[str] | None = None,
) -> set[str]:
    gold_sheets = {e.get("sheet_id") for e in gold_ents if e.get("sheet_id")}
    gold_rows = {e.get("row_id") for e in gold_ents if e.get("row_id")}
    gold_cols = {e.get("col_id") for e in gold_ents if e.get("col_id")}
    gold_cells = {e.get("cell_id") for e in gold_ents if e.get("cell_id")}
    if layer == "locus":
        return {i for i in layer_input_ids(packet, layer) if i in gold_sheets}
    if layer == "subject":
        out: set[str] = set()
        for hit in packet.get("subject") or []:
            if hit.get("row_id") in gold_rows:
                out.update(_hit_ids(hit))
        return out
    if layer == "scope":
        out = set()
        for hit in packet.get("scope") or []:
            axis = hit.get("axis") or "column"
            if axis == "row" and hit.get("row_id") in gold_rows:
                out.update(_hit_ids(hit))
            elif axis != "row" and hit.get("col_id") in gold_cols:
                out.update(_hit_ids(hit))
        return out
    if layer == "source_relation_arguments":
        out = set()
        ref_rows = set()
        for cid in ref_cells or set():
            parsed = parse_cell_id(cid)
            if parsed:
                idx, row, _col = parsed
                ref_rows.add(f"row:s{idx:02d}:r{row}")
        for hit in packet.get("source") or []:
            if hit.get("row_id") in gold_rows or hit.get("row_id") in ref_rows or hit.get("cell_id") in (ref_cells or set()):
                out.update(_hit_ids(hit))
        return out
    if layer == "target_region":
        return {i for i in layer_input_ids(packet, layer) if i in gold_cells}
    return set()


def match_rule_key(hit: dict[str, Any]) -> tuple[str, ...]:
    rules = hit.get("rules") or []
    return tuple(sorted(rules))


def coambiguous_ids(packet: dict[str, Any], layer: str, gold_ids: set[str], obligation: dict[str, Any]) -> set[str]:
    inputs = set(layer_input_ids(packet, layer))
    if layer == "target_region":
        return inputs
    if layer == "scope":
        spec = parse_scope_spec(obligation)
        multi = bool(spec.get("all")) or len(spec.get("years") or []) > 1 or len(spec.get("months") or []) > 1
        if multi:
            return inputs
        gold_hits = [h for h in (packet.get("scope") or []) if gold_ids & _hit_ids(h)]
        keys = {
            ((h.get("period") or {}).get("year"), (h.get("period") or {}).get("month"))
            for h in gold_hits
        }
        years = {year for year, _month in keys}
        out = set()
        for hit in packet.get("scope") or []:
            period = hit.get("period") or {}
            if (period.get("year"), period.get("month")) in keys or period.get("year") in years:
                if hit.get("id"):
                    out.add(hit["id"])
        return out or (gold_ids & inputs)
    key_name = {"locus": "locus", "subject": "subject", "source_relation_arguments": "source"}.get(layer)
    if not key_name:
        return gold_ids & inputs
    gold_keys = {match_rule_key(h) for h in packet.get(key_name) or [] if gold_ids & _hit_ids(h)}
    out = set()
    for hit in packet.get(key_name) or []:
        if match_rule_key(hit) in gold_keys:
            ident = hit.get("sheet_id") if layer == "locus" else hit.get("id")
            if ident:
                out.add(ident)
    return out or (gold_ids & inputs)


def scope_unparsed(obligation: dict[str, Any]) -> bool:
    text = field_text(obligation.get("scope"))
    if not text:
        return False
    spec = parse_scope_spec(obligation)
    return not (spec["all"] or spec["years"] or spec["months"])


def classify_eligibility(
    packet: dict[str, Any],
    obligation: dict[str, Any],
    gold_ents: list[dict[str, Any]],
    *,
    ref_cells: set[str] | None = None,
    rendered_ids: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    rendered_ids = rendered_ids or {layer: layer_input_ids(packet, layer) for layer in LAYERS}
    out = {}
    for layer in LAYERS:
        inputs = list(rendered_ids.get(layer) or [])
        gold = gold_compatible_ids(packet, layer, gold_ents, ref_cells=ref_cells) & set(inputs)
        reason = None
        applicable = True
        if layer == "locus":
            applicable = bool(field_text(obligation.get("locus")))
        elif layer == "subject":
            applicable = bool(field_text(obligation.get("subject")))
        elif layer == "scope":
            if not field_text(obligation.get("scope")):
                applicable = False
            elif scope_unparsed(obligation):
                applicable = False
                reason = "TASK_SCOPE_UNPARSED"
        elif layer == "source_relation_arguments":
            applicable = bool(field_text(obligation.get("source_relation")))
        elif layer == "target_region":
            applicable = True
        if not applicable:
            status = "NOT_APPLICABLE" if reason is None else "TASK_SCOPE_UNPARSED"
        elif not gold_ents:
            status = "NO_GOLD_ASSOCIATION"
        elif not inputs:
            status = "UPSTREAM_MISSING"
            reason = reason or "empty_candidates"
        elif not gold:
            status = "UPSTREAM_MISSING"
            reason = reason or "gold_absent_from_packet"
        else:
            status = "ELIGIBLE"
        out[layer] = {
            "status": status,
            "reason": reason,
            "n_input": len(inputs),
            "n_gold": len(gold),
            "input_ids": inputs,
            "gold_ids": sorted(gold),
            "coambiguous_ids": sorted(coambiguous_ids(packet, layer, gold, obligation) & set(inputs))
            if status == "ELIGIBLE"
            else [],
        }
    return out


def packet_callable(eligibility: dict[str, Any]) -> bool:
    return any(rec["status"] == "ELIGIBLE" for rec in eligibility.values())


def evidence_available(packet: dict[str, Any]) -> list[str]:
    tags = []
    subj = packet.get("subject") or []
    if any("exact_norm" in (h.get("rules") or []) for h in subj):
        tags.append("exact text match")
    if any(h.get("rules") and "exact_norm" not in (h.get("rules") or []) for h in subj):
        tags.append("normalized text match")
    if packet.get("locus"):
        tags.append("locus agreement")
    if subj:
        tags.append("subject context")
    if packet.get("scope"):
        tags.append("period compatibility")
    if packet.get("formula_class_facts"):
        tags.append("formula-class context")
    deps = packet.get("dependency_facts") or []
    if any((d.get("type") or "").upper().startswith("POINT") for d in deps):
        tags.append("point dependency")
    if any((d.get("type") or "").upper().find("RANGE") >= 0 for d in deps):
        tags.append("range dependency")
    if any(d.get("cross_sheet") for d in deps):
        tags.append("cross-sheet relation")
    if field_text((packet.get("fields") or {}).get("occupancy_filter")):
        tags.append("occupancy")
    if any(h.get("neighbor_left") or h.get("neighbor_right") for h in subj):
        tags.append("local neighboring text")
    return tags


def validate_resolution(
    payload: dict[str, Any] | None,
    packet: dict[str, Any],
    *,
    input_ids: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    allowed = packet_id_universe(packet)
    allowed.add(KEEP_ALL_TOKEN)
    input_ids = input_ids or {layer: layer_input_ids(packet, layer) for layer in LAYERS}
    invalid: list[str] = []
    cleaned: dict[str, Any] = {}
    fields = list(LAYERS) + ["subject_interval"]
    for field in fields:
        node = payload.get(field) if isinstance(payload, dict) else None
        inputs = input_ids.get(field) or layer_input_ids(packet, field)
        if not isinstance(node, dict):
            cleaned[field] = {
                "status": "UNRESOLVED",
                "candidate_ids": [],
                "evidence_ids": [],
                "invalid_ids": [],
                "keep_all": False,
            }
            continue
        raw_ids = [i for i in (node.get("candidate_ids") or []) if isinstance(i, str)]
        raw_ev = [i for i in (node.get("evidence_ids") or []) if isinstance(i, str)]
        keep_all = KEEP_ALL_TOKEN in raw_ids
        if keep_all:
            ids = list(inputs)
        else:
            ids = raw_ids
        bad = [i for i in ids if i not in allowed]
        bad_ev = [i for i in raw_ev if i not in allowed]
        invalid.extend(bad)
        invalid.extend(bad_ev)
        kept = [i for i in ids if i in allowed and i != KEEP_ALL_TOKEN]
        ev = [i for i in raw_ev if i in allowed]
        status = node.get("status") or "UNRESOLVED"
        if status not in STATUSES:
            status = "UNRESOLVED"
        if bad and not kept:
            status = "UNRESOLVED"
        if keep_all:
            status = "RESOLVED" if len(kept) == 1 else ("AMBIGUOUS" if kept else "UNRESOLVED")
        if status == "RESOLVED" and len(kept) > 1:
            status = "AMBIGUOUS"
        if status == "RESOLVED" and len(kept) == 0:
            status = "UNRESOLVED"
        if status == "AMBIGUOUS" and len(kept) == 1:
            status = "RESOLVED"
        cleaned[field] = {
            "status": status,
            "candidate_ids": kept,
            "evidence_ids": ev,
            "invalid_ids": bad + bad_ev,
            "keep_all": keep_all,
        }
    return {
        "fields": cleaned,
        "invalid": invalid,
        "invalid_entity_reference": bool(invalid),
    }


def baseline_keep_all(packet: dict[str, Any], input_ids: dict[str, list[str]]) -> dict[str, Any]:
    payload = {}
    for layer in list(LAYERS) + ["subject_interval"]:
        ids = input_ids.get(layer) or []
        payload[layer] = {
            "status": "RESOLVED" if len(ids) == 1 else ("AMBIGUOUS" if ids else "UNRESOLVED"),
            "candidate_ids": [KEEP_ALL_TOKEN] if ids else [],
            "evidence_ids": [],
        }
    return validate_resolution(payload, packet, input_ids=input_ids)


def _strongest_exact(hits: list[dict[str, Any]]) -> list[str]:
    exact = []
    weaker = []
    for hit in hits:
        ident = hit.get("sheet_id") if "title" in hit else hit.get("id")
        if not ident:
            continue
        rules = set(hit.get("rules") or [])
        if "exact_norm" in rules or "compact" in rules or "compact_title" in rules:
            exact.append(ident)
        else:
            weaker.append(ident)
    if len(set(exact)) == 1 and weaker:
        return [exact[0]]
    return [h.get("sheet_id") if "title" in h else h.get("id") for h in hits if (h.get("sheet_id") if "title" in h else h.get("id"))]


def baseline_exact_match(packet: dict[str, Any], input_ids: dict[str, list[str]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    locus_ids = _strongest_exact(packet.get("locus") or [])
    subj_ids = _strongest_exact(packet.get("subject") or [])
    src_ids = _strongest_exact(packet.get("source") or [])
    mapping = {
        "locus": locus_ids or input_ids.get("locus") or [],
        "subject": subj_ids or input_ids.get("subject") or [],
        "scope": input_ids.get("scope") or [],
        "source_relation_arguments": src_ids or input_ids.get("source_relation_arguments") or [],
        "target_region": input_ids.get("target_region") or [],
        "subject_interval": [],
    }
    for layer, ids in mapping.items():
        orig = input_ids.get(layer) or []
        narrowed = list(dict.fromkeys([i for i in ids if i in set(orig)])) or orig
        payload[layer] = {
            "status": "RESOLVED" if len(narrowed) == 1 else ("AMBIGUOUS" if narrowed else "UNRESOLVED"),
            "candidate_ids": [KEEP_ALL_TOKEN] if narrowed == orig and orig else narrowed,
            "evidence_ids": [],
        }
    return validate_resolution(payload, packet, input_ids=input_ids)


def count_bucket(n: int) -> str:
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    if n <= 5:
        return "3-5"
    if n <= 10:
        return "6-10"
    if n <= 50:
        return "11-50"
    return ">50"


def classify_output(
    *,
    input_ids: list[str],
    output_ids: list[str],
    gold_ids: set[str],
    coambiguous_ids: set[str],
    status: str,
    invalid: bool,
) -> dict[str, Any]:
    inputs = list(dict.fromkeys(input_ids))
    outputs = list(dict.fromkeys(output_ids))
    gold = set(gold_ids)
    retained = set(outputs) & gold
    if not outputs:
        false_elim = False
    else:
        false_elim = bool(gold) and not retained
    if not outputs:
        category = "UNRESOLVED_SAFE"
    elif false_elim and len(outputs) == 1:
        category = "WRONG_UNIQUE"
    elif false_elim:
        category = "GOLD_DROPPED"
    elif set(outputs) == set(inputs):
        category = "NO_REDUCTION_SAFE"
    elif len(outputs) == 1:
        category = "CORRECT_UNIQUE"
    else:
        category = "CORRECT_AMBIGUOUS"
    safe_reduction = (not false_elim) and len(outputs) < len(inputs) and bool(retained)
    premature = (
        len(outputs) == 1
        and len(set(coambiguous_ids) | gold) > 1
        and category in {"CORRECT_UNIQUE", "WRONG_UNIQUE", "NO_REDUCTION_SAFE"}
    )
    if category == "CORRECT_UNIQUE" and len(set(coambiguous_ids)) > 1:
        premature = True
    return {
        "category": category,
        "false_elimination": false_elim,
        "safe_reduction": safe_reduction,
        "premature_resolution": premature,
        "unresolved": status == "UNRESOLVED" or category == "UNRESOLVED_SAFE",
        "n_input": len(inputs),
        "n_output": len(outputs),
        "reduction_ratio": round(len(outputs) / len(inputs), 4) if inputs else None,
        "gold_retained": sorted(retained),
        "bucket": count_bucket(len(inputs)),
        "invalid_entity_reference": invalid,
    }


def formula_synthesis_leakage(raw_text: str | None) -> bool:
    if not raw_text:
        return False
    return bool(FORMULA_LEAK.search(raw_text))


def associated_gold(
    spine: dict[str, Any],
    obligation: dict[str, Any],
    packet: dict[str, Any],
    changes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    gold_ents = []
    matched_changes = []
    refs: set[str] = set()
    for change in changes:
        assoc = associate_gold(spine, [obligation], [packet], change)
        if not assoc["explainable"]:
            continue
        ents = gold_entities(spine, change)
        gold_ents.append(ents)
        matched_changes.append(change)
        title_to = spine.get("title_to_index") or {}
        for ref in change.get("refs_added") or []:
            if "!" in ref:
                sheet, addr = ref.split("!", 1)
            else:
                sheet, addr = change["sheet"], ref
            idx = title_to.get(sheet)
            if idx is None:
                continue
            col_letters = "".join(ch for ch in addr if ch.isalpha())
            row_digits = "".join(ch for ch in addr if ch.isdigit())
            if not col_letters or not row_digits:
                continue
            from fingerprint import column_number

            refs.add(f"cell:s{int(idx):02d}:r{int(row_digits)}:c{column_number(col_letters)}")
    return gold_ents, matched_changes, refs


def aggregate_scores(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows) or 1
    cats = Counter(r["category"] for r in rows)
    return {
        "n": len(rows),
        "FALSE_ELIMINATION_RATE": round(sum(1 for r in rows if r["false_elimination"]) / n, 4) if rows else None,
        "SAFE_REDUCTION_RATE": round(sum(1 for r in rows if r["safe_reduction"]) / n, 4) if rows else None,
        "mean_reduction_ratio": round(
            sum(r["reduction_ratio"] or 1 for r in rows) / n, 4
        )
        if rows
        else None,
        "mean_reduction_among_safe": round(
            sum((r["reduction_ratio"] or 1) for r in rows if r["safe_reduction"])
            / max(1, sum(1 for r in rows if r["safe_reduction"])),
            4,
        )
        if any(r["safe_reduction"] for r in rows)
        else None,
        "CORRECT_UNIQUE": round(cats["CORRECT_UNIQUE"] / n, 4) if rows else None,
        "CORRECT_AMBIGUOUS": round(cats["CORRECT_AMBIGUOUS"] / n, 4) if rows else None,
        "NO_REDUCTION_SAFE": round(cats["NO_REDUCTION_SAFE"] / n, 4) if rows else None,
        "WRONG_UNIQUE": round(cats["WRONG_UNIQUE"] / n, 4) if rows else None,
        "GOLD_DROPPED": round(cats["GOLD_DROPPED"] / n, 4) if rows else None,
        "UNRESOLVED_SAFE": round(cats["UNRESOLVED_SAFE"] / n, 4) if rows else None,
        "PREMATURE_RESOLUTION_RATE": round(sum(1 for r in rows if r["premature_resolution"]) / n, 4)
        if rows
        else None,
        "INVALID_ENTITY_REFERENCE_RATE": round(sum(1 for r in rows if r["invalid_entity_reference"]) / n, 4)
        if rows
        else None,
        "categories": dict(cats),
        "buckets": {
            name: {
                "n": sum(1 for r in rows if r["bucket"] == name),
                "FALSE_ELIMINATION_RATE": round(
                    sum(1 for r in rows if r["bucket"] == name and r["false_elimination"])
                    / max(1, sum(1 for r in rows if r["bucket"] == name)),
                    4,
                ),
                "SAFE_REDUCTION_RATE": round(
                    sum(1 for r in rows if r["bucket"] == name and r["safe_reduction"])
                    / max(1, sum(1 for r in rows if r["bucket"] == name)),
                    4,
                ),
                "CORRECT_UNIQUE": round(
                    sum(1 for r in rows if r["bucket"] == name and r["category"] == "CORRECT_UNIQUE")
                    / max(1, sum(1 for r in rows if r["bucket"] == name)),
                    4,
                ),
                "CORRECT_AMBIGUOUS": round(
                    sum(1 for r in rows if r["bucket"] == name and r["category"] == "CORRECT_AMBIGUOUS")
                    / max(1, sum(1 for r in rows if r["bucket"] == name)),
                    4,
                ),
                "UNRESOLVED_SAFE": round(
                    sum(1 for r in rows if r["bucket"] == name and r["category"] == "UNRESOLVED_SAFE")
                    / max(1, sum(1 for r in rows if r["bucket"] == name)),
                    4,
                ),
            }
            for name in BUCKETS
        },
    }


def compare_models(gpt_rows: list[dict[str, Any]], glm_rows: list[dict[str, Any]]) -> dict[str, Any]:
    g = {(r["job_id"], r["layer"]): r for r in gpt_rows}
    z = {(r["job_id"], r["layer"]): r for r in glm_rows}
    keys = sorted(set(g) & set(z))
    counts = Counter()
    for key in keys:
        a, b = g[key], z[key]
        a_safe = not a["false_elimination"]
        b_safe = not b["false_elimination"]
        if a_safe and b_safe:
            counts["BOTH_SAFE"] += 1
            if a["safe_reduction"] and b["safe_reduction"]:
                ar = a["reduction_ratio"] if a["reduction_ratio"] is not None else 1
                br = b["reduction_ratio"] if b["reduction_ratio"] is not None else 1
                if ar < br:
                    counts["GPT_REDUCES_MORE_SAFE"] += 1
                elif br < ar:
                    counts["GLM_REDUCES_MORE_SAFE"] += 1
            elif a["safe_reduction"] and not b["safe_reduction"]:
                counts["GPT_REDUCES_MORE_SAFE"] += 1
            elif b["safe_reduction"] and not a["safe_reduction"]:
                counts["GLM_REDUCES_MORE_SAFE"] += 1
        elif a_safe and not b_safe:
            counts["GPT_SAFE_GLM_DROPS"] += 1
        elif b_safe and not a_safe:
            counts["GLM_SAFE_GPT_DROPS"] += 1
        else:
            counts["BOTH_DROP"] += 1
    n = len(keys) or 1
    return {"n_paired": len(keys), "counts": dict(counts), "rates": {k: round(v / n, 4) for k, v in counts.items()}}


def advisory_false_elim(authoritative_fe: bool) -> bool:
    """Advisory interface never deletes unpreferred candidates, so FE is 0."""
    return False if authoritative_fe else False
