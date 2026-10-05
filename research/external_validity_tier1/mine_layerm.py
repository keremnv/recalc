#!/usr/bin/env python3
"""Tier 1 Layer M miner. Implements PREREGISTRATION.md §8 definitions exactly.

Inputs: benchmark-runs/tier1-r*/ run dirs (ledger.jsonl + trajectory/*.traj).
Outputs (stdout JSONL unless --out given):
  RUN_LEDGER row + MODEL_BEHAVIOR row + OUTPUT_CENSUS row per cell, each with
  a "ledger" key naming the target ledger file.
"""
import ast
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUNS = BASE / "_overlay/benchmark-root/benchmark-runs/openrouter"

CELL_RE = re.compile(r"\b([A-Z]{1,3}[0-9]{1,7})(?::([A-Z]{1,3}[0-9]{1,7}))?\b")
HELPER_RE = re.compile(r"lx_helpers\s*\.\s*(inspect|inspect_ranges|periods|search|write_cells|write_formulas)")
IMPORT_HELPER_RE = re.compile(r"(import\s+lx_helpers|from\s+lx_helpers\s+import)")
PLAN_RE = re.compile(r"(?im)^(?:\s*(?:\d+[.)]\s+|[-*]\s+(?:\[[ xX]\]\s+)?).*){3,}")
PLAN_WORD_RE = re.compile(r"(?i)\b(plan of action|my plan|todo|step-by-step plan)\b")
_LO_INVOCATION_RE = re.compile(r"(?i)(?:['\"](soffice|libreoffice)['\"]|(soffice|libreoffice)\s+--)")
SUBMIT_RE = re.compile(r"^\s*submit\b", re.M)


def extract_python(action: str) -> list[str]:
    """Extract python code bodies from a bash tool action.

    Covers: `python3 << DELIM`, `python3 -c "..."` (incl. multi-line), and
    the dominant `cat > /tmp/*.py << DELIM` + `python3 /tmp/*.py` pattern.
    """
    bodies = []
    # heredoc: python3 << 'EOF' ... EOF (delimiter varies; D3: also
    # `python3 - << 'EOF'` stdin-script form, 33 blocks in Tier 1 data)
    for m in re.finditer(r"python3?\s+(?:-\s+)?<<\s*['\"]?(\w+)['\"]?\n(.*?)\n\1\b", action, re.S):
        bodies.append(m.group(2))
    # heredoc into a .py file: cat > /tmp/x.py << 'EOF' ... EOF
    for m in re.finditer(
        r"cat\s+>\s*\S+\.py\w*\s+<<\s*['\"]?(\w+)['\"]?\n(.*?)\n\1\b", action, re.S
    ):
        bodies.append(m.group(2))
    # python -c "...": body ends at the quote followed by &&/;/|/newline/end
    # (D3: the old greedy form swallowed trailing shell like `&& soffice`).
    for m in re.finditer(r"python3?\s+-c\s+(['\"])(.*?)\1(?=\s*(?:2>&1\s*)?(?:&&|;|\||\n|$))", action, re.S):
        bodies.append(m.group(2))
    return bodies


def ast_counts(sources: list[str]) -> dict:
    counts = {
        "load_workbook": 0, "iter_rows": 0, "iter_cols": 0,
        "subscript_access": 0, "cell_method": 0, "value_read": 0,
        "cell_write": 0, "formula_write": 0, "save": 0,
        "soffice_invoked": 0, "parse_failures": 0,
    }
    for src in sources:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            counts["parse_failures"] += 1
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = ""
                if isinstance(f, ast.Name):
                    name = f.id
                elif isinstance(f, ast.Attribute):
                    name = f.attr
                if name == "load_workbook":
                    counts["load_workbook"] += 1
                elif name == "iter_rows":
                    counts["iter_rows"] += 1
                elif name == "iter_cols":
                    counts["iter_cols"] += 1
                elif name == "cell":
                    counts["cell_method"] += 1
                elif name == "save":
                    counts["save"] += 1
            elif isinstance(node, ast.Attribute):
                if node.attr == "value":
                    counts["value_read"] += 1
            elif isinstance(node, ast.Subscript):
                counts["subscript_access"] += 1
            elif isinstance(node, ast.Assign):
                # D2 instrument correction: ast.dump renders `.value` as
                # "attr='value'", so match structurally, not on ".value".
                t0 = node.targets[0] if node.targets else None
                is_value_write = (
                    isinstance(t0, ast.Attribute) and t0.attr == "value"
                ) or isinstance(t0, ast.Subscript)
                if is_value_write:
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and node.value.value.startswith("="):
                        counts["formula_write"] += 1
                    else:
                        counts["cell_write"] += 1
    return counts


def dynamic_counts(sources: list[str]) -> dict:
    dyn = {"dim_loops": 0, "computed_coords": 0, "search_loops": 0,
           "cross_sheet": 0, "try_probe": 0}
    for src in sources:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        sheetnames = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                src_dump = ast.dump(node.iter)
                if "max_row" in src_dump or "max_column" in src_dump or "iter_rows" in src_dump or "iter_cols" in src_dump or "dimensions" in src_dump:
                    dyn["dim_loops"] += 1
                else:
                    dyn["search_loops"] += 1
            elif isinstance(node, ast.JoinedStr) or (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod))):
                d = ast.dump(node)
                if "column_letter" in d or "get_column_letter" in d or ("chr(" in d):
                    dyn["computed_coords"] += 1
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.JoinedStr):
                dyn["computed_coords"] += 1
            elif isinstance(node, ast.Try):
                dyn["try_probe"] += 1
        # cross-sheet: >=2 distinct sheet-name subscripts
        for m in re.finditer(r'\[\s*["\']([^"\']+)["\']\s*\]', src):
            sheetnames.add(m.group(1))
        if len(sheetnames) >= 2:
            dyn["cross_sheet"] += 1
    return dyn


def mine_run(run_dir: Path) -> list[dict]:
    ledger_path = run_dir / "ledger.jsonl"
    rec = json.loads(ledger_path.read_text().strip().splitlines()[0])
    trajs = sorted(run_dir.glob("*/trajectory/*/*.traj"))
    assert len(trajs) == 1, f"{run_dir}: {len(trajs)} trajs"
    t = json.loads(trajs[0].read_text())
    steps = t.get("trajectory", [])
    history = t.get("history", [])
    info = t.get("info", {})

    actions = [s.get("action", "") or "" for s in steps]
    observations = [s.get("observation", "") or "" for s in steps]
    blob_actions = "\n".join(actions)
    py_sources: list[str] = []
    for a in actions:
        py_sources.extend(extract_python(a))
    py_blob = "\n".join(py_sources)

    helper_calls = HELPER_RE.findall(blob_actions)
    helper_imported = bool(IMPORT_HELPER_RE.search(blob_actions))
    n_writes = len(re.findall(r"\.value\s*=", py_blob)) + len(re.findall(r"write_cells|write_formulas", py_blob))
    write_eligible = n_writes >= 2 or "write_cells" in py_blob or "write_formulas" in py_blob

    responses = " ".join(
        str(h.get("content", "")) for h in history if h.get("role") == "assistant")
    plan_artifact = bool(PLAN_RE.search(responses) or PLAN_WORD_RE.search(responses))

    py_obs_bytes = sum(len(o) for a, o in zip(actions, observations)
                       if "python" in a.lower())
    total_obs_bytes = sum(len(o) for o in observations)
    code_addrs = len(CELL_RE.findall(py_blob))
    out_addrs = sum(len(CELL_RE.findall(o)) for o in observations)
    largest_obs = max((len(o) for o in observations), default=0)

    cell = {"ledger": "RUN_LEDGER.jsonl",
            "run_name": run_dir.name,
            "task": rec.get("task"), "model": rec.get("model"),
            "arm": rec.get("arm"), "status": rec.get("status"),
            "error": rec.get("error"), "return_code": rec.get("return_code"),
            "model_calls": rec.get("model_calls"), "tool_calls": rec.get("tool_calls"),
            "prompt_tokens": rec.get("prompt_tokens"),
            "completion_tokens": rec.get("completion_tokens"),
            "charged_cost_usd": rec.get("charged_cost_usd"),
            "elapsed_seconds": rec.get("elapsed_seconds"),
            "exit_status": info.get("exit_status"),
            "submission_present": info.get("submission") is not None,
            "attempt": 1}
    behavior = {"ledger": "MODEL_BEHAVIOR.jsonl",
                "run_name": run_dir.name, "task": rec.get("task"),
                "model": rec.get("model"),
                "python_blocks": len(py_sources),
                "ast": ast_counts(py_sources),
                "dynamic": dynamic_counts(py_sources),
                "helper_imported": helper_imported,
                "helper_calls": {h: helper_calls.count(h) for h in sorted(set(helper_calls))},
                "helper_call_total": len(helper_calls),
                "write_family_eligible": write_eligible,
                "spontaneous_plan_artifact": plan_artifact,
                # D4 instrument correction: agents invoke LibreOffice via the
                # `soffice` OR the `libreoffice` binary (r01-P/r02-O use the
                # latter). Count command-position uses: quoted binary (as in
                # subprocess argv) or binary followed by a flag. Prose
                # mentions ("opening in LibreOffice and checking", r09-P
                # step 10, no subprocess call) do not count. Field name
                # kept for ledger shape.
                "soffice_in_actions": bool(_LO_INVOCATION_RE.search(blob_actions))}
    census = {"ledger": "OUTPUT_CENSUS.jsonl",
              "run_name": run_dir.name, "task": rec.get("task"),
              "model": rec.get("model"),
              "python_obs_bytes": py_obs_bytes,
              "total_obs_bytes": total_obs_bytes,
              "largest_single_obs_bytes": largest_obs,
              "code_celladdr_tokens": code_addrs,
              "output_celladdr_tokens": out_addrs}
    return [cell, behavior, census]


def main() -> None:
    pattern = sys.argv[1] if len(sys.argv) > 1 else "tier1-r*"
    rows = []
    for run_dir in sorted(RUNS.glob(pattern)):
        if (run_dir / "ledger.jsonl").exists():
            rows.extend(mine_run(run_dir))
    for r in rows:
        print(json.dumps(r))


if __name__ == "__main__":
    main()
