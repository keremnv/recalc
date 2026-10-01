# Default harness closure-transfer audit

**Verdict:** `SEMANTIC_MEMBER_CORRECTNESS_DOMINANT`

The limiting failure among correct-formula / wrong-value seeds is semantic construction of upstream edits, not their coordination. There were **zero** transferable execution candidates (T3), so identical agent-authored edits cannot be shown to score better solely by reordering.

Zero model calls. Provider cost **$0**. No Edit Plan. No new agent tool. Gold was not used to build `D(seed)` or choose replay edits. Architecture was not changed.

---

## Frozen contract

- Closure rule: input-side, OFFSET-aware ancestors of the *agent's* proposed formula's direct precedents
- Keep set (Edit-Plan-free analogue of required edits): blank-on-input ∪ `AUTHORED_CELL_SET`
- Authority invariant: `execution_unit(seed) = D(seed) ∩ AUTHORED_CELL_SET`; never add missing members
- Primary population: completed C0 default-harness GLM fill trajectories
- Expansion trigger: fewer than 5 `FORMULA_CORRECT_VALUE_WRONG` seeds
- R0/R1: identical authored content; T3 only. T3 was empty, so no causal replay ran.

---

## Population

Primary complete: **9 / 9** listed C0 tasks. Expansion **not used** (14 FCVW seeds ≥ 5).

| Task | Complete | Authored cells | Notes |
| --- | --- | --- | --- |
| `Financial_Model:08_03` | yes | 302 | C69 + J44:N44 reconstructed from `process.py` |
| `Financial_Model:08_04` | yes | 254 | 5 FCVW seeds |
| `Financial_Model:08_05` | yes | 385 | no FCVW |
| `Financial_Model:15_04` | yes | 1104 | no FCVW |
| `Financial_Model:08_02` | yes (workbook exists) | 0 | reconstruction failed: zip archive missing `xl/worksheets/sheet1.xml` |
| `Financial_Model:08_01` | yes | 772 | no FCVW |
| `Template:06_09` | yes | 65 | no FCVW |
| `Template:06_16` | yes | 48 | 9 FCVW seeds |
| `Debugging:10_04` | yes | 0 | color/XML edits; no formula mutations reconstructed |

`Debugging:10_02` excluded (no workbook). Visualization excluded. C1 excluded (prompt changed).

---

## Primary aggregates

- Total authored formula edits: **2651**
- Formula-correct edits: **1425**
- Formula-correct / value-wrong seeds: **14**

Among those 14:

| Class | Count | Tasks |
| --- | --- | --- |
| `T0_CLOSURE_EMPTY` | 0 | — |
| `T1_AUTHORITY_GAP` | 5 | `Financial_Model:08_04` DCF G20:K20 |
| `T2_AUTHORED_MEMBER_SEMANTIC_FAILURE` | 9 | `Template:06_16` QuarterlyPL_Forecast |
| `T3_TRANSFERABLE_EXECUTION_CANDIDATE` | 0 | — |

Faithful R0/R1 pairs: **0**. R1 gains/ties/losses: **0 / 0 / 0**.

---

## Answers

1. **Does the loose default harness produce correct-formula / wrong-value failures?** Yes, 14 seeds (5 on `08_04`, 9 on `06_16`). Most authored formulas that match gold also match gold values (1411 `FORMULA_CORRECT_VALUE_CORRECT`).
2. **Does proposal-seeded closure recover relevant dependencies?** It always returned a nonempty `D(seed)` for FCVW seeds. On `06_16` the recovered members are the immediate upstream rows the seed formula names. On `08_04` blank-keep over-generates a large ancestor set (146–191 cells).
3. **Were those dependencies already authored?** On `06_16`, yes (T2). On `08_04`, many blank ancestors were never authored (T1). After freeze, **none of those T1 missing members are official modification targets** (`missing_are_gold_targets = []`). That T1 is keep-set overbreadth, not a gold-required authority gap.
4. **Were the authored dependency edits semantically correct?** On `06_16`, no: every FCVW seed's closure members include wrong upstream formulas (e.g. `J16 = J12+J14` is gold-identical, but `J12`/`J14` are not). On `08_03`, `J44:N44` are authored and **value-correct** but fail official formula-text identity because operand order differs (`=J6+J15+J26+J35` vs gold `=+J35+J26+J15+J6`).
5. **Can identical semantic edits score better solely through deterministic coordination?** Not testable: T3 is empty. No R0/R1 pair exists.
6. **Did the old closure benefit transfer, or was it Edit-Plan-dependent?** The old C1 keep set was Edit Plan authority. Without it, blank-keep either over-generates (T1 noise) or, when members are already authored, the failure is semantic (T2). The historical `C69 → J44:N44` composition miss **does not reproduce** as a wrong-value seed.
7. **Enough evidence to justify a live coordination runtime?** **No.**

---

## Financial_Model:08_03 autopsy

Historical claim: `Income Statement!C69 = C68/C$6` required `Working Capital!J44:N44` for correct workbook behavior.

| Question | Result |
| --- | --- |
| Did C0 author `C69`? | **yes** `=C68/C$6` |
| Was that formula evaluator-correct? | **yes** (exact gold match) |
| Were `J44:N44` all authored? | **yes** via ordinary Python |
| Were those five formulas semantically correct? | **value-correct**; formula-text differs by commutative operand order |
| Was the final C69 value correct after LibreOffice? | **yes** |
| Does coordinated replay improve it? | not applicable; no T3 |
| Historical class | **`NO_HEADROOM_IN_DEFAULT_CONTROL`** |

The old composition failure does not survive in this default C0 run. Remaining official miss is `Ratio Analysis!C19`, outside this witness.

Diagnostic (not a FCVW seed): unrestricted blank-keep around C69 yields `|D|=356` with 40 authored members including `J44:N44`. Missing members include blank assumption/capex cells and `Working Capital!C44:I44`, which old Edit Plan authorised but gold does not edit. This shows Edit Plan was load-bearing for making `D(seed)` a *small required-edit* set.

---

## T1 and T2 diagnosis (no repair)

**T1 (`08_04` DCF `G20:K20`).** Seed formulas `=+G17*G19` etc. match gold after the official `=+` strip. Final values are wrong. Closure has 146–191 members; 34–40 authored; missing members are blank ancestors, **none of them official modification targets**. Do not invent edits for them.

**T2 (`06_16`).** Compact, earned-rule-like closures (2–3 members), all authored, at least one member formula/value wrong. Example: `QuarterlyPL_Forecast!J16 = J12+J14` (gold-identical) with wrong `J12`/`J14`. Dependency order cannot fix wrong semantic programs. No hypothetical repair.

---

## Integrity notes

- Reconstruction confidence for captured mutations: `RECONSTRUCTED_FROM_SCRIPT` (sequential workbook diffs after replaying trajectory Python/zip writers).
- `08_02`: stored workbook exists and was officially scored; trajectory replay could not snapshot the agent's zip-patched archive (`sheet1.xml` missing). That task contributes no seeds.
- `10_04`: complete trajectory and workbook; mutations are style/XML, not formula edits.
- `cell_provenance.jsonl` is empty because no T3 replay deltas exist.

---

## Decision

Do **not** build the live default-harness coordination runtime.

```text
AUTHORITY_GAP_DOMINANT
SEMANTIC_MEMBER_CORRECTNESS_DOMINANT
NO_COMPOSITION_DEPENDENT_FAILURE_IN_CONTROL
```

all say the same next step here: there is no earned T3 coordination gap. This experiment's dominant class is semantic upstream construction (`06_16`). The old `08_03` composition miss is `NO_HEADROOM_IN_DEFAULT_CONTROL`.

---

## Cost

Provider/API inference: **$0**. Compute runtime: **1219 s** (`closure_transfer_audit/verdict.json`).
