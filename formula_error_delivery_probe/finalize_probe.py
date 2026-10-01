#!/usr/bin/env python3
"""Post-inference artifact collation. No model calls or workbook recalculation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "formula_error_delivery_probe"


def read(path: Path):
    return json.loads(path.read_text())


def put(name: str, value) -> None:
    (EXP / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def jsonl(name: str, rows: list[dict]) -> None:
    (EXP / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    spec_hash = read(EXP / "spec_hash.json")
    frozen_ok = {p: (sha(ROOT / p) == digest) for p, digest in spec_hash["files"].items()}
    if not all(frozen_ok.values()):
        raise RuntimeError(f"frozen hash mismatch: {[p for p, ok in frozen_ok.items() if not ok]}")
    order = read(EXP / "run_order.json")["slots"]
    tasks = read(EXP / "population.json")["selected_tasks"]
    all_names = [s["run_dir"].split("/")[-1] for s in order] + ["Debugging_02_03_TREATMENT_R1"]
    records = []
    classes = {}
    for name in all_names:
        folder = EXP / "runs" / name
        d = read(folder / "run_record.json")
        raw = d["status"]
        output = bool(d["output_produced"])
        if raw == "SUBMITTED" and output:
            cls, reason = "VALID_SUBMISSION", "submit invoked and output.xlsx exists"
        elif raw == "PROVIDER_ERROR":
            cls, reason = "PROVIDER_CENSORED", "provider errors after frozen retry limit"
        elif raw == "CENSORED_CAP":
            cls, reason = "RUNNER_CENSORED", "global experiment spend cap"
        else:
            cls = "MODEL_NONCOMPLETION"
            reason = "submit invoked without output.xlsx" if raw == "SUBMITTED" else raw
        classes[name] = {"class": cls, "runner_status": raw, "reason": reason,
                         "primary_or_replacement": "replacement" if name.endswith("_R1") else "primary"}
        report = read(folder / "treatment_report.json") if (folder / "treatment_report.json").exists() else None
        events = [json.loads(x) for x in (folder / "live_nfe_events.jsonl").read_text().splitlines() if x]
        rec = {"run_dir": name, "task_id": d["task_id"], "arm": d["arm"], "attempt": "R1" if name.endswith("_R1") else "primary",
               "class": cls, "runner_status": raw, "output_produced": output,
               "api_calls": d["efficiency"]["api_calls"], "provider_failures": d["efficiency"]["failures"],
               "provider_retries": d["efficiency"]["retries"], "save_events": events,
               "report_call": report["call"] if report else None,
               "timely_contact": bool(report and report["call"] <= 25 and report["calls_remaining"] >= 25),
               "final_nfe": read(folder / "final_nfe.json"),
               "run_record_path": str((folder / "run_record.json").relative_to(ROOT)),
               "transcript_full_path": str((folder / "transcript_full.jsonl").relative_to(ROOT))}
        records.append(rec)
    jsonl("run_records.jsonl", records)
    put("censoring.json", {"attempts": classes,
                           "counts": {c: sum(v["class"] == c for v in classes.values()) for c in ["VALID_SUBMISSION", "MODEL_NONCOMPLETION", "PROVIDER_CENSORED", "RUNNER_CENSORED", "WORKBOOK_INFRA_CENSORED", "OTHER"]}})

    # In each task, use a replacement only for an infrastructure-censored primary.
    by_name = {r["run_dir"]: r for r in records}
    contact_rows = []
    for task in tasks:
        tid = task.split(":")[1]
        primary = by_name[f"Debugging_{tid}_TREATMENT"]
        r1 = by_name.get(f"Debugging_{tid}_TREATMENT_R1")
        eff = r1 if r1 is not None and primary["class"] in ("PROVIDER_CENSORED", "RUNNER_CENSORED", "WORKBOOK_INFRA_CENSORED") else primary
        unresolved = eff["class"] in ("PROVIDER_CENSORED", "RUNNER_CENSORED", "WORKBOOK_INFRA_CENSORED")
        contact_rows.append({"task_id": task, "primary_run": primary["run_dir"],
                             "replacement_run": r1["run_dir"] if r1 else None,
                             "effective_run": eff["run_dir"], "effective_class": eff["class"],
                             "observed_nonempty_save": any((e.get("nfe_total") or 0) > 0 for e in eff["save_events"]),
                             "delivered": eff["report_call"] is not None,
                             "report_call": eff["report_call"],
                             "calls_remaining": 50 - eff["report_call"] if eff["report_call"] else None,
                             "timely_contact": eff["timely_contact"], "unresolved_due_to_infra": unresolved})
    put("contact_table.json", {"task_rows": contact_rows,
                               "observed_timely_contact": sum(x["timely_contact"] for x in contact_rows),
                               "maximum_timely_contact_if_censored_task_had_contact": sum(x["timely_contact"] or x["unresolved_due_to_infra"] for x in contact_rows),
                               "gate": ">=3/4"})

    # The two output save snapshots are exact byte copies of their respective input.
    mutations = []
    for r in records:
        folder = EXP / "runs" / r["run_dir"]
        inputs = EXP / "runs" / "Debugging" / r["run_dir"] / "input.xlsx"
        snaps = sorted((folder / "output_snapshots").glob("call_*.xlsx"))
        prior = None
        for snap in snaps:
            call = int(snap.stem.split("_")[1])
            source = prior or inputs
            is_copy = sha(source) == sha(snap)
            mutations.append({"run_dir": r["run_dir"], "call": call,
                              "output_path_created_or_bytes_changed": True,
                              "baseline": "prior output snapshot" if prior else "input.xlsx (first output creation)",
                              "baseline_sha256": sha(source), "output_sha256": sha(snap),
                              "byte_identical_to_baseline": is_copy,
                              "cell_content_edits": [] if is_copy else "see archived snapshot and full transcript",
                              "after_feedback": bool(r["report_call"] and call > r["report_call"]),
                              "snapshot_path": str(snap.relative_to(ROOT))})
            prior = snap
    jsonl("workbook_mutations.jsonl", mutations)

    # Full post-contact call ledger with an explicit, narrow evidence-use adjudication.
    actions = []
    for r in records:
        if r["report_call"] is None:
            continue
        folder = EXP / "runs" / r["run_dir"]
        report = read(folder / "treatment_report.json")
        call = 0
        for msg in (json.loads(x) for x in (folder / "transcript_full.jsonl").read_text().splitlines()):
            if msg.get("role") != "assistant" or not msg.get("tool_calls"):
                continue
            call += 1
            if call <= report["call"]:
                continue
            fn = msg["tool_calls"][0]["function"]
            args = json.loads(fn.get("arguments", "{}"))
            cmd = args.get("command")
            # For this sole contact, explicit named-sheet or data-table inspection is traceable.
            related = (r["run_dir"] == "Debugging_02_02_TREATMENT" and call in
                       {5, 9, 10, 16, 17, 20, 21, 22, 44, 45, 46, 47, 48})
            actions.append({"run_dir": r["run_dir"], "call": call, "tool": fn["name"],
                            "args": args if cmd is None else {"command": cmd},
                            "relevant_inspection": related,
                            "relevance_basis": "reported Berk-Hath sensitivity cells/data-table recalculation inspected" if related else None,
                            "output_xlsx_mutation": any(m["run_dir"] == r["run_dir"] and m["call"] == call for m in mutations),
                            "submitted": fn["name"] == "submit"})
    jsonl("post_contact_actions.jsonl", actions)

    # Preserve only scores for actual staged workbooks. Official missing-output zero rows are not outcomes.
    score_rows = []
    official = {arm: read(EXP / "score_staging" / arm / "official_eval.json") for arm in ("CONTROL", "TREATMENT")}
    for task in tasks:
        tid = task.split(":")[1]
        for arm in ("CONTROL", "TREATMENT"):
            primary = by_name[f"Debugging_{tid}_{arm}"]
            r1 = by_name.get(f"Debugging_{tid}_{arm}_R1")
            eff = r1 if r1 and primary["class"] in ("PROVIDER_CENSORED", "RUNNER_CENSORED", "WORKBOOK_INFRA_CENSORED") else primary
            erow = next(x for x in official[arm]["scores"] if str(x["id"]) == tid)
            has_workbook = bool(eff["output_produced"])
            score_rows.append({"task_id": task, "arm": arm, "effective_run": eff["run_dir"],
                               "class": eff["class"], "output_produced": has_workbook,
                               "official_modification": erow.get("modification_accuracy") if has_workbook else None,
                               "official_regression": erow.get("regression_accuracy") if has_workbook else None,
                               "official_accuracy": erow.get("accuracy") if has_workbook else None,
                               "official_error_message": erow.get("error_message") if has_workbook else None,
                               "valid_for_pair": eff["class"] == "VALID_SUBMISSION"})
    put("scores.json", {"scorer": "unmodified official evaluation.py after open_spreadsheet.py refresh",
                        "rows": score_rows, "raw_scorer_paths": ["score_staging/CONTROL/official_eval.json", "score_staging/TREATMENT/official_eval.json"]})
    pairs = []
    for task in tasks:
        c = next(x for x in score_rows if x["task_id"] == task and x["arm"] == "CONTROL")
        t = next(x for x in score_rows if x["task_id"] == task and x["arm"] == "TREATMENT")
        valid = c["valid_for_pair"] and t["valid_for_pair"]
        pairs.append({"task_id": task, "valid_pair": valid,
                      "control_modification": c["official_modification"] if valid else None,
                      "treatment_modification": t["official_modification"] if valid else None,
                      "modification_delta": t["official_modification"] - c["official_modification"] if valid else None,
                      "control_regression": c["official_regression"] if valid else None,
                      "treatment_regression": t["official_regression"] if valid else None,
                      "regression_delta": t["official_regression"] - c["official_regression"] if valid else None,
                      "reason_if_unpaired": None if valid else "one or both arms lacked a valid submitted output"})
    put("paired_scores.json", {"valid_pairs": sum(p["valid_pair"] for p in pairs), "pairs": pairs})

    contact = read(EXP / "contact_table.json")
    assert contact["observed_timely_contact"] == 1
    assert contact["maximum_timely_contact_if_censored_task_had_contact"] == 2
    put("decision.json", {"experiment": "ASSISTED_DELIVERY_TIMING_PROBE",
                          "verdict": "DELIVERY_TIMING_NOT_SUPPORTED",
                          "timely_contact_observed": "1/4",
                          "timely_contact_upper_bound_with_censored_task": "2/4",
                          "gate": ">=3/4", "gate_passed": False,
                          "reason": "Two fully observed treatment noncontacts (02_05, 01_03) make the gate unattainable even if doubly provider-censored 02_03 had contacted. Only 02_02 contacted, at call 4, via a byte-identical input-to-output copy; it inspected related evidence but never changed output after feedback.",
                          "traceable_evidence_use_observed": "1/1 contacted, inspection only; no relevant output edit",
                          "mechanical_error_reduction": "none; contacted 02_02 remained 30 to 30",
                          "paired_capability_outcomes": 0,
                          "regression_safety_assessable": False,
                          "single_next_action": "Close the unchanged assisted-delivery capability retry route; do not run a larger unchanged-mechanism benchmark. Any different trigger or report requires a newly preregistered mechanism and fresh discovery population."})

    manifest = {"experiment": "ASSISTED_DELIVERY_TIMING_PROBE",
                "frozen_spec_hashes_valid_after_last_run": all(frozen_ok.values()),
                "frozen_files": spec_hash["files"],
                "result_files": {}}
    for path in sorted(EXP.rglob("*")):
        if path.is_file() and path.name != "final_hash_manifest.json":
            manifest["result_files"][str(path.relative_to(ROOT))] = sha(path)
    put("final_hash_manifest.json", manifest)
    print("wrote final artifacts; attempts", len(records), "timely", contact["observed_timely_contact"], "pairs", sum(p["valid_pair"] for p in pairs))


if __name__ == "__main__":
    main()
