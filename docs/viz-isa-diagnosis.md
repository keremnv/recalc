# Visualization ISA diagnosis (handover)

**Audience:** GPT-5.6 Sol Codex implementing chart-world fixes.
**Do not** treat this as permission to raise call limits, mint restore tools, or expand
absence detectors. Visualization only.

Measured 2026-08-26 against a live LibreOffice UNO listener (`localhost:2021`).
Raw probe log: [`viz-isa-diagnosis.json`](viz-isa-diagnosis.json).
Re-run: `uv run python benchmark/diagnose_viz_isa.py` (needs UNO).

K2.7 canary on `Visualization:Task 95` is the intelligence-vs-ISA check
(`kimi-k2.7-viz-canary-task-95-low-1`). If the model never upserts, that is a
compiler miss. If it upserts and the chart is still wrong, use the gaps below.

## Already working (do not re-litigate)

Unit tests: 19 passed (2 UNO skipped without listener). With listener:
`test_uno_chart_axis_titles_data_labels_and_point_colors` **passed**.

Live apply_log on fixtures:

| feature | result |
|---|---|
| Size floor / Excel spans (`width=16,height=9` → HMM) | domain tests pass; PNG exports 13–18 KB, not postage stamps |
| Axis titles via `HasX/YAxisTitle` + title shape | applied on stacked + line Y |
| Y min/max | applied |
| Label rotation | applied (`xaxis.label_rotation`) |
| Series / point colors | applied (bubble fixture 4 points) |
| `data_labels` caption + Chart2 category names | applied |
| Stacked column `diagram.Stacked` | applied |
| Combo / pareto / waterfall / gauge / sunburst | honest `compile_note` (`approximated` / `scaffold` / `unsupported`); combo upsert `ok: false` |

LO-vs-Excel combo and multi-level category axes stay **translation loss**, not missing
ops. Do not fake Excel combo with a stacked column.

## Blocking ISA gaps (implement these)

### 1. `series.bubble_size_range` is domain-only

`ChartSeriesSpec.bubble_size_range` exists. `uno_charts.py` never reads it.
`addNewByName` gets `category_range` + `values_range` only.

**Task 95** needs X=revenue, Y=growth, size=market. Size cannot be expressed.
Wire the third range into the UNO data ranges (and inspect it back).

### 2. `x_axis.number_format` is domain-only

`ChartAxisSpec.number_format` is accepted. `_apply_axis` never sets a number format.
**Task 1411527** wants `dd/mm/yyyy` on dates. Rotation already lands; format does not.

### 3. UNO inspect is too thin (and lies in the tool docstring)

`calc_inspect_charts` docs promise `category_range`, series ranges, `compile_note`.
`inspect_charts_from_document` returns only:

```text
id, sheet, title, chart_type, has_legend
```

Live inspect after a successful upsert:

- `id` is `"Object 1"`, not the requested `Portfolio` / `Burndown` / `Sales`
- `chart_type` is `"unknown"` even for bubble/line/stacked (implementation-name
  matching is wrong or the diagram is Chart2-only)

Agents cannot verify what they wrote. Expand inspect to round-trip ChartSpec
fields that apply_log marked applied, and keep requested `id`.

### 4. Series names drop with `AttributeError`

Every fixture: `series[N].name (AttributeError)` in `dropped`. Legend still
shows `has_legend: true` on line/stacked. Fix name apply or report it as
unsupported honestly.

## Non-goals for this handover

- Do not implement combo as a real dual-axis chart unless UNO can do it and
  inspect round-trips it. The world already refuses combo.
- Do not change the cheap compiler (K2.7) or start a 297-task run.
- Do not raise `--call-limit` / `--max-tokens`.
- Memory backend already round-trips full `ChartSpec`; UNO is the gap.

## Suggested implementation order

1. Inspect payload + requested id (otherwise agents and tests fly blind).
2. `bubble_size_range` (unblocks Task 95).
3. Axis `number_format` (unblocks Task 1411527).
4. Series name apply.
5. Re-run `LIBRECALC_RUN_UNO=1 uv run pytest tests/test_chart_translation.py`
   and `uv run python benchmark/diagnose_viz_isa.py`.
6. Then a K2.7 Task 95 canary, not Sol, until writes+inspect look right.
