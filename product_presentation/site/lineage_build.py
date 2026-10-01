"""Build lineage visuals from frozen Candidate-A exact-trace data.

Reads candidate_a_a1_checkpoint_rerun_01/exact_trace_performance.jsonl +
.json, verifies the frozen report values (median 1.423s saved, 44.46%,
50/51 positive, 7 tasks, 3 real parses vs 0 per trace), and emits:
  - lineage_traces.svg       per-task small multiples, all 51 traces
  - lineage_composition.svg  live H1 task-time composition (model/network share)
  - lineage_tasks.html       per-task table snippet for the review page

Usage: python3 lineage_build.py   (run from repo root; output to
product_presentation/site/). Fails loudly if the data does not match the
frozen report. INTERNAL LINEAGE ONLY — not rc2 product behavior.
"""

from __future__ import annotations

import html
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "candidate_a_a1_checkpoint_rerun_01"
SITE = ROOT / "product_presentation" / "site"


def load() -> tuple[list[dict], dict]:
    rows = [json.loads(line) for line in (DATA / "exact_trace_performance.jsonl").read_text().splitlines()]
    summary = json.loads((DATA / "exact_trace_performance.json").read_text())
    return rows, summary


def verify(rows: list[dict], summary: dict) -> None:
    assert len(rows) == 51 == summary["traces"], len(rows)
    saved = [r["absolute_time_saved_s"] for r in rows]
    assert abs(statistics.median(saved) - summary["median_absolute_time_saved_s"]) < 1e-9
    assert abs(statistics.median(saved) - 1.423197805066593) < 1e-6
    assert sum(1 for s in saved if s > 0) == 50 == summary["positive_traces"]
    assert all(r["parse_count_real"] == 3 and r["parse_count_candidate"] == 0 for r in rows)
    by_task: dict[str, list[dict]] = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)
    assert sorted(by_task) == sorted(summary["by_task"]), sorted(by_task)
    for task, expected in summary["by_task"].items():
        assert len(by_task[task]) == expected["traces"], task


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def traces_svg(rows: list[dict]) -> str:
    tasks = sorted({r["task_id"] for r in rows})
    by_task = {t: [r for r in rows if r["task_id"] == t] for t in tasks}
    max_s = max(r["real_openpyxl_time_s"] for r in rows)
    # Nice upper bound: round up to whole or half second.
    top = (int(max_s) + 1) if max_s % 1 > 0.5 else (int(max_s) + 0.5)
    left, right, width = 150, 745, 760
    scale = (right - left - 70) / top  # 70px reserved for saved-value labels
    x0 = left
    row_h, head_h = 14, 30
    head_block = 76
    total_h = head_block + len(tasks) * head_h + len(rows) * row_h + 46
    parts = [
        (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {total_h}" '
        'font-family="system-ui, -apple-system, sans-serif" role="img">'),
        ("<desc>All 51 exact-trace read replays grouped by the 7 contacted tasks: "
        "real openpyxl seconds vs fast-path seconds per trace.</desc>"),
        ('<text x="12" y="22" font-size="15" font-weight="600" fill="#111">'
        "51 exact-trace read replays, by task — seconds per trace</text>"),
        ('<text x="12" y="40" font-size="12" fill="#555">gray = real openpyxl (3 parses) · '
        "green = fast path (0 parses) · exact-trace replay, Candidate-A era — not rc2, "
        "not task time</text>"),
        f'<line x1="{x0}" y1="62" x2="{x0 + top * scale}" y2="62" stroke="#999"/>',
    ]
    tick = 1.0 if top > 4 else 0.5
    tick_val = 0.0
    while tick_val <= top + 1e-9:
        x = x0 + tick_val * scale
        label = f"{tick_val:g}s"
        parts.append(f'<line x1="{x:.1f}" y1="58" x2="{x:.1f}" y2="62" stroke="#999"/>')
        parts.append(
            f'<text x="{x:.1f}" y="55" font-size="10" fill="#555" text-anchor="middle">'
            f"{label}</text>"
        )
        tick_val += tick
    y = head_block
    for task in tasks:
        group = by_task[task]
        med_saved = statistics.median(r["absolute_time_saved_s"] for r in group)
        med_pct = statistics.median(r["reduction_pct"] for r in group)
        pos = sum(1 for r in group if r["absolute_time_saved_s"] > 0)
        parts.append(
            f'<text x="12" y="{y + 19}" font-size="13" font-weight="600" fill="#111">'
            f"{esc(task)}</text>"
            f'<text x="252" y="{y + 19}" font-size="12" fill="#555">— {len(group)} traces · '
            f"median {med_saved:.2f}s "
            f"saved ({med_pct:.1f}%) · {pos}/{len(group)} positive</text>"
        )
        y += head_h
        for k, r in enumerate(group, 1):
            real_w = r["real_openpyxl_time_s"] * scale
            fast_w = r["candidate_a_time_s"] * scale
            saved = r["absolute_time_saved_s"]
            tag = f"{saved:+.2f}s" if saved < 0 else f"{saved:.2f}s"
            tag_color = "#b42318" if saved < 0 else "#555"
            parts.append(
                f'<text x="24" y="{y + 10}" font-size="10" fill="#555">t{k}</text>'
                f'<rect x="{x0:.1f}" y="{y + 1}" width="{real_w:.1f}" height="5" '
                'fill="#999"/>'
                f'<rect x="{x0:.1f}" y="{y + 7}" width="{fast_w:.1f}" height="5" '
                'fill="#1a7f37"/>'
                f'<text x="{x0 + top * scale + 6:.1f}" y="{y + 11}" font-size="10" '
                f'fill="{tag_color}">{tag}</text>'
            )
            y += row_h
    parts.append(
        f'<text x="12" y="{y + 22}" font-size="12" fill="#555">Each trace = one replayed '
        "read sequence (3 real parses vs 0). 50/51 traces positive; overall median "
        "1.42s saved (44.5%). Source: exact_trace_performance.jsonl.</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def composition_svg() -> str:
    total, model = 5690.7, 2629.2
    other = total - model
    _width, bar_x, bar_w, bar_y = 760, 12, 560, 78
    model_w = bar_w * model / total
    return "\n".join([
        ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 200" '
        'font-family="system-ui, -apple-system, sans-serif" role="img">'),
        "<desc>Live H1 task-time composition: model and network wait dominate.</desc>",
        ('<text x="12" y="22" font-size="15" font-weight="600" fill="#111">'
        "Live task time, summed over the checkpoint (seconds)</text>"),
        ('<text x="12" y="40" font-size="12" fill="#555">exact-trace savings measure '
        "the read backend only — a sliver of task time, not end-to-end speedup</text>"),
        f'<rect x="{bar_x}" y="{bar_y}" width="{model_w:.1f}" height="34" fill="#333"/>',
        (f'<rect x="{bar_x + model_w:.1f}" y="{bar_y}" width="{bar_w - model_w:.1f}" '
        'height="34" fill="#ddd"/>'),
        (f'<text x="{bar_x + 8}" y="{bar_y + 22}" font-size="13" fill="#fff">model/network '
        f"wait {model:,.0f}s (46.2%)</text>"),
        (f'<text x="{bar_x + model_w + 8:.1f}" y="{bar_y + 22}" font-size="13" '
        f'fill="#111">everything else {other:,.0f}s</text>'),
        ('<text x="12" y="150" font-size="12" fill="#555">Total 5,691s across live H1 '
        "runs. Read-trace savings (median 1.4s/trace on 51 replays) sit inside the "
        '"everything else" slice.</text>'),
        ('<text x="12" y="170" font-size="12" fill="#555">Candidate-A era, 12-task '
        "checkpoint rerun — not rc2, not a task-time claim.</text>"),
        "</svg>",
        "",
    ])


def tasks_table(rows: list[dict]) -> str:
    by_task: dict[str, list[dict]] = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)
    lines = [
        '<table class="lineage-table">',
        ("<thead><tr><th>Task</th><th>Family</th><th>Traces</th>"
        "<th>Median saved</th><th>Median reduction</th><th>Positive</th></tr></thead>"),
        "<tbody>",
    ]
    for task in sorted(by_task):
        group = by_task[task]
        med_saved = statistics.median(r["absolute_time_saved_s"] for r in group)
        med_pct = statistics.median(r["reduction_pct"] for r in group)
        pos = sum(1 for r in group if r["absolute_time_saved_s"] > 0)
        family = esc(task.split(":")[0])
        lines.append(
            f"<tr><td><code>{esc(task)}</code></td><td>{family}</td>"
            f"<td>{len(group)}</td><td>{med_saved:.2f} s</td><td>{med_pct:.1f}%</td>"
            f"<td>{pos}/{len(group)}</td></tr>"
        )
    lines.extend(["</tbody>", "</table>"])
    return "\n".join(lines) + "\n"


def main() -> None:
    rows, summary = load()
    verify(rows, summary)
    (SITE / "lineage_traces.svg").write_text(traces_svg(rows))
    (SITE / "lineage_composition.svg").write_text(composition_svg())
    (SITE / "lineage_tasks.html").write_text(tasks_table(rows))
    print(f"lineage visuals OK: {len(rows)} traces, "
          f"{len({r['task_id'] for r in rows})} tasks verified against frozen report")


if __name__ == "__main__":
    main()
