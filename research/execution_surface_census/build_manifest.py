"""Build WORKLOAD_MANIFEST.json for the execution-surface census.

Populations A/B: frozen pre-tidy RC identities (scripts + hashes verified).
Population C: mechanical round-robin sample over control-audit purpose strata.
No outcome inspection: selection uses labels/IDs only.
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path(__file__).parent / "_staging" / "rc_acceleration_validation"
AUDIT = ROOT / "research" / "history" / "control_python_audit"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    manifest = json.loads((STAGE / "workload_manifest.json").read_text())
    cands = {c["workload_id"]: c for c in manifest["all_candidates"]}
    elig = json.loads((STAGE / "eligible_population.json").read_text())["workload_ids"]
    rep = json.loads((STAGE / "representative_population.json").read_text())["workload_ids"]

    def entry(wid, pop):
        c = cands[wid]
        sp = STAGE / "workloads" / (wid + ".py")
        assert sp.exists(), wid
        assert sha_file(sp) == c["script_sha256"], wid
        wb = Path(c["workbook_path"])
        assert wb.exists(), (wid, c["workbook_path"])
        return {
            "population": pop,
            "workload_id": wid,
            "family": c["family"],
            "task": c["task"],
            "script_sha256": c["script_sha256"],
            "workbook_sha256": c["workbook_sha256"],
            "workbook_bytes": wb.stat().st_size,
            "a1_decision_archived": c["a1_decision"],
            "control_read_class_archived": c.get("control_read_class"),
        }

    pop_a = [entry(w, "A") for w in sorted(rep)]
    pop_b = [entry(w, "B") for w in sorted(elig)]

    # Population C: mechanical stratified round-robin (prereg §3).
    purposes = {}
    with open(AUDIT / "purpose_classification.jsonl") as f:
        for line in f:
            r = json.loads(line)
            purposes[r["exec_id"]] = tuple(sorted(r["labels"]))
    universe = []
    with open(AUDIT / "python_executions.jsonl") as f:
        for line in f:
            r = json.loads(line)
            if r["action_kind"] != "python_heredoc" or not r.get("source"):
                continue
            if r["population"] == "P-C_viz":
                continue
            universe.append(r)
    strata = defaultdict(list)
    for r in universe:
        strata[purposes[r["exec_id"]]].append(r)
    for k in strata:
        strata[k].sort(key=lambda r: (r["task_id"], r["exec_id"]))
    order = sorted(strata)
    selected, per_task = [], defaultdict(int)
    cap, target = 4, 120
    while True:
        # Round-robin with per-stratum cursors.
        cursors = {k: 0 for k in order}
        remaining = True
        while len(selected) < target and remaining:
            remaining = False
            for key in order:
                rows = strata[key]
                i = cursors[key]
                while i < len(rows) and per_task[rows[i]["task_id"]] >= cap:
                    i += 1
                cursors[key] = i
                if i < len(rows):
                    remaining = True
                    r = rows[i]
                    cursors[key] = i + 1
                    per_task[r["task_id"]] += 1
                    selected.append(r)
                    if len(selected) >= target:
                        break
        tasks = {r["task_id"] for r in selected}
        if len(tasks) < 50 and cap == 4:
            cap = 6
            selected, per_task = [], defaultdict(int)
            continue
        break

    pop_c = []
    for r in selected:
        src = r["source"]
        pop_c.append({
            "population": "C",
            "exec_id": r["exec_id"],
            "task_id": r["task_id"],
            "family": r["family"],
            "turn": r["turn"],
            "purpose_labels": list(purposes[r["exec_id"]]),
            "script_sha256": hashlib.sha256(src.encode()).hexdigest(),
            "script_bytes": len(src.encode()),
            "archived_execution_time_s": r.get("execution_time_s"),
            "archived_observation_bytes": r.get("observation_bytes"),
        })

    out = {
        "populations": {
            "A": {"n": len(pop_a), "rule": "frozen representative_population.json (pre-tidy 554dc00)",
                  "workloads": pop_a},
            "B": {"n": len(pop_b), "rule": "frozen eligible_population.json (pre-tidy 554dc00)",
                  "workloads": pop_b},
            "C": {"n": len(pop_c),
                  "rule": "round-robin over purpose-label strata, (task_id,exec_id) order, task cap %d" % cap,
                  "distinct_tasks": len({r["task_id"] for r in selected}),
                  "strata": len(order),
                  "workloads": pop_c},
        }
    }
    dest = Path(__file__).parent / "WORKLOAD_MANIFEST.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print("A=%d B=%d C=%d tasks=%d strata=%d cap=%d" % (
        len(pop_a), len(pop_b), len(pop_c), out["populations"]["C"]["distinct_tasks"],
        len(order), cap))


if __name__ == "__main__":
    main()
