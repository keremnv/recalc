"""Warm/cold performance measurement for the iteration probe.

Arms per workload: BASE (plain openpyxl), OFF (product with
RECALC_NO_ITERATION_PROBE=1 — the rc3-behavior control), ON (probe).
Warm: one warmup build (discarded) + N timed reps on a REUSED artifact.
Cold: fresh cache per run (target subset only).
Results -> PERFORMANCE_RESULTS.jsonl (committed) + _staging rows.
"""
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
CENSUS = HERE.parent / "execution_surface_census"
STAGE = HERE / "_staging" / "perf"
sys.path.insert(0, str(CENSUS))
import stage as stager  # noqa: E402

WARM_REPS = 3
TIMEOUT_S = 600


def run(cmd, cwd, env, timeout=TIMEOUT_S):
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           timeout=timeout)
        return {"exit": p.returncode, "out": p.stdout, "err": p.stderr,
                "wall": time.perf_counter() - t, "timeout": False}
    except subprocess.TimeoutExpired as e:
        return {"exit": None, "out": e.stdout or b"", "err": e.stderr or b"",
                "wall": time.perf_counter() - t, "timeout": True}


def prod_run(workdir, script, cache_dir, tag, extra_env=None):
    cfg = Path(workdir) / ("rt_%s.toml" % tag)
    cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache_dir)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, "-m", "recalc_agent", "run", "--config", str(cfg),
           "--workdir", str(workdir), str(Path(workdir) / script)]
    return run(cmd, cwd=workdir, env=env)


def receipt(cache_dir):
    try:
        ptr = json.loads((Path(cache_dir) / "runs" / "last_run.json").read_text())
        rd = Path(ptr["run_dir"])
        out = {}
        for name in ("setup.json", "runtime_state.json"):
            p = rd / name
            if p.exists():
                out[name] = json.loads(p.read_text())
        return out
    except (OSError, ValueError, KeyError):
        return {}


def measure_workload(wid, script_name, src_workdir, pops):
    import shutil
    rec = {"workload": wid, "populations": pops, "arms": {}}
    # BASE: fresh stage per rep (read-only workloads, but keep discipline).
    base_walls = []
    for rep in range(WARM_REPS):
        wd = STAGE / "warm" / wid / f"base_{rep}"
        if wd.exists():
            shutil.rmtree(wd)
        shutil.copytree(src_workdir, wd)
        r = run([sys.executable, script_name], cwd=wd, env=dict(os.environ))
        base_walls.append(r["wall"])
        if rep == 0:
            rec["base_exit"] = r["exit"]
            rec["base_stdout_bytes"] = len(r["out"])
    rec["arms"]["BASE"] = {"wall_s": [round(x, 4) for x in base_walls]}
    for arm, extra in (("OFF", {"RECALC_NO_ITERATION_PROBE": "1"}),
                       ("ON", {})):
        cache = STAGE / "warm" / wid / f"cache_{arm.lower()}"
        if cache.exists():
            shutil.rmtree(cache)
        cache.mkdir(parents=True)
        # Warmup (discarded timing, builds artifact).
        wd0 = STAGE / "warm" / wid / f"{arm.lower()}_warmup"
        if wd0.exists():
            shutil.rmtree(wd0)
        shutil.copytree(src_workdir, wd0)
        prod_run(wd0, script_name, cache, "wu", extra)
        walls, routes, statuses, counts, times, exits, outs = [], [], [], [], [], [], []
        for rep in range(WARM_REPS):
            wd = STAGE / "warm" / wid / f"{arm.lower()}_{rep}"
            if wd.exists():
                shutil.rmtree(wd)
            shutil.copytree(src_workdir, wd)
            r = prod_run(wd, script_name, cache, f"{arm.lower()}{rep}", extra)
            walls.append(r["wall"])
            exits.append(r["exit"])
            outs.append(len(r["out"]))
            rc = receipt(cache)
            st = rc.get("setup.json", {})
            rt = rc.get("runtime_state.json", {})
            routes.append(rt.get("route") or st.get("route"))
            arts = st.get("artifacts") or {}
            statuses.append(sorted({e.get("status") for e in arts.values()
                                    if isinstance(e, dict)}))
            counts.append(rt.get("counts", {}))
            times.append(rt.get("times", {}))
        rec["arms"][arm] = {"wall_s": [round(x, 4) for x in walls],
                            "exits": exits, "routes": routes,
                            "artifact_status": statuses, "counts": counts,
                            "times": times}
    return rec


def cold_check(wid, script_name, src_workdir):
    import shutil
    rec = {"workload": wid}
    for arm, extra in (("OFF", {"RECALC_NO_ITERATION_PROBE": "1"}),
                       ("ON", {})):
        walls = []
        for rep in range(2):
            wd = STAGE / "cold" / wid / f"{arm.lower()}_{rep}"
            if wd.exists():
                shutil.rmtree(wd)
            shutil.copytree(src_workdir, wd)
            cache = STAGE / "cold" / wid / f"cache_{arm.lower()}_{rep}"
            if cache.exists():
                shutil.rmtree(cache)
            cache.mkdir(parents=True)
            r = prod_run(wd, script_name, cache, "c", extra)
            walls.append(r["wall"])
        rec[arm] = [round(x, 4) for x in walls]
    return rec


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pops", default="A,B")
    ap.add_argument("--cold", action="store_true")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    man = json.loads((CENSUS / "WORKLOAD_MANIFEST.json").read_text())
    targets = set(json.loads((HERE / "TARGET_WORKLOADS.json").read_text())["workloads"])
    wid_pops = {}
    for pp in ("A", "B"):
        for x in man["populations"][pp]["workloads"]:
            wid_pops.setdefault(x["workload_id"], []).append(pp)
    clean = CENSUS / "_staging" / "staged" / "clean"
    jobs = []
    seen = set()
    for pop in args.pops.split(","):
        for w in man["populations"][pop]["workloads"]:
            wid = w["workload_id"]
            if wid in seen:
                continue
            seen.add(wid)
            jobs.append((wid, pop, clean / pop / wid))
    if args.only:
        keep = set(args.only.split(","))
        jobs = [j for j in jobs if j[0] in keep]
    out = HERE / ("PERFORMANCE_RESULTS.jsonl" if not args.cold
                  else "_staging/cold_results.jsonl")
    mode = "a" if out.exists() and args.only else "w"
    with open(out, mode) as f:
        for wid, pop, src in jobs:
            if args.cold and wid not in targets:
                continue
            if args.cold:
                rec = cold_check(wid, "workload.py", src)
                rec["population"] = pop
            else:
                rec = measure_workload(wid, "workload.py", src,
                                       sorted(wid_pops[wid]))
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            a = rec["arms"]["BASE"]["wall_s"] if not args.cold else None
            print(wid, (("base=%.2f" % statistics.median(a)) if a else rec),
                  flush=True)


if __name__ == "__main__":
    main()
