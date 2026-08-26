# Visualization ISA diagnosis and implementation status

Measured 2026-08-26 against a live LibreOffice UNO listener (`localhost:2021`).
Raw reproducible probe: [`viz-isa-diagnosis.json`](viz-isa-diagnosis.json).
Re-run: `uv run python benchmark/diagnose_viz_isa.py` (needs UNO).

## Task 95 diagnosis

K2.7 wrote a workbook on `Visualization:Task 95`
(`kimi-k2.7-viz-canary-task-95-low-1`, `$0.015`, 10 calls). It correctly selected a
bubble chart, title, labels, point colors, axis titles, and no legend. The failure was an
ISA miss, not a compiler-intelligence miss.

The old ChartSpec could name only three semantic channels:

```text
category_range + series.values_range + series.bubble_size_range
```

Task 95 needs four independent channels:

```text
product label + numeric X (revenue) + numeric Y (growth) + bubble size (market)
```

The handoff initially identified only the unwired size field. Live Chart2 inspection showed
that this was incomplete: using product labels as `category_range` made LibreOffice consume
them as bubble X values. `series.x_values_range` is therefore a required part of the fix.

## Implemented and live-verified

- `ChartSeriesSpec.x_values_range` now exists. Bubble series require explicit X, Y
  (`values_range`), and `bubble_size_range`; `category_range` remains label text.
- UNO binds Chart2 sequences by role (`values-x`, `values-y`, `values-size`) instead of
  relying on `addNewByName` range inference.
- Bubble/scatter product labels are copied from `category_range` into right-positioned
  per-point text labels.
- Requested chart IDs persist through XLSX reload in the drawing shape name. Inspect,
  replacement, and deletion resolve that stable ID even though LibreOffice renames the
  embedded storage object to `Object 1`.
- `calc_inspect_charts` now returns stable id, storage id, reliable Chart2 type, title,
  legend, series role ranges, rendered point colors, point-label text, axes, and compile
  note.
- `x_axis` / `y_axis.number_format` now applies through the chart number-format supplier
  and round-trips through inspect.
- A series name is linked to the header cell immediately above its values range when that
  header matches the requested name. Otherwise the apply log reports literal names as
  unsupported instead of silently dropping them.
- Bar/column creation and inspection follow UNO's `BarDiagram.Vertical` semantics; the
  stacked-column fixture round-trips as `stacked_column`.

Live checks:

```text
LIBRECALC_RUN_UNO=1 uv run pytest tests/test_chart_translation.py -q
4 passed

uv run python benchmark/diagnose_viz_isa.py
static gaps: []
UNO fixtures: bubble, line, stacked-column, honest combo refusal all completed
```

A direct gold-blind Task 95 application produces a 514x300 PNG with the expected revenue
X positions, growth-rate Y positions, proportional bubbles, labels A/B/C/D/E/F/G/X/Y,
largest C green, smallest B red, and no legend. Inspect reads back:

```text
id=portfolio
chart_type=bubble
X=$Strategy.$N$5:$N$13
Y=$Strategy.$O$5:$O$13
size=$Strategy.$P$5:$P$13
category_labels=[A,B,C,D,E,F,G,X,Y]
```

The first corrected-contract K2.7 canary
(`kimi-k2.7-viz-canary-task-95-four-channel-low-1`) cost `$0.022778` and used 11
calls. K2.7 supplied all four ranges and the correct B-red/C-green point indices on its
first write. It exposed one remaining backend-version defect: the official benchmark image
uses LibreOffice 7.0.4, where `DataPointLabel.ShowCustomLabel` does not exist. The initial
fallback persisted only label A. The adapter now uses 7.0's `ShowCategoryName` visibility
flag with the per-point custom text fields. A direct probe inside the official image renders
all nine labels and round-trips `data_labels=true`.

## Honest translation losses

- LibreOffice aborts its XLSX exporter when per-point custom labels retain live
  `CELLRANGE` fields in this runtime. Text custom-label fields save and reload correctly,
  so XY labels are a write-time snapshot. UNO inspect returns `category_labels`; it cannot
  truthfully recover `category_range` after XLSX reload and returns `null` for that field.
- Arbitrary literal series names have no reliable Chart2 setter with an external Calc data
  provider. Matching worksheet headers are linked; unmatched names appear in `dropped`.
- Combo, multi-level category axes, waterfall, gauge, and sunburst remain explicit
  translation loss / refusal. Do not fake an Excel combo with a stacked column.

## Next measurement

Run one final K2.7 Task 95 development canary with the LibreOffice 7.0 visibility fallback,
then score its PNG. Do not use Sol or Opus for this probe, raise the call/token limits, or
start the 15/297 slices.
