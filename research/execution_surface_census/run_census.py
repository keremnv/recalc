"""Census runner: stage workloads, run arms, collect telemetry.

Arms: BASE (plain python), HOOK (I1 census shim), PROD (recalc-agent run),
HOOKPROD (I1 chained under product, for gate G3).
Raw rows -> _staging/telemetry/*.jsonl (gitignored). Compact committed
ledgers are produced by aggregate.py.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
HOOKDIR = HERE / "census_hook"
TELEMETRY = HERE / "_staging" / "telemetry"
STAGE_ROOT = HERE / "_staging" / "staged"

sys.path.insert(0, str(HERE))
import stage as stager  # noqa: E402

TIMEOUT_S = 300


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


_ADDR = re.compile(rb"0x[0-9a-fA-F]+")


def norm_addr(b):
    """Mask memory addresses (object reprs) for determinism comparison."""
    return _ADDR.sub(b"0xADDR", b)


def workdir_state(d):
    out = {}
    for p in sorted(Path(d).rglob("*.xlsx")):
        try:
            out[str(p.relative_to(d))] = sha_bytes(p.read_bytes())
        except OSError:
            out[str(p.relative_to(d))] = "UNREADABLE"
    return out


def run(cmd, cwd, env, timeout=TIMEOUT_S):
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           timeout=timeout)
        dt = time.perf_counter() - t
        return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
                "wall_s": dt, "timeout": False}
    except subprocess.TimeoutExpired as e:
        dt = time.perf_counter() - t
        return {"exit": None, "stdout": e.stdout or b"", "stderr": e.stderr or b"",
                "wall_s": dt, "timeout": True}


def prod_env(cache_dir, extra_hook=False):
    env = dict(os.environ)
    pp = [str(ROOT / "src")]
    if extra_hook:
        pp.append(str(HOOKDIR))
        env["RECALC_CENSUS"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        pp + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env.pop("RECALC_CONFIG", None)
    env.pop("RECALC_NO_RUNTIME", None)
    return env, cache_dir


def run_prod(workdir, script_name, cache_dir, tag):
    cfg = Path(workdir) / ("runtime_%s.toml" % tag)
    cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache_dir)
    env, _ = prod_env(cache_dir)
    cmd = [sys.executable, "-m", "recalc_agent", "run", "--config", str(cfg),
           "--workdir", str(workdir), str(Path(workdir) / script_name)]
    return run(cmd, cwd=workdir, env=env), cfg


def read_receipt(cache_dir):
    last = Path(cache_dir) / "runs" / "last_run.json"
    try:
        ptr = json.loads(last.read_text())
        rd = Path(ptr["run_dir"])
        out = {}
        for name in ("observer_receipt.json", "setup.json", "runtime_state.json",
                     "capture_state.json", "bootstrap_failure.json"):
            p = rd / name
            if p.exists():
                try:
                    out[name] = json.loads(p.read_text())
                except ValueError:
                    out[name] = "UNPARSEABLE"
        out["_run_dir"] = str(rd)
        return out
    except (OSError, ValueError, KeyError):
        return {}


def run_one(wid, kind, script_name, workdir, cache_base, reps, arms):
    rows = []
    for rep in range(reps):
        for arm in arms:
            # Fresh stage per invocation (workbooks may be mutated).
            run_dir = STAGE_ROOT / kind / wid / ("rep%d_%s" % (rep, arm))
            if run_dir.exists():
                shutil.rmtree(run_dir)
            shutil.copytree(workdir, run_dir)
            env = dict(os.environ)
            census_out = run_dir / "census_out.json"
            cache_dir = cache_base / kind / wid / ("rep%d_%s" % (rep, arm))
            cache_dir.mkdir(parents=True, exist_ok=True)
            receipt = {}
            if arm == "BASE":
                r = run([sys.executable, script_name], cwd=run_dir, env=env)
            elif arm == "HOOK":
                env["PYTHONPATH"] = os.pathsep.join(
                    [str(HOOKDIR)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
                env["RECALC_CENSUS"] = "1"
                env["RECALC_CENSUS_OUT"] = str(census_out)
                r = run([sys.executable, script_name], cwd=run_dir, env=env)
            elif arm in ("PROD", "HOOKPROD"):
                if arm == "HOOKPROD":
                    os.environ["RECALC_CENSUS"] = "1"
                    os.environ["RECALC_CENSUS_OUT"] = str(census_out)
                else:
                    os.environ.pop("RECALC_CENSUS", None)
                    os.environ.pop("RECALC_CENSUS_OUT", None)
                # Chain hook dir through the product bootstrap environment.
                if arm == "HOOKPROD":
                    old_pp = os.environ.get("PYTHONPATH", "")
                    os.environ["PYTHONPATH"] = os.pathsep.join(
                        [x for x in [str(HOOKDIR), old_pp] if x])
                try:
                    r, _ = run_prod(run_dir, script_name, cache_dir, arm.lower())
                finally:
                    if arm == "HOOKPROD":
                        if old_pp:
                            os.environ["PYTHONPATH"] = old_pp
                        else:
                            os.environ.pop("PYTHONPATH", None)
                    os.environ.pop("RECALC_CENSUS", None)
                    os.environ.pop("RECALC_CENSUS_OUT", None)
                receipt = read_receipt(cache_dir)
            census = {}
            if census_out.exists():
                try:
                    census = json.loads(census_out.read_text())
                except ValueError:
                    census = {"unparseable": True}
            rows.append({
                "workload": wid, "kind": kind, "arm": arm, "rep": rep,
                "exit": r["exit"], "timeout": r["timeout"], "wall_s": r["wall_s"],
                "stdout_sha256": sha_bytes(r["stdout"]),
                "stdout_norm_sha256": sha_bytes(norm_addr(r["stdout"])),
                "stdout_bytes": len(r["stdout"]),
                "stderr_sha256": sha_bytes(r["stderr"]),
                "stderr_bytes": len(r["stderr"]),
                "state": workdir_state(run_dir),
                "census": census,
                "receipt": {k: receipt.get(k) for k in
                            ("observer_receipt.json", "setup.json",
                             "runtime_state.json", "capture_state.json")
                            if k in receipt},
                "bootstrap_failure": "bootstrap_failure.json" in receipt,
            })
    return rows


def append_rows(rows, name):
    TELEMETRY.mkdir(parents=True, exist_ok=True)
    with open(TELEMETRY / name, "a") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", choices=["A", "B", "C"], required=True)
    ap.add_argument("--arms", default="BASE,HOOK,PROD,HOOKPROD")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--only", default=None)
    ap.add_argument("--telemetry", default="runs.jsonl")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    man = json.loads((HERE / "WORKLOAD_MANIFEST.json").read_text())
    rc_man = json.loads((HERE / "_staging" / "rc_acceleration_validation"
                         / "workload_manifest.json").read_text())
    cands = {c["workload_id"]: c for c in rc_man["all_candidates"]}
    index = stager.workbook_index() if args.pop == "C" else None
    execs = {}
    if args.pop == "C":
        with open(ROOT / "research" / "history" / "control_python_audit"
                  / "python_executions.jsonl") as f:
            for line in f:
                r = json.loads(line)
                execs[r["exec_id"]] = r

    workloads = man["populations"][args.pop]["workloads"]
    if args.only:
        keep = set(args.only.split(","))
        workloads = [w for w in workloads
                     if w.get("workload_id", str(w.get("exec_id"))) in keep]
    if args.limit:
        workloads = workloads[:args.limit]
    cache_base = HERE / "_staging" / "cache"
    staging_log = []
    for w in workloads:
        if args.pop in ("A", "B"):
            wid = w["workload_id"]
            c = cands[wid]
            wd = STAGE_ROOT / "clean" / args.pop / wid
            if wd.exists():
                shutil.rmtree(wd)
            rec = stager.stage_ab(wid, w["script_sha256"], c["workbook_path"], wd)
            rows = run_one(wid, args.pop, "workload.py", wd, cache_base,
                           args.reps, args.arms.split(","))
        else:
            wid = "C_%d" % w["exec_id"]
            wd = STAGE_ROOT / "clean" / "C" / wid
            if wd.exists():
                shutil.rmtree(wd)
            rec = stager.stage_c(execs[w["exec_id"]]["source"], wd, index)
            if rec["workbooks_missing"]:
                staging_log.append({"workload": wid, "status": "STATIC_ONLY",
                                    "missing": rec["workbooks_missing"]})
                continue
            staging_log.append({"workload": wid, "status": "STAGED",
                                "workbooks": [x["basename"] for x in
                                              rec["workbooks_staged"]]})
            rows = run_one(wid, "C", "script.py", wd, cache_base,
                           args.reps, args.arms.split(","))
        append_rows(rows, args.telemetry)
        n_ok = sum(1 for r in rows if r["exit"] == 0)
        print("%s: %d/%d exit-0" % (wid, n_ok, len(rows)), flush=True)
    if staging_log:
        append_rows(staging_log, "staging_c.jsonl")
        n_static = sum(1 for s in staging_log if s["status"] == "STATIC_ONLY")
        print("C static-only: %d/%d" % (n_static, len(staging_log)))
