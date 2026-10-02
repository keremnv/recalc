"""Differential parity: probe product path vs plain openpyxl on A/B.

Compares exit code, address-normalized stdout, and volatile-normalized
workbook state for every Population A/B workload. Writes PARITY_RESULTS.jsonl.
"""
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
CENSUS = HERE.parent / "execution_surface_census"
STAGE = HERE / "_staging" / "parity"
sys.path.insert(0, str(CENSUS))
import aggregate as agg  # noqa: E402

_ADDR = re.compile(rb"0x[0-9a-fA-F]+")


def run(cmd, cwd, env, timeout=600):
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           timeout=timeout)
        return {"exit": p.returncode, "out": p.stdout, "err": p.stderr,
                "wall": time.perf_counter() - t, "timeout": False}
    except subprocess.TimeoutExpired as e:
        return {"exit": None, "out": e.stdout or b"", "err": e.stderr or b"",
                "wall": time.perf_counter() - t, "timeout": True}


def state(d):
    out = {}
    for p in sorted(Path(d).glob("*.xlsx")):
        out[p.name] = agg.norm_xlsx(p.read_bytes())
    return out


def main():
    man = json.loads((CENSUS / "WORKLOAD_MANIFEST.json").read_text())
    clean = CENSUS / "_staging" / "staged" / "clean"
    rows = []
    for pop in ("A", "B"):
        for w in man["populations"][pop]["workloads"]:
            wid = w["workload_id"]
            src = clean / pop / wid
            results = {}
            for arm in ("base", "probe"):
                wd = STAGE / pop / wid / arm
                if wd.exists():
                    shutil.rmtree(wd)
                shutil.copytree(src, wd)
                if arm == "base":
                    r = run([sys.executable, "workload.py"], cwd=wd,
                            env=dict(os.environ))
                else:
                    cache = STAGE / pop / wid / "cache"
                    if cache.exists():
                        shutil.rmtree(cache)
                    cache.mkdir(parents=True)
                    cfg = wd / "rt.toml"
                    cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache)
                    env = dict(os.environ)
                    env["PYTHONPATH"] = os.pathsep.join(
                        [str(ROOT / "src")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
                    r = run([sys.executable, "-m", "recalc_agent", "run",
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
                results[arm] = (r, state(wd))
            b, p = results["base"], results["probe"]
            ok = (b[0]["exit"] == p[0]["exit"]
                  and _ADDR.sub(b"0xADDR", b[0]["out"]) == _ADDR.sub(b"0xADDR", p[0]["out"])
                  and b[1] == p[1]
                  and not b[0]["timeout"] and not p[0]["timeout"])
            rows.append({"population": pop, "workload": wid,
                         "parity": ok, "route": results.get("route"),
                         "exit": [b[0]["exit"], p[0]["exit"]]})
            print(("PASS " if ok else "FAIL ") + pop + " " + wid +
                  f" route={results.get('route')}", flush=True)
    (HERE / "PARITY_RESULTS.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
    fails = [r for r in rows if not r["parity"]]
    print(f"parity: {len(rows) - len(fails)}/{len(rows)} FAILURES={len(fails)}")


if __name__ == "__main__":
    main()
