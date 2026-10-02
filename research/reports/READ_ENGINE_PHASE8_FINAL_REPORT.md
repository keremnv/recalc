# Read Engine Phase 8A — semantic repair and resumed Phase-8 validation

Status: **completed offline validation; no public product change**. The original [Phase-8 stop report](READ_ENGINE_PHASE8_REPORT.md) remains intact. This report concerns the experimental Phase-6 observer with the Phase-7 read route and a hardened Phase-8A merged-cell certificate. It does not establish public-RC speed or broad openpyxl equivalence.

Evidence: [dispatch graph](../../read_engine_phase8a/DISPATCH_GRAPH.md), [hardening review](../../read_engine_phase8a/CERTIFICATE_HARDENING_REVIEW.md), [adversarial matrix](../../read_engine_phase8a/certificate_matrix.jsonl), [fixed-22 regression](../../read_engine_phase8a/fixed22_correctness.jsonl), [base validation spec](../../read_engine_phase8/PREREGISTERED_VALIDATION_SPEC.md), [Amendment 1](../../read_engine_phase8/PREREGISTERED_VALIDATION_SPEC_AMENDMENT_1.md), [Amendment 2](../../read_engine_phase8/PREREGISTERED_VALIDATION_SPEC_AMENDMENT_2.md), [raw representative timings](../private-data-manifest.json), [representative correctness](../../read_engine_phase8/representative_correctness.jsonl), [session timings](../../read_engine_phase8/session_timings.jsonl), [changed-file timings](../../read_engine_phase8/changed_file_timings.jsonl), [changed-file correctness](../../read_engine_phase8/changed_file_correctness.jsonl), [analysis](../../read_engine_phase8/analysis.json), and [profile](../../read_engine_phase8/profile.json). Ratios pair the same script/workbook and scored repetition; each workload contributes its median of three repetitions. Intervals are the preregistered 2,000 workload-resample bootstrap draws. The 30 scripts come from 21 tasks, so the intervals are descriptive for this frozen view, not a claim about a market population.

## ORIGINAL PHASE 8 STOP

Phase 8 stopped **before scored validation** because an admitted program obtained a covered merged cell through `ws.__getattribute__("cell")(1, 2)`. The Phase-7 certificate reported `certified=true` with zero recognized `.cell` AST calls. Reference openpyxl exposed a real `MergedCell`; treatment exposed `ProxyCell`, changing `type` and `repr`. `ws.__getitem__("B1")` was a second route. The original stopped report and analysis were preserved; their stopped status was not rewritten as a negative timing result. Phase-7's warm `0.513` and session results remain valid for its exact 22 tested programs, not for arbitrary admitted Python.

## ROOT CAUSE OF CERTIFICATE FALSE POSITIVE

The old certificate checked how **recognized literal** `.cell(...)` expressions were consumed. It did not prove that all runtime routes to the patched method had been found. Indirect bound-method acquisition and worksheet subscription reached the same runtime dispatch with no literal `.cell` syntax. Its zero-call success path turned absence of recognized syntax into an unsound safety claim.

## ACTUAL CELL DISPATCH GRAPH

The guarded bootstrap installs `Runtime.load` at ordinary `openpyxl.load_workbook`. An admitted direct load returns `ProxyWorkbook`; literal sheet lookup returns `ProxyWorksheet`. Its `.cell` reaches the merged-child decision. Its `__getitem__` also calls `.cell`. Python can obtain `.cell` through direct attribute syntax, `getattr`, `__getattribute__`, method aliases, helpers and dynamic execution where admission permits them. Worksheet aliases, nested access, closures and containers can move the resulting object beyond its original expression. [The graph](../../read_engine_phase8a/DISPATCH_GRAPH.md) separates two required proofs: **reachability of every cell-producing route** and **terminal scalar observation of every resulting object**. The frozen whole-script admission classifier proves neither by itself.

## HARDENED PROOF MODEL

The new experimental [certificate](../../read_engine_phase8a/certificate.py) uses a deliberately restricted, closed whole-module grammar. It positively recognizes ordinary `import openpyxl`, a direct literal `load_workbook`, a literal sheet binding, direct `ws.cell(...).value/.data_type/.coordinate/.row/.column`, and a small set of scalar loops, conditionals, comprehensions, printing and list appends. Every unrecognized AST statement, expression, receiver, binder, attribute, call or import returns `NOT_CERTIFIED`. The implementation has no default accept visitor. Certification requires frozen `A1_ADMIT` first and at least one proved terminal `.cell` call. No source rewriting, proxy change, admission broadening, artifact change or fallback change was made. This is a proof for the **restricted positive grammar under the tested runner**, not a proof of arbitrary Python/openpyxl equivalence.

The alternatives were assessed before implementation: a broader whole-script data-flow analysis has a much larger proof surface; per-expression proof needs trustworthy runtime call-site attribution without rewriting; a dynamic proxy cannot retroactively become a real `MergedCell` when `type`, identity or `repr` observes it. The selected design accepts false negatives. Admitted but uncertified scripts retain the existing reference merged-child route.

## ZERO CALL CERTIFICATION RULE

Zero positively proved `.cell` calls always returns `NOT_CERTIFIED`, including scripts that reach `.cell` through `__getattribute__` or `__getitem__`, and scripts that do not contact cells at all. This closes the specific unsound inference in Phase 7.

## INDIRECT ACCESS AND DUNDER ROUTES

`getattr`, `__getattribute__`, `__getitem__`, bound-method aliases, helper calls, worksheet aliases, dynamic attribute names, `eval`/`exec`, rebinding and unknown dunder paths are outside the positive grammar. Literal `ws["B1"]` is also rejected rather than presumed equivalent to direct `.cell(...).value`. The certificate does not patch two strings; it rejects any unproved call or attribute dispatch in the whole script. The runtime still uses reference fallback for covered merged children in those cases.

## ADVERSARIAL CERTIFICATE RESULTS

The original 37 Phase-7 fixtures and 32 new deterministic fixtures gave **69/69 expected routing outcomes**, including **zero false-positive merged direct routes**. Thirteen source fixtures were certified; eleven actually contacted the merged direct route, while anchor/unmerged cases had no covered-child contact. Sixty-seven fixtures were exact against reference. Two preserved `cell.parent is ws` identity falsifiers were H0/H1-equal but differed from PY and were **not** counted as direct successes. The [15 deterministic mutations](../../read_engine_phase8a/certificate_review/mutations.jsonl) of safe expressions all produced the expected conservative rejection. Finite tests support the inspected closed grammar; they are not formal proof of all Python environments.

## KNOWN PROXY IDENTITY LIMITS

Reference fallback can return a real cell whose `.parent` is the real worksheet while the script still holds a proxy worksheet; `cell.parent is ws` can therefore differ from reference execution. Ordinary direct `ProxyCell` also differs in `type`, `repr` and identity if exposed. Hardening prevents the **merged-child certificate** from admitting unproved observations; it does not repair these inherited proxy limits. Rich styles, arbitrary object escape, workbook iteration and concurrent source mutation after load remain outside the narrow direct contract or subject to reference/identity limitations. They must be explicit in product integration; no broad equivalence claim follows from this run.

## FIXED 22 REGRESSION

The unchanged Phase-7 contact-selected 22 scripts passed **44/44 unscored cold/reused correctness rows** against PY, including exit, normalized output and package state. `BUILT → REUSED`, direct contact and fallback reasons were retained; no new direct routes appeared. The three original merged target scripts remained positively certified, with covered merged direct counts **6**, **8** and **38** in each regime. Their Phase-7 speed result was not rerun or reinterpreted.

## PHASE 8 VALIDATION AMENDMENT

The frozen base spec SHA-256 is `20a149e390f102d26ef259082b34948d0d9eb5b4f2029e6ae5bbf268f2c1cd11`. [Amendment 1](../../read_engine_phase8/PREREGISTERED_VALIDATION_SPEC_AMENDMENT_1.md), SHA-256 `8616338db08aa404c186f4ad33b359f5195919eccfa70d777754b79fa249789b`, pinned the certificate repair after the semantic gates and before scored timing. Its first **unscored** validation passed 30/30 representative scripts but stopped at a changed-file output comparison: reference openpyxl had stamped `docProps/core.xml` one second later in one arm. All other package parts and effects matched. That attempt is preserved under [gate_attempt_1](../../read_engine_phase8a/gate_attempt_1); it produced no scored rows.

[Amendment 2](../../read_engine_phase8/PREREGISTERED_VALIDATION_SPEC_AMENDMENT_2.md), SHA-256 `7a19a9008e49243e74b6c923265e7c8374d2ebb5fca5ba7e1e5c4e5ceac94a98`, was hashed **before scoring**. It allows a changed-file `docProps/core.xml` difference only when replacing exactly one strict UTC `dcterms:modified` timestamp makes the entire XML byte-identical. Every other part, effect, output and receipt remains exact. It changed only the comparison runner, not treatment behavior, population or timers. The full gate was restarted with empty private caches. All three spec checksum files were verified after scoring.

## REPRESENTATIVE POPULATION

The same [frozen 30 scripts](../../read_engine_phase8/PREREGISTERED_VALIDATION_SPEC.md) from 21 tasks retained their archived script and workbook SHA-256 identities. Neither scripts nor eligibility were selected after timing. H1 classified **7 `DIRECT_CONTACT`**, **1 `FALLBACK_AFTER_CONTACT`**, **22 `REFERENCE_ONLY`**, and zero other. H0 and H1 classes and fallback reasons agreed. Across 450 scored representative pair sets, each arm made 150 commands: all 24 contact-session first commands built an artifact, and all 96 subsequent contact commands recorded `REUSED`; reference-only commands had no artifact status. The fixed five write fixtures are a separate assurance population, not a substitute for these 30.

## REPRESENTATIVE CORRECTNESS

The restarted unscored gate passed 30/30 cold and second commands. Scoring completed **1,350 command rows** (30 scripts × 3 repetitions × 5 invocations × 3 arms), **360 observed session rows**, and **450/450 valid scored pair sets**. Together with the gate, **510/510** correctness rows passed. Of these, 68 rows across four unchanged scripts had only the previously allowed volatile-output difference; the other 442 were exact by the frozen comparator. No stale artifact, missing reuse witness, capture failure, changed contact class or new merged-cell discrepancy appeared.

## REFERENCE ONLY ECONOMICS

The 22 reference-only scripts received no direct-read saving. On their **second invocation** (not `VALID_REUSE`), H1/PY median paired ratio was **1.089**, geometric mean **1.086**, workload-bootstrap 95% median interval **[1.075, 1.118]**, and median signed excess **+22.0 ms**; **3 faster, 19 slower**. Cold median was **1.088** with **+20.5 ms** excess and 4/18 faster/slower. This meets the preregistered descriptive standard for **measurable overhead**: median and lower interval exceed one, and signed excess is positive. It does not define a business acceptability threshold. The current broadly enabled runtime adds cost when it has nothing to accelerate.

## DIRECT CONTACT ECONOMICS

For the seven representative direct-contact scripts, actual second-command `REUSED` H1/PY median ratio was **0.622**, geometric mean **0.576**, interval **[0.352, 1.079]**, median signed difference **−113.5 ms**, and **5 faster, 2 slower**. This diagnostic subset is heterogeneous and only six tasks; its interval crosses one. Cold direct-contact median was **1.145** (3 faster, 4 slower). N=2/3/5 observed session medians were **0.894/0.723/0.686**, each with an upper bootstrap bound above one. The five financial-model winners show that direct serving can pay; the two Template direct-contact scripts remained slower on their second command. These subset results cannot replace the all-30 product-boundary result.

## FALLBACK ECONOMICS

The one `FALLBACK_AFTER_CONTACT` script, `Template_06_23__fc41ad37c48b`, retained one `proxy_operation_escape` reference parse per scored invocation, in both H0 and H1. Its H1/PY cold and second-command ratios were **1.191** and **1.110**; its N=5 session ratio was **1.142**. This is one workload, so no population inference or meaningful bootstrap interval applies. The fallback was not optimized in Phase 8A.

## REPRESENTATIVE COLD RESULT

For **all 30**, H1/PY first-command median paired ratio was **1.091**, geometric mean **1.093**, interval **[1.063, 1.123]**, median signed excess **+21.2 ms**, with **7 faster, 23 slower**. Equal-task median was **1.102** across 21 tasks. H0/PY cold median was **1.091**. The first-use boundary remains negative on this frozen representative view; the favorable Phase-7 fixed-22 warm result says nothing contrary about it.

## REPRESENTATIVE VALID REUSE OR SECOND INVOCATION RESULT

For **all 30**, the second-command H1/PY median ratio was **1.083**, geometric mean **0.937**, interval **[1.056, 1.111]**, median signed excess **+20.4 ms**, with **8 faster, 22 slower**. The geometric mean below one reflects large gains on some contact scripts; the median, count and task-cluster median (**1.082**) show the typical frozen script remained slower. H0/PY second-command median was **1.072**. Only the eight actual contact scripts had child-confirmed `VALID_REUSE`; the other 22 are correctly labeled `SECOND_INVOCATION`. There is no representative all-30 warm-speed claim.

## REPRESENTATIVE SESSION RESULT

Observed all-30 H1/PY session medians were **N=1: 1.091**, **N=2: 1.084**, **N=3: 1.073**, **N=5: 1.076**. Their respective bootstrap upper bounds were **1.123/1.119/1.112/1.106**; faster counts were **7/8/8/6** of 30. Session economics thus remain negative for the frozen full representative view through N=5, even though direct-contact sessions show useful diagnostic gains. Each session charged every fresh command and began without an artifact; no algebraic extrapolation is used.

## CHANGED FILE EFFECT CAPTURE

All five frozen write fixtures passed the unscored and three scored correctness gates: **20/20 valid pair sets**, one expected changed XLSX path per observer command, successful capture helper, part-exact derivation, state-exact replay and validation. Nine rows required only the amended core-property modified-time normalization. The raw Phase-3 comparator can label these byte differences `GENUINE_SEMANTIC_DIFFERENCE`; the stricter part-by-part comparison proved that only the single allowed timestamp differed. No other package-part mismatch was accepted.

| Fixed write fixture | PY median ms | H1 median ms | Paired H1/PY | Median excess ms | H1 helper envelope ms | H1 capture work ms |
|---|---:|---:|---:|---:|---:|---:|
| Existing-cell value | 175.2 | 266.4 | 1.558 | +95.5 | 76.6 | 9.4 |
| Formula | 170.9 | 270.8 | 1.584 | +99.8 | 79.3 | 9.1 |
| 20-cell write | 167.3 | 279.6 | 1.671 | +112.2 | 84.3 | 10.5 |
| New sheet | 167.5 | 262.2 | 1.550 | +92.2 | 75.8 | 9.7 |
| Output workbook | 172.0 | 267.5 | 1.531 | +91.3 | 76.2 | 8.6 |

The observer's pre-snapshot median was about **0.05 ms** and post comparison about **0.13–0.26 ms** on this 7.8 KiB source; the target wait was about **184–192 ms**. The capture helper envelope was **76–84 ms**, while measured package snapshot/derive/commit/validate/replay inside it totaled **9–11 ms**. The remaining envelope includes helper process startup/import, staging and teardown; it is **not** a separately measured pure startup timer. These nested medians are not additive. This is assurance overhead, **not write acceleration**, and larger changed workbooks remain unmeasured.

## ABRUPT EXIT WITH CHANGED WORKBOOK

Both predeclared diagnostic fixtures passed: mutation followed by `os._exit(7)` and mutation followed by SIGTERM. The external observer survived, recorded one changed XLSX, ran the helper successfully, and wrote a receipt with the target exit code or signal. These two diagnostics test the survivor property for completed saves; they do not prove behavior under observer death, disk-full, concurrent mutation or every fatal signal.

## MERGED CELL CERTIFICATE VERDICT

**The Phase-8 false-positive proof boundary is closed for the restricted positive grammar used here.** The original indirect and dunder routes now fail certification; zero calls fail certification; 69 adversarial fixtures, 15 mutations and the exact 22 regression had zero false-positive direct routes. All three original merged target scripts remain certified without script-identity exceptions. This is not an endorsement of static certification for arbitrary admitted Python: outside the narrow grammar the route is reference, and the inherited proxy identity limitation remains.

## INTEGRATION READINESS VERDICT

**B. `READY AFTER ONE BLOCKING EXPERIMENT` — a reference-only low-overhead path that preserves the external observer and changed-file assurance.** The specific Phase-8A semantic blocker is repaired, representative and changed-file correctness passed, and the architecture can be reengineered rather than copied. Yet 22/30 representative scripts receive no direct serving and incur a measured ~22 ms second-command tax; all-30 cold, second-command and N≤5 session medians are slower. Before enabling the runtime broadly in product code, test whether reference-only execution can approach direct Python **without** dropping post-termination observation, fallback, or the five changed-file effects. The changed-file helper's additional 76–84 ms envelope is measured and must be treated as an explicit assurance cost; no write-speed claim is warranted. Production engineering still needs proxy identity policy, observer failure/durability semantics, resource bounds, cache permissions/concurrency and platform packaging. This verdict authorizes a next experiment, not public integration or claims.

## AGENT INDEPENDENT PRODUCT ARCHITECTURE OPINION

Hardening changed my view of the certificate: a small **allowlisted grammar with default reference routing** can be maintained as an experimental optimization, but a generic whole-script proof for ordinary Python would be the wrong product promise. I would retain the merged-cell route only in this restricted form and treat its false negatives as acceptable; the representative run did not establish incremental economic value for that route outside the original three scripts. If responsible for shipping, I would keep one real script interpreter plus an external survivor, implement a cheap no-contact route first, and reengineer rather than copy the prototype observer/capture and certificate. The highest-risk standing assumption is that a production admission/proxy boundary can remain exact when ordinary Python exposes workbook or cell object identity.

## NEXT STEP

Run one preregistered causal experiment on the **same frozen 30 scripts and five write fixtures**: a reference-only fast path that preserves byte-identical script execution, external pre/post observation, abnormal-exit receipts and capture/replay, while skipping only direct-read bootstrap/artifact work when the unchanged classifier establishes no possible contact. Compare it with this Phase-8A H1 on the full command boundary and require exactness first. Keep the direct-contact path, artifact format, merged certificate and populations fixed. Do not modify the public RC or publish speed claims from this offline report.
