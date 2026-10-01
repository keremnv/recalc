#!/usr/bin/env python3
"""Preregistered fresh affordance discovery runner; never edits frozen RC."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from benchmark import ab_local_runner as base  # noqa: E402

OUT = ROOT / "token_affordance_discovery"
RC_VENV = Path("/tmp/librecalc-hygiene-rc-v55taghk/venv")
ENC = tiktoken.get_encoding("cl100k_base")
base.CHAT_TIMEOUT = 240


def read(name: str):
    return json.loads((OUT / name).read_text())


def add_spend(usd: float) -> float:
    path = OUT / "_spend.json"
    with open(path, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        try: previous = float(json.loads(fh.read() or "{}").get("usd", 0))
        except ValueError: previous = 0
        total = previous + usd
        fh.seek(0); fh.truncate(); fh.write(json.dumps({"usd": total}))
        fcntl.flock(fh, fcntl.LOCK_UN)
    return total


def current_spend() -> float:
    try: return float(read("_spend.json").get("usd", 0))
    except (OSError, ValueError): return 0


def append(name: str, obj: dict) -> None:
    path = OUT / name
    with open(path, "a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.write(json.dumps(obj, default=str) + "\n")
        fcntl.flock(fh, fcntl.LOCK_UN)


def valid_rc() -> None:
    rc = json.loads((ROOT / "product_hygiene/rc_manifest.json").read_text())
    spec = read("preregistered_spec.json")["product_rc"]
    if rc.get("source_configuration_sha256") != spec["source_config_sha256"] or rc.get("wheel",{}).get("sha256") != spec["wheel_sha256"]:
        raise RuntimeError("Frozen PRODUCT_HYGIENE_RC manifest mismatch; stop")
    for rel, digest in rc.get("source_sha256", {}).items():
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Frozen RC source changed: {rel}; stop")
    if hashlib.sha256((ROOT / rc["wheel"]["wheel"]).read_bytes()).hexdigest() != spec["wheel_sha256"]:
        raise RuntimeError("Frozen RC wheel changed; stop")
    if not RC_VENV.joinpath("bin/python").exists():
        raise RuntimeError("Validated RC wheel environment missing; stop")
    if hashlib.sha256((OUT / "preregistered_spec.json").read_bytes()).hexdigest() != read("spec_hash.json")["sha256"]:
        raise RuntimeError("Preregistration hash changed; stop")
    for file, digest in read("preregistered_spec.json")["hashes"].items():
        if hashlib.sha256((OUT / file).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Frozen design artifact {file} changed; stop")
    spec = read("preregistered_spec.json")
    if hashlib.sha256((ROOT / "token_claim_discovery/future_validation_reservation.json").read_bytes()).hexdigest() != spec["reserved_holdout_sha256"]:
        raise RuntimeError("reserved holdout identity changed; stop")
    if hashlib.sha256((ROOT / "token_claim_discovery/population.json").read_bytes()).hexdigest() != spec["prior_population_sha256"]:
        raise RuntimeError("previous discovery population changed; stop")


def task_item(task: str):
    family, tid = task.split(":")
    folder = ROOT / "benchmark-data/SpreadsheetBench-2/data" / family
    item = next(x for x in json.loads((folder / "dataset.json").read_text()) if str(x["id"]) == tid)
    return family, tid, item, folder


def tool_env(helper_on: bool) -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("LIBRECALC_AGENT_RUNTIME_ENABLED", None)
    env["LIBRECALC_AGENT_RUNTIME_ENABLED"] = "0"
    env["CANDIDATE_A_ENABLED"] = "0"
    env["LIBRECALC_AGENT_SUBSTRATE_ENABLED"] = "0"
    env["LIBRECALC_AGENT_CAPTURE_ENABLED"] = "0"
    if helper_on:
        site = list((RC_VENV / "lib").glob("python*/site-packages"))
        if len(site) != 1: raise RuntimeError("RC site-packages unavailable")
        env["PYTHONPATH"] = str(site[0])
    return env


def local_decomp(messages: list[dict], tools: list[dict], note: str) -> dict:
    parts = {"SYSTEM_BASE_SCAFFOLD": 0, "TASK_PROMPT": 0, "EXPERIMENT_NOTE": len(note.encode()),
             "TOOL_SCHEMAS": len(json.dumps(tools).encode()), "PRIOR_ASSISTANT_OUTPUT": 0,
             "PRIOR_TOOL_OBSERVATIONS": 0, "CURRENT_TOOL_USER_INPUT": 0, "OTHER": 0}
    for i, m in enumerate(messages):
        content = m.get("content")
        if i == 0: parts["SYSTEM_BASE_SCAFFOLD"] += len(str(content or "").encode())
        elif i == 1:
            parts["TASK_PROMPT"] += max(0, len(str(content or "").encode()) - parts["EXPERIMENT_NOTE"])
        elif m.get("role") == "assistant": parts["PRIOR_ASSISTANT_OUTPUT"] += len(json.dumps(m).encode())
        elif m.get("role") in ("user", "tool"): parts["PRIOR_TOOL_OBSERVATIONS"] += len(str(content or "").encode())
        else: parts["OTHER"] += len(json.dumps(m).encode())
    parts["CURRENT_TOOL_USER_INPUT"] = len(str(messages[-1].get("content") or "").encode()) if len(messages)>2 else 0
    return {"bytes_by_category": parts, "estimated_tokens_by_category": {k: len(ENC.encode("x"*0)) if v==0 else round(v/3.5) for k,v in parts.items()},
            "method": "raw UTF-8 bytes exact; category token estimates use 3.5 bytes/token proxy, not provider usage"}


def request_model(key: str, messages: list[dict], tools: list[dict], run_dir: Path,
                  task: str, arm: str, call: int, prices: tuple[float,float], note: str):
    payload = {"model": base.MODEL, "messages": messages, "tools": tools,
               "tool_choice": "required", "parallel_tool_calls": False,
               "temperature": base.TEMPERATURE, "top_p": base.TOP_P,
               "max_tokens": base.MAX_TOKENS}
    body = json.dumps(payload, separators=(",", ":")).encode()
    (run_dir / "requests").mkdir(exist_ok=True)
    (run_dir / "requests" / f"call_{call:02d}.json").write_bytes(body)
    decomp = local_decomp(messages, tools, note)
    append("request_decomposition.jsonl", {"task": task, "arm": arm, "call": call,
                                           "request_payload_bytes": len(body), **decomp})
    req = urllib.request.Request(base.API_URL, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type":"application/json"})
    t0 = time.monotonic()
    try:
        with base._absolute_request_deadline(base.CHAT_TIMEOUT):
            with urllib.request.urlopen(req, timeout=base.CHAT_SOCKET_TIMEOUT) as resp:
                response = resp.read()
    except (TimeoutError, socket.timeout) as exc:
        raise base.ProviderCensoredError("provider socket/read timeout") from exc
    out = json.loads(response)
    (run_dir / "requests" / f"response_{call:02d}.json").write_bytes(response)
    usage = out.get("usage") or {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    cost = prompt*prices[0] + completion*prices[1]
    row = {"task": task, "arm": arm, "call": call, "request_id": out.get("id"),
           "served_model": out.get("model"), "served_provider": out.get("provider"),
           "prompt_tokens": prompt, "completion_tokens": completion,
           "cached_input_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
           "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
           "reported_cost_usd": usage.get("cost"), "estimated_cost_usd": cost,
           "request_payload_bytes": len(body), "response_bytes": len(response),
           "tool_schema_bytes": len(json.dumps(tools).encode()),
           "wait_s": time.monotonic()-t0, "raw_usage": usage}
    append("provider_usage.jsonl", row)
    return out["choices"][0]["message"], row


def run_one(slot: dict, phase: str = "PRIMARY") -> dict:
    valid_rc()
    task, arm = slot["task"], slot["arm"]
    family, tid, item, folder = task_item(task)
    run_dir = OUT / "runs" / phase.lower() / f"{slot['slot']:02d}_{family}_{tid}_{arm}"
    run_dir.mkdir(parents=True, exist_ok=True)
    live = run_dir / "work"
    if live.exists(): shutil.rmtree(live)
    live.mkdir()
    shutil.copy2(folder / item["spreadsheet_path"], live / "input.xlsx")
    notes = read("exact_notes.json")
    helper_on = arm in ("C", "D")
    note = notes[arm]
    if arm == "D":
        preflight = subprocess.run(notes["preflight_command"], capture_output=True, text=True, timeout=20)
        if preflight.returncode or preflight.stdout.strip() != notes["D_status_observation"]:
            raise RuntimeError("Frozen helper availability preflight failed; stop before inference")
        note += "\n\n## Preflight status observation\n" + notes["D_status_observation"]
    tpls = base.load_templates()
    instance = tpls["instance"].replace("{{instruction}}", item["instruction"]).replace(
        "{{spreadsheet_path}}", str(live / "input.xlsx")).replace("{{output_path}}", str(live / "output.xlsx"))
    if note:
        instance += "\n\n" + note
    messages = [{"role":"system","content":tpls["system"]}, {"role":"user","content":instance}]
    env = tool_env(helper_on)
    key = base.load_key()
    prices = base.fetch_prices(key)
    calls = 0; failures = 0; prompt = 0; completion = 0; cost_total = 0.0
    status = "MODEL_NONCOMPLETION"; events=[]; started=time.monotonic()
    while calls < 40 and time.monotonic()-started < 900:
        if current_spend() >= 25: status="RUNNER_CENSORED"; break
        if cost_total >= 0.25: status="MODEL_NONCOMPLETION"; break
        try:
            msg, usage = request_model(key,messages,base.TOOLS,run_dir,task,arm,calls+1,prices,note)
        except Exception as exc:
            failures += 1
            events.append({"call": calls+1, "event":"provider_error", "class":type(exc).__name__, "message":str(exc)[:500]})
            if failures > 2:
                status = "PROVIDER_CENSORED" if isinstance(exc, (base.ProviderCensoredError, urllib.error.URLError)) else "RUNNER_CENSORED"
                break
            continue
        failures = 0; calls += 1
        prompt += usage["prompt_tokens"]; completion += usage["completion_tokens"]
        cost_total += usage["estimated_cost_usd"]
        add_spend(usage["estimated_cost_usd"])
        messages.append({"role":"assistant","content":msg.get("content"),"tool_calls":msg.get("tool_calls")})
        toolcalls = msg.get("tool_calls") or []
        if not toolcalls:
            obs = "Warning: no tool call issued. You must call exactly ONE tool per response."
            messages.append({"role":"user","content":tpls["next_step"].replace("{{observation}}",obs)})
            events.append({"call":calls,"event":"no_tool_call"}); continue
        fn = toolcalls[0].get("function") or {}
        name = fn.get("name") or ""
        try: args = json.loads(fn.get("arguments") or "{}")
        except ValueError: args={}
        event={"task":task,"arm":arm,"call":calls,"tool":name,"arguments":args}
        if name == "submit":
            status="SUBMITTED"; events.append(event); append("mechanism_events.jsonl",event); break
        if name == "view_xlsx":
            cmd=[str(base.VIEW_XLSX),str(args.get("file_path",""))]
            for k in ("mode","sheet","start_row","end_row"):
                if args.get(k) is not None: cmd.append(str(args[k]))
            try:
                p=subprocess.run(cmd,capture_output=True,text=True,timeout=60,cwd=live,env=env)
                obs=p.stdout+p.stderr; event["returncode"]=p.returncode
            except Exception as exc:
                obs=f"view_xlsx error: {exc}"; event["returncode"]=None
            event["broad_view"] = args.get("mode") != "list" and (not args.get("sheet") or args.get("start_row") is None)
        elif name == "bash":
            cmd=str(args.get("command", ""))
            event["python_inspection"] = bool(re.search(r"\bpython(?:3)?\b|openpyxl|lx_helpers",cmd))
            event["helper_mentioned"] = "lx_helpers" in cmd
            event["whole_workbook_scan"] = bool(re.search(r"iter_rows|for\s+\w+\s+in\s+wb|for\s+\w+\s+in\s+ws",cmd))
            event["targeted_range"] = bool(re.search(r"\[[\"'][A-Z]{1,3}[0-9]+(?::[A-Z]{1,3}[0-9]+)?[\"']\]",cmd))
            try:
                p=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=180,cwd=live,env=env)
                obs=p.stdout+p.stderr; event["returncode"]=p.returncode
            except subprocess.TimeoutExpired as exc:
                obs=tpls["cancelled"].replace("{{command}}",cmd[:200]).replace("{{timeout}}","180")
                event["returncode"]=None; event["tool_timeout"]=True
        else:
            obs=f"Unknown tool '{name}'. Available: bash, view_xlsx, submit."
            event["returncode"]=None
        event["observation_bytes_raw"] = len(obs.encode())
        event["observation_local_tokens_raw"] = len(ENC.encode(obs))
        obs,truncated=base.truncate_obs(obs,tpls["truncated"])
        event["truncated"] = truncated
        event["observation_bytes_model_visible"] = len(obs.encode())
        event["observation_local_tokens_model_visible"] = len(ENC.encode(obs))
        if not obs.strip(): obs=tpls["no_output"]
        messages.append({"role":"user","content":tpls["next_step"].replace("{{observation}}",obs)})
        events.append(event);append("mechanism_events.jsonl",event)
    if status == "MODEL_NONCOMPLETION" and calls == 40: status="MODEL_NONCOMPLETION"
    output=live/"output.xlsx"
    if output.exists(): shutil.copy2(output,run_dir/"output.xlsx")
    for e in events: append("inspection_events.jsonl",e)
    (run_dir/"transcript_full.jsonl").write_text("\n".join(json.dumps(m,default=str) for m in messages)+"\n")
    (run_dir/"events.jsonl").write_text("\n".join(json.dumps(e,default=str) for e in events)+"\n")
    rec={"phase":phase,"task":task,"family":family,"arm":arm,"slot":slot["slot"],"status":status,
         "censoring":status if status in ("PROVIDER_CENSORED","RUNNER_CENSORED") else "NONE",
         "submitted":status=="SUBMITTED","output_exists":output.exists(),"prompt_tokens":prompt,
         "completion_tokens":completion,"api_calls":calls,"cost_usd_estimate":cost_total,
         "elapsed_s":time.monotonic()-started,"run_dir":str(run_dir.relative_to(ROOT)),
         "helper_exposed":helper_on,"runtime_enabled":False,"provider_errors":failures}
    (run_dir/"run_record.json").write_text(json.dumps(rec,indent=2)+"\n")
    append("primary_runs.jsonl" if phase=="PRIMARY" else "replication_runs.jsonl",rec)
    return rec


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument("--slot",type=int);ap.add_argument("--all",action="store_true")
    args=ap.parse_args(); valid_rc()
    slots=read("run_order.json")["slots"]
    if args.slot:
        completed={r["slot"] for r in (json.loads(line) for line in (OUT/"primary_runs.jsonl").read_text().splitlines() if line.strip())} if (OUT/"primary_runs.jsonl").exists() else set()
        if args.slot in completed:
            raise RuntimeError(f"slot {args.slot} already has a frozen primary result; refusing rerun")
        rec=run_one(slots[args.slot-1]);print(json.dumps({k:rec[k] for k in ("slot","task","arm","status","prompt_tokens","api_calls")}),flush=True)
    elif args.all:
        for i in range(0,len(slots),4):
            completed={r["slot"] for r in (json.loads(line) for line in (OUT/"primary_runs.jsonl").read_text().splitlines() if line.strip())} if (OUT/"primary_runs.jsonl").exists() else set()
            pending=[s for s in slots[i:i+4] if s["slot"] not in completed]
            if not pending:
                continue
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures=[pool.submit(subprocess.run,[sys.executable,str(Path(__file__)),"--slot",str(s["slot"])],capture_output=True,text=True) for s in pending]
                for future in as_completed(futures):
                    p=future.result();print((p.stdout+p.stderr)[-1000:],flush=True)
                    if p.returncode:
                        raise RuntimeError(f"primary slot subprocess failed with code {p.returncode}; stop and inspect before resuming")
    else: ap.error("select --slot N or --all")


if __name__=="__main__":main()
