"""Score the 20_05 / 11_02 forced-exposure replication.

The experimental unit is one full task run. Primary metric is fingerprint
accuracy on the frozen exposed-target subset, not a pooled cell count.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "benchmark"))

from fingerprint import relative_fingerprint  # noqa: E402
from formula_index_ambient_score import parse_ambient_trajectory  # noqa: E402
from formula_index_score import _find_trajectory, load_formulas  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()

from ambient import build_ambient_payload, parse_view_xlsx_action  # noqa: E402

RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
MANIFEST = ROOT / "benchmark/slices/fm-ambient-replication-targets.json"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=RUNS)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--control-prefix", default="glm-5.3-flash-fm-ambient-repl-control")
    parser.add_argument(
        "--treatment-prefix", default="glm-5.3-flash-fm-ambient-repl-treatment"
    )
    parser.add_argument("--repeats", type=int, default=5)
    return parser.parse_args()


def _key(row: dict[str, Any]) -> tuple[str, int, int]:
    return row["sheet"], row["col"], row["row"]


def _rate(matches: int, n: int) -> float | None:
    if n == 0:
        return None
    return round(matches / n, 4)


def _summarize(values: list[float | None]) -> dict[str, Any]:
    present = [value for value in values if isinstance(value, (int, float))]
    if not present:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None, "values": values}
    return {
        "n": len(present),
        "mean": round(statistics.mean(present), 4),
        "median": round(float(statistics.median(present)), 4),
        "min": round(min(present), 4),
        "max": round(max(present), 4),
        "values": values,
    }


def _official(run_root: Path, task_key: str) -> dict[str, Any]:
    path = run_root / "official_scores.json"
    if not path.is_file():
        return {}
    return (json.loads(path.read_text()).get("tasks") or {}).get(task_key) or {}


def _first_index_meta(traj_path: Path | None) -> dict[str, Any]:
    empty = {
        "payload_emitted": False,
        "observation_length": None,
        "index_chars": None,
        "truncated": None,
    }
    if traj_path is None or not traj_path.is_file():
        return empty
    data = json.loads(traj_path.read_text(encoding="utf-8"))
    for step in data.get("trajectory", []):
        observation = str(step.get("observation") or "")
        start = observation.find("STRUCTURAL INDEX")
        if start < 0:
            continue
        body = observation[start:]
        header = body.split("\n", 1)[0]
        return {
            "payload_emitted": True,
            "observation_length": len(observation),
            "index_chars": len(body),
            "truncated": "truncated=true" in header,
        }
    return empty


def score_one(
    run_root: Path,
    task_id: str,
    frozen: dict[str, Any],
    *,
    inp_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    task_key = f"Financial_Model:{task_id}"
    task_root = run_root / f"Financial_Model-{task_id}"
    output = task_root / "output.xlsx"
    submitted = load_formulas(output) if output.is_file() else None
    traj_path = _find_trajectory(task_root)
    trajectory = parse_ambient_trajectory(traj_path)
    index_meta = _first_index_meta(traj_path)
    groups = {
        "exposed": [row for row in frozen["targets"] if row["in_fixed_exposed_subset"]],
        "recoverable_unexposed": [
            row
            for row in frozen["targets"]
            if row["recoverable"] and not row["in_fixed_exposed_subset"]
        ],
        "unrecoverable": [row for row in frozen["targets"] if not row["recoverable"]],
        "all_blank_fill": frozen["targets"],
    }

    def pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
        hits = 0
        for row in rows:
            pos = (row["sheet"], row["col"], row["row"])
            formula = None if submitted is None else submitted.get(pos)
            if not formula:
                continue
            fp = relative_fingerprint(formula, row["col"], row["row"], sheet=row["sheet"])
            if fp.text == row["golden_fingerprint"]:
                hits += 1
        return {
            "n": len(rows),
            "matches": hits,
            "rate": _rate(hits, len(rows)),
        }

    rates = {name: pack(rows) for name, rows in groups.items()}
    frozen_eq = set(frozen["fixed_exposed_eq_ids"])
    observed_eq = set(trajectory.get("eq_ids") or [])
    reconstructed_eq: set[str] = set()
    first = trajectory.get("first_content_action")
    parsed = parse_view_xlsx_action(first) if first else None
    if parsed is not None and parsed.mode == "content":
        reconstructed = build_ambient_payload(
            inp_path,
            sheet=parsed.sheet,
            start_row=parsed.start_row,
            end_row=parsed.end_row,
            limit=10_000,
        )
        reconstructed_eq = set(reconstructed["eq_ids"])
    official = _official(run_root, task_key)
    return {
        "task": task_key,
        "run_name": run_root.name,
        "workbook_present": output.is_file(),
        "rates": rates,
        "integrity": {
            **index_meta,
            "correct_class_exposed_observed": bool(frozen_eq) and frozen_eq <= observed_eq,
            "correct_class_exposed_reconstructed": (
                bool(frozen_eq) and frozen_eq <= reconstructed_eq
            ),
            "frozen_eq_ids": sorted(frozen_eq),
            "observed_eq_ids": sorted(observed_eq),
            "first_content_action": first,
        },
        "used_homologue": trajectory.get("used_homologue"),
        "model_calls": trajectory.get("model_calls"),
        "prompt_tokens": trajectory.get("prompt_tokens"),
        "completion_tokens": trajectory.get("completion_tokens"),
        "cost": trajectory.get("cost"),
        "modification_accuracy": official.get("modification_accuracy"),
        "regression_accuracy": official.get("regression_accuracy"),
        "exact": official.get("accuracy") == 1.0 if official else None,
        "official_error": official.get("error_message"),
    }


def pair_repeats(control: list[dict[str, Any]], treatment: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paired = []
    for left, right in zip(control, treatment, strict=True):
        exposed_c = left["rates"]["exposed"]["rate"]
        exposed_t = right["rates"]["exposed"]["rate"]
        unexp_c = left["rates"]["recoverable_unexposed"]["rate"]
        unexp_t = right["rates"]["recoverable_unexposed"]["rate"]
        unrec_c = left["rates"]["unrecoverable"]["rate"]
        unrec_t = right["rates"]["unrecoverable"]["rate"]
        delta_exposed = None if exposed_c is None or exposed_t is None else round(exposed_t - exposed_c, 4)
        paired.append(
            {
                "repeat": len(paired) + 1,
                "control_run": left["run_name"],
                "treatment_run": right["run_name"],
                "delta_exposed": delta_exposed,
                "delta_unexposed": (
                    None if unexp_c is None or unexp_t is None else round(unexp_t - unexp_c, 4)
                ),
                "delta_unrecoverable": (
                    None if unrec_c is None or unrec_t is None else round(unrec_t - unrec_c, 4)
                ),
                "direction_exposed": (
                    None
                    if delta_exposed is None
                    else "treatment+"
                    if delta_exposed > 0
                    else "treatment-"
                    if delta_exposed < 0
                    else "tie"
                ),
                "control": left,
                "treatment": right,
            }
        )
    return paired


def main() -> int:
    args = _arguments()
    frozen = json.loads(MANIFEST.read_text())
    dataset = json.loads((DATA / "Financial_Model" / "dataset.json").read_text())
    report: dict[str, Any] = {
        "primary_metric": (
            "run-level fingerprint accuracy on the frozen exposed-target subset"
        ),
        "tasks": {},
    }
    for task_id, task_frozen in frozen["tasks"].items():
        record = next(item for item in dataset if item["id"] == task_id)
        inp_path = DATA / "Financial_Model" / record["spreadsheet_path"]
        gold_path = DATA / "Financial_Model" / record["golden_response_path"]
        control_rows = []
        treatment_rows = []
        for repeat in range(1, args.repeats + 1):
            control_rows.append(
                score_one(
                    args.runs_dir / f"{args.control_prefix}-{repeat}",
                    task_id,
                    task_frozen,
                    inp_path=inp_path,
                    gold_path=gold_path,
                )
            )
            treatment_rows.append(
                score_one(
                    args.runs_dir / f"{args.treatment_prefix}-{repeat}",
                    task_id,
                    task_frozen,
                    inp_path=inp_path,
                    gold_path=gold_path,
                )
            )
        paired = pair_repeats(control_rows, treatment_rows)
        report["tasks"][task_id] = {
            "frozen_exposed_n": task_frozen["counts"]["fixed_exposed"],
            "frozen_exposed_strata": task_frozen["fixed_exposed_strata"],
            "control": {
                "exposed": _summarize([row["rates"]["exposed"]["rate"] for row in control_rows]),
                "recoverable_unexposed": _summarize(
                    [row["rates"]["recoverable_unexposed"]["rate"] for row in control_rows]
                ),
                "unrecoverable": _summarize(
                    [row["rates"]["unrecoverable"]["rate"] for row in control_rows]
                ),
                "all_blank_fill": _summarize(
                    [row["rates"]["all_blank_fill"]["rate"] for row in control_rows]
                ),
                "exact": sum(1 for row in control_rows if row.get("exact")),
                "modification_accuracy_mean": _summarize(
                    [row["modification_accuracy"] for row in control_rows]
                )["mean"],
                "regression_accuracy_mean": _summarize(
                    [row["regression_accuracy"] for row in control_rows]
                )["mean"],
                "model_calls": sum(row.get("model_calls") or 0 for row in control_rows),
                "prompt_tokens": sum(row.get("prompt_tokens") or 0 for row in control_rows),
                "completion_tokens": sum(
                    row.get("completion_tokens") or 0 for row in control_rows
                ),
                "cost": round(sum(row.get("cost") or 0 for row in control_rows), 6),
            },
            "treatment": {
                "exposed": _summarize(
                    [row["rates"]["exposed"]["rate"] for row in treatment_rows]
                ),
                "recoverable_unexposed": _summarize(
                    [row["rates"]["recoverable_unexposed"]["rate"] for row in treatment_rows]
                ),
                "unrecoverable": _summarize(
                    [row["rates"]["unrecoverable"]["rate"] for row in treatment_rows]
                ),
                "all_blank_fill": _summarize(
                    [row["rates"]["all_blank_fill"]["rate"] for row in treatment_rows]
                ),
                "exact": sum(1 for row in treatment_rows if row.get("exact")),
                "modification_accuracy_mean": _summarize(
                    [row["modification_accuracy"] for row in treatment_rows]
                )["mean"],
                "regression_accuracy_mean": _summarize(
                    [row["regression_accuracy"] for row in treatment_rows]
                )["mean"],
                "model_calls": sum(row.get("model_calls") or 0 for row in treatment_rows),
                "prompt_tokens": sum(row.get("prompt_tokens") or 0 for row in treatment_rows),
                "completion_tokens": sum(
                    row.get("completion_tokens") or 0 for row in treatment_rows
                ),
                "cost": round(sum(row.get("cost") or 0 for row in treatment_rows), 6),
            },
            "paired": paired,
        }
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
