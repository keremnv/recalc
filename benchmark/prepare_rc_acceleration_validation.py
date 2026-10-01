"""Control-only workload extraction and frozen RC acceleration preregistration."""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import os
import pathlib
import platform
import random
import re
import shlex
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "rc_acceleration_validation"
VENV = pathlib.Path("/tmp/librecalc-hygiene-rc-v55taghk/venv")
PY = VENV / "bin/python"
CLI = VENV / "bin/librecalc-agent"
WHEEL = ROOT / "product_hygiene/dist/librecalc_agent-0.2.0rc1-py3-none-any.whl"
SEED = 20261011


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(name: str, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def data_rows(path):
    with open(path) as stream:
        for line in stream:
            if line.strip():
                try:
                    yield json.loads(line)
                except ValueError:
                    pass


def verify_rc():
    manifest = json.loads((ROOT / "product_hygiene/rc_manifest.json").read_text())
    assert manifest["version"] == "0.2.0rc1"
    mapping = {name: sha((ROOT / name).read_bytes()) for name in manifest["source_sha256"]}
    assert mapping == manifest["source_sha256"], "RC source/config mismatch"
    source_hash = sha(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode())
    wheel_hash = sha(WHEEL.read_bytes())
    assert source_hash == "1aba31178faca5533c4a594cf1ee8bae2bf3668fcb5f7a9df65f84361f972aee"
    assert wheel_hash == "532e493f126087a45d86117343514a9a1cd0a4e0010af89bbd1be1b271d66b2e"
    probe = subprocess.run([str(PY), "-c", "import librecalc_agent; print(librecacl if False else librecalc_agent.__file__)"], capture_output=True, text=True, check=True)
    site = pathlib.Path(probe.stdout.strip()).parent.parent
    installed = {}
    with zipfile.ZipFile(WHEEL) as archive:
        for name in archive.namelist():
            if name.endswith("/") or ".dist-info/" in name:
                continue
            target = site / name
            if not target.is_file() or target.read_bytes() != archive.read(name):
                raise RuntimeError(f"Installed artifact differs from frozen wheel: {name}")
            installed[name] = sha(target.read_bytes())
    version = subprocess.run([str(CLI), "--version"], capture_output=True, text=True, check=True).stdout.strip()
    assert version == "0.2.0rc1"
    dump("rc_identity.json", {"version": version, "source_config_sha256": source_hash,
         "wheel_sha256": wheel_hash, "installed_package_file_count_identical_to_wheel": len(installed),
         "installed_prefix": str(VENV), "wheel": str(WHEEL), "source_manifest": "product_hygiene/rc_manifest.json"})


def dataset_map():
    out = {}
    base = ROOT / "benchmark-data/SpreadsheetBench-2/data"
    for family in ("Template", "Financial_Model", "Debugging"):
        for item in json.loads((base / family / "dataset.json").read_text()):
            out[f"{family}:{item['id']}"] = base / family / item["spreadsheet_path"]
    return out


def load_args(source: str):
    tree = ast.parse(source)
    args = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "load_workbook" and node.args:
            args.append(node.args[0].value if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) else None)
    return args


def normalize(source: str, original: str, basename: str):
    if original == basename:
        return source
    tree = ast.parse(source)
    target = next(node.args[0] for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "load_workbook" and node.args)
    segment = ast.get_source_segment(source, target)
    assert segment is not None
    return source.replace(segment, repr(basename), 1)


def extract():
    from librecalc_agent._frozen.eligibility import classify
    workbooks = dataset_map()
    census = {r["exec_id"]: r for r in data_rows(ROOT / "transparent_python_read_census/executions.jsonl")}
    candidates = {}

    def add(task, source, provenance, read_count=None, control_class=None):
        wb = workbooks.get(task)
        if wb is None or not wb.is_file() or not source or "openpyxl" not in source:
            return
        try:
            args = load_args(source)
        except SyntaxError:
            return
        if len(args) != 1 or args[0] is None or pathlib.Path(args[0]).name != wb.name and args[0] != "input.xlsx":
            return
        if re.search(r"\.save\s*\(|\.value\s*=|\._style\s*=|\bremove\s*\(", source):
            return
        if control_class and not control_class.startswith("READ_ONLY"):
            return
        standardized = normalize(source, args[0], "input.xlsx")
        decision = classify(standardized)["decision"]
        tree = ast.parse(standardized)
        static_reads = read_count if read_count is not None else sum(
            isinstance(n, ast.Attribute) and n.attr in {"load_workbook", "cell", "value", "iter_rows", "sheetnames", "max_row", "max_column", "dimensions"}
            for n in ast.walk(tree))
        key = (task, sha(standardized.encode()))
        row = {"workload_id": f"{task.replace(':','_')}__{sha(standardized.encode())[:12]}", "task": task,
               "family": task.split(":")[0], "source_sha256": sha(source.encode()),
               "script_sha256": sha(standardized.encode()), "source": standardized,
               "source_provenance": provenance, "original_load_argument": args[0],
               "workbook_path": str(wb.resolve()), "workbook_sha256": sha(wb.read_bytes()),
               "workbook_bytes": wb.stat().st_size, "static_read_events": static_reads,
               "a1_decision": decision, "control_read_class": control_class}
        candidates.setdefault(key, row)

    for r in data_rows(ROOT / "control_python_audit/python_executions.jsonl"):
        if r.get("has_source") and r["exec_id"] in census:
            c = census[r["exec_id"]]
            add(r["task_id"], r["source"], {"archive": "control_python_audit/python_executions.jsonl", "exec_id": r["exec_id"]},
                c.get("read_event_count"), c.get("read_write_classification"))
    archived_controls = (
        sorted((ROOT / "representative_architecture_checkpoint/reps").glob("*H0*/run_record.json"))
        + sorted((ROOT / "token_claim_discovery/runs/primary").glob("*_A/run_record.json"))
        + sorted((ROOT / "token_affordance_discovery/runs/primary").glob("*_A/run_record.json"))
    )
    for record_path in archived_controls:
        record = json.loads(record_path.read_text())
        task = record.get("task_id") or record.get("task")
        transcript = record_path.parent / "transcript_full.jsonl"
        for line_no, row in enumerate(data_rows(transcript), 1):
            for call in row.get("tool_calls") or []:
                if call.get("function", {}).get("name") != "bash":
                    continue
                try:
                    command = json.loads(call["function"]["arguments"])["command"]
                    tokens = shlex.split(command)
                except (ValueError, KeyError):
                    continue
                for i, token in enumerate(tokens[:-2]):
                    if token in {"python", "python3"} and tokens[i + 1] == "-c":
                        add(task, tokens[i + 2], {"archive": str(transcript.relative_to(ROOT)), "line": line_no})
    return list(candidates.values())


def preflight(rows):
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "LIBRECALC_RUN_CONTEXT"} and not k.startswith("CANDIDATE_A_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for row in rows:
        with tempfile.TemporaryDirectory(prefix="rc-control-preflight-") as tmp:
            work = pathlib.Path(tmp)
            (work / "input.xlsx").symlink_to(row["workbook_path"])
            (work / "workload.py").write_text(row["source"])
            try:
                result = subprocess.run([str(PY), str(work / "workload.py")], cwd=work,
                                        env=env, capture_output=True, timeout=30)
                row["control_preflight"] = {"exit_code": result.returncode,
                    "stdout_sha256": sha(result.stdout), "stdout_bytes": len(result.stdout),
                    "stderr_head": result.stderr.decode(errors="replace")[:300],
                    "usable": result.returncode == 0}
            except subprocess.TimeoutExpired:
                row["control_preflight"] = {"usable": False, "reason": "control_timeout_30s"}
    return rows


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT / "preregistered_spec.json").exists():
        raise RuntimeError("Study already frozen; preparation cannot be rerun")
    verify_rc()
    candidates = preflight(extract())
    usable = [r for r in candidates if r["control_preflight"]["usable"]]
    eligible = [r for r in usable if r["a1_decision"] == "A1_ADMIT" and r["static_read_events"] >= 5]
    rng = random.Random(SEED)
    # One frozen selection rule; cap at two scripts per underlying task to avoid one agent loop dominating.
    order = sorted(eligible, key=lambda r: (r["task"], r["script_sha256"]))
    rng.shuffle(order)
    per_task = collections.Counter()
    primary = []
    for row in order:
        if per_task[row["task"]] < 2:
            primary.append(row)
            per_task[row["task"]] += 1
    # Retain all qualifying distinct scripts under the cap; no post-timing threshold adjustment.
    representative = []
    for family in ("Template", "Financial_Model", "Debugging"):
        pool = sorted((r for r in usable if r["family"] == family), key=lambda r: r["script_sha256"])
        random.Random(SEED + len(representative)).shuffle(pool)
        used = collections.Counter()
        for row in pool:
            if used[row["task"]] < 2:
                representative.append(row)
                used[row["task"]] += 1
            if sum(r["family"] == family for r in representative) >= 10:
                break
    chosen = {r["workload_id"]: r for r in representative + primary}
    scripts = OUT / "workloads"
    scripts.mkdir(exist_ok=True)
    for row in chosen.values():
        (scripts / (row["workload_id"] + ".py")).write_text(row["source"])
    for row in candidates:
        row.pop("source")
    dump("workload_manifest.json", {"extraction": "Archived H0/control Python -c or recovered Python source; exactly one source-workbook load; read-only static filter; normalize workbook literal to input.xlsx; direct-Python success preflight; dedupe task+script hash.",
          "all_candidates": candidates, "usable_count": len(usable), "selected_ids": list(chosen)})
    dump("representative_population.json", {"label": "CONTROL_OBSERVED_TREATMENT_BLIND", "seed": SEED,
         "rule": "Seeded within-family sample of up to 10 usable control read scripts, max two per task; no eligibility requirement.",
         "workload_ids": [r["workload_id"] for r in representative]})
    dump("eligible_population.json", {"label": "A1_ADMITTED_READ_HEAVY_CONTROL_DEFINED", "seed": SEED,
         "rule": "Control-only: read-only source, exactly one source workbook load, control preflight success, packaged A1_ADMIT, >=5 static read API references; seeded order, max two scripts per task; retain all qualifying under cap. Workbook size is analyzed, not used for primary selection.",
         "workload_ids": [r["workload_id"] for r in primary], "distinct_tasks": len(set(r["task"] for r in primary))})
    dump("environment.json", {"platform": platform.platform(), "python": subprocess.run([str(PY), "--version"], capture_output=True, text=True).stdout.strip(),
         "venv": str(VENV), "openpyxl": subprocess.run([str(PY), "-c", "import openpyxl; print(openpyxl.__version__)"], capture_output=True, text=True).stdout.strip(),
         "machine": platform.node(), "parallel_benchmark_workers": 1})
    dump("control_command.json", {"argv_template": [str(PY), "{workdir}/workload.py"], "cwd": "{workdir}", "environment": "installed RC venv Python; XDG_CACHE_HOME fresh and PYTHONPATH cleared"})
    dump("treatment_command.json", {"argv_template": [str(CLI), "run", "--workdir", "{workdir}", "{workdir}/workload.py"], "cwd": "{workdir}", "environment": "shipped default runtime settings; XDG_CACHE_HOME fresh and PYTHONPATH cleared"})
    dump("timing_protocol.json", {"repetitions": 3, "warmup": "one unscored execution per arm on separate fresh cache", "order": "seeded AB/BA alternating per workload/repetition", "endpoint": "external perf_counter_ns subprocess invocation until process exit", "cache": "new XDG_CACHE_HOME per invocation, no reuse", "workbook_staging": "copy original workbook into invocation workdir before clock starts", "stdout": "capture exact bytes; compare control/treatment within workload", "timeout_seconds": 180})
    spec = {"scientific_question": "Does packaged RC 0.2.0rc1 accelerate admitted read-heavy control workloads after fresh per-invocation setup?",
        "identity_sha256": sha((OUT / "rc_identity.json").read_bytes()),
        "design_hashes": {name: sha((OUT / name).read_bytes()) for name in ("workload_manifest.json", "representative_population.json", "eligible_population.json", "environment.json", "control_command.json", "treatment_command.json", "timing_protocol.json")},
        "selected_eligible_ids": [r["workload_id"] for r in primary], "selected_representative_ids": [r["workload_id"] for r in representative],
        "endpoint": "TOTAL_PRODUCT_INVOCATION_WALL_TIME", "workload_statistic": "median of 3 scored external wall timings per arm", "bootstrap": "10000 workload resamples seed 20261011 of geometric mean ratio; cluster-by-task sensitivity descriptive",
        "exactness_gate": "0 unexplained stdout or exit-code mismatches in any scored pair; no silent workload exclusions",
        "performance_gate": "median eligible reduction >=10%; >half eligible faster; geometric bootstrap 95% upper bound <1; leave-two-largest-wins-out median still <1",
        "verdict_mapping": {"RC_ACCELERATION_CLAIM_SUPPORTED": "exactness and performance gates pass with actual contact >0", "RC_ACCELERATION_SUPPORTED_NARROWLY": "exactness passes, performance gate fails overall, but preregistered subset workbook>=1000000 bytes and static_read_events>=10 has median reduction>=10%, >half faster, and bootstrap upper<1", "RC_FASTPATH_ONLY_PRODUCT_SPEED_NOT_SUPPORTED": "exactness passes; acceleration contacts occur and per-operation telemetry shows faster reads but eligible total-invocation median reduction <10%", "NO_MATERIAL_RC_ACCELERATION": "exactness passes but no material eligible workload effect and no clear fast-path-only evidence", "EXPERIMENT_INCONCLUSIVE": "identity, measurement, or environment failure prevents valid paired endpoint"},
        "censoring": "No replacement after freeze; timeouts and process failures are reported, never counted as wins", "stop": "All selected workloads, 3 scored repetitions per arm; no outcome-driven rerun or RC change; research ends after verdict",
        "representative_role": "supporting descriptive view only", "lifecycle": "fresh per-invocation index/cache; packaged default capture included", "no_model_calls": True}
    dump("preregistered_spec.json", spec)
    dump("spec_hash.json", {"algorithm": "sha256", "sha256": sha((OUT / "preregistered_spec.json").read_bytes())})
    print(json.dumps({"candidates": len(candidates), "usable": len(usable), "representative": len(representative), "eligible": len(primary), "eligible_tasks": len(set(r["task"] for r in primary)), "spec_hash": sha((OUT / "preregistered_spec.json").read_bytes())}, indent=2))


if __name__ == "__main__":
    main()
