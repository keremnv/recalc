"""R4 residual census runner: BASE/HOOK/PROD-WARM/PROD-COLD arms on rc4.

Reuses R1 staging + manifest + census hook (frozen); telemetry goes to
R4 _staging (gitignored). One line per run in telemetry/runs.jsonl.
Static classifier scan (--scan) needs no execution.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
R1 = HERE.parent / "execution_surface_census"
HOOKDIR = R1 / "census_hook"
TELEMETRY = HERE / "_staging" / "telemetry"
CLEAN = R1 / "_staging" / "staged" / "clean"
CACHE_BASE = HERE / "_staging" / "cache"

sys.path.insert(0, str(ROOT / "src"))

TIMEOUT_S = 300


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, cwd, env, timeout=TIMEOUT_S):
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           timeout=timeout)
        return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
                "wall_s": time.perf_counter() - t, "timeout": False}
    except subprocess.TimeoutExpired as e:
        return {"exit": None, "stdout": e.stdout or b"",
                "stderr": e.stderr or b"", "wall_s": time.perf_counter() - t,
                "timeout": True}


_ADDR_RE = None


def norm_addr(b):
    global _ADDR_RE
    import re
    if _ADDR_RE is None:
        _ADDR_RE = re.compile(rb"0x[0-9a-fA-F]+")
    return _ADDR_RE.sub(b"0xADDR", b)


def workdir_state(d):
    out = {}
    for p in sorted(Path(d).rglob("*.xlsx")):
        try:
            out[str(p.relative_to(d))] = sha_file(p)
        except OSError:
            out[str(p.relative_to(d))] = "UNREADABLE"
    return out


def verify_stage(pop, wid, script_sha, workbook_sha):
    d = CLEAN / pop / wid
    script = d / "workload.py"
    if not script.exists():
        return False, "missing script"
    if sha_file(script) != script_sha:
        return False, "script sha mismatch"
    books = sorted(d.glob("*.xlsx"))
    if not books:
        return False, "no workbook"
    for b in books:
        if sha_file(b) == workbook_sha:
            return True, ""
    return False, "workbook sha mismatch"


def stage_run(pop, wid, tag):
    dest = HERE / "_staging" / "runs" / pop / wid / tag
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(CLEAN / pop / wid, dest)
    return dest


def prod_env(cache_dir):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env.pop("RECALC_CONFIG", None)
    env.pop("RECALC_NO_RUNTIME", None)
    return env


def run_prod(workdir, cache_dir, tag):
    cfg = Path(workdir) / ("runtime_%s.toml" % tag)
    cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache_dir)
    env = prod_env(cache_dir)
    cmd = [sys.executable, "-m", "recalc_agent", "run", "--config", str(cfg),
           "--workdir", str(workdir), str(Path(workdir) / "workload.py")]
    return run(cmd, cwd=workdir, env=env)


def read_receipt(cache_dir):
    last = Path(cache_dir) / "runs" / "last_run.json"
    try:
        rd = Path(json.loads(last.read_text())["run_dir"])
    except (OSError, ValueError, KeyError):
        return {}
    out = {}
    for name in ("observer_receipt.json", "setup.json", "runtime_state.json",
                 "capture_state.json"):
        p = rd / name
        if p.exists():
            try:
                out[name] = json.loads(p.read_text())
            except ValueError:
                out[name] = "UNPARSEABLE"
    return out


def one_run(pop, wid, arm, tag, cache_dir=None, hook=False):
    rd = stage_run(pop, wid, tag)
    env = dict(os.environ)
    census_out = rd / "census_out.json"
    receipt = {}
    if arm == "BASE":
        r = run([sys.executable, "workload.py"], cwd=rd, env=env)
    elif arm == "HOOK":
        env["PYTHONPATH"] = os.pathsep.join(
            [str(HOOKDIR)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        env["RECALC_CENSUS"] = "1"
        env["RECALC_CENSUS_OUT"] = str(census_out)
        r = run([sys.executable, "workload.py"], cwd=rd, env=env)
    else:  # PROD
        if hook:
            env["PYTHONPATH"] = os.pathsep.join(
                [str(HOOKDIR)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
            env["RECALC_CENSUS"] = "1"
            env["RECALC_CENSUS_OUT"] = str(census_out)
            old = (os.environ.get("PYTHONPATH"), os.environ.get("RECALC_CENSUS"),
                   os.environ.get("RECALC_CENSUS_OUT"))
            os.environ["PYTHONPATH"] = env["PYTHONPATH"]
            os.environ["RECALC_CENSUS"] = "1"
            os.environ["RECALC_CENSUS_OUT"] = str(census_out)
            try:
                r = run_prod(rd, cache_dir, tag)
            finally:
                for k, v in zip(("PYTHONPATH", "RECALC_CENSUS", "RECALC_CENSUS_OUT"), old):
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
        else:
            for k in ("RECALC_CENSUS", "RECALC_CENSUS_OUT"):
                env.pop(k, None)
            r = run_prod(rd, cache_dir, tag)
        receipt = read_receipt(cache_dir)
    census = {}
    if census_out.exists():
        try:
            census = json.loads(census_out.read_text())
        except ValueError:
            census = {"unparseable": True}
    return {
        "workload": wid, "population": pop, "arm": arm, "tag": tag,
        "exit": r["exit"], "timeout": r["timeout"], "wall_s": r["wall_s"],
        "stdout_sha256": hashlib.sha256(r["stdout"]).hexdigest(),
        "stdout_norm_sha256": hashlib.sha256(norm_addr(r["stdout"])).hexdigest(),
        "stdout_bytes": len(r["stdout"]),
        "stderr_bytes": len(r["stderr"]),
        "state": workdir_state(rd),
        "census": census,
        "receipt": receipt,
    }


def append(row):
    TELEMETRY.mkdir(parents=True, exist_ok=True)
    with open(TELEMETRY / "runs.jsonl", "a") as f:
        f.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def cmd_run(args):
    man = json.loads((R1 / "WORKLOAD_MANIFEST.json").read_text())
    workloads = man["populations"][args.pop]["workloads"]
    if args.only:
        keep = set(args.only.split(","))
        workloads = [w for w in workloads if w["workload_id"] in keep]
    if args.limit:
        workloads = workloads[:args.limit]
    for w in workloads:
        wid = w["workload_id"]
        ok, why = verify_stage(args.pop, wid, w["script_sha256"],
                               w["workbook_sha256"])
        if not ok:
            print("%s: STAGE INVALID (%s)" % (wid, why), flush=True)
            append({"workload": wid, "population": args.pop, "arm": "INVALID",
                    "reason": why})
            continue
        # BASE x3
        for i in range(3):
            append(one_run(args.pop, wid, "BASE", "base%d" % i))
        # HOOK x2
        for i in range(2):
            append(one_run(args.pop, wid, "HOOK", "hook%d" % i))
        # PROD-WARM: persistent cache, warmup + 3
        wc = CACHE_BASE / "warm" / args.pop / wid
        if wc.exists():
            shutil.rmtree(wc)
        wc.mkdir(parents=True)
        append(one_run(args.pop, wid, "PROD", "warmup", cache_dir=wc))
        for i in range(3):
            append(one_run(args.pop, wid, "PROD", "warm%d" % i, cache_dir=wc))
        # PROD-COLD x1
        cc = CACHE_BASE / "cold" / args.pop / wid
        if cc.exists():
            shutil.rmtree(cc)
        cc.mkdir(parents=True)
        append(one_run(args.pop, wid, "PROD", "cold0", cache_dir=cc))
        print("%s: done" % wid, flush=True)


def cmd_scan(args):
    from recalc_agent._frozen import eligibility
    man = json.loads((R1 / "WORKLOAD_MANIFEST.json").read_text())
    out = []
    for pop in (args.pop,) if args.pop != "ALL" else ("A", "B"):
        for w in man["populations"][pop]["workloads"]:
            wid = w["workload_id"]
            script = CLEAN / pop / wid / "workload.py"
            src = script.read_text() if script.exists() else None
            res = eligibility.classify(src)
            out.append({
                "workload": wid, "population": pop,
                "decision": res.get("decision"),
                "reason": res.get("reason"),
                "blockers": sorted({b.get("reason", "?") for b in
                                    res.get("blockers", [])}),
                "blocker_detail": [
                    {"reason": b.get("reason"),
                     "detail": str(b.get("detail", ""))[:160]}
                    for b in res.get("blockers", [])],
                "categories": sorted({c.get("category", "?") for c in
                                      res.get("categories", [])}),
            })
    dest = HERE / "_staging" / ("classifier_scan_%s.jsonl" % args.pop)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        for r in out:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    print("scanned %d -> %s" % (len(out), dest))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--pop", choices=["A", "B"], required=True)
    r.add_argument("--only", default=None)
    r.add_argument("--limit", type=int, default=None)
    s = sub.add_parser("scan")
    s.add_argument("--pop", choices=["A", "B", "ALL"], default="ALL")
    args = ap.parse_args()
    if args.cmd == "run":
        cmd_run(args)
    else:
        cmd_scan(args)
