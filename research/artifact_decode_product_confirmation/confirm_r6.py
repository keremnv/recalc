"""R6 D1 confirmation scoring: parity, corruption, full-command, cold, compat, memory.

Control: pristine rc4 from /tmp/rc4control worktree (master fed04b5).
Candidate: branch src with in-src D1. Arms alternate by workload index
(even: rc4 block first; odd: D1 block first) per the prereg order rule.
"""
import hashlib
import json
import os
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
CONTROL_SRC = Path("/tmp/rc4control/src")

sys.path.insert(0, str(ROOT / "src"))

TIMEOUT_S = 300


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_pristine_artifact():
    import importlib.util
    base = CONTROL_SRC / "recalc_agent"
    for name, path in (("rc4ctrl", base), ("rc4ctrl.read_engine", base / "read_engine")):
        spec = importlib.util.spec_from_file_location(
            name, path / "__init__.py", submodule_search_locations=[str(path)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    spec = importlib.util.spec_from_file_location(
        "rc4ctrl.read_engine.artifact", base / "read_engine" / "artifact.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rc4ctrl.read_engine.artifact"] = mod
    spec.loader.exec_module(mod)
    assert not hasattr(mod, "_direct_value"), "control worktree not pristine"
    return mod


def canon_value(v):
    import datetime as dt
    n = type(v).__name__
    if n == "ArrayFormula":
        return json.dumps({"kind": "array", "ref": v.ref, "text": v.text}, sort_keys=True)
    if n == "DataTableFormula":
        return json.dumps({"kind": "datatable", "attrs": dict(vars(v))}, sort_keys=True)
    if isinstance(v, dt.datetime):
        return json.dumps({"kind": "datetime", "value": v.isoformat()}, sort_keys=True)
    if isinstance(v, dt.date):
        return json.dumps({"kind": "date", "value": v.isoformat()}, sort_keys=True)
    if isinstance(v, dt.time):
        return json.dumps({"kind": "time", "value": v.isoformat()}, sort_keys=True)
    if isinstance(v, dt.timedelta):
        return json.dumps({"kind": "timedelta", "seconds": v.total_seconds()}, sort_keys=True)
    return json.dumps({"kind": "scalar", "value": v}, sort_keys=True)


def canon_book(book):
    sheets = []
    for name in book.sheetnames:
        info = book._sheets[name]
        cells = sorted((c, canon_value(v), d) for c, (v, d) in info.cells.items())
        sheets.append({"name": name,
                       "bounds": [info.min_row, info.min_col, info.max_row, info.max_col],
                       "merged": sorted(info.merged), "cells": cells})
    return {"sheets": sheets}


def all_workloads():
    man = json.loads((R1 / "WORKLOAD_MANIFEST.json").read_text())
    out = []
    for pop in ("A", "B"):
        for w in man["populations"][pop]["workloads"]:
            out.append((pop, w["workload_id"]))
    return out


def cmd_parity():
    from recalc_agent.read_engine import artifact
    rc4artifact = load_pristine_artifact()
    rows = []
    for pop, wid in all_workloads():
        src = CLEAN / pop / wid
        books = sorted(src.glob("*.xlsx"))
        assert len(books) == 1, (pop, wid)
        digest = sha_file(books[0])
        apath, _, _ = artifact.ensure(books[0], HERE / "_staging" / "pcache" / pop / wid, digest)
        data = apath.read_bytes()
        b0 = rc4artifact.decode(data, digest)
        b1 = artifact.decode(data, digest)
        eq = canon_book(b0) == canon_book(b1)
        rows.append({"workload": wid, "population": pop, "canon_equal": eq,
                     "n_cells": sum(len(b0._sheets[n].cells) for n in b0.sheetnames)})
        if not eq:
            print("MISMATCH", pop, wid, flush=True)
    with open(HERE / "SEMANTIC_PARITY.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    bad = [r for r in rows if not r["canon_equal"]]
    print("parity: %d/%d equal" % (len(rows) - len(bad), len(rows)))


def mutate_base():
    import struct
    import zlib
    from recalc_agent.read_engine import artifact
    wid = "Template_03_03__c76ea596b408"
    src = CLEAN / "A" / wid
    book = sorted(src.glob("*.xlsx"))[0]
    digest = sha_file(book)
    apath, _, _ = artifact.ensure(book, HERE / "_staging" / "ccache", digest)
    data = apath.read_bytes()
    hlen = struct.unpack(">I", data[8:12])[0]
    header = json.loads(data[12:12 + hlen])
    offset = 12 + hlen
    clen = struct.unpack(">Q", data[offset:offset + 8])[0]
    raw = zlib.decompress(data[offset + 8:offset + 8 + clen])
    return data, digest, raw, header, {"offset": offset, "clen": clen}


def rebuild_app(header, raw, ident_mod, magic_ok=True):
    import struct
    import zlib
    from recalc_agent.read_engine.artifact import canonical, sha_bytes
    comp = zlib.compress(raw, level=1)
    header = dict(header)
    header["payload_sha256"] = sha_bytes(raw)
    h = canonical(header)
    body = (ident_mod.MAGIC if magic_ok else b"BADMAGIC") + struct.pack(">I", len(h)) + h \
        + struct.pack(">Q", len(comp)) + comp
    return body + hashlib.sha256(body).digest()


def cmd_corrupt():
    import struct
    import zlib
    from recalc_agent.read_engine import artifact
    rc4artifact = load_pristine_artifact()
    import rc4ctrl.read_engine._identity as rc4ident
    data, digest, raw, header, off = mutate_base()
    cases = {}
    cases["truncated_header"] = data[:20]
    cases["truncated_payload"] = data[:-40]
    bad = bytearray(data)
    bad[-1] ^= 0xFF
    cases["wrong_checksum"] = bytes(bad)
    cases["wrong_source_hash"] = ("__DIGEST__", "0" * 64)
    cases["wrong_decoder_version"] = ("__HEADERFIELD__", ("decoder_sha256", "0" * 64))
    cases["wrong_format_version"] = ("__HEADERFIELD__", ("format_version", "NOPE_V9"))
    bad2 = bytearray(data)
    bad2[off["offset"] + 10] ^= 0xFF
    cases["corrupt_compressed_stream"] = bytes(bad2)
    cases["corrupt_serialized_structure"] = rebuild_app(header, b"{not json", rc4ident)
    dup = json.loads(raw)
    dup["sheets"][0]["cells"].append(dup["sheets"][0]["cells"][0])
    cases["duplicate_coordinates"] = rebuild_app(header, json.dumps(dup).encode(), rc4ident)
    inv = json.loads(raw)
    inv["sheets"][0]["cells"][0][2] = {"kind": "scalar", "value": float("nan")}
    raw_nan = json.dumps(inv, allow_nan=True).encode()
    comp = zlib.compress(raw_nan, level=1)
    h = dict(header)
    h["payload_sha256"] = hashlib.sha256(raw_nan).hexdigest()
    hb = json.dumps(h, sort_keys=True, separators=(",", ":")).encode()
    body = rc4ident.MAGIC + struct.pack(">I", len(hb)) + hb + struct.pack(">Q", len(comp)) + comp
    cases["nan_typed_value"] = body + hashlib.sha256(body).digest()
    inv2 = json.loads(raw)
    inv2["sheets"][0]["cells"][0][0] = "ZZZ999999999999"
    cases["impossible_coordinate"] = rebuild_app(header, json.dumps(inv2).encode(), rc4ident)
    inv3 = json.loads(raw)
    inv3["sheets"][0]["cells"][0][2] = {"kind": "frobnicate", "value": 1}
    cases["impossible_typed_kind"] = rebuild_app(header, json.dumps(inv3).encode(), rc4ident)
    results = {}
    for name, payload in cases.items():
        row = {}
        for label, mod in (("rc4", rc4artifact), ("d1", artifact)):
            try:
                if isinstance(payload, tuple) and payload[0] == "__DIGEST__":
                    mod.decode(data, payload[1])
                elif isinstance(payload, tuple) and payload[0] == "__HEADERFIELD__":
                    hh = dict(header)
                    hh[payload[1][0]] = payload[1][1]
                    hb = json.dumps(hh, sort_keys=True, separators=(",", ":")).encode()
                    o = off["offset"]
                    b = (rc4ident.MAGIC + struct.pack(">I", len(hb)) + hb
                         + data[o:o + 8 + off["clen"]])
                    mod.decode(b + hashlib.sha256(b).digest(), digest)
                else:
                    mod.decode(payload, digest)
                row[label] = "SERVED (BAD)"
            except mod.ArtifactError as e:
                row[label] = "REJECTED: %s" % str(e)[:60]
            except Exception as e:  # noqa: BLE001
                row[label] = "OTHER-EXC: %s" % type(e).__name__
        results[name] = row
        print("%-28s rc4=%-40s d1=%s" % (name, row["rc4"], row["d1"]), flush=True)
    bad_rows = {k: v for k, v in results.items()
                if not v["rc4"].startswith("REJECTED") or not v["d1"].startswith("REJECTED")}
    with open(HERE / "CORRUPTION_RESULTS.json", "w") as f:
        json.dump({"results": results, "verdict": "PASS" if not bad_rows else "FAIL",
                   "non_rejecting": sorted(bad_rows)}, f, indent=1, sort_keys=True)
    print("corruption verdict:", "PASS" if not bad_rows else "FAIL")


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


def prod_env(src):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(src)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env.pop("RECALC_CONFIG", None)
    env.pop("RECALC_NO_RUNTIME", None)
    return env


def one(workdir, cache_dir, src, tag):
    import re
    cfg = Path(workdir) / ("rt_%s.toml" % tag)
    cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache_dir)
    script = str(Path(workdir) / "workload.py")
    p, dt = run([sys.executable, "-m", "recalc_agent", "run", "--config", str(cfg),
                 "--workdir", str(workdir), script], cwd=workdir, env=prod_env(src))
    receipt = {}
    try:
        rd = Path(json.loads((Path(cache_dir) / "runs" / "last_run.json").read_text())["run_dir"])
        for name in ("setup.json", "runtime_state.json"):
            q = rd / name
            if q.exists():
                receipt[name] = json.loads(q.read_text())
    except (OSError, ValueError, KeyError):
        pass
    norm = re.sub(rb"0x[0-9a-fA-F]+", b"0xADDR", p.stdout)
    return {"exit": p.returncode, "wall_s": dt,
            "stdout_norm_sha": hashlib.sha256(norm).hexdigest(),
            "stdout_bytes": len(p.stdout), "state": state(workdir), "receipt": receipt}


def route_of(receipt):
    rt = receipt.get("runtime_state.json") or {}
    st = receipt.get("setup.json") or {}
    return rt.get("route") or st.get("route") or "UNKNOWN"


def cmd_full(only=None, reverse_all=False, out_suffix=""):
    branch_src = (ROOT / "src").resolve()
    full, perf, cold = [], [], []
    workloads = all_workloads()
    if only:
        workloads = [w for w in workloads if w in only]
    for idx, (pop, wid) in enumerate(workloads):
        # Prereg order rule: even index rc4-first, odd d1-first.
        first_d1 = (idx % 2 == 1)
        if reverse_all:
            first_d1 = not first_d1
        order = (("d1", True), ("rc4", False)) if first_d1 else (("rc4", False), ("d1", True))
        arms = {}
        for label, is_d1 in order:
            src = branch_src if is_d1 else CONTROL_SRC
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
                recs.append(one(rd, cache, src, "%s_%s" % (label, tag)))
            ccache = HERE / "_staging" / "fcache" / pop / wid / (label + "_cold")
            if ccache.exists():
                shutil.rmtree(ccache)
            ccache.mkdir(parents=True)
            rd = HERE / "_staging" / "fruns" / pop / wid / label / "cold0"
            if rd.exists():
                shutil.rmtree(rd)
            shutil.copytree(CLEAN / pop / wid, rd)
            cold_rec = one(rd, ccache, src, "%s_cold" % label)
            arts = sorted((cache / "read-engine").glob("*.r3jz")) if (cache / "read-engine").exists() else []
            arms[label] = {"recs": recs, "cold": cold_rec,
                           "artifacts": [(a.name, a.stat().st_size, sha_file(a)) for a in arts]}
        r0, r1 = arms["rc4"], arms["d1"]
        par = all(a["exit"] == b["exit"] and a["stdout_norm_sha"] == b["stdout_norm_sha"]
                  and a["state"] == b["state"] and route_of(a["receipt"]) == route_of(b["receipt"])
                  for a, b in zip(r0["recs"][1:], r1["recs"][1:]))
        full.append({"workload": wid, "population": pop, "program_parity": par,
                     "rc4_routes": [route_of(r["receipt"]) for r in r0["recs"][1:]],
                     "d1_routes": [route_of(r["receipt"]) for r in r1["recs"][1:]],
                     "first_arm": order[0][0]})
        perf.append({
            "workload": wid, "population": pop,
            "rc4_warm_s": [round(r["wall_s"], 4) for r in r0["recs"][1:]],
            "d1_warm_s": [round(r["wall_s"], 4) for r in r1["recs"][1:]],
            "rc4_decode_s": [round((r["receipt"].get("runtime_state.json", {}) or {}).get("times", {}).get("artifact_load_ns", 0) / 1e9, 6) for r in r0["recs"][1:]],
            "d1_decode_s": [round((r["receipt"].get("runtime_state.json", {}) or {}).get("times", {}).get("artifact_load_ns", 0) / 1e9, 6) for r in r1["recs"][1:]],
            "first_arm": order[0][0]})
        a0 = {n: (s, h) for n, s, h in r0["artifacts"]}
        a1 = {n: (s, h) for n, s, h in r1["artifacts"]}
        cold.append({
            "workload": wid, "population": pop,
            "rc4_cold_s": round(r0["cold"]["wall_s"], 4),
            "d1_cold_s": round(r1["cold"]["wall_s"], 4),
            "artifacts_identical": a0 == a1,
            "rc4_artifact_bytes": {n: s for n, (s, _) in a0.items()}})
        print("%s %s: rc4w=%.3f d1w=%.3f parity=%s first=%s" % (
            pop, wid, statistics.median(r["wall_s"] for r in r0["recs"][1:]),
            statistics.median(r["wall_s"] for r in r1["recs"][1:]), par, order[0][0]), flush=True)
    with open(HERE / ("FULL_COMMAND_PARITY%s.jsonl" % out_suffix), "w") as f:
        for r in full:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with open(HERE / ("PERFORMANCE_RESULTS%s.jsonl" % out_suffix), "w") as f:
        for r in perf:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with open(HERE / ("COLD_RESULTS%s.jsonl" % out_suffix), "w") as f:
        for r in cold:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    print("full-command done: %d workloads" % len(full))


def cmd_compat():
    """rc4-built artifacts must REUSE under D1 with correct semantics."""
    from recalc_agent.read_engine import artifact as d1artifact
    rc4artifact = load_pristine_artifact()
    rows = []
    for pop, wid in all_workloads():
        src = CLEAN / pop / wid
        book = sorted(src.glob("*.xlsx"))[0]
        digest = sha_file(book)
        cache = HERE / "_staging" / "compat" / pop / wid
        if cache.exists():
            shutil.rmtree(cache)
        cache.mkdir(parents=True)
        # Build with pristine rc4.
        apath_b, status_b, _ = rc4artifact.ensure(book, cache, digest)
        assert status_b == "BUILT", (pop, wid, status_b)
        # Validate + load with D1.
        from recalc_agent.read_engine import cache as d1cache
        art_p, side_p = d1cache.paths(cache, digest) if hasattr(d1cache, "paths") else (None, None)
        if art_p is None:
            from recalc_agent.read_engine._identity import paths as ipaths
            art_p, side_p = ipaths(cache, digest)
        good, reason, _ = d1cache.validate(art_p, side_p, digest)
        b_d1 = d1artifact.decode(apath_b.read_bytes(), digest) if good else None
        b_rc4 = rc4artifact.decode(apath_b.read_bytes(), digest)
        rows.append({"workload": wid, "population": pop, "reused_under_d1": good,
                     "reuse_reason": reason, "canon_equal": (canon_book(b_d1) == canon_book(b_rc4)) if good else False})
        if not good or not (canon_book(b_d1) == canon_book(b_rc4)):
            print("COMPAT ISSUE", pop, wid, good, reason, flush=True)
    with open(HERE / "ARTIFACT_COMPATIBILITY.json", "w") as f:
        json.dump({"rows": rows, "all_reused_equal": all(r["reused_under_d1"] and r["canon_equal"] for r in rows)},
                  f, indent=1, sort_keys=True)
    print("compat: %d/%d reused+equal" % (sum(1 for r in rows if r["reused_under_d1"] and r["canon_equal"]), len(rows)))


def cmd_memory():
    for label, src in (("rc4", CONTROL_SRC), ("d1", (ROOT / "src").resolve())):
        run = HERE / "_staging" / "mem" / label
        if run.exists():
            shutil.rmtree(run)
        shutil.copytree(CLEAN / "A" / "Debugging_10_10__c7eca76e6646", run)
        cache = HERE / "_staging" / "memcache" / label
        if cache.exists():
            shutil.rmtree(cache)
        cache.mkdir(parents=True)
        cfg = run / "rt.toml"
        cfg.write_text('[runtime]\ncache_dir = "%s"\n' % cache)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(src)
        env.pop("RECALC_CONFIG", None)
        env.pop("RECALC_NO_RUNTIME", None)
        cmd = [sys.executable, "-m", "recalc_agent", "run", "--config", str(cfg),
               "--workdir", str(run), str(run / "workload.py")]
        subprocess.run(cmd, cwd=run, env=env, capture_output=True, timeout=TIMEOUT_S)
        p = subprocess.run(["/usr/bin/time", "-v"] + cmd, cwd=run, env=env,
                           capture_output=True, text=True, timeout=TIMEOUT_S)
        rss = [l for l in p.stderr.splitlines() if "Maximum resident" in l]
        print(label, rss[0].strip() if rss else "NO_RSS", "exit=", p.returncode, flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=["parity", "corrupt", "full", "compat", "memory"], required=True)
    ap.add_argument("--only", default=None)
    ap.add_argument("--reverse-all", action="store_true")
    ap.add_argument("--out-suffix", default="")
    args = ap.parse_args()
    if args.step == "parity":
        cmd_parity()
    elif args.step == "corrupt":
        cmd_corrupt()
    elif args.step == "full":
        only = None
        if args.only:
            only = set()
            for item in args.only.split(","):
                pop, wid = item.split(":", 1)
                only.add((pop, wid))
        cmd_full(only=only, reverse_all=args.reverse_all, out_suffix=args.out_suffix)
    elif args.step == "compat":
        cmd_compat()
    else:
        cmd_memory()
