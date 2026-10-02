"""R3 confirmation runs: warm A/B (BASE/OFF/ON) + differential parity + cold + memory.

Reuses R2 harness functions unchanged; writes R3 ledgers:
REPRESENTATIVE_RESULTS.jsonl, FIXED22_RESULTS.jsonl, PRODUCT_GATE.json.
"""
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
R2 = HERE.parent / "full_cell_iteration_probe"
CENSUS = HERE.parent / "execution_surface_census"
sys.path.insert(0, str(R2))
sys.path.insert(0, str(CENSUS))
import measure as r2measure  # noqa: E402
import parity_check as r2parity  # noqa: E402

r2measure.STAGE = HERE / "_staging" / "perf"
r2parity.STAGE = HERE / "_staging" / "parity"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=["warm", "parity", "cold", "memory"],
                    required=True)
    args = ap.parse_args()
    man = json.loads((CENSUS / "WORKLOAD_MANIFEST.json").read_text())
    clean = CENSUS / "_staging" / "staged" / "clean"
    if args.step == "warm":
        for pop, dest in (("A", HERE / "REPRESENTATIVE_RESULTS.jsonl"),
                          ("B", HERE / "FIXED22_RESULTS.jsonl")):
            with open(dest, "w") as f:
                for w in man["populations"][pop]["workloads"]:
                    wid = w["workload_id"]
                    rec = r2measure.measure_workload(
                        wid, "workload.py", clean / pop / wid, [pop])
                    f.write(json.dumps(rec, sort_keys=True) + "\n")
                    f.flush()
                    b = statistics.median(rec["arms"]["BASE"]["wall_s"])
                    print(pop, wid, "base=%.2f" % b, flush=True)
    elif args.step == "parity":
        import shutil
        rows = []
        for pop in ("A", "B"):
            for w in man["populations"][pop]["workloads"]:
                wid = w["workload_id"]
                src = clean / pop / wid
                results = {}
                for arm in ("base", "probe"):
                    wd = r2parity.STAGE / pop / wid / arm
                    if wd.exists():
                        shutil.rmtree(wd)
                    shutil.copytree(src, wd)
                    if arm == "base":
                        r = r2parity.run([sys.executable, "workload.py"],
                                         cwd=wd, env=dict(__import__("os").environ))
                    else:
                        import os
                        cache = r2parity.STAGE / pop / wid / "cache"
                        if cache.exists():
                            shutil.rmtree(cache)
                        cache.mkdir(parents=True)
                        cfg = wd / "rt.toml"
                        cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache)
                        env = dict(os.environ)
                        env["PYTHONPATH"] = os.pathsep.join(
                            [str(ROOT / "src")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
                        r = r2parity.run(
                            [sys.executable, "-m", "recalc_agent", "run",
                             "--config", str(cfg), "--workdir", str(wd),
                             str(wd / "workload.py")], cwd=wd, env=env)
                        try:
                            ptr = json.loads((cache / "runs" / "last_run.json").read_text())
                            rd = Path(ptr["run_dir"])
                            st = json.loads((rd / "setup.json").read_text())
                            rt = {}
                            if (rd / "runtime_state.json").exists():
                                rt = json.loads((rd / "runtime_state.json").read_text())
                            results["route"] = rt.get("route") or st.get("route")
                        except (OSError, ValueError, KeyError):
                            results["route"] = None
                    results[arm] = (r, r2parity.state(wd))
                b, p = results["base"], results["probe"]
                import re
                ok = (b[0]["exit"] == p[0]["exit"]
                      and re.sub(rb"0x[0-9a-fA-F]+", b"0xADDR", b[0]["out"])
                      == re.sub(rb"0x[0-9a-fA-F]+", b"0xADDR", p[0]["out"])
                      and b[1] == p[1]
                      and not b[0]["timeout"] and not p[0]["timeout"])
                rows.append({"population": pop, "workload": wid, "parity": ok,
                             "route": results.get("route")})
                print(("PASS " if ok else "FAIL ") + pop + " " + wid, flush=True)
        (HERE / "_staging" / "parity_r3.jsonl").write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
        fails = [r for r in rows if not r["parity"]]
        print(f"parity: {len(rows) - len(fails)}/{len(rows)}")
    elif args.step == "cold":
        targets = set(json.loads((R2 / "TARGET_WORKLOADS.json").read_text())["workloads"])
        with open(HERE / "_staging" / "cold_r3.jsonl", "w") as f:
            for w in man["populations"]["A"]["workloads"]:
                wid = w["workload_id"]
                if wid not in targets:
                    continue
                rec = r2measure.cold_check(wid, "workload.py", clean / "A" / wid)
                rec["population"] = "A"
                f.write(json.dumps(rec, sort_keys=True) + "\n")
                f.flush()
                print(wid, rec, flush=True)
    elif args.step == "memory":
        sys.path.insert(0, str(ROOT / "src"))
        import econ_probe as _  # noqa: F401  (R2 module for construction cost)
        from econ_probe import construction_cost  # noqa: E402
        per_cell = construction_cost()
        import subprocess
        import shutil
        import re
        import os
        wid = "Debugging_10_10__c7eca76e6646"
        clean_wd = clean / "A" / wid
        out = {"workload": wid, "proxy_construction_s_per_cell": per_cell}
        for arm in ("base", "probe"):
            wd = HERE / "_staging" / "econ" / wid / arm
            if wd.exists():
                shutil.rmtree(wd)
            shutil.copytree(clean_wd, wd)
            if arm == "base":
                cmd = ["/usr/bin/time", "-v", sys.executable, "workload.py"]
                env = dict(os.environ)
            else:
                cache = HERE / "_staging" / "econ" / wid / "cache"
                if cache.exists():
                    shutil.rmtree(cache)
                cache.mkdir(parents=True)
                (wd / "rt.toml").write_text('[runtime]\ncache_dir = "%s"\n' % cache)
                env = dict(os.environ)
                env["PYTHONPATH"] = str(ROOT / "src") + (
                    ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
                subprocess.run([sys.executable, "-m", "recalc_agent", "run",
                                "--config", str(wd / "rt.toml"), "--workdir",
                                str(wd), str(wd / "workload.py")],
                               cwd=wd, env=env, capture_output=True)
                cmd = ["/usr/bin/time", "-v", sys.executable, "-m",
                       "recalc_agent", "run", "--config", str(wd / "rt.toml"),
                       "--workdir", str(wd), str(wd / "workload.py")]
            p = subprocess.run(cmd, cwd=wd, env=env, capture_output=True)
            m = re.search(r"Maximum resident set size.*?: (\d+)",
                          p.stderr.decode(errors="replace"))
            out[arm + "_rss_peak_kb"] = int(m.group(1)) if m else None
            print(arm, out[arm + "_rss_peak_kb"], flush=True)
        (HERE / "_staging" / "memory_r3.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
