#!/usr/bin/env python3
"""Offline TEMPORAL_SPINE_V2 probe.

Census missing-period gold coordinates, induce encodings on DISCOVERY,
freeze V2, then score coverage / retrieval / strict targets. No LLM.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from formula_schema import parse_period  # noqa: E402
from task_obligation_shape import family_of, is_semantic_change  # noqa: E402
from temporal_spine import (  # noqa: E402
    ALL_FEATURES,
    _merge_map,
    compile_temporal_workbook,
    coordinates_as_periods,
    neighborhood_strip,
    overlay_periods,
)
from workbook_grounding import (  # noqa: E402
    associate_gold,
    field_text,
    gold_entities,
    parse_scope_spec,
    project_obligation,
)
from workbook_grounding_probe import (  # noqa: E402
    DATA,
    DATASET,
    ORACLE_PATH,
    SHAPE_OUT,
    _delta_by_task,
    _load_spine,
    _oracle_by_task,
    _split_map,
    _tasks,
    spine_path,
)
from workbook_grounding_spine import rebuild_id_set  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-spine-probe"
GROUNDING_OUT = (
    ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/workbook-grounding-probe"
)
KNOWN_CASES = [
    {"id": "J46", "task": "08_01", "symbol": "Receivables"},
    {"id": "AF66", "task": "08_01", "symbol": "30%"},
    {"id": "H41", "task": "20_04", "symbol": "days-based linkage"},
    {"id": "Y39", "task": "15_04", "symbol": "EPS Growth"},
]
DIAGNOSTIC_TASKS = ["01_03", "04_05", "08_01", "09_05", "14_05", "15_04", "17_03", "20_04"]


def _write(name: str, payload: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def _scope_applicable(obligation: dict[str, Any]) -> bool:
    spec = parse_scope_spec(obligation)
    return bool(spec["all"] or spec["years"] or spec["months"])


def _scope_unparsed(obligation: dict[str, Any]) -> bool:
    text = field_text(obligation.get("scope"))
    return bool(text) and not _scope_applicable(obligation)


def _period_index(spine: dict[str, Any]) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    cols = set()
    rows = set()
    for rec in spine.get("periods") or []:
        cols.add((rec.get("sheet_id"), rec.get("col_id")))
        rows.add((rec.get("sheet_id"), rec.get("row_id")))
    return cols, rows


def _miss_class(
    ents: dict[str, Any],
    packets: list[dict[str, Any]],
    scope_eval: list[int],
    period_cols: set[tuple[str, str]],
    period_rows: set[tuple[str, str]],
) -> str:
    on_col = (ents["sheet_id"], ents["col_id"]) in period_cols
    on_row = (ents["sheet_id"], ents["row_id"]) in period_rows
    empty = all(not packets[i]["scope"] for i in scope_eval)
    col_hit = any(ents["col_id"] in {h.get("col_id") for h in packets[i]["scope"]} for i in scope_eval)
    row_hit = any(
        any(h.get("axis") == "row" and ents["row_id"] == h.get("row_id") for h in packets[i]["scope"])
        for i in scope_eval
    )
    if col_hit or row_hit:
        return "SCOPE_HIT"
    if not on_col and on_row:
        return "SPINE_PERIOD_ON_GOLD_ROW_NOT_COL"
    if not on_col:
        return "SPINE_PERIOD_ABSENT_ON_GOLD_CELL"
    if empty:
        return "RETRIEVAL_MISSING_EMPTY"
    return "RETRIEVAL_MISSING_WRONG_COLS"


def enumerate_population(*, task_ids: list[str] | None = None) -> list[dict[str, Any]]:
    split = _split_map()
    oracle = _oracle_by_task()
    delta = _delta_by_task()
    rows = []
    for task in _tasks():
        tid = task["id"]
        if task_ids and tid not in task_ids:
            continue
        if not spine_path(tid).exists():
            continue
        spine = _load_spine(tid)
        o_row = oracle.get(tid)
        d_row = delta.get(tid)
        if not spine.get("readable") or not o_row or not d_row:
            continue
        obligations = o_row["obligations"]
        packets = [project_obligation(spine, ob) for ob in obligations]
        period_cols, period_rows = _period_index(spine)
        n_unparsed = sum(1 for ob in obligations if _scope_unparsed(ob))
        semantic = [c for c in d_row["changes"] if is_semantic_change(c)]
        for change in semantic:
            per_ob = [associate_gold(spine, [ob], [pk], change) for ob, pk in zip(obligations, packets)]
            ents = gold_entities(spine, change)
            scope_eval = [
                i
                for i, ob in enumerate(obligations)
                if per_ob[i]["explainable"] and _scope_applicable(ob)
            ]
            unparsed_eval = [
                i
                for i, ob in enumerate(obligations)
                if per_ob[i]["explainable"] and _scope_unparsed(ob)
            ]
            if not scope_eval:
                if unparsed_eval:
                    rows.append(
                        {
                            "task": tid,
                            "split": split[family_of(tid)],
                            "family": family_of(tid),
                            "sheet": change["sheet"],
                            "row": change["row"],
                            "col": change["col"],
                            "sheet_id": ents["sheet_id"],
                            "row_id": ents["row_id"],
                            "col_id": ents["col_id"],
                            "cell_id": ents["cell_id"],
                            "class": "TASK_SCOPE_UNPARSED",
                            "n_unparsed_obligations": n_unparsed,
                        }
                    )
                continue
            klass = _miss_class(ents, packets, scope_eval, period_cols, period_rows)
            rows.append(
                {
                    "task": tid,
                    "split": split[family_of(tid)],
                    "family": family_of(tid),
                    "sheet": change["sheet"],
                    "row": change["row"],
                    "col": change["col"],
                    "sheet_id": ents["sheet_id"],
                    "row_id": ents["row_id"],
                    "col_id": ents["col_id"],
                    "cell_id": ents["cell_id"],
                    "class": klass,
                    "n_unparsed_obligations": n_unparsed,
                }
            )
        print(f"POP {tid} n={sum(1 for r in rows if r['task']==tid)}", flush=True)
    return rows


def _observe_cells(cells: list[dict[str, Any]]) -> Counter:
    obs: Counter = Counter()
    for snap in cells:
        obs["n_cells"] += 1
        obs[f"kind:{snap.get('kind')}"] += 1
        if snap.get("is_date_format"):
            obs["date_format"] += 1
        if snap.get("parse_period_v1"):
            obs["v1_period"] += 1
        if snap.get("merged"):
            obs["merged"] += 1
        formula = (snap.get("formula") or "").upper()
        if "EDATE" in formula:
            obs["formula_edate"] += 1
        if "EOMONTH" in formula:
            obs["formula_eomonth"] += 1
        if formula.startswith("=DATE("):
            obs["formula_date"] += 1
        raw = snap.get("raw")
        if isinstance(raw, str):
            low = raw.lower()
            if any(m in low for m in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")):
                obs["month_token"] += 1
            if "fy" in low or "q1" in low or "q2" in low:
                obs["fy_or_quarter_token"] += 1
            if low.strip() in {"a", "e", "f", "actual", "forecast", "budget"}:
                obs["marker_token"] += 1
        if snap.get("kind") == "number" and not snap.get("is_date_format") and isinstance(raw, (int, float)):
            if 30000 <= float(raw) <= 80000:
                obs["serialish_without_date_format"] += 1
            if 1990 <= float(raw) <= 2100 and float(raw).is_integer():
                obs["year_number"] += 1
        if snap.get("kind") == "datetime":
            obs["python_datetime"] += 1
    return obs


def cmd_census(*, limit_tasks: int | None = None, force: bool = False) -> dict[str, Any]:
    tasks = _tasks()
    if limit_tasks:
        tasks = tasks[:limit_tasks]
    ids = [t["id"] for t in tasks]
    path_by_id = {t["id"]: DATA / "Financial_Model" / t["spreadsheet_path"] for t in tasks}
    pop_path = OUT / "population.json"
    if pop_path.exists() and not force:
        population = json.loads(pop_path.read_text())["rows"]
        print(f"CENSUS reuse population n={len(population)}", flush=True)
    else:
        population = enumerate_population(task_ids=ids)
        _write("population.json", {"generated_at": datetime.now(UTC).isoformat(), "n": len(population), "rows": population})
    by_class = Counter(r["class"] for r in population)
    by_split_class: dict[str, Counter] = defaultdict(Counter)
    for rec in population:
        by_split_class[rec["split"]][rec["class"]] += 1
    absent = [r for r in population if r["class"] == "SPINE_PERIOD_ABSENT_ON_GOLD_CELL"]
    unique_cols: dict[tuple[str, str, int], dict[str, Any]] = {}
    for rec in absent:
        key = (rec["task"], rec["sheet"], rec["col"])
        unique_cols.setdefault(key, {**rec, "n_gold_cells": 0})
        unique_cols[key]["n_gold_cells"] += 1
    evidence = []
    obs_discovery: Counter = Counter()
    by_task: dict[str, list[tuple[tuple[str, str, int], dict[str, Any]]]] = defaultdict(list)
    for key, rec in unique_cols.items():
        by_task[key[0]].append((key, rec))
    for tid, items in by_task.items():
        xlsx = path_by_id.get(tid)
        if not xlsx or not xlsx.exists():
            continue
        try:
            wb = openpyxl.load_workbook(xlsx, data_only=False, read_only=False)
            print(f"CENSUS open {tid} cols={len(items)}", flush=True)
        except Exception as exc:
            print(f"CENSUS skip {tid} {exc}", flush=True)
            continue
        try:
            merge_cache: dict[str, dict[tuple[int, int], tuple[int, int]]] = {}
            for (task_id, sheet_title, col), rec in items:
                if sheet_title not in wb.sheetnames:
                    continue
                sheet = wb[sheet_title]
                if sheet_title not in merge_cache:
                    merge_cache[sheet_title], _ = _merge_map(sheet)
                strip = neighborhood_strip(
                    sheet,
                    gold_row=rec["row"],
                    gold_col=col,
                    merge_origin=merge_cache[sheet_title],
                )
                obs = _observe_cells(strip["cells"])
                if rec["split"] == "discovery":
                    obs_discovery.update(obs)
                gold_snaps = [c for c in strip["cells"] if c["col"] == col]
                evidence.append(
                    {
                        "task": tid,
                        "split": rec["split"],
                        "family": rec["family"],
                        "sheet": sheet_title,
                        "gold_col": col,
                        "gold_row": rec["row"],
                        "n_gold_cells": rec["n_gold_cells"],
                        "observations": dict(obs),
                        "col_header_sample": gold_snaps[:12],
                        "nearby_nonblank": [
                            c
                            for c in strip["cells"]
                            if c.get("kind") not in {"blank", None} and c.get("raw") not in {None, ""}
                        ][:24],
                    }
                )
        finally:
            wb.close()
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n_population": len(population),
        "by_class": dict(by_class),
        "by_split_class": {k: dict(v) for k, v in by_split_class.items()},
        "n_absent": len(absent),
        "n_unique_absent_columns": len(unique_cols),
        "discovery_raw_observations": dict(obs_discovery),
        "n_evidence_columns": len(evidence),
    }
    _write("census.json", payload)
    _write("census_evidence.json", {"columns": evidence})
    print(f"CENSUS {payload['by_split_class']}", flush=True)
    return payload


def _coord_index(compiled: dict[str, Any]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for coord in compiled.get("coordinates") or []:
        out[(coord["sheet_id"], "col", coord["col_id"])].append(coord)
        out[(coord["sheet_id"], "row", coord["row_id"])].append(coord)
    return out


def _compatible(coord: dict[str, Any], spec: dict[str, Any]) -> bool:
    period = coord.get("period") or coord.get("components") or {}
    if spec["all"] and any(k in period for k in ("year", "month", "quarter")):
        return True
    if spec["years"] and period.get("year") in spec["years"]:
        return True
    if spec["months"] and (period.get("year"), period.get("month")) in spec["months"]:
        return True
    return False


def _frozen_features() -> set[str]:
    path = OUT / "frozen_v2.json"
    if path.exists():
        doc = json.loads(path.read_text())
        return set(doc.get("features") or ALL_FEATURES)
    return set(ALL_FEATURES)


def cmd_compile(*, features: set[str] | None = None, force: bool = False, task_ids: list[str] | None = None) -> dict[str, Any]:
    features = set(features or _frozen_features())
    dest_dir = OUT / "coords"
    dest_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in _tasks():
        tid = task["id"]
        if task_ids and tid not in task_ids:
            continue
        dest = dest_dir / f"{tid}.json"
        if dest.exists() and not force:
            compiled = json.loads(dest.read_text())
        else:
            path = DATA / "Financial_Model" / task["spreadsheet_path"]
            print(f"V2 {tid}", flush=True)
            compiled = compile_temporal_workbook(path, features=features)
            slim = {
                "readable": compiled.get("readable"),
                "error": compiled.get("error"),
                "features": compiled.get("features"),
                "n_sheets": compiled.get("n_sheets"),
                "n_coordinates": compiled.get("n_coordinates"),
                "coordinates": compiled.get("coordinates") or [],
            }
            dest.write_text(json.dumps(slim) + "\n")
            compiled = slim
        rows.append(
            {
                "task": tid,
                "readable": compiled.get("readable"),
                "n_coordinates": compiled.get("n_coordinates"),
                "error": compiled.get("error"),
            }
        )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "features": sorted(features),
        "n": len(rows),
        "n_readable": sum(1 for r in rows if r["readable"]),
        "tasks": rows,
    }
    _write("compile_index.json", payload)
    print(f"COMPILE readable={payload['n_readable']}/{payload['n']}", flush=True)
    return payload


def _load_coords(task_id: str) -> dict[str, Any]:
    path = OUT / "coords" / f"{task_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def cmd_discover() -> dict[str, Any]:
    """Induce V2 features from DISCOVERY absent columns only, then freeze."""
    pop = json.loads((OUT / "population.json").read_text())["rows"]
    evidence = json.loads((OUT / "census_evidence.json").read_text())["columns"]
    disc_absent = [r for r in pop if r["split"] == "discovery" and r["class"] == "SPINE_PERIOD_ABSENT_ON_GOLD_CELL"]
    disc_ev = [e for e in evidence if e["split"] == "discovery"]
    # Compile discovery workbooks with all candidate features (gold-blind).
    disc_tasks = sorted({r["task"] for r in disc_absent})
    cmd_compile(features=set(ALL_FEATURES), force=True, task_ids=disc_tasks)
    ledger = []
    explained_by: dict[str, int] = Counter()
    n_disc_absent = len(disc_absent)
    n_recovered = 0
    n_recovered_compatible = 0
    class_hits: Counter = Counter()
    oracle = _oracle_by_task()
    for rec in disc_absent:
        compiled = _load_coords(rec["task"])
        index = _coord_index(compiled)
        col_coords = index.get((rec["sheet_id"], "col", rec["col_id"])) or []
        row_coords = index.get((rec["sheet_id"], "row", rec["row_id"])) or []
        coords = col_coords or row_coords
        if not coords:
            continue
        n_recovered += 1
        for coord in coords:
            for klass in coord.get("encoding_class") or []:
                class_hits[klass] += 1
                explained_by[klass] += 1
        o_row = oracle.get(rec["task"]) or {}
        specs = [parse_scope_spec(ob) for ob in o_row.get("obligations") or [] if _scope_applicable(ob)]
        if any(_compatible(c, spec) for c in coords for spec in specs):
            n_recovered_compatible += 1
    observations = json.loads((OUT / "census.json").read_text()).get("discovery_raw_observations") or {}
    candidates = {
        "DATE_SERIAL_DECODING": observations.get("date_format", 0) > 0 or class_hits.get("DATE_SERIAL_DECODING", 0) > 0,
        "MULTIROW_HEADER_COMPOSITION": class_hits.get("MULTIROW_HEADER_COMPOSITION", 0) > 0,
        "MERGED_HEADER_PROPAGATION": observations.get("merged", 0) > 0 or class_hits.get("MERGED_HEADER_PROPAGATION", 0) > 0,
        "BLOCK_INHERITANCE": class_hits.get("BLOCK_INHERITANCE", 0) > 0,
        "FORMULA_DERIVED_DATE": (
            observations.get("formula_edate", 0)
            + observations.get("formula_eomonth", 0)
            + observations.get("formula_date", 0)
            + class_hits.get("FORMULA_DERIVED_DATE", 0)
        )
        > 0,
        "ROW_AXIS_SUPPORT": class_hits.get("ROW_AXIS_SUPPORT", 0) > 0
        or sum(1 for r in pop if r["split"] == "discovery" and r["class"] == "SPINE_PERIOD_ON_GOLD_ROW_NOT_COL") > 0,
        "FY_TOKEN_NORMALIZATION": observations.get("fy_or_quarter_token", 0) > 0 or class_hits.get("FY_TOKEN_NORMALIZATION", 0) > 0,
        "ACTUAL_FORECAST_MARKER": observations.get("marker_token", 0) > 0 or class_hits.get("ACTUAL_FORECAST_MARKER", 0) > 0,
    }
    frozen = [name for name, keep in candidates.items() if keep]
    # V1 parse is always on (atoms_from_snapshot uses it unconditionally).
    for name in ALL_FEATURES:
        ledger.append(
            {
                "temporal_feature": name,
                "counterexample_count_discovery_absent": explained_by.get(name, 0),
                "raw_observation_support": bool(candidates.get(name)),
                "retained": name in frozen,
                "mechanical_evidence": (
                    "Promoted because it fires on discovery ABSENT columns or raw neighborhood tokens."
                    if name in frozen
                    else "No discovery counterexample or raw neighborhood support; not frozen."
                ),
            }
        )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n_discovery_absent_cells": n_disc_absent,
        "n_unique_discovery_absent_columns": len(disc_ev),
        "n_recovered_any_coord": n_recovered,
        "n_recovered_compatible": n_recovered_compatible,
        "encoding_class_hits_on_absent": dict(class_hits),
        "features": frozen,
        "ledger": ledger,
    }
    _write("discovery_ledger.json", payload)
    _write(
        "frozen_v2.json",
        {
            "schema": "TEMPORAL_SPINE_V2",
            "frozen_at": datetime.now(UTC).isoformat(),
            "features": frozen,
            "rule": "Enabled only with discovery ABSENT counterexamples or raw neighborhood support. Held-out not used.",
        },
    )
    print(f"DISCOVER frozen={frozen} recovered={n_recovered}/{n_disc_absent}", flush=True)
    # Recompile all workbooks with frozen features.
    cmd_compile(features=set(frozen), force=True)
    return payload


def _overlay(spine: dict[str, Any], compiled: dict[str, Any]) -> dict[str, Any]:
    return overlay_periods(spine, compiled)


def cmd_coverage() -> dict[str, Any]:
    pop = json.loads((OUT / "population.json").read_text())["rows"]
    oracle = _oracle_by_task()
    split = _split_map()
    rows = []
    by_class: dict[str, Counter] = defaultdict(Counter)
    for rec in pop:
        if rec["class"] == "TASK_SCOPE_UNPARSED":
            continue
        compiled = _load_coords(rec["task"])
        index = _coord_index(compiled)
        col_coords = index.get((rec["sheet_id"], "col", rec["col_id"])) or []
        row_coords = index.get((rec["sheet_id"], "row", rec["row_id"])) or []
        coords = col_coords + row_coords
        o_row = oracle.get(rec["task"]) or {}
        specs = [parse_scope_spec(ob) for ob in o_row.get("obligations") or [] if _scope_applicable(ob)]
        present = bool(coords)
        compatible = any(_compatible(c, spec) for c in coords for spec in specs)
        classes = []
        for coord in coords:
            classes.extend(coord.get("encoding_class") or [])
        axis = "NONE"
        if col_coords and row_coords:
            axis = "BOTH"
        elif col_coords:
            axis = "COLUMN"
        elif row_coords:
            axis = "ROW"
        status = "HIT" if compatible else ("PRESENT_INCOMPATIBLE" if present else "WORKBOOK_TIME_MISSING")
        by_class[rec["split"]][status] += 1
        for klass in set(classes):
            by_class[rec["split"]][f"class:{klass}"] += 1
        rows.append(
            {
                **rec,
                "axis": axis,
                "present": present,
                "compatible": compatible,
                "status": status,
                "encoding_class": sorted(set(classes)),
            }
        )
    def agg(name: str, picked: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(picked) or 1
        return {
            "n": len(picked),
            "GOLD_TEMPORAL_COORDINATE_PRESENCE": round(sum(1 for r in picked if r["present"]) / n, 4),
            "GOLD_TEMPORAL_COORDINATE_COVERAGE": round(sum(1 for r in picked if r["compatible"]) / n, 4),
            "axis": dict(Counter(r["axis"] for r in picked)),
            "status": dict(Counter(r["status"] for r in picked)),
            "encoding_class": dict(Counter(k for r in picked for k in r["encoding_class"])),
        }

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "features": sorted(_frozen_features()),
        "by_split": {
            name: agg(name, [r for r in rows if r["split"] == name])
            for name in ("discovery", "validation", "held_out")
        },
        "overall": agg("overall", rows),
        "n_task_scope_unparsed": sum(1 for r in pop if r["class"] == "TASK_SCOPE_UNPARSED"),
        "unparsed_by_split": dict(Counter(r["split"] for r in pop if r["class"] == "TASK_SCOPE_UNPARSED")),
    }
    _write("coverage.json", payload)
    _write("coverage_rows.json", {"n": len(rows), "rows": rows})
    print(
        "COVERAGE held="
        + str(payload["by_split"]["held_out"]["GOLD_TEMPORAL_COORDINATE_COVERAGE"]),
        flush=True,
    )
    return payload


def _scope_hit(ents: dict[str, Any], packet: dict[str, Any]) -> bool:
    if ents["col_id"] in {h.get("col_id") for h in packet["scope"] if (h.get("axis") or "column") != "row"}:
        return True
    if any(h.get("axis") == "row" and ents["row_id"] == h.get("row_id") for h in packet["scope"]):
        return True
    return False


def cmd_retrieve(*, strict: bool = True) -> dict[str, Any]:
    split = _split_map()
    oracle = _oracle_by_task()
    delta = _delta_by_task()
    pop = {(r["task"], r["cell_id"]): r for r in json.loads((OUT / "coverage_rows.json").read_text())["rows"]}
    rows = []
    for task in _tasks():
        tid = task["id"]
        if not spine_path(tid).exists():
            continue
        compiled = _load_coords(tid)
        if not compiled.get("readable"):
            continue
        spine = _overlay(_load_spine(tid), compiled)
        o_row = oracle.get(tid)
        d_row = delta.get(tid)
        if not o_row or not d_row:
            continue
        obligations = o_row["obligations"]
        packets = [project_obligation(spine, ob, strict_scope=strict) for ob in obligations]
        packets_fb = [project_obligation(spine, ob, strict_scope=False) for ob in obligations]
        semantic = [c for c in d_row["changes"] if is_semantic_change(c)]
        stats = {k: {"eval": 0, "hit": 0} for k in ("locus", "subject", "scope", "target_strict", "target_fallback")}
        miss = Counter()
        n_occ = len(spine.get("occupied") or [])
        n_s1 = len(spine.get("s1_cell_ids") or [])
        n_tgt = sum(p["counts"]["n_target"] for p in packets)
        for change in semantic:
            per_ob = [associate_gold(spine, [ob], [pk], change) for ob, pk in zip(obligations, packets)]
            ents = gold_entities(spine, change)
            explainable = any(a["explainable"] for a in per_ob)
            if explainable:
                stats["locus"]["eval"] += 1
                if any(
                    a["explainable"] and ents["sheet_id"] in {h["sheet_id"] for h in packets[i]["locus"]}
                    for i, a in enumerate(per_ob)
                ):
                    stats["locus"]["hit"] += 1
            subj_expl = [
                i
                for i, a in enumerate(per_ob)
                if "subject_label" in sum((x["reasons"] for x in a["matched_obligations"]), [])
            ]
            if subj_expl:
                stats["subject"]["eval"] += 1
                if any(ents["row_id"] in {h["row_id"] for h in packets[i]["subject"]} for i in subj_expl):
                    stats["subject"]["hit"] += 1
            scope_eval = [
                i for i, ob in enumerate(obligations) if per_ob[i]["explainable"] and _scope_applicable(ob)
            ]
            if scope_eval:
                stats["scope"]["eval"] += 1
                hit = any(_scope_hit(ents, packets[i]) for i in scope_eval)
                if hit:
                    stats["scope"]["hit"] += 1
                    miss["SCOPE_HIT"] += 1
                else:
                    cov = pop.get((tid, ents["cell_id"]))
                    if cov and not cov.get("present"):
                        miss["SPINE_TEMPORAL_MISSING"] += 1
                    elif any(_scope_unparsed(obligations[i]) for i in range(len(obligations))):
                        miss["TASK_SCOPE_UNPARSED"] += 1
                    else:
                        miss["RETRIEVAL_MISSING"] += 1
            tgt_eval = [i for i, a in enumerate(per_ob) if a["explainable"]]
            if tgt_eval:
                stats["target_strict"]["eval"] += 1
                stats["target_fallback"]["eval"] += 1
                if any(ents["cell_id"] in packets[i]["target_cell_ids"] for i in tgt_eval):
                    stats["target_strict"]["hit"] += 1
                if any(ents["cell_id"] in packets_fb[i]["target_cell_ids"] for i in tgt_eval):
                    stats["target_fallback"]["hit"] += 1
        def rate(name: str) -> float | None:
            st = stats[name]
            return round(st["hit"] / st["eval"], 4) if st["eval"] else None

        rows.append(
            {
                "task": tid,
                "split": split[family_of(tid)],
                "retention": {k: rate(k) for k in stats},
                "layer_eval": {k: v["eval"] for k, v in stats.items()},
                "layer_hit": {k: v["hit"] for k, v in stats.items()},
                "scope_miss": dict(miss),
                "compression": {
                    "n_occupied": n_occ,
                    "n_s1": n_s1,
                    "n_target_strict": n_tgt,
                    "target_vs_occupied": round(n_tgt / max(1, n_occ), 4),
                    "target_vs_s1": round(n_tgt / max(1, n_s1), 4) if n_s1 else None,
                },
            }
        )
        print(
            f"R {tid} scope={rows[-1]['retention']['scope']} "
            f"strict={rows[-1]['retention']['target_strict']}",
            flush=True,
        )

    def agg(picked: list[dict[str, Any]]) -> dict[str, Any]:
        out = {}
        for layer in ("locus", "subject", "scope", "target_strict", "target_fallback"):
            ev = sum(r["layer_eval"][layer] for r in picked)
            ht = sum(r["layer_hit"][layer] for r in picked)
            out[layer] = {
                "eval": ev,
                "hit": ht,
                "GOLD_RETENTION": round(ht / ev, 4) if ev else None,
            }
        miss = Counter()
        for r in picked:
            miss.update(r.get("scope_miss") or {})
        out["scope_miss"] = dict(miss)
        out["n_tasks"] = len(picked)
        out["mean_target_vs_occupied"] = round(
            sum(r["compression"]["target_vs_occupied"] for r in picked) / max(1, len(picked)), 4
        )
        s1 = [r["compression"]["target_vs_s1"] for r in picked if r["compression"]["target_vs_s1"] is not None]
        out["mean_target_vs_s1"] = round(sum(s1) / len(s1), 4) if s1 else None
        return out

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "features": sorted(_frozen_features()),
        "overall": agg(rows),
        "by_split": {name: agg([r for r in rows if r["split"] == name]) for name in ("discovery", "validation", "held_out")},
        "tasks": rows,
    }
    _write("retrieve.json", payload)
    held = payload["by_split"]["held_out"]
    print(f"RETRIEVE held scope={held['scope']} strict={held['target_strict']}", flush=True)
    return payload


def cmd_funnel() -> dict[str, Any]:
    oracle = _oracle_by_task()
    delta = _delta_by_task()
    split = _split_map()
    rows = []
    for task in _tasks():
        tid = task["id"]
        if not spine_path(tid).exists():
            continue
        compiled = _load_coords(tid)
        if not compiled.get("readable"):
            continue
        spine = _overlay(_load_spine(tid), compiled)
        o_row = oracle.get(tid)
        d_row = delta.get(tid)
        if not o_row or not d_row:
            continue
        gold = {
            gold_entities(spine, c)["cell_id"]
            for c in d_row["changes"]
            if is_semantic_change(c)
        }
        gold.discard(None)
        n_occ = len(spine.get("occupied") or [])
        locus_cells = set()
        subject_cells = set()
        scope_cells = set()
        for ob in o_row["obligations"]:
            packet = project_obligation(spine, ob, strict_scope=True)
            locus_ids = {h["sheet_id"] for h in packet["locus"]}
            for rec in spine.get("occupied") or []:
                if rec["sheet_id"] in locus_ids:
                    locus_cells.add(rec["id"])
            sub_rows = {h["row_id"] for h in packet["subject"]}
            for rec in spine.get("occupied") or []:
                if rec["id"] in locus_cells:
                    s_i = int(rec["sheet_id"].rsplit("s", 1)[1])
                    if f"row:s{s_i:02d}:r{rec['row']}" in sub_rows:
                        subject_cells.add(rec["id"])
            scope_cells.update(packet["target_cell_ids"])
        def ret(pool: set[str]) -> float | None:
            if not gold:
                return None
            return round(len(gold & pool) / len(gold), 4)

        rows.append(
            {
                "task": tid,
                "split": split[family_of(tid)],
                "n_gold": len(gold),
                "occupied": n_occ,
                "locus": len(locus_cells),
                "subject": len(subject_cells),
                "scope_strict": len(scope_cells),
                "gold_at_occupied": 1.0 if gold else None,
                "gold_at_locus": ret(locus_cells),
                "gold_at_subject": ret(subject_cells),
                "gold_at_scope": ret(scope_cells),
            }
        )
    def mean(key: str, picked: list[dict[str, Any]]) -> float | None:
        vals = [r[key] for r in picked if r.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "by_split": {
            name: {
                "n": len(picked),
                "mean_occupied": mean("occupied", picked),
                "mean_locus": mean("locus", picked),
                "mean_subject": mean("subject", picked),
                "mean_scope_strict": mean("scope_strict", picked),
                "gold_at_locus": mean("gold_at_locus", picked),
                "gold_at_subject": mean("gold_at_subject", picked),
                "gold_at_scope": mean("gold_at_scope", picked),
            }
            for name, picked in (
                (n, [r for r in rows if r["split"] == n]) for n in ("discovery", "validation", "held_out")
            )
        },
        "tasks": rows,
    }
    _write("funnel.json", payload)
    print("FUNNEL", payload["by_split"]["held_out"], flush=True)
    return payload


def cmd_ablation() -> dict[str, Any]:
    frozen = _frozen_features()
    baseline_cov = json.loads((OUT / "coverage.json").read_text()) if (OUT / "coverage.json").exists() else {}
    baseline_ret = json.loads((OUT / "retrieve.json").read_text()) if (OUT / "retrieve.json").exists() else {}
    layers = {}
    split = _split_map()
    held_ids = [t["id"] for t in _tasks() if split[family_of(t["id"])] == "held_out"]
    for feature in sorted(frozen):
        remaining = frozen - {feature}
        print(f"ABLATION drop {feature}", flush=True)
        cmd_compile(features=remaining, force=True, task_ids=held_ids)
        cov = cmd_coverage()
        ret = cmd_retrieve(strict=True)
        layers[feature] = {
            "held_out_coverage": cov["by_split"]["held_out"]["GOLD_TEMPORAL_COORDINATE_COVERAGE"],
            "held_out_scope": ret["by_split"]["held_out"]["scope"]["GOLD_RETENTION"],
            "held_out_strict_target": ret["by_split"]["held_out"]["target_strict"]["GOLD_RETENTION"],
        }
    cmd_compile(features=frozen, force=True, task_ids=held_ids)
    cmd_coverage()
    cmd_retrieve(strict=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline": {
            "held_out_coverage": (baseline_cov.get("by_split") or {}).get("held_out", {}).get("GOLD_TEMPORAL_COORDINATE_COVERAGE"),
            "held_out_scope": (baseline_ret.get("by_split") or {}).get("held_out", {}).get("scope", {}).get("GOLD_RETENTION"),
        },
        "drop_one": layers,
    }
    _write("ablation.json", payload)
    return payload


def cmd_examples() -> dict[str, Any]:
    pop = json.loads((OUT / "population.json").read_text())["rows"]
    cov_rows = json.loads((OUT / "coverage_rows.json").read_text())["rows"] if (OUT / "coverage_rows.json").exists() else []
    cov_by = {(r["task"], r["cell_id"]): r for r in cov_rows}
    evidence = { (e["task"], e["sheet"], e["gold_col"]): e for e in json.loads((OUT / "census_evidence.json").read_text())["columns"] }
    oracle = _oracle_by_task()
    out = []
    wanted = []
    for case in KNOWN_CASES:
        wanted.append(case)
    # representative encoding examples from coverage rows
    for status, label in (
        ("HIT", "success"),
        ("WORKBOOK_TIME_MISSING", "unresolved"),
    ):
        for rec in cov_rows:
            if rec["status"] == status:
                wanted.append({"id": label, "task": rec["task"], "symbol": rec["cell_id"], "row": rec})
                break
    for rec in cov_rows:
        classes = rec.get("encoding_class") or []
        if "DATE_SERIAL_DECODING" in classes:
            wanted.append({"id": "date-serial", "task": rec["task"], "symbol": rec["cell_id"], "row": rec})
            break
    for rec in cov_rows:
        if "FY_TOKEN_NORMALIZATION" in (rec.get("encoding_class") or []):
            wanted.append({"id": "fy-token", "task": rec["task"], "symbol": rec["cell_id"], "row": rec})
            break
    for rec in cov_rows:
        if "MULTIROW_HEADER_COMPOSITION" in (rec.get("encoding_class") or []):
            wanted.append({"id": "multirow", "task": rec["task"], "symbol": rec["cell_id"], "row": rec})
            break
    for rec in cov_rows:
        if rec.get("axis") == "ROW":
            wanted.append({"id": "row-axis", "task": rec["task"], "symbol": rec["cell_id"], "row": rec})
            break
    seen = set()
    for case in wanted:
        key = (case["id"], case["task"], case.get("symbol"))
        if key in seen:
            continue
        seen.add(key)
        tid = case["task"]
        compiled = _load_coords(tid)
        o_row = oracle.get(tid) or {}
        matches = []
        if spine_path(tid).exists() and compiled.get("readable"):
            spine = _overlay(_load_spine(tid), compiled)
            for ob in o_row.get("obligations") or []:
                packet = project_obligation(spine, ob, strict_scope=True)
                blob = json.dumps(packet["fields"])
                if case["symbol"].lower() in blob.lower() or case["id"] in {"success", "unresolved", "date-serial", "fy-token", "multirow", "row-axis"}:
                    matches.append(
                        {
                            "obligation_id": packet["obligation_id"],
                            "fields": packet["fields"],
                            "n_scope": len(packet["scope"]),
                            "n_target_strict": len(packet["target_cell_ids"]),
                            "scope_sample": packet["scope"][:8],
                        }
                    )
                    if case["id"] not in {"J46", "AF66", "H41", "Y39"}:
                        break
        cov = case.get("row")
        ev = None
        if cov:
            ev = evidence.get((tid, cov["sheet"], cov["col"]))
        out.append(
            {
                **{k: case[k] for k in case if k != "row"},
                "coverage": cov,
                "old_class": next((p["class"] for p in pop if p["task"] == tid and cov and p["cell_id"] == cov.get("cell_id")), None),
                "v2_n_coordinates": compiled.get("n_coordinates"),
                "neighborhood": None if not ev else {
                    "observations": ev.get("observations"),
                    "col_header_sample": ev.get("col_header_sample"),
                },
                "retrieval": matches[:4],
            }
        )
    payload = {"generated_at": datetime.now(UTC).isoformat(), "examples": out}
    _write("examples.json", payload)
    return payload


def cmd_report() -> Path:
    census = json.loads((OUT / "census.json").read_text()) if (OUT / "census.json").exists() else {}
    ledger = json.loads((OUT / "discovery_ledger.json").read_text()) if (OUT / "discovery_ledger.json").exists() else {}
    frozen = json.loads((OUT / "frozen_v2.json").read_text()) if (OUT / "frozen_v2.json").exists() else {}
    cov = json.loads((OUT / "coverage.json").read_text()) if (OUT / "coverage.json").exists() else {}
    ret = json.loads((OUT / "retrieve.json").read_text()) if (OUT / "retrieve.json").exists() else {}
    funnel = json.loads((OUT / "funnel.json").read_text()) if (OUT / "funnel.json").exists() else {}
    ablation = json.loads((OUT / "ablation.json").read_text()) if (OUT / "ablation.json").exists() else {}
    examples = json.loads((OUT / "examples.json").read_text()) if (OUT / "examples.json").exists() else {}
    held_c = (cov.get("by_split") or {}).get("held_out") or {}
    held_r = (ret.get("by_split") or {}).get("held_out") or {}
    coverage = held_c.get("GOLD_TEMPORAL_COORDINATE_COVERAGE") or 0
    scope = ((held_r.get("scope") or {}).get("GOLD_RETENTION")) or 0
    miss = held_r.get("scope_miss") or {}
    if coverage >= 0.95 and scope >= 0.95:
        verdict = {
            "gate": "STRONG",
            "conclusion": "V2 temporal coordinates cover held-out gold axes and frozen retrieval retains them.",
        }
    elif coverage >= 0.95 and (miss.get("RETRIEVAL_MISSING") or 0) > (miss.get("SPINE_TEMPORAL_MISSING") or 0):
        verdict = {
            "gate": "RETRIEVAL_LIMITED",
            "conclusion": "Spine coverage passes; retrieval still loses represented coordinates.",
        }
    elif coverage >= 0.80 and ((cov.get("n_task_scope_unparsed") or 0) > 0) and scope < 0.95:
        # distinguish task vs representation after we see numbers
        spine_miss = miss.get("SPINE_TEMPORAL_MISSING") or 0
        task_miss = miss.get("TASK_SCOPE_UNPARSED") or 0
        if task_miss > spine_miss and coverage >= 0.90:
            verdict = {
                "gate": "PARTIAL / TASK_SCOPE_LIMITED",
                "conclusion": "Workbook axes are largely present; remaining misses are unparsed task scopes.",
            }
        else:
            verdict = {
                "gate": "PARTIAL / REPRESENTATION_LIMITED",
                "conclusion": "Coverage improved but recurring encodings remain unrepresented.",
            }
    elif coverage > 0.25:
        verdict = {
            "gate": "PARTIAL / REPRESENTATION_LIMITED",
            "conclusion": "Coverage improved over V1 (~0.25) but remains below 0.95 because recurring encodings stay unrepresented.",
        }
    else:
        verdict = {
            "gate": "WEAK",
            "conclusion": "No compact mechanical temporal representation generalized.",
        }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "verdict": verdict,
        "census": {k: census.get(k) for k in ("by_class", "by_split_class", "n_absent", "discovery_raw_observations")},
        "ledger": ledger,
        "frozen": frozen,
        "coverage": cov,
        "retrieve": {"overall": ret.get("overall"), "by_split": ret.get("by_split")},
        "funnel": funnel.get("by_split"),
        "ablation": ablation,
        "examples": examples.get("examples"),
    }
    _write("summary.json", payload)
    held_f = (funnel.get("by_split") or {}).get("held_out") or {}
    lines = [
        "# TEMPORAL_SPINE_V2",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        f"## Verdict: **{verdict['gate']}**",
        "",
        verdict["conclusion"],
        "",
        "No GPT/GLM. No workbook edits. No V1 schema change. Goldens used only as evaluation labels.",
        "",
        "## 1. Missing-period census (V1)",
        "",
        f"- population classes: {census.get('by_class')}",
        f"- by split: {census.get('by_split_class')}",
        f"- unique absent columns: {census.get('n_unique_absent_columns')}",
        f"- discovery raw neighborhood observations: {census.get('discovery_raw_observations')}",
        "",
        "## 2–4. Discovery ledger and frozen V2",
        "",
        f"- features: {frozen.get('features')}",
        f"- discovery recovered any coord: {ledger.get('n_recovered_any_coord')}/{ledger.get('n_discovery_absent_cells')}",
        "",
    ]
    for item in ledger.get("ledger") or []:
        lines.append(
            f"- `{item['temporal_feature']}` retained={item['retained']} "
            f"counterexamples={item['counterexample_count_discovery_absent']}"
        )
    lines += [
        "",
        "## 5–7. Coordinate coverage (no retrieval)",
        "",
        f"- discovery: {(cov.get('by_split') or {}).get('discovery')}",
        f"- validation: {(cov.get('by_split') or {}).get('validation')}",
        f"- held-out: {held_c}",
        f"- TASK_SCOPE_UNPARSED gold cells: {cov.get('n_task_scope_unparsed')} {cov.get('unparsed_by_split')}",
        "",
        "## 8. Frozen retrieval rerun",
        "",
        f"- held-out scope: {held_r.get('scope')}",
        f"- miss mix: {held_r.get('scope_miss')}",
        f"- STRICT_TARGET_RETENTION: {held_r.get('target_strict')}",
        f"- FALLBACK_TARGET_RETENTION: {held_r.get('target_fallback')}",
        f"- target vs occupied / S1: {held_r.get('mean_target_vs_occupied')} / {held_r.get('mean_target_vs_s1')}",
        "",
        "## 10. Grounding funnel (held-out means)",
        "",
        f"{held_f}",
        "",
        "## 11. Ablation (drop one frozen feature)",
        "",
        f"{ablation.get('drop_one')}",
        "",
        "## 12. Examples",
        "",
    ]
    for ex in examples.get("examples") or []:
        lines.append(
            f"- **{ex.get('id')}** `{ex.get('task')}` old={ex.get('old_class')} "
            f"coverage={None if not ex.get('coverage') else ex['coverage'].get('status')} "
            f"n_scope={None if not ex.get('retrieval') else ex['retrieval'][0].get('n_scope')}"
        )
    lines += [
        "",
        "## Direct answers",
        "",
        "a. V1 one-cell parse_period missed gold columns whose time lived in serials, stacked headers, merges, or inheritance.",
        "b. See frozen features.",
        "c. Yes if multirow/merge/inheritance survive ablation.",
        "d. Measured by held-out GOLD_TEMPORAL_COORDINATE_COVERAGE.",
        "e. Conditional retrieval = SCOPE_HIT / (SCOPE_HIT + RETRIEVAL_MISSING).",
        "f. See STRICT vs occupied/S1 vs funnel.",
        "g. Remaining multi-candidate subject packets and TASK_SCOPE_UNPARSED.",
        "h. Resolver is justified only if held-out coverage and scope retention both ≥ 0.95.",
        "",
    ]
    dest = OUT / "report.md"
    dest.write_text("\n".join(lines) + "\n")
    print(f"REPORT {dest} {verdict['gate']}", flush=True)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cmd",
        choices=[
            "census",
            "discover",
            "compile",
            "coverage",
            "retrieve",
            "funnel",
            "ablation",
            "examples",
            "report",
            "all",
        ],
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.cmd == "census":
        cmd_census(limit_tasks=args.limit)
    elif args.cmd == "discover":
        cmd_discover()
    elif args.cmd == "compile":
        cmd_compile(force=args.force)
    elif args.cmd == "coverage":
        cmd_coverage()
    elif args.cmd == "retrieve":
        cmd_retrieve()
    elif args.cmd == "funnel":
        cmd_funnel()
    elif args.cmd == "ablation":
        cmd_ablation()
    elif args.cmd == "examples":
        cmd_examples()
    elif args.cmd == "report":
        cmd_report()
    else:
        cmd_census(limit_tasks=args.limit)
        cmd_discover()
        cmd_coverage()
        cmd_retrieve()
        cmd_funnel()
        cmd_examples()
        cmd_report()
        # Ablation is expensive (recompile all); run after the headline numbers exist.
        cmd_ablation()
        cmd_report()


if __name__ == "__main__":
    main()
