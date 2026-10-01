#!/usr/bin/env python3
"""Resume frozen primary slots after an orchestrator/session interruption.

This changes no model request, arm, task, or runtime setting. Completed primary
slots are never relaunched. Four arms of each remaining task retain the frozen
local block and concurrent-worker schedule.
"""
from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "token_claim_discovery"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from benchmark.run_token_claim_discovery import valid_rc  # noqa: E402


def completed_slots() -> set[int]:
    p = OUT / "primary_runs.jsonl"
    return {int(json.loads(line)["slot"]) for line in p.read_text().splitlines() if line.strip()} if p.exists() else set()


def main() -> None:
    valid_rc()
    slots = json.loads((OUT / "run_order.json").read_text())["slots"]
    for i in range(0, len(slots), 4):
        block = [s for s in slots[i:i+4] if s["slot"] not in completed_slots()]
        if not block:
            continue
        print("resuming slots", [s["slot"] for s in block], flush=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(subprocess.run,
                                   [sys.executable, str(ROOT / "benchmark/run_token_claim_discovery.py"), "--slot", str(s["slot"])],
                                   capture_output=True, text=True)
                       for s in block]
            for future in as_completed(futures):
                p = future.result()
                print((p.stdout + p.stderr)[-1500:], flush=True)
                if p.returncode:
                    print("worker subprocess exit", p.returncode, flush=True)
    done = completed_slots()
    print(f"primary slots recorded: {len(done)}/60; missing: {sorted(set(range(1,61))-done)}", flush=True)


if __name__ == "__main__":
    main()
