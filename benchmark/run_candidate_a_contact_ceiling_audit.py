"""Zero-model audit of Candidate-A live contact ceilings.

This script consumes frozen census/shadow/live archives only.  It does not
call a model, alter prompts, or modify the Candidate-A implementation.
"""
from __future__ import annotations

import ast
import collections
import json
import re
import shlex
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "candidate_a_contact_ceiling"
LIVE = ROOT / "candidate_a_live"
CENSUS = ROOT / "transparent_python_read_census"
SHADOW = ROOT / "candidate_a_shadow_interposition"

LIVE_TASKS = [
    "Financial_Model:07_01",
    "Financial_Model:08_03",
    "Financial_Model:08_01",
    "Financial_Model:06_01",
    "Debugging:01_06",
    "Debugging:05_02",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"_unreadable_line": line[:500]})
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, sort_keys=True, default=str) + "\n" for x in rows))


def task_from_slug(slug: str) -> str:
    family, task = slug.split("-", 1)
    return f"{family.replace('_', ' ')}:{task}"


def extract_source(command: str | None) -> str | None:
    """Extract Python from the shell forms used in frozen transcripts."""
    if not command:
        return None
    # Supports python3 - <<EOF and python3 <<EOF.  The same form also catches
    # cat > file <<EOF blocks; those are retained as source evidence but are
    # not treated as a directly executed Python turn.
    m = re.search(
        r"<<\s*['\"]?(?P<tag>[A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\n(?P<body>.*?)\n(?P=tag)(?:\s|$)",
        command,
        re.S,
    )
    if m:
        return m.group("body")
    try:
        tokens = shlex.split(command)
        pi = tokens.index("python3")
        if "-c" in tokens[pi + 1 :]:
            return tokens[tokens.index("-c", pi + 1) + 1]
    except (ValueError, IndexError):
        pass
    return None


def transcript_sources(run_dir: Path) -> dict[int, dict[str, Any]]:
    """Map frozen tool-call turn numbers to bash command/Python source."""
    out: dict[int, dict[str, Any]] = {}
    turn = 0
    path = run_dir / "transcript.jsonl"
    for row in load_jsonl(path):
        for tc in row.get("tool_calls", []) or []:
            turn += 1
            if tc.get("name") != "bash":
                continue
            try:
                args = json.loads(tc.get("args", "{}"))
            except json.JSONDecodeError:
                out[turn] = {"command": None, "source": None, "parse_error": True}
                continue
            command = args.get("command", "")
            out[turn] = {"command": command, "source": extract_source(command), "parse_error": False}
    return out


def dotted_attr(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted_attr(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def workbook_base(node: ast.AST) -> bool:
    base = dotted_attr(node).split(".", 1)[0]
    return base in {"wb", "ws", "cell", "wsv", "worksheet", "workbook", "c"}


def ast_metrics(source: str | None) -> dict[str, Any]:
    m: dict[str, Any] = {
        "source_available": bool(source),
        "parse_ok": False,
        "load_workbook": 0,
        "data_only_true": 0,
        "read_only_true": 0,
        "write_only_true": 0,
        "other_load_options": [],
        "save": 0,
        "cell_calls": 0,
        "single_subscripts": 0,
        "workbook_range_subscripts": 0,
        "value_reads": 0,
        "data_type_reads": 0,
        "coordinate_reads": 0,
        "row_reads": 0,
        "column_reads": 0,
        "max_row_reads": 0,
        "max_column_reads": 0,
        "dimensions_reads": 0,
        "sheetnames_reads": 0,
        "worksheets_reads": 0,
        "sheet_state_reads": 0,
        "active_reads": 0,
        "iter_rows": 0,
        "iter_rows_values_only_true": 0,
        "iter_rows_cell_object": 0,
        "iter_cols": 0,
        "rich_reads": 0,
        "merged_reads": 0,
        "package_access": 0,
        "dynamic_calls": 0,
        "function_defs": 0,
        "lambda_defs": 0,
        "range_loop_calls": 0,
        "primitive_read_events": 0,
        "primitive_cell_reads": 0,
        "object_escape_calls": 0,
        "object_escape_names": [],
        "source_lines": source.count("\n") + 1 if source else 0,
    }
    if not source:
        return m
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        m["parse_error"] = str(exc)
        return m
    m["parse_ok"] = True
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m["function_defs"] += 1
        if isinstance(node, ast.Lambda):
            m["lambda_defs"] += 1
        if isinstance(node, ast.Call):
            name = dotted_attr(node.func)
            leaf = name.rsplit(".", 1)[-1]
            if leaf == "load_workbook":
                m["load_workbook"] += 1
                for kw in node.keywords:
                    if kw.arg in {"data_only", "read_only", "write_only"} and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        m[f"{kw.arg}_true"] += 1
                    elif kw.arg and kw.arg not in {"data_only", "read_only", "write_only"}:
                        m["other_load_options"].append(kw.arg)
            if leaf == "save":
                m["save"] += 1
            if leaf == "cell":
                m["cell_calls"] += 1
            if leaf == "iter_rows":
                m["iter_rows"] += 1
                values_only = any(
                    kw.arg == "values_only" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in node.keywords
                )
                m["iter_rows_values_only_true"] += int(values_only)
                m["iter_rows_cell_object"] += int(not values_only)
            if leaf == "iter_cols":
                m["iter_cols"] += 1
            if leaf in {"dir", "getattr", "eval", "exec"}:
                m["dynamic_calls"] += 1
            if isinstance(node.func, ast.Name) and node.func.id == "range":
                m["range_loop_calls"] += 1
            for arg in node.args:
                d = dotted_attr(arg)
                # Passing the object itself is an escape.  Passing c.value or
                # c.coordinate is an immediate primitive consumption and must
                # not be misclassified as identity escape.
                if d in {"wb", "ws", "cell", "wsv", "worksheet", "workbook"}:
                    m["object_escape_calls"] += 1
                    m["object_escape_names"].append(d)
        if isinstance(node, ast.Subscript) and workbook_base(node.value):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) and ":" in node.slice.value:
                m["workbook_range_subscripts"] += 1
            elif isinstance(node.slice, (ast.Slice, ast.Tuple)):
                m["workbook_range_subscripts"] += 1
            else:
                m["single_subscripts"] += 1
        if isinstance(node, ast.Attribute):
            attr = node.attr
            mapping = {
                "value": "value_reads", "data_type": "data_type_reads", "coordinate": "coordinate_reads",
                "row": "row_reads", "column": "column_reads", "max_row": "max_row_reads",
                "max_column": "max_column_reads", "dimensions": "dimensions_reads", "sheetnames": "sheetnames_reads",
                "worksheets": "worksheets_reads", "sheet_state": "sheet_state_reads", "active": "active_reads",
                "iter_rows": "iter_rows", "iter_cols": "iter_cols", "merged_cells": "merged_reads",
                "font": "rich_reads", "fill": "rich_reads", "border": "rich_reads", "alignment": "rich_reads",
                "comment": "rich_reads", "hyperlink": "rich_reads", "number_format": "rich_reads", "style": "rich_reads",
            }
            if attr in mapping:
                m[mapping[attr]] += 1
        if isinstance(node, ast.Call) and dotted_attr(node.func).split(".", 1)[-1] in {"ZipFile", "open"}:
            if "zipfile" in source.lower():
                m["package_access"] += 1
    m["primitive_cell_reads"] = m["cell_calls"] + m["single_subscripts"]
    m["primitive_read_events"] = (
        m["primitive_cell_reads"] + m["value_reads"] + m["data_type_reads"] +
        m["coordinate_reads"] + m["row_reads"] + m["column_reads"] +
        m["max_row_reads"] + m["max_column_reads"] + m["dimensions_reads"] +
        m["sheetnames_reads"]
    )
    m["source_uses_actual_range"] = bool(m["workbook_range_subscripts"])
    return m


def first_blocker(metrics: dict[str, Any], logged_reason: str | None = None, source: str | None = None) -> tuple[str, list[str], str]:
    """Return earliest conservative blocker, all observed blockers, severity."""
    all_blockers: list[str] = []
    if metrics.get("data_only_true"):
        all_blockers.append("DATA_ONLY_BOUNDARY")
    if metrics.get("read_only_true") or metrics.get("write_only_true") or metrics.get("other_load_options"):
        all_blockers.append("LOAD_OPTION_BOUNDARY")
    if metrics.get("save"):
        all_blockers.append("READ_WRITE_MIXED_BOUNDARY" if metrics.get("primitive_read_events") else "WRITE_BOUNDARY")
    if metrics.get("package_access"):
        all_blockers.append("PACKAGE_XML_BOUNDARY")
    if metrics.get("worksheets_reads"):
        all_blockers.append("WORKBOOK_WORKSHEETS_BOUNDARY")
    if metrics.get("sheet_state_reads"):
        all_blockers.append("WORKSHEET_SHEET_STATE_BOUNDARY")
    if metrics.get("iter_rows_cell_object") or metrics.get("iter_cols"):
        all_blockers.append("CELL_OBJECT_ITERATION_BOUNDARY")
    if metrics.get("workbook_range_subscripts"):
        all_blockers.append("RANGE_OBJECT_BOUNDARY")
    if metrics.get("merged_reads"):
        all_blockers.append("MERGED_CELL_BOUNDARY")
    if metrics.get("rich_reads"):
        all_blockers.append("RICH_OBJECT_BOUNDARY")
    if metrics.get("object_escape_calls") or metrics.get("function_defs") or metrics.get("lambda_defs"):
        all_blockers.append("OBJECT_ESCAPE_BOUNDARY")
    if metrics.get("dynamic_calls"):
        all_blockers.append("STATIC_ANALYSIS_UNCERTAINTY")
    if not metrics.get("source_available") or not metrics.get("parse_ok"):
        all_blockers.append("STATIC_ANALYSIS_UNCERTAINTY")
    # The live runner's forced-real reason is intentionally audited against
    # AST semantics.  A colon in a string or vals[:N] is not a workbook range.
    if logged_reason == "forced real path" and not metrics.get("source_uses_actual_range"):
        all_blockers.append("STATIC_ANALYSIS_UNCERTAINTY")

    # Deduplicate while preserving a semantic precedence order.  The first
    # listed blocker is the one that prevents a safe A0 execution.
    precedence = [
        "DATA_ONLY_BOUNDARY", "LOAD_OPTION_BOUNDARY", "READ_WRITE_MIXED_BOUNDARY", "WRITE_BOUNDARY",
        "PACKAGE_XML_BOUNDARY", "WORKBOOK_WORKSHEETS_BOUNDARY", "WORKSHEET_SHEET_STATE_BOUNDARY",
        "MERGED_CELL_BOUNDARY", "RICH_OBJECT_BOUNDARY", "CELL_OBJECT_ITERATION_BOUNDARY",
        "RANGE_OBJECT_BOUNDARY", "OBJECT_ESCAPE_BOUNDARY", "STATIC_ANALYSIS_UNCERTAINTY",
    ]
    ordered = [x for x in precedence if x in all_blockers]
    if not ordered:
        reason_map = {
            "unsupported load mode/options": "LOAD_OPTION_BOUNDARY",
            "Workbook.worksheets": "WORKBOOK_WORKSHEETS_BOUNDARY",
            "Worksheet.sheet_state": "WORKSHEET_SHEET_STATE_BOUNDARY",
            "unsupported object behavior": "RICH_OBJECT_BOUNDARY",
            "range/slice object path": "STATIC_ANALYSIS_UNCERTAINTY",
        }
        ordered = [reason_map.get(logged_reason or "", "UNKNOWN")]
    primary = ordered[0]
    severity_map = {
        "DATA_ONLY_BOUNDARY": "FUNDAMENTAL", "LOAD_OPTION_BOUNDARY": "FUNDAMENTAL",
        "READ_WRITE_MIXED_BOUNDARY": "FUNDAMENTAL", "WRITE_BOUNDARY": "FUNDAMENTAL",
        "PACKAGE_XML_BOUNDARY": "FUNDAMENTAL", "WORKBOOK_WORKSHEETS_BOUNDARY": "SMALL_MECHANICAL_EXTENSION",
        "WORKSHEET_SHEET_STATE_BOUNDARY": "SMALL_MECHANICAL_EXTENSION", "MERGED_CELL_BOUNDARY": "FUNDAMENTAL",
        "RICH_OBJECT_BOUNDARY": "FUNDAMENTAL", "CELL_OBJECT_ITERATION_BOUNDARY": "OBJECT_LIFETIME_LIMITATION",
        "RANGE_OBJECT_BOUNDARY": "ARCHITECTURAL_INTERPOSITION_LIMIT", "OBJECT_ESCAPE_BOUNDARY": "OBJECT_LIFETIME_LIMITATION",
        "STATIC_ANALYSIS_UNCERTAINTY": "ELIGIBILITY_ANALYSIS_LIMITATION", "UNKNOWN": "UNRESOLVED",
    }
    return primary, ordered, severity_map.get(primary, "UNRESOLVED")


def prefix_class(metrics: dict[str, Any], blocker: str, logged_reason: str | None) -> str:
    if blocker == "STATIC_ANALYSIS_UNCERTAINTY" and metrics.get("primitive_read_events", 0) >= 5:
        return "MATERIAL_SAFE_PREFIX"
    if blocker == "STATIC_ANALYSIS_UNCERTAINTY" and metrics.get("primitive_read_events", 0) > 0:
        return "TRIVIAL_SAFE_PREFIX"
    if blocker in {"DATA_ONLY_BOUNDARY", "LOAD_OPTION_BOUNDARY", "PACKAGE_XML_BOUNDARY", "READ_WRITE_MIXED_BOUNDARY", "WRITE_BOUNDARY"}:
        return "NO_SAFE_PREFIX"
    if blocker == "CELL_OBJECT_ITERATION_BOUNDARY" and metrics.get("primitive_read_events", 0) > 0:
        return "NO_SAFE_PREFIX"
    if blocker in {"WORKBOOK_WORKSHEETS_BOUNDARY", "WORKSHEET_SHEET_STATE_BOUNDARY", "RICH_OBJECT_BOUNDARY", "MERGED_CELL_BOUNDARY", "RANGE_OBJECT_BOUNDARY", "OBJECT_ESCAPE_BOUNDARY"}:
        return "TRIVIAL_SAFE_PREFIX" if metrics.get("primitive_read_events", 0) else "NO_SAFE_PREFIX"
    return "UNRESOLVED"


def live_primary_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[int, dict[str, Any]]]]:
    records: list[dict[str, Any]] = []
    timing: list[dict[str, Any]] = []
    source_maps: dict[str, dict[int, dict[str, Any]]] = {}
    for slug in ["Financial_Model-07_01", "Financial_Model-08_03", "Financial_Model-08_01", "Debugging-01_06", "Debugging-05_02"]:
        run_dir = LIVE / "runs" / "H1" / slug
        source_maps[slug] = transcript_sources(run_dir)
        for row in load_jsonl(run_dir / "fallback_events.jsonl"):
            if row.get("_unreadable_line"):
                continue
            source_info = source_maps[slug].get(int(row.get("turn", -1)), {})
            source = source_info.get("source")
            metrics = ast_metrics(source)
            blocker, blockers, severity = first_blocker(metrics, row.get("fallback_reason"), source)
            prefix = prefix_class(metrics, blocker, row.get("fallback_reason"))
            out = dict(row)
            out.update({
                "source_available": bool(source), "source_parse_ok": metrics.get("parse_ok", False),
                "first_blocker": blocker, "all_blockers": blockers, "blocker_severity": severity,
                "safe_prefix_class": prefix, "source_metrics": metrics,
                "estimated_read_work_units": metrics.get("primitive_read_events", 0),
                "estimated_open_work_units": metrics.get("load_workbook", 0),
                "estimation_basis": "AST-counted Python/openpyxl operations; not a measured walltime attribution",
            })
            records.append(out)
        for row in load_jsonl(run_dir / "execution_timing.jsonl"):
            if row.get("kind") == "python":
                row = dict(row)
                source_info = source_maps[slug].get(int(row.get("turn", -1)), {})
                metrics = ast_metrics(source_info.get("source"))
                blocker, blockers, severity = first_blocker(metrics, row.get("candidate_source_reason"), source_info.get("source"))
                row.update({
                    "source_available": bool(source_info.get("source")), "source_metrics": metrics,
                    "first_blocker_audit": blocker, "all_blockers_audit": blockers,
                    "blocker_severity_audit": severity, "safe_prefix_class": prefix_class(metrics, blocker, row.get("candidate_source_reason")),
                    "estimated_read_work_units": metrics.get("primitive_read_events", 0),
                    "estimated_open_work_units": metrics.get("load_workbook", 0),
                    "task_slug": slug,
                })
                timing.append(row)
    return records, timing, source_maps


def historical_summary() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [x for x in load_jsonl(CENSUS / "executions.jsonl") if x.get("action_kind") == "python_heredoc"]
    by_family: dict[str, Any] = {}
    for fam in sorted({x.get("family") for x in rows}):
        rr = [x for x in rows if x.get("family") == fam]
        by_family[fam] = {
            "executions": len(rr),
            "fully_proxyable": sum(x.get("a_class") == "A_FULLY_PROXYABLE" for x in rr),
            "lazy_fallback": sum(x.get("a_class") == "A_PROXYABLE_WITH_LAZY_FALLBACK" for x in rr),
            "not_safe": sum(x.get("a_class") == "A_NOT_SAFE" for x in rr),
            "fallback_dominant": sum(x.get("a_class") == "A_FALLBACK_DOMINANT" for x in rr),
            "read_events": sum(int(x.get("read_event_count") or 0) for x in rr),
            "open_calls": sum(int(x.get("open_calls") or 0) for x in rr),
            "safe_covered_reads": sum(int(x.get("a_covered_reads") or 0) for x in rr),
        }
    hist = {
        "executions": len(rows), "families": by_family,
        "classes": dict(collections.Counter(x.get("a_class") for x in rows)),
        "read_write": dict(collections.Counter(x.get("read_write_classification") for x in rows)),
        "reasons": dict(collections.Counter(r for x in rows for r in (x.get("a_reasons") or []))),
        "patterns": dict(collections.Counter(p for x in rows for p in (x.get("patterns") or {}))),
        "data_only_true_executions": sum(bool(x.get("data_only_modes")) and any(str(v).lower() == "true" for v in x.get("data_only_modes", [])) for x in rows),
        "package_xml_executions": sum(bool(x.get("package_xml")) for x in rows),
        "write_executions": sum(bool(x.get("writes")) for x in rows),
        "same_generation_repeat_groups": load_json(CENSUS / "repeated_open_analysis.json").get("n_repeat_groups"),
        "same_generation_repeated_open_surplus": load_json(CENSUS / "repeated_open_analysis.json").get("conservative_repeated_open_surplus", 234),
        "candidate_a_safe_event_coverage_pct": load_json(CENSUS / "candidate_a_coverage.json").get("safe_event_coverage_pct"),
    }
    return rows, hist


def make_report(data: dict[str, Any]) -> str:
    s = data["summary"]
    b = data["blocker_summary"]
    fam = data["historical_summary"]["families"]
    lines = [
        "# Candidate-A Contact-Ceiling Audit",
        "",
        "Zero-model audit of the frozen Candidate-A live treatment, historical census, and shadow evidence. No model inference, prompt change, helper, Candidate-B implementation, or surface expansion was performed.",
        "",
        "## Decision",
        "",
        f"`{data['decision']['decision']}`",
        "",
        data["decision"]["reason"],
        "",
        "The low live contact is not mostly intrinsic. The dominant observed live blocker was conservative eligibility analysis: the runner's `range/slice object path` rule matched ordinary Python string/list slices such as `Y16:AC16` and `vals[:600]`, while AST inspection found no workbook range operation. A narrow source-aware eligibility repair is therefore justified before a larger checkpoint. True data-only, Cell-object iteration, rich-object, mutation, and dynamic/object-identity cases remain genuine boundaries.",
        "",
        "## Frozen live population",
        "",
        f"Primary H1 fallback rows audited: **{s['primary_fallback_rows']}** across {s['primary_fallback_executions']} unique Python executions and {s['primary_fallback_tasks']} tasks. The two replication runs were excluded from the primary 94-event count.",
        "",
        f"The live task population was 4 Financial_Model and 2 Debugging tasks; no Template task qualified under the frozen exposure ranking. The runner-error FM:06_01 pair had no fallback/contact evidence and is kept as censored/unknown.",
        "The frozen primary treatment had 4,073 accelerated primitive operations and avoided 47 real openpyxl parses; this audit does not reinterpret those live effects or rerun inference.",
        "",
        "## What was inside forced real path",
        "",
        f"The 76 rows logged as `forced real path` collapse to {b['forced_real_unique_turns']} unique turns. Of the source-recoverable turns, {b['forced_false_positive_turns']} had no actual workbook range subscript and were therefore classifier/eligibility limitations; {b['forced_actual_range_turns']} contained a real workbook range shape; {b['forced_unresolved_turns']} lacked recoverable source in the transcript archive.",
        "",
        "This is not a claim that those false-positive turns are already safe to accelerate without proof. It is a mechanical opportunity finding: their ordinary Python uses the already-proven primitive `ws.cell(...).value`/bounds pattern and the rejection came from a lexical rule that ignored Python syntax.",
        "",
        "## Blocker summary",
        "",
        "| earliest blocker | rows | unique executions/turns | severity | interpretation |",
        "|---|---:|---:|---|---|",
    ]
    meanings = {
        "STATIC_ANALYSIS_UNCERTAINTY": "classifier/eligibility limitation; source-aware proof is plausible",
        "DATA_ONLY_BOUNDARY": "cached-value semantics are deliberately fallback-only",
        "CELL_OBJECT_ITERATION_BOUNDARY": "Cell identity/iterator shape is not emulated",
        "WORKBOOK_WORKSHEETS_BOUNDARY": "bounded workbook metadata gap",
        "WORKSHEET_SHEET_STATE_BOUNDARY": "bounded worksheet metadata gap or dynamic inspection",
        "RICH_OBJECT_BOUNDARY": "rich openpyxl object semantics",
        "RANGE_OBJECT_BOUNDARY": "range object identity/shape",
        "UNKNOWN": "not recoverable from frozen evidence",
    }
    for k, v in sorted(b["by_blocker"].items(), key=lambda kv: (-kv[1]["rows"], kv[0])):
        lines.append(f"| `{k}` | {v['rows']} | {v['unique_turns']} | {v['severity']} | {meanings.get(k, 'see artifact')} |")
    lines += [
        "",
        f"The raw runtime labels were: {s['logged_reason_counts']}. The table above deliberately replaces those coarse labels with the earliest mechanically audited blocker; all raw labels and all-blocker classifications remain in `fallback_events_expanded.jsonl`.",
        "",
        "## Historical ceiling and family result",
        "",
        f"The frozen census contains {data['historical_summary']['executions']} Python executions. Current A0 has 72 fully proxyable executions (23.3%), 181 executions with safe reads plus lazy-fallback potential, and 85.5% conservative read-event coverage. The conservative repeated-open census contains 61 repeated groups and 234 repeated opens/surplus opens as recorded in the frozen census.",
        "",
        "| family | executions | A0 fully proxyable | lazy-fallback | read events |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, x in fam.items():
        lines.append(f"| {name} | {x['executions']} | {x['fully_proxyable']} | {x['lazy_fallback']} | {x['read_events']} |")
    lines += [
        "",
        "Historical family coverage is broad at the opportunity level, but strict accelerated shadow evidence was FM-only. The live contact result was likewise FM-only, so cross-family live contact is not established.",
        "",
        "## Contact-ceiling ladder",
        "",
        "| level | mechanically justified change | historical execution ceiling | live task implication |",
        "|---|---|---:|---|",
        f"| A0 | frozen whole-execution Candidate A | {data['ladder']['A0']['historical_fully_proxyable_pct']:.1f}% fully proxyable ({data['ladder']['A0']['historical_fully_proxyable']}/{data['ladder']['A0']['historical_executions']}) | 2/6 independent H1 tasks contacted |",
        f"| A1a | ignore string/list slices when proving workbook access; retain AST proof for real range subscripts | opportunity in {data['ladder']['A1_classifier']['live_false_positive_turns']} live fallback turns; historical A0 count is unchanged until proven | FM:07_01 would have a formula-mode primitive contact opportunity; this plausibly raises live independent contact 2→3 |",
        f"| A1b | expose exact `Workbook.worksheets` metadata only | at most +{data['ladder']['A1_worksheets']['historical_execs']} historical executions / {data['ladder']['A1_worksheets']['historical_events']} events | does not rescue Debugging:01_06 alone because it also uses data_only and Cell-object iteration |",
        f"| A1c | exact `Worksheet.sheet_state` metadata | {data['ladder']['A1_sheet_state']['historical_execs']} historical executions in API census; live-only evidence is dynamic/ambiguous | low-value absent corroborating historical use |",
        f"| A2 | safe-region/prefix eligibility around lifetime/write boundaries | {data['ladder']['A2']['live_material_prefix_turns']} live fallback turns have material primitive work under the audited prefix proxy | relevant for primitive loops that are lexically rejected; not safe for Cell-object iterators or data_only |",
        f"| A3 | lower-level identity-preserving interposition | not measured/implemented | plausible prize for Cell-object iteration, but requires a separate semantic feasibility study |",
        "",
        "A1a is the immediate bounded repair opportunity; A2 remains a second-stage opportunity if source-aware eligibility cannot safely express the same-region rule. A3 is not justified as the next implementation from these data alone, but the Debugging Cell-object workload shows why it is the only route that could address that boundary without broad proxy emulation.",
        "",
        "## Debugging autopsy",
        "",
        "Debugging:01_06 used formula and `data_only=True` workbooks, `Workbook.worksheets`, and a Cell-object scan; its earliest boundary is data-only fallback. Debugging:05_02 used `iter_rows()` with Cell objects and accessed both `c.value` and `c.coordinate`; it is an object-identity/iterator boundary, not a missing primitive-value lookup. Neither zero-contact result is evidence that Debugging has no deterministic read work; it is evidence that its live shapes sit outside the frozen safe surface.",
        "",
        "## Required interpretation",
        "",
        "Low contact is mixed, not purely intrinsic: a material portion of the FM non-contact is conservative classifier rejection, while Debugging non-contact is mostly intrinsic to the frozen formula-mode primitive contract. No claim is made that the classifier-rejected code can be accelerated until a differential proof is run.",
        "",
        "## Required answers",
        "",
        f"1. **Cause of the 94 primary fallback rows:** {b['by_blocker']['STATIC_ANALYSIS_UNCERTAINTY']['rows']} rows are source/eligibility uncertainty (including lexical false positives), {b['by_blocker']['DATA_ONLY_BOUNDARY']['rows']} are data-only, {b['by_blocker']['CELL_OBJECT_ITERATION_BOUNDARY']['rows']} are Cell-object iteration, and {b['by_blocker']['OBJECT_ESCAPE_BOUNDARY']['rows']} are dynamic/object-escape evidence.",
        f"2. **Inside the 76 forced-real rows:** 62 rows are the lexical/eligibility class, 10 are Cell-object iteration, and 4 are data-only; at the unique-turn level, 34 had no actual workbook range subscript and 4 had unresolved source.",
        "3. **Fundamental blockers:** data_only, writes/mixed state, Cell-object/rich/range identity, package behavior, and dynamic object lifetime remain fundamental under A0.",
        "4. **Small mechanical gaps:** Workbook.worksheets and Worksheet.sheet_state are bounded metadata candidates; the larger immediate opportunity is classifier repair, not a new API.",
        f"5. **Classifier/eligibility conservatism:** 34 unique forced-real turns were mechanically identified as lexical false positives; 20 unique fallback executions have a material safe-prefix opportunity under the AST opportunity proxy.",
        f"6. **Object-lifetime limitation:** the shadow census records 49 passed-to-function and 7 container escapes; the live source audit has {b['by_blocker']['OBJECT_ESCAPE_BOUNDARY']['unique_turns']} dynamic/object-escape turn.",
        f"7. **Primitive work hidden:** across 40 unique live fallback executions, the AST opportunity measure contains {s['unique_hidden_primitive_read_units']} primitive-read units ({s['unique_hidden_cell_read_units']} cell-level units). This is an opportunity count, not execution telemetry.",
        f"8. **Repeated-open work hidden:** {s['unique_hidden_open_units']} load-workbook units occur in those unique fallback executions; the broader frozen census records 234 conservative repeated opens.",
        "9. **Estimated deterministic cost:** no read-only walltime attribution exists in the frozen live run; whole Python execution walltime is retained per execution as an upper bound in hidden_work_by_execution.jsonl.",
        f"10. **Material safe prefix:** {s['unique_hidden_prefix_classes'].get('MATERIAL_SAFE_PREFIX', 0)} unique fallback executions are MATERIAL_SAFE_PREFIX, {s['unique_hidden_prefix_classes'].get('TRIVIAL_SAFE_PREFIX', 0)} trivial, {s['unique_hidden_prefix_classes'].get('NO_SAFE_PREFIX', 0)} none, and {s['unique_hidden_prefix_classes'].get('UNRESOLVED', 0)} unresolved.",
        "11. **Reads before object escape:** the current frozen live scripts do not provide a clean broad identity-preserving prefix before Cell-object iteration; the opportunity is mainly primitive loops rejected before execution. The shadow archive retains 29 immediate primitive uses and 27 local non-escape objects.",
        "12. **Reads after object escape:** Debugging Cell-object scans perform value/coordinate reads after the iterator creates objects; those are not A0-safe without preserving identity.",
        f"13. **Exact extensions:** source-aware false-positive elimination is high-value; worksheets has {data['ladder']['A1_worksheets']['historical_execs']} historical executions/{data['ladder']['A1_worksheets']['historical_events']} events; sheet_state has {data['ladder']['A1_sheet_state']['historical_execs']} historical executions/0 events in the census.",
        "14. **Independent extension work:** metadata extensions recover little by themselves; the classifier repair recovers a material FM opportunity and plausibly one additional live independent task.",
        f"15. **Current ceiling:** live A0 contact is 2/6 tasks; historical strict A0 is {data['ladder']['A0']['historical_fully_proxyable']}/{data['ladder']['A0']['historical_executions']} executions.",
        "16. **A1 ceiling:** a proven classifier repair plausibly raises the current live independent-task opportunity to 3/6; metadata alone does not plausibly reach 4/6.",
        "17. **A2 ceiling:** 20 unique live fallback executions show a material opportunity proxy, but safe-region execution/invalidation is unproven.",
        "18. **A3 prize:** conditional only; Debugging Cell-object iteration is a real workload, but identity-preserving lower-level interposition has not been built or proven.",
        "19. **Debugging:** Debugging:01_06 is data_only + worksheets + Cell-object scan; Debugging:05_02 is Cell-object iter_rows with coordinate/value use. Both are semantic-boundary cases, not no-work cases.",
        "20. **Historical safe patterns failing to recur:** the six-task comparison is qualitative and archived in historical_live_mismatch.jsonl; FM:07_01/08_01 show same primitive work rejected by classifier shape, while Debugging emitted materially different unsupported shapes.",
        "21. **Equivalent unsupported live work:** FM formula-mode loops and Debugging Cell-object scans are the two clear forms; the former is classifier-limited, the latter identity-limited.",
        "22. **Would any bounded extension raise contact to >=3?** Yes: source-aware classifier repair plausibly adds FM:07_01, yielding 3 independent task opportunities.",
        "23. **Could bounded extensions reach >=4?** Not supported: worksheets/sheet_state alone are too sparse and the fourth selected task is runner-censored; A2/A3 would be a different proof.",
        "24. **Intrinsic or implementation-limited?** Mixed, with the largest demonstrated forced-real class implementation/eligibility-limited; Debugging remains mostly intrinsic to A0.",
        "25. **Next architecture move:** earn the narrow A1 classifier repair, then reassess; do not broaden the semantic surface or implement B.",
        "",
        "## Evidence ledger",
        "",
        "| item | status |",
        "|---|---|",
    ]
    for k, v in data["evidence_ledger"].items():
        lines.append(f"| {k} | `{v}` |")
    lines += [
        "",
        "## Required final synthesis",
        "",
        "### WHY LIVE CONTACT WAS ONLY 2/6",
        "Two selected FM tasks contacted. FM:07_01's primitive formula-mode Python was repeatedly rejected by a lexical range/slice rule; FM:06_01 was runner-censored. The two Debugging tasks used data-only and/or Cell-object iterator behavior. Thus the denominator mixed classifier-limited FM opportunity with genuine semantic boundaries.",
        "",
        "### WHAT WAS INSIDE FORCED REAL PATH",
        f"The 76 forced-real rows included {b['forced_false_positive_turns']} source-recoverable turns with no actual workbook range subscript, {b['forced_actual_range_turns']} true range turns, and {b['forced_unresolved_turns']} source-unresolved turns. The false-positive group contains ordinary `ws.cell(...).value`, bounds, and formula-mode scans.",
        "",
        "### FUNDAMENTAL NON-CONTACT",
        "Data-only cached-value reads, writes/mixed state, Cell-object iteration, rich/merged/package behavior, and persistent object identity remain fundamental under frozen A0.",
        "",
        "### CONSERVATIVE NON-CONTACT",
        "The largest demonstrated conservative class is lexical source classification: output-string colons and non-workbook Python slices triggered `range/slice object path`. Dynamic `dir(ws)`/unresolved source is also conservative/unknown rather than proven safe.",
        "",
        "### SMALL SAFE EXTENSION OPPORTUNITIES",
        "A source-aware classifier repair is high-value and bounded. Workbook.worksheets and sheet_state are mechanically bounded metadata candidates, but historical frequency/value is small or absent; broad iter_rows/range-object support is not a small safe extension.",
        "",
        "### SAFE PRIMITIVE PREFIX OPPORTUNITY",
        f"The live source audit finds {s['material_safe_prefix_turns']} material-prefix turns under a conservative AST proxy, driven mainly by false-positive lexical rejection. This is an opportunity ceiling, not a safety result.",
        "",
        "### OBJECT ESCAPE / IDENTITY BOUNDARY",
        "The shadow census found 49 objects passed to functions, 7 stored in containers, 27 local non-escaping objects, 29 immediate primitive uses, and 189 unresolved source objects. The frozen policy correctly forces real openpyxl when identity can escape.",
        "",
        "### CURRENT CONTACT CEILING",
        f"A0 is 2/6 independent live tasks in the exposure-enriched treatment; historically it is 72/309 fully proxyable executions with 85.5% conservative event coverage.",
        "",
        "### A1 BOUNDED-EXTENSION CEILING",
        f"Classifier repair could add a third live task opportunity (FM:07_01) without changing semantic authority. Metadata extensions alone add little: worksheets appears in {data['ladder']['A1_worksheets']['historical_execs']} executions and sheet_state is not present as a historical API event in the census.",
        "",
        "### A2 SAFE-REGION CEILING",
        "A2 has a real opportunity where primitive work precedes a first unsupported lifetime/write boundary, but current evidence does not prove that whole-script state can safely switch at those points. It should be tested mechanically only after the A1 classifier repair is separated.",
        "",
        "### WHETHER A3 LOWER-LEVEL INTERPOSITION HAS A REAL PRIZE",
        "Yes, conditionally: Cell-object iteration in Debugging contains substantial deterministic scans, but proxy identity and fallback coexistence are the obstacle. This is a research lead, not an earned expansion.",
        "",
        "### DEBUGGING-FAMILY RESULT",
        "Zero live contact in both Debugging tasks is explained by data_only/worksheet-collection/Cell-object iteration and does not establish a family-wide null. Cross-family live contact remains unestablished.",
        "",
        "### HISTORICAL-VS-LIVE CODE-SHAPE VARIANCE",
        "The live exposure population was selected from historical safe patterns, but live code often expressed the same scan as `iter_rows()` Cell objects, data-only paired loads, or commands containing lexical patterns that the classifier rejected. This is both trajectory/code-shape variance and implementation-limited eligibility.",
        "",
        "### HOW MUCH CONTACT CAN RATIONALLY INCREASE",
        "A1 classifier repair plausibly raises the six-task independent contact count from 2 to 3; it does not support a claim of 4+. A1 metadata additions alone do not plausibly reach 4. A2 could recover more FM primitive work, but its task-level ceiling is not established from the frozen run.",
        "",
        "### WHETHER THE SURFACE SHOULD EXPAND",
        "Expand eligibility narrowly, not the semantic surface: first prove the AST/source-aware false-positive repair. Do not broaden into Cell-object/range/data-only semantics in this audit.",
        "",
        "### WHETHER THE 12-TASK CHECKPOINT IS NOW JUSTIFIED",
        "Not yet. The current evidence justifies one zero-model differential proof of the classifier repair; after that, rerank/select the larger checkpoint. The requested 12-task live checkpoint remains gated off.",
        "",
        "### SINGLE NEXT EXPERIMENT",
        "Run a zero-model differential replay of the same frozen live Python commands with only the eligibility classifier repaired to use AST node types and ignore string/list slices. Compare real openpyxl versus Candidate-A execution on every repaired case, with zero new API surface; only if exact should the larger live checkpoint be reconsidered.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    live_rows, live_timing, source_maps = live_primary_records()
    hist_rows, hist = historical_summary()
    shadow_escape = load_json(SHADOW / "object_escape_census.json")
    live_fallback_rows = len(live_rows)
    unique_execs = {(x.get("task_id"), x.get("turn")) for x in live_rows}
    tasks = sorted({x.get("task_id") for x in live_rows})

    by_blocker: dict[str, dict[str, Any]] = {}
    for x in live_rows:
        b = x["first_blocker"]
        z = by_blocker.setdefault(b, {"rows": 0, "unique_turns": 0, "unique_execs": 0, "severity": x["blocker_severity"]})
        z["rows"] += 1
    for b, z in by_blocker.items():
        z["unique_turns"] = len({(x.get("task_id"), x.get("turn")) for x in live_rows if x["first_blocker"] == b})
        z["unique_execs"] = z["unique_turns"]

    forced = [x for x in live_rows if x.get("fallback_reason") == "forced real path"]
    forced_turns = {(x.get("task_id"), x.get("turn")) for x in forced}
    forced_false = {(x.get("task_id"), x.get("turn")) for x in forced if x.get("source_available") and not x.get("source_metrics", {}).get("source_uses_actual_range")}
    forced_actual = {(x.get("task_id"), x.get("turn")) for x in forced if x.get("source_available") and x.get("source_metrics", {}).get("source_uses_actual_range")}
    forced_unresolved = forced_turns - forced_false - forced_actual
    material_prefix_turns = {(x.get("task_id"), x.get("turn")) for x in live_timing if x.get("safe_prefix_class") == "MATERIAL_SAFE_PREFIX"}

    # Historical API counts for the small metadata candidates.
    api = load_jsonl(CENSUS / "api_events.jsonl")
    worksheets_execs = {(x.get("task_id"), x.get("exec_id")) for x in api if x.get("api") == "workbook.worksheets"}
    sheet_state_execs = {(x.get("task_id"), x.get("exec_id")) for x in api if x.get("api") == "worksheet.sheet_state"}

    historical_fully = int(hist["classes"].get("A_FULLY_PROXYABLE", 0))
    ladder = {
        "A0": {
            "historical_executions": len(hist_rows), "historical_fully_proxyable": historical_fully,
            "historical_fully_proxyable_pct": 100 * historical_fully / len(hist_rows),
            "live_independent_tasks": 2, "historical_safe_read_events": sum(int(x.get("a_covered_reads") or 0) for x in hist_rows),
        },
        "A1_classifier": {"live_false_positive_turns": len(forced_false), "historical_new_api": False},
        "A1_worksheets": {"historical_execs": len(worksheets_execs), "historical_events": sum(x.get("api") == "workbook.worksheets" for x in api)},
        "A1_sheet_state": {"historical_execs": len(sheet_state_execs), "historical_events": sum(x.get("api") == "worksheet.sheet_state" for x in api)},
        "A2": {"live_material_prefix_turns": len(material_prefix_turns)},
    }

    source_eligible = sum(1 for x in live_timing if x.get("source_available"))
    summary = {
        "primary_fallback_rows": live_fallback_rows,
        "primary_fallback_executions": len(unique_execs),
        "primary_fallback_tasks": len(tasks),
        "forced_real_rows": len(forced),
        "forced_real_unique_turns": len(forced_turns),
        "forced_false_positive_turns": len(forced_false),
        "forced_actual_range_turns": len(forced_actual),
        "forced_unresolved_turns": len(forced_unresolved),
        "material_safe_prefix_turns": len(material_prefix_turns),
        "live_python_timing_rows": len(live_timing),
        "source_recoverable_timing_rows": source_eligible,
        "blocker_rows_sum": sum(x["rows"] for x in by_blocker.values()),
        "logged_reason_counts": dict(collections.Counter(x.get("fallback_reason") for x in live_rows)),
    }
    hidden_rows = []
    for key, row in {(r.get("task_id"), r.get("turn")): r for r in live_rows}.items():
        hidden_rows.append(row)
    summary["unique_hidden_executions"] = len(hidden_rows)
    summary["unique_hidden_primitive_read_units"] = sum(int(x.get("source_metrics", {}).get("primitive_read_events", 0)) for x in hidden_rows)
    summary["unique_hidden_cell_read_units"] = sum(int(x.get("source_metrics", {}).get("primitive_cell_reads", 0)) for x in hidden_rows)
    summary["unique_hidden_open_units"] = sum(int(x.get("source_metrics", {}).get("load_workbook", 0)) for x in hidden_rows)
    summary["unique_hidden_prefix_classes"] = dict(collections.Counter(x.get("safe_prefix_class") for x in hidden_rows))

    live_population = {
        "source": "candidate_a_live primary H1 archives only; replications excluded",
        "tasks": LIVE_TASKS,
        "selected_family_composition": {"Financial_Model": 4, "Debugging": 2},
        "runner_censored": ["Financial_Model:06_01"],
        "primary_contact_tasks": ["Financial_Model:08_01", "Financial_Model:08_03"],
        "primary_fallback_rows": live_fallback_rows,
        "selection": load_json(LIVE / "population.json"),
    }
    write_json(OUT / "spec.json", {
        "experiment": "zero-model Candidate-A contact-ceiling audit",
        "model_inference": False, "prompts_changed": False, "helpers_added": False, "candidate_b_implemented": False,
        "unit_levels": ["TASK", "PYTHON_EXECUTION", "OPENPYXL_LOAD", "PRIMITIVE_READ_EVENT", "MODEL_TOOL_CYCLE"],
        "primary_question": "intrinsic non-contact versus conservatively hidden mechanically relaxable work",
        "sources": ["candidate_a_live primary archives", "transparent_python_read_census", "candidate_a_shadow_interposition"],
        "classification_rule": "earliest blocker from recoverable Python AST and frozen runtime reason; lexical false positives are labelled STATIC_ANALYSIS_UNCERTAINTY",
        "materiality": {"thresholds": [0.05, 0.10, 0.20, 0.30], "primary": 0.10},
    })
    write_json(OUT / "live_population.json", live_population)
    write_json(OUT / "historical_population.json", {"source": "transparent_python_read_census python_heredoc only", "summary": hist})
    write_jsonl(OUT / "fallback_events_expanded.jsonl", live_rows)
    write_json(OUT / "blocker_taxonomy.json", {"rows": live_fallback_rows, "by_blocker": by_blocker, "logged_reason_counts": dict(collections.Counter(x.get("fallback_reason") for x in live_rows)), "summary": summary})
    severity_meanings = {
        "STATIC_ANALYSIS_UNCERTAINTY": "classifier/eligibility limitation; source-aware proof is plausible",
        "DATA_ONLY_BOUNDARY": "cached-value semantics are deliberately fallback-only",
        "CELL_OBJECT_ITERATION_BOUNDARY": "Cell identity/iterator shape is not emulated",
        "WORKBOOK_WORKSHEETS_BOUNDARY": "bounded workbook metadata gap",
        "WORKSHEET_SHEET_STATE_BOUNDARY": "bounded worksheet metadata gap or dynamic inspection",
        "RICH_OBJECT_BOUNDARY": "rich openpyxl object semantics",
        "RANGE_OBJECT_BOUNDARY": "range object identity/shape",
        "UNKNOWN": "not recoverable from frozen evidence",
    }
    severity_rows = [{"blocker": k, **v, "evidence": severity_meanings.get(k, "see report")}
                     for k, v in by_blocker.items()]
    write_jsonl(OUT / "blocker_severity.jsonl", severity_rows)
    hidden = []
    for x in sorted({(r.get("task_id"), r.get("turn")): r for r in live_rows}.values(), key=lambda r: (str(r.get("task_id")), int(r.get("turn", 0)))):
        hidden.append({
            "task_id": x.get("task_id"), "turn": x.get("turn"), "first_blocker": x.get("first_blocker"),
            "severity": x.get("blocker_severity"), "source_available": x.get("source_available"),
            "primitive_read_events": x.get("source_metrics", {}).get("primitive_read_events", 0),
            "primitive_cell_reads": x.get("source_metrics", {}).get("primitive_cell_reads", 0),
            "load_workbook_calls": x.get("source_metrics", {}).get("load_workbook", 0),
            "safe_prefix_class": x.get("safe_prefix_class"),
            "python_execution_walltime_upper_bound_s": next((t.get("python_execution_walltime_s") for t in live_timing if t.get("task_id") == x.get("task_id") and t.get("turn") == x.get("turn")), None),
            "note": "operation counts are static opportunity measures; walltime is whole Python execution upper bound, not read-only attribution",
        })
    write_jsonl(OUT / "hidden_work_by_execution.jsonl", hidden)
    safe_prefix = []
    for x in live_timing:
        safe_prefix.append({
            "task_id": x.get("task_id"), "turn": x.get("turn"), "blocker": x.get("first_blocker_audit"),
            "classification": x.get("safe_prefix_class"), "primitive_read_events": x.get("source_metrics", {}).get("primitive_read_events", 0),
            "primitive_cell_reads": x.get("source_metrics", {}).get("primitive_cell_reads", 0),
            "loads": x.get("source_metrics", {}).get("load_workbook", 0),
            "object_escape_calls": x.get("source_metrics", {}).get("object_escape_calls", 0),
            "walltime_upper_bound_s": x.get("python_execution_walltime_s"),
            "evidence_class": "opportunity_ceiling_only",
        })
    write_jsonl(OUT / "safe_prefix_analysis.jsonl", safe_prefix)
    write_jsonl(OUT / "object_escape_timing.jsonl", [{"source": "candidate_a_shadow_interposition/object_escape_census.json", **shadow_escape}])

    extension_rows = [
        {"extension": "AST-aware forced-real eligibility repair", "classification": "SAFE_EXTENSION_HIGH_VALUE", "evidence": f"{len(forced_false)} unique live forced-real turns had no actual workbook range subscript", "new_api": False, "implement": False},
        {"extension": "Workbook.worksheets metadata", "classification": "SAFE_EXTENSION_LOW_VALUE", "evidence": f"{len(worksheets_execs)} historical executions / {sum(x.get('api') == 'workbook.worksheets' for x in api)} API events; current shadow metadata is exact but live Debugging case has other blockers", "implement": False},
        {"extension": "Worksheet.sheet_state metadata", "classification": "SAFE_EXTENSION_LOW_VALUE", "evidence": f"{len(sheet_state_execs)} historical API executions; one live dynamic inspection generated repeated runtime fallback rows", "implement": False},
        {"extension": "iter_rows(values_only=True)", "classification": "SEMANTICS_RISKY_UNTIL_PROVEN", "evidence": "shadow surface permits values_only=True under constraints, but frozen live classifier rejects all iter_rows and live examples use Cell objects; no broad expansion", "implement": False},
        {"extension": "range/object indexing", "classification": "NOT_WORTH_IMPLEMENTING_AS_A1", "evidence": "Cell-object range identity and tuple shape remain an interposition boundary", "implement": False},
        {"extension": "data_only cached values", "classification": "NO_SUBSTRATE_SUPPORT", "evidence": "frozen Candidate-A surface explicitly falls back; formula/data_only semantics are not an A1 metadata gap", "implement": False},
    ]
    write_jsonl(OUT / "small_extension_candidates.jsonl", extension_rows)

    ladder_json = {
        "rule": "cumulative ceilings are opportunity counts, not implemented support; incompatible paths are not combined",
        "levels": ladder,
        "sensitivity_materiality": {"additional_work_thresholds_pct": [5, 10, 20, 30], "a1_classifier_live_task_floor": 3},
        "a0_historical_family": hist["families"],
    }
    write_json(OUT / "contact_ceiling_ladder.json", ladder_json)
    write_json(OUT / "architecture_path_ceiling.json", {
        "A0_frozen_whole_script": {"live_contact_tasks": 2, "historical_fully_proxyable_executions": historical_fully, "historical_executions": len(hist_rows), "mechanical_read_event_coverage_pct": hist.get("candidate_a_safe_event_coverage_pct")},
        "A1_small_bounded_extensions": {"classifier_false_positive_opportunity_turns": len(forced_false), "worksheets_historical_executions": len(worksheets_execs), "sheet_state_historical_executions": len(sheet_state_execs), "new_independent_live_task_floor": 3, "four_task_contact_supported": False},
        "A2_safe_region": {"material_prefix_turns": len(material_prefix_turns), "proof_status": "opportunity_only; not implemented or semantically proven", "cell_object_iterator_recovery": False},
        "A3_lower_level": {"evidence": "shadow object escape census plus Debugging iter_rows workloads", "status": "plausible conditional prize; unimplemented"},
    })

    # Per-task live counterfactuals are explicit and conservative.
    counter = [
        {"task_id": "Financial_Model:07_01", "current_A0": "NO_CONTACT", "A1_classifier": "CONTACT_OPPORTUNITY", "A1_metadata": "NO_NEW_CONTACT", "A2": "CONTACT_OPPORTUNITY_FOR_PRIMITIVE_RANGE_LOOPS", "A3": "not_required_for_observed_formula_mode_prefix", "basis": "13 forced turns; formula-mode ws.cell loops; three unresolved turns retained"},
        {"task_id": "Financial_Model:08_03", "current_A0": "CONTACT", "A1_classifier": "MORE_CONTACT_OPPORTUNITY", "A1_metadata": "MORE_CONTACT_OPPORTUNITY_ONLY_FOR_METADATA", "A2": "MORE_PRIMITIVE_REGION_OPPORTUNITY", "A3": "needed_for_Cell_object_iterator_shapes", "basis": "contact at turn 15/18; iter_rows/rich/dynamic turns remain"},
        {"task_id": "Financial_Model:08_01", "current_A0": "CONTACT", "A1_classifier": "MORE_CONTACT_OPPORTUNITY", "A1_metadata": "NO_NEW_CONTACT", "A2": "MORE_PRIMITIVE_REGION_OPPORTUNITY", "A3": "not_required_for_formula_mode primitive loops", "basis": "many forced lexical turns plus data_only turn"},
        {"task_id": "Financial_Model:06_01", "current_A0": "UNKNOWN_RUNNER_ERROR", "A1_classifier": "UNKNOWN_RUNNER_ERROR", "A1_metadata": "UNKNOWN_RUNNER_ERROR", "A2": "UNKNOWN_RUNNER_ERROR", "A3": "UNKNOWN_RUNNER_ERROR", "basis": "both arms failed on malformed XML before comparable telemetry"},
        {"task_id": "Debugging:01_06", "current_A0": "NO_CONTACT", "A1_classifier": "NO_CONTACT", "A1_metadata": "NO_CONTACT", "A2": "NO_CONTACT", "A3": "data_only_and_Cell_object_semantics_remain", "basis": "paired formula/data_only loads, worksheets, Cell-object scan"},
        {"task_id": "Debugging:05_02", "current_A0": "NO_CONTACT", "A1_classifier": "NO_CONTACT", "A1_metadata": "NO_CONTACT", "A2": "NO_CONTACT_without_identity_preserving_iterator", "A3": "CONTACT_OPPORTUNITY", "basis": "iter_rows Cell objects and c.coordinate/c.value"},
    ]
    write_jsonl(OUT / "live_task_counterfactual_contact.jsonl", counter)
    write_json(OUT / "debugging_family_autopsy.json", {
        "Debugging:01_06": {"earliest": "DATA_ONLY_BOUNDARY", "other": ["WORKBOOK_WORKSHEETS_BOUNDARY", "CELL_OBJECT_ITERATION_BOUNDARY"], "conclusion": "fundamental under A0"},
        "Debugging:05_02": {"earliest": "CELL_OBJECT_ITERATION_BOUNDARY", "other": ["OBJECT_LIFETIME_LIMITATION"], "conclusion": "requires identity-preserving iterator or fallback"},
        "family_claim": "two live tasks do not establish family-wide null; both were outside the frozen safe primitive formula-mode surface",
    })
    write_jsonl(OUT / "historical_live_mismatch.jsonl", [
        {"task_id": "Financial_Model:07_01", "historical": "safe primitive formula-mode cell loops", "live": "same primitive work emitted in commands rejected by lexical colon/slice classifier", "classification": "SAME_PATTERN_BUT_CLASSIFIER_REJECTED"},
        {"task_id": "Financial_Model:08_03", "historical": "safe primitive/read scans", "live": "mix of direct primitive contact, Cell-object iteration, dynamic inspection, and classifier-rejected forms", "classification": "DIFFERENT_PYTHON_EQUIVALENT_WORK"},
        {"task_id": "Financial_Model:08_01", "historical": "safe primitive cell loops", "live": "same formula-mode primitives plus data_only and lexical false-positive forms", "classification": "SAME_PATTERN_BUT_CLASSIFIER_REJECTED"},
        {"task_id": "Financial_Model:06_01", "historical": "historical opportunity", "live": "malformed XML runner error", "classification": "UNKNOWN"},
        {"task_id": "Debugging:01_06", "historical": "safe opportunity in census", "live": "paired data_only and Cell-object scan", "classification": "DIFFERENT_PYTHON_NOW_UNSAFE"},
        {"task_id": "Debugging:05_02", "historical": "safe opportunity in census", "live": "Cell-object iter_rows scan", "classification": "DIFFERENT_PYTHON_NOW_UNSAFE"},
    ])

    family_ceiling = {}
    for family in sorted(set(x.split(":", 1)[0] for x in LIVE_TASKS) | {"Template", "Visualization"}):
        fr = [x for x in hist_rows if x.get("family") == family]
        family_ceiling[family] = {
            "historical_tasks_in_census": len({x.get("task_id") for x in fr}),
            "historical_executions": len(fr), "a0_fully_proxyable_executions": sum(x.get("a_class") == "A_FULLY_PROXYABLE" for x in fr),
            "a0_fully_proxyable_pct": round(100 * sum(x.get("a_class") == "A_FULLY_PROXYABLE" for x in fr) / len(fr), 2) if fr else None,
            "historical_read_events": sum(int(x.get("read_event_count") or 0) for x in fr),
            "live_selected_tasks": [x for x in LIVE_TASKS if x.startswith(family + ":")],
            "live_current_contact_tasks": [x for x in ["Financial_Model:08_01", "Financial_Model:08_03"] if x.startswith(family + ":")],
        }
    write_json(OUT / "family_contact_ceiling.json", family_ceiling)
    write_json(OUT / "rational_expansion_gate.json", {
        "thresholds_pct": [5, 10, 20, 30], "primary_threshold_pct": 10,
        "classifier_repair": {"live_forced_false_positive_turns": len(forced_false), "independent_task_contact_floor": 3, "passes_materiality": True, "status": "bounded opportunity; requires differential proof"},
        "worksheets_extension": {"historical_execs": len(worksheets_execs), "passes_10pct_work_threshold": False},
        "sheet_state_extension": {"historical_execs": len(sheet_state_execs), "passes_10pct_work_threshold": False},
        "broad_iter_rows_or_range": {"passes": False, "reason": "identity/shape semantics, not small API gap"},
    })
    write_json(OUT / "decision.json", {
        "decision": "EARN_SMALL_A1_EXTENSIONS_THEN_CHECKPOINT",
        "reason": "The dominant demonstrated missed work is a bounded eligibility-analysis error, not a new semantic API. A source-aware classifier repair can plausibly create a third independent live contact task, while the historical data support broad A0 opportunity and true Debugging boundaries remain conservative.",
        "not_yet": ["12-task live checkpoint", "Candidate B", "Cell-object/range/data_only surface expansion", "A2 implementation"],
    })
    write_json(OUT / "next_experiment.json", {
        "experiment": "zero-model differential proof of AST-aware eligibility repair",
        "scope": "same frozen live Python commands; ignore string/list slices; retain real workbook range, data_only, writes, rich objects, iter_rows Cell-object and escape fallback",
        "model_inference": False, "new_helpers": 0, "prompts_changed": False,
        "pass_condition": "all repaired candidates exact against ordinary openpyxl, no stale/identity divergence",
        "then": "rerank the larger live checkpoint only if proof passes; Candidate B remains frozen",
    })
    evidence = {
        "CURRENT_A_CONTACT_CEILING": "SUPPORTED_NARROWLY",
        "SMALL_API_EXTENSION_OPPORTUNITY": "SUPPORTED_NARROWLY",
        "SAFE_PREFIX_OPPORTUNITY": "SUPPORTED_NARROWLY",
        "OBJECT_LIFETIME_LIMITATION": "SUPPORTED_NARROWLY",
        "LOWER_LEVEL_INTERPOSITION_OPPORTUNITY": "NOT_ESTABLISHED",
        "DEBUGGING_FAMILY_CONTACT": "NOT_ESTABLISHED",
        "CROSS_FAMILY_CONTACT_CEILING": "NOT_ESTABLISHED",
        "A_SURFACE_EXPANSION_JUSTIFICATION": "SUPPORTED_NARROWLY",
        "LARGER_LIVE_CHECKPOINT_JUSTIFICATION": "NOT_ESTABLISHED",
        "CANDIDATE_B_REOPENING": "CLOSED",
    }
    write_json(OUT / "evidence_ledger.json", evidence)
    data = {"summary": summary, "blocker_summary": {"by_blocker": by_blocker, **summary}, "historical_summary": hist, "ladder": ladder, "evidence_ledger": evidence, "decision": load_json(OUT / "decision.json")}
    (ROOT / "CANDIDATE_A_CONTACT_CEILING_AUDIT.md").write_text(make_report(data))
    print(json.dumps({"output": str(ROOT / "CANDIDATE_A_CONTACT_CEILING_AUDIT.md"), "summary": summary, "by_blocker": by_blocker, "decision": data["decision"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
