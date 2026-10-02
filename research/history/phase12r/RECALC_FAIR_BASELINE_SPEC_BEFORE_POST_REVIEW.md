# Minimal recalc-fair evaluation protocol (research specification)

This specification does not integrate anything into product runtime or production
benchmark code. Final adoption scope follows the completed replay report.

Candidate workbook → immutable copy into isolated evaluation workspace → headless
LibreOffice load → force calculation → separately saved/hash-identified XLSX →
unchanged official scorer. Preserve the original, historical scores and evaluator
version identity separately from the derived recalc-fair result. No formula repair,
model involvement, permissive metadata repair, or diagnostic intervention.

Record workbook/input/golden/dataset/scorer hashes, Python/openpyxl/OS/LO version,
locale/timezone, complete LO command/profile and macro/link/calculation settings.
Keep ORIGINAL_SCORE, current V0 score and RECALC_SCORE separate; version drift is
an explicit qualification. A normalized comparison is never a rewritten historical
score. Formula identity and package/cache changes are available for audit; success
at loading/exporting does not establish unchanged workbook semantics.

Use a fresh profile, unique UNO connection, macros disabled, link updates disabled,
calculation forced by calculateAll(), and explicit load/export completion. Candidate
and reference-scoring semantics must use a compatible declared engine. Do not
recalculate references opportunistically inside a candidate comparison: freeze and
version references separately. Error caches can invoke the local scorer's formula
fallback, so an official score recovery is not an automatic claim of numerical
correctness. Preserve the official scorer boundary in this phase.

Failure policy:

| Condition | Result | Score handling |
|---|---|---|
| Successful load/calculate/export and validated output | RECALC_PASS | Score derived workbook; retain original separately |
| Crash, timeout, malformed workbook, failed export | RECALC_FAILED | Explicit unscorable recalc result; no silent original fallback |
| Encryption/password, macros/UDF, external connections/links | RECALC_UNSUPPORTED | Explicit unsupported state; do not imply refresh succeeded |
| Volatile functions | RECALC_UNSUPPORTED in this replay | No deterministic semantic baseline unless a separately versioned policy is defined |
| Iterative calculations | Attempt with stored settings | Gains remain ambiguous in this phase; no strong cache-only promotion |
| Formula rewrites/unsupported semantics/semantic metadata changes | Record diff and score if readable | Recalc-associated effect only, never cache-only |
| Scorer exception/zero assessed cells/resource failure | UNSCORABLE | Preserve error/counts; avoid interpreting ordinary-looking zero as a semantic failure |

Operational policy: one fresh workbook subprocess at a time under the measured
resource envelope; exact identity caches may reuse deterministic completed work.
Record reuse and timing separately. An execution resource failure is visible even
if the official scorer catches it and emits zeros. Recalc treatment times are
measured independently of scoring and diagnostic-count validation.

AGENT TOOLING POLICY and EVALUATOR FAIRNESS POLICY are distinct. Evaluator refresh
makes score depend less on whether an agent happened to materialize caches. Submit
refresh can improve the usable deliverable and allow readback before submission.
Once evaluation refreshes reliably, this experiment does not identify incremental
score benefit from also refreshing at submission. Do not require formula-writing
agents to repair formulas merely because original cached values are absent.

## Adoption policy from replay

Retain/enforce deterministic recalc before evaluation for supported formula-containing candidates, including ordinary Python research harnesses that currently bypass the archived submission pipeline. The retained ordinary archive pipeline already has this stage; no broad retroactive ordinary rebaseline is established. Apply one declared evaluator boundary to all arms, irrespective of score or task category. This is EVALUATOR FAIRNESS POLICY, justified by same-formula, cache-sufficient official recoveries in the newer corpus. It is not a diagnostic success or a formula-repair mechanism.

AGENT TOOLING POLICY recommendation: **ADD RECALC BEFORE EVALUATION ONLY**. Evaluation-only refresh produced the demonstrated gains; incremental benefit of refreshing additionally before submission was not identified. A user-facing deliverable/readback requirement may separately motivate submission refresh, but this replay does not establish that additional score intervention. Keep that rationale separate. The existing ordinary archive pipeline need not change its successful behavior.

For any future implementation set UNO MacroExecutionMode=0 (NEVER_EXECUTE), not4; UpdateDocMode=0 (NO_UPDATE). The primary helper actually used4; preserve that deviation and its bounded mode comparison. Configure calculation settings/locale/timezone and pin engine identities. Unsupported workbooks require a versioned explicit policy rather than a hidden fallback. Formula rewrites cannot be claimed to prove cache-only changes.

Freeze input/golden reference bytes and evaluator together; confirm the intended value-versus-formula/color modes. Do not fill benchmark-expected blank cells in the reference. Two reviewed harms came from existing candidate formulas in genuinely blank golden cells; their newly visible values correctly lost regression agreement. Error fallback matching formula text must remain disclosed. Raw missing-cache scores must not be called a fair numeric semantics test merely because their empty values agree with blank reference cells. Operationally successful recalculation is not guaranteed score improvement.

Only separately versioned reference validation can establish engine/reference compatibility. This phase keeps original reference caches and scorer rules unchanged. It does not introduce opportunistic reference repair or change official benchmark semantics.
