#!/usr/bin/env python3
"""Phase-12 live A/B runner: CONTROL / TREATMENT / SHAM.

Reuses the frozen ab_local_runner scaffold (templates, tools, model,
budgets) and adds a submit-boundary intervention for TREATMENT/SHAM.
Research-only; never touches product code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "research/history/phase12"))

import benchmark.ab_local_runner as base  # noqa: E402
from verification_block import verify  # noqa: E402

# Pilot finding (2026-09-28): the model can emit max-length reasoning
# generations (~195s server-side) on ordinary states; the inherited 90s
# per-call absolute deadline censored these legitimate slow generations
# as PROVIDER_ERROR. Raised to 300s for Phase 12; per-socket timeout,
# RUN_TIMEOUT, CALL_LIMIT, and cost caps unchanged. Prereg amendment A1.
base.CHAT_TIMEOUT = 300

RUNS_DIR = PROJECT_ROOT / "research/history/phase12" / "runs"
REPAIR_CALLS = 8
REPAIR_COST = 0.10
REPAIR_WALL = 300

SHAM_MESSAGE = (
    "Post-edit check complete. The workbook was recalculated and the "
    "current file is ready for review. Review it before deciding whether "
    "to submit or revise.")


def run_task(task: str, arm: str, pop: str) -> dict:
    assert arm in ("CONTROL", "TREATMENT", "SHAM"), arm
    category, _, tid = task.partition(":")
    tpls = base.load_templates()
    dataset = json.loads((base.DATA_ROOT / category / "dataset.json").read_text())
    item = next(d for d in dataset if str(d["id"]) == tid)
    workdir = RUNS_DIR / pop / f"{category}_{tid}_{arm}"
    workdir.mkdir(parents=True, exist_ok=True)
    import shutil
    src = base.DATA_ROOT / category / item["spreadsheet_path"]
    sheet_in = workdir / "input.xlsx"
    sheet_out = workdir / "output.xlsx"
    shutil.copy2(src, sheet_in)
    if sheet_out.exists():
        sheet_out.unlink()
    instance = tpls["instance"].replace("{{instruction}}", item["instruction"]
        ).replace("{{spreadsheet_path}}", str(sheet_in)
        ).replace("{{output_path}}", str(sheet_out))
    messages = [{"role": "system", "content": tpls["system"]},
                {"role": "user", "content": instance}]
    template_hash = hashlib.sha256((tpls["system"] + instance).encode()).hexdigest()
    key = base.load_key()
    price_p, price_c = base.fetch_prices(key)
    traj, behavior_cats = [], {"bash": 0, "view_xlsx": 0, "submit": 0}
    eff = {"api_calls": 0, "tokens": 0, "cost_usd": 0.0, "walltime_s": 0.0,
           "python_execs": 0, "opens": 0, "saves": 0, "lo_invocations": 0,
           "failures": 0, "retries": 0}
    verifier_ledger: dict = {"intervened": False}
    start = time.time()
    status, submitted, call_idx = "INCOMPLETE", False, 0
    repair_mode, repair_calls, repair_cost, repair_start = False, 0, 0.0, 0.0

    def budgets_ok() -> bool:
        if base.get_spend() >= base.TOTAL_CAP:
            return False
        if eff["cost_usd"] >= base.INSTANCE_COST_LIMIT:
            return False
        if repair_mode and (repair_calls >= REPAIR_CALLS
                            or repair_cost >= REPAIR_COST
                            or time.time() - repair_start >= REPAIR_WALL):
            return False
        return True

    while call_idx < base.CALL_LIMIT and (time.time() - start) < base.RUN_TIMEOUT:
        if not budgets_ok():
            status = "CENSORED_CAP" if base.get_spend() >= base.TOTAL_CAP else status
            if repair_mode:
                break  # repair window exhausted -> finalize current candidate
            if eff["cost_usd"] >= base.INSTANCE_COST_LIMIT:
                status = "TRUNCATED_INSTANCE_COST"
                break
            break
        try:
            res, cost = base.chat(key, messages, price_p, price_c)
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
        base.add_spend(cost)
        if repair_mode:
            repair_calls += 1
            repair_cost += cost
        msg = res["message"]
        messages.append({"role": "assistant", "content": msg.get("content"),
                         "tool_calls": msg.get("tool_calls")})
        calls = msg.get("tool_calls") or []
        if not calls:
            traj.append({"call": call_idx, "tool": "NO_TOOL_CALL",
                         "request_id": res["id"], "cost": cost,
                         "finish_reason": res.get("finish_reason"),
                         "repair_mode": repair_mode})
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}",
                "Warning: no tool call issued. You must call exactly ONE tool per response.")})
            continue
        tc = calls[0]
        fname = (tc.get("function") or {}).get("name", "")
        try:
            fargs = json.loads((tc.get("function") or {}).get("arguments", "{}"))
        except ValueError:
            fargs = {}
        traj.append({"call": call_idx, "tool": fname, "repair_mode": repair_mode,
                     "request_id": res["id"], "cost": cost,
                     "finish_reason": res.get("finish_reason")})
        if fname == "submit":
            behavior_cats["submit"] += 1
            if arm == "CONTROL" or repair_mode:
                submitted = True
                status = "SUBMITTED"
                messages.append({"role": "user", "content": tpls["next_step"].replace(
                    "{{observation}}", "<<SWE_AGENT_SUBMISSION>>")})
                break
            # ---- submit boundary intervention (TREATMENT / SHAM) ----
            pre_path = workdir / "pre_intervention.xlsx"
            if sheet_out.exists():
                shutil.copy2(sheet_out, pre_path)
            else:
                verifier_ledger = {"intervened": False, "reason": "no output at boundary"}
                submitted = True
                status = "SUBMITTED"
                messages.append({"role": "user", "content": tpls["next_step"].replace(
                    "{{observation}}", "<<SWE_AGENT_SUBMISSION>>")})
                break
            if arm == "SHAM":
                verifier_ledger = {"intervened": True, "kind": "sham",
                                   "repair_opened": True}
                repair_mode, repair_start = True, time.time()
                messages.append({"role": "user", "content": tpls["next_step"].replace(
                    "{{observation}}", SHAM_MESSAGE)})
                continue
            # TREATMENT: frozen verifier on frozen artifacts
            t0 = time.monotonic()
            report = verify(sheet_in, sheet_out)
            vwall = time.monotonic() - t0
            (workdir / "verifier_report.json").write_text(json.dumps(report, indent=1, default=str))
            verifier_ledger = {"intervened": True, "kind": "evidence",
                               "positive": report.get("positive"),
                               "status": report.get("status"),
                               "families": report.get("positive_families"),
                               "verifier_wall_s": vwall,
                               "repair_opened": bool(report.get("positive"))}
            if report.get("positive"):
                repair_mode, repair_start = True, time.time()
                messages.append({"role": "user", "content": tpls["next_step"].replace(
                    "{{observation}}", report["model_block"])})
                continue
            submitted = True
            status = "SUBMITTED"
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", "<<SWE_AGENT_SUBMISSION>>")})
            break
        elif fname == "view_xlsx":
            behavior_cats["view_xlsx"] += 1
            eff["opens"] += 1
            cmd = [str(base.VIEW_XLSX), str(fargs.get("file_path", ""))]
            for k in ("mode", "sheet", "start_row", "end_row"):
                if fargs.get(k) is not None:
                    cmd.append(str(fargs[k]))
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                obs = proc.stdout + proc.stderr
            except Exception as exc:
                obs = f"view_xlsx error: {exc}"
            obs, _ = base.truncate_obs(obs, tpls["truncated"])
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
            obs, timed_out = base.run_bash(cmd, workdir)
            if timed_out:
                obs = tpls["cancelled"].replace("{{command}}", cmd[:200]).replace(
                    "{{timeout}}", str(base.BASH_TIMEOUT))
            obs, _ = base.truncate_obs(obs, tpls["truncated"])
            if not obs.strip():
                obs = tpls["no_output"]
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}", obs)})
        else:
            messages.append({"role": "user", "content": tpls["next_step"].replace(
                "{{observation}}",
                f"Unknown tool '{fname}'. Available: bash, view_xlsx, submit.")})
    if status == "INCOMPLETE" and call_idx >= base.CALL_LIMIT:
        status = "TRUNCATED_CALL_LIMIT"
    if repair_mode and not submitted and sheet_out.exists():
        submitted = True  # window exhausted with a candidate: finalize it
        status = "SUBMITTED_AFTER_REPAIR_WINDOW"
    output_exists = sheet_out.exists()
    record = {
        "family": category, "task_id": task, "arm": arm, "pop": pop,
        "model": base.MODEL,
        "declared": {"temperature": base.TEMPERATURE, "top_p": base.TOP_P,
                     "max_tokens": base.MAX_TOKENS, "call_limit": base.CALL_LIMIT,
                     "instance_cost_limit": base.INSTANCE_COST_LIMIT,
                     "repair_calls": REPAIR_CALLS, "repair_cost": REPAIR_COST,
                     "repair_wall": REPAIR_WALL},
        "template_hash": template_hash,
        "status": status if submitted or status != "INCOMPLETE" else "NO_SUBMIT",
        "output_produced": output_exists,
        "efficiency": eff, "behavior": behavior_cats,
        "repair": {"used": repair_mode, "calls": repair_calls,
                   "cost": repair_cost},
        "verifier": verifier_ledger,
        "workdir": str(workdir),
    }
    (workdir / "run_record.json").write_text(json.dumps(record, indent=1))
    (workdir / "trajectory.jsonl").write_text(
        "\n".join(json.dumps(t) for t in traj) + "\n")
    with open(workdir / "transcript_full.jsonl", "w") as fh:
        for m in messages:
            fh.write(json.dumps(m, default=str) + "\n")
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--arm", required=True, choices=("CONTROL", "TREATMENT", "SHAM"))
    ap.add_argument("--pop", required=True)
    args = ap.parse_args()
    rec = run_task(args.task, args.arm, args.pop)
    print(json.dumps({k: rec[k] for k in (
        "task_id", "arm", "pop", "status", "output_produced", "verifier",
        "repair")}, indent=1))


if __name__ == "__main__":
    main()
