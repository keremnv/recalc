#!/usr/bin/env python3
"""Post-hoc, read-only trajectory audit for the frozen token discovery runs.

Labels are observable syntactic proxies. They do not infer model confidence,
intent, or whether an inspection was semantically redundant.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics as stats
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "token_claim_discovery"
OUT = ROOT / "token_claim_review"
OUT.mkdir(exist_ok=True)

SAVE_RE = re.compile(r"\b(?:wb|workbook|book|w)\.save\s*\(")
RECALC_RE = re.compile(r"\b(?:soffice|libreoffice)\b")
READ_RE = re.compile(r"\b(?:load_workbook|read_excel)\s*\(")
SHELL_READ_RE = re.compile(r"\b(?:sed|grep|head|tail)\b[^\n]*(?:dump|\.txt)")


def jsonlines(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def view_key(event):
    arg = event.get("arguments") or {}
    return (Path(str(arg.get("file_path") or "")).name, arg.get("mode"),
            arg.get("sheet"), arg.get("start_row"), arg.get("end_row"))


def transcript_observations(run_dir: Path):
    messages = jsonlines(run_dir / "transcript_full.jsonl")
    observations = {}
    successful_call = 0
    for i, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        successful_call += 1
        if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
            content = str(messages[i + 1].get("content") or "")
            if len(content) > 100 and "<observation>" in content:
                observations[successful_call] = {
                    "sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "formula_visible": bool(re.search(r"(?<![A-Za-z0-9_])=[A-Za-z$0-9]", content)),
                }
    return observations


def analyze_run(rec):
    run_dir = ROOT / rec["run_dir"]
    events = [e for e in jsonlines(run_dir / "events.jsonl") if e.get("tool")]
    observations = transcript_observations(run_dir)
    if len({e["call"] for e in events}) != len(events):
        raise RuntimeError(f"duplicate tool event in {rec['run_dir']}")
    save_calls = [e["call"] for e in events
                  if e.get("tool") == "bash" and e.get("returncode") == 0
                  and SAVE_RE.search(str((e.get("arguments") or {}).get("command") or ""))]
    first_save = save_calls[0] if save_calls else None
    last_save = save_calls[-1] if save_calls else None
    seen_views = set()
    seen_read_commands = set()
    seen_observations = set()
    labeled = []
    for event in events:
        call = event["call"]
        tool = event["tool"]
        command = str((event.get("arguments") or {}).get("command") or "")
        is_save = tool == "bash" and event.get("returncode") == 0 and bool(SAVE_RE.search(command))
        is_recalc = tool == "bash" and bool(RECALC_RE.search(command))
        is_read = tool == "bash" and bool(READ_RE.search(command) or SHELL_READ_RE.search(command))
        is_workbook_open = tool == "bash" and bool(READ_RE.search(command))
        after_first_save = first_save is not None and call > first_save
        after_last_save = last_save is not None and call > last_save
        repeat_view = False
        if tool == "view_xlsx":
            key = view_key(event)
            repeat_view = key in seen_views and key[1] != "list"
            seen_views.add(key)
        repeat_exact_read_command = bool(is_read and not is_save and command in seen_read_commands)
        if is_read and not is_save and event.get("returncode") == 0:
            seen_read_commands.add(command)
        observed = observations.get(call) or {}
        observation_hash = observed.get("sha256")
        repeated_visible_observation = bool(observation_hash and observation_hash in seen_observations)
        if observation_hash:
            seen_observations.add(observation_hash)

        if tool == "view_xlsx" and (event.get("arguments") or {}).get("mode") == "list":
            category = "initial discovery / navigation"
        elif repeat_view and observed.get("formula_visible"):
            category = "repeated formula-chain or range inspection"
        elif repeat_view or repeat_exact_read_command:
            category = "reinspection of previously observed facts"
        elif is_save:
            category = "other / ambiguous"
        elif is_recalc and after_first_save:
            category = "post-edit verification"
        elif tool == "view_xlsx" and after_first_save and key[0] == "output.xlsx":
            category = "reopen / reread after mutation"
        elif is_workbook_open and after_first_save and "output.xlsx" in command:
            category = "reopen / reread after mutation"
        elif is_read and after_first_save:
            category = "post-edit verification"
        elif is_read and re.search(r"\bassert\b|#\s*(?:check|verify)\b", command, re.I):
            category = "verification / double-checking before edit"
        elif is_read or (tool == "view_xlsx" and not repeat_view):
            category = "new-evidence inspection"
        else:
            category = "other / ambiguous"

        flags = {
            "successful_workbook_save_command_proxy": is_save,
            "recalc_command": is_recalc,
            "workbook_open_command": is_workbook_open,
            "read_command": is_read,
            "exact_repeat_view_target": repeat_view,
            "repeat_view_with_visible_formula": repeat_view and bool(observed.get("formula_visible")),
            "exact_repeat_read_command": repeat_exact_read_command,
            "repeated_identical_visible_observation": repeated_visible_observation,
            "after_first_save_proxy": after_first_save,
            "after_last_save_proxy": after_last_save,
            "post_edit_read_or_recalc_proxy": after_first_save and (is_read or is_recalc or tool == "view_xlsx"),
            "post_final_save_inspection_proxy": after_last_save and (is_read or is_recalc or tool == "view_xlsx"),
            "helper_mentioned": bool(event.get("helper_mentioned")),
        }
        labeled.append({"task": rec["task"], "family": rec["family"], "arm": rec["arm"],
                        "call": call, "tool": tool, "category": category, "flags": flags,
                        "returncode": event.get("returncode")})

    # A loop means an observed save was followed by a recalc/read in that same
    # command or before the next save. It is an edit/check loop, not evidence
    # that either the edit or the check was unnecessary.
    edit_check_loops = 0
    for i, save_call in enumerate(save_calls):
        next_save = save_calls[i + 1] if i + 1 < len(save_calls) else rec["api_calls"] + 1
        if any(save_call <= x["call"] < next_save and
               (x["flags"]["recalc_command"] or x["flags"]["post_edit_read_or_recalc_proxy"])
               for x in labeled):
            edit_check_loops += 1

    flags = Counter()
    for item in labeled:
        flags.update({key: int(value) for key, value in item["flags"].items()})
    categories = Counter(item["category"] for item in labeled)
    summary = {
        "task": rec["task"], "family": rec["family"], "arm": rec["arm"],
        "status": rec["status"], "model_calls": rec["api_calls"],
        "first_save_command_call": first_save, "last_save_command_call": last_save,
        "save_command_calls": save_calls,
        "submit_calls_after_last_save": rec["api_calls"] - last_save if rec["status"] == "SUBMITTED" and last_save else None,
        "non_submit_tool_calls_after_last_save": sum(x["call"] > last_save for x in labeled) if last_save else None,
        "edit_check_loop_proxy_count": edit_check_loops,
        "categories": dict(categories), "flags": dict(flags),
        "helper_command_calls": flags["helper_mentioned"],
        "classifier_limit": "Categories are syntactic and conservative. Save command is only a mutation proxy; combined save/recalc commands stay ambiguous. Required-edit completion and factual redundancy are not mechanically identifiable.",
    }
    return summary, labeled


def paired_metric(rows, metric, *, dual_valid=False, exclude_helper=False):
    values = []
    for task in sorted({r["task"] for r in rows}):
        a = next(r for r in rows if r["task"] == task and r["arm"] == "A")
        b = next(r for r in rows if r["task"] == task and r["arm"] == "B")
        if a["status"] == "PROVIDER_CENSORED" or b["status"] == "PROVIDER_CENSORED":
            continue
        if dual_valid and not (a["status"] == "SUBMITTED" and b["status"] == "SUBMITTED"):
            continue
        if exclude_helper and b["helper_command_calls"]:
            continue
        va, vb = metric(a), metric(b)
        if va is not None and vb is not None:
            values.append({"task": task, "A": va, "B": vb, "difference_B_minus_A": vb - va})
    return {
        "n": len(values), "A_median": stats.median(v["A"] for v in values) if values else None,
        "B_median": stats.median(v["B"] for v in values) if values else None,
        "B_lower": sum(v["B"] < v["A"] for v in values),
        "equal": sum(v["B"] == v["A"] for v in values),
        "B_higher": sum(v["B"] > v["A"] for v in values),
        "pairs": values,
    }


def main():
    primary_path = DISCOVERY / "primary_runs.jsonl"
    primary = jsonlines(primary_path)
    freeze = json.loads((DISCOVERY / "primary_freeze.json").read_text())
    if hashlib.sha256(primary_path.read_bytes()).hexdigest() != freeze["files_sha256"]["primary_runs.jsonl"]:
        raise RuntimeError("primary outcome changed")
    rows = []
    events = []
    for rec in primary:
        summary, labeled = analyze_run(rec)
        rows.append(summary)
        events.extend(labeled)
    with (OUT / "trajectory_classification.jsonl").open("w") as stream:
        for event in events:
            stream.write(json.dumps(event, sort_keys=True) + "\n")

    final_event_count = len(events)
    raw_event_count = len(jsonlines(DISCOVERY / "mechanism_events.jsonl"))
    per_arm = {}
    for arm in "ABCD":
        arm_rows = [r for r in rows if r["arm"] == arm]
        per_arm[arm] = {
            "runs": len(arm_rows), "calls": sum(r["model_calls"] for r in arm_rows),
            "save_commands": sum(len(r["save_command_calls"]) for r in arm_rows),
            "edit_check_loop_proxies": sum(r["edit_check_loop_proxy_count"] for r in arm_rows),
            "categories": dict(sum((Counter(r["categories"]) for r in arm_rows), Counter())),
            "flags": dict(sum((Counter(r["flags"]) for r in arm_rows), Counter())),
        }

    comparisons = {}
    metrics = {
        "model_calls": lambda r: r["model_calls"],
        "first_save_call": lambda r: r["first_save_command_call"],
        "submit_gap_after_final_save": lambda r: r["submit_calls_after_last_save"],
        "post_final_save_non_submit_calls": lambda r: r["non_submit_tool_calls_after_last_save"],
        "save_commands": lambda r: len(r["save_command_calls"]),
        "edit_check_loop_proxies": lambda r: r["edit_check_loop_proxy_count"],
        "workbook_open_commands": lambda r: r["flags"].get("workbook_open_command", 0),
        "exact_repeat_view_targets": lambda r: r["flags"].get("exact_repeat_view_target", 0),
        "exact_repeat_read_commands": lambda r: r["flags"].get("exact_repeat_read_command", 0),
        "post_edit_read_or_recalc": lambda r: r["flags"].get("post_edit_read_or_recalc_proxy", 0),
    }
    for group, dual, no_helper in (("all_uncensored", False, False), ("dual_submitted", True, False),
                                   ("B_zero_helper", False, True), ("dual_submitted_B_zero_helper", True, True)):
        comparisons[group] = {key: paired_metric(rows, fn, dual_valid=dual, exclude_helper=no_helper)
                              for key, fn in metrics.items()}

    selected_events = []
    for rec in primary:
        selected_events.extend(e for e in jsonlines(ROOT / rec["run_dir"] / "events.jsonl") if e.get("tool"))
    raw_events = jsonlines(DISCOVERY / "mechanism_events.jsonl")
    corrected_observations = {
        arm: {
            "visible_observation_bytes": sum(e.get("observation_bytes_model_visible", 0) for e in selected_events if e.get("arm") == arm),
            "view_calls": sum(e.get("tool") == "view_xlsx" for e in selected_events if e.get("arm") == arm),
            "broad_views": sum(bool(e.get("broad_view")) for e in selected_events if e.get("arm") == arm),
        }
        for arm in "ABCD"
    }
    result = {
        "phase": "POST_HOC_INDEPENDENT_FORENSIC_REVIEW",
        "source_primary_sha256": freeze["files_sha256"]["primary_runs.jsonl"],
        "packet_sha256": hashlib.sha256((ROOT / "ASTRA_TOKEN_DIAGNOSIS_PACKET.md").read_bytes()).hexdigest(),
        "model_calls_added": 0, "holdout_used": False,
        "lineage": {"raw_mechanism_events": raw_event_count,
                    "selected_primary_tool_events": final_event_count,
                    "superseded_partial_block_events": raw_event_count - final_event_count,
                    "corrected_observation_totals": corrected_observations},
        "per_arm": per_arm,
        "paired_A_vs_B": comparisons,
        "task_summaries": rows,
        "interpretation_limit": "This is post-hoc behavioral classification, not a preregistered mediation test. No category measures confidence, intent, or whether the model had already performed the required edit correctly.",
    }
    write("affordance_trajectory_review.json", result)
    print(json.dumps({"tool_events": len(events), "raw_events": raw_event_count,
                      "A_save": per_arm["A"]["save_commands"], "B_save": per_arm["B"]["save_commands"],
                      "A_calls": per_arm["A"]["calls"], "B_calls": per_arm["B"]["calls"]}))


if __name__ == "__main__":
    main()
