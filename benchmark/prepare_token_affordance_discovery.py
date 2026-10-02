#!/usr/bin/env python3
"""Freeze the final fresh token-affordance discovery design before inference."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark import ab_local_runner as base  # noqa: E402

OUT = ROOT / "research/history/token_affordance_discovery"
SEED = 20261007
FAMILIES = ("Template", "Financial_Model", "Debugging")
RC_VENV = Path("/tmp/librecalc-hygiene-rc-v55taghk/venv")
CONTROL_GLOBS = (
    "research/history/representative_architecture_checkpoint/reps/*H0*/run_record.json",
    "research/history/thin_architecture_checkpoint/reps/*H0/run_record.json",
    "research/history/live_transparent_runtime_ab/runs/**/*H0/run_record.json",
    "research/history/batch_write_helper_ab/reps/*C0/run_record.json",
)


def put(name, obj):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if (OUT / "preregistered_spec.json").exists():
        raise RuntimeError("preregistration already exists; refuse to overwrite frozen design")
    previous = set(json.loads((ROOT / "research/history/token_claim_discovery/population.json").read_text())["tasks"])
    reservation = json.loads((ROOT / "research/history/token_claim_discovery/future_validation_reservation.json").read_text())
    holdout = reservation["tasks"]
    holdout = set(sum(holdout.values(), [])) if isinstance(holdout, dict) else set(holdout)
    if len(previous) != 15 or len(holdout) != 30:
        raise RuntimeError("prior discovery or holdout reservation changed")
    if not RC_VENV.joinpath("bin/python").exists():
        raise RuntimeError("frozen RC virtual environment unavailable")

    candidates = {}
    inspected = []
    for pattern in CONTROL_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            record = json.loads(path.read_text())
            task = record.get("task_id") or record.get("task")
            if not task or ":" not in task:
                continue
            family, tid = task.split(":", 1)
            if family not in FAMILIES:
                continue
            why = None
            if task in previous:
                why = "previous_15_task_discovery"
            elif task in holdout:
                why = "reserved_30_task_validation"
            else:
                dataset_dir = ROOT / f"benchmark-data/SpreadsheetBench-2/data/{family}"
                dataset = json.loads((dataset_dir / "dataset.json").read_text())
                item = next((x for x in dataset if str(x["id"]) == tid), None)
                if not item or not (dataset_dir / item["spreadsheet_path"]).is_file():
                    why = "workbook_or_task_missing"
            eff = record.get("efficiency") or {}
            status = str(record.get("status") or "")
            calls = int(eff.get("api_calls") or 0)
            tokens = int(eff.get("prompt_tokens") or eff.get("tokens") or 0)
            row = {
                "task": task, "family": family, "historical_control_record": str(path.relative_to(ROOT)),
                "historical_control_sha256": sha(path), "historical_control_status": status,
                "historical_control_calls": calls, "historical_control_token_burden": tokens,
                "historical_control_output_produced": bool(record.get("output_produced")),
                "excluded_reason": why,
            }
            inspected.append(row)
            if why is not None:
                continue
            # Multiple H0/C0 observations of one task do not create extra
            # candidate tasks. Keep the best control-only completion/headroom
            # record, with a deterministic path tie-break.
            rank = (2 if status == "SUBMITTED" and row["historical_control_output_produced"] else
                    1 if status == "NO_SUBMIT" and calls >= 8 else 0,
                    calls, tokens, str(path))
            prior = candidates.get(task)
            if prior is None or rank > prior[0]:
                candidates[task] = (rank, row)

    rng = random.Random(SEED)
    tie = {task: rng.random() for task in sorted(candidates)}
    selected = []
    rankings = []
    for family in FAMILIES:
        pool = [row for _, row in candidates.values() if row["family"] == family]
        pool.sort(key=lambda r: (
            -(2 if r["historical_control_status"] == "SUBMITTED" and r["historical_control_output_produced"] else
               1 if r["historical_control_status"] == "NO_SUBMIT" and r["historical_control_calls"] >= 8 else 0),
            -r["historical_control_calls"], -r["historical_control_token_burden"],
            tie[r["task"]], r["task"],
        ))
        if len(pool) < 4:
            raise RuntimeError(f"insufficient fresh control-side candidates in {family}: {len(pool)}")
        for index, row in enumerate(pool, 1):
            rankings.append({**row, "family_rank": index, "selected": index <= 4,
                             "selection_reason": "top four by frozen control-only completion, nontruncated interaction, calls, token headroom" if index <= 4 else "below family cutoff"})
        selected.extend(r["task"] for r in pool[:4])
    if len(selected) != 12 or set(selected) & (previous | holdout):
        raise RuntimeError("fresh cohort invalid")

    put("selection_manifest.json", {
        "seed": SEED,
        "source_patterns": CONTROL_GLOBS,
        "rule": "Best H0/C0 record per task; within family rank completed output first, then usable nontruncated no-submit interaction, then call count, then control token burden, then seeded tie; take four.",
        "historical_records_inspected": inspected, "eligible_task_rankings": rankings,
        "previous_treatment_advantage_used": False, "helper_adoption_used": False, "score_delta_used": False,
        "reserved_holdout_task_ids_used_only_for_exclusion": True,
    })
    put("population.json", {"label": "AFFORDANCE_DISCOVERY_FRESH_NONREPRESENTATIVE", "seed": SEED,
                            "tasks": selected,
                            "families": {f: [t for t in selected if t.startswith(f + ":")] for f in FAMILIES},
                            "previous_discovery_overlap": 0, "reserved_holdout_overlap": 0,
                            "selection_scope": "control-side historical completion and model-call/token headroom only"})

    heading = "## Optional factual lookup\n"
    b_note = heading + ("Optional factual lookup capabilities may be available in some environments.\n"
                        "If you choose to rely on one, verify that it is available before use.\n"
                        "Ordinary Python/openpyxl remains fully available.")
    c_note = heading + ("Optional factual helpers are available through lx_helpers.\n"
                        "Available functions: search(...), periods(...), inspect(...).\n"
                        "You may import them if useful. Ordinary Python/openpyxl remains fully available.")
    status_command = [str(RC_VENV / "bin/python"), "-c",
                      "import lx_helpers; names=('search','periods','inspect'); "
                      "assert all(callable(getattr(lx_helpers,n,None)) for n in names); "
                      "print('lx_helpers availability: confirmed\\nfunctions available:\\n'+'\\n'.join(names))"]
    status_proc = subprocess.run(status_command, capture_output=True, text=True, timeout=20)
    if status_proc.returncode or not status_proc.stdout.startswith("lx_helpers availability: confirmed"):
        raise RuntimeError(f"frozen helper preflight failed: {status_proc.stderr[:300]}")
    d_observation = status_proc.stdout.strip()
    enc = tiktoken.get_encoding("cl100k_base")
    b_len, c_len = len(enc.encode(b_note)), len(enc.encode(c_note))
    if abs(b_len - c_len) > 5:
        raise RuntimeError(f"B/C notes not locally token-matched: {b_len}, {c_len}")
    put("exact_notes.json", {
        "A": "", "B": b_note, "C": c_note, "D": c_note,
        "D_status_observation": d_observation,
        "note_local_cl100k_tokens": {"A": 0, "B": b_len, "C": c_len, "D": c_len},
        "D_status_local_cl100k_tokens": len(enc.encode(d_observation)),
        "provider_native_note_tokenization": "not exposed; record provider-reported whole first-request input separately",
        "placement": "append note after identical task instance; D appends a separate neutral preflight observation before first model request",
        "format": "same heading and three short factual lines in B/C/D",
        "preflight_command": status_command,
        "preflight_stdout_sha256": hashlib.sha256(status_proc.stdout.encode()).hexdigest(),
    })
    put("arm_profiles.json", {
        "A": {"cue": "none", "helper_importable": False, "preflight_observation": False},
        "B": {"cue": "possible capability, verify before use", "helper_importable": False, "preflight_observation": False},
        "C": {"cue": "helper available with names", "helper_importable": True, "preflight_observation": False},
        "D": {"cue": "same as C", "helper_importable": True, "preflight_observation": True},
        "helper_backend": "frozen RC reference openpyxl", "provider_tool_schemas_identical": True,
        "provider_tools": base.TOOLS,
    })

    shuffled = selected[:]
    random.Random(SEED).shuffle(shuffled)
    latin = ("ABCD", "BCDA", "CDAB", "DABC")
    slots = []
    for index, task in enumerate(shuffled):
        for position, arm in enumerate(latin[index % 4], 1):
            slots.append({"slot": len(slots) + 1, "task": task, "arm": arm,
                          "within_task_position": position, "worker_preassignment": position})
    put("run_order.json", {"seed": SEED, "method": "seeded task order and cyclic Latin arm rotation, one four-arm concurrent block per task", "slots": slots})

    rc = json.loads((ROOT / "research/history/product_hygiene/rc_manifest.json").read_text())
    rc_sources_bad = [name for name, digest in rc["source_sha256"].items() if sha(ROOT / name) != digest]
    if rc_sources_bad or sha(ROOT / rc["wheel"]["wheel"]) != rc["wheel"]["sha256"]:
        raise RuntimeError(f"frozen RC changed: {rc_sources_bad}")
    settings = {
        "model": base.MODEL, "temperature": base.TEMPERATURE, "top_p": base.TOP_P,
        "max_tokens_per_call": base.MAX_TOKENS, "reasoning": "same unspecified/default provider setting as previous discovery",
        "tool_choice": "required", "parallel_tool_calls": False, "call_cap": 40,
        "task_deadline_seconds": 900, "provider_deadline_seconds": 240,
        "per_slot_estimated_cost_cap_usd": 0.25, "maximum_estimated_spend_usd": 25.0,
        "routing_policy": "same default OpenRouter routing as previous discovery; served provider recorded per call",
        "invisible_runtime": {"runtime_enabled": False, "candidate_a": False,
                              "compiled_substrate": False, "capture": False, "freshness": "inactive"},
        "scaffold": "same frozen bash/view_xlsx/submit tool schemas and prompt templates as previous discovery",
    }
    put("preregistered_spec.json", {
        "phase": "FINAL_FRESH_AFFORDANCE_CLAIM_DISCOVERY",
        "population_label": "AFFORDANCE_DISCOVERY_FRESH_NONREPRESENTATIVE",
        "product_rc": {"version": rc["version"], "source_config_sha256": rc["source_configuration_sha256"],
                       "wheel_sha256": rc["wheel"]["sha256"]},
        "hashes": {name: sha(OUT / name) for name in ("selection_manifest.json", "population.json",
                                                      "exact_notes.json", "arm_profiles.json", "run_order.json")},
        "prior_population_sha256": sha(ROOT / "research/history/token_claim_discovery/population.json"),
        "reserved_holdout_sha256": sha(ROOT / "research/history/token_claim_discovery/future_validation_reservation.json"),
        "primary_slots": 48, "model_and_runtime_settings": settings,
        "primary_endpoints": ["total provider-reported input tokens per task", "model-call count per task"],
        "contrasts": {"B_vs_A": "textual cue", "C_vs_B": "actual availability beyond cue",
                      "D_vs_C": "demonstrated queryability beyond announced availability",
                      "C_vs_A": "shippable announced availability", "D_vs_A": "shippable demonstrated queryability"},
        "secondary_resources": ["reported cached input", "input minus cached", "output tokens", "billed tokens if distinct", "provider-reported dollar cost"],
        "trajectory_telemetry": ["first workbook open", "first recorded save", "save count", "workbook opens", "recalc commands",
                                 "post-edit reads/recalc", "final-save-to-submit interval", "strict repeated views/reads/observations",
                                 "formula dumps", "whole-workbook scans", "targeted inspections", "Python inspection/stdout", "view/total observation bytes",
                                 "helper import attempts/failures", "helper calls/output"],
        "analysis": "Task-paired uncensored ratios and differences; dual-valid subset; 10000 task-bootstrap resamples seed 20261007; family stratification; leave-one-task/family-out; no outcome-driven exclusions.",
        "censoring": "provider/runner/workbook infra failures censored; model noncompletion and invalid submission remain outcomes; all 48 primary slots attempted",
        "capability_guard": "Official scorer after LibreOffice refresh for submitted workbooks; report validity, modification, regression, and submission discordance. No formal equivalence claim. Savings from premature termination or materially worse edits fail.",
        "gates": {
            "AFFORDANCE_EFFECT_DISCOVERED": "C or D vs A: median input reduction >=10%; geometric ratio <0.90; favorable >=2 families; favorable leave-one-task-out except <=1 mild reversal; call count favorable; capability guard; not noncompletion-driven; coherent trajectory.",
            "CUE_EFFECT_SUPPORTED": "B/A materially favorable plus lower calls plus capability guard",
            "AVAILABILITY_ADDS_VALUE": "C/B materially favorable",
            "DEMONSTRATED_QUERYABILITY_ADDS_VALUE": "D/C materially favorable",
            "strong_support": "bootstrap 95% CI for token ratio excludes one",
            "stop": "If neither C nor D clears and B does not robustly replicate, TOKEN_PRODUCT_EFFECT_NOT_ROBUST; end token-mechanism discovery and do not open holdout.",
        },
        "replication": "No automatic replication. Primary 48 slots frozen; only mechanical retries within original provider policy. No old-task reruns.",
        "architecture_discovery": "CLOSED", "holdout_run": False,
    })
    put("spec_hash.json", {"algorithm": "sha256", "sha256": sha(OUT / "preregistered_spec.json")})
    print("SPEC", sha(OUT / "preregistered_spec.json"))
    print("POPULATION", json.dumps(selected))
    print("NOTE_TOKENS", b_len, c_len, len(enc.encode(d_observation)))


if __name__ == "__main__":
    main()
