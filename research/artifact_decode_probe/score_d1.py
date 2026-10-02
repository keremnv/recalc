"""R5 D1 scoring part 1 (in-process): semantic parity, microbenchmarks, corruption.

parity: canon-compare product decode vs D1 on all 52 A/B artifacts.
bench: product vs D1 decode walls x5 on 7-book subset + smalls.
corrupt: 11 malformed-artifact cases; both decoders must reject.
"""
import hashlib
import json
import statistics
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
R1 = HERE.parent / "execution_surface_census"
CLEAN = R1 / "_staging" / "staged" / "clean"
CACHE = HERE / "_staging" / "cache"

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from profile_r5 import SUBSET, canon_book, ensure_artifact  # noqa: E402


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def all_workloads():
    man = json.loads((R1 / "WORKLOAD_MANIFEST.json").read_text())
    out = []
    for pop in ("A", "B"):
        for w in man["populations"][pop]["workloads"]:
            out.append((pop, w["workload_id"]))
    return out


CAND = {"d1": "d1", "d1b": "d1b"}
CAND_BOOK = {}


def cand_book(name):
    if name not in CAND_BOOK:
        if name == "d1":
            import candidates.d1 as m
            CAND_BOOK[name] = m._book_direct
        else:
            import candidates.d1b as m
            CAND_BOOK[name] = m._book_d1b
    return CAND_BOOK[name]


def cmd_parity(cand):
    from recalc_agent.read_engine import artifact
    # Baseline is pristine rc4 (branch src carries the D1 probe).
    rc4artifact = load_pristine_artifact()
    book_fn = cand_book(cand)
    rows = []
    for pop, wid in all_workloads():
        src = CLEAN / pop / wid
        books = sorted(src.glob("*.xlsx"))
        assert len(books) == 1, (pop, wid)
        digest = sha_file(books[0])
        apath, status, _ = artifact.ensure(books[0], CACHE / ("parity_%s_%s" % (pop, wid)), digest)
        data = apath.read_bytes()
        b0 = rc4artifact.decode(data, digest)
        real_book = artifact._book
        artifact._book = book_fn
        try:
            b1 = artifact.decode(data, digest)
        finally:
            artifact._book = real_book
        eq = canon_book(b0) == canon_book(b1)
        rows.append({"workload": wid, "population": pop, "canon_equal": eq,
                     "n_cells": sum(len(b0._sheets[n].cells) for n in b0.sheetnames)})
        if not eq:
            print("MISMATCH", pop, wid, flush=True)
    with open(HERE / ("SEMANTIC_PARITY_%s.jsonl" % cand), "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    bad = [r for r in rows if not r["canon_equal"]]
    print("parity: %d/%d equal; mismatches=%d" % (len(rows) - len(bad), len(rows), len(bad)))


def load_pristine_artifact():
    """Load the pristine rc4 artifact module from the control worktree.

    Needed because branch src now carries the in-src D1 probe; the
    baseline must be true rc4. Package inits are trivial (no cycles).
    """
    import importlib.util
    base = Path("/tmp/rc4control/src/recalc_agent")
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


def cmd_bench(cand):
    from recalc_agent.read_engine import artifact
    rc4artifact = load_pristine_artifact()
    book_fn = cand_book(cand)
    wids = list(SUBSET) + ["Template_03_03__c76ea596b408", "Financial_Model_02_01__79352976d750"]
    rows = []
    for wid in wids:
        apath, digest, _ = ensure_artifact(wid)
        data = apath.read_bytes()
        t_base, t_c = [], []
        for _ in range(5):
            t0 = time.perf_counter()
            rc4artifact.decode(data, digest)
            t_base.append(time.perf_counter() - t0)
        real_book = artifact._book
        artifact._book = book_fn
        try:
            for _ in range(5):
                t0 = time.perf_counter()
                artifact.decode(data, digest)
                t_c.append(time.perf_counter() - t0)
        finally:
            artifact._book = real_book
        rows.append({"workload": wid, "candidate": cand,
                     "rc4_decode_s": [round(x, 6) for x in t_base],
                     "cand_decode_s": [round(x, 6) for x in t_c],
                     "rc4_med": round(statistics.median(t_base), 6),
                     "cand_med": round(statistics.median(t_c), 6)})
        print("%s %s: rc4=%.4f cand=%.4f (%.2fx)" % (wid, cand, statistics.median(t_base),
              statistics.median(t_c), statistics.median(t_base) / statistics.median(t_c)), flush=True)
    dest = HERE / ("DECODE_BENCHMARKS_%s.jsonl" % cand)
    with open(dest, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def cmd_coordfuzz():
    import random
    import candidates.d1b as d1b
    from recalc_agent.read_engine.artifact import COORD
    rng = random.Random(20261002)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_!@:."
    cases = set()
    while len(cases) < 200000:
        n = rng.randint(0, 15)
        cases.add("".join(rng.choice(alphabet) for _ in range(n)))
    cases.update(["A1", "XFD1048576", "A0", "A", "1", "AAAA1", "AAAAA1", "A12345678", "A123456789",
                  "a1", " A1", "A1 ", "AA00", "Z9" * 7])
    bad = 0
    for c in cases:
        want = COORD.fullmatch(c) is not None and len(c) <= 12
        # product order: len>12 rejects first, then regex; language = both
        want = (len(c) <= 12) and (COORD.fullmatch(c) is not None)
        if d1b.coord_ok(c) != want:
            bad += 1
            if bad < 5:
                print("FUZZ MISMATCH:", repr(c), flush=True)
    print("coordfuzz: %d cases, mismatches=%d" % (len(cases), bad))


def mutate_valid_artifact():
    """Return (data, digest, raw_payload_bytes, header_dict, offsets) for mutation base."""
    import struct
    from recalc_agent.read_engine import artifact, _identity as ident
    wid = "Template_03_03__c76ea596b408"
    apath, digest, _ = ensure_artifact(wid)
    data = apath.read_bytes()
    hlen = struct.unpack(">I", data[8:12])[0]
    header = json.loads(data[12:12 + hlen])
    offset = 12 + hlen
    clen = struct.unpack(">Q", data[offset:offset + 8])[0]
    raw = zlib.decompress(data[offset + 8:offset + 8 + clen])
    return data, digest, raw, header, {"hlen": hlen, "offset": offset, "clen": clen}


def rebuild(header, raw, magic_ok=True):
    import struct
    from recalc_agent.read_engine import _identity as ident
    from recalc_agent.read_engine.artifact import canonical, sha_bytes
    comp = zlib.compress(raw, level=1)
    header = dict(header)
    header["payload_sha256"] = sha_bytes(raw)
    h = canonical(header)
    body = (ident.MAGIC if magic_ok else b"BADMAGIC") + struct.pack(">I", len(h)) + h \
        + struct.pack(">Q", len(comp)) + comp
    return body + hashlib.sha256(body).digest()


def cmd_corrupt(cand):
    import struct
    from recalc_agent.read_engine import artifact, _identity as ident
    book_fn = cand_book(cand)
    data, digest, raw, header, off = mutate_valid_artifact()
    obj = json.loads(raw)
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
    cases["corrupt_serialized_structure"] = rebuild(header, b"{not json")
    dup = json.loads(raw)
    dup["sheets"][0]["cells"].append(dup["sheets"][0]["cells"][0])
    cases["duplicate_coordinates"] = rebuild(header, json.dumps(dup).encode())
    inv = json.loads(raw)
    inv["sheets"][0]["cells"][0][2] = {"kind": "scalar", "value": float("nan")}
    raw_nan = json.dumps(inv, allow_nan=True).encode()
    comp = zlib.compress(raw_nan, level=1)
    h = dict(header)
    h["payload_sha256"] = hashlib.sha256(raw_nan).hexdigest()
    hb = json.dumps(h, sort_keys=True, separators=(",", ":")).encode()
    body = ident.MAGIC + struct.pack(">I", len(hb)) + hb + struct.pack(">Q", len(comp)) + comp
    cases["nan_typed_value"] = body + hashlib.sha256(body).digest()
    inv2 = json.loads(raw)
    inv2["sheets"][0]["cells"][0][0] = "ZZZ999999999999"
    cases["impossible_coordinate"] = rebuild(header, json.dumps(inv2).encode())
    inv3 = json.loads(raw)
    inv3["sheets"][0]["cells"][0][2] = {"kind": "frobnicate", "value": 1}
    cases["impossible_typed_kind"] = rebuild(header, json.dumps(inv3).encode())

    results = {}
    for name, payload in cases.items():
        row = {}
        for label, fn in (("rc4", None), (cand, book_fn)):
            real = artifact._book
            if fn is not None:
                artifact._book = fn
            try:
                if isinstance(payload, tuple) and payload[0] == "__DIGEST__":
                    artifact.decode(data, payload[1])
                elif isinstance(payload, tuple) and payload[0] == "__HEADERFIELD__":
                    hh = dict(header)
                    hh[payload[1][0]] = payload[1][1]
                    hb = json.dumps(hh, sort_keys=True, separators=(",", ":")).encode()
                    o = off["offset"]
                    b = (ident.MAGIC + struct.pack(">I", len(hb)) + hb
                         + data[o:o + 8 + off["clen"]])
                    artifact.decode(b + hashlib.sha256(b).digest(), digest)
                else:
                    artifact.decode(payload, digest)
                row[label] = "SERVED (BAD)"
            except artifact.ArtifactError as e:
                row[label] = "REJECTED: %s" % str(e)[:60]
            except Exception as e:  # noqa: BLE001
                row[label] = "OTHER-EXC: %s" % type(e).__name__
            finally:
                artifact._book = real
        results[name] = row
        print("%-28s rc4=%-40s %s=%s" % (name, row["rc4"], cand, row[cand]), flush=True)
    bad_rows = {k: v for k, v in results.items()
                if not v["rc4"].startswith("REJECTED") or not v[cand].startswith("REJECTED")}
    with open(HERE / ("CORRUPTION_CASES_%s.json" % cand), "w") as f:
        json.dump({"results": results,
                   "verdict": "PASS" if not bad_rows else "FAIL",
                   "non_rejecting": sorted(bad_rows)}, f, indent=1, sort_keys=True)
    print("corruption verdict:", "PASS" if not bad_rows else "FAIL")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=["parity", "bench", "corrupt", "coordfuzz"], required=True)
    ap.add_argument("--cand", choices=["d1", "d1b"], default="d1")
    args = ap.parse_args()
    if args.step == "coordfuzz":
        cmd_coordfuzz()
    else:
        {"parity": cmd_parity, "bench": cmd_bench, "corrupt": cmd_corrupt}[args.step](args.cand)
