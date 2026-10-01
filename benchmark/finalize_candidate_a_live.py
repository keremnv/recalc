"""Finalize Candidate-A live artifacts after primary/targeted runs.

This performs no model inference. It merges the already archived targeted
replication into the telemetry/report artifacts and preserves the primary
six-task gates separately.
"""
from __future__ import annotations

import json
from pathlib import Path

import candidate_a_live_treatment as live


ROOT = live.ROOT
OUT = live.OUT


def read_jsonl(path: Path) -> list[dict]:
    return live.load_jsonl(path) if path.exists() else []


def write_jsonl(path: Path, rows: list[dict]) -> None:
    live.write_jsonl(path, rows)


def rep_events(records: list[dict], name: str) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        archive = Path(record.get("archive", ""))
        rows.extend(read_jsonl(archive / name))
    return rows


def pair_row(h0: dict, h1: dict) -> dict:
    e0, e1 = h0.get("efficiency", {}), h1.get("efficiency", {})
    return {
        "task_id": h0.get("task_id"),
        "replication": True,
        "h0_status": h0.get("status"),
        "h1_status": h1.get("status"),
        "h0_contact": h0.get("contact"),
        "h1_contact": h1.get("contact"),
        "h0_reads": e0.get("real_openpyxl_parses", 0),
        "h1_reads": e1.get("real_openpyxl_parses", 0),
        "real_openpyxl_parses_avoided": max(0, int(e0.get("real_openpyxl_parses", 0)) - int(e1.get("real_openpyxl_parses", 0))),
        "h0_python_walltime_s": e0.get("python_walltime_s", 0),
        "h1_python_walltime_s": e1.get("python_walltime_s", 0),
        "h0_tool_walltime_s": e0.get("tool_walltime_s", 0),
        "h1_tool_walltime_s": e1.get("tool_walltime_s", 0),
        "h0_total_walltime_s": h0.get("walltime_total_s"),
        "h1_total_walltime_s": h1.get("walltime_total_s"),
        "h0_model_network_s": e0.get("model_network_wait_s", 0),
        "h1_model_network_s": e1.get("model_network_wait_s", 0),
        "h0_common_substrate_s": e0.get("common_substrate_s", 0),
        "h1_common_substrate_s": e1.get("common_substrate_s", 0),
        "h1_contact_operations": h1.get("contact_operations", 0),
        "h0_output_produced": h0.get("output_produced"),
        "h1_output_produced": h1.get("output_produced"),
    }


def main() -> None:
    primary = read_jsonl(OUT / "primary_runs.jsonl")
    replication = read_jsonl(OUT / "replication_runs.jsonl")
    ranking = json.loads((OUT / "population_ranking.json").read_text())
    population = json.loads((OUT / "population.json").read_text())["selected"]

    # Reconstruct primary-only streams from their archives; the aggregate
    # files may already include replication from an earlier finalization.
    primary_contacts = rep_events(primary, "contact_events.jsonl")
    primary_fallbacks = rep_events(primary, "fallback_events.jsonl")
    primary_freshness = rep_events(primary, "freshness_events.jsonl")

    # Merge event streams so the deliverables cover both the primary and the
    # protocol-triggered targeted replication. Primary gates remain primary.
    for name in ("contact_events.jsonl", "fallback_events.jsonl", "freshness_events.jsonl", "execution_timing.jsonl", "pre_contact_variance.jsonl"):
        primary_rows = read_jsonl(OUT / name)
        rep_rows = rep_events(replication, name)
        write_jsonl(OUT / name, primary_rows + rep_rows)

    primary_matched = [x for x in read_jsonl(OUT / "matched_mechanism_cases.jsonl") if not x.get("replication")]
    rep_by_arm = {r.get("arm"): r for r in replication if r.get("task_id") == "Financial_Model:08_03"}
    rep_matched = [pair_row(rep_by_arm["H0"], rep_by_arm["H1"])] if {"H0", "H1"} <= set(rep_by_arm) else []
    matched = primary_matched + rep_matched
    write_jsonl(OUT / "matched_mechanism_cases.jsonl", matched)
    live.write_json(OUT / "task_timing.json", {
        "pairs": matched,
        "note": "Model/network and deterministic tool/Python timing are separate. Direct workbook-load/read timing was not instrumented; tool walltime is retained only as a deterministic proxy. Primary and targeted replication pairs are marked separately.",
    })
    live.write_json(OUT / "repeated_open_analysis.json", {
        "pairs": matched,
        "definition": "real openpyxl parse counts from runtime telemetry; H1 proxy loads are not real parses; common substrate refresh is separate; arm differences are not causal without matched behavioral equivalence",
        "primary_same_generation_repeated_open_difference": sum(max(0, int(x.get("real_openpyxl_parses_avoided", 0))) for x in primary_matched),
        "replication_same_generation_repeated_open_difference": sum(max(0, int(x.get("real_openpyxl_parses_avoided", 0))) for x in rep_matched),
    })

    effect = json.loads((OUT / "effectiveness_gate.json").read_text())
    for row in effect.get("contact_task_reductions", []):
        row["h0_deterministic_tool_walltime_s"] = row.pop("h0_read_open_time_s", row.get("h0_deterministic_tool_walltime_s"))
        row["h1_deterministic_tool_walltime_s"] = row.pop("h1_read_open_time_s", row.get("h1_deterministic_tool_walltime_s"))
    effect["direct_workbook_read_open_time_instrumented"] = False
    effect["measurement_basis"] = "deterministic tool walltime proxy; includes Python/tool execution and does not isolate workbook load/read"
    effect["note"] = "Primary n=1 contact comparisons only; replication is preserved separately and does not add an independent task."
    live.write_json(OUT / "effectiveness_gate.json", effect)

    # Score files were refreshed after replication. Add explicit replication
    # capability rows without allowing the extra pair to alter the six-task
    # primary contact/effectiveness gates.
    capability = json.loads((OUT / "capability.json").read_text())
    cap_gate = json.loads((OUT / "capability_gate.json").read_text())
    cap_gate["targeted_replication"] = [
        {
            "task_id": r.get("task_id"),
            "arm": r.get("arm"),
            "status": r.get("status"),
            "output_produced": r.get("output_produced"),
            "submitted": r.get("submitted"),
            "contact": r.get("contact"),
            "contact_operations": r.get("contact_operations", 0),
        }
        for r in replication
    ]
    cap_gate["targeted_replication_result"] = {
        "output_discordance_reproduced": bool(rep_by_arm) and rep_by_arm["H0"].get("output_produced") != rep_by_arm["H1"].get("output_produced"),
        "capability_loss_attributed": False,
        "note": "The primary H0 output/H1 no-output discordance was not reproduced: both targeted-replication arms produced no output.",
    }
    cap_gate["note"] = "Primary n=1 capability rows are preserved; the required targeted replication did not reproduce the output discordance, and no Candidate-A-caused capability loss was established."
    live.write_json(OUT / "capability_gate.json", cap_gate)
    capability["targeted_replication"] = cap_gate["targeted_replication"]
    capability["targeted_replication_result"] = cap_gate["targeted_replication_result"]
    live.write_json(OUT / "capability.json", capability)

    behavior = json.loads((OUT / "model_behavior.json").read_text())
    behavior["targeted_replication"] = [
        {
            "task_id": r.get("task_id"),
            "arm": r.get("arm"),
            "run_id": r.get("run_id"),
            "status": r.get("status"),
            "model_calls": r.get("efficiency", {}).get("api_calls", 0),
            "total_tokens": r.get("efficiency", {}).get("tokens", 0),
            "cost_usd": r.get("efficiency", {}).get("cost_usd", 0),
            "contact": r.get("contact", False),
            "contact_operations": r.get("contact_operations", 0),
        }
        for r in replication
    ]
    live.write_json(OUT / "model_behavior.json", behavior)

    reliability = json.loads((OUT / "reliability_gate.json").read_text())
    rep_freshness_count = len(rep_events(replication, "freshness_events.jsonl"))
    reliability["primary_freshness_events"] = len(primary_freshness)
    reliability["targeted_replication_freshness_events"] = rep_freshness_count
    reliability["freshness_events"] = reliability["primary_freshness_events"] + rep_freshness_count
    reliability["targeted_replication_stale_reads"] = 0
    reliability["targeted_replication_wrong_generation_reads"] = 0
    reliability["targeted_replication_fallback_identity_corruption"] = 0
    live.write_json(OUT / "reliability_gate.json", reliability)

    verdict = json.loads((OUT / "verdict.json").read_text())
    verdict["reliability"] = reliability
    verdict["effectiveness"] = effect
    verdict["targeted_replication"] = {
        "task_id": "Financial_Model:08_03",
        "order": [r.get("arm") for r in replication],
        "h0_output_produced": rep_by_arm.get("H0", {}).get("output_produced"),
        "h1_output_produced": rep_by_arm.get("H1", {}).get("output_produced"),
        "h1_contact": rep_by_arm.get("H1", {}).get("contact"),
        "h1_contact_operations": rep_by_arm.get("H1", {}).get("contact_operations", 0),
        "output_discordance_reproduced": cap_gate["targeted_replication_result"]["output_discordance_reproduced"],
        "capability_loss_attributed": False,
    }
    live.write_json(OUT / "verdict.json", verdict)
    live.write_json(OUT / "next_experiment.json", {
        "experiment": "instrumented identical-interface Candidate-A checkpoint with a larger exposure-enriched population and direct per-load/read timing; preserve conservative fallback and do not add model-facing functionality",
        "reason": "primary live contact reached only 2 independent tasks and the runner measured deterministic tool walltime rather than isolated workbook-read/open time",
        "candidate_B": "remain frozen",
        "no_new_helpers": True,
    })
    ledger = json.loads((OUT / "evidence_ledger.json").read_text())
    ledger["CANDIDATE_A_LIVE_CONTACT"] = "SUPPORTED_NARROWLY"
    live.write_json(OUT / "evidence_ledger.json", ledger)

    # Keep the six-task primary report as the main adjudication and add an
    # explicit replication section before the ledger/final synthesis.
    report = live.render_report(
        population, ranking["ranking"], primary, primary_matched,
        primary_contacts,
        primary_fallbacks,
        primary_freshness,
        cap_gate.get("rows", []),
        effect,
        verdict["verdict"], verdict.get("contact_tasks", []),
        reliability,
    )
    marker = "## Evidence ledger\n"
    replication_section = (
        "## Targeted replication\n\n"
        "The required matched replication of Financial_Model:08_03 ran H1 first. "
        f"H1 contacted Candidate A ({rep_by_arm.get('H1', {}).get('contact_operations', 0)} accelerated operations); "
        f"H0 contacted Candidate A: {rep_by_arm.get('H0', {}).get('contact', False)}. "
        f"Output produced was H0={rep_by_arm.get('H0', {}).get('output_produced')} and H1={rep_by_arm.get('H1', {}).get('output_produced')}; "
        "the primary output/no-output discordance was therefore not reproduced. "
        "The replication does not add an independent task to the contact gate. "
        f"Its deterministic tool walltime was H0={rep_matched[0].get('h0_tool_walltime_s') if rep_matched else None:.2f}s versus H1={rep_matched[0].get('h1_tool_walltime_s') if rep_matched else None:.2f}s; this was not a positive timing replication.\n\n"
    )
    report = report.replace(marker, replication_section + marker, 1)
    report = report.replace(
        "H1 contacted 2 tasks and 4073 primitive operations:",
        "H1 contacted 2 primary tasks and 4073 primary primitive operations; the targeted replication additionally contacted 1 already-counted task (7211 operations):",
        1,
    )
    report = report.replace(
        "Direct workbook read/open time was not isolated. The deterministic tool-walltime proxy fell by a median 50.9573008375064% across the two primary contact comparisons, with 2 positive tasks; this is a small n=1 mechanism witness, not a benchmark estimate.",
        "Direct workbook read/open time was not isolated. The deterministic tool-walltime proxy fell by 50.96% and 33.79% on the two primary contact comparisons, but the required replication was H0=83.95s versus H1=86.31s; the live timing evidence is therefore mixed and not a clean read-time causal estimate.",
        1,
    )
    report = report.replace(
        "Run-level Python/tool timings are in `task_timing.json`; model latency can dominate and the timing sample is not statistically powered.",
        "On the two primary contact pairs, Python walltime fell from 82.82s to 26.65s and from 98.54s to 52.50s; total task walltime nevertheless rose from 870.01s to 934.51s and from 906.17s to 942.13s because model/network wait dominated. The replication Python walltime was H0=73.96s versus H1=79.97s. Full timings are in `task_timing.json`.",
        1,
    )
    report = report.replace(
        "Any total-task movement is secondary. The experiment’s success criterion is deterministic read/open time, not total task time.",
        "Total task time did not improve on the primary contact pairs: H1 was +7.4% and +4.0%; the replication was +2.9%. Model/network latency accounted for roughly 88–94% of those contacted task totals.",
        1,
    )
    report = report.replace(
        "No model-visible behavior or token/cost benefit is claimed; aggregate call/token/cost records are retained for neutrality checks.",
        "Primary aggregate behavior was H0=167 calls/6.69M tokens/$0.628 versus H1=133 calls/5.50M tokens/$0.523, but this is trajectory variance, not a treatment claim; the model surface was identical and token/cost benefit is not established.",
        1,
    )
    report = report.replace(
        "Run one targeted matched replication of the largest-contact pair only if its primary output/capability or pre-contact trajectory is discordant; otherwise freeze Candidate A and design a broader identical-interface checkpoint.",
        "Run one larger identical-interface Candidate-A checkpoint with direct per-load/read timing and an exposure-enriched population; keep conservative fallback and the model surface unchanged.",
        1,
    )
    report = report.replace(
        "No stale reads, wrong-generation reads, identity corruption, or unexplained semantic substitutions were recorded:",
        "Across primary and targeted-replication runs, no stale reads, wrong-generation reads, identity corruption, or unexplained semantic substitutions were recorded:",
        1,
    )
    (ROOT / "CANDIDATE_A_LIVE_TREATMENT_REPORT.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
