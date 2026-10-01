#!/usr/bin/env python3
"""Run the mechanically certified formula-completion experiment.

Phases are separate so the certificate set can be frozen before goldens are
opened. No LLM. No harness change.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from formula_completion_certs import (  # noqa: E402
    DEFINITIONS,
    RULES,
    apply_certificates,
    certificates_for_workbook,
)
from fingerprint import formula_text, relative_fingerprint  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

from score_openrouter_run import score_run  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-completion"
)
CATEGORIES = ("Financial_Model", "Debugging", "Template")
ARMS = ("INPUT_BASELINE", "LR_ONLY", "UD_ONLY", "CROSS_ONLY", "K2_ONLY", "K3_ONLY", "K4_ONLY")
ARM_RULE = {
    "LR_ONLY": "LR",
    "UD_ONLY": "UD",
    "CROSS_ONLY": "CROSS",
    "K2_ONLY": "K2",
    "K3_ONLY": "K3",
    "K4_ONLY": "K4",
}


def _pct(values: list[int | float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[low])
    return float(ordered[low] * (high - rank) + ordered[high] * (rank - low))


def _summarize_counts(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p90": None, "max": None}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 4),
        "median": _pct(values, 50),
        "p90": _pct(values, 90),
        "max": max(values),
    }


def _rate(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return round(num / den, 4)


def _task_list(category: str) -> list[dict[str, str]]:
    return json.loads((DATA / category / "dataset.json").read_text())


def _cert_path(category: str, task_id: str) -> Path:
    return OUT / "certificates" / category / f"{task_id}.json"


def _load_task_certs(category: str, task_id: str) -> dict[str, Any]:
    return json.loads(_cert_path(category, task_id).read_text())


def generate(categories: tuple[str, ...] = CATEGORIES, limit: int = 0) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "definitions": DEFINITIONS,
        "rules": list(RULES),
        "arms": list(ARMS),
        "golden_used": False,
        "note": "Certificate generation is gold-blind. Do not edit this freeze after evaluate.",
    }
    (OUT / "definitions.json").write_text(json.dumps(freeze, indent=2) + "\n")
    for category in categories:
        tasks = _task_list(category)
        if limit:
            tasks = tasks[:limit]
        dest_dir = OUT / "certificates" / category
        dest_dir.mkdir(parents=True, exist_ok=True)
        for index, task in enumerate(tasks, 1):
            task_id = task["id"]
            dest = dest_dir / f"{task_id}.json"
            if dest.is_file():
                print(f"SKIP {category}:{task_id} existing", flush=True)
                continue
            source = DATA / category / task["spreadsheet_path"]
            print(f"GEN {index}/{len(tasks)} {category}:{task_id}", flush=True)
            try:
                payload = certificates_for_workbook(source)
            except Exception as exc:  # noqa: BLE001
                payload = {
                    "path": str(source),
                    "error": f"{type(exc).__name__}: {exc}",
                    "certificates": {rule: [] for rule in RULES},
                    "conflicts": [],
                    "lr_ud_disagree": [],
                    "sheets": 0,
                    "formula_cells": 0,
                }
            payload["category"] = category
            payload["task_id"] = task_id
            dest.write_text(json.dumps(payload) + "\n")
    _write_census(categories, limit)


def _iter_generated(categories: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
    rows = []
    for category in categories:
        tasks = _task_list(category)
        if limit:
            tasks = tasks[:limit]
        for task in tasks:
            path = _cert_path(category, task["id"])
            if path.is_file():
                rows.append(json.loads(path.read_text()))
    return rows


def _write_census(categories: tuple[str, ...], limit: int) -> None:
    census: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "definitions": DEFINITIONS,
        "categories": {},
    }
    for category in categories:
        tasks = _task_list(category)
        if limit:
            tasks = tasks[:limit]
        rule_counts: dict[str, list[int]] = {rule: [] for rule in RULES}
        workbooks_with = Counter()
        distances: dict[str, list[int]] = {rule: [] for rule in RULES}
        adjacent = Counter()
        nonadjacent = Counter()
        same_class = Counter()
        mixed_class = Counter()
        axes = Counter()
        lr_only = ud_only = both_present = both_agree = both_disagree = 0
        k_overlap = Counter()
        conflicts = Counter()
        errors = 0
        formula_cells = []
        for task in tasks:
            path = _cert_path(category, task["id"])
            if not path.is_file():
                continue
            payload = json.loads(path.read_text())
            if payload.get("error"):
                errors += 1
            formula_cells.append(payload.get("formula_cells") or 0)
            certs = payload.get("certificates") or {}
            lr_keys = {(c["sheet"], c["col"], c["row"]) for c in certs.get("LR", [])}
            ud_keys = {(c["sheet"], c["col"], c["row"]) for c in certs.get("UD", [])}
            disagree = {
                (item["sheet"], item["address"])
                for item in payload.get("lr_ud_disagree") or []
            }
            lr_only += len(lr_keys - ud_keys)
            ud_only += len(ud_keys - lr_keys)
            both_present += len(lr_keys & ud_keys)
            both_agree += len(certs.get("CROSS") or [])
            both_disagree += len(disagree)
            k_sets = {
                k: {(c["sheet"], c["col"], c["row"]) for c in certs.get(f"K{k}", [])}
                for k in (2, 3, 4)
            }
            k_overlap["K2"] += len(k_sets[2])
            k_overlap["K3"] += len(k_sets[3])
            k_overlap["K4"] += len(k_sets[4])
            k_overlap["K2_and_LR"] += len(k_sets[2] & lr_keys)
            k_overlap["K2_and_UD"] += len(k_sets[2] & ud_keys)
            k_overlap["K2_and_CROSS"] += len(
                k_sets[2] & {(c["sheet"], c["col"], c["row"]) for c in certs.get("CROSS", [])}
            )
            for conflict in payload.get("conflicts") or []:
                conflicts[conflict["rule"]] += 1
            for rule in RULES:
                items = certs.get(rule) or []
                rule_counts[rule].append(len(items))
                if items:
                    workbooks_with[rule] += 1
                for cert in items:
                    distances[rule].append(cert.get("max_distance") or 0)
                    if cert.get("adjacent"):
                        adjacent[rule] += 1
                    else:
                        nonadjacent[rule] += 1
                    if cert.get("same_equivalence_class"):
                        same_class[rule] += 1
                    else:
                        mixed_class[rule] += 1
                    axis_key = "+".join(cert.get("axes") or [])
                    axes[(rule, axis_key)] += 1
        census["categories"][category] = {
            "tasks": len(tasks),
            "generation_errors": errors,
            "formula_cells": _summarize_counts(formula_cells),
            "rules": {
                rule: {
                    "workbooks_with_certificate": workbooks_with[rule],
                    "certified_blank_cells": sum(rule_counts[rule]),
                    "per_workbook": _summarize_counts(rule_counts[rule]),
                    "adjacent": adjacent[rule],
                    "nonadjacent": nonadjacent[rule],
                    "same_equivalence_class": same_class[rule],
                    "mixed_equivalence_class": mixed_class[rule],
                    "max_distance": _summarize_counts(distances[rule]),
                }
                for rule in RULES
            },
            "overlap": {
                "lr_only": lr_only,
                "ud_only": ud_only,
                "lr_and_ud_present": both_present,
                "lr_ud_agreeing": both_agree,
                "lr_ud_disagreeing": both_disagree,
                "k": dict(k_overlap),
                "k_conflicts": dict(conflicts),
            },
            "axes": {f"{rule}:{axis}": n for (rule, axis), n in sorted(axes.items())},
        }
    (OUT / "census.json").write_text(json.dumps(census, indent=2) + "\n")
    print(f"CENSUS {OUT / 'census.json'}", flush=True)


def _cell_map(path: Path) -> dict[tuple[str, int, int], object]:
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    out: dict[tuple[str, int, int], object] = {}
    try:
        for sheet in workbook.worksheets:
            for cell in sheet._cells.values():
                out[(sheet.title, int(cell.column), int(cell.row))] = cell.value
    finally:
        workbook.close()
    return out


def _blank(value: object) -> bool:
    if formula_text(value):
        return False
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _classify(cert: dict[str, Any], golden_value: object | None) -> str:
    golden_formula = formula_text(golden_value)
    if golden_formula:
        fp = relative_fingerprint(
            golden_formula, cert["col"], cert["row"], sheet=cert["sheet"]
        )
        if fp.opaque:
            return "E"
        if fp.text == cert["candidate_fingerprint"]:
            return "A"
        return "B"
    if _blank(golden_value):
        return "C"
    return "D"


def _blank_formula_targets(
    input_cells: dict[tuple[str, int, int], object],
    golden_cells: dict[tuple[str, int, int], object],
) -> list[dict[str, Any]]:
    targets = []
    keys = set(input_cells) | set(golden_cells)
    for key in keys:
        if not _blank(input_cells.get(key)):
            continue
        golden_formula = formula_text(golden_cells.get(key))
        if not golden_formula:
            continue
        sheet, col, row = key
        fp = relative_fingerprint(golden_formula, col, row, sheet=sheet)
        targets.append(
            {
                "sheet": sheet,
                "col": col,
                "row": row,
                "opaque": fp.opaque,
                "fingerprint": fp.text,
            }
        )
    return targets


def evaluate(categories: tuple[str, ...] = CATEGORIES, limit: int = 0) -> None:
    freeze = json.loads((OUT / "definitions.json").read_text())
    report: dict[str, Any] = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "categories": {},
        "examples": {"A": [], "B": [], "C": [], "D": [], "E": [], "conflict": []},
    }
    for category in categories:
        tasks = _task_list(category)
        if limit:
            tasks = tasks[:limit]
        rule_stats: dict[str, Any] = {}
        totals = {rule: {"correct": 0, "targets": 0} for rule in RULES}
        for rule in RULES:
            rule_stats[rule] = {
                "A": 0,
                "B": 0,
                "C": 0,
                "D": 0,
                "E": 0,
                "task_action_precision": [],
                "task_formula_precision": [],
                "task_recall": [],
                "tasks_with_correct": 0,
                "tasks_cover_10": 0,
                "tasks_cover_25": 0,
                "tasks_cover_50": 0,
                "correct_on_adjacent": 0,
                "adjacent": 0,
                "correct_on_distant": 0,
                "distant": 0,
                "correct_same_class": 0,
                "same_class": 0,
                "correct_mixed_class": 0,
                "mixed_class": 0,
            }
        for task in tasks:
            task_id = task["id"]
            cert_file = _cert_path(category, task_id)
            if not cert_file.is_file():
                continue
            payload = json.loads(cert_file.read_text())
            inp = DATA / category / task["spreadsheet_path"]
            gold = DATA / category / task["golden_response_path"]
            try:
                input_cells = _cell_map(inp)
                golden_cells = _cell_map(gold)
            except Exception as exc:  # noqa: BLE001
                print(f"EVAL-ERROR {category}:{task_id} {type(exc).__name__}: {exc}", flush=True)
                continue
            targets = _blank_formula_targets(input_cells, golden_cells)
            target_keys = {(row["sheet"], row["col"], row["row"]) for row in targets}
            n_targets = len(targets)
            for rule in RULES:
                totals[rule]["targets"] += n_targets
            print(
                f"EVAL {category}:{task_id} blanks_to_formula={n_targets}",
                flush=True,
            )
            for conflict in (payload.get("conflicts") or [])[:2]:
                if len(report["examples"]["conflict"]) < 8:
                    report["examples"]["conflict"].append(
                        {"task": f"{category}:{task_id}", **conflict}
                    )
            for rule in RULES:
                stats = rule_stats[rule]
                classes = Counter()
                correct_keys: set[tuple[str, int, int]] = set()
                for cert in payload.get("certificates", {}).get(rule, []):
                    key = (cert["sheet"], cert["col"], cert["row"])
                    label = _classify(cert, golden_cells.get(key))
                    classes[label] += 1
                    stats[label] += 1
                    if cert.get("adjacent"):
                        stats["adjacent"] += 1
                        if label == "A":
                            stats["correct_on_adjacent"] += 1
                    else:
                        stats["distant"] += 1
                        if label == "A":
                            stats["correct_on_distant"] += 1
                    if cert.get("same_equivalence_class"):
                        stats["same_class"] += 1
                        if label == "A":
                            stats["correct_same_class"] += 1
                    else:
                        stats["mixed_class"] += 1
                        if label == "A":
                            stats["correct_mixed_class"] += 1
                    if label == "A":
                        correct_keys.add(key)
                        if key in target_keys:
                            totals[rule]["correct"] += 1
                    if (
                        label in report["examples"]
                        and len(report["examples"][label]) < 6
                    ):
                        report["examples"][label].append(
                            {
                                "task": f"{category}:{task_id}",
                                "rule": rule,
                                "target": f"{cert['sheet']}!{cert['address']}",
                                "candidate": cert["candidate"],
                                "class": label,
                                "adjacent": cert.get("adjacent"),
                                "agreeing_sources": cert.get("agreeing_sources"),
                            }
                        )
                certified = sum(classes.values())
                formula_den = classes["A"] + classes["B"] + classes["E"]
                stats["task_action_precision"].append(_rate(classes["A"], certified))
                stats["task_formula_precision"].append(_rate(classes["A"], formula_den))
                recall = _rate(len(correct_keys), n_targets) if n_targets else None
                stats["task_recall"].append(recall)
                if classes["A"]:
                    stats["tasks_with_correct"] += 1
                if n_targets:
                    cover = len(correct_keys) / n_targets
                    if cover >= 0.10:
                        stats["tasks_cover_10"] += 1
                    if cover >= 0.25:
                        stats["tasks_cover_25"] += 1
                    if cover >= 0.50:
                        stats["tasks_cover_50"] += 1
        packed = {}
        for rule, stats in rule_stats.items():
            a, b, c, d, e = (stats["A"], stats["B"], stats["C"], stats["D"], stats["E"])
            certified = a + b + c + d + e
            packed[rule] = {
                "cell_weighted": {
                    "A_exact": a,
                    "B_wrong_formula": b,
                    "C_intended_blank": c,
                    "D_golden_value": d,
                    "E_ambiguous": e,
                    "certified_cells": certified,
                    "formula_precision": _rate(a, a + b + e),
                    "action_precision": _rate(a, certified),
                },
                "task_weighted": {
                    "action_precision_mean": _mean(stats["task_action_precision"]),
                    "formula_precision_mean": _mean(stats["task_formula_precision"]),
                    "recall_mean": _mean(stats["task_recall"]),
                    "tasks_with_ge1_correct": stats["tasks_with_correct"],
                    "tasks_cover_10pct": stats["tasks_cover_10"],
                    "tasks_cover_25pct": stats["tasks_cover_25"],
                    "tasks_cover_50pct": stats["tasks_cover_50"],
                    "n_tasks": len(tasks),
                },
                "strata": {
                    "adjacent_action_precision": _rate(
                        stats["correct_on_adjacent"], stats["adjacent"]
                    ),
                    "distant_action_precision": _rate(
                        stats["correct_on_distant"], stats["distant"]
                    ),
                    "same_class_action_precision": _rate(
                        stats["correct_same_class"], stats["same_class"]
                    ),
                    "mixed_class_action_precision": _rate(
                        stats["correct_mixed_class"], stats["mixed_class"]
                    ),
                },
                "target_recall_cell_weighted": _rate(
                    totals[rule]["correct"], totals[rule]["targets"]
                ),
                "golden_blank_to_formula_targets": totals[rule]["targets"],
                "correct_certificates_on_targets": totals[rule]["correct"],
            }
        report["categories"][category] = packed
    freeze["golden_used"] = True
    freeze["evaluated_at"] = report["evaluated_at"]
    (OUT / "definitions.json").write_text(json.dumps(freeze, indent=2) + "\n")
    (OUT / "golden_eval.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"GOLDEN {OUT / 'golden_eval.json'}", flush=True)


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if isinstance(value, (int, float))]
    if not present:
        return None
    return round(statistics.mean(present), 4)


def execute(
    categories: tuple[str, ...] = ("Financial_Model",),
    limit: int = 0,
    arms: tuple[str, ...] = ARMS,
) -> None:
    summary: dict[str, Any] = {
        "executed_at": datetime.now(UTC).isoformat(),
        "categories": list(categories),
        "arms": {},
    }
    for arm in arms:
        run_root = OUT / "execute" / arm
        writes_total = 0
        tasks_n = 0
        scored_path = run_root / "official_scores.json"
        if scored_path.is_file():
            official = json.loads(scored_path.read_text())
            summary["arms"][arm] = {
                "edits": None,
                "tasks": official.get("scored"),
                "skipped_existing_scores": True,
                "official": {
                    "exact": official.get("exact"),
                    "scored": official.get("scored"),
                },
                "tasks_detail": official.get("tasks"),
            }
            print(f"SKIP-SCORE {arm} existing={scored_path}", flush=True)
            continue
        for category in categories:
            tasks = _task_list(category)
            if limit:
                tasks = tasks[:limit]
            for task in tasks:
                task_id = task["id"]
                source = DATA / category / task["spreadsheet_path"]
                dest_dir = run_root / f"{category}-{task_id}"
                dest = dest_dir / "output.xlsx"
                dest_dir.mkdir(parents=True, exist_ok=True)
                if dest.is_file():
                    print(f"SKIP {arm} {category}:{task_id} existing", flush=True)
                    tasks_n += 1
                    continue
                if arm == "INPUT_BASELINE":
                    shutil.copy2(source, dest)
                    written = 0
                else:
                    payload = _load_task_certs(category, task_id)
                    certs = payload.get("certificates", {}).get(ARM_RULE[arm], [])
                    stats = apply_certificates(source, dest, certs)
                    written = stats["written"]
                writes_total += written
                tasks_n += 1
                print(f"WRITE {arm} {category}:{task_id} edits={written}", flush=True)
        print(f"SCORE {arm} tasks={tasks_n}", flush=True)
        score_run(run_root, model_name=f"formula-completion-{arm}", write_ledger=False)
        official = json.loads((run_root / "official_scores.json").read_text())
        summary["arms"][arm] = {
            "edits": writes_total,
            "tasks": tasks_n,
            "official": official.get("summary") or {
                "exact": official.get("exact"),
                "scored": official.get("scored"),
            },
            "tasks_detail": official.get("tasks"),
        }
    (OUT / "execute_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    _write_execute_comparison(summary, categories, limit)
    print(f"EXECUTE {OUT / 'execute_summary.json'}", flush=True)


def _write_execute_comparison(
    summary: dict[str, Any], categories: tuple[str, ...], limit: int
) -> None:
    baseline = summary["arms"].get("INPUT_BASELINE", {}).get("tasks_detail") or {}
    comparison: dict[str, Any] = {"baseline": "INPUT_BASELINE", "arms": {}}
    golden = json.loads((OUT / "golden_eval.json").read_text()) if (OUT / "golden_eval.json").is_file() else {}
    for arm, payload in summary["arms"].items():
        details = payload.get("tasks_detail") or {}
        improved = worsened = gained = lost = 0
        mod_base = []
        mod_arm = []
        reg_base = []
        reg_arm = []
        exact_base = exact_arm = 0
        for key, row in details.items():
            left = baseline.get(key) or {}
            b_mod = left.get("modification_accuracy") or 0.0
            a_mod = row.get("modification_accuracy") or 0.0
            b_reg = left.get("regression_accuracy") or 0.0
            a_reg = row.get("regression_accuracy") or 0.0
            b_ex = left.get("accuracy") == 1.0
            a_ex = row.get("accuracy") == 1.0
            mod_base.append(b_mod)
            mod_arm.append(a_mod)
            reg_base.append(b_reg)
            reg_arm.append(a_reg)
            exact_base += int(b_ex)
            exact_arm += int(a_ex)
            if a_mod > b_mod or a_reg > b_reg or (a_ex and not b_ex):
                improved += 1
            if a_mod < b_mod or a_reg < b_reg or (b_ex and not a_ex):
                worsened += 1
            if a_ex and not b_ex:
                gained += 1
            if b_ex and not a_ex:
                lost += 1
        rule = ARM_RULE.get(arm)
        eval_row = {}
        if rule:
            for category in categories:
                eval_row = (golden.get("categories") or {}).get(category, {}).get(rule) or eval_row
        comparison["arms"][arm] = {
            "edits": payload.get("edits"),
            "exact": f"{exact_arm}/{len(details)}",
            "exact_baseline": f"{exact_base}/{len(details)}",
            "exacts_gained": gained,
            "exacts_lost": lost,
            "tasks_improved": improved,
            "tasks_worsened": worsened,
            "modification_accuracy_mean": _mean(mod_arm),
            "modification_accuracy_baseline_mean": _mean(mod_base),
            "regression_accuracy_mean": _mean(reg_arm),
            "regression_accuracy_baseline_mean": _mean(reg_base),
            "precision_per_edit": (eval_row.get("cell_weighted") or {}).get(
                "action_precision"
            ),
            "correct_formula_writes": (eval_row.get("cell_weighted") or {}).get("A_exact"),
            "intended_blank_writes": (eval_row.get("cell_weighted") or {}).get(
                "C_intended_blank"
            ),
            "wrong_formula_writes": (eval_row.get("cell_weighted") or {}).get(
                "B_wrong_formula"
            ),
            "value_type_writes": (eval_row.get("cell_weighted") or {}).get(
                "D_golden_value"
            ),
        }
    (OUT / "execute_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=("generate", "evaluate", "execute", "census", "all-offline", "all"),
    )
    parser.add_argument("--category", action="append")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--arm", action="append")
    args = parser.parse_args()
    categories = tuple(args.category) if args.category else CATEGORIES
    if args.phase == "generate":
        generate(categories, args.limit)
    elif args.phase == "census":
        _write_census(categories, args.limit)
    elif args.phase == "evaluate":
        evaluate(categories, args.limit)
    elif args.phase == "execute":
        arms = tuple(args.arm) if args.arm else ARMS
        execute(categories, args.limit, arms)
    elif args.phase == "all-offline":
        generate(categories, args.limit)
        evaluate(categories, args.limit)
    elif args.phase == "all":
        generate(categories, args.limit)
        evaluate(categories, args.limit)
        execute(
            ("Financial_Model",) if categories == CATEGORIES else categories,
            args.limit,
            tuple(args.arm) if args.arm else ARMS,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
