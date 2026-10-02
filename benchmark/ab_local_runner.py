#!/usr/bin/env python3
"""Local non-docker H0/H1 runner for the live transparent-runtime A/B.

Model surface is byte-identical in both arms: official system_template +
instance_template from benchmark/sweagent/spreadsheet-control.yaml, tools
bash / view_xlsx / submit, same model/sampling/budgets. Only H1 wraps each
bash call's workbook effects in a transparent transaction (snapshot, run
unchanged, derive WorkbookDelta, mechanical validation, atomic commit of the
identical bytes, telemetry). No new model info, helpers, or prompts in H1.

Usage:
  python3 benchmark/ab_local_runner.py --task Financial_Model:01_01 --arm H0
  python3 benchmark/ab_local_runner.py --task Financial_Model:01_01 --arm H1
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
RUNS_DIR = PROJECT_ROOT / "research/history/live_transparent_runtime_ab" / "runs"
SPEND_FILE = PROJECT_ROOT / "research/history/live_transparent_runtime_ab" / "_spend.json"
FIDELITY_LOG = PROJECT_ROOT / "research/history/live_transparent_runtime_ab" / "runtime_fidelity.jsonl"


def fidelity_log_path() -> Path:
    override = os.environ.get("AB_FIDELITY_LOG")
    return Path(override) if override else FIDELITY_LOG
DATA_ROOT = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data"
VIEW_XLSX = PROJECT_ROOT / "benchmark" / "sweagent" / "view_xlsx_ambient" / "bin" / "view_xlsx"

MODEL = "z-ai/glm-5.3-flash"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
TEMPERATURE = 0.0
TOP_P = 1.0
MAX_TOKENS = 8192
CALL_LIMIT = 40
INSTANCE_COST_LIMIT = 0.25
TOTAL_CAP = 25.0
BASH_TIMEOUT = 180
RUN_TIMEOUT = 900
# The hierarchy is deliberate: an individual socket operation is bounded,
# the complete provider response has a shorter total deadline than the retry
# window, and the caller's task/run bounds remain larger still.  The total
# deadline is enforced independently of urllib's per-socket timeout because a
# chunked response can otherwise reset the socket timer forever.
CHAT_SOCKET_TIMEOUT = 15
CHAT_TIMEOUT = 90
CHAT_RETRY_BUDGET = 270
MODEL_CALL_BUDGET = 300
MAX_OBS = 10_000


class ProviderCensoredError(TimeoutError):
    """A provider request exceeded its bounded response deadline."""


@contextlib.contextmanager
def _absolute_request_deadline(seconds: float):
    """Interrupt a blocking urllib read at an absolute wall-clock deadline.

    The live runner is single-threaded and runs on Linux.  SIGALRM is used so
    a server that emits one chunk just before every socket timeout cannot keep
    a request alive indefinitely.  Existing signal state is restored exactly.
    """
    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def handler(_signum, _frame):
        raise ProviderCensoredError(f"provider request exceeded {seconds:.3f}s total deadline")

    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])

def _extract_block(text: str, key: str) -> str:
    """Extract a |- literal block for `key:` from the control yaml without a yaml dep."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == f"{key}: |-":
            indent = len(ln) - len(ln.lstrip())
            buf = []
            for ln2 in lines[i + 1:]:
                if ln2.strip() == "" or (len(ln2) - len(ln2.lstrip())) > indent:
                    buf.append(ln2[indent + 2:] if len(ln2) > indent + 2 else "")
                else:
                    break
            while buf and buf[-1] == "":
                buf.pop()
            return "\n".join(buf)
    raise RuntimeError(f"template {key} not found in control yaml")


def load_templates() -> dict:
    text = (PROJECT_ROOT / "benchmark" / "sweagent" / "spreadsheet-control.yaml").read_text()
    return {
        "system": _extract_block(text, "system_template"),
        "instance": _extract_block(text, "instance_template"),
        "next_step": _extract_block(text, "next_step_template"),
        "no_output": _extract_block(text, "next_step_no_output_template"),
        "truncated": _extract_block(text, "next_step_truncated_observation_template"),
        "cancelled": _extract_block(text, "command_cancelled_timeout_template"),
    }


SYSTEM_TEMPLATE = None  # loaded from spreadsheet-control.yaml at runtime (byte-identical)


TOOLS = [
    {"type": "function", "function": {
        "name": "bash",
        "description": "run shell commands (e.g., file operations, calling Python scripts with `python3`)",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "shell command to run"}},
         "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "view_xlsx",
        "description": "view the content of an xlsx file. Can list all sheets or view a specific sheet's contents with optional row range",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string"},
            "mode": {"type": "string", "description": "list or content"},
            "sheet": {"type": "string"},
            "start_row": {"type": "integer"},
            "end_row": {"type": "integer"}},
         "required": ["file_path"]}}},
    {"type": "function", "function": {
        "name": "submit",
        "description": "submits the current file",
        "parameters": {"type": "object", "properties": {}}}},
]


def load_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        env = PROJECT_ROOT / ".env"
        if env.is_file():
            for line in env.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY must be set in the environment or in .env at the repo root")
    return key


def fetch_prices(key: str) -> tuple[float, float]:
    req = urllib.request.Request(MODELS_URL, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    for m in payload.get("data", []):
        if m.get("id") == MODEL or m.get("id", "").endswith("/glm-5.3-flash"):
            return float(m["pricing"]["prompt"]), float(m["pricing"]["completion"])
    raise RuntimeError(f"model {MODEL} not in OpenRouter catalog")


def chat(key: str, messages: list, price_p: float, price_c: float) -> tuple[dict, float]:
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with _absolute_request_deadline(CHAT_TIMEOUT):
            with urllib.request.urlopen(req, timeout=CHAT_SOCKET_TIMEOUT) as resp:
                out = json.loads(resp.read().decode())
    except ProviderCensoredError:
        raise
    except (TimeoutError, socket.timeout) as exc:
        raise ProviderCensoredError("provider socket/read timeout") from exc
    dt = time.monotonic() - t0
    choice = out["choices"][0]["message"]
    usage = out.get("usage", {}) or {}
    cost = usage.get("prompt_tokens", 0) * price_p + usage.get("completion_tokens", 0) * price_c
    return {"id": out.get("id"), "message": choice, "usage": usage,
            "cost": cost, "wall_s": dt,
            "finish_reason": out["choices"][0].get("finish_reason")}, cost


def truncate_obs(text: str, tpl_trunc: str) -> tuple[str, bool]:
    if len(text) <= MAX_OBS:
        return text, False
    half = MAX_OBS // 2
    elided = len(text) - MAX_OBS
    return tpl_trunc.replace("{{observation[ : max_observation_length // 2]}}", text[:half]
        ).replace("{{observation[- max_observation_length // 2:]}}", text[-half:]
        ).replace("{{elided_chars}}", str(elided)), True


def run_bash(cmd: str, cwd: Path) -> tuple[str, bool]:
    try:
        proc = subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True,
                              text=True, timeout=BASH_TIMEOUT,
                              env={**os.environ, "PIP_PROGRESS_BAR": "off"})
        return (proc.stdout + proc.stderr), False
    except subprocess.TimeoutExpired:
        return "", True


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


def h1_wrap(workdir: Path, pre: dict[str, bytes], task_id: str, arm: str, call_idx: int) -> list[dict]:
    """Transparent transaction per changed workbook. Committed bytes are exactly
    the Python-produced bytes; validation is record-only (never blocks)."""
    from benchmark.transparent_runtime.delta import derive_delta, replay_delta, read_parts
    from benchmark.transparent_runtime.validate import validate_mechanical
    telemetry = []
    post = snapshot_xlsx(workdir)
    for rel in sorted(set(pre) | set(post)):
        a, b = pre.get(rel), post.get(rel)
        if a is not None and b is not None and a == b:
            continue
        target = workdir / rel
        if b is None:
            telemetry.append({"task_id": task_id, "arm": arm, "call_idx": call_idx,
                              "rel": rel, "deleted": True, "runtime_failure": False})
            continue
        pre_b = a
        post_b = b
        delta = derive_delta(pre_b, post_b)
        committed = post_b
        import tempfile as _tf
        fd, tmp = _tf.mkstemp(dir=str(target.parent), prefix=target.name + ".", suffix=".tmp")
        try:
            with open(fd, "wb") as h:
                h.write(committed)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        committed_b = target.read_bytes()
        validation = validate_mechanical(pre_b, post_b, committed_b, delta)
        replayed = replay_delta(pre_b, delta)
        f1 = read_parts(replayed) == read_parts(committed_b)
        rec = {"task_id": task_id, "arm": arm, "call_idx": call_idx, "rel": rel,
               "delta_id": delta.delta_id, "pre_hash": delta.pre_hash,
               "post_hash": delta.post_hash, "created": delta.created,
               "f1_part_exact": f1, "f2_state_exact": f1,
               "opaque_preserved": list(delta.opaque_preserved),
               "validation": dict(validation.checks),
               "validation_passed": validation.passed,
               "runtime_failure": (not f1) or (committed_b != post_b)}
        telemetry.append(rec)
    return telemetry


def get_spend() -> float:
    try:
        return float(json.loads(SPEND_FILE.read_text()).get("total_usd", 0.0))
    except (OSError, ValueError):
        return 0.0


def add_spend(amount: float) -> float:
    total = get_spend() + amount
    SPEND_FILE.write_text(json.dumps({"total_usd": total}))
    return total


MUTATION_VERBS = ("python", "sed -i", "soffice", "libreoffice", ">", "save",
                  "openpyxl", "pandas", "unzip", "cp ", "mv ")


def classify_bash(cmd: str) -> str:
    low = cmd.lower()
    if any(v in low for v in MUTATION_VERBS):
        return "BASH_MUTATION_CAPABLE"
    return "BASH_READ_ONLY"


def run_task(task: str, arm: str, workdir: Path | None = None,
             archive_dir: Path | None = None, dry_run: bool = False,
             prompt_note: str | None = None) -> dict:
    category, _, tid = task.partition(":")
    assert arm in ("H0", "H1", "C0", "C1"), arm
    wrap = arm in ("H1", "C0", "C1")
    tpls = load_templates()
    dataset = json.loads((DATA_ROOT / category / "dataset.json").read_text())
    item = next(d for d in dataset if str(d["id"]) == tid)
    if workdir is None:
        workdir = RUNS_DIR / category / f"{category}_{tid}_{arm}"
    workdir.mkdir(parents=True, exist_ok=True)
    import shutil
    src = DATA_ROOT / category / item["spreadsheet_path"]
    sheet_in = workdir / "input.xlsx"
    sheet_out = workdir / "output.xlsx"
    if archive_dir is None:
        archive_dir = workdir
    else:
        archive_dir.mkdir(parents=True, exist_ok=True)
    instance = tpls["instance"].replace("{{instruction}}", item["instruction"]
        ).replace("{{spreadsheet_path}}", str(sheet_in)
        ).replace("{{output_path}}", str(sheet_out))
    if prompt_note:
        instance += "\n\n" + prompt_note
    messages = [{"role": "system", "content": tpls["system"]},
                {"role": "user", "content": instance}]
    template_hash = hashlib.sha256((tpls["system"] + instance).encode()).hexdigest()
    if dry_run:
        return {
            "task_id": task, "arm": arm, "dry_run": True,
            "system_hash": hashlib.sha256(tpls["system"].encode()).hexdigest(),
            "instance_hash": hashlib.sha256(instance.encode()).hexdigest(),
            "tools": TOOLS,
            "tool_order": [t["function"]["name"] for t in TOOLS],
            "model": MODEL, "temperature": TEMPERATURE, "top_p": TOP_P,
            "max_tokens": MAX_TOKENS, "tool_choice": "required",
            "parallel_tool_calls": False,
            "workdir_listing": sorted(p.name for p in workdir.iterdir()),
            "input_hash": (hashlib.sha256(sheet_in.read_bytes()).hexdigest()
                           if sheet_in.exists() else None),
            "request_body": {"model": MODEL, "temperature": TEMPERATURE,
                             "top_p": TOP_P, "max_tokens": MAX_TOKENS,
                             "tool_choice": "required", "parallel_tool_calls": False,
                             "n_messages": len(messages),
                             "system_len": len(tpls["system"]), "user_len": len(instance)},
        }
    key = load_key()
    price_p, price_c = fetch_prices(key)
    shutil.copy2(src, sheet_in)
    if sheet_out.exists():
        sheet_out.unlink()
    instance = tpls["instance"].replace("{{instruction}}", item["instruction"]
        ).replace("{{spreadsheet_path}}", str(sheet_in)
        ).replace("{{output_path}}", str(sheet_out))
    if prompt_note:
        instance += "\n\n" + prompt_note
    messages = [{"role": "system", "content": tpls["system"]},
                {"role": "user", "content": instance}]
    template_hash = hashlib.sha256((tpls["system"] + instance).encode()).hexdigest()
    traj, behavior_cats, eff = [], {"bash": 0, "view_xlsx": 0, "submit": 0}, {
        "api_calls": 0, "tokens": 0, "cost_usd": 0.0, "walltime_s": 0.0,
        "python_execs": 0, "opens": 0, "saves": 0, "lo_invocations": 0,
        "commits": 0, "failures": 0, "retries": 0}
    start = time.time()
    status, submitted, call_idx = "INCOMPLETE", False, 0
    telem_counts = {"mutations": 0, "runtime_failures": 0, "validation_failed": 0}
    events: list[dict] = []
    treatment_executed = False

    def log_event(kind: str) -> None:
        events.append({"idx": len(events), "call": call_idx, "event": kind,
                       "treatment_executed_before": treatment_executed})
    while call_idx < CALL_LIMIT and (time.time() - start) < RUN_TIMEOUT:
        if get_spend() >= TOTAL_CAP:
            status = "CENSORED_CAP"
            break
        if eff["cost_usd"] >= INSTANCE_COST_LIMIT:
            status = "TRUNCATED_INSTANCE_COST"
            break
        try:
            res, cost = chat(key, messages, price_p, price_c)
        except Exception as exc:
            eff["failures"] += 1
            traj.append({"call": call_idx, "error": f"{type(exc).__name__}: {exc}"})
            if eff["failures"] > 2:
                status = "PROVIDER_ERROR"
                break
            eff["retries"] += 1
            continue
        call_idx += 1
        eff["api_calls"] += 1
        eff["cost_usd"] += cost
        eff["walltime_s"] += res["wall_s"]
        eff["tokens"] += (res["usage"].get("prompt_tokens", 0)
                          + res["usage"].get("completion_tokens", 0))
        add_spend(cost)
        msg = res["message"]
        messages.append({"role": "assistant", "content": msg.get("content"),
                         "tool_calls": msg.get("tool_calls")})
        calls = msg.get("tool_calls") or []
        if not calls:
            log_event("TEXT_ONLY")
            obs = "Warning: no tool call issued. You must call exactly ONE tool per response."
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", obs)})
            continue
        tc = calls[0]
        fname = (tc.get("function") or {}).get("name", "")
        try:
            fargs = json.loads((tc.get("function") or {}).get("arguments", "{}"))
        except ValueError:
            fargs = {}
        traj.append({"call": call_idx, "tool": fname, "args_keys": sorted(fargs),
                     "request_id": res["id"], "cost": cost})
        if fname == "submit":
            behavior_cats["submit"] += 1
            log_event("SUBMIT")
            submitted = True
            status = "SUBMITTED"
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", "<<SWE_AGENT_SUBMISSION>>")})
            break
        elif fname == "view_xlsx":
            behavior_cats["view_xlsx"] += 1
            log_event("VIEW_XLSX")
            eff["opens"] += 1
            cmd = [str(VIEW_XLSX), str(fargs.get("file_path", ""))]
            for k in ("mode", "sheet", "start_row", "end_row"):
                if fargs.get(k) is not None:
                    cmd.append(str(fargs[k]))
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                obs = proc.stdout + proc.stderr
            except Exception as exc:
                obs = f"view_xlsx error: {exc}"
            obs, _ = truncate_obs(obs, tpls["truncated"])
            if not obs.strip():
                obs = tpls["no_output"]
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", obs)})
        elif fname == "bash":
            behavior_cats["bash"] += 1
            cmd = str(fargs.get("command", ""))
            if "python" in cmd:
                eff["python_execs"] += 1
            if "soffice" in cmd or "libreoffice" in cmd:
                eff["lo_invocations"] += 1
            log_event(classify_bash(cmd))
            pre = snapshot_xlsx(workdir)
            obs, timed_out = run_bash(cmd, workdir)
            if timed_out:
                obs = tpls["cancelled"].replace("{{command}}", cmd[:200]).replace(
                    "{{timeout}}", str(BASH_TIMEOUT))
            if snapshot_xlsx(workdir) != pre:
                log_event("WORKBOOK_MUTATION")
            if wrap:
                treatment_executed = True
                for rec in h1_wrap(workdir, pre, task, arm, call_idx):
                    telem_counts["mutations"] += 1
                    eff["commits"] += 1
                    if rec.get("runtime_failure"):
                        telem_counts["runtime_failures"] += 1
                    if not rec.get("validation_passed", True):
                        telem_counts["validation_failed"] += 1
                    with open(fidelity_log_path(), "a") as fh:
                        fh.write(json.dumps(rec) + "\n")
            obs, _ = truncate_obs(obs, tpls["truncated"])
            if not obs.strip():
                obs = tpls["no_output"]
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", obs)})
        else:
            obs = f"Unknown tool '{fname}'. Available: bash, view_xlsx, submit."
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", obs)})
    if status == "INCOMPLETE" and call_idx >= CALL_LIMIT:
        status = "TRUNCATED_CALL_LIMIT"
    if not submitted:
        log_event("STALL")
    first_event = events[0]["event"] if events else "NO_EVENTS"
    first_mutation_idx = next((e["idx"] for e in events if e["event"] == "WORKBOOK_MUTATION"), None)
    output_exists = sheet_out.exists()
    pre_mutation_stall = (not submitted and not output_exists
                          and first_mutation_idx is None)
    record = {
        "family": category, "task_id": task, "arm": arm, "model": MODEL,
        "declared": {"temperature": TEMPERATURE, "top_p": TOP_P,
                     "max_tokens": MAX_TOKENS, "call_limit": CALL_LIMIT,
                     "instance_cost_limit": INSTANCE_COST_LIMIT,
                     "tool_choice": "required", "parallel_tool_calls": False},
        "template_hash": template_hash,
        "status": status if submitted or status != "INCOMPLETE" else "NO_SUBMIT",
        "output_produced": output_exists,
        "efficiency": eff, "behavior": {
            "tool_call_categories": behavior_cats,
            "python_count": eff["python_execs"],
            "repair_loops": eff["retries"],
            "trajectory": traj},
        "h1_telemetry": telem_counts if arm == "H1" else None,
        "workdir": str(workdir),
        "boundary_events": events,
        "first_event": first_event,
        "first_mutation_idx": first_mutation_idx,
        "pre_mutation_stall": pre_mutation_stall,
    }
    (archive_dir / "run_record.json").write_text(json.dumps(record, indent=1))
    (archive_dir / "trajectory.jsonl").write_text(
        "\n".join(json.dumps(t) for t in traj) + "\n")
    with open(archive_dir / "transcript.jsonl", "w") as fh:
        for m in messages:
            fh.write(json.dumps(_redact_message(m)) + "\n")
    if os.environ.get("AB_FULL_TRANSCRIPT") == "1":
        with open(archive_dir / "transcript_full.jsonl", "w") as fh:
            for m in messages:
                fh.write(json.dumps(m, default=str) + "\n")
    if output_exists:
        import shutil as _sh
        _sh.copy2(sheet_out, archive_dir / "output.xlsx")
    return record


def _redact_message(m: dict) -> dict:
    out = {"role": m.get("role")}
    content = m.get("content")
    out["content"] = content[:4000] if isinstance(content, str) else content
    if m.get("tool_calls"):
        out["tool_calls"] = [
            {"name": (tc.get("function") or {}).get("name"),
             "args": str((tc.get("function") or {}).get("arguments", ""))[:2000]}
            for tc in m["tool_calls"]]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="Category:ID e.g. Financial_Model:01_01")
    ap.add_argument("--arm", required=True, choices=("H0", "H1", "C0", "C1"))
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--archive-dir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--note-file", default=None)
    args = ap.parse_args()
    from pathlib import Path as _P
    note = _P(args.note_file).read_text() if args.note_file else None
    rec = run_task(args.task, args.arm,
                   workdir=_P(args.workdir) if args.workdir else None,
                   archive_dir=_P(args.archive_dir) if args.archive_dir else None,
                   dry_run=args.dry_run, prompt_note=note)
    if args.dry_run:
        print(json.dumps(rec, indent=1))
    else:
        print(json.dumps({k: rec[k] for k in (
            "task_id", "arm", "status", "output_produced", "efficiency",
            "first_event", "pre_mutation_stall")}, indent=1))


if __name__ == "__main__":
    main()
