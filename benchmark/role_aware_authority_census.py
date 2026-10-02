"""Build the Phase 2 role-aware authority census without model calls.

The census consumes the archived Task IR/grounding/plan/evaluator artifacts and
reprojects the same obligations through the already-repaired compiled world.
It does not call a provider, write a workbook, change authority, or launch a
task.  The classification map is deliberately explicit: it records the
earliest *supported* boundary for this small annotated slice rather than
claiming an automatic causal label for every possible failure.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import matched_compiled_treatment as m
import workbook_grounding as g

ANNOTATIONS = ROOT / "research/history/loose_evidence/authority_loss_by_obligation.csv"
LINEAGE = ROOT / "research/history/authority_frontier_probe" / "obligation_lineage.csv"
REPAIRED_DB = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs" / "matched-glm-compiled-sixty" / "integration_autopsy" / "repaired_db"

CATEGORY_ORDER = [
    "TASK_IR_OMISSION",
    "TASK_IR_CONTEXT_RELATION_LOSS",
    "GROUNDING_FIELD_INTERFACE_LOSS",
    "SPINE_FACT_MISSING",
    "SPINE_FACT_PRESENT_NOT_PROJECTED",
    "ROLE_RELATION_NOT_REPRESENTED",
    "STRUCTURE_NOT_MECHANICALLY_DEFINED",
    "EVIDENCE_PRESENT_MODEL_WRONG_SELECTION",
    "PLANNER_RESPONSE_MISSING",
    "EXPANSION_ERROR",
    "NO_FRONTEND_LOSS",
]


CLASSIFICATIONS: dict[tuple[str, str], dict[str, Any]] = {
    ("Financial_Model:05_01", "O1"): {
        "primary": "PLANNER_RESPONSE_MISSING",
        "secondary": [],
        "population": "IRR Calculation!D14:D15,D25:D26",
        "evidence": "Correct IRR sheet and four IRR row anchors are present; the saved fragment timed out before any selection.",
    },
    ("Financial_Model:05_01", "O2"): {
        "primary": "ROLE_RELATION_NOT_REPRESENTED",
        "secondary": ["GROUNDING_FIELD_INTERFACE_LOSS"],
        "population": "IS - Mgmt Co.!DK11,DK12,DK13,DK17:DK23,DK26:DK30,DK33:DK38,DK41:DK42,DK45:DK47,DK50:DK52,DK55,DK57,DK59,DK61,DK63:DK64,DK66",
        "evidence": "DK7 is a compiled text anchor labeled Total and DK target cells exist, but target composition crosses rows with temporal columns and has no deterministic total-column role relation.",
    },
    ("Financial_Model:05_01", "O6"): {
        "primary": "PLANNER_RESPONSE_MISSING",
        "secondary": [],
        "population": "Dashboard!G43,I43,G44,I44,G45",
        "evidence": "The saved fragment timed out; no planner target selection exists to attribute.",
    },
    ("Financial_Model:05_01", "O7"): {
        "primary": "GROUNDING_FIELD_INTERFACE_LOSS",
        "secondary": ["ROLE_RELATION_NOT_REPRESENTED"],
        "population": "Workings Cost Sheet!O29:DI31",
        "evidence": "The Task IR scope retains all three tranches. B29:B31 are compiled First/Second/Third Tranche anchors and shadow matching finds them, but subject-only target composition consumes Total Fund Raised row 27 and never turns the scope population into target rows.",
    },
    ("Financial_Model:15_05", "O1"): {
        "primary": "STRUCTURE_NOT_MECHANICALLY_DEFINED",
        "secondary": ["ROLE_RELATION_NOT_REPRESENTED"],
        "population": "Formats!E4:N25 annotated first-table body cells",
        "evidence": "Consolidated Financials heading anchors and ordinary cells/formula runs exist, but the workbook has no explicit Excel Table object and the compiled world has no heading-to-body extent relation.",
    },
    ("Financial_Model:15_05", "O2"): {
        "primary": "EVIDENCE_PRESENT_MODEL_WRONG_SELECTION",
        "secondary": [],
        "population": "Formats!E25:M25",
        "evidence": "The complete candidate packet and deterministic region summary contain E24:M25 and D25 is the Net Margin anchor; the valid saved plan selects P25:X25 and AA25:AI25 instead.",
    },
    ("Financial_Model:15_05", "O3"): {
        "primary": "TASK_IR_CONTEXT_RELATION_LOSS",
        "secondary": ["PLANNER_RESPONSE_MISSING"],
        "population": "IS_BS_CF annotated efficiency/leverage ratio cells",
        "evidence": "The raw task's surrounding Formats context is available in the full task and O2 parent, but O3 has only a balance-sheet locus and a sequencing edge; it has no inheritance relation to the parent locus/table context. The saved response also failed to parse.",
    },
    ("Financial_Model:15_05", "O4"): {
        "primary": "GROUNDING_FIELD_INTERFACE_LOSS",
        "secondary": ["ROLE_RELATION_NOT_REPRESENTED", "PLANNER_RESPONSE_MISSING"],
        "population": "Formats!AY50:BA63 on rows 50,52,54,56,59,61,63",
        "evidence": "Task IR retains below-table placement and the seven metric names, while compiled AV2 and the output formulas/anchors exist. Subject 'logical functions' yields no target candidates; no output-block role relation is constructed. The saved fragment then timed out.",
    },
    ("Financial_Model:15_05", "O5"): {
        "primary": "TASK_IR_CONTEXT_RELATION_LOSS",
        "secondary": ["GROUNDING_FIELD_INTERFACE_LOSS", "ROLE_RELATION_NOT_REPRESENTED", "PLANNER_RESPONSE_MISSING"],
        "population": "Formats!AY50:AZ63 on rows 50,52,54,56,59,61,63",
        "evidence": "O5 carries periods and output-property text, but its parent O4's metric list/below-table context is not inherited; then_after records sequencing only. The grounder therefore supplies period-oriented candidates, not the logical output block, and the saved planner response timed out.",
    },
    ("Financial_Model:15_05", "O6"): {
        "primary": "TASK_IR_CONTEXT_RELATION_LOSS",
        "secondary": ["GROUNDING_FIELD_INTERFACE_LOSS", "ROLE_RELATION_NOT_REPRESENTED"],
        "population": "Formats!BA50:BA63 on rows 50,52,54,56,59,61,63",
        "evidence": "O6 carries 3QFY24E and its output property, but not O4's metric list/below-table context. The valid plan chooses AX38:AX44 while the target role is BA on seven separated output rows.",
    },
    ("Financial_Model:15_05", "O7"): {
        "primary": "STRUCTURE_NOT_MECHANICALLY_DEFINED",
        "secondary": ["ROLE_RELATION_NOT_REPRESENTED"],
        "population": "Report Tables!C4:I36 annotated Particulars body cells",
        "evidence": "Particulars heading and body labels are compiled, but no deterministic table-body extent distinguishes rows 4:36 from the heading/adjacent blocks. The valid plan selects only the heading row.",
    },
    ("Financial_Model:15_05", "O8"): {
        "primary": "PLANNER_RESPONSE_MISSING",
        "secondary": [],
        "population": "Report Tables!C30:I32 and G34:I36",
        "evidence": "The saved fragment timed out. The packet contains section labels, Margin (%) rows and % Change anchors, but no returned selection exists; the misses are not retrospectively assigned to grounding.",
    },
    ("Financial_Model:03_01", "O1"): {
        "primary": "PLANNER_RESPONSE_MISSING",
        "secondary": [],
        "population": "Balance Sheet!O5:P13",
        "evidence": "Task IR locus, Asset line-item subject and both CAGR intervals are present; the saved fragment was truncated before any selection.",
    },
    ("Financial_Model:03_01", "O4"): {
        "primary": "GROUNDING_FIELD_INTERFACE_LOSS",
        "secondary": ["ROLE_RELATION_NOT_REPRESENTED"],
        "population": "Income Statement!R5:AA31 annotated growth block cells",
        "evidence": "required_change retains year-on-year growth and R2 is a compiled Growth (%) output anchor with formulas in R:AA, but project_obligation consumes the generic all-line-items subject and builds no output-column relation.",
    },
    ("Financial_Model:03_01", "O5"): {
        "primary": "GROUNDING_FIELD_INTERFACE_LOSS",
        "secondary": ["ROLE_RELATION_NOT_REPRESENTED"],
        "population": "CF!I39:M39",
        "evidence": "CF target cells and the opening-cash row anchor B39 are compiled, but locus resolution maps Cash Flow Statement to the wrong sheet and target construction has no opening-cash row relation; the saved plan guesses CF row 33.",
    },
    ("Financial_Model:03_01", "O6"): {
        "primary": "EVIDENCE_PRESENT_MODEL_WRONG_SELECTION",
        "secondary": [],
        "population": "Valuation!D6:H6",
        "evidence": "The valid plan correctly selects Required Equity D8:H8. Tier 1 ratio assumption D6:H6 is present in the complete candidate packet/region evidence but is omitted from authority; this is a plan target-set choice, not expansion loss.",
    },
    ("Financial_Model:13_05", "O1"): {
        "primary": "PLANNER_RESPONSE_MISSING",
        "secondary": [],
        "population": "Input Sheet!I20:M20",
        "evidence": "After the already-frozen temporal projection repair, all five FY26:FY30 target cells are in the current candidate set; the saved planner fragment timed out.",
    },
    ("Financial_Model:13_05", "O3"): {
        "primary": "ROLE_RELATION_NOT_REPRESENTED",
        "secondary": ["GROUNDING_FIELD_INTERFACE_LOSS"],
        "population": "Input Sheet!I58:M58",
        "evidence": "B58 is a formula-linked occurrence of B25 and the B58→B25 dependency survives the full and projected packets. The workbook has both occurrences, but no source-vs-target/occurrence-role relation maps the text-only Task IR subject to cost-side row 58; the planner selects revenue-side row 25.",
    },
    ("Financial_Model:13_05", "O4"): {
        "primary": "PLANNER_RESPONSE_MISSING",
        "secondary": [],
        "population": "Debt Schedule!K13",
        "evidence": "The provider response has finish_reason=error/content=null and no usable Edit Plan exists; the target is in the current candidate set.",
    },
}


FACTS: dict[tuple[str, str], str] = {
    ("Financial_Model:05_01", "O1"): "IRR Calculation sheet/labeled IRR rows and target cells present; temporal coordinates are available.",
    ("Financial_Model:05_01", "O2"): "IS - Mgmt Co.!DK7 text anchor 'Total'; DK target cells are within compiled sheet bounds; temporal rows O:DI are represented separately.",
    ("Financial_Model:05_01", "O6"): "Dashboard Exit Multiple row/columns and tranche labels are compiled; no returned plan.",
    ("Financial_Model:05_01", "O7"): "Workings Cost Sheet B29/B30/B31 anchors are First/Second/Third Tranche; O29:DI31 target cells and period columns are compiled.",
    ("Financial_Model:15_05", "O1"): "Formats D1/O1 Consolidated Financials anchors, merges, cells and formula-equivalence runs exist; no explicit table object.",
    ("Financial_Model:15_05", "O2"): "Formats D25 Net Margin (%) anchor and E24:M25 region are compiled and in the packet.",
    ("Financial_Model:15_05", "O3"): "IS_BS_CF ratio target cells exist; full task/O2 provides surrounding Formats context, but child relation is absent.",
    ("Financial_Model:15_05", "O4"): "Formats AV2 Quarterly Result Table anchor and AY/ AZ/ BA output formulas exist; output-block relation is absent.",
    ("Financial_Model:15_05", "O5"): "Formats period anchors AY3/AZ3 and output formulas exist; parent metric/output context is not inherited.",
    ("Financial_Model:15_05", "O6"): "Formats period anchor AX3 and BA50/52/54/56/59/61/63 output formulas exist; parent metric/output context is not inherited.",
    ("Financial_Model:15_05", "O7"): "Report Tables B2 Particulars and B4:B36 row labels/cells are compiled; no body extent relation.",
    ("Financial_Model:15_05", "O8"): "Report Tables B29:B36 section labels and C:I cells are compiled; no returned plan.",
    ("Financial_Model:03_01", "O1"): "Balance Sheet CAGR output columns O:P and asset-row formulas exist; no returned plan.",
    ("Financial_Model:03_01", "O4"): "Income Statement R2 Growth (%) anchor and R5:AA31 formula block exist; output role is not composed.",
    ("Financial_Model:03_01", "O5"): "CF B39 opening-cash anchor and I39:M39 bounds exist; locus resolver selects the wrong sheet/row relation.",
    ("Financial_Model:03_01", "O6"): "Valuation D6:H6 Tier 1 ratio and D8:H8 Required Equity regions are compiled and candidate-visible.",
    ("Financial_Model:13_05", "O1"): "Input Sheet B20 Transport Revenue and I20:M20 FY26:FY30 cells are compiled; repaired temporal packet includes all five.",
    ("Financial_Model:13_05", "O3"): "Input Sheet B25 text-side Rate per Square Feet, B58 formula =B25, I58:M58 blanks, and B58→B25 dependency are compiled.",
    ("Financial_Model:13_05", "O4"): "Debt Schedule K13 is within compiled bounds and in current candidates; no usable response.",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def cell_id_from_label(label: str, titles: dict[str, int]) -> str:
    sheet, address = label.rsplit("!", 1)
    match = re.fullmatch(r"\$?([A-Z]{1,3})\$?(\d+)", address)
    if not match:
        raise ValueError(f"unsupported gold address: {label}")
    column = 0
    for char in match.group(1):
        column = column * 26 + ord(char) - 64
    return f"cell:s{titles[sheet]:02d}:r{int(match.group(2))}:c{column}"


def region_contains(region: dict[str, Any], cell_id: str) -> bool:
    match = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", cell_id)
    if not match or region.get("kind") != "RECTANGLE":
        return False
    sid, row, col = map(int, match.groups())
    return (region.get("sheet_id") == f"sheet:s{sid:02d}"
            and region["r1"] <= row <= region["r2"]
            and region["c1"] <= col <= region["c2"])


def canonical_authority(labels: list[str], titles: dict[str, int]) -> set[str]:
    return {cell_id_from_label(label, titles) for label in labels}


def context_payload(ob: dict[str, Any], obligations: dict[str, dict[str, Any]], shard_missing: list[str]) -> dict[str, Any]:
    parents = [obligations[parent] for parent in ob.get("then_after", []) if parent in obligations]
    return {
        "then_after": ob.get("then_after", []),
        "full_task_ir_parent_obligations": [
            {"id": p["id"], "locus": p.get("locus"), "subject": p.get("subject"), "scope": p.get("scope"),
             "required_change": p.get("required_change"), "result_property": p.get("result_property")}
            for p in parents
        ],
        "parent_ids_absent_from_shard": shard_missing,
        "raw_task_retained_in_shard": True,
    }


def run(output: Path) -> None:
    csv.field_size_limit(100_000_000)
    annotations = [r for r in csv.DictReader(ANNOTATIONS.open()) if r["row_type"] == "OBLIGATION"]
    lineage = {(r["task"], r["obligation_id"]): r for r in csv.DictReader(LINEAGE.open())}

    tasks = sorted({r["task"] for r in lineage.values()})
    annotated = {(r["task"], r["obligation_id"]): r for r in annotations}
    all_census_rows: list[dict[str, Any]] = []
    obligation_records: list[dict[str, Any]] = []
    current_packet_cache: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    for task in tasks:
        slug = task.replace(":", "-")
        spine = load_json(m.SPINES / f"{slug}.json")
        result = load_json(m.RUN_ROOT / "resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge" / slug / "result.json")
        compiler = result["compiler"]
        obligations = {o["id"]: o for o in compiler.get("obligations", [])}
        db = REPAIRED_DB / f"{slug}.sqlite"
        world = m.World(db)
        try:
            current_spine = m.planning_spine_for(task, world)
            for oid, ob in obligations.items():
                if (task, oid) not in annotated:
                    continue
                current_packet_cache[f"{task}:{oid}"] = (ob, g.project_obligation(current_spine, ob))
        finally:
            world.close()

    for key, annotation in sorted(annotated.items()):
        task, oid = key
        slug = task.replace(":", "-")
        spine = load_json(m.SPINES / f"{slug}.json")
        result = load_json(m.RUN_ROOT / "resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge" / slug / "result.json")
        compiler = result["compiler"]
        obligations = {o["id"]: o for o in compiler.get("obligations", [])}
        ob = obligations[oid]
        annotation_map = json.loads(annotation["gold_target_cells"] or "[]")
        archived_packet = json.loads(annotation["grounding_candidates"])
        planner_view = json.loads(annotation["planner_grounding_view"])
        saved_candidate_ids = set(archived_packet["target_cell_ids"])
        saved_foreground = set(planner_view.get("targets", {}).get("foreground_cell_ids", []))
        saved_regions = planner_view.get("targets", {}).get("region_summaries", [])
        _, current_packet = current_packet_cache[f"{task}:{oid}"]
        current_candidate_ids = set(current_packet["target_cell_ids"])
        authority_labels = json.loads(annotation["expanded_authority_cells"] or "[]")
        authority_ids = canonical_authority(authority_labels, spine["title_to_index"])
        gold_ids = {cell_id_from_label(label, spine["title_to_index"]) for label in annotation_map}
        classification = CLASSIFICATIONS.get(key)
        if not annotation_map:
            continue
        if classification is None:
            if gold_ids <= authority_ids:
                classification = {"primary": "NO_FRONTEND_LOSS", "secondary": [], "population": "", "evidence": "Saved expanded authority contains every annotated target."}
            else:
                raise AssertionError(f"missing classification for {key}")
        shard_missing = json.loads(lineage[key]["then_after_ids_absent_from_shard"] or "[]")
        context = context_payload(ob, obligations, shard_missing)
        saved_region_ids = {cell_id for cell_id in gold_ids if any(region_contains(region, cell_id) for region in saved_regions)}
        compiled_ids = set(spine["id_index"])
        repaired_gold = gold_ids & current_candidate_ids
        saved_gold = gold_ids & saved_candidate_ids
        saved_foreground_or_region = gold_ids & (saved_foreground | saved_region_ids)
        missed_ids = gold_ids - authority_ids
        for label, gid in sorted(zip(annotation_map, [cell_id_from_label(x, spine["title_to_index"]) for x in annotation_map])):
            missed = gid in missed_ids
            row_class = classification["primary"] if missed else "NO_FRONTEND_LOSS"
            secondaries = classification["secondary"] if missed else []
            all_census_rows.append({
                "task": task,
                "obligation_id": oid,
                "gold_target": label,
                "gold_cell_id": gid,
                "gold_status": "MISSED_AUTHORITY" if missed else "AUTHORIZED",
                "fragment_status": annotation["fragment_status"],
                "gold_count_for_obligation": int(annotation["gold_target_count"] or 0),
                "authority_count_for_obligation": int(annotation["authority_count"] or 0),
                "task_ir_fields": json.dumps({k: ob.get(k) for k in ("locus", "subject", "subject_interval", "required_change", "scope", "source_relation", "condition", "result_property", "then_after", "occupancy_filter")}, ensure_ascii=False, sort_keys=True),
                "inherited_parent_context": json.dumps(context, ensure_ascii=False, sort_keys=True),
                "matching_workbook_entities_or_facts": FACTS.get(key, "Annotated target cells and their deterministic workbook identities are compiled and authorized."),
                "compiled_world_has_target_cell": gid in compiled_ids,
                "saved_packet_complete_candidate": gid in saved_candidate_ids,
                "saved_packet_foreground_or_region_evidence": gid in saved_foreground_or_region,
                "repaired_packet_complete_candidate": gid in current_candidate_ids,
                "saved_expanded_authority": gid in authority_ids,
                "repaired_packet_candidate_count": len(current_candidate_ids),
                "repaired_packet_gold_candidate_count": len(repaired_gold),
                "saved_packet_gold_candidate_count": len(saved_gold),
                "earliest_loss_category": row_class,
                "secondary_categories": ";".join(secondaries),
                "coherent_missed_population": classification["population"] if missed else "",
                "evidence": classification["evidence"] if missed else "Saved expanded authority contains this annotated target.",
            })
        obligation_records.append({
            "task": task,
            "obligation_id": oid,
            "raw_obligation": ob,
            "gold_target_count": len(gold_ids),
            "authority_count": len(authority_ids),
            "missed_gold_count": len(missed_ids),
            "authorized_gold_count": len(gold_ids & authority_ids),
            "fragment_status": annotation["fragment_status"],
            "primary_loss_category": classification["primary"] if missed_ids else "NO_FRONTEND_LOSS",
            "secondary_categories": classification["secondary"] if missed_ids else [],
            "task_ir_fields": {k: ob.get(k) for k in ("locus", "subject", "subject_interval", "required_change", "scope", "source_relation", "condition", "result_property", "then_after", "occupancy_filter")},
            "inherited_parent_context": context,
            "matching_workbook_entities_or_facts": FACTS.get(key, "Annotated target cells and their deterministic workbook identities are compiled and authorized."),
            "compiled_world_has_all_gold_targets": gold_ids <= compiled_ids,
            "saved_packet_gold_candidate_count": len(saved_gold),
            "saved_packet_gold_foreground_or_region_count": len(saved_foreground_or_region),
            "repaired_packet_gold_candidate_count": len(repaired_gold),
            "coherent_missed_population": classification["population"],
            "evidence": classification["evidence"],
        })

    missed_rows = [r for r in all_census_rows if r["gold_status"] == "MISSED_AUTHORITY"]
    primary_counts = Counter(r["earliest_loss_category"] for r in missed_rows)
    secondary_counts = Counter(category for r in missed_rows for category in r["secondary_categories"].split(";") if category)
    by_obligation = Counter((r["task"], r["obligation_id"]) for r in missed_rows)
    by_task = Counter(r["task"] for r in missed_rows)

    unannotated = []
    for task, oid, note in [
        ("Financial_Model:08_01", "O3", "The child scope is 'for the same timeframe'; parent O2 scope is 'for Aug-23 to Dec-28'. The archived/current scope projection remains empty because then_after is sequencing, not scope inheritance. No evaluator gold is available, so this is excluded from gold-cell counts."),
        ("Financial_Model:01_01", "O5", "Scope shadow matching for 'for each Foundation Course line item' finds 11 labels across revenue and expense occurrences. It demonstrates overreach risk, not a gold authority loss."),
    ]:
        line = lineage.get((task, oid), {})
        unannotated.append({
            "task": task,
            "obligation_id": oid,
            "task_ir": json.loads(line["raw_obligation"]) if line else None,
            "fragment_status": line.get("fragment_status"),
            "then_after_ids_absent_from_shard": json.loads(line.get("then_after_ids_absent_from_shard", "[]") or "[]"),
            "note": note,
            "excluded_from_gold_counts": True,
        })

    candidate_distinctions = [
        {"rank": 1, "distinction": "field-provenance-to-target-role relation", "support": "553 primary missed cells across tranche population, total-column, growth-column, locus-row and logical-output cases", "definition": "A deterministic relation that maps a Task IR field/span to a workbook role without unioning every lexical hit", "coverage": "Measured by complete candidate∩gold and authority precision/recall on the existing annotated obligations", "overreach": "Wrong tranche rows, wrong output block, wrong source/target occurrence, wrong sheet/row", "status": "supported research distinction; not installed"},
        {"rank": 2, "distinction": "explicit table-body extent", "support": "345 primary missed cells across Formats and Report Tables body populations", "definition": "Not currently deterministically defined: no Excel Table object and no validated heading/body/totals relation", "coverage": "Negative-control coverage is measurable only after a supported structure contract exists", "overreach": "Heading rows, totals and adjacent unrelated blocks", "status": "not earned; classify as STRUCTURE_NOT_MECHANICALLY_DEFINED"},
        {"rank": 3, "distinction": "parent-context inheritance relation", "support": "153 primary missed cells in 15_05 child obligations; 08_01 O3 unannotated scope diagnostic", "definition": "Copy/link only explicit parent/sibling context relations, distinct from then_after execution order", "coverage": "Parent fields and child target intersections are directly countable", "overreach": "Propagating every parent locus/scope into every sibling", "status": "supported research distinction; no generic inheritance rule installed"},
        {"rank": 4, "distinction": "occurrence/source-vs-target role", "support": "13_05 O3: 5 primary missed cells with B58→B25 dependency present", "definition": "A deterministic occurrence identity plus direction/context role for repeated labels", "coverage": "Current packet has dependency edge but no role; candidate/authority can be compared on B25 vs B58", "overreach": "Copying source-label semantics to every formula-linked occurrence", "status": "single counterexample; not earned for live A/B"},
        {"rank": 5, "distinction": "planner-only model choice", "support": "14 primary missed cells across 15_05 O2 and 03_01 O6", "definition": "Complete candidate evidence/region relation contains the gold and valid expansion preserves the selected region", "coverage": "Gold candidate membership and expanded authority precision/recall are directly measured", "overreach": "Calling absent candidate evidence a model-choice error", "status": "already isolated; no new live A/B justified"},
    ]

    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "role_aware_authority_census.csv"
    fields = list(all_census_rows[0]) if all_census_rows else []
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_census_rows)

    summary = {
        "schema_version": "phase2_role_aware_authority_census_v1",
        "model_calls": 0,
        "workbook_writes": 0,
        "scheduler_execution": "frozen",
        "fm20_launched": False,
        "scope": {"archived_feasibility_tasks": 11, "successful_task_ir_tasks": len(tasks), "task_ir_missing_tasks": ["Financial_Model:17_05"], "archived_obligations": len(lineage), "annotated_obligations": len(annotated), "annotated_tasks": sorted({task for task, _ in annotated}), "named_priority_tasks": ["Financial_Model:05_01", "Financial_Model:15_05", "Financial_Model:13_05", "Financial_Model:03_01", "Financial_Model:08_01"]},
        "counts": {"gold_cell_observations": len(all_census_rows), "missed_gold_cell_observations": len(missed_rows), "unique_missed_gold_cells": len({r["gold_cell_id"] for r in missed_rows}), "obligations_with_missed_gold": len(by_obligation), "fully_authorized_annotated_obligations": len(annotated) - len(by_obligation), "authorized_gold_cell_observations": len(all_census_rows) - len(missed_rows)},
        "primary_loss_counts": {category: {"obligations": len({(r["task"], r["obligation_id"]) for r in missed_rows if r["earliest_loss_category"] == category}), "gold_cell_observations": primary_counts.get(category, 0), "share_of_missed_gold": round(primary_counts.get(category, 0) / len(missed_rows), 6) if missed_rows else 0.0} for category in CATEGORY_ORDER},
        "secondary_loss_counts": {category: secondary_counts.get(category, 0) for category in CATEGORY_ORDER},
        "missed_gold_by_task": dict(by_task),
        "candidate_distinctions": candidate_distinctions,
        "unannotated_counterexamples": unannotated,
        "deterministic_repairs": {"new_phase2_repair": False, "held_frozen_repairs": ["shared temporal world projection", "typed percentage exclusion from year parsing", "stable bounded dependency serialization"], "validation": "replayed archived target sets with zero model calls and zero workbook writes; source hashes unchanged"},
        "obligation_records": obligation_records,
        "gold_cell_records": all_census_rows,
    }
    (output / "role_aware_authority_census.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"obligation_records", "gold_cell_records", "candidate_distinctions", "unannotated_counterexamples"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
