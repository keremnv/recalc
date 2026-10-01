#!/usr/bin/env python3
"""Zero-model forensic autopsy of Spark compiled Financial_Model:02_01.

Offline only: replay official modification cells, join them to the frozen
authorised set / scheduler dispositions / writes / remaining envelope, and
inspect HARD_VERIFIER_REJECT under the existing validate_formula contract.
Does not call a model or change architecture.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "benchmark-data/SpreadsheetBench-2/evaluation"))

import openpyxl

from mismatch_census import _load_views, census_workbooks
from composition_closure import a1
from formula_synthesis_probe import _used_sheet_bounds

RUN_ROOT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/official-score-probe/spark-compiled"
)
TASK_DIR = RUN_ROOT / "Financial_Model-02_01"
DATA_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/data"
INPUT_XLSX = DATA_ROOT / "Financial_Model/spreadsheet/02_Project PP/02_01_PP_input.xlsx"
GOLD_XLSX = DATA_ROOT / "Financial_Model/spreadsheet/02_Project PP/02_PP_golden.xlsx"
OUT_JSON = ROOT / "spark_fm_02_01_autopsy.json"
OUT_CSV = ROOT / "spark_fm_02_01_autopsy.csv"
CELL_RE = re.compile(r"cell:s(\d+):r(\d+):c(\d+)")


def col_letter(col: int) -> str:
    out = ""
    n = col
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def cell_id_to_tuple(cell_id: str, index_to_title: dict[str, str]) -> tuple[str, str, int, int] | None:
    match = CELL_RE.fullmatch(cell_id or "")
    if not match:
        return None
    sheet_index, row, col = (int(x) for x in match.groups())
    title = index_to_title.get(str(sheet_index)) or index_to_title.get(sheet_index)  # type: ignore[arg-type]
    if not title:
        return None
    return title, f"{col_letter(col)}{row}", row, col


def display(cell: tuple[str, int, int]) -> str:
    return f"{cell[0]}!{a1(cell[1], cell[2])}"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sheet_bounds(path: Path) -> dict[str, dict[str, int | None]]:
    wb = openpyxl.load_workbook(path, data_only=False, read_only=True)
    try:
        out = {}
        for name in wb.sheetnames:
            max_col, max_row = _used_sheet_bounds(wb[name])
            out[name] = {"max_col": max_col, "max_row": max_row, "max_col_letter": col_letter(max_col) if max_col else None}
        return out
    finally:
        wb.close()


def classify_miss(
    *,
    sheet: str,
    address: str,
    authorised: set[tuple[str, str]],
    written: set[tuple[str, str]],
    rejected: set[tuple[str, str]],
    remaining: set[tuple[str, str]],
    attempted: set[tuple[str, str]],
    disposition_by_cell: dict[tuple[str, str], dict[str, Any]],
    causal_class: str,
    output_value: Any,
    output_raw: Any,
    golden_raw: Any,
    input_raw: Any,
) -> str:
    key = (sheet, address)
    disp = (disposition_by_cell.get(key) or {}).get("status")
    if key not in authorised:
        return "unauthorized"
    if key in remaining:
        return "authorized_never_active_40_call_censored"
    if key in rejected or disp in {"REJECTED_HARD", "REJECTED_HARD_TRANSLATION"}:
        return "attempted_and_rejected"
    if key in written:
        if output_raw != golden_raw:
            return "wrong_proposal"
        if output_value in {"#DIV/0!", "#VALUE!", "#REF!", "#N/A", "#NAME?"} or (
            isinstance(output_value, str) and output_value.startswith("#")
        ):
            return "dependency_value_failure"
        return "written_value_mismatch"
    if disp == "NO_SEMANTIC_CHANGE":
        return "authorized_no_semantic_change"
    if key in attempted:
        return "attempted_not_written"
    if causal_class.startswith("downstream"):
        return "downstream_cascade_not_a_direct_write"
    return "authorized_but_never_active"


def main() -> int:
    scores = load_json(RUN_ROOT / "official_scores.json")
    tasks = scores.get("tasks") or {}
    if isinstance(tasks, dict):
        stored = dict(tasks["Financial_Model:02_01"])
        stored.setdefault("error_message", stored.get("error_message"))
    else:
        stored = next(row for row in tasks if str(row.get("id")) == "02_01")
    dataset = load_json(DATA_ROOT / "Financial_Model/dataset.json")
    record = next(row for row in dataset if row["id"] == "02_01")
    result = load_json(TASK_DIR / "result.json")
    state = load_json(TASK_DIR / "state.json")
    output_xlsx = RUN_ROOT / "submission/outputs/Financial_Model/02_01_output.xlsx"
    if not output_xlsx.is_file():
        output_xlsx = TASK_DIR / "output.xlsx"

    input_views = _load_views(INPUT_XLSX, with_formula=False)
    golden_views = _load_views(GOLD_XLSX, with_formula=False)
    output_views = _load_views(output_xlsx, with_formula=False)
    census = census_workbooks(
        run_name="official-score-probe/spark-compiled",
        task_key="Financial_Model:02_01",
        answer_position=record["answer_position"],
        input_views=input_views,
        golden_views=golden_views,
        output_views=output_views,
        stored_score=stored,
        with_font_color=False,
        with_formula=False,
    )

    spine = (result.get("edit_plan") or {}).get("spine") or state.get("edit_plan", {}).get("spine") or {}
    if not spine:
        # Spine is stripped from result; recover from plan expansion via state.
        sys.path.insert(0, str(ROOT / "src"))
        import matched_compiled_treatment as compiled

        spine = compiled.spine_for("Financial_Model:02_01")
    index_to_title = {str(k): v for k, v in (spine.get("index_to_title") or {}).items()}
    if not index_to_title:
        index_to_title = {str(v): k for k, v in (spine.get("title_to_index") or {}).items()}

    authorised_ids = list((result.get("edit_plan") or {}).get("expansion", {}).get("cell_ids") or state.get("authorised_target_set") or [])
    authorised_cells: list[dict[str, Any]] = []
    authorised_keys: set[tuple[str, str]] = set()
    for cid in authorised_ids:
        mapped = cell_id_to_tuple(cid, index_to_title)
        if not mapped:
            continue
        sheet, address, row, col = mapped
        authorised_cells.append({"cell_id": cid, "sheet": sheet, "address": address, "row": row, "col": col})
        authorised_keys.add((sheet, address))

    write_audit = result.get("write_audit") or {}
    written_keys = {(e["sheet"], e["address"]) for e in write_audit.get("applied") or []}
    writer_rejected = {(e.get("sheet"), e.get("address")) for e in write_audit.get("rejected") or [] if e.get("sheet") and e.get("address")}

    remaining_ids = list(result.get("unresolved_authorised_targets") or state.get("unresolved_authorised_targets") or [])
    remaining_keys: set[tuple[str, str]] = set()
    remaining_cells = []
    for cid in remaining_ids:
        mapped = cell_id_to_tuple(cid, index_to_title)
        if not mapped:
            continue
        sheet, address, row, col = mapped
        remaining_keys.add((sheet, address))
        remaining_cells.append({"cell_id": cid, "sheet": sheet, "address": address, "row": row, "col": col})

    dispositions = result.get("schedule", {}).get("dispositions") or state.get("scheduler_v3", {}).get("dispositions") or {}
    disposition_by_cell: dict[tuple[str, str], dict[str, Any]] = {}
    attempted_keys: set[tuple[str, str]] = set()
    rejected_keys: set[tuple[str, str]] = set()
    for cid, disp in dispositions.items():
        cell = disp.get("cell") or []
        if len(cell) == 3:
            key = (cell[0], a1(cell[1], cell[2]))
        else:
            mapped = cell_id_to_tuple(cid, index_to_title)
            if not mapped:
                continue
            key = (mapped[0], mapped[1])
        disposition_by_cell[key] = disp
        attempted_keys.add(key)
        if disp.get("status") in {"REJECTED_HARD", "REJECTED_HARD_TRANSLATION"}:
            rejected_keys.add(key)

    failures = result.get("failure_ledger") or result.get("schedule", {}).get("failures") or []
    reject_events = [f for f in failures if f.get("failure_class") == "HARD_VERIFIER_REJECT"]
    for event in reject_events:
        cell = event.get("cell") or []
        if len(cell) == 3:
            rejected_keys.add((cell[0], a1(cell[1], cell[2])))

    miss_rows = []
    class_counts: Counter[str] = Counter()
    for miss in census.mismatches:
        if miss.official_partition != "modification":
            continue
        bucket = classify_miss(
            sheet=miss.sheet,
            address=miss.address,
            authorised=authorised_keys,
            written=written_keys,
            rejected=rejected_keys,
            remaining=remaining_keys,
            attempted=attempted_keys,
            disposition_by_cell=disposition_by_cell,
            causal_class=miss.causal_class,
            output_value=miss.output_value,
            output_raw=miss.output_raw,
            golden_raw=miss.golden_raw,
            input_raw=miss.input_raw,
        )
        class_counts[bucket] += 1
        miss_rows.append(
            {
                "sheet": miss.sheet,
                "address": miss.address,
                "official_partition": miss.official_partition,
                "target_kind": miss.target_kind,
                "causal_class": miss.causal_class,
                "forensic_class": bucket,
                "authorised": (miss.sheet, miss.address) in authorised_keys,
                "written": (miss.sheet, miss.address) in written_keys,
                "remaining": (miss.sheet, miss.address) in remaining_keys,
                "rejected": (miss.sheet, miss.address) in rejected_keys,
                "disposition": (disposition_by_cell.get((miss.sheet, miss.address)) or {}).get("status"),
                "input_raw": miss.input_raw,
                "golden_raw": miss.golden_raw,
                "output_raw": miss.output_raw,
                "golden_value": miss.golden_value,
                "output_value": miss.output_value,
            }
        )

    regression_misses = [asdict(m) for m in census.mismatches if m.official_partition == "regression"]

    # Existing validate_formula contract: HARD_ACCEPT iff not hard_reject and
    # parser_ok and not invalid_sheet and not invalid_address and not unsupported_external.
    reject_inspections = []
    bounds = sheet_bounds(INPUT_XLSX)
    for event in reject_events:
        cell = event.get("cell") or []
        validation = event.get("validation") or {}
        inner_hard_reject = bool(validation.get("hard_reject"))
        parser_ok = bool(validation.get("parser_ok"))
        invalid_address = bool(validation.get("invalid_address"))
        invalid_sheet = bool(validation.get("invalid_sheet"))
        unsupported_external = bool(validation.get("unsupported_external"))
        accepted = (
            not inner_hard_reject
            and parser_ok
            and not invalid_sheet
            and not invalid_address
            and not unsupported_external
        )
        formula = None
        sessions = (state.get("scheduler_v3") or {}).get("sessions") or {}
        if len(cell) == 3:
            disp_key = (cell[0], a1(cell[1], cell[2]))
            for cid, session in sessions.items():
                seed = session.get("seed") or []
                if seed == cell:
                    formula = session.get("formula")
                    break
        out_of_bounds_refs = []
        for rec in validation.get("parsed_refs") or [] if isinstance(validation.get("parsed_refs"), list) else []:
            pass
        parsed_refs = validation.get("parsed_refs") or {}
        slots = parsed_refs.get("slots") if isinstance(parsed_refs, dict) else None
        if isinstance(slots, list):
            for slot in slots:
                sheet = slot.get("sheet")
                r2 = slot.get("r2") or slot.get("r1")
                c2 = slot.get("c2") or slot.get("c1")
                bound = bounds.get(sheet) or {}
                if bound.get("max_col") and bound.get("max_row") and c2 and r2:
                    if c2 > bound["max_col"] or r2 > bound["max_row"]:
                        out_of_bounds_refs.append(
                            {
                                "sheet": sheet,
                                "c1": slot.get("c1"),
                                "r1": slot.get("r1"),
                                "c2": slot.get("c2"),
                                "r2": slot.get("r2"),
                                "used_max_col": bound["max_col"],
                                "used_max_row": bound["max_row"],
                                "used_max_col_letter": bound["max_col_letter"],
                            }
                        )
        reject_inspections.append(
            {
                "cell": display(tuple(cell)) if len(cell) == 3 else cell,
                "formula": formula,
                "hard_verifier_result": validation.get("hard_verifier_result"),
                "inner_hard_reject": inner_hard_reject,
                "parser_ok": parser_ok,
                "invalid_address": invalid_address,
                "invalid_sheet": invalid_sheet,
                "unsupported_external": unsupported_external,
                "hard_policy_pass": not inner_hard_reject,
                "wrapper_would_accept": accepted,
                "reject_gate": (
                    "invalid_address"
                    if invalid_address
                    else "invalid_sheet"
                    if invalid_sheet
                    else "unsupported_external"
                    if unsupported_external
                    else "parser"
                    if not parser_ok
                    else "hard_reject"
                    if inner_hard_reject
                    else "none"
                ),
                "correct_under_existing_contract": (not accepted)
                and validation.get("hard_verifier_result") == "HARD_REJECT",
                "out_of_bounds_refs": out_of_bounds_refs,
                "parsed_refs": parsed_refs,
            }
        )

    remaining_in_mod_miss = [r for r in miss_rows if r["forensic_class"] == "authorized_never_active_40_call_censored"]
    remaining_not_in_mod_miss = [
        c for c in remaining_cells if not any(r["sheet"] == c["sheet"] and r["address"] == c["address"] for r in miss_rows)
    ]

    payload = {
        "task": "Financial_Model:02_01",
        "run": "official-score-probe/spark-compiled",
        "output_xlsx": str(output_xlsx),
        "official": {
            "accuracy": stored.get("accuracy"),
            "modification_accuracy": stored.get("modification_accuracy") or stored.get("mod_acc"),
            "regression_accuracy": stored.get("regression_accuracy") or stored.get("reg_acc"),
            "first_error": stored.get("error_message") or stored.get("information") or stored.get("error") or stored.get("msg"),
        },
        "recomputed": {
            "modification_correct": census.modification_correct,
            "modification_total": census.modification_total,
            "modification_accuracy": census.recomputed_modification_accuracy,
            "regression_correct": census.regression_correct,
            "regression_total": census.regression_total,
            "regression_accuracy": census.recomputed_regression_accuracy,
            "score_matches_stored": census.score_matches_stored,
            "modification_miss_count": len(miss_rows),
            "regression_miss_count": len(regression_misses),
        },
        "authority": {
            "authorised_count": len(authorised_keys),
            "written_count": len(written_keys),
            "remaining_count": len(remaining_keys),
            "rejected_count": len(rejected_keys),
            "writer_rejected_count": len(writer_rejected),
            "disposition_counts": dict(Counter(d.get("status") for d in dispositions.values())),
        },
        "remaining_cells": remaining_cells,
        "remaining_in_official_modification_miss": remaining_in_mod_miss,
        "remaining_not_scored_as_modification_miss": remaining_not_in_mod_miss,
        "forensic_class_counts": dict(class_counts),
        "modification_misses": miss_rows,
        "regression_misses": regression_misses,
        "hard_verifier_rejects": reject_inspections,
        "failure_classes": dict(Counter(f.get("failure_class") for f in failures)),
        "call_limit_events": [f for f in failures if f.get("failure_class") == "TASK_MODEL_CALL_LIMIT"],
        "input_sheet_bounds": bounds,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        "sheet,address,target_kind,causal_class,forensic_class,authorised,written,remaining,rejected,disposition,golden_value,output_value,golden_raw,output_raw"
    ]
    for row in miss_rows:
        lines.append(
            ",".join(
                json.dumps(row[k] if k != "sheet" else row[k])
                for k in [
                    "sheet",
                    "address",
                    "target_kind",
                    "causal_class",
                    "forensic_class",
                    "authorised",
                    "written",
                    "remaining",
                    "rejected",
                    "disposition",
                    "golden_value",
                    "output_value",
                    "golden_raw",
                    "output_raw",
                ]
            )
        )
    OUT_CSV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("official", "recomputed", "authority", "forensic_class_counts", "failure_classes")}, indent=2, default=str))
    print(f"modification_misses={len(miss_rows)} remaining={len(remaining_cells)} rejects={len(reject_inspections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
