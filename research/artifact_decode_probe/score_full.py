"""R5 full-command scoring: rc4 vs D1 (via sitecustomize injector).

Per A/B workload: stage copy, persistent cache per arm, warmup+3 warm,
1 cold. Collects walls, routes, receipts, stdout/state parity, artifact
SHA equality. Writes FULL_COMMAND_RESULTS.jsonl + BUILD_RESULTS.jsonl
+ ARTIFACT_SIZE_RESULTS.json.
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
CLEAN = R1 / "_staging" / "staged" / "clean"
CONTROL_SRC = Path("/tmp/rc4control/src")  # pristine master worktree (rc4 arm)

sys.path.insert(0, str(ROOT / "src"))

TIMEOUT_S = 300


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, cwd, env):
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=TIMEOUT_S)
    return p, time.perf_counter() - t


def state(d):
    out = {}
    for p in sorted(Path(d).rglob("*.xlsx")):
        try:
            out[str(p.relative_to(d))] = sha_file(p)
        except OSError:
            out[str(p.relative_to(d))] = "UNREADABLE"
    return out


def prod_env(with_d1):
    # D1 lives in branch src; the rc4 control runs from a pristine master
    # worktree (the sitecustomize-injector approach was defeated by the
    # product bootstrap's own sitecustomize shadowing; see REPORT).
    env = dict(os.environ)
    src = str((ROOT / "src").resolve()) if with_d1 else str(CONTROL_SRC)
    env["PYTHONPATH"] = os.pathsep.join(
        [src] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env.pop("R5_DECODER", None)
    env.pop("RECALC_CONFIG", None)
    env.pop("RECALC_NO_RUNTIME", None)
    return env


def one(workdir, cache_dir, with_d1, tag):
    cfg = Path(workdir) / ("rt_%s.toml" % tag)
    cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache_dir)
    script = str(Path(workdir) / "workload.py")
    p, dt = run([sys.executable, "-m", "recalc_agent", "run", "--config", str(cfg),
                 "--workdir", str(workdir), script], cwd=workdir, env=prod_env(with_d1))
    receipt = {}
    try:
        rd = Path(json.loads((Path(cache_dir) / "runs" / "last_run.json").read_text())["run_dir"])
        for name in ("setup.json", "runtime_state.json"):
            q = rd / name
            if q.exists():
                receipt[name] = json.loads(q.read_text())
    except (OSError, ValueError, KeyError):
        pass
    import re
    norm = re.sub(rb"0x[0-9a-fA-F]+", b"0xADDR", p.stdout)
    return {"exit": p.returncode, "wall_s": dt,
            "stdout_sha": hashlib.sha256(p.stdout).hexdigest(),
            "stdout_norm_sha": hashlib.sha256(norm).hexdigest(),
            "stdout_bytes": len(p.stdout), "state": state(workdir),
            "receipt": receipt}


def route_of(receipt):
    rt = receipt.get("runtime_state.json") or {}
    st = receipt.get("setup.json") or {}
    return rt.get("route") or st.get("route") or "UNKNOWN"


def main(only=None, reverse=False, out_suffix=""):
    man = json.loads((R1 / "WORKLOAD_MANIFEST.json").read_text())
    full, build, size = [], [], []
    order = (("rc4", False), ("d1", True))
    if reverse:
        order = (("d1", True), ("rc4", False))
    for pop in ("A", "B"):
        for w in man["populations"][pop]["workloads"]:
            wid = w["workload_id"]
            if only and (pop, wid) not in only:
                continue
            arms = {}
            for label, with_d1 in order:
                cache = HERE / "_staging" / "fcache" / pop / wid / label
                if cache.exists():
                    shutil.rmtree(cache)
                cache.mkdir(parents=True)
                recs = []
                for tag in ("warmup", "warm0", "warm1", "warm2"):
                    rd = HERE / "_staging" / "fruns" / pop / wid / label / tag
                    if rd.exists():
                        shutil.rmtree(rd)
                    shutil.copytree(CLEAN / pop / wid, rd)
                    recs.append(one(rd, cache, with_d1, "%s_%s" % (label, tag)))
                ccache = HERE / "_staging" / "fcache" / pop / wid / (label + "_cold")
                if ccache.exists():
                    shutil.rmtree(ccache)
                ccache.mkdir(parents=True)
                rd = HERE / "_staging" / "fruns" / pop / wid / label / "cold0"
                if rd.exists():
                    shutil.rmtree(rd)
                shutil.copytree(CLEAN / pop / wid, rd)
                cold = one(rd, ccache, with_d1, "%s_cold" % label)
                arts = sorted((cache / "read-engine").glob("*.r3jz")) if (cache / "read-engine").exists() else []
                arms[label] = {"recs": recs, "cold": cold,
                               "artifacts": [(a.name, a.stat().st_size, sha_file(a)) for a in arts]}
            r0, r1 = arms["rc4"], arms["d1"]
            w0 = [r["wall_s"] for r in r0["recs"][1:]]
            w1 = [r["wall_s"] for r in r1["recs"][1:]]
            import statistics as st
            par = all(a["exit"] == b["exit"] and a["stdout_norm_sha"] == b["stdout_norm_sha"] and a["state"] == b["state"]
                      for a, b in zip(r0["recs"][1:], r1["recs"][1:]))
            full.append({
                "workload": wid, "population": pop,
                "rc4_warm_s": [round(x, 4) for x in w0],
                "d1_warm_s": [round(x, 4) for x in w1],
                "rc4_routes": [route_of(r["receipt"]) for r in r0["recs"][1:]],
                "d1_routes": [route_of(r["receipt"]) for r in r1["recs"][1:]],
                "rc4_decode_s": [round((r["receipt"].get("runtime_state.json", {}) or {}).get("times", {}).get("artifact_load_ns", 0) / 1e9, 6) for r in r0["recs"][1:]],
                "d1_decode_s": [round((r["receipt"].get("runtime_state.json", {}) or {}).get("times", {}).get("artifact_load_ns", 0) / 1e9, 6) for r in r1["recs"][1:]],
                "program_parity": par,
            })
            build.append({
                "workload": wid, "population": pop,
                "rc4_cold_s": round(r0["cold"]["wall_s"], 4),
                "d1_cold_s": round(r1["cold"]["wall_s"], 4),
            })
            a0 = {n: (s, h) for n, s, h in r0["artifacts"]}
            a1 = {n: (s, h) for n, s, h in r1["artifacts"]}
            size.append({
                "workload": wid, "population": pop,
                "rc4_artifacts": {n: {"bytes": s, "sha256": h} for n, (s, h) in a0.items()},
                "d1_artifacts": {n: {"bytes": s, "sha256": h} for n, (s, h) in a1.items()},
                "bytes_identical": a0 == a1,
            })
            print("%s %s: rc4w=%.3f d1w=%.3f routes=%s/%s parity=%s" % (
                pop, wid, st.median(w0), st.median(w1),
                route_of(r0["recs"][1]["receipt"]), route_of(r1["recs"][1]["receipt"]), par), flush=True)
    with open(HERE / ("FULL_COMMAND_RESULTS%s.jsonl" % out_suffix), "w") as f:
        for r in full:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with open(HERE / ("BUILD_RESULTS%s.jsonl" % out_suffix), "w") as f:
        for r in build:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with open(HERE / ("ARTIFACT_SIZE_RESULTS%s.json" % out_suffix), "w") as f:
        json.dump({"rows": size,
                   "all_identical": all(r["bytes_identical"] for r in size)}, f, indent=1, sort_keys=True)
    print("full-command done: %d workloads" % len(full))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None,
                    help="comma-separated POP:workload pairs")
    ap.add_argument("--reverse", action="store_true",
                    help="run d1 arm before rc4 arm (order-bias check)")
    ap.add_argument("--out-suffix", default="")
    args = ap.parse_args()
    only = None
    if args.only:
        only = set()
        for item in args.only.split(","):
            pop, wid = item.split(":", 1)
            only.add((pop, wid))
    main(only=only, reverse=args.reverse, out_suffix=args.out_suffix)
