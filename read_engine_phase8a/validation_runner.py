"""Frozen Phase-8 full-command validation resumed only after Phase-8A gates."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import zipfile
from pathlib import Path

from read_engine_phase3 import benchmark as b3
from read_engine_phase6 import benchmark as b6
from read_engine_phase7 import benchmark as b7

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PHASE8 = ROOT / "read_engine_phase8"
OVERLAY = HERE / "overlay"
RUNS_ROOT = PHASE8 / "runs_resume_v2"
ARMS = ("PY", "H0", "H1")
FIXTURE_NAMES = ("existing_cell", "formula", "multi_cell", "new_sheet", "output_file")
FIXTURE_BOOK = ROOT / "benchmark-data/SpreadsheetBench-2/data/Template/spreadsheet/15_re_debt/15_03_input.xlsx"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append(path: Path, row: dict) -> None:
    with path.open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def verify() -> tuple[dict, list[dict]]:
    for name in ("PREREGISTERED_VALIDATION_SPEC", "PREREGISTERED_VALIDATION_SPEC_AMENDMENT_1"):
        recorded = (PHASE8 / f"{name}.sha256").read_text().split()[0]
        if sha(PHASE8 / f"{name}.md") != recorded:
            raise RuntimeError(f"Changed preregistration: {name}")
    pop = b7.verify()
    representative = json.loads((ROOT / "research/history/rc_acceleration_validation/representative_population.json").read_text())
    if len(pop["secondary_ids"]) != 30 or pop["secondary_ids"] != representative["workload_ids"]:
        raise RuntimeError("Representative population differs from frozen RC manifest")
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    for wid in pop["secondary_ids"]:
        row = by_id[wid]
        if sha(Path(row["script_path"])) != row["script_sha256"] or \
                sha(Path(row["source_workbook_path"])) != row["source_workbook_sha256"]:
            raise RuntimeError(f"Representative identity changed: {wid}")
    pins = json.loads((HERE / "implementation_identity_v2.json").read_text())
    for rel, digest in pins.items():
        if sha(ROOT / rel) != digest:
            raise RuntimeError(f"Phase-8A implementation changed: {rel}")
    changed = []
    book_hash = sha(FIXTURE_BOOK)
    for name in FIXTURE_NAMES:
        script = PHASE8 / "changed_file_fixtures" / f"{name}.py"
        changed.append({"workload_id": "phase8_changed_" + name, "task": "PHASE8_CHANGED",
                        "family": "ChangedFile", "script_path": str(script),
                        "script_sha256": sha(script), "source_workbook_path": str(FIXTURE_BOOK),
                        "source_workbook_sha256": book_hash,
                        "staged_workbook_sha256": book_hash})
    return pop, changed


def command(row: dict, arm: str, base: Path) -> dict:
    if arm == "PY":
        result = b6.command(row, "PY", base)
    else:
        original = b6.ROOT
        try:
            b6.ROOT = original if arm == "H0" else OVERLAY
            result = b6.command(row, "H2", base)
        finally:
            b6.ROOT = original
        last = base / "runs/last_run.json"
        if last.exists():
            run = Path(json.loads(last.read_text())["run_dir"])
            capture_profile = run / "capture_profile.json"
            result["capture_profile"] = json.loads(capture_profile.read_text()) if capture_profile.exists() else None
            capture_rows = run / "capture.json"
            result["capture_rows"] = json.loads(capture_rows.read_text()) if capture_rows.exists() else None
            setup = run / "setup.json"
            result["certificate"] = json.loads(setup.read_text()).get("merged_certificate") if setup.exists() else None
    result["workdir"] = str((base / "work").resolve())
    return result


def classification(result: dict) -> str:
    summary = result.get("summary") or {}
    direct = summary.get("direct_served_loads") or 0
    reasons = summary.get("reference_reasons") or []
    if direct:
        return "FALLBACK_AFTER_CONTACT" if reasons else "DIRECT_CONTACT"
    return "REFERENCE_ONLY" if reasons else "OTHER"


def statuses(result: dict) -> list[str]:
    return sorted(x.get("status") for x in (result.get("summary") or {}).get("artifacts", {}).values())


MODIFIED = re.compile(rb'(<dcterms:modified\b[^>]*>)(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)(</dcterms:modified>)')


def normalized_core(result: dict, rel: str) -> bytes | None:
    try:
        with zipfile.ZipFile(Path(result["workdir"]) / rel) as workbook:
            raw = workbook.read("docProps/core.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    if len(MODIFIED.findall(raw)) != 1:
        return None
    return MODIFIED.sub(rb'\g<1>VOLATILE_MODIFIED_TIME\g<3>', raw)


def package_relation(a: dict, b: dict) -> tuple[bool, list[str]]:
    x, y = a["files_after"], b["files_after"]
    if set(x) != set(y):
        return False, []
    volatile: list[str] = []
    for rel in x:
        if rel.endswith(".xlsx"):
            xp, yp = x[rel].get("package_parts"), y[rel].get("package_parts")
            if not isinstance(xp, dict) or not isinstance(yp, dict) or set(xp) != set(yp):
                return False, volatile
            for part in xp:
                if xp[part] == yp[part]:
                    continue
                if part != "docProps/core.xml" or normalized_core(a, rel) is None \
                        or normalized_core(a, rel) != normalized_core(b, rel):
                    return False, volatile
                volatile.append(rel + ":" + part)
        elif x[rel].get("sha256") != y[rel].get("sha256"):
            return False, volatile
    return True, volatile


def capture_ok(result: dict, *, changed: bool) -> bool:
    summary = result.get("summary") or {}
    receipt = summary.get("observer_receipt") or {}
    if receipt.get("capture_helper_exit") != 0 or summary.get("capture_failures") != 0:
        return False
    if changed:
        if receipt.get("changed_xlsx") != 1 or summary.get("capture_records") != 1:
            return False
        base = result.get("capture_profile") or {}
        rows = result.get("capture_rows") or []
        if base.get("failures") != 0 or base.get("records") != 1 or len(rows) != 1:
            return False
        if not all(row.get("validation_passed") is True and row.get("f1_part_exact") is True
                   and row.get("f2_state_exact") is True and row.get("runtime_failure") is False
                   for row in rows):
            return False
    return True


def correctness(row: dict, phase: str, rep: int, invocation: int,
                results: dict, *, changed: bool) -> bool:
    py, h0, h1 = (results[a] for a in ARMS)
    checks = {"PY_H0": b3.compare(py, h0), "PY_H1": b3.compare(py, h1),
              "H0_H1": b3.compare(h0, h1)}
    allowed = {"EXACT", "VOLATILE_ONLY_DIFFERENCE"}
    if changed:
        relations = {a: package_relation(py, results[a]) for a in ("H0", "H1")}
        output_ok = all(v[0] for v in relations.values())
        volatile_package_parts = sorted({part for v in relations.values() for part in v[1]})
        label = "CHANGED_FILE"
        expected = []
        witness = all(statuses(results[a]) == expected for a in ("H0", "H1"))
        expected_rel = "output.xlsx" if row["workload_id"].endswith("output_file") else "input.xlsx"
        effects_ok = all([x.get("rel") for x in (results[a].get("capture_rows") or [])] == [expected_rel]
                         for a in ("H0", "H1"))
        semantic_ok = all(results[a]["exit_code"] == 0 and not results[a]["timed_out"] for a in ARMS) \
            and all((py["stdout"], py["stderr"]) == (results[a]["stdout"], results[a]["stderr"])
                    for a in ("H0", "H1"))
        valid = (output_ok and witness and effects_ok and semantic_ok
                 and all(capture_ok(results[a], changed=True) for a in ("H0", "H1")))
    else:
        volatile_package_parts = []
        output_ok = all(c["classification"] in allowed for c in checks.values())
        label = "COLD" if invocation == 1 else "SECOND_INVOCATION"
        c0, c1 = classification(h0), classification(h1)
        expected = ["BUILT"] if invocation == 1 else ["REUSED"]
        witness = (c0 == c1 and (statuses(h0) == statuses(h1) == expected if
                    c0 in {"DIRECT_CONTACT", "FALLBACK_AFTER_CONTACT"} else
                    statuses(h0) == statuses(h1) == []))
        if invocation > 1 and c1 in {"DIRECT_CONTACT", "FALLBACK_AFTER_CONTACT"}:
            label = "VALID_REUSE"
        valid = (output_ok and witness and all(results[a]["exit_code"] == 0 and not results[a]["timed_out"]
                                           for a in ARMS)
                 and all(capture_ok(results[a], changed=False) for a in ("H0", "H1")))
    record = {"workload_id": row["workload_id"], "phase": phase, "rep": rep,
              "invocation": invocation, "label": label, "changed_file": changed,
              "checks": checks, "output_state_ok": output_ok, "witness_ok": witness,
              "volatile_package_parts": volatile_package_parts,
              "effects_ok": effects_ok if changed else None,
              "H0_class": classification(h0), "H1_class": classification(h1),
              "H0_statuses": statuses(h0), "H1_statuses": statuses(h1),
              "H0_capture_ok": capture_ok(h0, changed=changed),
              "H1_capture_ok": capture_ok(h1, changed=changed), "valid": valid}
    append(PHASE8 / ("changed_file_correctness.jsonl" if changed else "representative_correctness.jsonl"), record)
    return valid


def persist(row: dict, phase: str, rep: int, invocation: int,
            arm: str, result: dict, *, changed: bool) -> None:
    keep = {k: v for k, v in result.items() if k not in {"events", "stdout", "stderr"}}
    append(PHASE8 / ("changed_file_timings.jsonl" if changed else "representative_timings.jsonl"),
           {"workload_id": row["workload_id"], "task": row["task"], "family": row["family"],
            "phase": phase, "rep": rep, "invocation": invocation, "arm": arm,
            "contact_class": classification(result) if arm != "PY" else None,
            "artifact_statuses": statuses(result) if arm != "PY" else [], **keep})


def gate() -> None:
    pop, changed = verify()
    if (PHASE8 / "validation_gate_pass.json").exists():
        raise RuntimeError("Gate already completed")
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    for pos, wid in enumerate(pop["secondary_ids"], 1):
        row = by_id[wid]
        base = RUNS_ROOT / "gate/representative" / wid
        for invocation in (1, 2):
            results = {arm: command(row, arm, base / arm.lower()) for arm in ARMS}
            for arm in ARMS:
                persist(row, "gate", 0, invocation, arm, results[arm], changed=False)
            if not correctness(row, "gate", 0, invocation, results, changed=False):
                raise RuntimeError(f"Representative correctness gate failed: {wid} {invocation}")
        print(f"representative gate {pos}/30 {wid}", flush=True)
    for pos, row in enumerate(changed, 1):
        base = RUNS_ROOT / "gate/changed" / row["workload_id"]
        results = {arm: command(row, arm, base / arm.lower()) for arm in ARMS}
        for arm in ARMS:
            persist(row, "gate", 0, 1, arm, results[arm], changed=True)
        if not correctness(row, "gate", 0, 1, results, changed=True):
            raise RuntimeError(f"Changed-file correctness gate failed: {row['workload_id']}")
        print(f"changed-file gate {pos}/5 {row['workload_id']}", flush=True)
    abrupt = []
    for name, expected_code in (("exit_after_save", 7), ("signal_after_save", -15)):
        script = HERE / "abrupt_fixtures" / f"{name}.py"
        book_hash = sha(FIXTURE_BOOK)
        row = {"workload_id": name, "task": "PHASE8_ABRUPT", "family": "ChangedFile",
               "script_path": str(script), "script_sha256": sha(script),
               "source_workbook_path": str(FIXTURE_BOOK), "source_workbook_sha256": book_hash,
               "staged_workbook_sha256": book_hash}
        result = command(row, "H1", RUNS_ROOT / "gate/abrupt" / name)
        receipt = (result.get("summary") or {}).get("observer_receipt") or {}
        passed = (result["exit_code"] == expected_code and capture_ok(result, changed=True)
                  and receipt.get("target_signal") == (15 if expected_code < 0 else 0))
        item = {"case": name, "exit_code": result["exit_code"], "receipt": receipt,
                "capture_profile": result.get("capture_profile"), "passed": passed}
        append(PHASE8 / "abrupt_exit.jsonl", item)
        abrupt.append(item)
        if not passed:
            raise RuntimeError(f"Abrupt changed-file assurance failed: {name}")
    (PHASE8 / "validation_gate_pass.json").write_text(json.dumps(
        {"representative_ids": pop["secondary_ids"], "changed_ids": [x["workload_id"] for x in changed],
         "abrupt_cases": [x["case"] for x in abrupt], "status": "PASSED"}, indent=2) + "\n")


def score() -> None:
    pop, changed = verify()
    gate_path = PHASE8 / "validation_gate_pass.json"
    if not gate_path.exists() or json.loads(gate_path.read_text()).get("status") != "PASSED":
        raise RuntimeError("Correctness gate absent")
    if any(json.loads(x).get("phase") == "scored" for x in
           (PHASE8 / "representative_timings.jsonl").read_text().splitlines()):
        raise RuntimeError("Scored rows already exist")
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    ids = list(pop["secondary_ids"])
    random.Random(20260927).shuffle(ids)
    for pos, wid in enumerate(ids, 1):
        row = by_id[wid]
        for arm in ARMS:
            command(row, arm, RUNS_ROOT / "warmup/representative" / wid / arm.lower())
        for rep in range(1, 4):
            base = RUNS_ROOT / "scored/representative" / wid / f"rep-{rep}"
            totals = {arm: 0 for arm in ARMS}
            for invocation in range(1, 6):
                shift = (pos + rep + invocation) % len(ARMS)
                ordered = ARMS[shift:] + ARMS[:shift]
                results = {}
                for arm in ordered:
                    results[arm] = command(row, arm, base / arm.lower())
                    totals[arm] += results[arm]["wall_ns"]
                    persist(row, "scored", rep, invocation, arm, results[arm], changed=False)
                if not correctness(row, "scored", rep, invocation, results, changed=False):
                    raise RuntimeError(f"Scored representative correctness failure: {wid} {rep} {invocation}")
                if invocation in (1, 2, 3, 5):
                    append(PHASE8 / "session_timings.jsonl",
                           {"workload_id": wid, "rep": rep, "N": invocation,
                            "PY_ns": totals["PY"], "H0_ns": totals["H0"], "H1_ns": totals["H1"],
                            "H1_class": classification(results["H1"]),
                            "H1_valid_reuse": invocation == 1 or statuses(results["H1"]) == ["REUSED"]})
        print(f"representative scored {pos}/30 {wid}", flush=True)
    for pos, row in enumerate(changed, 1):
        wid = row["workload_id"]
        for rep in range(1, 4):
            base = RUNS_ROOT / "scored/changed" / wid / f"rep-{rep}"
            shift = (pos + rep) % len(ARMS)
            ordered = ARMS[shift:] + ARMS[:shift]
            results = {}
            for arm in ordered:
                results[arm] = command(row, arm, base / arm.lower())
                persist(row, "scored", rep, 1, arm, results[arm], changed=True)
            if not correctness(row, "scored", rep, 1, results, changed=True):
                raise RuntimeError(f"Scored changed-file correctness failure: {wid} {rep}")
        print(f"changed-file scored {pos}/5 {wid}", flush=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in {"gate", "score"}:
        raise SystemExit("usage: python -m read_engine_phase8a.validation_runner gate|score")
    (gate if sys.argv[1] == "gate" else score)()
