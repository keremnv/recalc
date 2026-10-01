#!/usr/bin/env python3
"""Offline 297-task structural recoverability census.

The script reads input/golden workbooks only for evaluator-side classification.
It performs no model, SQL, retrieval, workbook-write, or production-agent call.
Formula identity and translation are delegated to the frozen fingerprint and
formula-completion primitives already used by the earlier probes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark-data/SpreadsheetBench-2"
DATA = BENCH / "data"
OUT = BENCH / "benchmark-runs/mechanical/structural-recoverability-census"

sys.path[:0] = [str(ROOT / "benchmark"), str(ROOT / "benchmark/sweagent/formula_index/lib"), str(ROOT / "src")]
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402
from openpyxl.utils.cell import range_boundaries  # noqa: E402

from execution_unit_score import _same  # noqa: E402
from formula_completion_certs import translate_to_target  # noqa: E402
from librecalc_mcp.domain.formulas import formula_a1_references  # noqa: E402
from program_group import groups_for, input_kinds as _pg_input_kinds, input_formulas as _pg_input_formulas  # noqa: E402
import program_group as pg  # noqa: E402
from task_obligation_shape import family_of, load_cell_map  # noqa: E402
from fingerprint import formula_text, relative_fingerprint  # noqa: E402


CATEGORIES = ("Template", "Financial_Model", "Debugging")
CLASS_ORDER = (
    "RECOVERABLE_EXACT",
    "RECOVERABLE_FINGERPRINT_ONLY",
    "EXISTING_BUT_NOT_TRANSLATABLE",
    "GENUINELY_NOVEL",
    "OPAQUE_OR_UNSUPPORTED",
)
TASK_BUCKETS = (
    "T0_ALL_EXACTLY_RECOVERABLE",
    "T1_NO_NOVEL_BUT_BINDING_REQUIRED",
    "T2_ONE_NOVEL_PROGRAM",
    "T3_TWO_TO_THREE_NOVEL_PROGRAMS",
    "T4_MANY_NOVEL_PROGRAMS",
    "T5_OPAQUE",
    "NO_FORMULA_PROGRAM_REQUIREMENT",
    "UNCLASSIFIABLE",
)


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(n: int | float, d: int | float) -> float | None:
    return round(100.0 * n / d, 3) if d else None


def a1(row: int, col: int) -> str:
    return pg.cc.a1(row, col)


def task_key(category: str, task_id: str) -> str:
    return f"{category}:{task_id}"


def load_population() -> list[dict]:
    rows = []
    for category in CATEGORIES:
        for item in load(DATA / category / "dataset.json"):
            rows.append({
                "task_key": task_key(category, item["id"]),
                "category": category,
                "task": item["id"],
                "instruction": item.get("instruction", ""),
                "input_path": str(DATA / category / item["spreadsheet_path"]),
                "gold_path": str(DATA / category / item["golden_response_path"]),
                "answer_position": item.get("answer_position"),
            })
    return rows


def formula_cells(path: Path) -> tuple[dict[tuple[str, int, int], dict], dict[tuple[str, int, int], str]]:
    """Formula payloads and input kinds, without saving or modifying a workbook."""
    cell_map, _ = load_cell_map(path)
    kinds: dict[tuple[str, int, int], str] = {}
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False)
    try:
        for ws in wb.worksheets:
            for cell in ws._cells.values():
                value = cell.value
                if formula_text(value):
                    kinds[(ws.title, int(cell.column), int(cell.row))] = "formula"
                elif value is None or (isinstance(value, str) and not value.strip()):
                    kinds[(ws.title, int(cell.column), int(cell.row))] = "blank"
                else:
                    kinds[(ws.title, int(cell.column), int(cell.row))] = "value"
    finally:
        wb.close()
    return cell_map, kinds


def ref_sheets(formula: str, home: str) -> list[str]:
    out = []
    try:
        for host, _start, _end in formula_a1_references(formula):
            out.append(host or home)
    except Exception:
        return []
    return sorted(set(out))


def program_identity(formula: str, sheet: str, col: int, row: int) -> tuple[str | None, bool, str | None]:
    fp = relative_fingerprint(formula, col, row, sheet=sheet)
    return (None if fp.opaque else fp.text, fp.opaque, fp.reason)


def classify_target(
    target: dict,
    input_formulas: list[dict],
    gold_formula: str,
) -> dict:
    sheet, col, row = target["sheet"], target["col"], target["row"]
    target_fp, target_opaque, opaque_reason = program_identity(gold_formula, sheet, col, row)
    base = {
        "target": f"{sheet}!{a1(row, col)}",
        "sheet": sheet,
        "row": row,
        "col": col,
        "gold_formula": gold_formula,
        "gold_fingerprint": target_fp,
        "gold_opaque": target_opaque,
        "gold_opaque_reason": opaque_reason,
        "matching_input_occurrences": 0,
        "same_sheet_matching_occurrences": 0,
        "legal_translations": 0,
        "exact_translations": 0,
        "translation_examples": [],
    }
    if target_opaque:
        base["availability_class"] = "OPAQUE_OR_UNSUPPORTED"
        return base

    matches = [x for x in input_formulas if x["fingerprint"] == target_fp]
    base["matching_input_occurrences"] = len(matches)
    same_sheet = [x for x in matches if x["sheet"] == sheet]
    base["same_sheet_matching_occurrences"] = len(same_sheet)
    for source in same_sheet:
        translated = translate_to_target(
            source["formula"], src_sheet=source["sheet"], src_col=source["col"], src_row=source["row"],
            tgt_sheet=sheet, tgt_col=col, tgt_row=row,
        )
        if translated is None:
            continue
        base["legal_translations"] += 1
        is_exact = bool(_same(translated["formula"], gold_formula))
        base["exact_translations"] += int(is_exact)
        if len(base["translation_examples"]) < 3:
            base["translation_examples"].append({
                "source": f'{source["sheet"]}!{a1(source["row"], source["col"])}',
                "formula": source["formula"],
                "translated": translated["formula"],
                "exact": is_exact,
            })
    if base["exact_translations"]:
        cls = "RECOVERABLE_EXACT"
    elif not matches:
        cls = "GENUINELY_NOVEL"
    elif base["legal_translations"]:
        cls = "RECOVERABLE_FINGERPRINT_ONLY"
    else:
        cls = "EXISTING_BUT_NOT_TRANSLATABLE"
    base["availability_class"] = cls
    return base


def content_delta(input_cells: dict, gold_cells: dict) -> tuple[list[dict], list[dict]]:
    changes = []
    for sheet, col, row in sorted(set(input_cells) | set(gold_cells), key=lambda x: (x[0], x[2], x[1])):
        left, right = input_cells.get((sheet, col, row)), gold_cells.get((sheet, col, row))
        in_kind = left["kind"] if left else "blank"
        gold_kind = right["kind"] if right else "blank"
        in_payload = left.get("payload") if left else None
        gold_payload = right.get("payload") if right else None
        if in_kind == gold_kind and in_payload == gold_payload:
            continue
        edit_type = (
            "BLANK_TO_FORMULA" if in_kind == "blank" and gold_kind == "formula" else
            "VALUE_TO_FORMULA" if in_kind == "value" and gold_kind == "formula" else
            "FORMULA_TO_FORMULA" if in_kind == "formula" and gold_kind == "formula" else
            "FORMULA_TO_VALUE" if in_kind == "formula" and gold_kind == "value" else
            "FORMULA_TO_BLANK" if in_kind == "formula" and gold_kind == "blank" else
            "BLANK_TO_VALUE" if in_kind == "blank" and gold_kind == "value" else
            "VALUE_TO_BLANK" if in_kind == "value" and gold_kind == "blank" else
            "VALUE_TO_VALUE"
        )
        changes.append({
            "sheet": sheet, "row": row, "col": col, "address": a1(row, col),
            "input_kind": in_kind, "gold_kind": gold_kind,
            "input_payload": in_payload, "gold_payload": gold_payload,
            "edit_type": edit_type,
        })
    formulas = [x for x in changes if x["gold_kind"] == "formula"]
    nonformulas = [x for x in changes if x["gold_kind"] != "formula"]
    return formulas, nonformulas


def program_class(classes: set[str]) -> str:
    if len(classes) == 1:
        return next(iter(classes))
    return "MIXED_INSTANCE_AVAILABILITY"


def translation_consistency(targets: list[dict]) -> bool | None:
    if len(targets) <= 1:
        return True
    first = targets[0]
    for other in targets[1:]:
        if first["sheet"] != other["sheet"]:
            return False
        translated = translate_to_target(
            first["gold_formula"], src_sheet=first["sheet"], src_col=first["col"], src_row=first["row"],
            tgt_sheet=other["sheet"], tgt_col=other["col"], tgt_row=other["row"],
        )
        if translated is None or not _same(translated["formula"], other["gold_formula"]):
            return False
    return True


def build_programs(formula_targets: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for target in formula_targets:
        ident = target["gold_fingerprint"]
        if ident is None:
            ident = f'OPAQUE_TARGET::{target["target"]}'
        groups[ident].append(target)
    out = []
    for ident, targets in sorted(groups.items()):
        classes = {x["availability_class"] for x in targets}
        out.append({
            "program_id": hashlib.sha1(ident.encode()).hexdigest()[:12],
            "program_fingerprint": None if ident.startswith("OPAQUE_TARGET::") else ident,
            "opaque": any(x["gold_opaque"] for x in targets),
            "n_target_cells": len(targets),
            "repeated_across_targets": len(targets) >= 2,
            "availability_class": program_class(classes),
            "instance_classes": sorted(classes),
            "has_novel_instance": "GENUINELY_NOVEL" in classes,
            "all_instances_exact": classes == {"RECOVERABLE_EXACT"},
            "translation_consistent": translation_consistency(targets),
            "sheets_touched": sorted({s for x in targets for s in [x["sheet"], *ref_sheets(x["gold_formula"], x["sheet"])]}),
            "edit_types": sorted({x["edit_type"] for x in targets}),
            "targets": targets,
        })
    return out


def generic_input_maps(path: Path) -> tuple[dict, dict]:
    """Maps accepted by the frozen ProgramGroup implementation."""
    forms: dict = {}
    kinds: dict = {}
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False)
    try:
        for ws in wb.worksheets:
            for cell in ws._cells.values():
                key = (ws.title, int(cell.row), int(cell.column))
                text = formula_text(cell.value)
                if text:
                    forms[key] = text
                    kinds[key] = "formula"
                elif cell.value is None or (isinstance(cell.value, str) and not cell.value.strip()):
                    kinds[key] = "blank"
                else:
                    kinds[key] = "value"
    finally:
        wb.close()
    return forms, kinds


def programgroup_surface(task_row: dict, formula_changes: list[dict], gold_by_cell: dict, forms: dict, kinds: dict) -> dict:
    if not formula_changes:
        return {"status": "NO_FORMULA_TARGETS", "groups": [], "refused": [], "grouped_cells": 0, "uniform_grouped_cells": 0, "new_canonical_decisions": 0}
    try:
        members = [(x["sheet"], x["row"], x["col"]) for x in formula_changes]
        by_cell = {m: {"operation_id": "ORACLE_FORMULA_EDIT"} for m in members}
        groups, refused = groups_for(members, by_cell, task_row["task"], forms=forms, kinds=kinds, min_lines=pg.MIN_WITNESS_LINES)
        uniform = []
        for group in groups:
            canon = tuple(group["canonical_cell"])
            if canon not in gold_by_cell:
                continue
            exact = True
            detail = []
            for raw in group["member_cells"]:
                cell = tuple(raw)
                try:
                    translated = pg.translate(gold_by_cell[canon], canon, cell)
                    ok = bool(_same(translated, gold_by_cell.get(cell)))
                except Exception as exc:
                    translated, ok = None, False
                    detail.append({"cell": list(cell), "error": type(exc).__name__})
                detail.append({"cell": list(cell), "translated": translated, "exact": ok})
                exact &= ok
            group["gold_translation_uniform"] = exact
            group["gold_translation_detail"] = detail
            if exact:
                uniform.append(group)
        grouped_cells = sum(len(g["member_cells"]) for g in groups)
        uniform_cells = sum(len(g["member_cells"]) for g in uniform)
        return {
            "status": "MEASURED", "groups": groups, "uniform_groups": uniform, "refused": refused,
            "grouped_cells": grouped_cells, "uniform_grouped_cells": uniform_cells,
            "group_count": len(groups), "uniform_group_count": len(uniform),
            "new_canonical_decisions": len(groups) + (len(members) - grouped_cells),
            "uniform_canonical_decisions": len(uniform) + (len(members) - uniform_cells),
        }
    except Exception as exc:
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}", "groups": [], "refused": [], "grouped_cells": 0, "uniform_grouped_cells": 0, "new_canonical_decisions": len(formula_changes)}


def classify_task(task_row: dict, input_cells: dict, gold_cells: dict, input_formula_records: list[dict]) -> dict:
    formula_changes, nonformula_changes = content_delta(input_cells, gold_cells)
    formula_targets = []
    for change in formula_changes:
        target = classify_target(change, input_formula_records, change["gold_payload"])
        target.update({"edit_type": change["edit_type"], "input_kind": change["input_kind"], "gold_kind": change["gold_kind"]})
        formula_targets.append(target)
    programs = build_programs(formula_targets)
    counts = Counter(x["availability_class"] for x in formula_targets)
    program_counts = Counter(x["availability_class"] for x in programs)
    novel_programs = sum(1 for p in programs if p["has_novel_instance"])
    opaque_programs = sum(1 for p in programs if p["opaque"])
    if not formula_targets:
        bucket = "NO_FORMULA_PROGRAM_REQUIREMENT"
    elif opaque_programs:
        bucket = "T5_OPAQUE"
    elif novel_programs == 0 and all(p["all_instances_exact"] for p in programs):
        bucket = "T0_ALL_EXACTLY_RECOVERABLE"
    elif novel_programs == 0:
        bucket = "T1_NO_NOVEL_BUT_BINDING_REQUIRED"
    elif novel_programs == 1:
        bucket = "T2_ONE_NOVEL_PROGRAM"
    elif novel_programs <= 3:
        bucket = "T3_TWO_TO_THREE_NOVEL_PROGRAMS"
    else:
        bucket = "T4_MANY_NOVEL_PROGRAMS"
    gold_by_cell = {(x["sheet"], x["row"], x["col"]): x["gold_formula"] for x in formula_targets}
    forms = {(sheet, row, col): cell["payload"] for (sheet, col, row), cell in input_cells.items() if cell["kind"] == "formula"}
    kinds = {(sheet, row, col): cell["kind"] for (sheet, col, row), cell in input_cells.items()}
    pg_surface = programgroup_surface(task_row, formula_changes, gold_by_cell, forms, kinds)
    exact_cells = counts["RECOVERABLE_EXACT"]
    nonnovel_cells = sum(counts[c] for c in ("RECOVERABLE_EXACT", "RECOVERABLE_FINGERPRINT_ONLY", "EXISTING_BUT_NOT_TRANSLATABLE"))
    formula_all_exact = bool(formula_targets) and exact_cells == len(formula_targets)
    formula_no_novel = bool(formula_targets) and nonnovel_cells == len(formula_targets)
    formula_oracle = bool(formula_targets) and counts["OPAQUE_OR_UNSUPPORTED"] == 0
    if not formula_targets:
        formula_all_exact = True
        formula_no_novel = True
        formula_oracle = True
    return {
        **task_row,
        "status": "CLASSIFIED",
        "n_content_edits": len(formula_changes) + len(nonformula_changes),
        "n_formula_edits": len(formula_changes),
        "n_nonformula_edits": len(nonformula_changes),
        "formula_edit_type_counts": dict(Counter(x["edit_type"] for x in formula_changes)),
        "nonformula_edit_type_counts": dict(Counter(x["edit_type"] for x in nonformula_changes)),
        "formula_target_counts": dict(counts),
        "n_independent_programs": len(programs),
        "program_class_counts": dict(program_counts),
        "n_recoverable_exact_programs": sum(1 for p in programs if p["all_instances_exact"]),
        "n_fingerprint_only_programs": sum(1 for p in programs if p["availability_class"] == "RECOVERABLE_FINGERPRINT_ONLY"),
        "n_existing_not_translatable_programs": sum(1 for p in programs if p["availability_class"] == "EXISTING_BUT_NOT_TRANSLATABLE"),
        "n_novel_programs": novel_programs,
        "n_opaque_programs": opaque_programs,
        "n_repeated_programs": sum(p["repeated_across_targets"] for p in programs),
        "recoverable_exact_formula_cells": exact_cells,
        "recoverable_non_novel_formula_cells": nonnovel_cells,
        "recoverable_exact_cell_share": (exact_cells / len(formula_changes)) if formula_changes else 1.0,
        "recoverable_non_novel_cell_share": (nonnovel_cells / len(formula_changes)) if formula_changes else 1.0,
        "formula_perfect": formula_all_exact,
        "no_novel_formula_perfect": formula_no_novel,
        "formula_oracle_perfect": formula_oracle,
        "strict_recovery_full_task": formula_all_exact and not nonformula_changes,
        "no_novel_full_task": formula_no_novel and not nonformula_changes,
        "formula_oracle_full_task": formula_oracle and not nonformula_changes,
        "task_bucket": bucket,
        "programgroup": pg_surface,
        "formula_edits": formula_targets,
        "nonformula_edits": nonformula_changes,
        "programs": programs,
    }


def run_census() -> tuple[list[dict], list[dict]]:
    tasks = load_population()
    task_rows, errors = [], []
    for idx, task_row in enumerate(tasks, 1):
        print(f"{idx}/{len(tasks)} {task_row['task_key']}", flush=True)
        try:
            input_cells, _input_kinds = load_cell_map(Path(task_row["input_path"]))
            gold_cells, _gold_kinds = load_cell_map(Path(task_row["gold_path"]))
            input_formula_records = []
            for (sheet, col, row), cell in input_cells.items():
                if cell["kind"] != "formula":
                    continue
                fp = relative_fingerprint(cell["payload"], col, row, sheet=sheet)
                input_formula_records.append({"sheet": sheet, "col": col, "row": row, "formula": cell["payload"], "fingerprint": None if fp.opaque else fp.text, "opaque": fp.opaque})
            task_rows.append(classify_task(task_row, input_cells, gold_cells, input_formula_records))
        except Exception as exc:
            errors.append({"task_key": task_row["task_key"], "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})
            task_rows.append({**task_row, "status": "UNCLASSIFIABLE", "task_bucket": "UNCLASSIFIABLE", "error": errors[-1]["error"], "traceback": errors[-1]["traceback"]})
    programs = []
    for task in task_rows:
        for program in task.get("programs", []):
            programs.append({"task_key": task["task_key"], "category": task["category"], "task": task["task"], **{k: v for k, v in program.items() if k != "targets"}, "targets": program["targets"]})
    write(OUT / "tasks.json", task_rows)
    write(OUT / "programs.json", programs)
    write(OUT / "unclassifiable.json", errors)
    return task_rows, programs


def load_scores(run_name: str) -> dict[str, dict]:
    path = BENCH / "benchmark-runs/openrouter" / run_name / "official_scores.json"
    if not path.exists():
        return {}
    data = load(path)
    return data.get("tasks", {}) if isinstance(data.get("tasks"), dict) else {}


def overlays(task_rows: list[dict]) -> dict:
    runs = {
        "historical_openpyxl_control_glm": "glm-5.3-flash-nonvisual-297-1",
        "historical_gpt_full_run": "gpt-5.6-sol-nonvisual-all-medium-1",
    }
    joined = {}
    for label, run in runs.items():
        scores = load_scores(run)
        for task in task_rows:
            row = scores.get(task["task_key"])
            task.setdefault("historical_scores", {})[label] = None if row is None else {
                "run": run, "exact": float(row.get("accuracy", 0)) == 1.0,
                "modification_accuracy": row.get("modification_accuracy"),
                "regression_accuracy": row.get("regression_accuracy"),
                "accuracy": row.get("accuracy"),
            }
        joined[label] = {"run": run, "matched": sum(task["task_key"] in scores for task in task_rows), "scores": scores}
    return joined


def summarize_distribution(task_rows: list[dict], programs: list[dict]) -> dict:
    out = {}
    for category in (*CATEGORIES, "OVERALL"):
        ts = task_rows if category == "OVERALL" else [x for x in task_rows if x["category"] == category]
        ps = programs if category == "OVERALL" else [x for x in programs if x["category"] == category]
        cells = [x for t in ts for x in t.get("formula_edits", [])]
        cell_counts = Counter(x["availability_class"] for x in cells)
        prog_counts = Counter(x["availability_class"] for x in ps)
        out[category] = {
            "tasks": len(ts), "formula_target_cells": len(cells), "independent_programs": len(ps),
            "formula_cell_counts": dict(cell_counts), "program_counts": dict(prog_counts),
            "formula_cell_percent": {c: pct(cell_counts[c], len(cells)) for c in CLASS_ORDER},
            "program_percent": {c: pct(prog_counts[c], len(ps)) for c in CLASS_ORDER},
            "mixed_programs": prog_counts["MIXED_INSTANCE_AVAILABILITY"],
            "opaque_tasks": sum(t.get("n_opaque_programs", 0) > 0 for t in ts),
        }
    return out


def contamination(task_rows: list[dict]) -> dict:
    out = {}
    for category in (*CATEGORIES, "OVERALL"):
        ts = task_rows if category == "OVERALL" else [x for x in task_rows if x["category"] == category]
        counts = Counter()
        novel_values = []
        for t in ts:
            if t["status"] != "CLASSIFIED":
                counts["UNCLASSIFIABLE"] += 1
                continue
            n = t["n_novel_programs"]
            novel_values.append(n)
            if n == 0:
                counts["zero_novel"] += 1
            if n == 1:
                counts["one_novel"] += 1
            if 2 <= n <= 3:
                counts["two_to_three_novel"] += 1
            if n >= 4:
                counts["four_or_more_novel"] += 1
            if n >= 2:
                counts["at_least_two"] += 1
            if n >= 3:
                counts["at_least_three"] += 1
            if n >= 5:
                counts["at_least_five"] += 1
            if n >= 10:
                counts["at_least_ten"] += 1
        novel_values.sort()
        out[category] = {
            "tasks": len(ts), **dict(counts),
            "median_novel_programs": median(novel_values) if novel_values else None,
            "p75_novel_programs": percentile(novel_values, 0.75),
            "p90_novel_programs": percentile(novel_values, 0.90),
            "max_novel_programs": max(novel_values) if novel_values else None,
            "bucket_counts": dict(Counter(t.get("task_bucket") for t in ts)),
        }
    return out


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return values[lo]
    return round(values[lo] + (values[hi] - values[lo]) * (pos - lo), 3)


def ceilings(task_rows: list[dict]) -> dict:
    out = {}
    for category in (*CATEGORIES, "OVERALL"):
        ts = task_rows if category == "OVERALL" else [x for x in task_rows if x["category"] == category]
        out[category] = {
            "tasks": len(ts),
            "strict_recovery_formula_perfect": sum(t.get("formula_perfect", False) for t in ts),
            "strict_recovery_full_task": sum(t.get("strict_recovery_full_task", False) for t in ts),
            "no_novel_formula_perfect": sum(t.get("no_novel_formula_perfect", False) for t in ts),
            "no_novel_full_task": sum(t.get("no_novel_full_task", False) for t in ts),
            "formula_oracle_full_task": sum(t.get("formula_oracle_full_task", False) for t in ts),
            "no_formula_program_requirement": sum(t.get("task_bucket") == "NO_FORMULA_PROGRAM_REQUIREMENT" for t in ts),
            "unclassifiable": sum(t.get("status") != "CLASSIFIED" for t in ts),
        }
        for key in ("strict_recovery_formula_perfect", "strict_recovery_full_task", "no_novel_formula_perfect", "no_novel_full_task", "formula_oracle_full_task"):
            out[category][key + "_pct"] = pct(out[category][key], len(ts))
    return out


def concentration(task_rows: list[dict]) -> dict:
    out = {}
    bins = ((0, 0, "0%"), (1e-12, .25, "(0,25%]"), (.25, .5, "(25,50%]"), (.5, .75, "(50,75%]"), (.75, 1.0 - 1e-12, "(75,100%)"), (1.0, 1.0, "100%"))
    for category in (*CATEGORIES, "OVERALL"):
        ts = task_rows if category == "OVERALL" else [x for x in task_rows if x["category"] == category]
        shares = Counter(); program_shares = Counter()
        high_contaminated = {"ge75": 0, "ge90": 0, "ge95": 0}
        for t in ts:
            if t.get("status") != "CLASSIFIED" or not t["n_formula_edits"]:
                continue
            s = t["recoverable_exact_cell_share"]
            ps = t["n_recoverable_exact_programs"] / t["n_independent_programs"] if t["n_independent_programs"] else 0
            for lo, hi, label in bins:
                if lo <= s <= hi:
                    shares[label] += 1; break
            for lo, hi, label in bins:
                if lo <= ps <= hi:
                    program_shares[label] += 1; break
            if t["n_novel_programs"]:
                high_contaminated["ge75"] += s >= .75
                high_contaminated["ge90"] += s >= .90
                high_contaminated["ge95"] += s >= .95
        out[category] = {"cell_share_buckets": dict(shares), "program_share_buckets": dict(program_shares), "high_recoverable_but_novel": high_contaminated}
    return out


def repetition(task_rows: list[dict], programs: list[dict]) -> dict:
    novel = [p["n_target_cells"] for p in programs if p["has_novel_instance"]]
    recov = [p["n_target_cells"] for p in programs if p["all_instances_exact"]]
    return {
        "novel": stats(novel), "recoverable_exact": stats(recov),
        "novel_formula_cells": sum(novel), "novel_independent_programs": len(novel),
        "recoverable_formula_cells": sum(recov), "recoverable_independent_programs": len(recov),
    }


def stats(values: list[int]) -> dict:
    return {"n": len(values), "sum": sum(values), "mean": round(sum(values) / len(values), 3) if values else None,
            "median": median(values) if values else None, "p90": percentile(sorted(values), .9), "max": max(values) if values else None}


def compression(task_rows: list[dict]) -> dict:
    out = {}
    for category in (*CATEGORIES, "OVERALL"):
        ts = task_rows if category == "OVERALL" else [x for x in task_rows if x["category"] == category]
        rows = [t for t in ts if t.get("status") == "CLASSIFIED" and t.get("n_formula_edits", 0)]
        old = sum(t["n_formula_edits"] for t in rows)
        new = sum(t.get("programgroup", {}).get("new_canonical_decisions", t["n_formula_edits"]) for t in rows)
        by_bucket = {}
        for bucket in TASK_BUCKETS:
            rs = [t for t in rows if t["task_bucket"] == bucket]
            o, n = sum(t["n_formula_edits"] for t in rs), sum(t.get("programgroup", {}).get("new_canonical_decisions", t["n_formula_edits"]) for t in rs)
            by_bucket[bucket] = {"tasks": len(rs), "old_decisions": o, "new_canonical_decisions": n, "reduction": o - n, "reduction_pct": pct(o - n, o)}
        out[category] = {"tasks_with_formula": len(rows), "old_formula_decisions": old, "new_canonical_decisions": new, "reduction": old - new, "reduction_pct": pct(old - new, old), "by_bucket": by_bucket}
    return out


def historical_by_bucket(task_rows: list[dict], label: str) -> dict:
    out = {}
    for bucket in TASK_BUCKETS:
        rows = [t for t in task_rows if t.get("task_bucket") == bucket and t.get("historical_scores", {}).get(label)]
        out[bucket] = {
            "tasks": len(rows),
            "exact_rate": pct(sum(t["historical_scores"][label]["exact"] for t in rows), len(rows)),
            "mean_modification": round(sum(t["historical_scores"][label]["modification_accuracy"] or 0 for t in rows) / len(rows), 6) if rows else None,
            "mean_regression": round(sum(t["historical_scores"][label]["regression_accuracy"] or 0 for t in rows) / len(rows), 6) if rows else None,
        }
    return out


def sensitivity(task_rows: list[dict]) -> list[dict]:
    rows = []
    for p in (.50, .75, .90, 1.00):
        for q in (0.00, .10, .25, .50):
            probs = []
            by_cat = {}
            for category in (*CATEGORIES, "OVERALL"):
                ts = task_rows if category == "OVERALL" else [t for t in task_rows if t["category"] == category]
                vals = []
                for t in ts:
                    if t.get("status") != "CLASSIFIED":
                        continue
                    if t.get("n_nonformula_edits", 0) or t.get("n_opaque_programs", 0):
                        val = 0.0
                    else:
                        a = sum(1 for x in t.get("programs", []) if x["availability_class"] == "RECOVERABLE_EXACT")
                        b = sum(1 for x in t.get("programs", []) if x["availability_class"] in {"RECOVERABLE_FINGERPRINT_ONLY", "EXISTING_BUT_NOT_TRANSLATABLE"})
                        n = t.get("n_novel_programs", 0)
                        val = (p ** a) * (p ** b) * (q ** n)
                    vals.append(val)
                by_cat[category] = round(sum(vals) / len(vals), 6) if vals else None
            rows.append({"recoverable_success_p": p, "novel_success_p": q, **by_cat})
    return rows


def render_report(summary: dict) -> str:
    def table(headers, rows):
        out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        out += ["| " + " | ".join(str(x) if x is not None else "" for x in row) + " |" for row in rows]
        return out
    dist, contam, ceil = summary["distribution"], summary["contamination"], summary["ceilings"]
    lines = [
        "# SpreadsheetBench 2 structural recoverability census",
        "",
        "Offline evaluator-side census over all 297 non-visual tasks. Model calls, prompt changes, retrieval calls, and workbook writes: **0**.",
        "Gold is used only for input→gold edit extraction, formula availability classification, and counterfactual ceilings.",
        "",
        "## Headline",
        "",
        "The benchmark is structurally heterogeneous. Cell-level recoverability and task-level exact solvability diverge because a single novel independent program contaminates an otherwise recoverable task. Financial_Model, Template, and Debugging are reported separately below.",
        "",
        "## Table A — program distribution",
        "",
    ]
    rows = []
    for cat in (*CATEGORIES, "OVERALL"):
        d = dist[cat]
        rows.append([cat, d["formula_target_cells"], d["independent_programs"], pct(d["formula_cell_counts"].get("RECOVERABLE_EXACT", 0), d["formula_target_cells"]), pct(d["program_counts"].get("RECOVERABLE_EXACT", 0), d["independent_programs"]), pct(d["program_counts"].get("RECOVERABLE_FINGERPRINT_ONLY", 0), d["independent_programs"]), pct(d["program_counts"].get("GENUINELY_NOVEL", 0), d["independent_programs"]), pct(d["program_counts"].get("OPAQUE_OR_UNSUPPORTED", 0), d["independent_programs"]), d["mixed_programs"]])
    lines += table(["category", "formula cells", "programs", "% exact recoverable cells", "% exact recoverable programs", "% fingerprint-only programs", "% novel programs", "% opaque programs", "mixed programs"], rows)
    lines += ["", "### Raw availability counts", ""]
    raw_rows = []
    for cat in (*CATEGORIES, "OVERALL"):
        d = dist[cat]
        cc, pc = d["formula_cell_counts"], d["program_counts"]
        raw_rows.append([cat, cc.get("RECOVERABLE_EXACT", 0), cc.get("RECOVERABLE_FINGERPRINT_ONLY", 0), cc.get("EXISTING_BUT_NOT_TRANSLATABLE", 0), cc.get("GENUINELY_NOVEL", 0), cc.get("OPAQUE_OR_UNSUPPORTED", 0), pc.get("RECOVERABLE_EXACT", 0), pc.get("RECOVERABLE_FINGERPRINT_ONLY", 0), pc.get("EXISTING_BUT_NOT_TRANSLATABLE", 0), pc.get("GENUINELY_NOVEL", 0), pc.get("OPAQUE_OR_UNSUPPORTED", 0)])
    lines += table(["category", "cell exact", "cell fingerprint-only", "cell non-translatable", "cell novel", "cell opaque", "program exact", "program fingerprint-only", "program non-translatable", "program novel", "program opaque"], raw_rows)
    lines += ["", "## Content edit population", ""]
    edit_rows = []
    for cat in (*CATEGORIES, "OVERALL"):
        ts = summary["tasks"] if cat == "OVERALL" else [t for t in summary["tasks"] if t["category"] == cat]
        formula_edits = [x for t in ts for x in t.get("formula_edits", [])]
        nonformula_edits = [x for t in ts for x in t.get("nonformula_edits", [])]
        edit_rows.append([cat, len(ts), len(formula_edits), sum(x["edit_type"] == "BLANK_TO_FORMULA" for x in formula_edits), sum(x["edit_type"] == "FORMULA_TO_FORMULA" for x in formula_edits), sum(x["edit_type"] == "VALUE_TO_FORMULA" for x in formula_edits), len(nonformula_edits), sum(bool(t.get("n_nonformula_edits", 0)) for t in ts if t.get("status") == "CLASSIFIED"), sum(not t.get("n_formula_edits", 0) for t in ts if t.get("status") == "CLASSIFIED"), sum(t.get("status") != "CLASSIFIED" for t in ts)])
    lines += table(["category", "tasks", "formula edits", "blank→formula", "formula→formula", "value→formula", "nonformula edits", "tasks with nonformula", "no-formula tasks", "unclassifiable tasks"], edit_rows)
    lines += ["", "## Table B — task contamination", ""]
    lines += table(["category", "tasks", "zero novel", "one novel", "2–3 novel", "≥4 novel", "opaque", "unclassifiable"], [[cat, contam[cat]["tasks"], contam[cat].get("zero_novel", 0), contam[cat].get("one_novel", 0), contam[cat].get("two_to_three_novel", 0), contam[cat].get("four_or_more_novel", 0), sum(1 for t in summary["tasks"] if (cat == "OVERALL" or t["category"] == cat) and t.get("task_bucket") == "T5_OPAQUE"), contam[cat].get("UNCLASSIFIABLE", 0)] for cat in (*CATEGORIES, "OVERALL")])
    lines += ["", "### Novel-program contamination curves", ""]
    curve_rows = []
    for cat in (*CATEGORIES, "OVERALL"):
        c = contam[cat]
        n = c["tasks"]
        curve_rows.append([cat, f'{c.get("zero_novel", 0)}/{n} ({pct(c.get("zero_novel", 0), n)}%)', f'{n - c.get("zero_novel", 0) - c.get("UNCLASSIFIABLE", 0)}/{n} ({pct(n - c.get("zero_novel", 0) - c.get("UNCLASSIFIABLE", 0), n)}%)', f'{c.get("at_least_two", 0)}/{n} ({pct(c.get("at_least_two", 0), n)}%)', f'{c.get("at_least_three", 0)}/{n} ({pct(c.get("at_least_three", 0), n)}%)', f'{c.get("at_least_five", 0)}/{n} ({pct(c.get("at_least_five", 0), n)}%)', f'{c.get("at_least_ten", 0)}/{n} ({pct(c.get("at_least_ten", 0), n)}%)', c["median_novel_programs"], c["p75_novel_programs"], c["p90_novel_programs"], c["max_novel_programs"]])
    lines += table(["category", "0 novel", "≥1 novel", "≥2 novel", "≥3 novel", "≥5 novel", "≥10 novel", "median", "p75", "p90", "max"], curve_rows)
    lines += ["", "## Table C — structural ceilings", ""]
    lines += table(["category", "strict formula-perfect", "strict full-task", "no-novel formula-perfect", "no-novel full-task", "formula-oracle full-task"], [[cat, f'{ceil[cat]["strict_recovery_formula_perfect"]}/{ceil[cat]["tasks"]} ({ceil[cat]["strict_recovery_formula_perfect_pct"]}%)', f'{ceil[cat]["strict_recovery_full_task"]}/{ceil[cat]["tasks"]} ({ceil[cat]["strict_recovery_full_task_pct"]}%)', f'{ceil[cat]["no_novel_formula_perfect"]}/{ceil[cat]["tasks"]} ({ceil[cat]["no_novel_formula_perfect_pct"]}%)', f'{ceil[cat]["no_novel_full_task"]}/{ceil[cat]["tasks"]} ({ceil[cat]["no_novel_full_task_pct"]}%)', f'{ceil[cat]["formula_oracle_full_task"]}/{ceil[cat]["tasks"]} ({ceil[cat]["formula_oracle_full_task_pct"]}%)'] for cat in (*CATEGORIES, "OVERALL")])
    lines += ["", "Strict/full-task ceilings assume every nonformula edit remains unsolved. Formula-perfect columns ignore nonformula edits and are reported separately. The formula oracle assumes every nonopaque formula program, including novel programs, is solved, while nonformula edits remain unsolved. `STRICT_RECOVERY_CEILING` is the exact-recoverable-only row; `NO_NOVEL_CEILING` additionally grants fingerprint-only/non-translatable programs (none are present in this census); `FORMULA_ORACLE_CEILING` grants all nonopaque formula programs.", ""]
    lines += ["## Earned-mechanism ceiling", ""]
    earned = summary["programgroup"]["OVERALL"]
    exact_cells = dist["OVERALL"]["formula_cell_counts"].get("RECOVERABLE_EXACT", 0)
    lines += [f'`EARNED_MECHANISM_CEILING`: {exact_cells} exact-recoverable formula target cells; {earned["uniform_grouped_cells"]} target instances lie in translation-uniform ProgramGroups under oracle target authority; {ceil["OVERALL"]["strict_recovery_full_task"]}/{ceil["OVERALL"]["tasks"]} tasks have a fully exact-recoverable formula edit set and no nonformula edits. This is an evaluator-side ceiling, not runtime accuracy.']
    lines += ["## Table D — leverage versus scorer", ""]
    leverage_rows = []
    for cat in (*CATEGORIES, "OVERALL"):
        ts = summary["tasks"] if cat == "OVERALL" else [t for t in summary["tasks"] if t["category"] == cat]
        leverage_rows.append([cat, pct(sum(t.get("recoverable_exact_formula_cells", 0) for t in ts), sum(t.get("n_formula_edits", 0) for t in ts)), pct(summary["programgroup"][cat]["uniform_grouped_cells"], summary["distribution"][cat]["formula_target_cells"]), pct(contam[cat].get("zero_novel", 0), contam[cat]["tasks"]), summary["concentration"][cat]["high_recoverable_but_novel"]["ge75"], summary["concentration"][cat]["high_recoverable_but_novel"]["ge90"], summary["concentration"][cat]["high_recoverable_but_novel"]["ge95"]])
    lines += table(["category", "exact-recoverable cell share", "ProgramGroup-uniform cell share", "zero-novel task share", "≥75% recoverable + novel", "≥90% recoverable + novel", "≥95% recoverable + novel"], leverage_rows)
    lines += ["", "## Recoverable-cell and recoverable-program concentration", ""]
    bucket_order = ["0%", "(0,25%]", "(25,50%]", "(50,75%]", "(75,100%)", "100%"]
    concentration_rows = []
    for cat in (*CATEGORIES, "OVERALL"):
        c = summary["concentration"][cat]
        concentration_rows.append([cat] + [c["cell_share_buckets"].get(b, 0) for b in bucket_order] + [c["program_share_buckets"].get(b, 0) for b in bucket_order])
    lines += table(["category", "cells 0%", "cells (0,25]", "cells (25,50]", "cells (50,75]", "cells (75,100)", "cells 100%", "programs 0%", "programs (0,25]", "programs (25,50]", "programs (50,75]", "programs (75,100)", "programs 100%"], concentration_rows)
    lines += ["", "## ProgramGroup leverage and decision compression", ""]
    pg_rows = []
    for cat in (*CATEGORIES, "OVERALL"):
        p = summary["programgroup"][cat]
        pg_rows.append([cat, p["formula_target_cells"], p["grouped_cells"], p["uniform_grouped_cells"], p["groups"], p["uniform_groups"], p["old_formula_decisions"], p["new_canonical_decisions"], p["decision_reduction"], p["decision_reduction_pct"]])
    lines += table(["category", "formula cells", "grouped cells", "uniform gold cells", "groups", "uniform groups", "old decisions", "new decisions", "reduction", "reduction %"], pg_rows)
    lines += ["", "All ProgramGroup figures are `PROGRAMGROUP_ORACLE_AUTHORITY_CEILING`: gold target authority is used evaluator-side to expose the mechanical leverage surface. They are not deployable runtime eligibility results.", ""]
    lines += ["", "## Table E — historical descriptive overlay", ""]
    for label, title in (("historical_openpyxl_control_glm", "GLM nonvisual-297 control"), ("historical_gpt_full_run", "GPT full historical run")):
        lines += [f"### {title}", ""]
        rows = []
        for bucket, v in summary["historical_by_bucket"][label].items():
            rows.append([bucket, v["tasks"], v["exact_rate"], v["mean_modification"], v["mean_regression"]])
        lines += table(["novelty bucket", "tasks", "exact %", "mean modification", "mean regression"], rows) + [""]
    lines += ["Historical overlays are descriptive joins. The GLM nonvisual-297 run is treated as the available openpyxl/control overlay; the GPT full run is not a matched causal comparison with the census.", ""]
    lines += ["### Historical overlay by category", ""]
    for cat in CATEGORIES:
        cat_tasks = [t for t in summary["tasks"] if t["category"] == cat]
        lines += [f"#### {cat}", ""]
        for label, title in (("historical_openpyxl_control_glm", "GLM control"), ("historical_gpt_full_run", "GPT full historical run")):
            rows = []
            for bucket, v in historical_by_bucket(cat_tasks, label).items():
                rows.append([bucket, v["tasks"], v["exact_rate"], v["mean_modification"], v["mean_regression"]])
            lines += [title, ""] + table(["novelty bucket", "tasks", "exact %", "mean modification", "mean regression"], rows) + [""]
    lines += ["No separate full 297-task current-LibreCalc/harness official-score overlay was present, so no unmatched partial run is promoted into this table. The per-task JSON retains the two joined historical score records where available.", ""]
    lines += ["## Category findings", ""]
    for cat in CATEGORIES:
        c = summary["category_findings"][cat]
        lines += [f"### {cat}", "", c, ""]
    lines += ["## Repetition and decision compression", "", json.dumps(summary["repetition"], indent=2), "", "## Illustrative sensitivity model", "", "These are not forecasts. They use an independence approximation over program decisions, with recoverable and fingerprint-only programs assigned the same success parameter and opaque/nonformula requirements treated as zero.", ""]
    lines += table(["p recoverable", "p novel", "overall indicative task-perfect"], [[x["recoverable_success_p"], x["novel_success_p"], x["OVERALL"]] for x in summary["sensitivity"]])
    lines += ["", "## Verdict", "", summary["verdict"], ""]
    return "\n".join(lines)


def csv_write(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    flat = []
    keys = sorted({k for row in rows for k, v in row.items() if not isinstance(v, (dict, list))})
    for row in rows:
        flat.append({k: row.get(k) for k in keys})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(flat)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "tasks.json").exists() and (OUT / "programs.json").exists() and os.environ.get("STRUCTURAL_CENSUS_RERUN") != "1":
        tasks, programs = load(OUT / "tasks.json"), load(OUT / "programs.json")
        print("Reusing completed evaluator ledgers; no workbook reread.", flush=True)
    else:
        tasks, programs = run_census()
    joined = overlays(tasks)
    dist = summarize_distribution(tasks, programs)
    contam = contamination(tasks)
    ceil = ceilings(tasks)
    pg_surface = {}
    for cat in (*CATEGORIES, "OVERALL"):
        ts = tasks if cat == "OVERALL" else [t for t in tasks if t["category"] == cat]
        pg_surface[cat] = {
            "formula_target_cells": sum(t.get("n_formula_edits", 0) for t in ts if t.get("status") == "CLASSIFIED"),
            "grouped_cells": sum(t.get("programgroup", {}).get("grouped_cells", 0) for t in ts if t.get("status") == "CLASSIFIED"),
            "uniform_grouped_cells": sum(t.get("programgroup", {}).get("uniform_grouped_cells", 0) for t in ts if t.get("status") == "CLASSIFIED"),
            "groups": sum(t.get("programgroup", {}).get("group_count", 0) for t in ts if t.get("status") == "CLASSIFIED"),
            "uniform_groups": sum(t.get("programgroup", {}).get("uniform_group_count", 0) for t in ts if t.get("status") == "CLASSIFIED"),
            "old_formula_decisions": sum(t.get("n_formula_edits", 0) for t in ts if t.get("status") == "CLASSIFIED"),
            "new_canonical_decisions": sum(t.get("programgroup", {}).get("new_canonical_decisions", 0) for t in ts if t.get("status") == "CLASSIFIED"),
        }
        pg_surface[cat]["grouped_share"] = pct(pg_surface[cat]["grouped_cells"], pg_surface[cat]["formula_target_cells"])
        pg_surface[cat]["uniform_grouped_share"] = pct(pg_surface[cat]["uniform_grouped_cells"], pg_surface[cat]["formula_target_cells"])
        pg_surface[cat]["decision_reduction"] = pg_surface[cat]["old_formula_decisions"] - pg_surface[cat]["new_canonical_decisions"]
        pg_surface[cat]["decision_reduction_pct"] = pct(pg_surface[cat]["decision_reduction"], pg_surface[cat]["old_formula_decisions"])
    category_findings = {}
    for cat in CATEGORIES:
        d, c, ce = dist[cat], contam[cat], ceil[cat]
        if cat == "Financial_Model":
            readable = [t for t in tasks if t["category"] == cat and t.get("status") == "CLASSIFIED"]
            fm_blank = sum(1 for t in readable for x in t.get("formula_edits", []) if x["edit_type"] == "BLANK_TO_FORMULA")
            fm_blank_exact = sum(1 for t in readable for x in t.get("formula_edits", []) if x["edit_type"] == "BLANK_TO_FORMULA" and x.get("availability_class") == "RECOVERABLE_EXACT")
            finding = f'{cat}: {d["formula_target_cells"]} formula target cells across {d["independent_programs"]} programs; {d["formula_cell_counts"].get("RECOVERABLE_EXACT", 0)} exact-recoverable cells ({pct(d["formula_cell_counts"].get("RECOVERABLE_EXACT", 0), d["formula_target_cells"])}%). {c.get("zero_novel", 0)}/{c["tasks"]} tasks are confirmed zero-novel; 5 FM tasks are UNCLASSIFIABLE, so at most 7/100 can currently be said to be zero-novel. On the 95 readable tasks, exact legal recovery covers {fm_blank_exact}/{fm_blank} blank→formula edits ({pct(fm_blank_exact, fm_blank)}%). The earlier ~40.7% FM blank→formula figure is not directly comparable: it used a different existing-fingerprint/program criterion and denominator; this census requires exact mechanical translation and includes all formula edit types.'
        elif cat == "Template":
            finding = f'{cat}: {c.get("zero_novel", 0)}/{c["tasks"]} tasks have zero novel programs; {sum(1 for t in tasks if t["category"] == cat and t.get("n_formula_edits", 0) == 0)}/{c["tasks"]} have no formula edits. Formula-program burden and nonformula/template work must be kept separate.'
        else:
            finding = f'{cat}: {d["formula_target_cells"]} formula target cells across {d["independent_programs"]} programs; {sum(1 for t in tasks if t["category"] == cat and any(x["edit_type"] == "FORMULA_TO_FORMULA" for x in t.get("formula_edits", [])))} tasks contain formula-to-formula edits. Structural recoverability is an opportunity ceiling, not historical debugging success.'
        category_findings[cat] = finding
    summary = {
        "tasks": tasks,
        "population": {"tasks": len(tasks), "categories": {c: sum(t["category"] == c for t in tasks) for c in CATEGORIES}, "unclassifiable": sum(t.get("status") != "CLASSIFIED" for t in tasks)},
        "distribution": dist, "contamination": contam, "ceilings": ceil, "concentration": concentration(tasks),
        "programgroup": pg_surface, "repetition": repetition(tasks, programs), "compression": compression(tasks),
        "historical_runs": joined, "historical_by_bucket": {label: historical_by_bucket(tasks, label) for label in joined},
        "sensitivity": sensitivity(tasks), "category_findings": category_findings,
        "verdict": "CATEGORY_HETEROGENEOUS + CELL_RECOVERABLE_TASK_NOVEL_CONTAMINATED: structural recovery is a real cell-level regime, but task exactness is capped by per-task novel-program contamination; category distributions must not be collapsed into one benchmark-wide story.",
        "constraints": {"model_calls": 0, "prompt_changes": 0, "retrieval_calls": 0, "workbook_writes": 0, "gold_runtime": False},
    }
    write(OUT / "summary.json", summary)
    write(OUT / "CENSUS_REPORT.md", render_report(summary))
    csv_write(OUT / "tasks.csv", tasks)
    csv_write(OUT / "programs.csv", programs)
    print(json.dumps({"output": str(OUT), "tasks": len(tasks), "programs": len(programs), "unclassifiable": summary["population"]["unclassifiable"], "headline": summary["verdict"]}, indent=2))


if __name__ == "__main__":
    main()
