"""Token and call cost of the two arms, counted from the sessions themselves.

P1's canonical session *is* one of P0's sessions, byte for byte -- the arms share
the seed session and every member session P1 uses is a session P0 also ran. So
the cost comparison is not an estimate: it is the same set of session files,
summed over two different subsets. P1 pays for the canonical member of each
group plus every member that no group claimed; P0 pays for all of them.
"""
from __future__ import annotations

import json

import end_to_end_composition_probe as old
import execution_unit_probe as P
import program_group_probe as C

FIELDS = ("retrieval_input_tokens", "retrieval_output_tokens",
          "synthesis_input_tokens", "synthesis_output_tokens")


def _index() -> dict:
    """Every session this probe could have used, keyed by task and cell."""
    idx = {}
    for d in (C.OUT / "sessions", P.OUT / "sessions"):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            s = json.loads(p.read_text())
            cell = s.get("cell")
            if not cell:
                continue
            task = p.name.split("__")[0]
            idx.setdefault((task, tuple(cell)), s)
    return idx


def _tokens(s: dict) -> dict:
    return {f: int(s.get(f) or 0) for f in FIELDS}


def run() -> dict:
    idx = _index()
    units, totals = [], {"P0": {f: 0 for f in FIELDS}, "P1": {f: 0 for f in FIELDS}}
    calls = {"P0": 0, "P1": 0}
    for p in sorted((C.OUT / "units").glob("*.json")):
        rec = json.loads(p.read_text())
        task = rec["unit"]["task"]
        members = rec["members"]
        by_addr = dict(zip(members, [tuple(c) for c in rec["member_cells"]]))
        canon = {g["canonical_member"] for g in rec["program_groups"]}
        grouped = set(rec["members_in_a_group"])
        p1_members = [m for m in members if m in canon or m not in grouped]
        row = {"task": task, "seed": rec["unit"]["seed"],
               "P0_sessions": 0, "P1_sessions": 0,
               "P0": {f: 0 for f in FIELDS}, "P1": {f: 0 for f in FIELDS},
               "sessions_missing": []}
        for arm, ms in (("P0", members), ("P1", p1_members)):
            for m in ms:
                s = idx.get((task, by_addr[m]))
                if s is None:
                    row["sessions_missing"].append([arm, m])
                    continue
                row[f"{arm}_sessions"] += 1
                calls[arm] += 1
                for f, v in _tokens(s).items():
                    row[arm][f] += v
                    totals[arm][f] += v
        units.append(row)
    for arm in ("P0", "P1"):
        totals[arm]["total_input_tokens"] = (totals[arm]["retrieval_input_tokens"]
                                             + totals[arm]["synthesis_input_tokens"])
        totals[arm]["total_output_tokens"] = (totals[arm]["retrieval_output_tokens"]
                                              + totals[arm]["synthesis_output_tokens"])
        totals[arm]["member_sessions"] = calls[arm]
    out = {"units": units, "totals": totals,
           "note": "P1 sessions are a subset of P0 sessions; no session is unique to P1."}
    old.write(C.OUT / "phase_c_cost.json", out)
    return out


if __name__ == "__main__":
    o = run()
    print(json.dumps(o["totals"], indent=1))
    miss = [u for u in o["units"] if u["sessions_missing"]]
    if miss:
        print("MISSING", json.dumps([[u["seed"], u["sessions_missing"]] for u in miss]))
