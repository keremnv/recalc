#!/usr/bin/env python3
"""Representative Architecture Economics & Capability Checkpoint.

30 tasks x 2 arms (H0 ordinary / H1 practical retained invisible stack).
Identical model-facing surface incl. helper note + lx_helpers shim in BOTH
arms. H0: real openpyxl (+inert spy), reference helper backend, no capture,
no substrate. H1: substrate + Candidate A interposition + capture wrap +
freshness + substrate-backed helpers. Fine-grained monotonic timing with
substrate role attribution. No mechanism search: measure only.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark import ab_local_runner as base  # noqa: E402

# Amendment 01 (2026-09-22, arm-symmetric, predeclared): 90s absolute
# request deadline censors slow-finite deep-history calls (126s measured
# for an 84K-token prompt). 240s for all subsequent attempts, both arms.
# Process-local override; ab_local_runner.py untouched.
base.CHAT_TIMEOUT = 240
from benchmark.candidate_a_live_treatment import (  # noqa: E402
    candidate_safe_source,
    read_events,
)
from benchmark.inspection_helpers import index  # noqa: E402
from benchmark.transparent_runtime.delta import (  # noqa: E402
    derive_delta,
    read_parts,
    replay_delta,
)
from benchmark.transparent_runtime.validate import (  # noqa: E402
    validate_mechanical,
)

OUT = PROJECT_ROOT / "research/history/representative_architecture_checkpoint"
SPEND_FILE = OUT / "_spend.json"
SHIM_H0 = OUT / "_shim_h0_lx_helpers.py"
SHIM_H1 = OUT / "_shim_h1_lx_helpers.py"
BOOTSTRAP = OUT / "sitecustomize.py"

# Frozen model/runtime settings: identical values to ab_local_runner.
MODEL = base.MODEL
TEMPERATURE = base.TEMPERATURE
TOP_P = base.TOP_P
MAX_TOKENS = base.MAX_TOKENS
CALL_LIMIT = base.CALL_LIMIT
INSTANCE_COST_LIMIT = base.INSTANCE_COST_LIMIT
TOTAL_CAP = base.TOTAL_CAP
BASH_TIMEOUT = base.BASH_TIMEOUT
RUN_TIMEOUT = base.RUN_TIMEOUT

NOTE = """## Optional inspection helpers (available in this environment)

A Python module `lx_helpers` is importable from your working directory. You may
use it or ignore it entirely; ordinary Python/openpyxl/view_xlsx all work as usual.
- `lx_helpers.periods(workbook_path, sheet=None)` returns mechanically recovered
  period/header coordinates (e.g. FY24 -> column letter). It does not say which
  periods the task needs.
- `lx_helpers.search(workbook_path, pattern, regex=False, sheet=None)` returns
  exact occurrences (sheet/address/value/formula) in sheet order. No ranking.
- `lx_helpers.inspect(workbook_path, sheet, range, with_styles=False)` returns
  values/formulas/dtypes for an explicitly requested range and reports paging
  when its bounded result is truncated.
- `lx_helpers.inspect_ranges(workbook_path, ranges)` reads several explicitly
  requested ranges in one freshness-checked call, using compact cell rows and
  a total output budget.
Example: `import lx_helpers; lx_helpers.search("input.xlsx", "revenue")`
"""


# ---------------- spend (process-safe) --------------------------------------
def get_spend() -> float:
    try:
        return float(json.loads(SPEND_FILE.read_text()).get("total_usd", 0.0))
    except (OSError, ValueError):
        return 0.0


def add_spend(amount: float) -> float:
    SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEND_FILE, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        try:
            total = float(json.loads(fh.read() or "{}").get("total_usd", 0.0))
        except ValueError:
            total = 0.0
        total += amount
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps({"total_usd": total}))
        fcntl.flock(fh, fcntl.LOCK_UN)
    return total


# ---------------- integrity observation (H0, observational only) -------------
def observe_workbook_integrity(path: Path) -> dict[str, Any]:
    """Cheap mechanical open checks. Never writes. Timed as instrumentation."""
    t0 = time.perf_counter_ns()
    rec: dict[str, Any] = {"path": path.name}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            rec["zip_ok"] = "[Content_Types].xml" in names
            rec["has_workbook"] = any(n.endswith("workbook.xml") for n in names)
            bad = z.testzip()
            rec["testzip_bad"] = bad
    except Exception as exc:  # noqa: BLE001 - observation must not fail runs
        rec["zip_ok"] = False
        rec["zip_error"] = f"{type(exc).__name__}: {exc}"[:200]
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=False, read_only=True)
        try:
            rec["openpyxl_open_ok"] = True
            rec["n_sheets"] = len(wb.sheetnames)
        finally:
            wb.close()
    except Exception as exc:  # noqa: BLE001
        rec["openpyxl_open_ok"] = False
        rec["openpyxl_error"] = f"{type(exc).__name__}: {exc}"[:200]
    rec["duration_ns"] = time.perf_counter_ns() - t0
    return rec


# ---------------- substrate prep with role attribution (H1 only) -------------
def prepare_substrate(workdir: Path, shared: Path, phase: str,
                      serves_roles: list[str]) -> dict[str, Any]:
    """Prepare optional acceleration; workbook failures never veto the runner."""
    from benchmark.inspection_helpers.substrate import prepare
    return prepare(workdir, shared, phase, serves_roles)


def load_env_for_call(task: str, arm: str, run_id: str, workdir: Path,
                      call_idx: int, force_real: bool) -> tuple[dict, Path, Path]:
    # Children run with cwd=workdir: telemetry paths in env must be absolute
    # or every telemetry write fails (H1 silently, H0 reference_api fatally).
    workdir = Path(os.path.abspath(workdir))
    call_dir = workdir / "runtime_events"
    call_dir.mkdir(parents=True, exist_ok=True)
    event_path = call_dir / f"call_{call_idx:03d}.jsonl"
    helper_path = call_dir / f"call_{call_idx:03d}.helpers.jsonl"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(OUT), str(PROJECT_ROOT), env.get("PYTHONPATH", "")])
    env["CANDIDATE_A_ARM"] = arm
    env["CANDIDATE_A_TASK"] = task
    env["CANDIDATE_A_RUN_ID"] = run_id
    env["CANDIDATE_A_EXEC_TELEMETRY"] = str(event_path)
    env["CANDIDATE_A_SUBSTRATE_MANIFEST"] = str(
        workdir / "shared_substrate" / "manifest.json")
    env["REP_HELPER_TELEMETRY"] = str(helper_path)
    env["REP_ARM"] = arm
    env["LX_REPO_ROOT"] = str(PROJECT_ROOT)
    if force_real:
        env["CANDIDATE_A_FORCE_REAL"] = "1"
    else:
        env.pop("CANDIDATE_A_FORCE_REAL", None)
    return env, event_path, helper_path


def snapshot_xlsx(workdir: Path) -> dict[str, bytes]:
    snaps = {}
    for p in sorted(workdir.rglob("*.xlsx")):
        if ".tmp" in p.name:
            continue
        try:
            snaps[str(p.relative_to(workdir))] = p.read_bytes()
        except OSError:
            pass
    return snaps


def capture_wrap_timed(workdir: Path, pre: dict[str, bytes], task_id: str,
                       arm: str, call_idx: int) -> tuple[list[dict], dict]:
    """H1 transparent transaction with per-section monotonic timing."""
    import tempfile as _tf
    t_sections: dict[str, float] = {"snapshot_post_s": 0.0, "derive_s": 0.0,
                                    "commit_s": 0.0, "validate_s": 0.0,
                                    "replay_s": 0.0}
    t0 = time.perf_counter()
    post = snapshot_xlsx(workdir)
    t_sections["snapshot_post_s"] = time.perf_counter() - t0
    telemetry = []
    for rel in sorted(set(pre) | set(post)):
        a, b = pre.get(rel), post.get(rel)
        if a is not None and b is not None and a == b:
            continue
        target = workdir / rel
        if b is None:
            telemetry.append({"task_id": task_id, "arm": arm,
                              "call_idx": call_idx, "rel": rel,
                              "deleted": True, "runtime_failure": False})
            continue
        t1 = time.perf_counter()
        delta = derive_delta(a, b)
        t_sections["derive_s"] += time.perf_counter() - t1
        committed = b
        fd, tmp = _tf.mkstemp(dir=str(target.parent),
                              prefix=target.name + ".", suffix=".tmp")
        t2 = time.perf_counter()
        try:
            with open(fd, "wb") as h:
                h.write(committed)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        committed_b = target.read_bytes()
        t_sections["commit_s"] += time.perf_counter() - t2
        t3 = time.perf_counter()
        validation = validate_mechanical(a, b, committed_b, delta)
        t_sections["validate_s"] += time.perf_counter() - t3
        t4 = time.perf_counter()
        replayed = replay_delta(a, delta)
        try:
            f1 = read_parts(replayed) == read_parts(committed_b)
        except Exception:  # noqa: BLE001 - record-only
            f1 = False
        t_sections["replay_s"] += time.perf_counter() - t4
        telemetry.append({"task_id": task_id, "arm": arm, "call_idx": call_idx,
                          "rel": rel, "delta_id": delta.delta_id,
                          "pre_hash": delta.pre_hash,
                          "post_hash": delta.post_hash,
                          "created": delta.created,
                          "f1_part_exact": f1, "f2_state_exact": f1,
                          "opaque_preserved": list(delta.opaque_preserved),
                          "validation": dict(validation.checks),
                          "validation_passed": validation.passed,
                          "runtime_failure": (not f1) or (committed_b != b)})
    return telemetry, t_sections


def run_bash_env(command: str, workdir: Path,
                 env: dict) -> tuple[str, bool, float, int | None]:
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(command, shell=True, cwd=str(workdir),
                              capture_output=True, text=True,
                              timeout=BASH_TIMEOUT, env=env)
        return (proc.stdout + proc.stderr, False,
                time.perf_counter() - t0, proc.returncode)
    except subprocess.TimeoutExpired as exc:
        return ((exc.stdout or "") + (exc.stderr or ""), True,
                time.perf_counter() - t0, None)


def classify_censoring(status: str, submitted: bool) -> str:
    if status in ("SUBMITTED", "NO_SUBMIT"):
        return "COMPLETED"
    if status in ("TRUNCATED_CALL_LIMIT", "TRUNCATED_INSTANCE_COST"):
        return "MODEL_BUDGET_EXHAUSTED"
    if status in ("PROVIDER_CENSORED", "PROVIDER_ERROR"):
        return "PROVIDER_CENSORED"
    if status in ("CENSORED_CAP", "RUNNER_ERROR"):
        return "RUNNER_CENSORED"
    return "OTHER"


DATA_ROOT = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data"


def task_source(task: str) -> Path:
    cat, _, tid = task.partition(":")
    ds = json.loads((DATA_ROOT / cat / "dataset.json").read_text())
    item = next(d for d in ds if str(d["id"]) == tid)
    return DATA_ROOT / cat / item["spreadsheet_path"]


def reset_live(task: str, arm: str, workdir: Path) -> Path:
    live = workdir / task.replace(":", "_")
    if live.exists():
        shutil.rmtree(live)
    live.mkdir(parents=True)
    shutil.copy2(task_source(task), live / "input.xlsx")
    (live / "lx_helpers.py").write_text(SHIM_H0_TEXT)
    return live


def run_task(task: str, arm: str, run_id: str, live: Path,
             archive_dir: Path, fidelity_log: Path,
             dry_run: bool = False) -> dict:
    assert arm in ("H0", "H1"), arm
    category, _, tid = task.partition(":")
    tpls = base.load_templates()
    dataset = json.loads((DATA_ROOT / category / "dataset.json").read_text())
    item = next(d for d in dataset if str(d["id"]) == tid)
    sheet_in = live / "input.xlsx"
    sheet_out = live / "output.xlsx"
    instance = tpls["instance"].replace("{{instruction}}", item["instruction"]
        ).replace("{{spreadsheet_path}}", str(sheet_in)
        ).replace("{{output_path}}", str(sheet_out))
    instance += "\n\n" + NOTE
    if dry_run:
        return {
            "task_id": task, "arm": arm, "dry_run": True,
            "system_hash": hashlib.sha256(tpls["system"].encode()).hexdigest(),
            "instance_hash": hashlib.sha256(instance.encode()).hexdigest(),
            "tool_order": [t["function"]["name"] for t in base.TOOLS],
            "model": MODEL, "temperature": TEMPERATURE, "top_p": TOP_P,
            "max_tokens": MAX_TOKENS, "tool_choice": "required",
            "parallel_tool_calls": False,
            "workdir_listing": sorted(p.name for p in live.iterdir()),
            "input_hash": (hashlib.sha256(sheet_in.read_bytes()).hexdigest()
                           if sheet_in.exists() else None),
            "shim": (live / "lx_helpers.py").read_text()[:60],
        }
    key = base.load_key()
    price_p, price_c = base.fetch_prices(key)
    # Loop guard (time.time) and wall_total (time.time) share this clock.
    t_start = time.time()
    # H1-only shared substrate (initial build, timed, role-tagged).
    substrate_records: list[dict] = []
    helper_used = False
    if arm == "H1":
        index.reset()
        rec = prepare_substrate(live, live / "shared_substrate", "initial",
                                ["OTHER_SHARED_FIXED"])
        rec.update({"task_id": task, "run_id": run_id, "turn": -1})
        substrate_records.append(rec)
    messages = [{"role": "system", "content": tpls["system"]},
                {"role": "user", "content": instance}]
    template_hash = hashlib.sha256((tpls["system"] + instance).encode()
                                   ).hexdigest()
    traj: list[dict] = []
    timing: list[dict] = []
    a_contact: list[dict] = []
    a_fallback: list[dict] = []
    h0_counterfactual: list[dict] = []
    freshness_log: list[dict] = []
    helper_rows: list[dict] = []
    integrity_obs: list[dict] = []
    provider_rows: list[dict] = []
    eff = {"api_calls": 0, "tokens": 0, "cost_usd": 0.0, "walltime_s": 0.0,
           "prompt_tokens": 0, "completion_tokens": 0,
           "python_execs": 0, "opens": 0, "saves": 0, "lo_invocations": 0,
           "commits": 0, "failures": 0, "retries": 0,
           "a_accelerated_ops": 0, "a_fallbacks": 0,
           "h0_eligible_loads": 0, "helper_calls": 0}
    t_provider = 0.0
    t_tool = 0.0
    t_view = 0.0
    t_lo = 0.0
    t_python = 0.0
    t_capture = 0.0
    t_substrate = substrate_records[0]["total_s"] if substrate_records else 0.0
    t_instrument = 0.0
    telem = {"mutations": 0, "runtime_failures": 0, "validation_failed": 0}
    status, submitted, call_idx = "INCOMPLETE", False, 0
    first_contact_turn = None
    while call_idx < CALL_LIMIT and (time.time() - t_start) < RUN_TIMEOUT:
        if get_spend() >= TOTAL_CAP:
            status = "CENSORED_CAP"
            break
        if eff["cost_usd"] >= INSTANCE_COST_LIMIT:
            status = "TRUNCATED_INSTANCE_COST"
            break
        try:
            res, cost = base.chat(key, messages, price_p, price_c)
        except Exception as exc:  # noqa: BLE001 - hardened transport path
            eff["failures"] += 1
            traj.append({"call": call_idx,
                         "error": f"{type(exc).__name__}: {exc}"})
            if eff["failures"] > 2:
                status = ("PROVIDER_CENSORED"
                          if isinstance(exc, base.ProviderCensoredError)
                          else "PROVIDER_ERROR")
                break
            eff["retries"] += 1
            continue
        call_idx += 1
        eff["api_calls"] += 1
        eff["cost_usd"] += cost
        eff["walltime_s"] += res["wall_s"]
        t_provider += res["wall_s"]
        usage = res.get("usage", {}) or {}
        eff["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
        eff["completion_tokens"] += int(usage.get("completion_tokens", 0)
                                        or 0)
        eff["tokens"] += int(usage.get("prompt_tokens", 0) or 0) + int(
            usage.get("completion_tokens", 0) or 0)
        add_spend(cost)
        provider_rows.append(
            {"task_id": task, "run_id": run_id, "call": call_idx,
             "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
             "completion_tokens": int(usage.get("completion_tokens", 0)
                                      or 0),
             "cost_usd": cost, "wait_s": res["wall_s"],
             "request_id": res.get("id")})
        msg = res["message"]
        messages.append({"role": "assistant", "content": msg.get("content"),
                         "tool_calls": msg.get("tool_calls")})
        calls = msg.get("tool_calls") or []
        if not calls:
            obs = "Warning: no tool call issued. You must call exactly ONE tool per response."
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", obs)})
            continue
        tc = calls[0]
        fname = (tc.get("function") or {}).get("name", "")
        try:
            fargs = json.loads((tc.get("function") or {}).get("arguments",
                                                              "{}"))
        except ValueError:
            fargs = {}
        traj.append({"call": call_idx, "tool": fname,
                     "args_keys": sorted(fargs),
                     "request_id": res.get("id"), "cost": cost})
        if fname == "submit":
            submitted = True
            status = "SUBMITTED"
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", "<<SWE_AGENT_SUBMISSION>>")})
            break
        if fname == "view_xlsx":
            t0 = time.perf_counter()
            cmd = [str(base.VIEW_XLSX), str(fargs.get("file_path", ""))]
            for k in ("mode", "sheet", "start_row", "end_row"):
                if fargs.get(k) is not None:
                    cmd.append(str(fargs[k]))
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=60)
                obs = proc.stdout + proc.stderr
                rc = proc.returncode
            except Exception as exc:  # noqa: BLE001
                obs, rc = f"view_xlsx error: {exc}", None
            el = time.perf_counter() - t0
            t_tool += el
            t_view += el
            eff["opens"] += 1
            timing.append({"task_id": task, "run_id": run_id, "arm": arm,
                           "turn": call_idx, "kind": "view_xlsx",
                           "wall_s": el, "returncode": rc})
            obs, _ = base.truncate_obs(obs, tpls["truncated"])
            if not obs.strip():
                obs = tpls["no_output"]
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", obs)})
            continue
        if fname == "bash":
            cmd = str(fargs.get("command", ""))
            is_python = "python" in cmd
            has_lo = "soffice" in cmd or "libreoffice" in cmd
            if is_python:
                eff["python_execs"] += 1
            if has_lo:
                eff["lo_invocations"] += 1
            safe, reason = (candidate_safe_source(cmd) if is_python
                            else (False, "not a Python inspection command"))
            force_real = is_python and not safe
            pre = snapshot_xlsx(live)
            env, event_path, helper_path = load_env_for_call(
                task, arm, run_id, live, call_idx, force_real)
            obs, timed_out, el, rc = run_bash_env(cmd, live, env)
            t_tool += el
            if is_python:
                t_python += el
            if has_lo:
                t_lo += el
            if timed_out:
                obs = tpls["cancelled"].replace("{{command}}", cmd[:200]
                    ).replace("{{timeout}}", str(BASH_TIMEOUT))
            changed = snapshot_xlsx(live) != pre
            # Candidate-A / spy telemetry.
            rows = read_events(event_path, call_idx) if event_path.exists(
            ) else []
            for row in rows:
                row.update({"task_id": task, "run_id": run_id, "arm": arm})
                if row.get("operation") == "load_workbook":
                    eff["opens"] += 1
                st = row.get("status")
                if st == "ACCELERATED" and row.get("operation") != (
                        "load_workbook"):
                    a_contact.append(row)
                    eff["a_accelerated_ops"] += 1
                    if first_contact_turn is None:
                        first_contact_turn = call_idx
                elif st == "ACCELERATED":
                    # Accelerated load_workbook: parse avoided. Archive the
                    # witness row (eff counters unchanged: schema stability).
                    a_contact.append(row)
                elif st in ("PREDECLARED_FALLBACK", "RUNTIME_FALLBACK",
                            "FAIL_CLOSED"):
                    a_fallback.append(row)
                    eff["a_fallbacks"] += 1
                elif st == "H0_COUNTERFACTUAL_ELIGIBLE":
                    eff["h0_eligible_loads"] += 1
                    h0_counterfactual.append(row)
                elif st == "H0_COUNTERFACTUAL_REJECTED":
                    h0_counterfactual.append(row)
            # Helper telemetry.
            if helper_path.exists():
                for line in helper_path.read_text().splitlines():
                    try:
                        h = json.loads(line)
                    except ValueError:
                        continue
                    h.update({"task_id": task, "run_id": run_id, "arm": arm,
                              "turn": call_idx})
                    helper_rows.append(h)
                    if h.get("event") == "helper_backend":
                        helper_used = True
                        eff["helper_calls"] += 1
            row_timing: dict[str, Any] = {
                "task_id": task, "run_id": run_id, "arm": arm,
                "turn": call_idx,
                "kind": "python" if is_python else "bash",
                "wall_s": el, "returncode": rc, "timed_out": timed_out,
                "a1_safe": safe, "a1_reason": reason,
                "workbook_changed": changed}
            if arm == "H1":
                recs, tsections = capture_wrap_timed(
                    live, pre, task, arm, call_idx)
                tcap = sum(tsections.values())
                t_capture += tcap
                row_timing["capture_s"] = tcap
                row_timing["capture_sections"] = {
                    k: round(v, 6) for k, v in tsections.items()}
                for rec in recs:
                    telem["mutations"] += 1
                    eff["commits"] += 1
                    if rec.get("runtime_failure"):
                        telem["runtime_failures"] += 1
                    if not rec.get("validation_passed", True):
                        telem["validation_failed"] += 1
                    rec["run_id"] = run_id
                    with open(fidelity_log, "a") as fh:
                        fh.write(json.dumps(rec) + "\n")
                roles = ["A_READ_ACCELERATION", "FRESHNESS"]
                if helper_used:
                    roles.append("HELPER_MIXED")
                t0 = time.perf_counter()
                ref = prepare_substrate(live, live / "shared_substrate",
                                        f"after_call_{call_idx}", roles)
                ref.update({"task_id": task, "run_id": run_id,
                            "turn": call_idx})
                substrate_records.append(ref)
                t_substrate += ref["total_s"]
                row_timing["substrate_refresh_s"] = ref["total_s"]
                freshness_log.append(ref)
            else:
                if changed:
                    ti0 = time.perf_counter()
                    for rel in sorted({str(p.relative_to(live))
                                       for p in live.rglob("*.xlsx")}
                                      - {".tmp"}):
                        if ".tmp" in rel:
                            continue
                        rec = observe_workbook_integrity(live / rel)
                        rec.update({"task_id": task, "run_id": run_id,
                                    "arm": arm, "turn": call_idx, "rel": rel})
                        integrity_obs.append(rec)
                    t_instrument += time.perf_counter() - ti0
            timing.append(row_timing)
            obs, _ = base.truncate_obs(obs, tpls["truncated"])
            if not obs.strip():
                obs = tpls["no_output"]
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", obs)})
            continue
        obs = f"Unknown tool '{fname}'. Available: bash, view_xlsx, submit."
        messages.append({"role": "user", "content": tpls["next_step"].replace(
            "{{observation}}", obs)})
    if status == "INCOMPLETE" and call_idx >= CALL_LIMIT:
        status = "TRUNCATED_CALL_LIMIT"
    if not submitted:
        status = status if status != "INCOMPLETE" else "NO_SUBMIT"
    wall_total = time.time() - t_start
    output_exists = sheet_out.exists()
    record = {
        "family": category, "task_id": task, "arm": arm, "run_id": run_id,
        "model": MODEL,
        "declared": {"temperature": TEMPERATURE, "top_p": TOP_P,
                     "max_tokens": MAX_TOKENS, "call_limit": CALL_LIMIT,
                     "instance_cost_limit": INSTANCE_COST_LIMIT,
                     "tool_choice": "required",
                     "parallel_tool_calls": False},
        "template_hash": template_hash,
        "status": status, "submitted": submitted,
        "censoring": classify_censoring(status, submitted),
        "output_produced": output_exists,
        "efficiency": eff,
        "h1_telemetry": telem if arm == "H1" else None,
        "first_contact_turn": first_contact_turn,
        "timing_totals": {
            "TOTAL_TASK_WALL_S": wall_total,
            "MODEL_PROVIDER_WAIT_S": t_provider,
            "TOOL_TOTAL_S": t_tool,
            "VIEW_XLSX_S": t_view,
            "PYTHON_TOOL_S": t_python,
            "LIBREOFFICE_BUCKET_S": t_lo,
            "CAPTURE_TOTAL_S": t_capture,
            "SUBSTRATE_TOTAL_S": t_substrate,
            "INSTRUMENTATION_S": t_instrument,
            "RUNNER_OVERHEAD_S": max(
                0.0, wall_total - t_provider - t_tool - t_capture
                - t_substrate - t_instrument),
        },
        "workdir": str(live),
    }
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "run_record.json").write_text(json.dumps(record, indent=1))
    (archive_dir / "trajectory.jsonl").write_text(
        "\n".join(json.dumps(t) for t in traj) + "\n")
    with open(archive_dir / "transcript_full.jsonl", "w") as fh:
        for m in messages:
            fh.write(json.dumps(m, default=str) + "\n")
    with open(archive_dir / "timing.jsonl", "w") as fh:
        for t in timing:
            fh.write(json.dumps(t) + "\n")
    with open(archive_dir / "provider.jsonl", "w") as fh:
        for t in provider_rows:
            fh.write(json.dumps(t) + "\n")
    with open(archive_dir / "candidate_a.jsonl", "w") as fh:
        for t in a_contact + a_fallback + h0_counterfactual:
            fh.write(json.dumps(t, default=str) + "\n")
    with open(archive_dir / "substrate.jsonl", "w") as fh:
        for t in substrate_records:
            fh.write(json.dumps(t, default=str) + "\n")
    with open(archive_dir / "helpers.jsonl", "w") as fh:
        for t in helper_rows:
            fh.write(json.dumps(t, default=str) + "\n")
    with open(archive_dir / "integrity.jsonl", "w") as fh:
        for t in integrity_obs:
            fh.write(json.dumps(t, default=str) + "\n")
    if output_exists:
        shutil.copy2(sheet_out, archive_dir / "output.xlsx")
    return record


SHIM_H0_TEXT = '''"""Model-facing shim: search/periods/inspect (reference backend, H0).

Optional: the agent may ignore this file and use ordinary Python/openpyxl.
Identical factual contract to the H1 shim; ordinary openpyxl reads only.
"""
import json as _json
import os as _os
import sys as _sys
import time as _time

_ROOT = _os.environ.get("LX_REPO_ROOT", "/home/kerem/Desktop/Personal Projects/librecalc-mcp")
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from benchmark.inspection_helpers import reference_api as _api

_ROLES = {"periods": "HELPER_PERIODS", "search": "HELPER_SEARCH",
          "inspect": "HELPER_INSPECT", "inspect_ranges": "HELPER_INSPECT"}


def _wrap(name):
    fn = getattr(_api, name)

    def call(*args, **kwargs):
        t0 = _time.perf_counter_ns()
        try:
            return fn(*args, **kwargs)
        finally:
            tel = _os.environ.get("REP_HELPER_TELEMETRY")
            if tel:
                try:
                    with open(tel, "a", encoding="utf-8") as fh:
                        fh.write(_json.dumps(
                            {"event": "helper_backend", "helper": name,
                             "consumer_role": _ROLES[name],
                             "backend": "reference_openpyxl",
                             "duration_ns": _time.perf_counter_ns() - t0,
                             "python_pid": _os.getpid()}) + "\\n")
                except OSError:
                    pass

    call.__name__ = name
    return call


periods = _wrap("periods")
search = _wrap("search")
inspect = _wrap("inspect")
inspect_ranges = _wrap("inspect_ranges")

__all__ = ["inspect", "inspect_ranges", "periods", "search"]
'''

# Final freeze: both arms use the same reference helper implementation.
SHIM_H1_TEXT = SHIM_H0_TEXT

BOOTSTRAP_TEXT = '"""Checkpoint-only bootstrap; no model-facing behavior."""\n\nimport benchmark.candidate_a_live_runtime  # noqa: F401\n'


def write_frozen() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SHIM_H0.write_text(SHIM_H0_TEXT)
    SHIM_H1.write_text(SHIM_H1_TEXT)
    BOOTSTRAP.write_text(BOOTSTRAP_TEXT)
    (OUT / "_helper_note.txt").write_text(NOTE)
    lo = subprocess.run(["soffice", "--headless", "--version"],
                        capture_output=True, text=True, timeout=60)
    json.dump({
        "soffice_executable": lo.returncode == 0,
        "soffice_version": lo.stdout.strip(),
        "scoring": "official evaluation.py WITH open_spreadsheet.py LO refresh, both arms",
    }, open(OUT / "environment.json", "w"), indent=1)
    json.dump({
        "name": "representative-architecture-economics-capability-checkpoint",
        "h0": "ordinary reference: real openpyxl (+inert spy), reference helper backend, no capture, no substrate",
        "h1": "practical retained invisible stack: substrate + Candidate A+A1 + capture + freshness; substrate helper backend",
        "model_config": "frozen production (z-ai/glm-5.3-flash, t=0, top_p=1, call cap 40, $0.25/instance)",
        "n": 1, "population": "30 tasks (10/family), seed 20260921",
        "forbidden": ["mechanism search", "A2/A3/B", "Track-C", "helper design",
                      "feedback", "surface changes", "budget changes"],
    }, open(OUT / "spec.json", "w"), indent=1)
    json.dump({
        "H0": {"model": MODEL, "temperature": TEMPERATURE, "top_p": TOP_P,
               "call_limit": CALL_LIMIT,
               "instance_cost_limit": INSTANCE_COST_LIMIT,
               "invisible": ["h0_spy_counterfactual", "reference_helpers",
                             "observational_integrity"]},
        "H1": {"model": MODEL, "temperature": TEMPERATURE, "top_p": TOP_P,
               "call_limit": CALL_LIMIT,
               "instance_cost_limit": INSTANCE_COST_LIMIT,
               "invisible": ["substrate", "candidate_a_a1", "capture",
                             "freshness", "substrate_helpers"]},
        "identical_surface": ["system prompt", "instance prompt incl note",
                              "tool schemas", "budgets", "runner", "scorer"],
    }, open(OUT / "arm_configs.json", "w"), indent=1)


def tasks_in_order() -> list[str]:
    pop = json.load(open(OUT / "population.json"))["selected"]
    out = []
    for cat in ("Template", "Financial_Model", "Debugging"):
        out.extend(f"{cat}:{tid}" for tid in pop[cat])
    return out


def identity_audit() -> dict:
    diffs = []
    for task in tasks_in_order():
        recs = {}
        for arm in ("H0", "H1"):
            live = reset_live(task, arm, OUT / "work")
            recs[arm] = run_task(task, arm, "dryrun", live, live,
                                 OUT / "fidelity_dry.jsonl", dry_run=True)
        c0, c1 = recs["H0"], recs["H1"]
        for field in ("system_hash", "instance_hash", "tool_order", "model",
                      "temperature", "top_p", "max_tokens", "tool_choice",
                      "parallel_tool_calls", "input_hash"):
            if c0[field] != c1[field]:
                diffs.append({"task": task, "field": field})
        if "lx_helpers.py" not in c0["workdir_listing"]:
            diffs.append({"task": task, "field": "shim_missing_H0"})
        if "lx_helpers.py" not in c1["workdir_listing"]:
            diffs.append({"task": task, "field": "shim_missing_H1"})
    audit = {"differences_unintended": diffs, "pass": not diffs,
             "intended_differences": [
                 "lx_helpers.py backend (H0 reference vs H1 substrate; identical surface)",
                 "invisible runtime flags (CANDIDATE_A_ARM, capture wrap, substrate manifest)",
                 "per-call telemetry paths"]}
    json.dump(audit, open(OUT / "experiment_integrity.json", "w"), indent=1)
    print("identity audit:", "PASS" if audit["pass"] else f"FAIL {diffs}")
    return audit


def primary_order() -> list[dict]:
    order = []
    for i, task in enumerate(tasks_in_order()):
        arms = ["H0", "H1"] if i % 2 == 0 else ["H1", "H0"]
        for arm in arms:
            order.append({"task_id": task, "arm": arm, "slot": len(order)})
    return order


def run_one(task: str, arm: str, run_id: str, phase: str = "primary") -> dict:
    live = reset_live(task, arm, OUT / "work")
    arch = OUT / ("reps" if phase == "primary" else "reps_replication"
                  ) / f"{task.replace(':', '_')}_{arm}_{run_id}"
    if arch.exists():
        shutil.rmtree(arch)
    fidelity_log = OUT / f"fidelity_{phase}.jsonl"
    try:
        return run_task(task, arm, run_id, live, arch, fidelity_log)
    except Exception as exc:  # noqa: BLE001 - never lose a slot silently
        rec = {"task_id": task, "arm": arm, "run_id": run_id,
               "status": "RUNNER_ERROR",
               "error": {"class": type(exc).__name__,
                         "message": str(exc)[:500]}}
        arch.mkdir(parents=True, exist_ok=True)
        (arch / "run_record.json").write_text(json.dumps(rec, indent=1))
        return rec


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-only", action="store_true")
    ap.add_argument("--worker", default=None,
                    help="i/N static partition over tasks")
    ap.add_argument("--run-one", default=None,
                    help="TASK:ARM:RUN_ID single slot")
    ap.add_argument("--phase", default="primary")
    args = ap.parse_args()
    write_frozen()
    if args.run_one:
        # TASK itself contains ':'; split arm/run from the right.
        task2, arm2, run2 = args.run_one.rsplit(":", 2)
        print(f"=== {task2} {arm2} {run2} ===", flush=True)
        rec = run_one(task2, arm2, run2, phase=args.phase)
        print(json.dumps({k: rec.get(k) for k in (
            "task_id", "arm", "status", "output_produced")}), flush=True)
        return
    audit = identity_audit()
    if not audit["pass"]:
        sys.exit(2)
    if args.audit_only:
        return
    order = primary_order()
    if args.worker:
        i, n = (int(x) for x in args.worker.split("/"))
        tasks = tasks_in_order()
        mine = set(tasks[i::n])
        order = [o for o in order if o["task_id"] in mine]
    done_log = OUT / ("run_order.json" if not args.worker else
                      f"run_order_w{args.worker.replace('/', '_')}.json")
    done = []
    if done_log.exists():
        try:
            done = json.load(open(done_log))
        except ValueError:
            done = []
    done_keys = {(d["task_id"], d["arm"]) for d in done}
    for o in order:
        if (o["task_id"], o["arm"]) in done_keys:
            continue
        run_id = f"primary_{o['slot']:02d}"
        print(f"=== {o['task_id']} {o['arm']} ({run_id}) ===", flush=True)
        rec = run_one(o["task_id"], o["arm"], run_id)
        print(json.dumps({k: rec.get(k) for k in (
            "task_id", "arm", "status", "output_produced")}), flush=True)
        done.append({**o, "run_id": run_id, "status": rec.get("status")})
        json.dump(done, open(done_log, "w"), indent=1)
    print("CHECKPOINT_SLOTS_DONE")


if __name__ == "__main__":
    main()

