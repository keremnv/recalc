# Read Engine Phase 2 — persistent state across fresh processes

Status: **offline experiment**, not a product change or public speed claim. The active, hashed [v2 preregistration](../../read_engine_phase2/PREREGISTERED_SPEC_v2.md) (`227c7618a244ef9dc4960b6d1aed751165ec326bd2a6d9670895e773df7bddde`) fixes the decoder, 39-workbook construction corpus, 51 archived traces, formats, F1 freshness, and ten fresh-process invocations per trace/arm. The original [v1 spec](../../read_engine_phase2/PREREGISTERED_SPEC.md) and its [partial ledgers](../../read_engine_phase2/v1_partial) are preserved but excluded: before reaching the known malformed-oracle workbook in construction timing, a runner review found that P0 would abort instead of recording an unavailable reference. V2 changed only that error handling, was hashed before rerun, and restarted all gates and scored rows. [Implementation identity](../../read_engine_phase2/implementation_identity_v2.json) and the complete [population](../../read_engine_phase2/population.json), [correctness](../../read_engine_phase2/raw_correctness.jsonl), [timing](../../read_engine_phase2/raw_timings.jsonl), [session](../../read_engine_phase2/session_timings.jsonl), [invalidation](../../read_engine_phase2/invalidation.jsonl), [profile](../../read_engine_phase2/profile.json), and [paired analysis](../../read_engine_phase2/analysis.json) are retained.

All ratios below are **treatment/comparator** on the same workbook or trace; below 1 is faster. Construction has 39 workbook identities (38 for P1/P0). Trace results have 51 contact-selected traces from only seven snapshots, not 51 independent workbooks. The 2,000-resample percentile intervals are conditional on these fixed identities; they do not establish a broader workbook-population confidence interval. OS filesystem cache was not flushed, so these are neither controlled cold-disk measurements nor public product invocations.

## PHASE 1 RESULT CARRIED FORWARD

Phase 1 established exact R2/R3 replay on 51/51 archived Candidate-A traces and parity on 1,022,280 nonempty cells per direct variant across 38/38 reference-loadable workbooks. The 39th remains `REFERENCE_ORACLE_UNAVAILABLE` because normal openpyxl fails on malformed core-properties XML. R2 first-use mechanism median ratio to R0 was 0.844; R3 was 1.129; all R3 traces broke even by N=2 in that offline experiment. Phase 2 does not reinterpret those as product results or alter the decoder.

## PERSISTENT REPRESENTATIONS

P0 loads the workbook normally with openpyxl on every invocation. P1 directly decodes OOXML to the frozen in-memory `MemoryBook` on every invocation. P2 persists the Phase-1 minimal SQLite sheet/cell schema with version/identity metadata; it is file-backed and opened read-only. P3 pickles the Phase-1 `MemoryBook` with a versioned envelope, then fully deserializes it in each process. P3 is **EXPERIMENTAL_TRUSTED_CACHE_FORMAT — NOT A PRODUCT SAFETY DECISION**. It was chosen to measure native-object persistence economics, not to authorize untrusted pickle loading.

No additional format was added after results. All 2,040 session invocations used fresh Python processes. Each trace/arm had one empty-cache, ten-invocation session; the measured cumulative prefixes are N=1,2,3,5,10. P2/P3 had 51 `BUILT` first invocations each and 459 `REUSED` later invocations each. No in-memory registry supplied reuse.

## FRESHNESS CONTRACT

P2/P3 compute whole-file SHA-256 of the source on **every** process invocation, derive a deterministic key from source SHA, decoder ID, contract ID and format version, then validate a sidecar, artifact size/SHA and internal metadata. P2 also runs SQLite `PRAGMA integrity_check` on every reuse. The validated manifest is published last after file sync and atomic renames. P0/P1 do not pay a freshness hash because they have no persistent derived artifact. This comparator asymmetry is part of the measured lifecycle. No metadata-only F2 shortcut was attempted: path, size and mtime alone do not fail-closed detect arbitrary byte changes.

## CORRECTNESS AFTER REOPEN

The v2 gate compared P1/P2/P3 to a fresh P0 oracle on **all 51 exact traces**; all 153 treatment rows were exact, with no reference/treatment trace error. P2/P3 artifacts were built in one child and reopened in another before comparison. All 38 normal-reference-loadable corpus workbooks matched ordered sheet names, bounds and **1,022,280 nonempty cells per persistent variant** after reopen, with zero mismatch. The fixed 39th workbook remained oracle-unavailable but successfully constructed and stayed in artifact/freshness timing. A sentinel blocked both `openpyxl.load_workbook` entry points during direct construction and serving. These gates cover the frozen narrow surface, not all workbook APIs or exhaustive empty-cell coordinates.

## INVALIDATION AND CORRUPTION

For the preregistered Template and Financial_Model staged copies, both formats followed `H1 BUILT → H1 REUSED → changed bytes H2 BUILT → restored H1 REUSED → missing artifact BUILT → truncated artifact BUILT`. All four workbook/format probe rows passed. The H2 scalar edit, H1/H2 hashes and reasons are in the invalidation ledger. The source fixtures were not mutated. This establishes rejection on the tested changes and corruptions, not an exhaustive adversarial cache-safety proof.

## BUILD COST

BUILD starts at source identity/freshness and ends when the representation/artifact is ready. It includes P2/P3 source hashing, direct decoding, storage, artifact hashing and atomic publication; attach and process launch are reported separately. One rotated first observation per workbook/arm was scored; no disk-cache claim follows from that label.

| Paired BUILD ratio | Books | Median | Geometric mean | Faster/slower/tied | Range | 95% bootstrap median interval |
|---|---:|---:|---:|---:|---:|---:|
| P1 direct rebuild / P0 normal load | 38 | 0.630 | 0.593 | 38/0/0 | 0.341–0.965 | 0.456–0.794 |
| P2 SQLite build / P1 memory build | 39 | 1.385 | 1.437 | 1/38/0 | 0.991–2.067 | 1.322–1.503 |
| P3 native build / P1 memory build | 39 | 1.037 | 1.095 | 6/33/0 | 0.872–1.389 | 1.023–1.071 |
| P3 native build / P2 SQLite build | 39 | 0.727 | 0.763 | 39/0/0 | 0.591–0.989 | 0.713–0.779 |

Median individual build observations were P0 156.8 ms on 38 loadable books, P1 64.5 ms, P2 86.9 ms, P3 57.9 ms; these **unpaired medians are descriptive only**. The malformed book has no ready P0 observation and remains in every direct-arm denominator.

## WARM ENGINE COST

WARM ENGINE starts inside a fresh child at source verification and stops after trace plus release. P0's analogous interior endpoint loads normally and reads the same trace. Per-trace medians aggregate the nine reused invocations at positions 1–9 before pairing.

| Paired WARM ENGINE ratio | Median | Geometric mean | Faster/slower/tied | Range | 95% bootstrap median interval |
|---|---:|---:|---:|---:|---:|
| P2 / P0 | 0.010 | 0.013 | 51/0/0 | 0.002–0.317 | 0.010–0.014 |
| P3 / P0 | 0.016 | 0.014 | 51/0/0 | 0.004–0.133 | 0.015–0.016 |
| P3 / P2 | 1.556 | 1.115 | 17/34/0 | 0.373–1.775 | 1.181–1.598 |

The P2/P3 ordering varies by snapshot: four larger snapshots favored SQLite interior latency; three smaller ones favored native deserialization. This is a seven-snapshot observation, not a general workbook rule. The actual trace-operation median was 3.12 ms for P2 and 1.22 ms for P3; P2's better overall warm engine time on many large snapshots arises from avoiding a full object reload.

## WARM PROCESS COST

WARM PROCESS is the external parent timer from Python child launch to exit for each reused invocation. It includes interpreter startup, imports, trace-data loading, freshness, artifact validation/load, reads, telemetry and exit.

| Paired WARM PROCESS ratio | Median | Geometric mean | Faster/slower/tied | Range | 95% bootstrap median interval |
|---|---:|---:|---:|---:|---:|
| P2 / P0 | 0.194 | 0.212 | 51/0/0 | 0.048–0.985 | 0.193–0.197 |
| P3 / P0 | 0.199 | 0.215 | 50/1/0 | 0.050–1.001 | 0.197–0.200 |
| P3 / P2 | 1.013 | 1.013 | 11/40/0 | 0.900–1.072 | 1.007–1.026 |

Thus process startup substantially reduces the *size* of the engine-level advantage but does not erase it on these traces. The process figures are still offline trace execution, not LibreCalc invocation wall time.

## SESSION ECONOMICS

SESSION measures the observed elapsed time from the first child launch with no artifact through the Nth child exit. Every subsequent P2/P3 child verified and reopened the first child's artifact. Comparator P0 independently loaded the identical snapshot N times. P1 independently decoded it N times.

| N | Ratio | Median | Geometric mean | Faster/slower/tied | Range | 95% bootstrap median interval |
|---:|---|---:|---:|---:|---:|---:|
| 1 | P1/P0 | 0.844 | 0.822 | 50/1/0 | 0.638–1.020 | 0.840–0.852 |
| 1 | P2/P0 | 1.064 | 0.983 | 13/38/0 | 0.683–1.115 | 1.039–1.072 |
| 1 | P3/P0 | 0.879 | 0.845 | 50/1/0 | 0.640–1.014 | 0.869–0.884 |
| 2 | P1/P0 | 0.842 | 0.822 | 51/0/0 | 0.640–0.998 | 0.837–0.848 |
| 2 | P2/P0 | 0.631 | 0.623 | 51/0/0 | 0.369–0.927 | 0.628–0.636 |
| 2 | P3/P0 | 0.537 | 0.552 | 51/0/0 | 0.346–0.941 | 0.533–0.543 |
| 3 | P1/P0 | 0.843 | 0.821 | 51/0/0 | 0.644–0.976 | 0.840–0.848 |
| 3 | P2/P0 | 0.485 | 0.496 | 51/0/0 | 0.263–0.950 | 0.483–0.489 |
| 3 | P3/P0 | 0.426 | 0.449 | 51/0/0 | 0.248–0.954 | 0.421–0.429 |
| 5 | P1/P0 | 0.843 | 0.822 | 51/0/0 | 0.645–0.971 | 0.841–0.847 |
| 5 | P2/P0 | 0.369 | 0.391 | 51/0/0 | 0.178–0.965 | 0.367–0.372 |
| 5 | P3/P0 | 0.335 | 0.363 | 51/0/0 | 0.169–0.977 | 0.333–0.337 |
| 10 | P1/P0 | 0.843 | 0.822 | 51/0/0 | 0.646–0.978 | 0.840–0.846 |
| 10 | P2/P0 | 0.282 | 0.307 | 51/0/0 | 0.113–0.980 | 0.281–0.284 |
| 10 | P3/P0 | 0.267 | 0.293 | 51/0/0 | 0.110–0.995 | 0.266–0.269 |

For N=2, P2's geometric mean ratio was 0.623 and bootstrap median interval 0.628–0.636; P3's were 0.552 and 0.533–0.543. At N=10, P2's interval was 0.281–0.284 and P3's 0.266–0.269. P3 beat P2 on 50/51 sessions at N=1–5 and 49/51 at N=10. The dense repeated use of seven contact-selected snapshots is central to this result; it does not establish economics for one-off or fallback-heavy product scripts.

## BREAK-EVEN BY REUSE HORIZON

The first **observed** favorable N among 1,2,3,5,10 was N=1 for 13 P2 traces and N=2 for the other 38. P3 broke even at N=1 for 50 traces and N=2 for one. P1 was favorable at N=1 for 50 and N=2 for one. Both persistent formats therefore beat repeated reference execution by **N=2 on all 51 fixed traces**, without extrapolation beyond the measured horizon. P2 N=1 was generally unfavorable once its initial SQLite artifact was charged; P3 N=1 was generally favorable, although P1 remained cheaper to construct as a pure in-memory baseline on most paired workbooks.

## SQLITE COST

P2's median BUILD was 1.385× P1 on paired corpus books. Its warm interior median was 42.5 ms, including approximately 2.5 ms source SHA, 10.6 ms artifact SHA, 24.6 ms SQLite metadata/integrity validation, 0.58 ms read-only attach, and 3.12 ms trace operations. These are medians of components and do not algebraically sum to the median total. The complete `PRAGMA integrity_check` is a deliberately conservative v1 format rule and is charged on every process; it is not an intrinsic property of every possible SQLite lifecycle. P2's lookup trace cost exceeded P3's on the median observed trace, but P2 avoided full deserialization and won warm interior time on the four large snapshots.

## NATIVE PERSISTENCE COST

P3's median paired construction was 0.727× P2. Its warm interior median was 67.5 ms, including about 2.5 ms source SHA, 5.23 ms artifact SHA, **56.5 ms combined file read and deserialization/attach**, and 1.22 ms trace reads. Serialization during BUILD had a 1.35 ms median on the 39-book corpus; the corresponding direct decode median was 55.2 ms. File read versus pickle deserialization was **UNMEASURED separately**; the combined attach dominates P3 warm engine on the large snapshots. The artifact is fully loaded into process memory. The trusted pickle format is only an economics probe and must not be treated as a public cache design.

## HASHING COST

On reused trace invocations, median source SHA was about 2.5 ms for each persistent arm. This is about 6% of P2's median interior time and 4% of P3's; medians are descriptive, not exact contribution accounting. Full **artifact** SHA cost was larger: 10.6 ms P2 and 5.23 ms P3. Source hashing therefore did not erase the observed warm advantage on these workbooks, but artifact validation and P2 integrity checking consume a meaningful share. No metadata-only freshness policy was measured; any future shortcut must still fail closed on changed bytes.

## PROCESS STARTUP COST

Median external process times were 5,824 ms P0, 1,125 ms P2, and 1,148 ms P3. The median external-minus-child-engine residual was about 1,550 ms P0 and 1,081–1,084 ms P2/P3. The residual includes interpreter startup, imports, trace JSON loading, telemetry serialization, IPC and exit; **pure Python startup is UNMEASURED separately**. On P2/P3 the residual is much larger than the 43–68 ms warm engine interior. It narrows the apparent speedup from roughly 60–100× interior to roughly 5× at the process endpoint, but does not reverse it on the fixed traces.

## ARTIFACT SIZE AND MEMORY

Across the 39 construction workbooks, P2 median artifact size was 180,224 bytes and median artifact/source ratio 2.712 (sum 72.2 MB versus 31.2 MB source). P3 median size was 66,585 bytes and median ratio 0.563 (sum 34.4 MB). Ratios ranged 0.274–4.551 for P2 and 0.105–2.249 for P3. The seven trace snapshots show a clear descriptive association for P3: 2 KB artifacts attached in about 0.1 ms, while 3.8–4.8 MB artifacts took about 53–58 ms; no causal size model is claimed. P2 is file-backed with one read-only serving connection; P3 fully loads its object graph. Linux process high-water RSS was recorded after trace (median roughly 329 MB in all arms), but **incremental artifact memory after attach is UNMEASURED** because imports and prior process allocations dominate this coarse measure. Physical file-read counts are also unmeasured.

## OPENPYXL DEPENDENCY BOUNDARY

P1/P2/P3 used the frozen Phase-1 ZIP/XML decoder, guarded against `openpyxl.load_workbook` during construction and serving. The decoder still imports openpyxl formula translation, number-format/date helpers and formula observable classes (`ArrayFormula`, `DataTableFormula`). This is **workbook-parser independence**, not openpyxl-library independence. P0 remained the normal-openpyxl reference oracle; the malformed core-properties workbook remained unresolved rather than being counted as a direct-decoder semantic pass.

## DOES THE ADVANTAGE SURVIVE REAL REUSE?

**Yes for the measured offline, contact-selected traces under F1 freshness and fresh processes.** P2/P3 proved actual cross-process reuse and beat N independent P0 executions on all 51 traces by N=2. P3 also beat P0 on 50/51 N=1 sessions; P2 did so on 13/51. Hashing and process startup reduced, but did not erase, the advantage. This answers the Phase-2 mechanism/session question, not public RC speed: the packaged runtime still has whole-script admission, pre/post capture, fallback, validation and product lifecycle costs outside these trace sessions. The 51 traces come from seven snapshots and were selected for read contact.

## HAS A REPRESENTATION EARNED INTEGRATION?

**A P3-like persisted in-memory read representation has earned the next limited integration experiment**, because it kept P1-like construction economics more closely than P2 and won 49–50/51 measured P2 session pairs across N=1–10. Raw pickle has **not** earned public use; its trusted-cache assumption is an explicit safety boundary. P2 remains a viable conservative comparator and sometimes gives lower warm engine latency, especially on large snapshots. There is no basis here for another unrestricted format shootout. Neither representation has established product speed or broad semantic coverage.

## NEXT DISCRIMINATING EXPERIMENT

Prototype the chosen persistent-state lifecycle behind the existing narrow read contract in a **separate offline, product-shaped harness** on fixed identical scripts/workbooks, with a safe artifact loading rule, real whole-script admission/fallback, process startup, capture/validation and correct source invalidation. Score cold and genuinely reused warm invocations separately; preserve reference-openpyxl fallback and publication witnesses. Only that experiment can establish whether the observed trace/session advantage survives the public product boundary. Do not modify RC or public claims on the basis of Phase 2.
