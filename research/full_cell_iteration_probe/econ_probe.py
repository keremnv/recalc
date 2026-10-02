"""Proxy/allocation economics probes (run after warm scoring).

1. Per-object ProxyCell construction cost (tight loop, upper bound).
2. RSS-peak comparison BASE vs ON on the heaviest target workload.
3. Per-cell wall decomposition from PERFORMANCE_RESULTS.jsonl.
"""
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


def construction_cost():
    sys.path.insert(0, str(ROOT / "src"))
    from recalc_agent.read_engine.runtime import ProxyCell
    ws = None  # ProxyCell stores ws without touching it at construction
    t = time.perf_counter()
    n = 200000
    for i in range(n):
        ProxyCell(ws, (i % 5000) + 1, (i % 200) + 1)
    dt = time.perf_counter() - t
    print(f"ProxyCell construction: {dt / n * 1e6:.2f} us/cell (n={n})")
    return dt / n


def rss_peak(workload):
    import shutil
    clean = (HERE.parent / "execution_surface_census" / "_staging" /
             "staged" / "clean" / "A" / workload)
    out = {}
    for arm in ("base", "probe"):
        wd = HERE / "_staging" / "econ" / workload / arm
        if wd.exists():
            shutil.rmtree(wd)
        shutil.copytree(clean, wd)
        if arm == "base":
            cmd = ["/usr/bin/time", "-v", sys.executable, "workload.py"]
            env = dict(__import__("os").environ)
        else:
            cache = HERE / "_staging" / "econ" / workload / "cache"
            if cache.exists():
                shutil.rmtree(cache)
            cache.mkdir(parents=True)
            (wd / "rt.toml").write_text('[runtime]\ncache_dir = "%s"\n' % cache)
            env = dict(__import__("os").environ)
            env["PYTHONPATH"] = str(ROOT / "src") + (
                ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            # warmup then measured run under time
            subprocess.run([sys.executable, "-m", "recalc_agent", "run",
                            "--config", str(wd / "rt.toml"), "--workdir",
                            str(wd), str(wd / "workload.py")],
                           cwd=wd, env=env, capture_output=True)
            cmd = ["/usr/bin/time", "-v", sys.executable, "-m", "recalc_agent",
                   "run", "--config", str(wd / "rt.toml"), "--workdir",
                   str(wd), str(wd / "workload.py")]
        p = subprocess.run(cmd, cwd=wd, env=env, capture_output=True)
        err = p.stderr.decode(errors="replace")
        import re
        m = re.search(r"Maximum resident set size.*?: (\d+)", err)
        out[arm] = int(m.group(1)) if m else None
        print(f"{workload} {arm}: RSS peak = {out[arm]} KB")
    return out


def per_cell_walls():
    rows = [json.loads(l) for l in
            open(HERE / "PERFORMANCE_RESULTS.jsonl")]
    print(f"{'workload':44s} {'cells':>8s} {'base/cell':>10s} {'on/cell':>10s}")
    for r in sorted(rows, key=lambda x: x["workload"]):
        on = r["arms"]["ON"]
        counts = on.get("counts", [{}])[0]
        cells = counts.get("direct_iteration_cells", 0)
        if not cells:
            continue
        b = statistics.median(r["arms"]["BASE"]["wall_s"])
        o = statistics.median(on["wall_s"])
        print(f"{r['workload'][:44]:44s} {cells:8d} {b / cells * 1e6:9.1f}u {o / cells * 1e6:9.1f}u")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--rss", default=None)
    args = ap.parse_args()
    construction_cost()
    if args.rss:
        rss_peak(args.rss)
    try:
        per_cell_walls()
    except FileNotFoundError:
        print("(PERFORMANCE_RESULTS.jsonl not ready)")
