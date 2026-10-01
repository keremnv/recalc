# Read-engine Phase 1: direct OOXML prototype

**Status:** offline experiment; no product change or public speed claim. The final evidence is the v5 run in [raw correctness](read_engine_phase1/raw_correctness.jsonl), [raw timings](read_engine_phase1/raw_timings.jsonl), [profile](read_engine_phase1/profile.json), and [paired analysis](read_engine_phase1/analysis.json). Prototype code is confined to [read_engine_phase1](read_engine_phase1/). No model calls were made; `src/librecalc_agent/`, RC behavior, README, claim registry, and frozen research records were not edited for this experiment.

The original [preregistration](read_engine_phase1/PREREGISTERED_SPEC.md) was written and hashed before prototype implementation or benchmark execution (SHA-256 `9b95f912318a27e2c9bc2114b9f8495e9f3183e71339afa790c9d69a8d4ed1af`). The frozen [population](read_engine_phase1/population.json) has SHA-256 `6492d1cbc2163ea252c0d34cf346171d332a923bd5f05fc1fd54c3e851097afa`. The active [v5 amendment](read_engine_phase1/PREREGISTERED_SPEC_v5.md) was hashed before its implementation changes and run (SHA-256 `70a0bffe9402a79907aa63bdc7ae3188b758c4316cc79b91914ca5902af8a869`). [Implementation identity](read_engine_phase1/implementation_identity.json) pins the v5 code files. The repository HEAD was `254a5c14fa74fc3534493c565de84b38e7317175` (tree `dc7ae5512e4d47e56663564ad72b7a18600bbf5c`). Python 3.13.12, openpyxl 3.1.5, lxml 6.1.3, SQLite 3.51.1, Linux 7.0.0, and an Intel Core Ultra 5 125H were used with one benchmark worker. No disk-cache flush or CPU pinning was performed.

The version history is part of the evidence, not a workload search: v2 fixed cross-filesystem staging before any result row; v3 recorded a normal-openpyxl oracle failure on one frozen workbook; v4 removed per-cell profiler calls that unfairly charged millions of timer operations to R2/R3; v5 made R3's SQLite artifact self-contained after a complete v4 audit showed that sheet metadata had remained in builder memory. Each change was documented and hashed before rerun. Earlier partial and complete ledgers remain under versioned names. Only the fresh v5 ledgers support the results below. A server restart interrupted an early v4 index-ready attempt; its partial rows were archived and that phase was rerun whole without a code or protocol change.

Ratios below are **treatment time / comparator time** on the same workbook or trace; smaller is faster. Each construction ratio uses a per-workbook median; each index-ready ratio uses a per-trace median of two repetitions. Geometric-mean intervals are 2,000-resample percentile bootstrap intervals over those paired identities, conditional on this fixed population. The 51 traces come from only seven snapshots, so trace intervals do not imply independent-workbook generalization. “First observation” means cold-ish ordering only; it is **not** cold-disk measurement.

## SEMANTIC CONTRACT

The reference is normal `openpyxl.load_workbook(path, data_only=False)`. The frozen surface is ordered `sheetnames`, literal sheet lookup, worksheet `max_row`, `max_column`, calculated `dimensions`, literal coordinate lookup, integer `.cell(row,column)`, and cell `.value`/`.data_type`. Comparison retains Python scalar type and value, date/time type, exact formula text, and array/data-table formula object attributes. It checks exception class/message where an operation fails. Handle creation must succeed and later reads use the returned handle; rich object identity is outside the contract. Writes, styles, ranges, arbitrary iteration, charts, tables, macros, and other workbook APIs are outside it.

R0 is normal openpyxl. R1 is the frozen current read-only-openpyxl → existing SQLite index → proxy path, with one isolated workbook and actual publication. R2 directly decodes ZIP/OOXML into in-memory contract state. R3 uses the same decoder but persists cells, sheet order/names, bounds, and merged ranges in a minimal SQLite artifact; a fresh read-only connection reconstructs the contract state from that artifact. R2/R3 do not build anchors, temporal tables, search structures, or dependencies.

## FROZEN POPULATION

The construction corpus is 39 unique whole-file SHA-256 hashes: 14 unique final-RC eligible workbooks plus 30 representative-checkpoint task workbooks, with five shared hashes. Their full hashes, family/task provenance, paths, byte sizes, sheet counts, and XML nonempty counts are frozen in [population.json](read_engine_phase1/population.json) and the preregistration. The files total 31,188,723 source bytes and 1,050,145 XML nonempty `<c>` elements; median source size is 88,645 bytes. None was removed after results were observed.

The index-ready and reuse corpus is all 51 archived hardened Candidate-A exact contact traces, in original order, over seven snapshot hashes. It includes the original 135,989 recorded operations: 69,256 `.cell` acquisitions, 65,345 `.value` reads, 1,188 `max_column` reads, 69 sheet-name reads, 69 sheet lookups, 10 `max_row` reads, and 52 load markers. The replay acquires a workbook once per trace and skips subsequent load markers, as frozen in the specification. These traces were historically selected for acceleration contact; they are not a representative product-invocation population.

## DIRECT OOXML FEASIBILITY

The direct decoder reads workbook order/relationships, worksheet XML, shared and inline strings, numeric/boolean/error cells, style-dependent date/time values, sparse bounds, merged ranges, and normal/shared/array/data-table formulas. A treatment-blind XML [edge census](read_engine_phase1/edge_census.json) found 109,860 normal-formula elements, 604,697 shared-formula elements, 65,749 array-formula elements, 10 data-table formula elements, and 1,018 merge ranges across the 39 packages. These are package-shape counts, including the workbook with the failed reference oracle; they are not separate semantic pass counts.

The treatment decoder opens XLSX ZIP/XML directly and never calls `openpyxl.load_workbook`. It does still import openpyxl date/number-format helpers, formula translation, and formula value classes to reproduce reference Python semantics. Thus this phase demonstrates **independence from openpyxl workbook parsing**, not independence from every openpyxl utility. Replacing those helpers without widening the contract remains unproved.

## CORRECTNESS RESULTS

All 51 traces replayed exactly in each of R0/R1/R2/R3: 204 exact variant rows and zero trace errors or mismatches. R2 and R3 also matched every checked nonempty reference cell in the 38 corpus workbooks that normal openpyxl could load: **1,022,280 cells per direct variant**, with sheet order and bounds exact. There were zero recorded mismatches in every required taxonomy category: shared/inline string, number, boolean, date/time, error, normal formula, array/shared formula, merged cell, bounds/dimension, and other. Empty-cell `.data_type` was exercised only where a frozen trace requested it, not exhaustively across every coordinate.

The 39th workbook, SHA-256 `71233a0b02e0680361836392ca41c567aae657ce91dd24c4248f273f459fd53c` (`Financial_Model:06_01`), has an unbound `dc` prefix on `<dc:creator>` in `docProps/core.xml`. Normal openpyxl raises `XMLSyntaxError` before returning a workbook; R1's read-only parse also fails. R2/R3 construct from its worksheet parts, but there is no reference oracle for a full-cell semantic comparison. It remains in construction timing and the denominator. **Full-corpus semantic exactness and a corpus-wide speed claim are unresolved.** The 51-trace mechanism result has a complete reference oracle and passes its own correctness gate.

The direct arms were guarded during construction and serving by a sentinel replacing both public and reader-module `openpyxl.load_workbook`; no call escaped. Code inspection confirms ZIP/XML decoding. R3's fresh-process read-only probe exercised representative `sheetnames`, first-sheet bounds, and cell value/type reads from all **39/39** artifacts, with only the artifact path passed to the child. A separate synthetic check removed the source workbook before fresh-process R3 reads. R1's basic read-only SQLite attach succeeded on its 38 successful artifacts.

## CONSTRUCTION COST

The construction timer starts just before builder invocation and stops when the representation is ready. It includes R1 hashing, read-only openpyxl parse, traversal, SQLite population, backup/publication and manifest work; R2 direct decoding; and R3 direct decoding plus self-contained SQLite creation/publication. Input-copy staging, imports, and cross-process probes are outside the timer. R0 ends after a normal workbook load.

| Arm | Median first observation | Median repeated observation | Successful workbooks |
|---|---:|---:|---:|
| R0 normal openpyxl | 0.157 s | 0.150 s | 38/39 |
| R1 current index | 0.137 s | 0.139 s | 38/39 |
| R2 direct memory | 0.060 s | 0.054 s | 39/39 |
| R3 direct SQLite | 0.085 s | 0.086 s | 39/39 |

These are descriptive medians across different workbook sizes; savings use **paired ratios**. In the repeated observations, R2/R1 had median ratio **0.445**, geometric mean 0.494 (95% bootstrap interval 0.407–0.596), range 0.220–1.262, and 32/6/0 faster/slower/tied among 38 pairs. R3/R1 had median **0.642**, geometric mean 0.713 (0.621–0.812), range 0.412–1.292, and 25/13/0. R3/R2 across all 39 hashes had median **1.435**, geometric mean 1.431 (1.339–1.529), range 0.998–2.070, and 1/38/0. R2/R0 had median 0.552 (38/0/0); R3/R0 had median 0.791 (29/9/0). All 39 hashes are retained; R0/R1 lack three successful rows each on the one oracle-failing workbook.

For the first observation, R2/R1 had median ratio 0.487, geometric mean 0.502 (95% interval 0.411–0.611), range 0.160–1.253, and 32/6/0 faster/slower/tied; R3/R1 had median 0.653, geometric mean 0.697 (0.601–0.806), range 0.288–1.259, and 25/13/0. R2 and R3 exceed the preregistered 10% median construction-difference threshold versus R1, so stop rule 2 did not fire. These comparisons do not measure the public RC launcher, child process, capture, or validation.

## INDEX-READY COST

R1/R2/R3 were constructed once per trace **outside** this timer. Each timed repetition starts before backend acquisition/attach and stops after trace operations and release. R0 has no derived state: its normal openpyxl load is inside the timer. The randomized two-repetition design yielded 408 error-free rows.

| Arm | Median acquisition | Median trace operations | Median total | Paired total ratio to R0: median; geometric mean (95% CI); faster/slower/tied |
|---|---:|---:|---:|---|
| R0 | 4.554 s | 0.000676 s | 4.554 s | reference |
| R1 | 2.143 s | 0.0412 s | 2.196 s | 0.505; 0.534 (0.499–0.575); 49/2/0 |
| R2 | 0.0000016 s | 0.000883 s | 0.000885 s | 0.000237; 0.000398 (0.000199–0.000768); 51/0/0 |
| R3 | 0.000497 s | 0.00251 s | 0.00293 s | 0.000863; 0.00146 (0.000773–0.00265); 51/0/0 |

The paired total-ratio ranges are R1 0.383–1.106, R2 0.00000583–0.0711, and R3 0.0000490–0.1945. The large total reductions mainly avoid **normal reference workbook parsing on acquisition**. They do not mean every individual cell lookup is faster. Paired operation-only median ratios to R0 are R1 **27.8** (1/50 faster/slower), R2 **1.41** (15/36), and R3 **3.97** (7/44). R1's acquisition still performs workbook freshness hashes, complete raw worksheet metadata XML parsing, and SQLite attach; R2 retains an already-built Python object; R3 opens SQLite and reconstructs persisted metadata. R2 and R3 do not perform product-level freshness checks. Their microsecond index-ready totals therefore cannot be read as product invocation speed.

The historical hardened exact-trace report measured a **44.46% median reduction** with R1-like derived state already prepared and 50/51 positive traces. This v5 R1 trace boundary gives a **49.54% median paired reduction** and 49/51 positive traces. Different runs vary, but the sign and approximate scale reproduce on the same archived population at a comparable construction-excluded boundary. Neither figure includes the construction charged below.

## FIRST-USE COST

First use is measured, not inferred: construct R1/R2/R3 once and execute one real trace; R0 executes one independent normal openpyxl load and trace. It is a **mechanism** endpoint. It excludes CLI, child-process startup, sitecustomize, effect capture, validation, and telemetry.

| Arm | Median observed total | Paired ratio to R0: median; geometric mean (95% CI) | Faster/slower/tied |
|---|---:|---|---:|
| R0 | 2.724 s | reference | — |
| R1 | 4.223 s | 1.524; 1.517 (1.442–1.596) | 1/50/0 |
| R2 | 2.322 s | 0.844; 0.844 (0.801–0.886) | 45/6/0 |
| R3 | 3.113 s | 1.129; 1.063 (1.014–1.114) | 17/34/0 |

The paired ratio ranges are R1 0.978–3.114, R2 0.456–1.283, and R3 0.672–1.423. R2's first-use result uses in-process memory with no persistent artifact. R3's first use includes a complete reusable SQLite artifact. These fixed traces were selected for read contact; neither result predicts the final RC's whole-script cold population.

## REUSE ECONOMICS

Each arm executed the same trace ten times, acquiring a fresh backend view on each execution; R0 performed ten independent normal loads. Derived arms paid construction once. The observed cumulative prefixes are below as **median paired ratio to R0** over 51 traces. A ratio below one is faster on that measured horizon.

| Observed N | R1 | R2 | R3 |
|---:|---:|---:|---:|
| 1 | 1.524 | 0.844 | 1.129 |
| 2 | 0.937 | 0.403 | 0.547 |
| 3 | 0.752 | 0.265 | 0.364 |
| 5 | 0.603 | 0.160 | 0.216 |
| 10 | 0.490 | 0.0809 | 0.109 |

At N=10, geometric mean ratios (95% intervals) were R1 0.537 (0.503–0.577), R2 0.0831 (0.0795–0.0870), and R3 0.1085 (0.1014–0.1167). Faster/slower/tied counts were 48/3/0, 51/0/0, and 51/0/0, respectively. R1's first observed break-even occurred at N=1/2/3/10 for 1/35/11/1 traces and did not occur by N=10 for three. R2 first broke even at N=1 for 45 traces and N=2 for six. R3 first broke even at N=1 for 17 and N=2 for 34. These are observed prefixes only; no break-even beyond ten is claimed. Repeated execution is within this offline benchmark session, not a measured public warm-RC invocation.

## REPRESENTATION SIZE

| Representation | Median footprint | Range | Median artifact/source ratio | Fresh-process read-only use |
|---|---:|---:|---:|---|
| R1 current SQLite | 507,904 B | 28,672–34,861,056 B | 5.74× | Basic SQLite attach on 38/38 successful artifacts |
| R2 Python memory | ~464,600 B | ~9,319–25,826,258 B | n/a | No persistent artifact |
| R3 minimal SQLite | 176,128 B | 16,384–9,834,496 B | 2.35× | Representative contract reads on 39/39 artifacts |

R2 memory is a recursive `getsizeof` estimate with shared-object deduplication; it is **approximate** and can omit interpreter/native or imported-object costs. Artifact bytes are actual files. R3 persists sheet metadata and cell payloads in one SQLite file; no source workbook is required for the tested read-only attach.

## BOTTLENECK DECOMPOSITION

The [profile](read_engine_phase1/profile.json) contains nested medians, which must not be added to independently reported median totals. R1's `ensure_s` median was 0.137 s; it contains initial/second hashing, read-only openpyxl Parse A, traversal/materialization, SQLite insertion/index work, and other builder work. Those subcomponents are individually **UNMEASURED** in this frozen arm. R1 backup/publication had a measured median 0.000768 s. Manifest work is inside construction total but separately **UNMEASURED**.

R2's median direct decode was 0.0554 s; its worksheet XML interval was 0.0519 s, containing XML parse, value decoding, and Python insertion. Shared strings, styles/date metadata, and workbook relationships had medians 0.000231, 0.00195, and 0.000470 s. R3's median decode was 0.0837 s, with 0.0807 s in worksheet XML plus value decoding and SQLite insertion/typed serialization. Its measured sheet-metadata insert, SQLite commit, and atomic publication medians were 0.000183, 0.000261, and 0.0000404 s. ZIP open itself is included in total but **UNMEASURED** separately; `zip_open_list_s` measures listing after opening. Per-cell decode and insertion timings were deliberately removed because their profiler overhead distorted construction; those individual components are **UNMEASURED**. The paired R3/R2 construction difference isolates their combined representation/storage effect, not an exact SQLite-insertion stopwatch value.

## OPENPYXL CONSTRUCTION DEPENDENCY

R1 construction invokes `openpyxl.load_workbook(..., read_only=True, data_only=False)` before traversing cells into the inherited schema. R0 invokes normal `load_workbook` inside each reference execution. R2/R3 construction and serving invoke neither; the sentinel guarded both public and reader-module loaders in correctness and timing, and no invocation occurred. This answers the Phase-1 parse question affirmatively: the narrow read representation can be built from ZIP/XML without paying openpyxl's workbook parse on these fixed traces and 38 oracle-loadable corpus books.

It does **not** yet establish a library-free semantic engine: R2/R3 use openpyxl helpers/classes for date conversion, date-format recognition, shared-formula translation, and array/data-table formula observables. Those are named dependencies, not hidden parsing. The malformed corpus workbook demonstrates a boundary: direct construction succeeds from worksheet parts, but reference parity cannot be asserted because the oracle fails on an unrelated package part.

## WHAT SQLITE COSTS

For the same decoder and 39 workbook hashes, self-contained R3 construction cost a median **1.435×** R2 construction (geometric mean 1.431, 95% interval 1.339–1.529; 38 slower, one faster). At index-ready service, R3/R2 median paired total ratio was **3.36×**. Median R3 acquisition was 0.497 ms versus R2's in-memory object acquisition of about 1.6 µs; R3 must open SQLite and reconstruct sheet metadata. Median R3 trace operations were 2.51 ms versus R2's 0.883 ms. R3 buys a reusable, read-only, self-contained cross-process artifact; R2 does not persist state. SQLite inserts and JSON typed-value decoding are within these measured totals, but their individual contribution was not isolated. These numbers describe this simple schema and one-query-per-cell prototype, not a lower bound on SQLite.

## WHAT DIRECT DECODING CHANGES

Direct OOXML removes R1's openpyxl Parse A and its product-unused anchor/temporal representation from construction. On the 38 paired construction books, both direct variants built faster than R1 by median ratio. On the 51 contact-selected traces, R2's measured mechanism first use was faster on 45/51 and R3's on 17/51; all R3 traces were faster by the second real execution. R2's index-ready advantage includes retaining Python state; R3's includes reusable state but still omits product freshness and lifecycle. The strongest explanation of the historical-versus-RC sign difference remains accounting: index-ready savings can coexist with cold invocation losses when construction and product setup are charged every time.

| Arm | Correctness evidence | Construction/serving character | Persistence and semantic edge surface |
|---|---|---|---|
| R0 | Oracle where loadable | Mature normal parse on every independent execution | No derived state; full openpyxl API outside this benchmark |
| R1 | 51/51 exact traces | Inherited broad index and repeated metadata XML/freshness on acquisition | Published SQLite; existing fallback behavior and openpyxl Parse A |
| R2 | 51/51 traces; 38/38 loadable full-cell books | Fast direct build; object-ready reads | Process memory only; direct date/formula semantics rely on openpyxl helpers |
| R3 | Same semantic gate as R2 | Direct build plus minimal SQLite; artifact-backed attach | Self-contained read-only artifact; typed payload and metadata schema add complexity |

No variant is selected as product architecture by this report.

## DOES A NARROW INDEPENDENT READ ENGINE LOOK VIABLE?

**Parse-independent narrow serving looks viable on the tested surface.** The direct variants passed every archived exact trace and every checked cell where a normal openpyxl oracle existed; R2 had favorable measured mechanism first-use economics on most of the fixed contact traces. R3 demonstrates that a complete persistent artifact can be built and reopened in another process, with a measurable storage/attach cost and a first-use tradeoff. Full semantic exactness on all 39 workbooks remains unproven because one frozen input defeats the reference oracle. Full independence from openpyxl utilities, broader read APIs, freshness, product lifecycle, and public product speed are also unproven. The results neither replace nor negate the final RC cold-product finding.

## NEXT DISCRIMINATING EXPERIMENT

Pre-register a fixed-identity, separate-process session test that charges source freshness verification, persistent artifact acquisition, and N real invocations for a self-contained R3 artifact and a persisted R2-like representation on the **same** 51 traces and 39 workbook hashes. Keep the malformed-oracle workbook explicit and resolve its reference status separately. This would test whether representation choice and cross-invocation lifetime preserve the Phase-1 mechanism advantage at a complete reusable-session boundary, without selecting new favorable workloads or changing the public RC.
