"""Aggregate census telemetry into committed compact ledgers.

Reads _staging/telemetry/*.jsonl, writes:
  OPERATION_CENSUS.jsonl, COST_DECOMPOSITION.jsonl,
  INSPECTION_LOOP_CENSUS.jsonl, PARITY_REPORT.json
Also prints gate verdicts G2-G5.
"""
import io
import json
import re
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
TELE = HERE / "_staging" / "telemetry"
STAGED = HERE / "_staging" / "staged"

_TS = re.compile(rb"<dcterms:(modified|created)[^>]*>[^<]*</dcterms:\1>")


def norm_xlsx(raw):
    """Normalize volatile package metadata (timestamps) for comparison."""
    try:
        zin = zipfile.ZipFile(io.BytesIO(raw))
        names = zin.namelist()
        if "docProps/core.xml" not in names:
            return raw
        core = zin.read("docProps/core.xml")
        core_n = _TS.sub(lambda m: m.group(0)[: m.group(0).index(b">") + 1] + b"TS" + m.group(0)[m.group(0).rindex(b"<"):], core)
        # Rebuild deterministically: sorted names, fixed date_time.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for n in sorted(names):
                data = core_n if n == "docProps/core.xml" else zin.read(n)
                zi = zipfile.ZipInfo(n, date_time=(2020, 1, 1, 0, 0, 0))
                zout.writestr(zi, data)
        import hashlib
        return hashlib.sha256(buf.getvalue()).hexdigest()
    except Exception:
        import hashlib
        return "RAW:" + hashlib.sha256(raw).hexdigest()


def staged_state(kind, wid, arm, rep):
    d = STAGED / kind / wid / ("rep%d_%s" % (rep, arm))
    out = {}
    if not d.exists():
        return None
    for p in sorted(d.rglob("*.xlsx")):
        try:
            out[str(p.relative_to(d))] = norm_xlsx(p.read_bytes())
        except OSError:
            out[str(p.relative_to(d))] = "UNREADABLE"
    return out

# operation family -> class A-F (task sec 7)
CLASS = {
    # A: already Recalc-owned (when admitted; verified per-row)
    "sheet_enumeration": "A?", "sheet_lookup": "A?", "cell_getitem": "A?",
    "cell_call": "A?", "cell_value_get": "A?", "data_type_get": "A?",
    "bounds": "A?", "dimensions": "A?",
    # B: small plausible extension (read-only, no rich fidelity)
    "iter_rows": "B?", "iter_cols": "B?", "values": "B?",
    "worksheet_iteration": "B?", "workbook_iteration": "B?",
    "active_sheet": "B?", "cell_value_set": "C",
    # C: mutation ownership
    "cell_assign_getitem": "C", "row_append": "C", "row_ops": "C",
    "sheet_create": "C", "sheet_delete": "C", "save": "C",
    # E: rich fidelity
    "merged_access": "E?", "tables": "E", "defined_names": "E",
    "close": "F",
}


def load_all(pattern="runs_*.jsonl"):
    rows = []
    for p in sorted(TELE.glob(pattern)):
        with open(p) as f:
            for line in f:
                rows.append(json.loads(line))
    return rows


def parity_report(rows):
    by = defaultdict(dict)
    for r in rows:
        by[(r["kind"], r["workload"], r["rep"])][r["arm"]] = r
    rep = {"pairs": len(by), "mismatch": [], "overhead": [],
           "nondeterministic": [], "admission_changes": []}
    for key, arms in sorted(by.items()):
        if set(arms) != {"BASE", "HOOK", "PROD", "HOOKPROD"}:
            rep["mismatch"].append({"key": key, "why": "missing arm"})
            continue
        b, h, p, hp = (arms[a] for a in ("BASE", "HOOK", "PROD", "HOOKPROD"))
        states = [staged_state(r["kind"], r["workload"], r["arm"], r["rep"])
                  for r in (b, h, p, hp)]
        state_eq = (None not in states and states[0] == states[1] == states[2] == states[3])
        ok = (b["exit"] == h["exit"] == p["exit"] == hp["exit"]
              and b["stdout_norm_sha256"] == h["stdout_norm_sha256"]
              == p["stdout_norm_sha256"] == hp["stdout_norm_sha256"]
              and state_eq)
        if not ok:
            rep["mismatch"].append({
                "key": [str(key[0]), key[1]],
                "exit": [b["exit"], h["exit"], p["exit"], hp["exit"]],
                "stdout": [b["stdout_norm_sha256"][:8], h["stdout_norm_sha256"][:8],
                           p["stdout_norm_sha256"][:8], hp["stdout_norm_sha256"][:8]],
                "state_eq": state_eq,
                "state_raw_eq": b["state"] == h["state"] == p["state"] == hp["state"]})
        # G3: admission/route identity PROD vs HOOKPROD
        ps, hs = p["receipt"].get("setup.json", {}), hp["receipt"].get("setup.json", {})
        pr, hr = p["receipt"].get("runtime_state.json", {}), hp["receipt"].get("runtime_state.json", {})
        if ((ps.get("admitted"), ps.get("route"), pr.get("route"),
             (pr.get("counts") or {}).get("direct_served_loads"))
                != (hs.get("admitted"), hs.get("route"), hr.get("route"),
                    (hr.get("counts") or {}).get("direct_served_loads"))):
            rep["admission_changes"].append([str(key[0]), key[1]])
        rep["overhead"].append({"key": [str(key[0]), key[1]],
                               "hook_minus_base_s": h["wall_s"] - b["wall_s"],
                               "base_s": b["wall_s"]})
    # G5 determinism: BASE rep0 vs rep1
    base = defaultdict(dict)
    for r in rows:
        if r["arm"] == "BASE":
            base[(r["kind"], r["workload"])][r["rep"]] = r
    for w, reps in base.items():
        if 0 in reps and 1 in reps:
            a, c = reps[0], reps[1]
            sa = staged_state(a["kind"], a["workload"], "BASE", 0)
            sc = staged_state(c["kind"], c["workload"], "BASE", 1)
            if not (a["exit"] == c["exit"] and a["stdout_norm_sha256"] == c["stdout_norm_sha256"]
                    and sa is not None and sa == sc):
                rep["nondeterministic"].append(w)
    return rep


def main():
    rows = load_all()
    print("telemetry rows:", len(rows))
    if not rows:
        return
    rep = parity_report(rows)
    (HERE / "_staging" / "parity.json").write_text(json.dumps(rep, indent=1))
    print("pairs:", rep["pairs"], "mismatches:", len(rep["mismatch"]),
          "admission_changes:", len(rep["admission_changes"]),
          "nondeterministic:", len(rep["nondeterministic"]))
    for m in rep["mismatch"][:10]:
        print("  MISMATCH", m)
    ov = [o["hook_minus_base_s"] for o in rep["overhead"]]
    if ov:
        print("overhead median: %.4fs  p90: %.4fs  max: %.4fs" % (
            statistics.median(ov), sorted(ov)[int(len(ov) * 0.9)],
            max(ov)))


if __name__ == "__main__":
    main()
