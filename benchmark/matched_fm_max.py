#!/usr/bin/env python3
"""Fresh, gated Financial_Model A/B. Never uses historical scores as baseline.

The shared local gateway retains exact outgoing provider requests and responses,
and enforces one frozen model configuration and opportunity budget for both arms.
No benchmark inference is possible without a passing Phase A gate manifest.
"""
from __future__ import annotations

import argparse
import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
from pathlib import Path
import shutil
import sys
import threading
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import integration_autopsy as a
import matched_compiled_treatment as m
import run_openrouter_slice as control

ROOT = m.ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-fm-glm-max"
REMOTE = "https://openrouter.ai/api/v1/chat/completions"
TASKS = ["01_01", "02_01", "03_01", "04_01", "05_01", "06_01", "07_01", "08_01", "10_01", "11_01", "11_05", "12_05", "13_05", "14_05", "15_05", "16_05", "17_05", "18_05", "19_05", "20_05"]


def require_gates():
    path = a.OUT / "repair_gates.json"
    if not path.exists():
        raise RuntimeError("PHASE_A_GATES_NOT_COMPLETE")
    gates = m.read_json(path)
    if gates.get("status") != "PASS":
        raise RuntimeError("PHASE_A_GATES_NOT_PASSED")
    for name, expected in gates["repaired_source_sha256"].items():
        if m.file_digest(m.ROOT / name) != expected:
            raise RuntimeError(f"REPAIRED_SOURCE_CHANGED: {name}")
    resource_path = a.OUT / "resource_envelope_audit.json"
    if not resource_path.exists() or m.read_json(resource_path).get("status") != "READY":
        raise RuntimeError("RESOURCE_ENVELOPE_NOT_FROZEN")
    return gates


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read())


def freeze():
    gates = require_gates()
    if (ROOT / "freeze.json").exists():
        return m.read_json(ROOT / "freeze.json")
    catalog = get_json(control.OPENROUTER_MODELS_URL)
    model = control._openrouter_model(catalog, m.MODEL)
    m.write_json(ROOT / "capability_catalog.json", model)
    supported = (model.get("reasoning") or {}).get("supported_efforts")
    order = ["max", "xhigh", "high", "medium", "low", "minimal", "none"]
    if not supported:
        raise RuntimeError("REASONING_ENUM_NOT_DECLARED: capability check required; do not guess or silently downgrade")
    effort = next((e for e in order if e in supported), None)
    if effort is None or effort in ("none", "minimal", "low", "medium"):
        raise RuntimeError(f"MAXIMUM_REASONING_UNRESOLVED: {supported}")
    provider = {"allow_fallbacks": True, "require_parameters": True}
    config = {"model": m.MODEL, "temperature": 0.0, "top_p": 1.0, "reasoning": {"effort": effort}, "provider": provider}
    data = {"version": "fresh-matched-fm-max-v1", "frozen_at": m.now(), "population": TASKS, "population_source": str(m.CONTROL_SLICE), "arms": {"A0": "new bash/view_xlsx/openpyxl/LibreOffice control", "A1": "new repaired compiled architecture"}, "model_config": config, "model_config_sha256": m.digest(config), "provider_capability_evidence": str(ROOT / "capability_catalog.json"), "maximum_stochastic_calls_per_task": 50, "per_task_monetary_cap_usd": 4.0, "primary": "paired modification accuracy; A1 minus A0", "secondary": ["exact", "regression", "value-only modification", "model calls", "input tokens", "output tokens", "provider cost"], "mechanism": "correct canonical inference -> directly correct formula cells, deterministic translations, and correct downstream recalculated cells; A0 homologous writes compared mechanically", "historical_control_is_descriptive_only": True, "06_01_policy": "identical metadata-only repaired input in both arms; same metadata-tolerant evaluator", "early_stop": "reopen integration if widespread near-inert A1 outputs recur", "repair_gates_sha256": m.digest(gates), "repaired_source_sha256": gates["repaired_source_sha256"], "pilot": False, "budget_rationale": "retain the 50-call opportunity ceiling after fixing group scope, delta leakage and final-call starvation; no increase to conceal scheduling inefficiency"}
    maximum_output = (model.get("top_provider") or {}).get("max_completion_tokens")
    if not maximum_output:
        raise RuntimeError("MAXIMUM_OUTPUT_ALLOWANCE_NOT_DECLARED")
    data["max_tokens_per_call"] = int(maximum_output)
    data["provider_prices_per_token"] = {k: control._maximum_token_price(model, k) for k in ("prompt", "completion")}
    m.write_json(ROOT / "freeze.json", data)
    m.write_json(ROOT / "tasks.json", {"model": m.MODEL, "tasks": [{"category": "Financial_Model", "id": task} for task in TASKS]})
    return data


class Gateway:
    def __init__(self, directory, frozen, api_key):
        self.directory = directory
        self.frozen = frozen
        self.api_key = api_key
        self.records = [m.read_json(p) for p in sorted(directory.glob("*.json"))]

    def forward(self, body):
        config = self.frozen["model_config"]
        for field in ("model", "temperature", "reasoning"):
            if body.get(field) != config[field]:
                raise RuntimeError(f"MODEL_CONFIGURATION_MISMATCH: {field}")
        if body.get("stream"):
            raise RuntimeError("STREAMING_NOT_FROZEN")
        body["provider"] = config["provider"]
        body["top_p"] = config["top_p"]
        if len(self.records) >= self.frozen["maximum_stochastic_calls_per_task"]:
            raise RuntimeError("TASK_MODEL_CALL_LIMIT")
        spent = sum(float((r.get("response", {}).get("usage") or {}).get("cost") or 0) for r in self.records)
        if spent >= self.frozen["per_task_monetary_cap_usd"]:
            raise RuntimeError("TASK_COST_LIMIT")
        prices = self.frozen["provider_prices_per_token"]
        # The same conservative token-budget calculation governs both arms.
        # Byte count upper-bounds text tokenization; include tool framing slack.
        prompt_upper = len(json.dumps({k: body.get(k) for k in ("messages", "tools")}, ensure_ascii=False).encode()) + 2048
        remaining = self.frozen["per_task_monetary_cap_usd"] - spent - prompt_upper * prices["prompt"]
        allowance = min(self.frozen["max_tokens_per_call"], math.floor(remaining / prices["completion"])) if prices["completion"] else self.frozen["max_tokens_per_call"]
        if allowance <= 0:
            raise RuntimeError("TASK_COST_LIMIT")
        body["max_tokens"] = allowance
        record = {"index": len(self.records)+1, "started_at": m.now(), "request": body, "request_sha256": m.digest(body), "model_config": config, "state": "REQUEST_STARTED"}
        path = self.directory / f"{record['index']:03d}.json"
        m.write_json(path, record)
        request = urllib.request.Request(REMOTE, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        status = 200
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read().decode(errors="replace")
        except Exception as exc:
            status, raw = 502, json.dumps({"error": {"message": f"{type(exc).__name__}: {exc}"}})
        try: parsed = json.loads(raw)
        except ValueError: parsed = {"raw": raw}
        record.update(response=parsed, raw_response_text=raw, http_status=status, state="RESPONSE_RETAINED", finished_at=m.now())
        m.write_json(path, record)
        self.records.append(record)
        return status, raw.encode()


@contextlib.contextmanager
def gateway(directory, frozen, api_key):
    adapter = Gateway(directory, frozen, api_key)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                status, content = adapter.forward(body)
            except Exception as exc:
                status, content = 400, json.dumps({"error": {"message": str(exc)}}).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content))); self.end_headers(); self.wfile.write(content)
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v1"
    finally:
        server.shutdown(); server.server_close(); thread.join()


def run_task(arm, task):
    require_gates()
    frozen = m.read_json(ROOT / "freeze.json")
    if task not in frozen["population"]:
        raise RuntimeError("TASK_NOT_FROZEN")
    key = m.provider_key()
    if not key:
        raise RuntimeError("PROVIDER_CREDENTIAL_MISSING")
    task_key = "Financial_Model:" + task
    task_dir = ROOT / arm / ("Financial_Model-" + task)
    if (task_dir / "output.xlsx").exists():
        raise RuntimeError("EXISTING_OUTPUT_REQUIRES_VERIFIED_RESUME")
    with gateway(ROOT / "provider_calls" / arm / task, frozen, key) as url:
        if arm == "A1":
            m.REASONING = frozen["model_config"]["reasoning"]["effort"]
            m.DATABASES = a.OUT / "repaired_db"
            m.relational.OPENROUTER_URL = url + "/chat/completions"
            m.run_one_task(task_key, resume=(task_dir / "state.json").exists(), output_root=ROOT / arm)
        else:
            saved_argv = sys.argv
            sys.argv = ["control", "--slice", str(ROOT / "tasks.json"), "--run-name", "matched-fm-glm-max-A0", "--model", m.MODEL, "--control", "--reasoning-effort", frozen["model_config"]["reasoning"]["effort"], "--cost-limit", str(frozen["per_task_monetary_cap_usd"]), "--call-limit", str(frozen["maximum_stochastic_calls_per_task"]), "--timeout", "10800", "--no-score"]
            try: args = control._apply_arm_config(control._arguments())
            finally: sys.argv = saved_argv
            model = control._model_preflight(m.MODEL)
            original_kwargs = control._completion_kwargs
            def kwargs(args, model):
                result = original_kwargs(args, model)
                result["api_base"] = url
                result["provider"] = frozen["model_config"]["provider"]
                return result
            control._completion_kwargs = kwargs
            original_stage = control._stage_task
            def stage(staging_root, benchmark_root, category, record):
                dest = original_stage(staging_root, benchmark_root, category, record)
                # Both arms receive the same private input copy, including 06_01.
                shutil.copy2(m.task_source(task_key), dest / record["spreadsheet_path"])
                return dest
            control._stage_task = stage
            control._run_task(args=args, api_key=key, task={"category": "Financial_Model", "id": task}, run_root=ROOT / arm, model_preflight=model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "run-task"])
    parser.add_argument("--arm", choices=["A0", "A1"])
    parser.add_argument("--task", choices=TASKS)
    args = parser.parse_args()
    if args.command == "freeze": print(json.dumps(freeze(), indent=2))
    else:
        if not args.arm or not args.task: parser.error("run-task requires --arm and --task")
        run_task(args.arm, args.task)
