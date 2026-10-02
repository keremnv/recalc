"""Build committed inspection ledgers from I3 raw rows + archives.

Outputs: INSPECTION_LOOP_CENSUS.jsonl, INSPECTION_PRIMITIVE_MAPPING.json.
Mechanical mapping rules; purpose inferred conservatively from code shape.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]

REF_RE = re.compile(r"[A-Z]{1,3}\d{1,7}")


def main():
    man = json.loads((HERE / "WORKLOAD_MANIFEST.json").read_text())
    execs = {}
    with open(ROOT / "research" / "history" / "control_python_audit"
              / "python_executions.jsonl") as f:
        for line in f:
            r = json.loads(line)
            execs[r["exec_id"]] = r
    raw = [json.loads(l) for l in
           open(HERE / "_staging" / "inspection_raw.jsonl")]
    by_script = defaultdict(list)
    for r in raw:
        by_script[(r["population"], r["id"])].append(r)

    census_f = open(HERE / "INSPECTION_LOOP_CENSUS.jsonl", "w")
    prim_hits = defaultdict(list)  # primitive -> list of script refs
    n_scripts = 0
    for (pop, sid), rows in sorted(by_script.items()):
        fams = defaultdict(int)
        for r in rows:
            fams[r["family"]] += 1
        scan_fams = {"SEARCH", "BROAD_INSPECTION", "NESTED_SCAN",
                     "FORMULA_INSPECTION", "PRINT_LOOP", "SEARCH_TEXT_OP"}
        n_scan = sum(v for k, v in fams.items() if k in scan_fams)
        has_mut = fams.get("MUTATION_LOOP", 0) > 0
        has_save = fams.get("SAVE", 0) > 0
        obs_bytes = None
        task = rows[0]["task"]
        if pop == "Cuniverse":
            eid = int(sid.split("_")[1])
            obs_bytes = execs[eid].get("observation_bytes")
        # Candidate primitive mapping (mechanical, conservative).
        mapped = set()
        for r in rows:
            ev = r.get("evidence", "")
            if r["family"] == "SEARCH":
                mapped.add("find_text")
                prim_hits["find_text"].append((pop, sid, task))
            elif r["family"] == "SEARCH_TEXT_OP":
                mapped.add("find_text")
            elif r["family"] in ("BROAD_INSPECTION", "NESTED_SCAN"):
                mapped.add("sparse_range_values")
                prim_hits["sparse_range_values"].append((pop, sid, task))
                if "print(" in ev:
                    mapped.add("inspect_neighborhood")
            elif r["family"] == "FORMULA_INSPECTION":
                mapped.add("formula_regions")
                prim_hits["formula_regions"].append((pop, sid, task))
                if REF_RE.search(ev) and ("==" in ev or " in " in ev):
                    mapped.add("reference_search")
                    prim_hits["reference_search"].append((pop, sid, task))
            elif r["family"] == "PRINT_LOOP":
                b = (r.get("detail") or {}).get("range_bound")
                if b is not None and b <= 40:
                    mapped.add("inspect_neighborhood")
                    prim_hits["inspect_neighborhood"].append((pop, sid, task))
                else:
                    mapped.add("sparse_range_values")
            elif r["family"] == "POSSIBLE_WORKBOOK_COMPARE":
                mapped.add("diff_workbooks")
                prim_hits["diff_workbooks"].append((pop, sid, task))
            elif r["family"] == "REOPEN_AFTER_SAVE":
                mapped.add("changed_cells")
                prim_hits["changed_cells"].append((pop, sid, task))
        census_f.write(json.dumps({
            "population": pop, "id": sid, "task": task,
            "families": dict(sorted(fams.items())),
            "n_scan_loops": n_scan, "has_mutation": has_mut,
            "has_save": has_save, "archived_observation_bytes": obs_bytes,
            "candidate_primitives": sorted(mapped),
        }, sort_keys=True) + "\n")
        n_scripts += 1
    census_f.close()

    prim_meta = {
        "find_text": {"risk": "L0", "needs_state": "none beyond read state",
                      "exact": True},
        "sparse_range_values": {"risk": "L1", "needs_state": "read state",
                                "exact": True},
        "inspect_neighborhood": {"risk": "L1", "needs_state": "read state",
                                 "exact": True},
        "formula_regions": {"risk": "L1", "needs_state": "formula presence",
                            "exact": True},
        "reference_search": {"risk": "L2", "needs_state": "formula text index",
                             "exact": True},
        "diff_workbooks": {"risk": "L2", "needs_state": "two read states",
                           "exact": True},
        "changed_cells": {"risk": "L2", "needs_state": "before/after states",
                          "exact": True},
    }
    mapping = {}
    for prim, hits in prim_hits.items():
        scripts = sorted({(p, s) for p, s, _ in hits})
        tasks = sorted({t for _, _, t in hits})
        # observation mass for C-universe hits (mechanical proxy)
        obs = []
        for p, s, t in hits:
            if p == "Cuniverse":
                b = execs[int(s.split("_")[1])].get("observation_bytes")
                if b:
                    obs.append(b)
        mapping[prim] = dict(prim_meta[prim],
                             loop_instances=len(hits),
                             scripts=len(scripts),
                             tasks=len(tasks),
                             archived_obs_bytes_sum=sum(obs),
                             archived_obs_bytes_max=max(obs) if obs else 0)
    (HERE / "INSPECTION_PRIMITIVE_MAPPING.json").write_text(
        json.dumps(mapping, indent=1, sort_keys=True) + "\n")
    print("scripts:", n_scripts, "primitives:", len(mapping))


if __name__ == "__main__":
    main()
