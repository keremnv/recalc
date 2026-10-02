#!/usr/bin/env python3
"""Freeze control-only selection and the token-claim discovery specification.

This script performs no model inference and never reads treatment outcomes for
task selection. It is intentionally outside the frozen product RC.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research/history/token_claim_discovery"
FAMILIES = ("Template", "Financial_Model", "Debugging")
SEED = 20260922
HOLDOUT_SEED = 20261001


def put(name: str, obj: object) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    registry = json.loads((ROOT / "research/history/product_hygiene/future_claim_evidence_registry.json").read_text())
    aggregates = []
    for r in registry["rows"]:
        if r.get("scope") != "aggregate":
            continue
        source = ROOT / r["source"]
        c, t = r.get("control_tokens"), r.get("treatment_tokens")
        aggregates.append({
            "experiment": r["experiment"], "population": r.get("sample_size"),
            "control_input_or_total_tokens": c, "treatment_input_or_total_tokens": t,
            "measure": r.get("token_measure"),
            "control_output_tokens": None, "treatment_output_tokens": None,
            "total_tokens_available": "total" in r.get("token_measure", ""),
            "calls": None, "completion": None, "censoring": r.get("censoring"),
            "model_facing_difference": r.get("model_facing_mechanism_differed"),
            "invisible_difference": r.get("invisible_mechanism_differed"),
            "helper_adoption": r.get("note") if "helper" in r["experiment"].lower() else None,
            "known_attribution_problem": r.get("note"),
            "source": r["source"], "source_sha256": sha(source) if source.exists() else None,
            "ratio": t / c if c and t is not None else None,
        })
    put("historical_token_summary.json", {
        "unit": "experiment/cohort, not registry row", "aggregates": aggregates,
        "registry_rows_not_pooled": len(registry["rows"]),
        "warning": "Provider total and input-token observations are not interchangeable; missing output/call/completion fields remain null.",
    })

    # The representative checkpoint's H0 arm is control-side only. Prefer
    # completed/usable runs, then large prompt-token burden. No H1 files enter.
    candidates = []
    for p in sorted((ROOT / "research/history/representative_architecture_checkpoint/reps").glob("*H0*/run_record.json")):
        d = json.loads(p.read_text())
        task = d["task_id"]
        fam, tid = task.split(":", 1)
        if fam not in FAMILIES or tid.startswith("06_0") and fam == "Financial_Model":
            continue
        dataset = json.loads((ROOT / f"benchmark-data/SpreadsheetBench-2/data/{fam}/dataset.json").read_text())
        item = next((x for x in dataset if str(x["id"]) == tid), None)
        if not item or not (ROOT / f"benchmark-data/SpreadsheetBench-2/data/{fam}" / item["spreadsheet_path"]).exists():
            continue
        eff = d.get("efficiency", {})
        broad_views = 0
        view_bytes = 0
        transcript = p.parent / "transcript_full.jsonl"
        if transcript.exists():
            for line in transcript.read_text().splitlines():
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                for call in m.get("tool_calls") or []:
                    fn = call.get("function") or {}
                    if fn.get("name") == "view_xlsx":
                        try:
                            a = json.loads(fn.get("arguments") or "{}")
                        except ValueError:
                            a = {}
                        if a.get("mode") != "list" and (not a.get("sheet") or a.get("start_row") is None):
                            broad_views += 1
                if m.get("role") == "user" and len(str(m.get("content") or "")) > 1000:
                    view_bytes += len(str(m.get("content") or "").encode())
        candidates.append({"task": task, "family": fam, "control_status": d["status"],
                           "control_input_tokens": eff.get("prompt_tokens", 0),
                           "control_calls": eff.get("api_calls", 0),
                           "control_broad_views": broad_views,
                           "large_observation_bytes_proxy": view_bytes,
                           "historical_control_record": str(p.relative_to(ROOT)),
                           "prior_completion_priority": int(d["status"] == "SUBMITTED" and d.get("output_produced")),
                           })
    selected = []
    for fam in FAMILIES:
        pool = [x for x in candidates if x["family"] == fam]
        pool.sort(key=lambda x: (-x["prior_completion_priority"], -x["control_broad_views"],
                                 -x["large_observation_bytes_proxy"], -x["control_input_tokens"], x["task"]))
        for rank, x in enumerate(pool, 1):
            x["family_rank"] = rank
            x["selected"] = rank <= 5
            x["reason"] = "top five by frozen control-only headroom rule" if rank <= 5 else "below family cutoff"
        selected.extend([x["task"] for x in pool[:5]])
    if len(selected) != 15:
        raise RuntimeError(f"only {len(selected)} selected")
    put("selection_manifest.json", {"seed": SEED, "rule": "family; submitted valid H0 first; then broad view count; then observation-byte proxy; then H0 input tokens; then task ID", "candidates": candidates,
                                    "treatment_outcomes_used": False, "score_deltas_used": False})
    put("population.json", {"label": "MECHANISM_ENRICHED_NOT_REPRESENTATIVE", "seed": SEED,
                            "tasks": selected, "families": {f: [t for t in selected if t.startswith(f+":")] for f in FAMILIES},
                            "reason": "Selected on frozen control-side completion and high inspection/context headroom, not representative random sampling."})
    holdout = {}
    for fam in FAMILIES:
        dataset = json.loads((ROOT / f"benchmark-data/SpreadsheetBench-2/data/{fam}/dataset.json").read_text())
        ids = sorted(f"{fam}:{x['id']}" for x in dataset if f"{fam}:{x['id']}" not in selected)
        random.Random(HOLDOUT_SEED + FAMILIES.index(fam)).shuffle(ids)
        holdout[fam] = ids[:10]
    put("future_validation_reservation.json", {"seed": HOLDOUT_SEED, "label": "TOKEN_EFFICIENCY_CLAIM_VALIDATION_RESERVED_UNRUN", "tasks": holdout,
                                               "selection": "independent seeded sample from dataset excluding discovery tasks; no treatment outcomes inspected"})

    neutral = "## Working note\nUse the available spreadsheet tools as appropriate for the task. Check the workbook and produce the requested output. Continue until you can submit the result."
    salience = "## Working note\nPrefer targeted inspection of needed cells or ranges using ordinary Python/openpyxl. Avoid dumping entire workbooks or sheets unless broad inspection is required. Gather evidence incrementally."
    enc = tiktoken.get_encoding("cl100k_base")
    # Match S-factor fixed overhead without suggesting a workflow in neutral.
    target = len(enc.encode(salience))
    fillers = [" Record the final output path.", " Verify the requested file exists.", " Follow the task instructions.", " Keep the output workbook available."]
    i = 0
    while len(enc.encode(neutral)) < target - 5:
        neutral += fillers[i % len(fillers)]
        i += 1
    if abs(len(enc.encode(neutral)) - target) > 5:
        raise RuntimeError("notes failed token matching")
    helper_note = "## Optional factual helpers\nYou may import `lx_helpers` in Python. Available signatures: `search(workbook, pattern, regex=False, sheet=None)`, `periods(workbook, sheet=None)`, `inspect(workbook, sheet, cell_range, with_styles=False)`. These read the workbook with ordinary openpyxl. They are optional; ordinary Python/openpyxl and view_xlsx remain available."
    put("exact_notes.json", {"neutral": neutral, "salience": salience, "helper_on_addendum": helper_note,
                             "tokenizer": "tiktoken cl100k_base local estimate; model-native tokenizer not available",
                             "neutral_estimated_tokens": len(enc.encode(neutral)),
                             "salience_estimated_tokens": len(enc.encode(salience)),
                             "difference": abs(len(enc.encode(neutral))-len(enc.encode(salience))),
                             "helper_addendum_estimated_tokens": len(enc.encode(helper_note))})
    from benchmark import ab_local_runner as base
    put("helper_schemas.json", {"provider_tool_schemas_all_arms": base.TOOLS,
                                "provider_tool_schemas_differ": False,
                                "reason": "Frozen RC helpers are Python-callable lx_helpers, not a new provider tool API. H factor is availability and its exact Python signatures in an addendum.",
                                "helper_on_signatures": ["search(workbook, pattern, regex=False, sheet=None)", "periods(workbook, sheet=None)", "inspect(workbook, sheet, cell_range, with_styles=False)"],
                                "backend": "librecalc_agent 0.2.0rc1 reference openpyxl"})
    arms = {"A": {"S": 0, "H": 0}, "B": {"S": 0, "H": 1}, "C": {"S": 1, "H": 0}, "D": {"S": 1, "H": 1}}
    put("arm_configs.json", {"arms": arms, "common": {"candidate_a": False, "compiled_substrate": False, "capture": False,
                  "freshness": "inactive", "model": base.MODEL, "temperature": base.TEMPERATURE,
                  "top_p": base.TOP_P, "max_tokens": base.MAX_TOKENS, "call_cap": 40,
                  "task_deadline_s": 900, "provider_deadline_s": 240,
                  "instance_cost_cap_usd": 0.25, "helper_backend": "reference_openpyxl"}})
    order = []
    rng = random.Random(SEED)
    shuffled = selected[:]
    rng.shuffle(shuffled)
    latin = ["ABCD", "BCDA", "CDAB", "DABC"]
    for idx, task in enumerate(shuffled):
        for pos, arm in enumerate(latin[idx % 4]):
            order.append({"slot": len(order)+1, "task": task, "arm": arm, "within_task_position": pos+1,
                          "worker_preassignment": pos+1})
    put("run_order.json", {"seed": SEED, "method": "seeded task order plus cyclic Latin arm rotation; each task's four arms occupy one local block, four workers may run concurrently", "slots": order})

    # Design-only estimates from independent prior H0/H1 paired tasks; not
    # used to select any task. Structural variance estimates are descriptive.
    pairs = {}
    for p in (ROOT / "research/history/representative_architecture_checkpoint/reps").glob("*/run_record.json"):
        d = json.loads(p.read_text()); pairs.setdefault(d["task_id"], {})[d["arm"]] = d
    logs, call_diffs, complete = [], [], []
    family_logs = {f: [] for f in FAMILIES}
    for task, a in pairs.items():
        if "H0" not in a or "H1" not in a or "efficiency" not in a["H0"] or "efficiency" not in a["H1"]: continue
        c = a["H0"]["efficiency"]; t = a["H1"]["efficiency"]
        if c.get("prompt_tokens") and t.get("prompt_tokens"):
            z = math.log(t["prompt_tokens"]/c["prompt_tokens"])
            logs.append(z); family_logs[task.split(":")[0]].append(z)
        call_diffs.append(t.get("api_calls",0)-c.get("api_calls",0))
        complete.append((a["H0"]["status"] == "SUBMITTED",a["H1"]["status"] == "SUBMITTED"))
    put("variance_estimates.json", {"source": "representative checkpoint paired H0/H1, design scale only; different mechanism",
                                     "paired_n": len(logs), "task_log_ratio_sd": statistics.stdev(logs) if len(logs)>1 else None,
                                     "call_difference_sd": statistics.stdev(call_diffs) if len(call_diffs)>1 else None,
                                     "completion_by_arm": {"H0": sum(x[0] for x in complete), "H1": sum(x[1] for x in complete), "pairs": len(complete)},
                                     "family_log_ratio_sd": {f: statistics.stdev(v) if len(v)>1 else None for f,v in family_logs.items()},
                                     "note": "Not an effect estimate for the new factorial intervention."})
    spec = {
        "phase": "CLAIM_DISCOVERY", "product_rc": {"version": "0.2.0rc1", "source_config_sha256": "1aba31178faca5533c4a594cf1ee8bae2bf3668fcb5f7a9df65f84361f972aee", "wheel_sha256": "532e493f126087a45d86117343514a9a1cd0a4e0010af89bbd1be1b271d66b2e"},
        "arm_definitions": arms, "exact_notes_file_sha256": sha(OUT/"exact_notes.json"),
        "tool_schemas_sha256": sha(OUT/"helper_schemas.json"), "model_settings_sha256": sha(OUT/"arm_configs.json"),
        "population_selection_sha256": sha(OUT/"selection_manifest.json"), "population_sha256": sha(OUT/"population.json"),
        "run_order_sha256": sha(OUT/"run_order.json"), "primary_slots": 60,
        "primary_endpoint": "total provider-reported input/prompt tokens per task",
        "contrasts": ["D/A", "C/A", "B/A", "D/C", "interaction=(log D-log C)-(log B-log A)"],
        "analysis": "Task-level paired ratios; median, arithmetic and geometric means, percentile bootstrap 95% CI over tasks (seed 20260922, 10000 resamples), sign count, family stratification; E1 dual valid, E2 all uncensored, E3 total tokens/valid submission.",
        "censoring_taxonomy": ["PROVIDER_CENSORED","RUNNER_CENSORED","WORKBOOK_INFRA_CENSORED","MODEL_NONCOMPLETION","VALID_SUBMISSION","INVALID_SUBMISSION","OTHER"],
        "capability_guard": "Official evaluator on all submitted workbooks after LibreOffice refresh; no formal equivalence claim. Fail on reproducible treatment-specific completion or modification/regression degradation or savings from early termination.",
        "gate": "TOKEN_MECHANISM_DISCOVERED requires D/A median >=10% reduction, not 1-2 pathological tasks, favorable >=2 families, capability guard, coherent telemetry, component contrast material. Strong if bootstrap CI excludes zero. Salience and helper gates follow user specification.",
        "replication": "Only one-arm provider/runner/workbook censoring, large completion or official-score discordance, or >3x token-ratio pathology; <=2 additional draws per affected arm/task. Primary frozen separately.",
        "maximum_spend_usd": 25.0, "per_slot_cost_cap_usd": 0.25,
        "reservation_sha256": sha(OUT/"future_validation_reservation.json"),
        "no_architecture_changes": True, "holdout_not_run": True,
    }
    put("preregistered_spec.json", spec)
    put("spec_hash.json", {"algorithm": "sha256", "path": "research/history/token_claim_discovery/preregistered_spec.json", "sha256": sha(OUT/"preregistered_spec.json")})
    print("frozen_spec_sha256", sha(OUT/"preregistered_spec.json"))
    print("population", selected)
    print("note_tokens", len(enc.encode(neutral)), len(enc.encode(salience)))


if __name__ == "__main__":
    main()
