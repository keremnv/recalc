"""R4 fixed-tax microbench + memory census (run AFTER main scoring).

tax: empty/minimal scripts BASE vs PROD-WARM x10, importtime splits,
     admission timing, receipt/observer splits from fresh receipts.
memory: /usr/bin/time -v peak RSS, BASE vs PROD-WARM, 4-workload subset.
Writes FIXED_TAX_ANALYSIS.json / MEMORY_CENSUS.json.
"""
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
R1 = HERE.parent / "execution_surface_census"
CLEAN = R1 / "_staging" / "staged" / "clean"
WORK = HERE / "_staging" / "taxmem"

sys.path.insert(0, str(ROOT / "src"))


def med(xs):
    return statistics.median(xs) if xs else None


def stage(pop, wid, tag):
    dest = WORK / "runs" / pop / wid / tag
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(CLEAN / pop / wid, dest)
    return dest


def run(cmd, cwd, env):
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True)
    return p, time.perf_counter() - t


def prod_env():
    env = dict()
    import os
    env.update(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env.pop("RECALC_CONFIG", None)
    env.pop("RECALC_NO_RUNTIME", None)
    return env


def run_prod(workdir, cache_dir):
    cfg = Path(workdir) / "runtime_tax.toml"
    cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache_dir)
    script = next(Path(workdir).glob("*.py"))
    return run([sys.executable, "-m", "recalc_agent", "run", "--config",
                str(cfg), "--workdir", str(workdir), str(script)],
               cwd=workdir, env=prod_env())


def cmd_tax():
    import os
    WORK.mkdir(parents=True, exist_ok=True)
    out = {"reps": 10}
    # 1. Bare interpreter + openpyxl import splits.
    bare, imp = [], []
    for _ in range(10):
        _, dt = run([sys.executable, "-c", "pass"], cwd="/tmp", env=dict(os.environ))
        bare.append(dt)
        p, _ = run([sys.executable, "-X", "importtime", "-c", "import openpyxl"],
                   cwd="/tmp", env=dict(os.environ))
        total_us = 0
        for line in p.stderr.decode().splitlines():
            if "openpyxl" in line and "|" in line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                try:
                    total_us = max(total_us, int(parts[-2].strip()))
                except ValueError:
                    pass
        imp.append(total_us / 1e6 if total_us else None)
    out["python_bare_c_s_median"] = round(med(bare), 4)
    out["openpyxl_import_s_median"] = round(med([x for x in imp if x]), 4)
    # 2. Empty script BASE vs PROD.
    empty = WORK / "empty"
    if empty.exists():
        shutil.rmtree(empty)
    empty.mkdir(parents=True)
    (empty / "task.py").write_text("print('hi')\n")
    eb, ep = [], []
    cache = WORK / "cache_empty"
    if cache.exists():
        shutil.rmtree(cache)
    cache.mkdir(parents=True)
    for i in range(11):
        _, dt = run([sys.executable, "task.py"], cwd=empty, env=dict(os.environ))
        if i:
            eb.append(dt)
    ep = []
    for i in range(11):
        ed = WORK / ("emptyrun%d" % i)
        if ed.exists():
            shutil.rmtree(ed)
        shutil.copytree(empty, ed)
        p, dt = run_prod(ed, cache)
        assert p.returncode == 0, p
        if i:
            ep.append(dt)
    out["empty_base_s_median"] = round(med(eb), 4)
    out["empty_prod_s_median"] = round(med(ep), 4)
    out["empty_tax_s_median"] = round(med(ep) - med(eb), 4)
    # 3. Admission timing (static classify over A/B scripts x20).
    from recalc_agent._frozen import eligibility
    man = json.loads((R1 / "WORKLOAD_MANIFEST.json").read_text())
    srcs = []
    for pop in ("A", "B"):
        for w in man["populations"][pop]["workloads"]:
            srcs.append((CLEAN / pop / w["workload_id"] / "workload.py").read_text())
    t = time.perf_counter()
    for _ in range(20):
        for s in srcs:
            eligibility.classify(s)
    out["admission_s_per_script"] = (time.perf_counter() - t) / (20 * len(srcs))
    # 4. Observer/receipt splits from one fresh tiny PROD run receipt.
    last = cache / "runs" / "last_run.json"
    try:
        rd = Path(json.loads(last.read_text())["run_dir"])
        ob = json.loads((rd / "observer_receipt.json").read_text())
        out["observer_profile_ns"] = ob.get("profile_ns")
    except (OSError, ValueError, KeyError):
        out["observer_profile_ns"] = None
    with open(HERE / "FIXED_TAX_ANALYSIS.json", "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


MEMORY_SET = [
    ("A", "Debugging_10_10__c7eca76e6646"),   # large direct-iteration
    ("A", "Template_03_03__c76ea596b408"),    # small direct
    ("A", "Template_06_02__85fab8c95cea"),    # reference-only
    ("A", "Template_06_23__fc41ad37c48b"),    # direct-with-fallback
]


def cmd_memory():
    import os
    out = {"workloads": []}
    for pop, wid in MEMORY_SET:
        row = {"workload": wid, "population": pop}
        # BASE peak RSS
        d = stage(pop, wid, "mem_base")
        p = subprocess.run(["/usr/bin/time", "-v", sys.executable, "workload.py"],
                           cwd=d, env=dict(os.environ), capture_output=True,
                           text=True)
        rss = None
        for line in p.stderr.splitlines():
            if "Maximum resident set size" in line:
                rss = int(line.split(":")[1].strip().split()[0])
        row["base_rss_peak_kb"] = rss
        row["base_exit"] = p.returncode
        # PROD-WARM peak RSS (own cache, warmup first)
        cache = WORK / "cache_mem" / wid
        if cache.exists():
            shutil.rmtree(cache)
        cache.mkdir(parents=True)
        d = stage(pop, wid, "mem_warmup")
        run_prod(d, cache)
        d = stage(pop, wid, "mem_prod")
        cfg = d / "runtime_mem.toml"
        cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache)
        p = subprocess.run(["/usr/bin/time", "-v", sys.executable, "-m",
                            "recalc_agent", "run", "--config", str(cfg),
                            "--workdir", str(d), str(d / "workload.py")],
                           cwd=d, env=prod_env(), capture_output=True, text=True)
        rss = None
        for line in p.stderr.splitlines():
            if "Maximum resident set size" in line:
                rss = int(line.split(":")[1].strip().split()[0])
        row["prod_rss_peak_kb"] = rss
        row["prod_exit"] = p.returncode
        out["workloads"].append(row)
        print(wid, "base=%s prod=%s" % (row["base_rss_peak_kb"], row["prod_rss_peak_kb"]),
              flush=True)
    with open(HERE / "MEMORY_CENSUS.json", "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=["tax", "memory"], required=True)
    args = ap.parse_args()
    if args.step == "tax":
        cmd_tax()
    else:
        cmd_memory()
