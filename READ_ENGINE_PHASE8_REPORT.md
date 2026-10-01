# Read Engine Phase 8 — integration readiness and representative product boundary

Status: **stopped before scored validation on a confirmed semantic blocker**. This is an offline research architecture audit, not a product change or speed claim. The public RC, `src/librecalc_agent/`, README, presentation, claim registry and frozen Phase 1–7 evidence were not modified. The independent [integration review](read_engine_phase8/INTEGRATION_READINESS_REVIEW.md), [known limits](read_engine_phase8/KNOWN_SEMANTIC_LIMITS.md), [claim boundaries](read_engine_phase8/CLAIM_BOUNDARIES.md), and [preregistered validation spec](read_engine_phase8/PREREGISTERED_VALIDATION_SPEC.md) contain the detailed audit. The spec SHA-256 is `20a149e390f102d26ef259082b34948d0d9eb5b4f2029e6ae5bbf268f2c1cd11`, also recorded in [its checksum file](read_engine_phase8/PREREGISTERED_VALIDATION_SPEC.sha256).

## PHASE 7 EVIDENCE CARRIED FORWARD

The exact 22 historical RC eligible/contact-selected scripts passed the Phase-7 scored output gate. H1/PY full-command warm median was **0.513**, 18/22 faster, with bootstrap median upper bound **0.749** and valid persistent reuse. Observed N=2/3/5 session medians were **0.878/0.708/0.662**, upper bounds **0.965/0.916/0.858**. Cold median was **1.194**, unsupported. The four residual warm losers were one workbook-iteration fallback and three short Templates. These facts remain valid **for those exact scripts**. Phase 8 found a new program outside that fixed population that the Phase-7 certificate mishandles; it does not rewrite their prior timings.

## INDEPENDENT INTEGRATION REVIEW

The process architecture has a credible core: a minimal external survivor waits for a genuine Python script process, while the script interpreter owns admission, source freshness, direct artifact serving and reference fallback. The observer can inspect effects after tested abnormal termination. Copying the prototype would be premature. The Phase-7 merged-cell observation certificate is **not fail closed** for admitted indirect method access, a concrete semantic stop before broader timing.

## ARCHITECTURE VS PROTOTYPE IMPLEMENTATION

**Earned conceptually:** one real script interpreter, an external post-death observer, a narrow direct OOXML read representation, strong content identity, persistent state and reference fallback. **Requires reengineering:** the native observer's snapshot/error/durability path, sitecustomize launch context, cache ownership, artifact loader/import split, classifier proof, proxy identity policy and product diagnostics. **Research-only:** benchmark ledgers/profiles, run-directory bookkeeping and wide event streams. **Reject as written:** the Phase-7 merged-cell certificate. The component-by-component classifications are in the integration review.

## REPRESENTATIVE POPULATION

The exact Phase-3/RC representative manifest has **30 distinct scripts from 21 tasks**, historically 8 direct-contact and 22 reference-only under the older Phase-3 architecture. All 30 ordered IDs matched the frozen RC manifest; all script and workbook SHA-256 values were rechecked against the archived files. The full identity table is frozen in the Phase-8 spec. The five separate changed-file fixtures are fixed to a pre-existing `Template_15_03` workbook and cover value, formula, multi-cell, new-sheet and output-file saves. They are not a replacement representative population.

## REPRESENTATIVE CORRECTNESS

**UNMEASURED UNDER PHASE 8.** A deterministic admitted fixture outside the 30 falsified the candidate's certificate before the representative correctness gate. Frozen admission returned `A1_ADMIT` and Phase-7 returned `certified=true, cell_calls=0` for `ws.__getattribute__("cell")(1,2)` on a covered merged child. Ordinary Python printed `MergedCell <MergedCell 'Sheet'.B1>`; unchanged Phase-7 treatment printed `ProxyCell <read_engine_phase3.runtime.ProxyCell object at ...>`. Runtime events confirmed direct serving and the merged-child direct route. The exact diagnostic is [indirect_cell_result.json](read_engine_phase8/certificate_review/indirect_cell_result.json). A nine-shape deterministic [certificate matrix](read_engine_phase8/certificate_review/matrix.jsonl) found two false positives: this method access and `ws.__getitem__("B1")`. This is not finite-fuzz proof of any other shape.

Per the requested stop rule, the four representative/changed-file JSONL ledgers contain **zero scored rows**, and [analysis.json](read_engine_phase8/analysis.json) explicitly records `STOPPED_BEFORE_SCORING`. No representative semantic equivalence conclusion follows.

## REFERENCE ONLY ECONOMICS

**UNMEASURED for Phase-7 architecture.** Phase 3 found 22/30 reference-only scripts, but its heavy parent/child lifecycle is different. The Phase-6/7 thin observer may be cheaper; the exact H1/PY ratio, median signed excess, bootstrap interval and practical non-interference question remain open. A second reference-only command would be labeled `SECOND_INVOCATION`, never `VALID_REUSE` without actual direct contact.

## DIRECT CONTACT ECONOMICS

**UNMEASURED outside the fixed 22.** Phase 7's 22 are contact-selected. The representative 30's historically eight direct-contact scripts need a new same-run full-command measurement after the semantic gate is repaired; their old Phase-3 ratios cannot be transferred to the Phase-7 runtime.

## FALLBACK ECONOMICS

**UNMEASURED in Phase 8.** The fixed 22's residual workbook-iteration parse remains a known double-work path. Broader fallbacks on the representative 30 must be classified by actual H1 events after the gate, not inferred from historical admission alone. General reference fallback must remain.

## REPRESENTATIVE COLD RESULT

No Phase-8 scored result. Phase-7 cold median **1.194** applies only to the fixed contact-selected 22 and cannot be presented as the 30-script cold result.

## REPRESENTATIVE WARM OR SECOND INVOCATION RESULT

No Phase-8 scored result. The spec separately defines actual child-confirmed `VALID_REUSE` for contact scripts and `SECOND_INVOCATION` for reference-only scripts. Neither endpoint has a Phase-8 number.

## REPRESENTATIVE SESSION RESULT

No Phase-8 scored N=1/2/3/5 sessions. Phase-7's favorable N=2/3/5 results remain limited to the exact 22 contact-selected scripts and do not establish a broadly enabled runtime's session economics.

## CHANGED FILE EFFECT CAPTURE

**FULL COST UNMEASURED.** The native observer compares byte snapshots, then starts a separate Python [capture helper](read_engine_phase6/capture_helper.py) only when XLSX bytes change. The helper re-snapshots post state, derives a package delta, rewrites committed bytes, validates and replays, then writes receipts. Its process startup and all these steps are inside the intended full-command timer, but the fixed 22 did not invoke them. The five fixed Phase-8 write fixtures were not scored after the semantic stop. The helper's failure status is recorded in the observer receipt, while `observer.c` returns the target's exit/signal status even if the helper fails; a production assurance policy cannot rely on process exit code alone.

## ABRUPT EXIT WITH CHANGED WORKBOOK

Phase 6 previously demonstrated post-death effect observation for `os._exit` and fatal SIGTERM fixtures. Phase 8 did not repeat or time a changed-file abrupt-exit run. Observer death, disk-full, helper failure and concurrent workbook mutation remain outside that established fixture result. Planned Phase-8 derivative diagnostics require a versioned spec amendment with script hashes before execution.

## MERGED CELL CERTIFICATE REVIEW

The certificate iterates literal AST `.cell` attribute nodes and requires each returned object to be immediately consumed by `.value`, `.data_type`, `.coordinate`, `.row` or `.column`. It also rejects literal worksheet subscripts on names in `proven_worksheets`. It does **not** establish that these are the only ways an admitted program can invoke the proxy's `.cell` path. `ws.__getattribute__("cell")` obtains a bound method without a literal `.cell` AST node. `ws.__getitem__("B1")` invokes `ProxyWorksheet.cell` internally without such a node. Both are admitted and certified; the first is an observed output difference. The certificate also returns true for zero `.cell` calls. Assignments, walrus, comprehensions, lambdas, nested functions, aliases, dynamic attribute access, rebinding and syntax-version changes therefore need proof against the *actual dispatch graph*, not just the syntactic terminal pattern. False negatives are acceptable; this false positive is not.

## KNOWN SEMANTIC LIMITS

The confirmed certificate bypass is the immediate blocker. Independently, `cell.parent is ws` was already known to differ after reference fallback because the returned real cell belongs to a real worksheet while `ws` remains a proxy. `type/repr/isinstance` of ordinary proxy cells, object escape, richer styles and mixed proxy/reference identity are not broadly equivalent. Source hashing is checked before load but not a lock against later concurrent mutation. The [limits register](read_engine_phase8/KNOWN_SEMANTIC_LIMITS.md) lists expression, behavior, admission/fallback and integration consequence separately. No broad openpyxl equivalence is earned.

## ARTIFACT READINESS

**`JSONZ_MEMORY_V1`: READY FOR INITIAL INTEGRATION AS A FORMAT CONCEPT, with loader hardening.** It has explicit magic, source/decoder/contract/format binding, whole-artifact and payload checks, typed schema, compressed/uncompressed size caps, no executable deserializer and atomic individual publication. A format shootout is unnecessary here. The current implementation imports the Phase-1 parser module in warm serving, permits very large JSON/decompressed payloads, lacks production cache permissions/locking/quotas and uses separate artifact/sidecar publication. Hostile-cache and resource-exhaustion behavior need reengineering before release; these do not require choosing a new representation now.

## OBSERVER PRODUCTION READINESS

**Production-engineerable concept, prototype not copy-ready.** Tested Linux/POSIX fork/exec, wait, signal re-raise, inherited stdout/stderr and post-death observation are strengths. `FTW_PHYS` symlink behavior differs from frozen Python capture; the observer snapshots all XLSX bytes into memory, caps each at 512 MiB and total count at 1000, rejects some legal paths, writes non-durable receipts, has no cleanup policy and aborts on several I/O failures without final status. Helper failure is reported but not reflected in target exit status. Portability and failure policy are engineering work, not reasons to discard the external-survivor architecture.

## SECURITY AND PORTABILITY

The cache key binds a whole-file SHA and version values, but a production cache must prevent symlink/path substitution and enforce owner permissions; concurrent publication needs deterministic validation/retry policy. The direct decoder reads ZIP members and parses XML without a product-level hostile-XLSX resource budget; the safe artifact cap alone does not bound source ZIP expansion. JSON/zlib parsing is bounded yet can still consume substantial memory. Context/PYTHONPATH injection must be scoped to the intended script and protect run-directory paths. Linux is the only demonstrated observer platform. macOS needs tests; Windows needs a different process/observation implementation or explicit unsupported scope. No cross-platform claim is supported.

## STATE LIFETIME AND CACHE OWNERSHIP

Recommend **user-scoped persistent derived artifacts** keyed by workbook content plus decoder/contract/format identity, with separately scoped per-run receipts. This is a conceptual lifecycle recommendation, not an implementation. Define cache permissions, quota/eviction, version invalidation, concurrent builders and multi-user isolation. A per-run cache would erase the reuse economics; a project-global cache without ownership rules invites permission and trust problems. Expected real reuse horizon remains unmeasured on representative workflows.

## PRODUCT DIAGNOSTICS

A compact product receipt should record source/artifact identity, `BUILT`/child-confirmed `REUSED`, direct contact, reference fallback reason, target exit/signal, effect-capture and validation status, plus coarse timing only when enabled. Per-cell events, raw research JSONL and benchmark profiles are research-only. Capture/helper failures must be surfaced in a reliable final status/receipt policy; silent observer or disk failures cannot be treated as successful assurance.

## CLAIM BOUNDARIES

Mechanism evidence supports avoiding normal openpyxl *workbook parsing* on supported direct paths, byte-identical ordinary script source, typed narrow-read parity on fixed evidence and cross-process artifact reuse. Warm and session speed are supported only on the fixed 22, not on a representative or public-product population. Cold speed, write speed, broad equivalence, changed-file economics, token/cost improvement and cross-platform support are unsupported. The new certificate counterexample narrows any merged-cell semantic statement to the exact tested programs until the proof is repaired. See [claim boundaries](read_engine_phase8/CLAIM_BOUNDARIES.md).

## WHAT MUST CHANGE BEFORE PRODUCT CODE

First close the semantic certificate false positive under unchanged agent code and reference fallback, including indirect method and dunder worksheet access, with deterministic adversarial fixtures and an exact fixed-22 regression gate. Then execute the frozen 30-script and changed-file validation under a versioned amended spec. Product engineering must also specify proxy identity/fallback limits, observer failure/capture contract, hostile-source/resource bounds, cache ownership/concurrency, platform scope and packaging. These are prerequisites for choosing how to reengineer experimental components, not optimizations of the fixed 22.

## IS ANOTHER PERFORMANCE EXPERIMENT REQUIRED?

**Yes, but only after the semantic blocker is resolved.** The highest-value missing performance evidence is the exact 30-script Phase-7 full-command study, especially reference-only overhead, followed by the fixed changed-file observer/capture endpoint. No Phase-8 scored benchmark was run, so this report cannot say either boundary wins or loses.

## INTEGRATION READINESS VERDICT

**D. `NOT YET READY — SEMANTIC/ASSURANCE ISSUE`.** A concrete admitted program received an unsafe merged direct route and produced a different observable cell type. This satisfies the specified pre-scoring stop condition. The existing 22-script result remains valid for its identities, but product integration should wait for a fail-closed certificate and the representative/changed-file gates. The direct engine, persistence and thin external observer remain credible architectural candidates.

## AGENT INDEPENDENT PRODUCT ARCHITECTURE OPINION

If responsible for implementation, I would build a real script interpreter with guarded interposition and a small external survivor, using content-addressed user cache state and explicit reference fallback. I would **not copy `observer.c` directly**: capture scope, resource bounds, durability, helper-failure propagation and portability need deliberate product semantics. The single highest-risk standing assumption is that the classifier plus certificate can safely decide when proxy objects cannot escape. Phase 8 disproved that assumption for the current certificate. The next highest economic unknown is changed-file assurance cost, followed by reference-only overhead.

## NEXT STEP

Run a **semantic hardening experiment** on the merged-cell certificate without changing the narrow read contract or optimizing the fixed 22. Require all ways an admitted program can reach `ProxyWorksheet.cell`—including `__getattribute__` and `__getitem__`—to be either proven terminal scalar observations or routed to reference. Verify adversarial fixtures, the known parent-identity boundary and the frozen 22 exactness gate. Only then amend/hash the Phase-8 validation spec and execute its unchanged 30-script representative and five-fixture changed-file full-command protocol. No public product files or claims should change before that evidence exists.
