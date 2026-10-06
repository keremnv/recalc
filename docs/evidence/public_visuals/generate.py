"""Public visual evidence generator (documentation-only).

Builds the three Step-1 public figures from frozen evidence:

  docs/assets/recalc-selective-execution.svg        (Figure A, schematic)
  docs/assets/recalc-task-replay-outcomes.svg       (Figure B, measured)
  docs/assets/recalc-controlled-applicability.svg   (Figure C, measured)

Usage:
  python docs/evidence/public_visuals/generate.py --verify   # checks only
  python docs/evidence/public_visuals/generate.py --build    # verify + write SVGs

--verify loads canonical frozen evidence, recomputes every displayed
measured value, and fails loudly on any mismatch. It executes no
benchmark workloads, issues no model calls, and needs no network.
--build runs verification first, then deterministically rewrites the
three SVGs (byte-stable for unchanged inputs; no timestamps/paths).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]

LEDGER_PATH = ROOT / "research/benefit_evidence_ledger/benefit_ledger.json"
AUDIT_PATH = ROOT / "research/spreadsheetbench_applicability_audit/summary.json"
TIER2_WORKLOADS_PATH = ROOT / "research/tier2_distribution_audit/tier2_workloads.json"
TIER2_SUMMARY_PATH = ROOT / "research/tier2_distribution_audit/tier2_summary.json"
MANIFEST_PATH = HERE / "manifest.json"

ASSET_A = ROOT / "docs/assets/recalc-selective-execution.svg"
ASSET_B = ROOT / "docs/assets/recalc-task-replay-outcomes.svg"
ASSET_C = ROOT / "docs/assets/recalc-controlled-applicability.svg"
ASSET_D = ROOT / "docs/assets/recalc-r3-distribution.svg"

# --- Expected display values (tripwires, not authority) ---------------------
# The ledger is the authority. These constants encode the display strings the
# docs already publish; verification recomputes them from evidence and fails
# if the evidence does not reproduce them.

FIGURE_B_ROWS = (
    {
        "trajectory_id": "tier1-r01-P-Debugging-07_01",
        "task_id": "Debugging:07_01",
        "display_identity": "Debugging:07_01 \u00b7 Claude",
        "model_marker": "claude-sonnet",
        "base_s": 15.477,
        "recalc_s": 13.210,
        "saved_s": "2.267 s saved",
        "pct": "14.6% lower",
        "served_invocations": 3,
        "total_invocations": 13,
        "served_share": "21.3%",
    },
    {
        "trajectory_id": "tier1-r06-O-mimo-Financial_Model-11_05",
        "task_id": "Financial_Model:11_05",
        "display_identity": "Financial_Model:11_05 \u00b7 Mimo",
        "model_marker": "mimo",
        "base_s": 28.001,
        "recalc_s": 26.141,
        "saved_s": "1.860 s saved",
        "pct": "6.6% lower",
        "served_invocations": 5,
        "total_invocations": 23,
        "served_share": "15.8%",
    },
    {
        "trajectory_id": "tier1-r14-O-mimo-Debugging-08_06",
        "task_id": "Debugging:08_06",
        "display_identity": "Debugging:08_06 \u00b7 Mimo",
        "model_marker": "mimo",
        "base_s": 12.254,
        "recalc_s": 13.176,
        "saved_s": "+0.922 s",
        "pct": "+7.5%",
        "served_invocations": 1,
        "total_invocations": 26,
        "served_share": "5.0%",
        "boundary": True,
    },
)

FIGURE_C_EXPECTED = {
    "population_key": "controlled_subset",
    "n_tasks": 6,
    "n_trajectories": 9,
    "executed_invocations": 136,
    "reference": 119,
    "fully_direct": 10,
    "fallback": 7,
    "useful": 10,
    "tasks_exposed": 4,
    "trajectories_exposed": 4,
    "served_pct": "7.4%",
}

SCOPE_B = "MEASURED \u00b7 WARM PAIRED TASK REPLAY \u00b7 BASE vs RECALC 0.2.0"
SCOPE_C = ("MEASURED \u00b7 SPREADSHEETBENCH-2 CONTROLLED STRATUM "
           "\u00b7 6 TASKS \u00b7 9 TRAJECTORIES")
SCOPE_D = ("MEASURED \u00b7 HISTORICAL R3 MECHANISM POPULATION \u00b7 WARM "
           "\u00b7 OFF \u2192 ON \u00b7 30 WORKLOADS")

FIGURE_D_EXPECTED = {
    "n_workloads": 30,
    "faster": 23,
    "slower": 7,
    "median_display": "0.913\u00d7",
    "median_pct_display": "8.75%",
    "top3_display": "84.2%",
    "largest_regression_display": "49.7 ms",
    "min_display": "0.067\u00d7",
    "max_display": "1.111\u00d7",
    "comparator": "OFF (rc3-equivalent predecessor control) -> ON (iteration candidate)",
}
BADGE_A = "SCHEMATIC \u00b7 NO TIMING"

FONT_SANS = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FONT_MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'

INK = "#1f2328"
MUTED = "#57606a"
PANEL = "#ffffff"
PANEL_EDGE = "#d0d7de"
CANVAS = "#f6f8fa"
ACCENT = "#0969da"       # Recalc / directly served (only saturated hue)
ACCENT_DARK = "#054da3"
NEUTRAL_FILL = "#e8ecf0"  # BASE / reference execution
NEUTRAL_EDGE = "#6e7781"
HATCH_INK = "#6e7781"

GENERATED_COMMENT = ("<!-- Generated from frozen Recalc evidence. Do not edit by hand.\n"
                     "     Rebuild: python docs/evidence/public_visuals/generate.py, build mode -->")


# --- Small helpers ------------------------------------------------------------

def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def fmt3(x: float) -> str:
    return f"{x:.3f}"


def fail(errors: list[str], context: str) -> bool:
    if errors:
        print(f"VERIFY FAIL ({context}):")
        for e in errors:
            print(f" - {e}")
        return False
    return True


# --- Evidence loading ----------------------------------------------------------

def load_ledger() -> list[dict]:
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def load_audit() -> dict:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def trajectory_rows(ledger: list[dict]) -> dict[str, dict]:
    """Trajectory-level rows only (whole-replay scope), keyed by trajectory."""
    out: dict[str, dict] = {}
    for row in ledger:
        if row.get("unit_type") == "trajectory" and row.get("trajectory_id"):
            out[row["trajectory_id"]] = row
    return out


# --- Figure B verification ------------------------------------------------------

_SCOPE_RE = re.compile(r"\((\d+) executed invocations\)")
_NOTES_RE = re.compile(r"(\d+) direct / (\d+) fallback / (\d+) reference")


def verify_figure_b(ledger: list[dict]) -> tuple[bool, list[dict]]:
    """Recompute every displayed Figure B value from the benefit ledger."""
    errors: list[str] = []
    by_traj = trajectory_rows(ledger)
    verified: list[dict] = []
    for want in FIGURE_B_ROWS:
        tid = want["trajectory_id"]
        row = by_traj.get(tid)
        if row is None:
            errors.append(f"{tid}: trajectory row missing from benefit ledger")
            continue
        # Identity.
        if row.get("benchmark") != "SpreadsheetBench-2":
            errors.append(f"{tid}: benchmark={row.get('benchmark')!r}")
        if row.get("task_id") != want["task_id"]:
            errors.append(f"{tid}: task_id={row.get('task_id')!r}")
        if want["model_marker"] not in str(row.get("model_family", "")).lower():
            errors.append(f"{tid}: model_family={row.get('model_family')!r}")
        # Comparator / regime / product scope.
        if not str(row.get("comparator", "")).startswith("BASE"):
            errors.append(f"{tid}: comparator={row.get('comparator')!r}")
        if row.get("recalc_variant") != "released recalc-agent 0.2.0":
            errors.append(f"{tid}: recalc_variant={row.get('recalc_variant')!r}")
        if not str(row.get("warm_or_cold", "")).startswith("warm"):
            errors.append(f"{tid}: warm_or_cold={row.get('warm_or_cold')!r}")
        # Runtime values (tolerant float compare; display rounds to 3 dp).
        base = row.get("base_runtime_s")
        recalc = row.get("recalc_runtime_s")
        if not isinstance(base, (int, float)) or abs(base - want["base_s"]) > 1e-9:
            errors.append(f"{tid}: base_runtime_s={base!r}")
        if not isinstance(recalc, (int, float)) or abs(recalc - want["recalc_s"]) > 1e-9:
            errors.append(f"{tid}: recalc_runtime_s={recalc!r}")
        if errors and errors[-1].startswith(tid):
            continue
        # Recompute derived display strings from evidence.
        saved = base - recalc
        if want.get("boundary"):
            saved_s = f"+{abs(saved):.3f} s"
            pct_s = f"+{abs(100 * saved / base):.1f}%"
        else:
            saved_s = f"{saved:.3f} s saved"
            pct_s = f"{100 * saved / base:.1f}% lower"
        if saved_s != want["saved_s"]:
            errors.append(f"{tid}: saved recomputes to {saved_s!r}")
        if pct_s != want["pct"]:
            errors.append(f"{tid}: pct recomputes to {pct_s!r}")
        # Ledger's own relative_delta must agree with the raw pair.
        rel = row.get("relative_delta")
        if not isinstance(rel, (int, float)) or abs(rel - (recalc - base) / base) > 1e-9:
            errors.append(f"{tid}: relative_delta={rel!r} inconsistent with pair")
        # Invocation counts: scope string, notes breakdown, served loads.
        m = _SCOPE_RE.search(str(row.get("measurement_scope", "")))
        n = _NOTES_RE.search(str(row.get("notes", "")))
        if m is None:
            errors.append(f"{tid}: cannot parse invocation total from scope")
            continue
        if n is None:
            errors.append(f"{tid}: cannot parse route breakdown from notes")
            continue
        total, (d_direct, _d_fb, _d_ref) = int(m.group(1)), tuple(int(g) for g in n.groups())
        if total != want["total_invocations"]:
            errors.append(f"{tid}: total invocations recompute to {total}")
        if d_direct != want["served_invocations"]:
            errors.append(f"{tid}: served invocations recompute to {d_direct}")
        if sum((d_direct, _d_fb, _d_ref)) != total:
            errors.append(f"{tid}: route breakdown does not sum to total")
        if row.get("direct_served_loads") != want["served_invocations"]:
            errors.append(f"{tid}: direct_served_loads={row.get('direct_served_loads')!r}")
        # Served-block BASE share.
        share = row.get("direct_base_share")
        if not isinstance(share, (int, float)):
            errors.append(f"{tid}: direct_base_share missing")
            continue
        if f"{100 * share:.1f}%" != want["served_share"]:
            errors.append(f"{tid}: served share recomputes to {100 * share:.1f}%")
        verified.append({
            "trajectory_id": tid,
            "task_id": want["task_id"],
            "display_identity": want["display_identity"],
            "base_s": float(base),
            "recalc_s": float(recalc),
            "saved_display": want["saved_s"],
            "pct_display": want["pct"],
            "served": want["served_invocations"],
            "total": want["total_invocations"],
            "share_display": want["served_share"],
            "boundary": bool(want.get("boundary")),
        })
    ok = fail(errors, "figure B")
    return ok, verified


# --- Figure C verification ------------------------------------------------------

def verify_figure_c(audit: dict) -> tuple[bool, dict]:
    """Recompute every displayed Figure C value from the audit summary."""
    errors: list[str] = []
    key = FIGURE_C_EXPECTED["population_key"]
    pop = audit.get(key)
    if not isinstance(pop, dict):
        fail([f"population key {key!r} missing"], "figure C")
        return False, {}
    if pop.get("n_tasks") != FIGURE_C_EXPECTED["n_tasks"]:
        errors.append(f"n_tasks={pop.get('n_tasks')!r}")
    if pop.get("n_trajectories") != FIGURE_C_EXPECTED["n_trajectories"]:
        errors.append(f"n_trajectories={pop.get('n_trajectories')!r}")
    if len(pop.get("tasks", [])) != FIGURE_C_EXPECTED["n_tasks"]:
        errors.append("tasks list length mismatch")
    if len(pop.get("trajectories", [])) != FIGURE_C_EXPECTED["n_trajectories"]:
        errors.append("trajectories list length mismatch")
    if pop.get("executed_invocations") != FIGURE_C_EXPECTED["executed_invocations"]:
        errors.append(f"executed_invocations={pop.get('executed_invocations')!r}")
    routes = pop.get("routes_executed", {})
    for name in ("reference", "fully_direct", "fallback", "useful"):
        if routes.get(name) != FIGURE_C_EXPECTED[name]:
            errors.append(f"routes_executed.{name}={routes.get(name)!r}")
    n = FIGURE_C_EXPECTED["executed_invocations"]
    if routes.get("reference", -1) + routes.get("fully_direct", -1) + routes.get("fallback", -1) != n:
        errors.append("route categories do not sum to executed invocations")
    if f"{100 * FIGURE_C_EXPECTED['fully_direct'] / n:.1f}%" != FIGURE_C_EXPECTED["served_pct"]:
        errors.append("10/136 does not recompute to 7.4%")
    if abs(pop.get("metric_B_useful_service_rate", -1) - 10 / 136) > 1e-12:
        errors.append("metric_B_useful_service_rate inconsistent with 10/136")
    if pop.get("metric_E_tasks_exposed") != FIGURE_C_EXPECTED["tasks_exposed"]:
        errors.append(f"metric_E_tasks_exposed={pop.get('metric_E_tasks_exposed')!r}")
    if pop.get("metric_F_runs_exposed") != FIGURE_C_EXPECTED["trajectories_exposed"]:
        errors.append(f"metric_F_runs_exposed={pop.get('metric_F_runs_exposed')!r}")
    if abs(pop.get("metric_E_task_exposure", -1) - 4 / 6) > 1e-12:
        errors.append("metric_E_task_exposure inconsistent with 4/6")
    if abs(pop.get("metric_F_trajectory_exposure", -1) - 4 / 9) > 1e-12:
        errors.append("metric_F_trajectory_exposure inconsistent with 4/9")
    ok = fail(errors, "figure C")
    verified = {
        "population_key": key,
        "n_tasks": 6,
        "n_trajectories": 9,
        "executed": 136,
        "reference": 119,
        "direct": 10,
        "admitted_zero": 7,
        "served_pct": "7.4%",
        "tasks_exposed": 4,
        "trajectories_exposed": 4,
    }
    return ok, verified


# --- Figure D verification ------------------------------------------------------

def verify_figure_d(workloads: list[dict], summary: dict) -> tuple[bool, dict]:
    """Recompute every displayed Figure D value from workload-level R3 data,
    cross-checking against tier2_summary.json."""
    import statistics

    errors: list[str] = []
    exp = FIGURE_D_EXPECTED
    if not isinstance(workloads, list) or len(workloads) != exp["n_workloads"]:
        got = len(workloads) if isinstance(workloads, list) else type(workloads).__name__
        return fail([f"workload population n={got}, want 30"], "figure D"), {}
    if summary.get("n_workloads") != exp["n_workloads"]:
        errors.append(f"summary n_workloads={summary.get('n_workloads')!r}")
    if summary.get("historical_pair") != exp["comparator"]:
        errors.append(f"historical_pair={summary.get('historical_pair')!r}")
    if "median" not in str(summary.get("historical_reducer", "")).lower():
        errors.append(f"historical_reducer={summary.get('historical_reducer')!r}")

    rows: list[dict] = []
    for w in workloads:
        wid = w.get("workload_id", "?")
        try:
            off_reps = w["off_rep_values"]
            on_reps = w["on_rep_values"]
            off = statistics.median(off_reps)
            on = statistics.median(on_reps)
        except (KeyError, TypeError, statistics.StatisticsError):
            errors.append(f"{wid}: OFF/ON rep values missing")
            continue
        if abs(off - w.get("off_median", off)) > 1e-9:
            errors.append(f"{wid}: off_median inconsistent with reps")
        if abs(on - w.get("on_median", on)) > 1e-9:
            errors.append(f"{wid}: on_median inconsistent with reps")
        if "warm" not in str(w.get("reducer_definition", "")).lower():
            errors.append(f"{wid}: reducer is not warm")
        if w.get("included_in_historical_aggregate") is not True:
            errors.append(f"{wid}: not in historical aggregate")
        saved = off - on
        if abs(saved - w.get("saved_s_off_on", saved)) > 1e-9:
            errors.append(f"{wid}: saved_s_off_on inconsistent with medians")
        rows.append({"workload_id": wid, "off": off, "on": on,
                     "ratio": on / off, "saved": saved})
    if errors:
        fail(errors, "figure D rows")
        return False, {}
    rows.sort(key=lambda r: r["ratio"])

    faster = sum(1 for r in rows if r["on"] < r["off"])
    slower = sum(1 for r in rows if r["on"] > r["off"])
    if faster != exp["faster"]:
        errors.append(f"faster recomputes to {faster}")
    if slower != exp["slower"]:
        errors.append(f"slower recomputes to {slower}")

    post = summary.get("posthoc_descriptive", {})
    median_ratio = statistics.median([r["ratio"] for r in rows])
    if abs(median_ratio - post.get("median_ratio_on_off", median_ratio)) > 1e-9:
        errors.append("median ratio disagrees with summary")
    if f"{median_ratio:.3f}\u00d7" != exp["median_display"]:
        errors.append(f"median display recomputes to {median_ratio:.3f}x")
    if f"{100 * (1 - median_ratio):.2f}%" != exp["median_pct_display"]:
        errors.append("median improvement pct mismatch")
    if abs(rows[0]["ratio"] - post.get("min_ratio", rows[0]["ratio"])) > 1e-12:
        errors.append("min ratio disagrees with summary")
    if abs(rows[-1]["ratio"] - post.get("max_ratio", rows[-1]["ratio"])) > 1e-12:
        errors.append("max ratio disagrees with summary")
    if rows[0]["workload_id"] != post.get("min_ratio_workload"):
        errors.append("min ratio workload mismatch")
    if rows[-1]["workload_id"] != post.get("max_ratio_workload"):
        errors.append("max ratio workload mismatch")
    if f"{rows[0]['ratio']:.3f}\u00d7" != exp["min_display"]:
        errors.append("min display mismatch")
    if f"{rows[-1]['ratio']:.3f}\u00d7" != exp["max_display"]:
        errors.append("max display mismatch")

    positive = sorted((r for r in rows if r["saved"] > 0),
                      key=lambda r: -r["saved"])
    top3 = (sum(r["saved"] for r in positive[:3])
            / sum(r["saved"] for r in positive))
    conc = post.get("concentration", {})
    if abs(top3 - conc.get("top3_share_of_positive_savings", top3)) > 1e-12:
        errors.append("top-3 concentration disagrees with summary")
    if f"{100 * top3:.1f}%" != exp["top3_display"]:
        errors.append(f"top-3 display recomputes to {100 * top3:.1f}%")

    worst = min(rows, key=lambda r: r["saved"])
    if abs(worst["saved"] - post.get("largest_regression_s", worst["saved"])) > 1e-12:
        errors.append("largest regression disagrees with summary")
    if worst["workload_id"] != post.get("largest_regression_workload"):
        errors.append("largest regression workload mismatch")
    if f"{-1000 * worst['saved']:.1f} ms" != exp["largest_regression_display"]:
        errors.append("largest regression display mismatch")

    ok = fail(errors, "figure D")
    data = {
        "rows": [{"rank": i + 1, "ratio": r["ratio"],
                  "faster": r["on"] < r["off"]} for i, r in enumerate(rows)],
        "faster": faster,
        "slower": slower,
        "median_ratio": median_ratio,
        "median_display": exp["median_display"],
        "median_pct_display": exp["median_pct_display"],
        "top3_display": exp["top3_display"],
        "largest_regression_display": exp["largest_regression_display"],
        "min_display": exp["min_display"],
        "max_display": exp["max_display"],
    }
    if ok:
        print(f"FIGURE D: n = 30, faster = {faster}, slower = {slower}, "
              f"median ratio = {median_ratio:.6f}, median improvement = "
              f"{100 * (1 - median_ratio):.2f}%, top-3 concentration = "
              f"{100 * top3:.1f}%, largest regression = {-worst['saved']:.4f} s, "
              f"min ratio = {rows[0]['ratio']:.6f}, "
              f"max ratio = {rows[-1]['ratio']:.6f}")
    return ok, data


# --- Manifest check ---------------------------------------------------------------

def verify_manifest() -> bool:
    errors: list[str] = []
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return fail([f"manifest unreadable: {e}"], "manifest")
    assets = {a.get("id"): a for a in manifest.get("assets", [])}
    want_b = [r["trajectory_id"] for r in FIGURE_B_ROWS]
    b = assets.get("recalc-task-replay-outcomes")
    if b is None:
        errors.append("manifest omits recalc-task-replay-outcomes")
    else:
        if b.get("kind") != "measured":
            errors.append("figure B kind must be measured")
        if b.get("trajectory_ids") != want_b:
            errors.append("figure B trajectory_ids mismatch")
        if "research/benefit_evidence_ledger/benefit_ledger.json" not in b.get("evidence_sources", []):
            errors.append("figure B evidence source mismatch")
    c = assets.get("recalc-controlled-applicability")
    if c is None:
        errors.append("manifest omits recalc-controlled-applicability")
    else:
        if c.get("kind") != "measured":
            errors.append("figure C kind must be measured")
        if c.get("population_key") != "controlled_subset":
            errors.append("figure C population_key mismatch")
        if "research/spreadsheetbench_applicability_audit/summary.json" not in c.get("evidence_sources", []):
            errors.append("figure C evidence source mismatch")
    a = assets.get("recalc-selective-execution")
    if a is None:
        errors.append("manifest omits recalc-selective-execution")
    elif a.get("kind") != "schematic":
        errors.append("figure A kind must be schematic")
    d = assets.get("recalc-r3-distribution")
    if d is None:
        errors.append("manifest omits recalc-r3-distribution")
    else:
        if d.get("kind") != "measured":
            errors.append("figure D kind must be measured")
        if d.get("population") != "R3 full-cell iteration mechanism population":
            errors.append("figure D population mismatch")
        if d.get("denominator") != "30 workloads":
            errors.append("figure D denominator mismatch")
        for src in ("research/tier2_distribution_audit/tier2_workloads.json",
                    "research/tier2_distribution_audit/tier2_summary.json"):
            if src not in d.get("evidence_sources", []):
                errors.append(f"figure D omits evidence source {src}")
        if d.get("used_in") != ["PERFORMANCE.md"]:
            errors.append("figure D must be PERFORMANCE-only")
    return fail(errors, "manifest")


def load_tier2() -> tuple[list[dict], dict]:
    workloads = json.loads(TIER2_WORKLOADS_PATH.read_text(encoding="utf-8"))
    summary = json.loads(TIER2_SUMMARY_PATH.read_text(encoding="utf-8"))
    return workloads, summary


def verify() -> tuple[bool, list[dict], dict, dict]:
    """Load evidence, validate scope, recompute every displayed value."""
    try:
        ledger = load_ledger()
    except (OSError, json.JSONDecodeError) as e:
        fail([f"benefit ledger unreadable: {e}"], "figure B")
        return False, [], {}, {}
    try:
        audit = load_audit()
    except (OSError, json.JSONDecodeError) as e:
        fail([f"applicability summary unreadable: {e}"], "figure C")
        return False, [], {}, {}
    try:
        workloads, tier2 = load_tier2()
    except (OSError, json.JSONDecodeError) as e:
        fail([f"R3 tier2 evidence unreadable: {e}"], "figure D")
        return False, [], {}, {}
    ok_b, rows_b = verify_figure_b(ledger)
    ok_c, data_c = verify_figure_c(audit)
    ok_d, data_d = verify_figure_d(workloads, tier2)
    ok_m = verify_manifest()
    ok = ok_b and ok_c and ok_d and ok_m
    if ok:
        print("VERIFY PASS: 3/3 task-replay trajectories recomputed from benefit ledger; "
              "controlled stratum 136 = 119 + 10 + 7 with 4/6 task and 4/9 trajectory "
              "exposure; R3 population n = 30 recomputed from workload reps; "
              "manifest consistent. No workloads executed, no model calls.")
    return ok, rows_b, data_c, data_d


# --- Shared SVG helpers ----------------------------------------------------------

def svg_open(w: int, h: int, title_id: str, title: str, desc_id: str, desc: str) -> list[str]:
    return [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-labelledby="{title_id} {desc_id}">',
        f'<title id="{title_id}">{esc(title)}</title>',
        f'<desc id="{desc_id}">{esc(desc)}</desc>',
    ]


def arrow_defs() -> str:
    return (
        '<defs>'
        f'<marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{INK}"/>'
        "</marker>"
        '<marker id="arrMut" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{MUTED}"/>'
        "</marker>"
        '<pattern id="hatch" width="9" height="9" patternTransform="rotate(45)" '
        'patternUnits="userSpaceOnUse">'
        f'<rect width="9" height="9" fill="{PANEL}"/>'
        f'<line x1="0" y1="0" x2="0" y2="9" stroke="{HATCH_INK}" stroke-width="2.4"/>'
        "</pattern>"
        "</defs>"
    )


def box(parts: list[str], x: int, y: int, w: int, h: int, line1: str,
        line2: str | None = None, mono1: bool = False, accent_edge: bool = False) -> None:
    edge = ACCENT if accent_edge else PANEL_EDGE
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{PANEL}" '
        f'stroke="{edge}" stroke-width="{2 if accent_edge else 1.5}"/>')
    cx = x + w / 2
    f1 = FONT_MONO if mono1 else FONT_SANS
    if line2 is None:
        parts.append(
            f'<text x="{cx:.1f}" y="{y + h / 2 + 6}" text-anchor="middle" '
            f'font-family="{f1}" font-size="16" font-weight="600" fill="{INK}">'
            f"{esc(line1)}</text>")
    else:
        parts.append(
            f'<text x="{cx:.1f}" y="{y + h / 2 - 3}" text-anchor="middle" '
            f'font-family="{f1}" font-size="16" font-weight="600" fill="{INK}">'
            f"{esc(line1)}</text>")
        parts.append(
            f'<text x="{cx:.1f}" y="{y + h / 2 + 19}" text-anchor="middle" '
            f'font-family="{FONT_SANS}" font-size="13" fill="{MUTED}">'
            f"{esc(line2)}</text>")


def badge(parts: list[str], x: int, y: int, text: str, w: int = 232) -> None:
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="28" rx="6" fill="{PANEL}" '
        f'stroke="{NEUTRAL_EDGE}" stroke-width="1.2"/>')
    parts.append(
        f'<text x="{x + w / 2}" y="{y + 19}" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="13" font-weight="700" '
        f'letter-spacing="1.5" fill="{MUTED}">{esc(text)}</text>')


def scope_strip(parts: list[str], x: int, y: int, text: str, w: int) -> None:
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="28" rx="6" fill="{INK}"/>')
    parts.append(
        f'<text x="{x + w / 2}" y="{y + 19}" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="13" font-weight="700" '
        f'letter-spacing="1.2" fill="#ffffff">{esc(text)}</text>')


def v_arrow(parts: list[str], x: float, y1: float, y2: float) -> None:
    parts.append(
        f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}" '
        f'stroke="{INK}" stroke-width="2" marker-end="url(#arr)"/>')


# --- Figure A: selective execution (schematic) ------------------------------------

FIGURE_A_DESC = (
    "Schematic flowchart with no timing. An ordinary Python openpyxl invocation "
    "first passes conservative admission. Not-eligible invocations run on genuine "
    "openpyxl reference execution. Direct-path eligible invocations may have "
    "supported reads served from validated workbook read state. Both paths merge "
    "into execution, where fallback to genuine openpyxl remains possible, and the "
    "outcome is recorded in a receipt. A separate external observer panel shows "
    "before, run, and after observation recording effects and assurance; it "
    "observes only and executes no spreadsheet semantics."
)


def build_figure_a() -> str:
    W, H = 1200, 650
    p = svg_open(W, H, "sel-title", "How Recalc handles an invocation",
                 "sel-desc", FIGURE_A_DESC)
    p.append(arrow_defs())
    p.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="{CANVAS}"/>')
    p.append(
        f'<text x="40" y="46" font-family="{FONT_SANS}" font-size="25" '
        f'font-weight="700" fill="{INK}">How Recalc handles an invocation</text>')
    badge(p, 40, 60, BADGE_A)

    # Entry: ordinary interface.
    box(p, 230, 108, 340, 56, "ordinary Python / openpyxl invocation",
        "user/agent interface \u2014 unchanged")
    v_arrow(p, 400, 164, 182)

    # Admission diamond.
    p.append('<polygon points="400,184 470,226 400,268 330,226" '
             f'fill="{PANEL}" stroke="{INK}" stroke-width="2"/>')
    p.append(
        f'<text x="400" y="222" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="15" font-weight="600" fill="{INK}">conservative</text>')
    p.append(
        f'<text x="400" y="241" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="15" font-weight="600" fill="{INK}">admission</text>')

    # Branch lines at diamond mid-height.
    p.append(
        f'<line x1="330" y1="226" x2="180" y2="226" stroke="{INK}" stroke-width="2"/>')
    p.append(
        f'<line x1="180" y1="226" x2="180" y2="296" stroke="{INK}" stroke-width="2" '
        'marker-end="url(#arr)"/>')
    p.append(
        f'<line x1="470" y1="226" x2="640" y2="226" stroke="{INK}" stroke-width="2"/>')
    p.append(
        f'<line x1="640" y1="226" x2="640" y2="296" stroke="{INK}" stroke-width="2" '
        'marker-end="url(#arr)"/>')
    p.append(
        f'<text x="255" y="216" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="14" fill="{INK}">not eligible</text>')
    p.append(
        f'<text x="555" y="216" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="14" fill="{INK}">direct-path eligible</text>')

    # Left: genuine openpyxl. Right: validated state supplies supported reads.
    box(p, 60, 300, 240, 60, "genuine openpyxl", "reference execution")
    box(p, 508, 300, 264, 56, "validated workbook read state",
        "reused / rebuilt when needed", accent_edge=True)
    v_arrow(p, 640, 356, 376)
    box(p, 508, 380, 264, 56, "supported reads", "certified \u00b7 served from state",
        accent_edge=True)

    # Merge into execution.
    p.append(
        f'<line x1="180" y1="360" x2="180" y2="478" stroke="{INK}" stroke-width="2"/>')
    p.append(
        f'<line x1="640" y1="436" x2="640" y2="478" stroke="{INK}" stroke-width="2"/>')
    p.append(
        f'<line x1="180" y1="478" x2="640" y2="478" stroke="{INK}" stroke-width="2"/>')
    v_arrow(p, 410, 478, 498)
    box(p, 230, 502, 360, 56, "execution", "fallback to genuine openpyxl if required")
    v_arrow(p, 410, 558, 574)
    box(p, 290, 578, 240, 50, "receipt", "records the outcome")

    # Eligibility caveat (right of the receipt row; tied to fallback, not failure).
    p.append(
        f'<text x="606" y="594" font-family="{FONT_SANS}" font-size="13" fill="{MUTED}">'
        "direct-path eligibility does not keep</text>")
    p.append(
        f'<text x="606" y="611" font-family="{FONT_SANS}" font-size="13" fill="{MUTED}">'
        "every operation direct</text>")

    # External observer: dashed panel, clearly outside the execution path.
    p.append(
        f'<rect x="830" y="108" width="330" height="252" rx="8" fill="{PANEL}" '
        f'stroke="{NEUTRAL_EDGE}" stroke-width="1.5" stroke-dasharray="7 5"/>')
    p.append(
        f'<text x="995" y="140" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="16" font-weight="700" fill="{INK}">external observer</text>')
    p.append(
        f'<line x1="850" y1="154" x2="1140" y2="154" stroke="{PANEL_EDGE}" stroke-width="1"/>')
    p.append(
        f'<text x="995" y="186" text-anchor="middle" font-family="{FONT_MONO}" '
        f'font-size="15" fill="{INK}">before \u2192 run \u2192 after</text>')
    p.append(
        f'<text x="995" y="216" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="14" fill="{INK}">records effects + assurance</text>')
    p.append(
        f'<text x="995" y="258" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{MUTED}">snapshots workbook bytes around</text>')
    p.append(
        f'<text x="995" y="277" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{MUTED}">the real script process;</text>')
    p.append(
        f'<text x="995" y="314" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" font-weight="600" fill="{MUTED}">observes only \u2014 executes</text>')
    p.append(
        f'<text x="995" y="333" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" font-weight="600" fill="{MUTED}">no spreadsheet semantics</text>')
    # Dotted observation tie, elbowed around the direct-path column
    # (no arrowhead: observation is not control flow).
    p.append(
        f'<line x1="900" y1="360" x2="900" y2="530" stroke="{MUTED}" stroke-width="1.5" '
        'stroke-dasharray="2 5" stroke-linecap="round"/>')
    p.append(
        f'<line x1="900" y1="530" x2="592" y2="530" stroke="{MUTED}" stroke-width="1.5" '
        'stroke-dasharray="2 5" stroke-linecap="round"/>')
    p.append(
        f'<text x="746" y="522" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" font-style="italic" fill="{MUTED}">observes</text>')

    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- Figure B: measured task-replay outcomes --------------------------------------

FIGURE_B_FENCE_1 = ("Specific model trajectories. Execution replay, "
                    "not model-in-the-loop end-to-end timing.")
FIGURE_B_FENCE_2 = "Served-share values are descriptive; no threshold is established."

FIGURE_B_DESC = (
    "Paired warm task-replay outcomes, BASE plain Python versus released Recalc "
    "0.2.0, on one shared linear seconds axis from 0 to 30. Debugging:07_01 "
    "Claude trajectory: 15.477 seconds BASE versus 13.210 Recalc, 2.267 seconds "
    "saved, 14.6 percent lower, 3 of 13 invocations directly served. "
    "Financial_Model:11_05 Mimo trajectory: 28.001 versus 26.141 seconds, 1.860 "
    "saved, 6.6 percent lower, 5 of 23 directly served. Boundary Debugging:08_06 "
    "Mimo trajectory: 12.254 versus 13.176 seconds, slower overall by 0.922 "
    "seconds despite local direct acceleration of one served block, 1 of 26 "
    "directly served. Served-block BASE shares 21.3, 15.8, and about 5.0 percent; "
    "descriptive; no threshold is established."
)

AXIS_MAX_S = 30.0
AXIS_TICKS = (0, 5, 10, 15, 20, 25, 30)


def build_figure_b(rows: list[dict]) -> str:
    W, H = 1200, 570
    PX0, PX1 = 360, 920
    scale = (PX1 - PX0) / AXIS_MAX_S

    def x_of(s: float) -> float:
        return PX0 + s * scale

    p = svg_open(W, H, "replay-title", "Measured task-replay outcomes",
                 "replay-desc", FIGURE_B_DESC)
    p.append(arrow_defs())
    p.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="{CANVAS}"/>')
    p.append(
        f'<text x="40" y="44" font-family="{FONT_SANS}" font-size="25" '
        f'font-weight="700" fill="{INK}">Measured task-replay outcomes</text>')
    scope_strip(p, 40, 58, SCOPE_B, 1120)

    # Legend: shape + label, never color alone.
    ly = 122
    p.append(
        f'<rect x="40" y="{ly - 12}" width="13" height="13" fill="{PANEL}" '
        f'stroke="{INK}" stroke-width="2.5"/>')
    p.append(
        f'<text x="60" y="{ly}" font-family="{FONT_SANS}" font-size="14" fill="{INK}">'
        "BASE (plain Python)</text>")
    p.append(
        f'<circle cx="258" cy="{ly - 5}" r="7" fill="{ACCENT}" '
        f'stroke="{ACCENT_DARK}" stroke-width="1.5"/>')
    p.append(
        f'<text x="272" y="{ly}" font-family="{FONT_SANS}" font-size="14" fill="{INK}">'
        "Recalc 0.2.0 (warm paired replay)</text>")
    p.append(
        f'<text x="1160" y="{ly}" text-anchor="end" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{MUTED}">paired points \u00b7 one linear axis</text>')

    row_ys = (178, 298, 418)
    # Gridlines span the row band.
    for t in AXIS_TICKS:
        gx = x_of(float(t))
        p.append(
            f'<line x1="{gx:.1f}" y1="140" x2="{gx:.1f}" y2="448" '
            f'stroke="{PANEL_EDGE}" stroke-width="1"/>')

    for row, ry in zip(rows, row_ys):
        if row["boundary"]:
            # Subtle left-side marker only: the row stays symmetric with the rest.
            p.append(
                f'<rect x="24" y="{ry - 26}" width="5" height="52" rx="2.5" '
                f'fill="{NEUTRAL_EDGE}"/>')
        # Left identity.
        p.append(
            f'<text x="40" y="{ry - 12}" font-family="{FONT_SANS}" font-size="17" '
            f'font-weight="700" fill="{INK}">{esc(row["display_identity"])}</text>')
        p.append(
            f'<text x="40" y="{ry + 10}" font-family="{FONT_MONO}" font-size="12.5" '
            f'fill="{MUTED}">{esc(row["trajectory_id"])}</text>')
        if row["boundary"]:
            p.append(
                f'<rect x="40" y="{ry + 20}" width="118" height="22" rx="11" '
                f'fill="{PANEL}" stroke="{NEUTRAL_EDGE}" stroke-width="1.2"/>')
            p.append(
                f'<text x="99" y="{ry + 36}" text-anchor="middle" '
                f'font-family="{FONT_SANS}" font-size="12.5" font-weight="600" '
                f'fill="{MUTED}">boundary case</text>')
        # Paired markers.
        bx, rx = x_of(row["base_s"]), x_of(row["recalc_s"])
        p.append(
            f'<line x1="{bx:.1f}" y1="{ry}" x2="{rx:.1f}" y2="{ry}" '
            f'stroke="{NEUTRAL_EDGE}" stroke-width="2.5"/>')
        p.append(
            f'<rect x="{bx - 6.5:.1f}" y="{ry - 6.5}" width="13" height="13" '
            f'fill="{PANEL}" stroke="{INK}" stroke-width="2.5"/>')
        p.append(
            f'<circle cx="{rx:.1f}" cy="{ry}" r="7" fill="{ACCENT}" '
            f'stroke="{ACCENT_DARK}" stroke-width="1.5"/>')
        p.append(
            f'<text x="{bx:.1f}" y="{ry - 15}" text-anchor="middle" '
            f'font-family="{FONT_SANS}" font-size="14" fill="{INK}">'
            f"{fmt3(row['base_s'])} s</text>")
        p.append(
            f'<text x="{rx:.1f}" y="{ry + 32}" text-anchor="middle" '
            f'font-family="{FONT_SANS}" font-size="14" font-weight="600" '
            f'fill="{ACCENT_DARK}">{fmt3(row["recalc_s"])} s</text>')
        # Right annotations, vertically centered on the row.
        ax = 944
        lines = [(f"{row['saved_display']} \u00b7 {row['pct_display']}", True, INK)]
        if row["boundary"]:
            lines.append(("task replay slower", True, INK))
        lines.append((f"{row['served']}/{row['total']} directly served", False, INK))
        lines.append((f"{row['share_display']} of BASE replay time", False, MUTED))
        y0 = ry - (len(lines) - 1) * 11
        for i, (text, bold, color) in enumerate(lines):
            p.append(
                f'<text x="{ax}" y="{y0 + i * 22}" font-family="{FONT_SANS}" '
                f'font-size="{"15" if bold and i == 0 else "13.5"}" '
                f'font-weight="{"700" if bold else "400"}" fill="{color}">'
                f"{esc(text)}</text>")

    # Shared linear axis.
    ay = 462
    p.append(
        f'<line x1="{PX0}" y1="{ay}" x2="{PX1}" y2="{ay}" '
        f'stroke="{INK}" stroke-width="1.5"/>')
    for t in AXIS_TICKS:
        gx = x_of(float(t))
        p.append(
            f'<line x1="{gx:.1f}" y1="{ay}" x2="{gx:.1f}" y2="{ay + 6}" '
            f'stroke="{INK}" stroke-width="1.5"/>')
        p.append(
            f'<text x="{gx:.1f}" y="{ay + 24}" text-anchor="middle" '
            f'font-family="{FONT_SANS}" font-size="13" fill="{MUTED}">{t}</text>')
    p.append(
        f'<text x="{(PX0 + PX1) / 2}" y="{ay + 44}" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="13" fill="{MUTED}">'
        "replay time in seconds \u2014 shared linear axis</text>")

    # Scope fence.
    p.append(
        f'<text x="600" y="536" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{MUTED}">{esc(FIGURE_B_FENCE_1)}</text>')
    p.append(
        f'<text x="600" y="555" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{MUTED}">{esc(FIGURE_B_FENCE_2)}</text>')

    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- Figure C: controlled applicability --------------------------------------------

FIGURE_C_DESC = (
    "Proportional stacked bar of 136 executed Python invocations in the frozen "
    "SpreadsheetBench-2 controlled stratum, 6 tasks and 9 trajectories. 119 "
    "invocations ran reference execution on genuine openpyxl. 10 invocations "
    "were fully directly served, 7.4 percent. 7 invocations were admitted but "
    "served zero direct loads, shown hatched as a neutral designed fallback "
    "outcome. Useful direct service appeared across 4 of 6 tasks "
    "and 4 of 9 trajectories. Operation counts measure depth inside served "
    "invocations, not prevalence."
)


def build_figure_c(data: dict) -> str:
    W, H = 1200, 425
    BX, BW, BY, BH = 60, 1080, 208, 64
    n = data["executed"]
    w_ref = BW * data["reference"] / n
    w_dir = BW * data["direct"] / n
    w_adm = BW - w_ref - w_dir

    p = svg_open(W, H, "appl-title", "Where Recalc directly served work",
                 "appl-desc", FIGURE_C_DESC)
    p.append(arrow_defs())
    p.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="{CANVAS}"/>')
    p.append(
        f'<text x="40" y="44" font-family="{FONT_SANS}" font-size="25" '
        f'font-weight="700" fill="{INK}">Where Recalc directly served work</text>')
    scope_strip(p, 40, 58, SCOPE_C, 1120)

    p.append(
        f'<text x="60" y="132" font-family="{FONT_SANS}" font-size="27" '
        f'font-weight="800" fill="{INK}">10 / 136 directly served \u00b7 7.4%</text>')
    p.append(
        f'<text x="60" y="164" font-family="{FONT_SANS}" font-size="17" '
        f'font-weight="600" fill="{INK}">Useful direct service appeared in '
        "4 / 6 tasks</text>")
    p.append(
        f'<text x="60" y="188" font-family="{FONT_SANS}" font-size="14" '
        f'fill="{MUTED}">4 / 9 trajectories</text>')

    # Proportional stacked bar.
    x_ref, x_dir, x_adm = BX, BX + w_ref, BX + w_ref + w_dir
    p.append(
        f'<rect x="{x_ref:.1f}" y="{BY}" width="{w_ref:.1f}" height="{BH}" '
        f'fill="{NEUTRAL_FILL}" stroke="{NEUTRAL_EDGE}" stroke-width="1.5"/>')
    p.append(
        f'<rect x="{x_dir:.1f}" y="{BY}" width="{w_dir:.1f}" height="{BH}" '
        f'fill="{ACCENT}" stroke="{ACCENT_DARK}" stroke-width="1.5"/>')
    p.append(
        f'<rect x="{x_adm:.1f}" y="{BY}" width="{w_adm:.1f}" height="{BH}" '
        'fill="url(#hatch)" '
        f'stroke="{NEUTRAL_EDGE}" stroke-width="1.5"/>')
    p.append(
        f'<text x="{x_ref + w_ref / 2:.1f}" y="{BY + BH / 2 + 6}" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="16" font-weight="600" fill="{INK}">'
        "119 reference</text>")
    p.append(
        f'<text x="{x_dir + w_dir / 2:.1f}" y="{BY + BH / 2 + 6}" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="15" font-weight="700" fill="#ffffff">'
        "10</text>")
    # Leader labels for the narrow segments (above vs below to avoid collision).
    cx_dir = x_dir + w_dir / 2
    p.append(
        f'<line x1="{cx_dir:.1f}" y1="{BY - 6}" x2="{cx_dir:.1f}" y2="{BY - 1}" '
        f'stroke="{NEUTRAL_EDGE}" stroke-width="1.2"/>')
    p.append(
        f'<text x="{cx_dir:.1f}" y="{BY - 10}" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="14" font-weight="600" fill="{INK}">'
        "10 directly served</text>")
    cx_adm = x_adm + w_adm / 2
    p.append(
        f'<line x1="{cx_adm:.1f}" y1="{BY + BH + 1}" x2="{cx_adm:.1f}" '
        f'y2="{BY + BH + 6}" stroke="{NEUTRAL_EDGE}" stroke-width="1.2"/>')
    p.append(
        f'<text x="{cx_adm:.1f}" y="{BY + BH + 28}" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="14" font-weight="600" fill="{INK}">'
        "7 admitted \u00b7 0 served</text>")

    p.append(
        f'<text x="60" y="{BY + BH + 28}" font-family="{FONT_SANS}" font-size="13.5" '
        f'fill="{MUTED}">136 executed Python invocations (controlled stratum)</text>')

    # Legend.
    ly = 340
    p.append(
        f'<rect x="60" y="{ly - 13}" width="18" height="14" fill="{NEUTRAL_FILL}" '
        f'stroke="{NEUTRAL_EDGE}" stroke-width="1.2"/>')
    p.append(
        f'<text x="84" y="{ly}" font-family="{FONT_SANS}" font-size="13.5" '
        f'fill="{INK}">reference execution (genuine openpyxl)</text>')
    p.append(
        f'<rect x="430" y="{ly - 13}" width="18" height="14" fill="{ACCENT}" '
        f'stroke="{ACCENT_DARK}" stroke-width="1.2"/>')
    p.append(
        f'<text x="454" y="{ly}" font-family="{FONT_SANS}" font-size="13.5" '
        f'fill="{INK}">fully directly served</text>')
    p.append(
        f'<rect x="668" y="{ly - 13}" width="18" height="14" fill="url(#hatch)" '
        f'stroke="{NEUTRAL_EDGE}" stroke-width="1.2"/>')
    p.append(
        f'<text x="692" y="{ly}" font-family="{FONT_SANS}" font-size="13.5" '
        f'fill="{INK}">admitted \u00b7 0 served (fallback \u2014 designed outcome)</text>')

    p.append(
        f'<text x="60" y="388" font-family="{FONT_SANS}" font-size="14" '
        f'fill="{MUTED}">Operation counts measure depth inside served invocations, '
        "not prevalence.</text>")

    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- Figure D: R3 distribution ------------------------------------------------------

FIGURE_D_TITLE = "Historical R3 mechanism effect was concentrated"

FIGURE_D_DESC = (
    "Historical R3 full-cell iteration mechanism population: 30 workloads ranked "
    "by ON/OFF warm runtime ratio, OFF rc3-equivalent predecessor control versus "
    "ON iteration candidate. 23 workloads faster under ON, 7 slower. Median ON/OFF "
    "ratio 0.913, about 8.75 percent lower. The top three workloads supplied 84.2 "
    "percent of positive savings; the largest regression was 49.7 milliseconds. "
    "The aggregate effect was concentrated and must not be interpreted as a "
    "typical-workload effect. Historical mechanism evidence, not released-product "
    "task performance."
)

FIGURE_D_FENCE_1 = "Historical R3 mechanism population \u00b7 OFF \u2192 ON only."
FIGURE_D_FENCE_2 = ("Heavy-tailed: must not be interpreted as a typical-workload effect.")

D_AXIS_MAX = 1.15
D_TICKS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.15)


def halo_text(x: float, y: float, text: str, size: float = 12.5,
              anchor: str = "start", weight: int = 400, color: str = INK) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="{FONT_SANS}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" stroke="{CANVAS}" stroke-width="3.5" paint-order="stroke">'
        f"{esc(text)}</text>")


def build_figure_d(data: dict) -> str:
    W, H = 1200, 640
    PX0, PX1 = 140, 800
    RY0, STEP = 168.0, 12.5

    def x_of(r: float) -> float:
        return PX0 + (PX1 - PX0) * r / D_AXIS_MAX

    def y_of(rank: int) -> float:
        return RY0 + (rank - 1) * STEP

    p = svg_open(W, H, "r3-title", FIGURE_D_TITLE, "r3-desc", FIGURE_D_DESC)
    p.append(arrow_defs())
    p.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="{CANVAS}"/>')
    p.append(
        f'<text x="40" y="44" font-family="{FONT_SANS}" font-size="25" '
        f'font-weight="700" fill="{INK}">{esc(FIGURE_D_TITLE)}</text>')
    scope_strip(p, 40, 58, SCOPE_D, 1120)

    # Column headers.
    p.append(
        f'<text x="112" y="150" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="12.5" fill="{MUTED}">rank</text>')
    p.append(
        f'<text x="420" y="150" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="12.5" fill="{MUTED}">\u2190 faster under ON</text>')
    p.append(
        f'<text x="{x_of(1.0):.1f}" y="150" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="12.5" font-weight="700" fill="{INK}">'
        "1.0\u00d7 = no change</text>")

    y_top, y_bot = RY0 - 8, y_of(30) + 8
    for t in (0.0, 0.25, 0.5, 0.75):
        gx = x_of(t)
        p.append(
            f'<line x1="{gx:.1f}" y1="{y_top}" x2="{gx:.1f}" y2="{y_bot}" '
            f'stroke="{PANEL_EDGE}" stroke-width="1"/>')
    # Prominent no-change reference.
    p.append(
        f'<line x1="{x_of(1.0):.1f}" y1="{y_top}" x2="{x_of(1.0):.1f}" y2="{y_bot}" '
        f'stroke="{INK}" stroke-width="2.5"/>')

    for row in data["rows"]:
        ry = y_of(row["rank"])
        px = x_of(row["ratio"])
        p.append(
            f'<text x="112" y="{ry + 4}" text-anchor="middle" '
            f'font-family="{FONT_SANS}" font-size="11" fill="{MUTED}">'
            f"{row['rank']}</text>")
        p.append(
            f'<line x1="{x_of(1.0):.1f}" y1="{ry:.1f}" x2="{px:.1f}" y2="{ry:.1f}" '
            f'stroke="{NEUTRAL_EDGE}" stroke-width="1.2"/>')
        if row["faster"]:
            p.append(
                f'<circle cx="{px:.1f}" cy="{ry:.1f}" r="3.5" fill="{INK}"/>')
        else:
            p.append(
                f'<circle cx="{px:.1f}" cy="{ry:.1f}" r="4.2" fill="{PANEL}" '
                f'stroke="{INK}" stroke-width="1.8"/>')

    # Median marker between ranks 15 and 16.
    y_med = (y_of(15) + y_of(16)) / 2
    p.append(
        f'<line x1="{PX0}" y1="{y_med:.1f}" x2="{PX1}" y2="{y_med:.1f}" '
        f'stroke="{MUTED}" stroke-width="1.2" stroke-dasharray="5 4"/>')
    p.append(halo_text(x_of(1.0) - 8, y_med - 5,
                       f"median {data['median_display']}", size=12,
                       anchor="end", color=MUTED))

    # Selected end annotations (haloed so stems pass underneath quietly).
    p.append(halo_text(x_of(data["rows"][0]["ratio"]) + 9, y_of(1) + 4,
                       f"strongest improvement \u00b7 {data['min_display']}"))
    p.append(halo_text(x_of(data["rows"][-1]["ratio"]) - 9, y_of(30) + 4,
                       f"largest regression \u00b7 {data['max_display']} "
                       f"(+{data['largest_regression_display']})", anchor="end"))

    # Summary panel: concentration context, never a new headline.
    PX, PW, PY = 830, 330, 168
    PH = 344
    p.append(
        f'<rect x="{PX}" y="{PY}" width="{PW}" height="{PH}" rx="8" '
        f'fill="{PANEL}" stroke="{PANEL_EDGE}" stroke-width="1.5"/>')
    tx = PX + 18
    p.append(
        f'<text x="{tx}" y="{PY + 30}" font-family="{FONT_SANS}" font-size="16.5" '
        f'font-weight="700" fill="{INK}">23 / 30 faster \u00b7 7 / 30 slower</text>')
    p.append(
        f'<text x="{tx}" y="{PY + 56}" font-family="{FONT_SANS}" font-size="14" '
        f'fill="{INK}">median ON/OFF {data["median_display"]} '
        f"(\u2248 {data['median_pct_display']} lower)</text>")
    p.append(
        f'<text x="{tx}" y="{PY + 82}" font-family="{FONT_SANS}" font-size="14" '
        f'font-weight="600" fill="{INK}">top 3 = {data["top3_display"]} '
        "of positive savings</text>")
    p.append(
        f'<text x="{tx}" y="{PY + 108}" font-family="{FONT_SANS}" font-size="14" '
        f'fill="{INK}">largest regression '
        f"{data['largest_regression_display']}</text>")
    p.append(
        f'<line x1="{tx}" y1="{PY + 124}" x2="{PX + PW - 18}" y2="{PY + 124}" '
        f'stroke="{PANEL_EDGE}" stroke-width="1"/>')
    p.append(f'<circle cx="{tx + 5}" cy="{PY + 144}" r="3.5" fill="{INK}"/>')
    p.append(
        f'<text x="{tx + 16}" y="{PY + 148}" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{INK}">faster under ON (23)</text>')
    p.append(
        f'<circle cx="{tx + 5}" cy="{PY + 166}" r="4.2" fill="{PANEL}" '
        f'stroke="{INK}" stroke-width="1.8"/>')
    p.append(
        f'<text x="{tx + 16}" y="{PY + 170}" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{INK}">slower under ON (7)</text>')
    p.append(
        f'<line x1="{tx}" y1="{PY + 186}" x2="{PX + PW - 18}" y2="{PY + 186}" '
        f'stroke="{PANEL_EDGE}" stroke-width="1"/>')
    p.append(
        f'<text x="{tx}" y="{PY + 208}" font-family="{FONT_SANS}" font-size="12.5" '
        f'fill="{MUTED}">OFF predecessor \u2192 ON iteration</text>')
    p.append(
        f'<text x="{tx}" y="{PY + 227}" font-family="{FONT_SANS}" font-size="12.5" '
        f'fill="{MUTED}">candidate \u2014 historical mechanism</text>')
    p.append(
        f'<text x="{tx}" y="{PY + 246}" font-family="{FONT_SANS}" font-size="12.5" '
        f'fill="{MUTED}">evidence, not BASE \u2192 Recalc 0.2.0</text>')
    p.append(
        f'<text x="{tx}" y="{PY + 280}" font-family="{FONT_SANS}" font-size="13" '
        f'font-weight="600" fill="{INK}">must not be interpreted as</text>')
    p.append(
        f'<text x="{tx}" y="{PY + 299}" font-family="{FONT_SANS}" font-size="13" '
        f'font-weight="600" fill="{INK}">a typical-workload effect</text>')
    p.append(
        f'<text x="{tx}" y="{PY + 329}" font-family="{FONT_SANS}" font-size="12.5" '
        f'fill="{MUTED}">30 / 30 workloads shown, ranked by ratio</text>')

    # Axis.
    ay = 550
    p.append(
        f'<line x1="{PX0}" y1="{ay}" x2="{PX1}" y2="{ay}" '
        f'stroke="{INK}" stroke-width="1.5"/>')
    for t in D_TICKS:
        gx = x_of(t)
        p.append(
            f'<line x1="{gx:.1f}" y1="{ay}" x2="{gx:.1f}" y2="{ay + 6}" '
            f'stroke="{INK}" stroke-width="1.5"/>')
        label = f"{t:g}\u00d7" if t != 1.0 else "1.0\u00d7"
        p.append(
            f'<text x="{gx:.1f}" y="{ay + 24}" text-anchor="middle" '
            f'font-family="{FONT_SANS}" font-size="13" fill="{MUTED}">{label}</text>')
    p.append(
        f'<text x="{(PX0 + PX1) / 2}" y="{ay + 44}" text-anchor="middle" '
        f'font-family="{FONT_SANS}" font-size="13" fill="{MUTED}">'
        "ON / OFF runtime ratio \u00b7 warm medians of 3 reps</text>")

    p.append(
        f'<text x="600" y="614" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{MUTED}">{esc(FIGURE_D_FENCE_1)}</text>')
    p.append(
        f'<text x="600" y="632" text-anchor="middle" font-family="{FONT_SANS}" '
        f'font-size="13" fill="{MUTED}">{esc(FIGURE_D_FENCE_2)}</text>')

    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- Build --------------------------------------------------------------------------

def build() -> bool:
    ok, rows_b, data_c, data_d = verify()
    if not ok:
        return False
    outputs = (
        (ASSET_A, GENERATED_COMMENT + "\n" + build_figure_a()),
        (ASSET_B, GENERATED_COMMENT + "\n" + build_figure_b(rows_b)),
        (ASSET_C, GENERATED_COMMENT + "\n" + build_figure_c(data_c)),
        (ASSET_D, GENERATED_COMMENT + "\n" + build_figure_d(data_d)),
    )
    for path, content in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(content.encode('utf-8'))} bytes)")
    return True


if __name__ == "__main__":
    if "--verify" in sys.argv:
        sys.exit(0 if verify()[0] else 1)
    if "--build" in sys.argv:
        sys.exit(0 if build() else 1)
    print("usage: generate.py --verify | --build")
    sys.exit(2)
