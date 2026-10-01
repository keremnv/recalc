#!/usr/bin/env python3
"""Zero-model write-to-score bridge audit for the contaminated treatment run.

It reads the persisted treatment ledgers and workbooks, refreshes copies with
LibreOffice, and compares formula-level, value-level, and official evaluator
target cells.  It never calls the model and never changes the treatment code.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils.cell import coordinate_to_tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark-data" / "SpreadsheetBench-2" / "evaluation"))
import integration_autopsy as ia  # noqa: E402
import matched_compiled_treatment as m  # noqa: E402
import fm_resource_feasibility as f  # noqa: E402
import evaluation as ev  # noqa: E402


RUN = f.RUN_ROOT
LIVE = f.REPAIRED_LIVE
AUDIT = RUN / "bridge_audit"
BRIDGE_SCORE = AUDIT / "bridge_score_run"
PRIMARY = ["03_01", "13_05", "14_05", "17_05"]
NEGATIVE = ["01_01", "05_01"]
TASKS = PRIMARY + NEGATIVE


def load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        out = csv.DictWriter(handle, fieldnames=fields)
        out.writeheader()
        for row in rows:
            out.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def raw_cells(path: Path, *, data_only: bool) -> dict[tuple[str, int, int], Any]:
    wb = openpyxl.load_workbook(path, data_only=data_only)
    try:
        out: dict[tuple[str, int, int], Any] = {}
        for ws in wb.worksheets:
            for cell in ws._cells.values():
                value = cell.value
                if hasattr(value, "text"):
                    value = value.text
                if value is not None:
                    out[(ws.title, cell.row, cell.column)] = value
        return out
    finally:
        wb.close()


def label(cell: tuple[str, int, int]) -> str:
    return f"{cell[0]}!{m.closure.a1(cell[1], cell[2])}"


def cell_addr(cell: tuple[str, int, int]) -> str:
    return f"{cell[0]}!{m.closure.a1(cell[1], cell[2])}"


def formula_equal(a: Any, b: Any) -> bool:
    return ia.exact(a, b)


def formula_fingerprint(value: Any, cell: tuple[str, int, int]) -> str | None:
    try:
        return ia.fp(value, cell)
    except Exception:
        return None


def has_excel_error_value(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("#")


def official_target_sets(task: str) -> dict[str, Any]:
    row = m.task_map()[f.key(task)]
    wi = ia.compact_workbook(row["input_path"], data_only=True)
    wg = ia.compact_workbook(row["gold_path"], data_only=True)
    wif = ia.compact_workbook(row["input_path"], data_only=False)
    wgf = ia.compact_workbook(row["gold_path"], data_only=False)
    modification: set[tuple[str, str]] = set()
    regression: set[tuple[str, str]] = set()
    for spec in ev.parse_answer_position(row["answer_position"]):
        sheet, cell_range = spec.split("!", 1) if "!" in spec else (wg.sheetnames[0], spec)
        sheet, cell_range = sheet.strip("'").strip(), cell_range.strip("'").strip()
        reg, mod = ev.classify_cells_by_modification(
            wi, wg, sheet, cell_range, False, False,
            wb_input_formula=wif, wb_answer_formula=wgf,
        )
        modification.update((sheet, c) for c in mod)
        regression.update((sheet, c) for c in reg)
    return {"modification": modification, "regression": regression, "input": wi, "gold": wg, "input_formula": wif, "gold_formula": wgf}


def official_cell_correct(official: dict[str, Any], task: str, cell: tuple[str, int, int], output_path: Path) -> tuple[bool | None, Any, Any]:
    if not output_path.exists():
        return None, None, None
    # Keep one output workbook cache per invocation through the caller; this
    # helper is replaced by the cached maps in build_lineage below.
    out = ia.compact_workbook(output_path, data_only=True)
    outf = ia.compact_workbook(output_path, data_only=False)
    sheet, address = cell[0], m.closure.a1(cell[1], cell[2])
    ws_gold = ev._find_sheet(official["gold"], sheet)
    ws_out = ev._find_sheet(out, sheet)
    if ws_gold is None or ws_out is None:
        return False, None, None
    gold_value, out_value = ws_gold[address].value, ws_out[address].value
    ws_gold_f = ev._find_sheet(official["gold_formula"], sheet)
    ws_out_f = ev._find_sheet(outf, sheet)
    fallback = ev._has_excel_error(gold_value) or ev._has_excel_error(out_value)
    if fallback and ws_gold_f is not None and ws_out_f is not None:
        ok = ev.compare_cell_formula(ws_gold_f[address], ws_out_f[address])
    else:
        ok = ev._compare_cells(ws_gold[address], ws_out[address], False, False)
    return ok, gold_value, out_value


def bridge_freeze() -> dict[str, Any]:
    files = {
        "task_ir": ROOT / "benchmark" / "task_obligation_compile.py",
        "frontend": ROOT / "benchmark" / "frontend_projection.py",
        "treatment": ROOT / "benchmark" / "matched_compiled_treatment.py",
        "scheduler": ROOT / "benchmark" / "compiled_scheduler.py",
        "closure": ROOT / "benchmark" / "composition_closure.py",
        "writer": ROOT / "benchmark" / "xlsx_cell_writer.py",
        "scorer": ROOT / "benchmark-data" / "SpreadsheetBench-2" / "evaluation" / "evaluation.py",
        "recalc": ROOT / "benchmark-data" / "SpreadsheetBench-2" / "evaluation" / "open_spreadsheet.py",
    }
    hashes = {name: digest(path) for name, path in files.items() if path.exists()}
    freeze = load(RUN / "freeze.json", {})
    result = {
        "phase": "A_zero_model_write_to_score_bridge_audit",
        "model_calls": 0,
        "tasks": [f"Financial_Model:{x}" for x in TASKS],
        "source_hashes": hashes,
        "freeze_sha256": hashlib.sha256(json.dumps(freeze, sort_keys=True).encode()).hexdigest(),
        "model_config": freeze.get("model_config"),
        "reasoning_request_field": freeze.get("reasoning_request_field"),
        "reasoning_request_value": freeze.get("reasoning_request_value"),
        "architecture_change": False,
        "prompt_change": False,
        "scorer_change": False,
    }
    dump(AUDIT / "bridge_freeze.json", result)
    return result


def group_maps(schedule: dict[str, Any]) -> tuple[dict[tuple[str, int, int], str], dict[tuple[str, int, int], dict[str, Any]]]:
    cell_to_group: dict[tuple[str, int, int], str] = {}
    groups: dict[tuple[str, int, int], dict[str, Any]] = {}
    for ui, unit in enumerate(schedule.get("groups") or []):
        for gi, group in enumerate(unit.get("groups") or []):
            gid = f"U{ui + 1}.G{gi + 1}:{group.get('operation_id') or ''}"
            for raw in group.get("member_cells") or []:
                if isinstance(raw, list) and len(raw) == 3:
                    cell_to_group[tuple(raw)] = gid
            canonical = tuple(group.get("canonical_cell") or ())
            groups[canonical] = {"group_id": gid, "unit_index": ui, "group_index": gi, "group": group}
    return cell_to_group, groups


def build_lineage(task: str, *, lo_paths: dict[str, Path], official_bridge: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    directory = LIVE / f"Financial_Model-{task}"
    result = load(directory / "result.json", {})
    schedule = result.get("schedule") or {}
    source_path = m.task_source(f.key(task))
    runtime_path = directory / "output.xlsx"
    staged_path = LIVE / "submission" / "outputs" / "Financial_Model" / f"{task}_output.xlsx"
    lo_path = lo_paths.get(task)
    source_formula = raw_cells(source_path, data_only=False)
    gold_formula = raw_cells(Path(m.task_map()[f.key(task)]["gold_path"]), data_only=False)
    runtime_formula = raw_cells(runtime_path, data_only=False) if runtime_path.exists() else {}
    staged_formula = raw_cells(staged_path, data_only=False) if staged_path.exists() else {}
    lo_formula = raw_cells(lo_path, data_only=False) if lo_path and lo_path.exists() else {}
    lo_values = raw_cells(lo_path, data_only=True) if lo_path and lo_path.exists() else {}
    source_values = raw_cells(source_path, data_only=True)
    gold_values = raw_cells(Path(m.task_map()[f.key(task)]["gold_path"]), data_only=True)
    official = official_target_sets(task)
    cell_to_group, group_by_canonical = group_maps(schedule)
    translations = {tuple(x["cell"]): x.get("formula") for x in schedule.get("translated_formula_instances") or [] if isinstance(x, dict) and isinstance(x.get("cell"), list)}
    canonical = {tuple(x.get("seed")): x for x in schedule.get("canonical_decisions") or [] if isinstance(x, dict) and isinstance(x.get("seed"), list)}
    applied = {}
    for x in (result.get("write_audit") or {}).get("applied", []) or []:
        if x.get("sheet") and x.get("address"):
            row, col = coordinate_to_tuple(x["address"])
            applied[(x["sheet"], row, col)] = x.get("formula")
    rows: list[dict[str, Any]] = []
    for cell, writer_formula in sorted(applied.items()):
        translated_formula = translations.get(cell)
        canonical_record = canonical.get(cell)
        proposal_formula = translated_formula if translated_formula is not None else (canonical_record or {}).get("formula")
        proposal_kind = "TRANSLATION" if translated_formula is not None and cell_to_group.get(cell) else "CANONICAL_OR_UNGROUPED"
        exact = formula_equal(proposal_formula, gold_formula.get(cell))
        fp_match = formula_fingerprint(proposal_formula, cell) is not None and formula_fingerprint(proposal_formula, cell) == formula_fingerprint(gold_formula.get(cell), cell)
        group_id = cell_to_group.get(cell)
        verifier = None
        if canonical_record:
            session = canonical_record.get("session") or {}
            verifier = ((session.get("validation") or {}).get("hard_verifier_result") or session.get("hard_verifier_result"))
        runtime_value = runtime_formula.get(cell)
        staged_value = staged_formula.get(cell)
        lo_formula_value = lo_formula.get(cell)
        lo_value = lo_values.get(cell)
        official_key = (cell[0], m.closure.a1(cell[1], cell[2]))
        official_target = official_key in official["modification"]
        official_correct = None
        if official_target and cell in lo_values:
            gold_value = gold_values.get(cell)
            actual_value = lo_values.get(cell)
            if has_excel_error_value(gold_value) or has_excel_error_value(actual_value):
                official_correct = ev.compare_cell_formula(official["gold_formula"][cell[0]][m.closure.a1(cell[1], cell[2])], ia.compact_workbook(lo_path, data_only=False)[cell[0]][m.closure.a1(cell[1], cell[2])]) if lo_path else False
            else:
                official_correct = ev.compare_cell_value(gold_value, actual_value)
        runtime_persisted = runtime_value == writer_formula or formula_equal(runtime_value, writer_formula)
        staged_persisted = staged_value == writer_formula or formula_equal(staged_value, writer_formula)
        lo_persisted = lo_formula_value == writer_formula or formula_equal(lo_formula_value, writer_formula)
        boundary = ""
        if exact or fp_match:
            if not runtime_persisted or not staged_persisted:
                boundary = "WRITTEN_NOT_PERSISTED"
            elif not lo_persisted:
                boundary = "PERSISTED_FORMULA_CHANGED"
            elif not official_target:
                boundary = "GOLD_WRITE_NOT_OFFICIAL_MOD_TARGET"
            elif official_correct is False:
                boundary = "PERSISTED_EXACT_FORMULA_VALUE_WRONG"
            elif official_correct is True:
                boundary = "NO_LOSS_OBSERVED"
            else:
                boundary = "OFFICIAL_SCORER_ALIGNMENT_MISMATCH"
        return_row = {
            "task": f.key(task), "task_id": task, "obligation_id": (canonical_record or {}).get("target", {}).get("obligation_id") if canonical_record else None,
            "operation_id": (canonical_record or {}).get("target", {}).get("operation_id") if canonical_record else None,
            "execution_unit_id": group_id, "program_group_id": group_id, "target": cell_addr(cell),
            "proposal_kind": proposal_kind, "proposal_formula": proposal_formula, "proposal_exact_vs_gold": exact,
            "proposal_fingerprint_vs_gold": fp_match, "translated_formula": translated_formula,
            "translated_exact_vs_gold": formula_equal(translated_formula, gold_formula.get(cell)) if translated_formula is not None else None,
            "verifier_result": verifier, "scheduled_write": True, "writer_input_formula": writer_formula,
            "runtime_formula_after_writer": runtime_value, "staged_formula": staged_value, "lo_formula": lo_formula_value,
            "lo_value": lo_value, "gold_formula": gold_formula.get(cell), "gold_value": gold_values.get(cell),
            "official_modification_target": official_target, "official_correct_after_lo": official_correct,
            "formula_gold_target": ia.formula(gold_formula.get(cell)) and formula_equal(gold_formula.get(cell), gold_formula.get(cell)),
            "value_changed_vs_input": source_values.get(cell) != gold_values.get(cell), "internal_correct": bool(exact or fp_match),
            "loss_boundary": boundary or "NOT_INTERNALLY_CORRECT", "runtime_persisted": runtime_persisted,
            "staged_persisted": staged_persisted, "lo_persisted": lo_persisted,
        }
        rows.append(return_row)
    return rows, group_lineage(task, schedule, source_formula, gold_formula, runtime_formula, staged_formula, lo_formula, lo_values, official, translations, applied, cell_to_group), {"official": official, "source_values": source_values, "gold_values": gold_values}


def group_lineage(task: str, schedule: dict[str, Any], source: dict, gold: dict, runtime: dict, staged: dict, lo: dict, lo_values: dict, official: dict, translations: dict, applied: dict, cell_to_group: dict) -> list[dict[str, Any]]:
    rows = []
    for ui, unit in enumerate(schedule.get("groups") or []):
        for gi, group in enumerate(unit.get("groups") or []):
            gid = f"U{ui + 1}.G{gi + 1}:{group.get('operation_id') or ''}"
            canonical_cell = tuple(group.get("canonical_cell") or ())
            canonical_record = next((x for x in schedule.get("canonical_decisions") or [] if tuple(x.get("seed") or ()) == canonical_cell), None)
            canonical_formula = (canonical_record or {}).get("formula")
            for raw in group.get("member_cells") or []:
                cell = tuple(raw)
                is_canonical = cell == canonical_cell
                translated = None if is_canonical else translations.get(cell)
                formula = canonical_formula if is_canonical else translated
                exact = formula_equal(formula, gold.get(cell)) if formula is not None else False
                scheduled = cell in applied
                writer_formula = applied.get(cell)
                runtime_ok = scheduled and (runtime.get(cell) == writer_formula or formula_equal(runtime.get(cell), writer_formula))
                staged_ok = scheduled and (staged.get(cell) == writer_formula or formula_equal(staged.get(cell), writer_formula))
                lo_ok = scheduled and (lo.get(cell) == writer_formula or formula_equal(lo.get(cell), writer_formula))
                official_target = (cell[0], m.closure.a1(cell[1], cell[2])) in official["modification"]
                official_correct = None
                if official_target and cell in lo_values:
                    gold_sheet = ev._find_sheet(official["gold"], cell[0])
                    official_correct = ev.compare_cell_value(gold_sheet[m.closure.a1(cell[1], cell[2])].value, lo_values.get(cell)) if gold_sheet is not None else False
                if exact:
                    if not scheduled:
                        boundary = "CORRECT_TRANSLATION_NOT_SCHEDULED" if not is_canonical else "CORRECT_PROPOSAL_NOT_SCHEDULED"
                    elif not runtime_ok or not staged_ok:
                        boundary = "WRITTEN_NOT_PERSISTED"
                    elif not lo_ok:
                        boundary = "PERSISTED_FORMULA_CHANGED"
                    elif not official_target:
                        boundary = "GOLD_WRITE_NOT_OFFICIAL_MOD_TARGET"
                    elif official_correct is False:
                        boundary = "PERSISTED_EXACT_FORMULA_VALUE_WRONG"
                    elif official_correct is True:
                        boundary = "NO_LOSS_OBSERVED"
                    else:
                        boundary = "OFFICIAL_SCORER_ALIGNMENT_MISMATCH"
                else:
                    boundary = "NOT_INTERNALLY_CORRECT"
                rows.append({
                    "task": f.key(task), "task_id": task, "execution_unit_id": gid, "program_group_id": gid,
                    "operation_id": group.get("operation_id"), "canonical_target": label(canonical_cell), "target": label(cell),
                    "is_canonical": is_canonical, "canonical_formula": canonical_formula, "translation_formula": translated,
                    "translation_generated": translated is not None, "translation_exact_vs_gold": exact if not is_canonical else None,
                    "canonical_exact_vs_gold": exact if is_canonical else None, "scheduled": scheduled,
                    "writer_formula": writer_formula, "runtime_formula": runtime.get(cell), "staged_formula": staged.get(cell),
                    "lo_formula": lo.get(cell), "lo_value": lo_values.get(cell), "official_modification_target": official_target,
                    "official_correct_after_lo": official_correct, "loss_boundary": boundary,
                })
    return rows


def refresh_lo(staged_paths: dict[str, Path]) -> dict[str, Path]:
    lo_dir = AUDIT / "lo_outputs"
    if lo_dir.exists():
        shutil.rmtree(lo_dir)
    lo_dir.mkdir(parents=True, exist_ok=True)
    copied = {}
    for task, staged in staged_paths.items():
        dest = lo_dir / f"Financial_Model-{task}_output.xlsx"
        if staged.exists():
            shutil.copy2(staged, dest)
            copied[task] = dest
    if copied:
        cmd = [sys.executable, str(ROOT / "benchmark-data" / "SpreadsheetBench-2" / "evaluation" / "open_spreadsheet.py"), "--dir_path", str(lo_dir), "--no-recursive"]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
        (AUDIT / "libreoffice_refresh.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"LibreOffice bridge refresh failed: {proc.returncode}")
    return copied


def score_bridge_outputs(lo_paths: dict[str, Path]) -> dict[str, Any]:
    if BRIDGE_SCORE.exists():
        shutil.rmtree(BRIDGE_SCORE)
    for task, path in lo_paths.items():
        directory = BRIDGE_SCORE / f"Financial_Model-{task}"
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, directory / "output.xlsx")
    if not lo_paths:
        return {}
    cmd = [sys.executable, str(ROOT / "benchmark" / "score_openrouter_run.py"), str(BRIDGE_SCORE), "--model-name", "bridge-audit-lo-zero-model", "--metadata-tolerant", "--no-refresh"]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    (AUDIT / "bridge_score.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    score_path = BRIDGE_SCORE / "official_scores.json"
    return load(score_path, {"score_command_status": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})


def main() -> None:
    bridge_freeze()
    staged = {task: LIVE / "submission" / "outputs" / "Financial_Model" / f"{task}_output.xlsx" for task in TASKS}
    lo_paths = refresh_lo(staged)
    all_lineage: list[dict[str, Any]] = []
    all_groups: list[dict[str, Any]] = []
    task_meta: dict[str, Any] = {}
    for task in TASKS:
        lineage, groups, meta = build_lineage(task, lo_paths=lo_paths, official_bridge={})
        all_lineage.extend(lineage)
        all_groups.extend(groups)
        task_meta[task] = meta
    bridge_scores = score_bridge_outputs(lo_paths)
    # Reconcile bridge-scored per-task results with cell-level lineage.
    for row in all_lineage:
        task_score = (bridge_scores.get("tasks") or {}).get(f"Financial_Model:{row['task_id']}", {})
        row["bridge_official_modification_accuracy"] = task_score.get("modification_accuracy")
        row["bridge_official_error"] = task_score.get("error_message")
    write_csv(RUN / "write_lineage.csv", all_lineage)
    write_csv(RUN / "programgroup_write_lineage.csv", all_groups)
    alignment = []
    for task in TASKS:
        meta = task_meta[task]
        official = meta["official"]
        source_values = meta["source_values"]
        gold_values = meta["gold_values"]
        gold_formula = raw_cells(Path(m.task_map()[f.key(task)]["gold_path"]), data_only=False)
        source_formula = raw_cells(m.task_source(f.key(task)), data_only=False)
        cells = set(source_values) | set(gold_values) | set(source_formula) | set(gold_formula)
        # Keep alignment rows compact: only cells in the evaluator answer
        # ranges or in an internally-correct treatment write.
        written = {tuple(coordinate_to_tuple(x["target"].split("!", 1)[1])) for x in all_lineage if x["task_id"] == task}
        for cell in sorted(cells):
            official_key = (cell[0], m.closure.a1(cell[1], cell[2]))
            formula_target = ia.formula(gold_formula.get(cell)) and source_formula.get(cell) != gold_formula.get(cell)
            value_target = source_values.get(cell) != gold_values.get(cell)
            if official_key not in official["modification"] and not formula_target and not value_target and cell not in written:
                continue
            alignment.append({"task": f.key(task), "task_id": task, "cell": label(cell), "formula_gold_target": formula_target, "value_only_gold_target": value_target, "official_modification_target": official_key in official["modification"], "official_regression_target": official_key in official["regression"], "input_formula": source_formula.get(cell), "gold_formula": gold_formula.get(cell), "input_value": source_values.get(cell), "gold_value": gold_values.get(cell), "treatment_write": cell in written})
    write_csv(RUN / "scorer_target_alignment.csv", alignment)
    internal = [r for r in all_lineage if r["internal_correct"]]
    summary = {
        "status": "COMPLETE",
        "model_calls": 0,
        "tasks": TASKS,
        "internally_correct_writes": len(internal),
        "persisted_correct_writes": sum(1 for r in internal if r["runtime_persisted"] and r["staged_persisted"]),
        "post_lo_correct_formulas": sum(1 for r in internal if r["lo_persisted"]),
        "official_modification_target_overlap": sum(1 for r in internal if r["official_modification_target"]),
        "bridge_official_correct_writes": sum(1 for r in internal if r["official_correct_after_lo"] is True),
        "loss_boundary_counts": dict(Counter(r["loss_boundary"] for r in internal)),
        "programgroup_count": len({r["program_group_id"] for r in all_groups}),
        "programgroup_translation_rows": sum(1 for r in all_groups if r["translation_generated"]),
        "programgroup_translation_exact": sum(1 for r in all_groups if r["translation_generated"] and r["translation_exact_vs_gold"]),
        "programgroup_translation_persisted": sum(1 for r in all_groups if r["translation_generated"] and r["scheduled"]),
        "programgroup_translation_official_overlap": sum(1 for r in all_groups if r["translation_generated"] and r["official_modification_target"]),
        "bridge_scores": bridge_scores,
        "lo_outputs": {k: str(v) for k, v in lo_paths.items()},
    }
    dump(RUN / "write_to_score_bridge_summary.json", summary)
    lines = [
        "# Write-to-score bridge audit",
        "",
        "**Status: COMPLETE; zero model calls.** The latest contaminated treatment run was audited without changing source, prompts, architecture, or task state.",
        "",
        "## Result",
        "",
        f"Internally correct writes: **{summary['internally_correct_writes']}**; persisted in runtime/staged files: **{summary['persisted_correct_writes']}**; still formula-correct after an explicit LibreOffice refresh: **{summary['post_lo_correct_formulas']}**; overlapping official modification targets: **{summary['official_modification_target_overlap']}**; correct under the bridge scorer: **{summary['bridge_official_correct_writes']}**.",
        "",
        "The lineage CSVs preserve proposal, translation, writer, staged workbook, LibreOffice, and evaluator-target stages separately. The bridge scorer uses LibreOffice-refreshed copies, not the contaminated run's unrefreshed staging files.",
        "",
        f"ProgramGroup lineage: {summary['programgroup_count']} runtime groups, {summary['programgroup_translation_rows']} generated member translations, {summary['programgroup_translation_exact']} translation formulas exact against gold, {summary['programgroup_translation_persisted']} scheduled/persisted, and {summary['programgroup_translation_official_overlap']} overlapping official modification targets.",
        "",
        "## Loss boundaries",
        "",
        f"`{json.dumps(summary['loss_boundary_counts'], sort_keys=True)}`",
        "",
        "The decisive question is whether internally-correct formulas survive into the LO-refreshed scorer-visible workbook and whether those cells are official modification targets. See `write_lineage.csv` and `scorer_target_alignment.csv` for every cell.",
        "",
        "No architecture or prompt change was made in Phase A.",
    ]
    (RUN / "WRITE_TO_SCORE_BRIDGE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
