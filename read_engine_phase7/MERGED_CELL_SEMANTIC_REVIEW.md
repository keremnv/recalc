# Phase 7 merged-cell semantic review — before treatment code

Status: offline architecture/semantic review, **not** a product contract. Sources: the exact scripts in `rc_acceleration_validation/workloads/`, frozen classifier `src/librecalc_agent/_frozen/eligibility.py`, frozen Phase-3/6 runtime and Phase-1 `MemoryBook`, and openpyxl 3.1.5 `MergedCell`/`StyleableObject` implementation. No scored Phase-7 timing was run for this review.

## Exact current escape and actual target observations

All three scripts load `input.xlsx` normally and use literal sheet lookup. Every covered-coordinate `.cell()` call currently enters `ProxyWorksheet.cell`, which detects the merge rectangle and calls `_real_sheet().cell(...)`. `_real_sheet()` materializes the entire reference workbook once through `_real_workbook()` and records `proxy_operation_escape`. The escape is triggered by the **covered coordinate**, before the script observes the returned object.

| Frozen workload | Exact source expression(s) | Accesses in source loops | Covered merged-child contacts in reference workbook | Actual later observation |
|---|---|---:|---:|---|
| `Debugging_01_06__7b42a0f86b41` | `[ws.cell(row=r,column=c).value for c in [2,3,4,10,17,24]]`, two loops on `Ex 5 - M&A`, then `Ex 10 - Balance Sheet` | 366 | 6, all on `Ex 10 - Balance Sheet` (`F8`, `D17`, `F17`, `F21`, `D31`, `F31`) | `.value` only; list/print contains scalar |
| `Debugging_05_02__9e6b464d2158` | `[ws.cell(row=r,column=c).value for c in range(2,28)]` on `Model` | 312 | 8 (`F11`–`H11`, `K11`–`N11`, `Q11`) | `.value` only; list/print contains scalar |
| `Financial_Model_08_03__59b98508fd79` | `v = ws.cell(row=r, column=c).value`; if `v is not None`, `(ws.cell(row=r,column=c).coordinate, repr(v)[:110])` | 700 first `.cell()` calls, plus second calls only for non-`None` values | 38 covered children on `DCF Valuation`; each returns `None`, so the second `.coordinate` call is not reached for those cells | `.value` and, for other cells, `.coordinate`; `repr` applies to scalar `v`, **not** a cell object |

The contact counts above are unscored semantic diagnostics against reference openpyxl, not a timing-selected subset. Merge geometry is already present in `SheetInfo.merged` and in the unchanged safe artifact. `MemoryBook.cell` already returns `(None, 'n')` for covered children and the proxy already constructs row/column/coordinate for normal cells. No decoder or format change is needed for these terminal observations.

## What the frozen classifier proves — and does not prove

The classifier is a whole-script **admission** gate for the inherited narrow runtime; it is not a proof of merged-cell object observation. It blocks function definitions, known rich attributes, some object escapes and dynamic operations. It does **not** generally track variables assigned `ws.cell(...)` as cells, and `type(ws.cell(...))`, `repr(ws.cell(...))`, storing a cell in a container, or passing a cell object to an unrelated callable can be admitted. `ProxyCell`'s `__getattr__` can fall back on named rich attributes, but `type`, `isinstance`, identity, hashing and container escape are not caught by that method. Therefore removing the merged-coordinate fallback for every admitted script would be a semantic false positive.

A separate, conservative **observation certificate** is required. The proposed certificate is whole-script and static, using the same source bytes/classifier decision already read at startup. It accepts only if every syntactic `.cell` attribute is invoked immediately and the returned object is immediately consumed by a read of one of `.value`, `.data_type`, `.coordinate`, `.row`, `.column`. Any assignment/return/pass/container insertion/`type`/`repr`/`str`/`bool`/comparison on the **cell object**, `.cell` method alias, unknown receiver, or worksheet cell subscript disqualifies the entire script. Dynamic evaluation or functions remain rejected by frozen admission. The certificate may reject safe scripts; that is an intentional false negative. It does not change `A1_ADMIT` or reference fallback.

For a certified expression, `ws.cell(...).value` produces a Python scalar before any user code can observe the cell's class or identity. Covered children are `(None, 'n')` in Phase-1 state; coordinate/row/column are computed from the literal request. The direct object is never exposed as a value to the program. For an uncertified script, the original merged-child `_real_sheet().cell(...)` branch remains exactly available. Reference fallback for all other proxy operations remains.

## Candidate designs considered

### A. Genuine openpyxl `MergedCell` on a lightweight worksheet

Openpyxl 3.1.5's real `MergedCell` constructor accepts a worksheet-like parent. With a minimal `title`, it reproduces `type`, `isinstance`, `repr`, `str`, coordinate, row, column, `value=None`, and `data_type='n'`. This is attractive but **not sufficient** for unbounded observation. `style_id`, font, fill, border, alignment, protection and number format depend on `parent.parent` and style tables; a dummy parent fails immediately. A proxy parent could lazily materialize the reference workbook, but the synthetic cell's `_style` may still differ from the genuine merged child, especially propagated border/style state. `parent` identity and object escape also become observable. Genuine construction is therefore not the selected general answer. It might be useful in a separately certified expanded contract, but that is outside Phase 7.

### B. Dedicated merged-cell proxy

A proxy can return exact scalar fields and dynamically fall back on named rich attributes. It cannot make `type(proxy) is MergedCell`, `isinstance`, default repr, identity or arbitrary hashing equal to openpyxl. Late fallback could also expose a mixed proxy/real object graph after the object escaped. Not selected as a blanket replacement.

### C. Observation-certified terminal scalar path — selected

Reuse the existing `ProxyCell` and existing merged geometry only for scripts with the whole-script observation certificate. Then the object is an internal temporary in a terminal attribute expression; its class/identity cannot be observed by the admitted source. `.value`/`.data_type` come from `MemoryBook.cell`; `.coordinate`/`.row`/`.column` come from the requested integers. A disqualified script takes the frozen reference branch for covered children. This is per-operation at execution time, with a conservative script-wide proof governing which operations may use it. It needs no artifact, decoder, observer or classifier change.

### D. Always return real merged objects, with style-triggered fallback

This would expand the semantic surface and require careful parent/style identity handling. It offers no necessary benefit on the three actual scripts and risks late mixed-state observations. Deferred.

## Adversarial observation taxonomy and fallback rule

Covered child terminal `.value`, `.data_type`, `.coordinate`, `.row` and `.column` are candidates for `EXACT_DIRECT` **only under the certificate**. For a script that asks `type(cell)`, `isinstance(cell, MergedCell)`, `repr(cell)`, `str(cell)`, `bool(cell)`, equality/identity/hash, `style_id`, font/fill/border/alignment/number format/protection, `parent`/worksheet, arbitrary attributes, repeated object identity, or stores/passes the cell object, the certificate fails and covered `.cell()` returns the real reference `MergedCell` via the frozen branch. These are `REQUIRES_REFERENCE` under the selected design, whether a few individual values could be mimicked. Dynamic or not-provably-cell paths are `UNSUPPORTED/UNPROVEN` for direct serving and likewise retain reference behavior.

Anchor cells and unmerged cells continue through the frozen direct path. Workbook iteration remains frozen reference fallback. No script is re-executed; certification happens before script execution and chooses the merged-child branch. The transition is monotonic: a certified script never exposes a merged-cell proxy object as a user value; an uncertified script materializes reference at first covered child, then uses frozen behavior. An unsupported later operation on an ordinary proxy still follows frozen fallback. This design avoids duplicate user-visible execution and makes false negatives cheap while preserving semantics.

## Answer to the semantic question

The current classifier alone is **not** enough to remove merged-child fallback. A separate conservative observation proof can safely serve the actual three scripts' terminal scalar observations using already-derived merge geometry, without pretending to implement rich `MergedCell` semantics. The adversarial fixture suite must verify both sides: certified terminal reads match reference, and all object/rich observations retain reference parsing. If that proof or fixture gate fails, no scored speed result is valid.
