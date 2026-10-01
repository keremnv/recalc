# Read Engine Phase 6 — thin external observer architecture experiment

Status: **offline experimental result; no public product change or public speed claim.** The selected H2 is a POSIX prototype. [Architecture decision](read_engine_phase6/ARCHITECTURE_DECISION.md) was written before H2 implementation; its SHA-256 is `d76e19fe92c40f816f5eaed29298d1b17408820f5c50c52883ff30528e2f3850`. [Preregistration](read_engine_phase6/PREREGISTERED_SPEC.md) was written and hashed before H2 implementation or scoring; its SHA-256 is `d2a7aa2f46ebbf351d43f6a259c986e9b3c312f7f6325f4de6d5ece34b8e5a6c`. The pinned [implementation identity](read_engine_phase6/implementation_identity.json) was verified during analysis. Sources are the [process fixture ledger](read_engine_phase6/process_semantics.jsonl), [correctness ledger](read_engine_phase6/raw_correctness.jsonl), [raw command timings](read_engine_phase6/raw_timings.jsonl), [session timings](read_engine_phase6/session_timings.jsonl), [profile](read_engine_phase6/profile.json), and [paired analysis](read_engine_phase6/analysis.json).

## PHASE 5 RESULT CARRIED FORWARD

Phase 5's fixed 22-workload result remains historical evidence: same-run warm H1/H0 `0.793` (22/22 faster), H1/PY `0.633` (15/22 faster), cold H1/PY `1.244`. Its one-interpreter `runpy` arm lost atexit `__main__` fidelity and could not observe effects after `os._exit` or fatal process death. Phase 6 does not reinterpret those archived numbers. Absolute command times drifted substantially between runs—the three PY Templates were approximately 88–89 ms in Phase 5 and 157–164 ms here—so **same-run Phase-6 pairs** are the timing authority.

## INDEPENDENT ARCHITECTURE REVIEW

Before H2 code, inspection of the Phase-4/5 harness, bootstrap, artifact path and capture machinery indicated that an external survivor is required for post-death observation, but a second **Python** runtime is not. Thirty unscored fresh-launch diagnostics gave medians of 1.08 ms for `/bin/true`, 1.12 ms for `/bin/sh -c :`, 18.44 ms for the RC Python running `pass`, and 40.26 ms for Python importing `pathlib,json,subprocess`. Those probes do not predict full commands; they made a fresh Python observer a poor first discriminator for short scripts. The decision note compares native, fresh Python, persistent Python, shell and pure one-interpreter forms. A small native observer was selected because it can distinguish signalled death from ordinary `exit(128+signal)`, survive the child, and keep spreadsheet work inside the real script interpreter. A persistent supervisor was deferred because its service/IPC/startup accounting is a different question.

## SELECTED THIN OBSERVER

H2 is the experimental [C observer](read_engine_phase6/observer.c) launching an ordinary fresh `<RC Python> workload.py` with a guarded [sitecustomize bootstrap](read_engine_phase6/bootstrap/sitecustomize.py). It retains one external survivor and one real script interpreter. The source script is byte-identical; there is no `runpy`, AST transform, script import, daemon or process pool. H0 is frozen Phase-4 two-Python-process execution; H1 is frozen Phase-5 one-interpreter execution; PY is direct Python. Only H2 is the candidate. H2 does not change the decoder, `JSONZ_MEMORY_V1` artifact, source SHA, classifier, proxy, merge/iteration fallback, or reference-openpyxl rules.

## OBSERVER RESPONSIBILITIES

The observer validates bounded paths, creates a run directory, snapshots exact bytes of discovered `.xlsx` files before execution, forks and waits for the real script process, snapshots again, records raw exit/signal status and writes a compact receipt. If workbook bytes changed, it starts a **post-termination** Python [capture helper](read_engine_phase6/capture_helper.py) using the frozen package delta/validation machinery and the saved pre bytes; this cost is inside the full-command timer, including after abrupt script death. With no changed workbook, it writes an empty effect record without launching the helper. It never imports Python/openpyxl, classifies scripts, hashes sources for artifact identity, parses OOXML, or materializes an artifact. It inherits stdout/stderr directly and does not close extra non-CLOEXEC descriptors.

## SCRIPT PROCESS RESPONSIBILITIES

The real Python script interpreter runs guarded `sitecustomize` before the unchanged source. It loads the existing config and unchanged whole-script classifier, discovers top-level source workbooks, computes whole-file SHA-256, performs frozen Phase-4 artifact discovery/integrity/build, imports and installs frozen Phase-3 Runtime, fully validates/decodes persistent state before direct serving, and preserves ordinary reference-openpyxl fallback. Runtime events and source recheck remain. The observer's artifact status is not a semantic `REUSED` witness: scored warm reuse requires the child to decode the artifact and emit direct-serving contact. No construction or semantic state is passed through observer memory.

## PROCESS SEMANTICS GATE

All **20 preregistered process fixtures ran before scored workloads**: 18 `EXACT`, two `OBSERVABLE_DIFFERENCE_BUT_ACCEPTABLE`, none `PRODUCT_CONTRACT_VIOLATION` or `UNTESTABLE`. The two acceptable differences were startup-loaded runtime modules visible in `sys.modules` and extra bootstrap/repository entries visible in `sys.path`, not script `__main__` identity, exit, output or effect observation. Those path entries are a real import-resolution surface for future production review. Fixtures covered module/file/package/spec/loader and `import __main__`; argv/path/cwd/environment/extra FD; local and repeated imports; stdout/stderr/flush; return, SystemExit and exception; finally/file flush; atexit output and workbook write; subprocess; caught signal, SIGINT, SIGTERM, `os._exit`, and normal exit 143. H2 restored the atexit `__main__` marker that H1 lost. This is evidence for the tested process contract, not an assertion that injection is indistinguishable to every arbitrary Python program.

## ABRUPT TERMINATION AND EFFECT OBSERVATION

After a fixture mutated a workbook then called `os._exit(7)`, H2 returned status 7 **and** persisted an observer receipt and one package-effect record; H1 left no post-run receipt. After the fatal SIGTERM fixture, H2 likewise recorded the effect and receipt after child death, then exposed signal termination. An atexit workbook write also appeared in H2's post snapshot, preserving the ordering Phase 5 could not get from naive `runpy`. The external observer itself must survive; host death, observer death and concurrent unrelated workbook mutation are outside this gate. The helper is charged on changed-file commands, but the fixed 22 primary scripts were read-only, so this experiment has not measured general write-heavy product economics.

## EXIT SIGNAL AND FD FIDELITY

`waitpid` retains normal exit versus signal. H2 writes the receipt and then re-raises the child signal against itself: SIGTERM and SIGINT appeared to the external runner as `-15` and `-2`, matching PY, while an ordinary `exit(143)` remained 143. H0's Python exit wrapping instead exposed 241 and 254 on those signal fixtures. Extra inherited FD content (`b'Z'`) was visible under PY and H2; H0's child closed it. Script stdout/stderr are inherited, not buffered and re-forwarded by the observer. These fixture observations establish the tested Linux/POSIX behavior, not Windows portability.

## CORRECTNESS ON THE FIXED 22

All 22 script/source/staged-workbook hashes matched the frozen Phase-3/RC eligible identities. Before timing, 26 lifecycle/invalidation probes passed, including missing, truncated, modified, version-incompatible and schema-invalid artifacts, same-path changed source and restoration. All 22 unscored four-arm cold/warm gates passed. The scored ledger has **1,320 command rows** (`22 × 3 repetitions × 5 invocations × 4 arms`), **330 paired correctness rows**, and **264 session rows**. Every scored correctness comparison passed: exit and normalized output, workbook/package state, direct-serving contact, fallback routes/counts and artifact status. All H2 warm rows had child-confirmed `REUSED`; the four existing proxy-operation fallbacks remained. There were no new semantic failures. The 22 scripts represent only 14 tasks and were originally contact-selected; this does not establish broad program equivalence.

## COLD RESULT

The full external timer includes observer startup, pre-snapshot, fresh script interpreter/bootstrap, source SHA, direct build and artifact publication, script/fallback, post-snapshot/validation, receipt and observer exit. Paired workload medians over three independent cold repetitions:

| Comparison | Median ratio | Geometric mean | Bootstrap median 95% | Faster / slower | Range |
|---|---:|---:|---:|---:|---:|
| H2 / PY | **1.215** | 1.209 | [1.019, 1.357] | 7 / 15 | [0.833, 2.423] |
| H2 / H0 | **0.695** | 0.697 | [0.625, 0.801] | 22 / 0 | [0.484, 0.950] |
| H2 / H1 | 0.973 | 0.980 | [0.956, 1.001] | 15 / 7 | [0.829, 1.185] |

H2 materially reduces H0's cold overhead, but cold product-shaped speed against direct Python remains **unsupported**. Cold H2 child-side pre-runtime work includes artifact construction; its across-workload median is 519 ms (range of per-workload medians 123–3,285 ms). This is not an observer cost.

## WARM RESULT

Every H2 warm invocation reused a valid child-decoded artifact; the same external command boundary charges observer, source freshness, artifact load, script and all post work. Paired workload medians:

| Comparison | Median ratio | Geometric mean | Bootstrap median 95% | Faster / slower | Range |
|---|---:|---:|---:|---:|---:|
| H2 / PY | **0.598** | 0.586 | **[0.406, 0.952]** | **15 / 7** | [0.185, 1.203] |
| H2 / H0 | **0.774** | 0.772 | [0.683, 0.797] | 22 / 0 | [0.657, 0.972] |
| H2 / H1 | **0.958** | 0.969 | [0.947, 0.973] | 19 / 3 | [0.911, 1.135] |

The preregistered H2/PY warm rule—median below one, majority faster, bootstrap upper bound below one—**passes**. Median signed H2 minus PY wall is −128.7 ms (range −2,019.2 to +546.1 ms). A task-cluster descriptive check has median ratio 0.631 over 14 tasks (11 faster, 3 slower; task bootstrap interval [0.469, 0.888]); it does not make these contact-selected scripts representative. The full-boundary speed result applies to this fixed offline population and H2 artifact-reuse regime, not the public RC.

## SESSION RESULT

Each observed session begins with no artifact, then reuses the artifact in fresh commands. The table is the ratio of H2's **complete N-command sum** to N independent PY commands; no construction is algebraically amortized away.

| N | H2/PY median | Geometric mean | Bootstrap median 95% | Faster / slower | Range | H2/H0 median | H2/H1 median |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.215 | 1.209 | [1.019, 1.357] | 7 / 15 | [0.833, 2.423] | 0.695 | 0.973 |
| 2 | 0.912 | 0.914 | [0.749, 1.082] | 14 / 8 | [0.513, 1.717] | 0.742 | 0.981 |
| 3 | 0.736 | 0.806 | [0.679, 1.042] | 15 / 7 | [0.404, 1.533] | 0.759 | 0.983 |
| 5 | 0.670 | 0.727 | [0.555, 1.008] | 15 / 7 | [0.310, 1.423] | 0.755 | 0.977 |

The observed session medians improve after reuse, but **none of N≤5 has a bootstrap upper bound below one**. The fixed session-support criterion therefore remains unmet. The N=5 interval is close to one; it is not a positive session claim. Startup is charged each time; no daemon is used.

## H2 VS H0

The same-run H2/H0 warm median is **0.774**, with H2 faster on **22/22** and interval [0.683, 0.797]. Cold H2/H0 is 0.695, also 22/22 faster. This is a process-ownership contrast with exact same scripts and unchanged read/fallback semantics. H0 still runs a heavy Python parent and child; H2 leaves semantic setup in the real script interpreter and retains only external observation in native code. The measurement establishes the combined architecture effect, not a precise per-import or per-process causal attribution.

## H2 VS H1

H1 was retained as a **normal-exit performance reference**, not an acceptable architecture. H2's same-run warm median is **0.958× H1** (19/22 faster; interval [0.947, 0.973]); cold median 0.973 has interval [0.956, 1.001]. A separate native observer did **not** force a return to H0 economics; on this run H2 was slightly faster than `runpy` H1 overall while repairing the tested assurance failures. This does not prove the observer itself accelerates anything: H2 also changes the target's execution mechanism from `runpy` to real script launch, and those effects are inseparable in this arm contrast.

## SHORT SCRIPT RESULT

The three Template scripts remain the strongest fixed-cost discriminator. Figures are Phase-6 same-run per-workload warm command medians from the paired analysis, rounded to 0.1 ms.

| Template | PY ms | H0 ms | H1 ms | H2 ms | H2/PY | H2 observer pre + post snapshot ms* |
|---|---:|---:|---:|---:|---:|---:|
| 03_03 | 156.7 | 254.5 | 184.2 | 169.3 | 1.080 | ~0.21 |
| 06_12 | 160.7 | 261.5 | 183.2 | 174.8 | 1.087 | ~0.20 |
| 16_07 | 164.0 | 263.7 | 185.1 | 176.5 | 1.077 | ~0.18 |

\*Separate component medians; not an additive accounting identity. H2 removes roughly 85–95 ms relative to H0 on these scripts and comes within 12–14 ms of PY, but **all three still lose**. Their artifact load is ~0.8–1.3 ms and no reference fallback occurs. H2's bootstrap (roughly 114–116 ms, including ~90–92 ms Runtime import/install) and remaining interpreter/script costs dominate; the external observer's own measured pre/post work is small. A 1 ms native-launch diagnostic was not used as a substitute for these full-command observations.

## FALLBACK RESULT

No merge or workbook-iteration serving changed. The four existing warm proxy-operation escapes remain, each with 12 fallback events over 12 scored warm commands. The reference parse time below is the median of warm raw H2 rows; ratios are paired-analysis per-workload medians.

| Workload | H2/PY | H2/H0 | H2 reference parse ms | Remaining route |
|---|---:|---:|---:|---|
| Debugging_01_06__7b42a0f86b41 | 1.191 | 0.782 | ~81 | merged-cell escape |
| Debugging_05_02__9e6b464d2158 | 1.117 | 0.972 | ~715 | merged-cell escape |
| Financial_Model_08_03__59b98508fd79 | 1.182 | 0.952 | ~2,109 | merged-cell escape |
| Financial_Model_15_03__472e28fbd6e0 | 1.203 | 0.909 | ~332 | workbook-iteration escape |

They pay direct artifact machinery and later normal reference-openpyxl parsing. H2 lowers fixed architecture overhead but cannot erase this double work. The large merged-cell case also has median artifact load ~816 ms. These remain separate candidate semantic-edge experiments; no fallback was removed to make H2 faster.

## OBSERVER COST DECOMPOSITION

Across 22 workloads, medians of each workload's warm H2 component median (nested timers; **do not add them**): argument/run-dir 0.27 ms; exact pre-snapshot 0.30 ms; fork/launch 0.18 ms; post-snapshot/compare 0.45 ms; empty-effect receipt 0.11 ms; external command residual beyond observer's internal receipt timer 2.40 ms. The observer's `wait_target` median is 279.75 ms and is mostly **script-process wall**, not observer computation. Its measured entry-to-receipt median is 280.69 ms. The child bootstrap median is 115.32 ms: config/admission 1.00 ms, discovery 0.24 ms, pre-Runtime work 23.73 ms and Runtime import/install 90.92 ms, with nested measurement boundaries. Child artifact load median is 47.76 ms across workloads, ranging from <1 to >800 ms; source rehash median is 0.51 ms. The post-change Python helper was not invoked on these read-only primary commands. Observer CPU time and kernel scheduling are not separately measured; the timer shows wall categories, not a CPU profile.

## IS THE OBSERVER ACTUALLY THIN?

**Yes on this read-only warm boundary.** It never imports the spreadsheet stack or opens a semantic artifact, and its own measured path outside target wait is low single-digit milliseconds plus an approximately 2.4 ms external residual. H2/H0 improves 22/22, while H2 is near or better than H1 on most scripts. Thinness is conditional: when a workbook changes, H2 invokes a separate frozen Python package-capture/validation helper after the script dies. That is an intended assurance cost and is fully timed in process fixtures, but the 22 speed scripts do not characterize it. The C snapshot prototype also has explicit bounds (1,000 files, 512 MiB per file), scans with `FTW_PHYS`, and is Linux/POSIX-specific. Symlink and very large-package parity with the public capture path, concurrent mutations, observer crash recovery and broader process behavior need a production review. No broad assurance or portability claim follows from this gate.

## PROCESS ASSURANCE VERDICT

`SUPPORTED` **for the preregistered Phase-6 contract and fixtures**: H2 uses a real script process, repaired H1's atexit `__main__` observation, retained post-run capture/receipt after `os._exit` and fatal signal, preserved tested exit/signal/FD/output behavior, passed 20/20 fixture classifications without a contract violation, and passed 22/22 fixed workload correctness gates. The two startup-environment/module-cache differences are documented as observable but acceptable for this experiment. This is not proof of arbitrary Python equivalence or product-ready capture robustness.

## FULL BOUNDARY SPEED VERDICT

`SUPPORTED` **for warm H2 on the exact fixed 22**, under the frozen median/majority/bootstrap rule: H2/PY `0.598`, 15/22 faster, upper bound `0.952`, with genuine child-confirmed reuse and exact scored outputs. Cold H2/PY `1.215` is `NOT SUPPORTED`; N≤5 session support is also `NOT SUPPORTED` under the same upper-bound discipline. This is the first tested assurance-preserving thin-observer warm architecture result, not a claim about the unchanged public RC or representative tasks.

## THIN OBSERVER DECISION

Outcome **A — H2 fast + tested assurance supported**: `THIN_OBSERVER_ARCHITECTURE_CANDIDATE = EARNED`. H2 is a candidate for a later integration checkpoint, **not** an integration or public release decision. The remaining seven warm losers are exactly the four unchanged reference-fallback workloads and three very short Templates. H2's native observer did not reintroduce the heavy-parent tax; cold construction and changed-file assurance economics remain open.

## AGENT INDEPENDENT ARCHITECTURE OPINION

If responsible for the product now, I would retain the **real fresh script interpreter plus a minimal external survivor** as the leading runtime shape, using H2's ownership split as the experimental reference. I would not copy this C code directly into the product: its capture bounds, symlink behavior, POSIX scope, error handling and changed-file helper need explicit engineering. I would keep source/artifact truth and direct serving in the script process, and keep pre/post effect observation outside it. A Python observer may still be attractive for portability or writing-heavy cases, but its startup cost deserves a direct product-shaped comparison before adoption; a persistent supervisor is a separate lifecycle bet.

The most important pre-Phase-6 assumption disproved was that **restoring an external observer necessarily sacrifices most of Phase-5's speed**. In the same-run test H2 was 0.958× H1 warm while repairing the observed process failures. The more important remaining assumption is that the thin read-only observer economics will generalize when changed workbooks require the post-capture helper; this study did not test that performance population.

## NEXT STEP

Keep H2 experimental. The next focused read-side experiment is the unchanged merged-cell fallback on the same fixed scripts, with exact proxy-object semantics and the full H2 command boundary; it targets three of seven remaining warm losers without conflating process ownership. In parallel, design—but do not claim—production-grade external capture for symlink/large-file/changed-package and portability cases before public integration. Preserve the direct-Python comparator, fixed population, cold/warm/session accounting and independent assurance gate. Do not update the RC, README or claim registry from this offline result.
