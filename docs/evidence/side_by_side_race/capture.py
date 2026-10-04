"""Capture byte-timed race recordings (documentation/evidence only).

Records the frozen FM_08_02 Line-01 scan under BASE (bare python) and RECALC
(warm recalc-agent run) using `script --log-timing`, so the side-by-side GIF
replays genuine output bytes with genuine pacing.

Protocol (mirrors the vignette timing protocol):
- BASE: 3 reps, fresh workdir each, bare python.
- RECALC: fresh cache, 1 discarded warmup, 3 reps in fresh workdirs.
- MEDIAN rep per arm (by wall) is kept as the race recording; all reps'
  walls/hashes/routes are logged in captures.json.

Usage: python3 docs/evidence/side_by_side_race/capture.py [--venv VENV]
"""
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
WID = "Financial_Model_08_02__4ca3ae46295d"
SRC = ROOT / "research/execution_surface_census/_staging/staged/clean/A" / WID


def run_capture(workdir, cmd, ts_path, log_path):
    """Run cmd under `script`, capturing typescript + timing. Returns wall, exit."""
    t0 = time.perf_counter()
    p = subprocess.run(
        ["script", "-qec", " ".join(cmd), "-T", str(log_path), str(ts_path)],
        cwd=workdir, capture_output=True)
    return round(time.perf_counter() - t0, 4), p.returncode


def program_output(raw: bytes) -> bytes:
    """Strip `script` header/footer lines, keeping only child output bytes."""
    lines = raw.replace(b"\r\n", b"\n").split(b"\n")
    if lines and lines[0].startswith(b"Script started on "):
        lines = lines[1:]
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith(b"Script done on "):
            del lines[i]
            break
    return b"\n".join(lines)


def norm_stdout(raw: bytes) -> bytes:
    text = program_output(raw).replace(b"\r", b"\n")
    text = re.sub(rb"0x[0-9a-fA-F]+", b"0xADDR", text)
    return text


def main():
    venv = Path(sys.argv[sys.argv.index("--venv") + 1]
                if "--venv" in sys.argv else "/tmp/racevenv")
    py = str(venv / "bin" / "python")
    agent = str(venv / "bin" / "recalc-agent")
    out = HERE / "captures"
    if out.exists():
        shutil.rmtree(out)
    (out / "raw").mkdir(parents=True)
    stage = Path("/tmp/race_capture")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    def fresh(name):
        wd = stage / name
        shutil.copytree(SRC, wd)
        return wd

    log = {"workload": WID, "arms": {}}
    # BASE x3
    base = []
    for rep in range(3):
        wd = fresh(f"base_{rep}")
        ts, tl = out / "raw" / f"base_{rep}.typescript", out / "raw" / f"base_{rep}.timing"
        wall, code = run_capture(wd, [py, "workload.py"], ts, tl)
        raw = ts.read_bytes()
        base.append({"wall": wall, "exit": code, "rep": rep,
                     "lines": program_output(raw).count(b"\n"),
                     "sha_norm": hashlib.sha256(norm_stdout(raw)).hexdigest()[:16]})
    log["arms"]["BASE"] = base
    # RECALC warmup + x3
    cache = stage / "cache"
    cache.mkdir()

    def prod(wd):
        (wd / "rt.toml").write_text('[runtime]\ncache_dir = "%s"\n' % cache)
        return [agent, "run", "--config", str(wd / "rt.toml"),
                "--workdir", str(wd), str(wd / "workload.py")]

    wd0 = fresh("warmup")
    run_capture(wd0, prod(wd0), out / "raw" / "warmup.typescript",
                out / "raw" / "warmup.timing")
    rec = []
    for rep in range(3):
        wd = fresh(f"recalc_{rep}")
        ts, tl = out / "raw" / f"recalc_{rep}.typescript", out / "raw" / f"recalc_{rep}.timing"
        wall, code = run_capture(wd, prod(wd), ts, tl)
        raw = ts.read_bytes()
        last = json.loads((cache / "runs" / "last_run.json").read_text())
        rd = Path(last["run_dir"])
        setup = json.loads((rd / "setup.json").read_text())
        rt = json.loads((rd / "runtime_state.json").read_text())
        rec.append({"wall": wall, "exit": code, "rep": rep,
                    "lines": program_output(raw).count(b"\n"),
                    "sha_norm": hashlib.sha256(norm_stdout(raw)).hexdigest()[:16],
                    "route": rt.get("route") or setup.get("route"),
                    "artifact": sorted({e.get("status") for e in
                                        (setup.get("artifacts") or {}).values()
                                        if isinstance(e, dict)}),
                    "counts": rt.get("counts", {})})
    log["arms"]["RECALC"] = rec
    # Select median reps; keep only their recordings.
    for arm, rows in (("BASE", base), ("RECALC", rec)):
        med = statistics.median(r["wall"] for r in rows)
        sel = min(rows, key=lambda r: abs(r["wall"] - med))
        log[f"{arm}_median_wall"] = med
        log[f"{arm}_selected"] = sel
        tag = "base" if arm == "BASE" else "recalc"
        shutil.move(str(out / "raw" / f"{tag}_{sel['rep']}.typescript"),
                    out / f"{tag}.typescript")
        shutil.move(str(out / "raw" / f"{tag}_{sel['rep']}.timing"),
                    out / f"{tag}.timing")
    shutil.rmtree(out / "raw")
    (out / "captures.json").write_text(json.dumps(log, indent=1) + "\n")
    print(json.dumps({k: v for k, v in log.items() if not k == "arms"}, indent=1))
    ok = (all(r["exit"] == 0 for r in base + rec)
          and all(r["route"] == "DIRECT_RUNTIME" for r in rec)
          and all(r["artifact"] == ["REUSED"] for r in rec)
          and len({r["sha_norm"] for r in base + rec}) == 1)
    print("GATES:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
