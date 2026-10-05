#!/usr/bin/env python3
"""Tier 1 served-model audit (prereg §3).

For each run dir: extract gen- ids from the debug log, query the OpenRouter
generation API, and verify served `model` equals the requested model id.
Emits one JSON row per run to stdout. Requires OPENROUTER_API_KEY (.env).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUNS = BASE / "_overlay/benchmark-root/benchmark-runs/openrouter"


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        env = BASE / "../../.env"
        for line in env.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    assert key, "OPENROUTER_API_KEY not found"
    for run_dir in sorted(RUNS.glob(sys.argv[1] if len(sys.argv) > 1 else "tier1-r*")):
        rec = json.loads((run_dir / "ledger.jsonl").read_text().strip().splitlines()[0])
        logs = sorted(run_dir.glob("*/trajectory/*/*.debug.log"))
        gen_ids = []
        for log in logs:
            gen_ids.extend(re.findall(r"id='(gen-[A-Za-z0-9_-]+)'", log.read_text()))
        gen_ids = list(dict.fromkeys(gen_ids))
        served = {}
        errors = 0
        for gid in gen_ids:
            req = urllib.request.Request(
                f"https://openrouter.ai/api/v1/generation?id={gid}",
                headers={"Authorization": f"Bearer {key}"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.load(resp)["data"]
                served[gid] = {"model": data.get("model"),
                               "provider": data.get("provider_name")}
            except (urllib.error.URLError, KeyError, ValueError):
                errors += 1
            time.sleep(0.2)
        requested = rec.get("model")
        # Normalization (documented instrument correction, see HALFWAY_DECISION.md):
        # OpenRouter reports fully-qualified snapshot ids (e.g.
        # anthropic/claude-4.5-sonnet-20250929) that are NOT separate catalog
        # models. VALID iff the served id shares the author slug and model
        # base with the requested catalog id. Raw served ids are recorded
        # verbatim; any genuinely different model still invalidates the run.
        def _tokens(mid):
            if not mid or "/" not in mid:
                return ("", ())
            author, name = mid.split("/", 1)
            toks = [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]
            toks = [t for t in toks if not re.fullmatch(r"\d{8}", t)]
            return (author.lower(), tuple(sorted(toks)))

        def _same_model(served_id, requested_id):
            if served_id == requested_id:
                return True
            # Same author + same model-name token set modulo separators,
            # token order, and date suffix. Served ids verified separately
            # to not exist as independent catalog models.
            return _tokens(served_id) == _tokens(requested_id)

        mismatched = [g for g, s in served.items()
                      if not _same_model(s["model"], requested)]
        print(json.dumps({"run_name": run_dir.name, "task": rec.get("task"),
                          "requested_model": requested,
                          "generations": len(gen_ids),
                          "audited": len(served), "audit_errors": errors,
                          "served_models": sorted({s["model"] for s in served.values()}),
                          "served_providers": sorted({s["provider"] for s in served.values()}),
                          "mismatched": mismatched,
                          "verdict": "VALID" if not mismatched and not errors else "PROVIDER_INVALID"}))


if __name__ == "__main__":
    main()
