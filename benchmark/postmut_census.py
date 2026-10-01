#!/usr/bin/env python3
"""Zero-model post-mutation verification/repair/reopen census.

Parses the frozen default-control trajectory corpus (historical .traj via
control_python_audit linearization + live reps) into mutation -> post-mutation
episodes, classifies post-mutation actions with deterministic heuristics,
measures self-readback overlap, follow-through, and replaceability.

Usage: python3 benchmark/postmut_census.py
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUD = PROJECT_ROOT / "post_mutation_verification_audit"
CTRL = PROJECT_ROOT / "control_python_audit"

# ---------- address extraction ----------
WS_SUB = re.compile(r"""\w+\[\s*["']([A-Za-z]{1,3}\d{1,7})["']\s*\]""")
CELL_RC = re.compile(r"\.cell\(\s*(\d{1,7})\s*,\s*(\d{1,4})\s*\)")
WB_SHEET = re.compile(r"""\w+\[\s*["']([^"']+)["']\s*\]""")
ASSIGN = re.compile(r"=\s*(?!=)")
FORMULA_LIT = re.compile(r"""=\s*["']=(.*?)["']""")


def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def extract_writes(src: str) -> tuple[set[str], set[str]]:
    """Return (value_addrs, formula_addrs) as bare A1 addresses (sheet
    association is approximate; see sheet_of)."""
    vals, fms = set(), set()
    for m in WS_SUB.finditer(src):
        addr = m.group(1).upper()
        after = src[m.end():m.end() + 120]
        am = ASSIGN.search(after.split("\n")[0] if "\n" in after else after)
        if not am:
            continue
        rhs = after[am.end():am.end() + 60].strip()
        (fms if rhs.startswith(("'=", '"=')) else vals).add(addr)
    for m in CELL_RC.finditer(src):
        addr = f"{col_letter(int(m.group(2)))}{m.group(1)}"
        after = src[m.end():m.end() + 160]
        if ".value" in after.split("\n")[0][:60] and ASSIGN.search(after):
            rhs = after.split("=", 1)[1][:40].strip() if "=" in after else ""
            (fms if rhs.startswith(("'=", '"=')) else vals).add(addr)
    return vals, fms


RANGE_FOR = re.compile(r"for\s+(\w+)\s+in\s+range\(\s*(\d+)\s*,\s*(\d+)\s*\)")
DYNAMIC_CELL = re.compile(r"\.cell\(\s*[^0-9\s]|\w+\[\s*f['\"]|\w+\[\s*['\"][^'\"]*\{|\w+\[\s*\w+\s*\+|for\s+\w+\s+in\s+\w+\s*:\s*\n?.{0,80}\.value\s*=(?!=)")


def has_dynamic_writes(src: str) -> bool:
    return bool(DYNAMIC_CELL.search(src))


def expand_range_writes(src: str) -> set[str]:
    """Expand the common single-var case: for c in range(a,b): ...cell(r,c).value= / cell(c,k)."""
    out: set[str] = set()
    for m in RANGE_FOR.finditer(src):
        var, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        if b - a > 500:
            continue
        tail = src[m.end():m.end() + 2000]
        for cm in re.finditer(r"\.cell\(\s*(\d+|\w+)\s*,\s*(\d+|\w+)\s*\)\s*\.value\s*=(?!=)", tail):
            r, c = cm.group(1), cm.group(2)
            try:
                if r == var and c.isdigit():
                    for rr in range(a, b):
                        out.add(f"{col_letter(int(c))}{rr}")
                elif c == var and r.isdigit():
                    for cc in range(a, b):
                        out.add(f"{col_letter(cc)}{r}")
            except ValueError:
                continue
    return out


def extract_reads(src: str) -> set[str]:
    """Addresses appearing in non-assignment position (prints, comparisons)."""
    reads = set()
    for m in WS_SUB.finditer(src):
        after = src[m.end():m.end() + 40].split("\n")[0]
        if not ASSIGN.match(after.strip()[:3]):
            reads.add(m.group(1).upper())
    for m in CELL_RC.finditer(src):
        after = src[m.end():m.end() + 120].split("\n")[0]
        if ".value" in after[:40] and not re.search(r"\.value\s*=(?!=)", after[:60]):
            reads.add(f"{col_letter(int(m.group(2)))}{m.group(1)}")
    return reads


# ---------- action classification ----------
def classify_post_action(kind: str, src: str, obs: str, head: str) -> list[str]:
    """Deterministic Phase-1 classes. src=head command text for shell actions."""
    low = (src + "\n" + head).lower()
    labels: list[str] = []
    blob = src if src else head
    if kind == "view_xlsx" or low.startswith("view_xlsx"):
        labels.append("VIEW_XLSX")
        return labels
    if "soffice" in low or "libreoffice" in low or "--convert-to" in low:
        labels.append("LIBREOFFICE_CONVERT" if "convert" in low else "LIBREOFFICE_RECALC")
        return labels
    if kind in ("submit",) or low.startswith("submit"):
        labels.append("SUBMISSION_PREP")
        return labels
    if "unzip -l" in low or ("xl/" in low and re.search(r"\bgrep\b", low)):
        labels.append("PACKAGE_XML_INSPECTION")
    if re.search(r"sed\s+-i.*\.py\b", low):
        return ["SCRIPT_PATCH_RERUN"]
    if re.search(r"python3\s+/tmp/\S+\.py", low) and not src:
        labels.append("AMBIGUOUS_FILE_RUN")
    if re.search(r"pip\s+install|apt(-get)?\s+install", low):
        labels.append("ENV_SETUP")
    if "site-packages" in low and re.search(r"\bsed\b|\bcat\b|\bgrep\b", low):
        labels.append("LIBRARY_SOURCE_READING")
    if labels and not src:
        return labels
    if not src and kind == "shell_other":
        if re.search(r"\b(ls|dir|stat|du|test|if.*-f|os\.path\.exists|exists)\b", low):
            labels.append("FILE_EXISTENCE_CHECK")
        if re.search(r"\bcp\b.*output|submit", low):
            labels.append("SUBMISSION_PREP")
        if "dump.txt" in low or (re.search(r"\bgrep\b|\bawk\b", low) and "!" in low):
            labels.append("DUMP_TEXT_SEARCH")
        return labels or ["SHELL_OTHER"]
    if src and "openpyxl" not in low and "lx_helpers" not in low and re.search(r"^[\d\s()+\-*/. ]+$", src.replace("python3 -c", "").strip().strip("\"'")):
        return ["ARITHMETIC_CHECK"]
    has = lambda *ws: any(w in low for w in ws)  # noqa: E731
    if "load_workbook" in low:
        labels.append("RELOAD_DATA_ONLY" if "data_only=true" in low.replace(" ", "") else "REOPEN_WORKBOOK")
    if has("#ref", "#value", "#name?", "#div", "#n/a", ".error", "errors"):
        labels.append("ERROR_SCAN")
    if re.search(r"startswith\(['\"]=", low) or ("formula" in low and ("iter_rows" in low or "for " in low)):
        labels.append("FORMULA_SCAN")
    if has("number_format", "font", "fill", "alignment", "border", "_style"):
        labels.append("STYLE_CHECK")
    if has("max_row", "max_column", "dimensions", "merged_cells"):
        labels.append("DIMENSION_CHECK")
    if "sheetnames" in low or " in wb" in low or "has_sheet" in low:
        labels.append("SHEET_EXISTENCE_CHECK")
    if re.search(r"\.save\(", low):
        labels.append("SAVE_CHECK")
    if re.search(r"assert|==\s*\d|expected", low):
        labels.append("MANUAL_EXPECTED_VALUE_CHECK")
    if "print" in low or "ws[" in src or ".cell(" in src:
        labels.append("RANGE_PRINT" if ("iter_rows" in low or "range(" in low) else "CELL_READ")
    return labels or ["UNCLASSIFIED_READ"]


# ---------- corpus loading ----------
def extract_dash_c(action: str) -> str | None:
    """Recover a `python3 -c "..."` body with backslash-escape scanning."""
    i = action.find("python3")
    if i < 0:
        return None
    j = action.find("-c", i)
    if j < 0:
        return None
    k = action.find('"', j)
    if k < 0:
        return None
    buf, p = [], k + 1
    while p < len(action):
        ch = action[p]
        if ch == "\\" and p + 1 < len(action):
            buf.append(action[p + 1])
            p += 2
            continue
        if ch == '"':
            return "".join(buf)
        buf.append(ch)
        p += 1
    return None


def load_historical() -> list[dict]:
    """Linearized historical execs joined with purpose labels + full .traj actions."""
    ex = [json.loads(l) for l in open(CTRL / "python_executions.jsonl")]
    labels = {}
    for line in open(CTRL / "purpose_classification.jsonl"):
        p = json.loads(line)
        labels[p["exec_id"]] = p["labels"]
    pop = json.load(open(CTRL / "population.json"))
    traj_steps: dict[tuple[str, str], list] = {}
    for p in ("P-A_matched_c0", "P-B_sixty_control", "P-C_viz"):
        for r in pop[p]:
            traj_steps[(p, r["task_id"])] = json.load(open(r["traj"]))["trajectory"]
    out = []
    for e in ex:
        steps = traj_steps[(e["population"], e["task_id"])]
        full_action = steps[e["turn"]].get("action", "") if e["turn"] < len(steps) else ""
        src = e.get("source") or ""
        kind = e["action_kind"]
        if not src and "python3" in full_action and "-c" in full_action:
            body = extract_dash_c(full_action)
            if body:
                src = body
                kind = "python_inline"
        out.append({
            "pop": e["population"], "task": e["task_id"], "fam": e["family"],
            "turn": e["turn"], "kind": kind,
            "src": src, "head": full_action[:500],
            "obs_bytes": e.get("observation_bytes", 0),
            "script_bytes": len(src) or e.get("script_bytes", 0),
            "script_loc": (src.count("\n") + 1) if src else e.get("script_loc", 0),
            "labels": labels.get(e["exec_id"], []),
            "exec_id": e["exec_id"], "live": False, "truncated": False,
            "run": e["population"] + "|" + e["task_id"],
        })
    return out


def parse_live_transcript(tf: Path) -> list[dict]:
    """Assistant tool calls paired with next user observation."""
    steps, pending = [], None
    for line in tf.read_text().splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls") or []:
                if isinstance(tc, dict) and "function" in tc:
                    fn = tc.get("function") or {}
                    name = fn.get("name", "") if isinstance(fn, dict) else ""
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except ValueError:
                        args = {}
                else:  # redacted transcript shape: {"name","args"}
                    name = tc.get("name", "") if isinstance(tc, dict) else ""
                    a = tc.get("args", "") if isinstance(tc, dict) else ""
                    try:
                        args = json.loads(a) if isinstance(a, str) else {}
                    except ValueError:
                        args = {"command": a}
                    if "command" not in args and isinstance(a, str):
                        args = {"command": a}
                pending = {"tool": name, "args": args, "obs": ""}
                steps.append(pending)
        elif m.get("role") == "user" and pending is not None and not pending["obs"]:
            c = m.get("content", "")
            pending["obs"] = c if isinstance(c, str) else json.dumps(c)
            pending = None
    return steps


MUT_VERBS = ("python", "openpyxl", ".save(", "soffice", "libreoffice")


def load_live() -> list[dict]:
    out = []
    reps = [
        ("live_transparent_runtime_ab/runs/*/*", True),
        ("targeted_runtime_replication/reps/*", True),
        ("inspection_efficiency_ab/reps/*", True),
        ("batch_write_helper_ab/reps/*", True),
    ]
    import glob as _g
    for pat, _ in reps:
        for rep in sorted(_g.glob(str(PROJECT_ROOT / pat))):
            rp = Path(rep)
            rr = rp / "run_record.json"
            if not rr.exists():
                continue
            rec = json.loads(rr.read_text())
            tf = rp / "transcript_full.jsonl"
            trunc = False
            if not tf.exists():
                tf = rp / "transcript.jsonl"
                trunc = True
            if not tf.exists():
                continue
            mut_calls = {e["call"] for e in rec.get("boundary_events", [])
                         if e.get("event") == "WORKBOOK_MUTATION"}
            steps = parse_live_transcript(tf)
            call_idx = 0
            for s in steps:
                if s["tool"] == "bash":
                    call_idx += 1
                    cmd = str(s["args"].get("command", ""))
                    src = cmd if "python" in cmd else ""
                    out.append({
                        "pop": rp.parent.name, "task": rec.get("task_id", rp.name),
                        "fam": rec.get("family", ""), "turn": call_idx,
                        "kind": "python_heredoc" if src else "shell_other",
                        "src": src, "head": cmd[:300], "obs_bytes": len(s["obs"]),
                        "script_bytes": len(src), "script_loc": src.count("\n") + 1 if src else 0,
                        "labels": [], "exec_id": f"{rp.name}#{call_idx}",
                        "live": True, "truncated": trunc,
                        "is_mutation_event": call_idx in mut_calls,
                        "run": rp.parent.name + "|" + rp.name,
                        "status": rec.get("status"),
                    })
                elif s["tool"] == "view_xlsx":
                    out.append({
                        "pop": rp.parent.name, "task": rec.get("task_id", rp.name),
                        "fam": rec.get("family", ""), "turn": -1,
                        "kind": "view_xlsx", "src": "",
                        "head": "view_xlsx " + json.dumps(s["args"])[:200],
                        "obs_bytes": len(s["obs"]), "script_bytes": 0,
                        "script_loc": 0, "labels": [], "exec_id": f"{rp.name}#v",
                        "live": True, "truncated": trunc,
                        "is_mutation_event": False, "status": rec.get("status"),
                        "run": rp.parent.name + "|" + rp.name,
                    })
                elif s["tool"] == "submit":
                    out.append({
                        "pop": rp.parent.name, "task": rec.get("task_id", rp.name),
                        "fam": rec.get("family", ""), "turn": 10 ** 9,
                        "kind": "submit", "src": "", "head": "submit",
                        "obs_bytes": 0, "script_bytes": 0, "script_loc": 0,
                        "labels": ["SUBMISSION_PREP"], "exec_id": f"{rp.name}#s",
                        "live": True, "truncated": trunc,
                        "is_mutation_event": False, "status": rec.get("status"),
                        "run": rp.parent.name + "|" + rp.name,
                    })
    # sequence index per run (transcript order)
    by_run: dict[str, int] = defaultdict(int)
    for e in out:
        e["seq"] = by_run[e["run"]]
        by_run[e["run"]] += 1
    return out


def is_mutation(e: dict) -> bool:
    if e.get("is_mutation_event"):
        return True
    if "MUTATION" in e["labels"]:
        return True
    src = e["src"]
    if not src:
        return False
    v, f = extract_writes(src)
    if ((v or f) or has_dynamic_writes(src)) and ".save(" in src.lower():
        return True
    # writes without explicit save in truncated live commands still count
    # when the runtime observed a mutation (handled above); otherwise require save
    return False


def build_episodes(execs: list[dict]) -> list[dict]:
    runs: dict[str, list[dict]] = defaultdict(list)
    for e in execs:
        runs[e["run"]].append(e)
    episodes = []
    for run, steps in runs.items():
        steps = sorted(steps, key=lambda e: (e["seq"] if e["live"] else e["turn"]))
        mut_idx = [i for i, e in enumerate(steps) if is_mutation(e)]
        for k, mi in enumerate(mut_idx):
            post = []
            nxt = None
            for j in range(mi + 1, len(steps)):
                if steps[j]["kind"] == "submit":
                    nxt = "submit"
                    break
                if is_mutation(steps[j]):
                    nxt = "mutation"
                    break
                post.append(steps[j])
            else:
                nxt = "termination"
            m = steps[mi]
            v, f = extract_writes(m["src"])
            dyn = has_dynamic_writes(m["src"]) if m["src"] else False
            if dyn:
                v |= expand_range_writes(m["src"])
            episodes.append({
                "run": run, "task": m["task"], "fam": m["fam"],
                "live": m["live"], "truncated": m.get("truncated", False),
                "mut_seq": k, "mut_turn": m["turn"],
                "mut_bytes": m["script_bytes"], "mut_loc": m["script_loc"],
                "write_vals": sorted(v)[:2000], "write_fms": sorted(f)[:2000],
                "n_write_vals": len(v), "n_write_fms": len(f),
                "dynamic_writes": dyn,
                "post": post, "terminator": nxt,
            })
    return episodes


def classify_episode_actions(ep: dict) -> list[dict]:
    out = []
    written = set(ep["write_vals"]) | set(ep["write_fms"])
    for pos, e in enumerate(ep["post"]):
        classes = classify_post_action(e["kind"], e["src"], "", e["head"])
        reads = extract_reads(e["src"]) if e["src"] else set()
        # refine CELL_READ / RANGE_PRINT into READ_BACK_* when overlapping writes
        overlap = reads & written
        if overlap and ("CELL_READ" in classes or "RANGE_PRINT" in classes):
            if overlap & set(ep["write_fms"]):
                classes.append("READ_BACK_WRITTEN_FORMULAS")
            if overlap & set(ep["write_vals"]):
                classes.append("READ_BACK_WRITTEN_CELLS")
        only_written = bool(overlap) and reads <= written
        out.append({
            "run": ep["run"], "task": ep["task"], "fam": ep["fam"],
            "mut_seq": ep["mut_seq"], "pos": pos, "turn": e["turn"],
            "head": e["head"][:200], "classes": classes,
            "kind": e["kind"], "reads": sorted(reads),
            "overlap_written": sorted(overlap),
            "only_written": only_written,
            "script_bytes": e["script_bytes"], "script_loc": e["script_loc"],
            "obs_bytes": e["obs_bytes"], "purpose_labels": e["labels"],
            "live": e["live"], "truncated": e.get("truncated", False),
        })
    return out


# question class -> mechanical/semantic verdict + runtime availability
AVAIL = {
    # class: (question_domain, replaceability_verdict, availability)
    "REOPEN_WORKBOOK": ("STRUCTURAL", "NOT_REPLACEABLE", "REQUIRES_REOPEN"),
    "RELOAD_DATA_ONLY": ("RECALC", "NOT_REPLACEABLE", "REQUIRES_LIBREOFFICE"),
    "READ_BACK_WRITTEN_CELLS": ("PERSISTENCE", "EXACTLY_REPLACEABLE", "ALREADY_AVAILABLE_EXACTLY"),
    "READ_BACK_WRITTEN_FORMULAS": ("PERSISTENCE", "EXACTLY_REPLACEABLE", "ALREADY_AVAILABLE_EXACTLY"),
    "RANGE_PRINT": ("MIXED", "PARTIALLY_REPLACEABLE", "AVAILABLE_WITH_SMALL_DETERMINISTIC_DERIVATION"),
    "CELL_READ": ("MIXED", "PARTIALLY_REPLACEABLE", "AVAILABLE_WITH_SMALL_DETERMINISTIC_DERIVATION"),
    "VIEW_XLSX": ("MIXED", "NOT_REPLACEABLE", "REQUIRES_REOPEN"),
    "FORMULA_SCAN": ("STRUCTURAL", "PARTIALLY_REPLACEABLE", "AVAILABLE_WITH_SMALL_DETERMINISTIC_DERIVATION"),
    "ERROR_SCAN": ("RECALC", "PARTIALLY_REPLACEABLE", "AVAILABLE_WITH_SMALL_DETERMINISTIC_DERIVATION"),
    "PRE_POST_DIFF": ("STRUCTURAL", "EXACTLY_REPLACEABLE", "ALREADY_AVAILABLE_EXACTLY"),
    "VALUE_DIFF": ("RECALC", "NOT_REPLACEABLE", "REQUIRES_LIBREOFFICE"),
    "STYLE_CHECK": ("PERSISTENCE", "PARTIALLY_REPLACEABLE", "AVAILABLE_WITH_SMALL_DETERMINISTIC_DERIVATION"),
    "DIMENSION_CHECK": ("STRUCTURAL", "EXACTLY_REPLACEABLE", "ALREADY_AVAILABLE_EXACTLY"),
    "SHEET_EXISTENCE_CHECK": ("STRUCTURAL", "EXACTLY_REPLACEABLE", "ALREADY_AVAILABLE_EXACTLY"),
    "FILE_EXISTENCE_CHECK": ("PERSISTENCE", "EXACTLY_REPLACEABLE", "ALREADY_AVAILABLE_EXACTLY"),
    "SAVE_CHECK": ("PERSISTENCE", "EXACTLY_REPLACEABLE", "ALREADY_AVAILABLE_EXACTLY"),
    "LIBREOFFICE_RECALC": ("RECALC", "NOT_REPLACEABLE", "REQUIRES_LIBREOFFICE"),
    "LIBREOFFICE_CONVERT": ("RECALC", "NOT_REPLACEABLE", "REQUIRES_LIBREOFFICE"),
    "REOPEN_AFTER_RECALC": ("RECALC", "NOT_REPLACEABLE", "REQUIRES_LIBREOFFICE"),
    "DEPENDENT_CELL_INSPECTION": ("SEMANTIC", "NOT_REPLACEABLE", "REQUIRES_MODEL_INTERPRETATION"),
    "MANUAL_EXPECTED_VALUE_CHECK": ("SEMANTIC", "NOT_REPLACEABLE", "REQUIRES_MODEL_INTERPRETATION"),
    "SUBMISSION_PREP": ("STRUCTURAL", "NOT_REPLACEABLE", "NOT_AVAILABLE"),
    "DUMP_TEXT_SEARCH": ("MIXED", "NOT_REPLACEABLE", "REQUIRES_REOPEN"),
    "PACKAGE_XML_INSPECTION": ("STRUCTURAL", "PARTIALLY_REPLACEABLE", "AVAILABLE_WITH_SMALL_DETERMINISTIC_DERIVATION"),
    "SCRIPT_PATCH_RERUN": ("MIXED", "NOT_REPLACEABLE", "REQUIRES_MODEL_INTERPRETATION"),
    "AMBIGUOUS_FILE_RUN": ("MIXED", "UNKNOWN", "NOT_AVAILABLE"),
    "ENV_SETUP": ("MIXED", "NOT_REPLACEABLE", "NOT_AVAILABLE"),
    "LIBRARY_SOURCE_READING": ("SEMANTIC", "NOT_REPLACEABLE", "REQUIRES_MODEL_INTERPRETATION"),
    "ARITHMETIC_CHECK": ("SEMANTIC", "NOT_REPLACEABLE", "REQUIRES_MODEL_INTERPRETATION"),
    "SHELL_OTHER": ("MIXED", "UNKNOWN", "NOT_AVAILABLE"),
    "UNCLASSIFIED_READ": ("MIXED", "UNKNOWN", "NOT_AVAILABLE"),
}

MECH = {
    "PERSISTENCE": "PURE_MECHANICAL",
    "STRUCTURAL": "PURE_MECHANICAL",
    "RECALC": "MECHANICAL_FACT_FOR_SEMANTIC_REASONING",
    "SEMANTIC": "SEMANTIC",
    "MIXED": "MIXED",
}


def followthrough(ep: dict, actions: list[dict]) -> dict:
    """What happened after the post-mutation window."""
    term = ep["terminator"]
    n_reads = len(actions)
    if term == "submit":
        return {"outcome": "VERIFY_SUBMIT" if n_reads else "MUTATE_SUBMIT",
                "trigger": None, "detail": "submitted after verification" if n_reads else "no post reads"}
    if term == "termination":
        return {"outcome": "VERIFY_ABANDON_STALL" if n_reads else "MUTATE_END",
                "trigger": None, "detail": "run ended without submit"}
    # next mutation: repair or expansion? compare write sets
    return {"outcome": "VERIFY_NEXT_MUTATION" if n_reads else "MUTATE_MUTATE",
            "trigger": "PENDING_REPAIR_CLASS", "detail": "see repair_loops"}


def main() -> None:
    AUD.mkdir(parents=True, exist_ok=True)
    hist = load_historical()
    live = load_live()
    print(f"historical execs: {len(hist)}, live execs: {len(live)}")
    episodes = build_episodes(hist) + build_episodes(live)
    print(f"episodes: {len(episodes)}")

    # population
    pop = {"historical_runs": len({e['run'] for e in hist}),
           "live_runs": len({e['run'] for e in live}),
           "historical_execs": len(hist), "live_execs": len(live),
           "episodes": len(episodes),
           "by_family": dict(Counter(e['fam'] for e in hist + live if e['fam'])),
           "sources": ["control_python_audit (P-A/P-B/P-C)",
                       "live_transparent_runtime_ab", "targeted_runtime_replication",
                       "inspection_efficiency_ab", "batch_write_helper_ab"]}
    json.dump(pop, open(AUD / "population.json", "w"), indent=1)

    # episodes + actions
    with open(AUD / "mutation_episodes.jsonl", "w") as fh:
        for ep in episodes:
            fh.write(json.dumps({k: v for k, v in ep.items() if k != "post"}) + "\n")
    all_actions = []
    for ep in episodes:
        all_actions.extend(classify_episode_actions(ep))
    with open(AUD / "post_mutation_actions.jsonl", "w") as fh:
        for a in all_actions:
            fh.write(json.dumps(a) + "\n")

    # verification classification + availability
    TRANSPORT = {"REOPEN_WORKBOOK"}  # retrieval method, not the fact itself
    with open(AUD / "verification_classification.jsonl", "w") as vc, \
         open(AUD / "runtime_fact_availability.jsonl", "w") as av, \
         open(AUD / "replaceability.jsonl", "w") as rp:
        for a in all_actions:
            doms, mechs, avail_set, repl_set = set(), set(), set(), set()
            fact_classes = [c for c in a["classes"] if c not in TRANSPORT] or a["classes"]
            for c in fact_classes:
                dom, repl, avl = AVAIL.get(c, ("MIXED", "UNKNOWN", "NOT_AVAILABLE"))
                doms.add(dom); mechs.add(MECH[dom]); avail_set.add(avl); repl_set.add(repl)
            # exactness requires only-written-cells reads for readback classes
            if repl_set == {"EXACTLY_REPLACEABLE"} and not a["only_written"] and \
               any(c.startswith("READ_BACK") for c in a["classes"]):
                repl_set = {"PARTIALLY_REPLACEABLE"}
            vc.write(json.dumps({"run": a["run"], "task": a["task"], "fam": a["fam"],
                                 "mut_seq": a["mut_seq"], "pos": a["pos"],
                                 "classes": a["classes"], "domains": sorted(doms),
                                 "verdicts": sorted(mechs)}) + "\n")
            av.write(json.dumps({"run": a["run"], "task": a["task"],
                                 "mut_seq": a["mut_seq"], "pos": a["pos"],
                                 "classes": a["classes"],
                                 "availability": sorted(avail_set)}) + "\n")
            rp.write(json.dumps({"run": a["run"], "task": a["task"], "fam": a["fam"],
                                 "mut_seq": a["mut_seq"], "pos": a["pos"],
                                 "classes": a["classes"], "only_written": a["only_written"],
                                 "replaceability": sorted(repl_set),
                                 "script_bytes": a["script_bytes"],
                                 "obs_bytes": a["obs_bytes"]}) + "\n")

    # follow-through + repair loops (link consecutive episodes per run)
    by_run_all: dict[str, list[dict]] = defaultdict(list)
    for e in hist + live:
        by_run_all[e["run"]].append(e)
    by_run_eps: dict[str, list[dict]] = defaultdict(list)
    for ep in episodes:
        by_run_eps[ep["run"]].append(ep)
    with open(AUD / "causal_followthrough.jsonl", "w") as fh, \
         open(AUD / "repair_loops.jsonl", "w") as rh:
        for run, eps in by_run_eps.items():
            eps = sorted(eps, key=lambda e: e["mut_seq"])
            for i, ep in enumerate(eps):
                acts = [a for a in all_actions if a["run"] == run and a["mut_seq"] == ep["mut_seq"]]
                ft = followthrough(ep, acts)
                ft.update({"run": run, "task": ep["task"], "fam": ep["fam"],
                           "mut_seq": ep["mut_seq"], "n_post": len(acts)})
                fh.write(json.dumps(ft) + "\n")
                if ep["terminator"] == "mutation" and i + 1 < len(eps):
                    nxt = eps[i + 1]
                    cur_w = set(ep["write_vals"]) | set(ep["write_fms"])
                    nxt_w = set(nxt["write_vals"]) | set(nxt["write_fms"])
                    ov = cur_w & nxt_w
                    post_classes = {c for a in acts for c in a["classes"]}
                    if ov and (nxt_w <= cur_w):
                        kind, trig = "MECHANICAL_RETRY", "PERSISTENCE_FAILURE"
                    elif ov:
                        kind, trig = "SEMANTIC_REPAIR", "OBSERVED_VALUE_MISMATCH"
                    elif not cur_w or not nxt_w:
                        # textual fallback: shared A1 tokens between mutation scripts
                        tok = re.compile(r"['\"]([A-Za-z]{1,3}\d{1,7})['\"]")
                        cur_src = next((s for s in by_run_all[run]
                                        if s["turn"] == ep["mut_turn"]), {}).get("src", "")
                        nxt_src = next((s for s in by_run_all[run]
                                        if s["turn"] == nxt["mut_turn"]), {}).get("src", "")
                        shared = set(tok.findall(cur_src)) & set(tok.findall(nxt_src))
                        if len(shared) >= 2:
                            kind, trig = "MECHANICAL_RETRY_TEXTUAL", "PERSISTENCE_FAILURE"
                        else:
                            reason = "truncated" if (ep["truncated"] or nxt["truncated"]) else "unlocated_writes"
                            kind, trig = f"UNRESOLVED_{reason}".upper(), "UNRESOLVED"
                    else:
                        kind = "SEMANTIC_REPAIR" if acts else "EXPANSION"
                        trig = "SEMANTIC_RECONSIDERATION" if acts else "UNRESOLVED"
                    if "STYLE_CHECK" in post_classes and kind == "SEMANTIC_REPAIR":
                        trig = "STYLE_LAYOUT_MISMATCH"
                    if "ERROR_SCAN" in post_classes:
                        trig = "OBSERVED_FORMULA_ERROR"
                    rh.write(json.dumps({"run": run, "task": ep["task"], "fam": ep["fam"],
                                         "mut_seq": ep["mut_seq"],
                                         "cur_writes": len(cur_w), "next_writes": len(nxt_w),
                                         "overlap": len(ov), "n_post_reads": len(acts),
                                         "repair_kind": kind, "trigger": trig}) + "\n")

    # reopen cycles: class bigrams/trigrams within post windows
    grams: Counter = Counter()
    for ep in episodes:
        acts = [a for a in all_actions if a["run"] == ep["run"] and a["mut_seq"] == ep["mut_seq"]]
        seq = [a["classes"][0] if a["classes"] else "?" for a in acts]
        for n in (2, 3):
            for i in range(len(seq) - n + 1):
                grams[" > ".join(seq[i:i + n])] += 1
    json.dump({"top_sequences": grams.most_common(25)}, open(AUD / "reopen_cycles.json", "w"), indent=1)

    # self-readback
    n_ep = len(episodes)
    rb = {"n_episodes": n_ep,
          "reread_ge1_written": 0, "only_written": 0, "written_plus_context": 0,
          "reread_formulas": 0, "reread_values": 0, "no_post_reads": 0}
    for ep in episodes:
        acts = [a for a in all_actions if a["run"] == ep["run"] and a["mut_seq"] == ep["mut_seq"]]
        if not acts:
            rb["no_post_reads"] += 1
            continue
        any_ov = any(a["overlap_written"] for a in acts)
        only = any(a["only_written"] for a in acts)
        if any_ov:
            rb["reread_ge1_written"] += 1
        if only:
            rb["only_written"] += 1
        elif any_ov:
            rb["written_plus_context"] += 1
        if any("READ_BACK_WRITTEN_FORMULAS" in a["classes"] for a in acts):
            rb["reread_formulas"] += 1
        if any("READ_BACK_WRITTEN_CELLS" in a["classes"] for a in acts):
            rb["reread_values"] += 1
    json.dump(rb, open(AUD / "self_readback.json", "w"), indent=1)

    # LO branch
    lo_eps = [ep for ep in episodes
              if any("LIBREOFFICE" in c for a in all_actions
                     if a["run"] == ep["run"] and a["mut_seq"] == ep["mut_seq"] for c in a["classes"])]
    lo_learn = Counter()
    for ep in lo_eps:
        acts = [a for a in all_actions if a["run"] == ep["run"] and a["mut_seq"] == ep["mut_seq"]]
        cls = {c for a in acts for c in a["classes"]}
        if "ERROR_SCAN" in cls:
            lo_learn["FORMULA_ERROR"] += 1
        if "RELOAD_DATA_ONLY" in cls:
            lo_learn["VALUE_RESULT"] += 1
        if "MANUAL_EXPECTED_VALUE_CHECK" in cls:
            lo_learn["SEMANTIC_PLAUSIBILITY"] += 1
        if "RANGE_PRINT" in cls or "CELL_READ" in cls:
            lo_learn["DOWNSTREAM_CHANGE"] += 1
        lo_learn["RECALC_OCCURRED"] += 1
    json.dump({"n_lo_episodes": len(lo_eps),
               "tasks": sorted({ep["task"] for ep in lo_eps}),
               "families": sorted({ep["fam"] for ep in lo_eps}),
               "learn_classes": dict(lo_learn)},
              open(AUD / "libreoffice_branch.json", "w"), indent=1)

    # opportunity ceiling
    tot = {"tool_calls": len(all_actions),
           "py_execs": sum(1 for a in all_actions if a["script_bytes"]),
           "view_calls": sum(1 for a in all_actions if "VIEW_XLSX" in a["classes"]),
           "py_bytes": sum(a["script_bytes"] for a in all_actions),
           "obs_bytes": sum(a["obs_bytes"] for a in all_actions)}
    repl_rows = [json.loads(l) for l in open(AUD / "replaceability.jsonl")]
    exact = [r for r in repl_rows if r["replaceability"] == ["EXACTLY_REPLACEABLE"]]
    sub = {"tool_calls": len(exact),
           "py_execs": sum(1 for r in exact if r["script_bytes"]),
           "py_bytes": sum(r["script_bytes"] for r in exact),
           "obs_bytes": sum(r["obs_bytes"] for r in exact)}
    json.dump({"TOTAL_POST_MUTATION_WORK": tot, "EXACTLY_REPLACEABLE_SUBSET": sub},
              open(AUD / "opportunity_ceiling.json", "w"), indent=1)

    # stalls: long post windows or verify->stall
    fts = [json.loads(l) for l in open(AUD / "causal_followthrough.jsonl")]
    stalls = [f for f in fts if f["outcome"] == "VERIFY_ABANDON_STALL" or f["n_post"] >= 6]
    stall_kinds = Counter()
    for f in stalls:
        acts = [a for a in all_actions if a["run"] == f["run"] and a["mut_seq"] == f["mut_seq"]]
        cls = Counter(c for a in acts for c in a["classes"])
        if cls.get("VIEW_XLSX", 0) + cls.get("RANGE_PRINT", 0) >= 3:
            stall_kinds["repeated_broad_inspection"] += 1
        elif cls.get("READ_BACK_WRITTEN_CELLS", 0) + cls.get("READ_BACK_WRITTEN_FORMULAS", 0) >= 2:
            stall_kinds["repeated_mechanical_verification"] += 1
        elif f["n_post"] >= 6:
            stall_kinds["repeated_semantic_reconsideration"] += 1
        else:
            stall_kinds["failure_to_submit"] += 1
    json.dump({"n_stall_episodes": len(stalls), "kinds": dict(stall_kinds)},
              open(AUD / "stall_analysis.json", "w"), indent=1)

    # candidate interventions by retention threshold (mechanical pre-filter;
    # final verdict composed in the report step)
    exact_tasks = {r["task"] for r in exact}
    exact_fams = {r["fam"] for r in exact}
    exact_classes = Counter(c for r in exact for c in r["classes"])
    cands = {
        "exact_replaceable_actions": len(exact),
        "exact_tasks": len(exact_tasks), "exact_families": sorted(exact_fams),
        "exact_classes": dict(exact_classes),
        "threshold": {"min_tasks": 3, "min_families": 2},
        "threshold_met": len(exact_tasks) >= 3 and len(exact_fams) >= 2,
        "shapes_considered": ["AUTO_COMMIT_RECEIPT", "EXPLICIT_VERIFY_HELPER",
                              "POST_RECALC_RECEIPT", "INSPECT_EXTENSION", "NO_INTERVENTION"],
    }
    json.dump(cands, open(AUD / "candidate_interventions.json", "w"), indent=1)
    json.dump({
        "SAVE_SUCCEEDED": "SAFE_TO_PUSH", "N_CELLS_CHANGED": "SAFE_TO_PUSH",
        "DECLARED_WRITES_PERSISTED": "SAFE_TO_PUSH",
        "RECALC_SUCCEEDED": "PREFER_PULL", "N_FORMULA_ERRORS": "PREFER_PULL",
        "FULL_DELTA": "REJECT", "DEPENDENCY_GRAPH": "REJECT",
        "DOWNSTREAM_VALUES": "PREFER_PULL", "CORRECTNESS_CLAIMS": "REJECT"},
        open(AUD / "push_vs_pull.json", "w"), indent=1)
    # inspect overlap: which post classes could a pull-based inspect() serve?
    pullable = {"CELL_READ", "RANGE_PRINT", "READ_BACK_WRITTEN_CELLS",
                "READ_BACK_WRITTEN_FORMULAS", "STYLE_CHECK", "DIMENSION_CHECK"}
    n_pull = sum(1 for a in all_actions if set(a["classes"]) & pullable)
    json.dump({"pullable_by_inspect": n_pull, "total_post_actions": len(all_actions),
               "frac": (n_pull / len(all_actions)) if all_actions else 0,
               "note": "inspect() can already retrieve range/cell facts on demand; "
                       "a receipt only saves the pull call itself"},
              open(AUD / "existing_helper_overlap.json", "w"), indent=1)
    print("census artifacts written")


if __name__ == "__main__":
    main()
