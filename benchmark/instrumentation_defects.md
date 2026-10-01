# Instrumentation defect ledger

Every entry is the same failure family: **a control fails silently and the
result is then read as a model-quality failure.** Each is recorded before it is
fixed, so the data collected under the defective control stays interpretable.

| # | defect | found | status |
|---|---|---|---|
| 1 | plan validator rejected identifier kinds the grounding contract exposes | edit-plan probe | fixed |
| 2 | synthesis reused the retrieval system prompt | edit-plan probe | fixed |
| 3 | writer was not neutral: an openpyxl round trip changed untouched cells | edit-plan probe | fixed (archive-level `write_cells`) |
| 4 | size guards were inert | edit-plan probe | fixed |
| 5 | synthesis shared the retrieval output budget and truncated to empty | replay | fixed (`SYNTHESIS_MAX_TOKENS`, `TRUNCATED_NO_CONTENT`) |
| 6 | parser rejected a valid object emitted more than once | replay | fixed (`_single_repeated_object`) |
| 7 | metric-population mismatch: E/F/S reported interchangeably | Phase A | fixed (populations always named) |
| 8 | **scorer error-value fallback**: a cell holding an Excel error is compared by *formula text* instead of value, so breaking a cell scores better than leaving it blank | Phase B | recorded; reported as a value-only diagnostic beside every official number. The official scorer is never modified. |
| 9 | **budget exhaustion with non-empty content**: a response that spends its entire output budget on reasoning and never emits the JSON is labelled `UNPARSEABLE`, because the truncation detector requires an *empty* body | Phase B | recorded; fix below |

## Defect 8 — measured

On the 07_03 isolated variant: official modification accuracy 0.750, value-only
modification accuracy 0.000. All 861 "correct" modification cells were correct
only because they held `#VALUE!` and were then compared by unchanged formula
text. Official regression 1.000, value-only regression 0.947: 1,952 regression
cells were damaged invisibly.

This retro-explains two earlier results:

* 07_03's post-hoc parse gain of 0.0 -> 0.75 was **not** a real gain. The
  recovered proposal `=Inputs!C11` is wrong (gold is `=Inputs!D10`); it resolves
  to a text label, propagates `#VALUE!`, and the fallback credits 861 cells.
  The parser repair itself remains correct; the score it appeared to produce
  does not.
* Phase A's "adding correct gold edits reduces 07_03 from 0.751 to 0.582" is the
  same mechanism seen from the other side: correct edits replace error values
  with real values, which are then compared by value and can fail, while the
  broken workbook was passing on formula text.

## Defect 9 — measured and fixed

One of 28 Phase B synthesis responses (`08_05` `Balance Sheet!P16`) returned
`completion_tokens == SYNTHESIS_MAX_TOKENS` with 21,754 characters of
deliberation and no JSON object. The detector only fired on an empty body, so
this was recorded as a parse failure rather than as budget exhaustion.

The fix widens the condition: a response that ends exactly at the output budget
without a parseable object is `TRUNCATED_AT_BUDGET`, whether or not it emitted
prose. It is a non-model failure class and never counts as a wrong answer.

The fix is applied *after* this run. The Phase B data above was collected under
the old detector, and the report labels that one session accordingly.
