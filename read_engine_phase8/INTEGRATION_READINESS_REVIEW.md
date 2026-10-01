# Phase 8 independent integration-readiness review

Status: **architecture discovery / integration audit, not an accepted product contract**. Reviewed before any Phase-8 scored timing. The public product and frozen Phase 1–7 implementations were not changed. Authority: Phase 1–7 reports and raw ledgers; `read_engine_phase6/observer.c`, bootstrap and capture helper; `read_engine_phase7/certificate.py` and merge route; frozen Phase-3 runtime/artifact; frozen classifier and capture. Git HEAD at review: `254a5c14fa74fc3534493c565de84b38e7317175`; the working tree contains pre-existing research changes, so the file hashes in the validation spec are the operative code identity.

## Independent answer

I would retain the **one real Python script interpreter plus an external survivor** architecture, transparent guarded interposition, conservative source hashing, direct OOXML narrow representation, and reference fallback. I would reengineer the native observer, bootstrap, artifact/cache boundary, admission proof, capture and diagnostics before shipping. I would not copy the research harness into production. The current Phase-7 merged-cell certificate is **unsound** for its stated fail-closed property; this is a concrete correctness blocker, not a performance concern.

## Component disposition

| Component | Disposition | Evidence / required work |
|---|---|---|
| External observer plus real script interpreter | INTEGRATE CONCEPTUALLY | Phase 6 preserves tested abnormal-exit observation and real `__main__` semantics with low read-only observer overhead. |
| `observer.c` exact implementation | INTEGRATE WITH REENGINEERING | POSIX-only; bounded snapshots, no durable receipt, weak helper-failure propagation, symlink/race/error cases unresolved. |
| Whole-byte pre/post observer snapshot | INTEGRATE WITH REENGINEERING | External capture after `os._exit` and signal was shown; production must define scope, bounds, symlinks, concurrent mutation and failure handling. |
| Post-change Python capture helper | NOT YET EARNED | Invoked only for changed bytes; fixed read benchmarks did not time changed-file economics. It rereads post state and rewrites committed bytes. |
| Guarded `sitecustomize` bootstrap | INTEGRATE WITH REENGINEERING | Real unchanged script interface is useful. Current context text, absolute experiment paths, `PYTHONPATH` override, fail-open exception handling and research telemetry need product ownership. |
| Phase-3 runtime/interposition and proxies | INTEGRATE WITH REENGINEERING | Exact on fixed narrow cases, with normal reference fallback. Object identity, direct `type/repr`, parent identity and arbitrary Python remain outside demonstrated equivalence. |
| JSONZ_MEMORY_V1 typed artifact concept | INTEGRATE WITH REENGINEERING | No executable deserializer, SHA/version binding, bounded compressed/uncompressed payload and atomic publication. Its Phase-1 imports in a warm child, large resource limits and cache ownership need production work. The current *format* need not be replaced merely for speed. |
| Source SHA and child recheck | INTEGRATE CONCEPTUALLY | Strong identity and load-time race check; does not lock source against later concurrent mutation. |
| Frozen whole-script classifier | INTEGRATE WITH REENGINEERING | It remains a narrow admission screen, not a complete proof that all reachable Python observations are proxy-safe. |
| Phase-7 merged observation certificate | **REJECT as currently written** | It certifies zero syntactic `.cell` calls as safe even when covered-cell objects are obtained via `ws.__getattribute__("cell")` or `ws.__getitem__`. A real admitted fixture produced `MergedCell` in PY and `ProxyCell` in H1. |
| Direct OOXML `MemoryBook` semantics | INTEGRATE CONCEPTUALLY | Exact frozen contract and typed values were demonstrated; decoder implementation needs hostile-XLSX resource controls and a runtime/build module split. |
| Reference openpyxl fallback | INTEGRATE CONCEPTUALLY | Required for richer operations and uncertain semantics; transition/object-identity limits must be documented and guarded. |
| JSONL runtime events, profiling and many research receipts | RESEARCH-ONLY | Preserve a compact product receipt; the per-phase experimental ledgers are not product requirements. |
| Run UUID directory and `last_run.json` | INTEGRATE WITH REENGINEERING | Separate per-invocation receipt from persistent cache; make durable/atomic where assurance requires it, define cleanup and concurrent ownership. |
| Cross-platform observer support | NOT YET EARNED | Linux/POSIX tested only. Windows requires a distinct process/wait/snapshot path; macOS requires validation, not inference. |

## Confirmed certificate falsifier and stop decision

The deterministic diagnostic source [indirect_cell.py](certificate_review/indirect_cell.py) uses an existing merged child `B1` in a tiny XLSX. Frozen admission returned `A1_ADMIT`; Phase-7 certificate returned `certified=true`, `cell_calls=0`. With ordinary Python/openpyxl the script printed `MergedCell <MergedCell 'Sheet'.B1>`. With the unchanged Phase-7 observer/bootstrap/runtime it printed `ProxyCell <read_engine_phase3.runtime.ProxyCell object at ...>`. Events included `direct_served_load`, `merged_child_contact`, `merged_child_direct`; the artifact was built and the observer completed. The complete diagnostic witness is [indirect_cell_result.json](certificate_review/indirect_cell_result.json). The same static false positive also arises from `ws.__getitem__("B1")`, which invokes the proxy's `.cell()` internally.

The certificate proves only the shape of **literal** AST `.cell` attribute nodes, but concludes safety for all merged-child paths. That implication is false. This is a new counterexample outside the fixed 22; it does not retroactively change their measured outputs or timings. It prevents product integration and triggers the user's explicit Phase-8 rule: **do not score broader performance while a blocking correctness issue remains**. Representative and changed-file timing ledgers therefore remain empty. There is no Phase-8 product speed verdict.

## Native observer production concern matrix

| Concern | Classification | Reason |
|---|---|---|
| Normal/`sys.exit`/signal/`os._exit` external survival on tested Linux fixtures | PROVEN | Phase-6 process suite and fixed 22. |
| Real script `__main__`, argv/path, inherited streams and tested FDs | PROVEN | Phase-6 fixtures, with documented environment/module differences. |
| Linux/POSIX fork/exec/wait path | PROVEN | Current host only. |
| macOS behavior | NEEDS EXPERIMENT | POSIX resemblance is insufficient for product packaging/signal/capture claims. |
| Windows behavior | ARCHITECTURAL RISK | `nftw`, fork, POSIX signals and wait status are not portable. |
| 512 MiB per XLSX, 1000-file cap, full-memory snapshots | NEEDS EXPERIMENT | Hard stop/bounds are explicit; aggregate memory can be much larger. |
| Symlinked XLSX | ARCHITECTURAL RISK | `FTW_PHYS` excludes symlink targets while frozen Python `rglob`/`read_bytes` can follow file symlinks; capture scope can diverge. |
| Concurrent rename/mutation and TOCTOU | ARCHITECTURAL RISK | Pre/post reads are not atomic filesystem transactions. |
| Permissions, locked/deleted files and disk full | NEEDS EXPERIMENT | `die(125)` often aborts without final receipt; policy not specified. |
| Path encodings, tab/newline, long paths | STRAIGHTFORWARD ENGINEERING | Current text context/TSV rejects or cannot represent some legal names. |
| Observer crash, power loss, receipt durability | ARCHITECTURAL RISK | Receipt/`last_run` are not fsynced/atomically published; no external survivor for observer death. |
| Capture helper failure propagation | ARCHITECTURAL RISK | `capture_helper_exit` is written, but observer ultimately returns the target status, including zero after failed capture. A caller must inspect receipt to notice assurance failure. |
| Concurrent artifact publication | NEEDS EXPERIMENT | Atomic individual files and hash checks exist, but no lock/lease and artifact + sidecar are published separately. |
| Run cleanup and disk retention | STRAIGHTFORWARD ENGINEERING | Per-run directories have no production retention policy. |

## Changed-file and economic readiness

The read-only fixed 22 do not exercise post-change helper startup, package delta, rewrite, validation or replay. Phase-6 abrupt-exit fixtures establish that the observer *can* invoke capture after script death, not its product cost across ordinary writes. All 30 archived representative scripts are read-oriented normalized scripts (`.save(` absent), so the intended five changed-file fixtures are separately frozen in the validation spec. Their timing and assurance behavior are **UNMEASURED in Phase 8** because the semantic stop occurred first. Cold remains 1.194 on the contact-selected Phase-7 view; N=2/3/5 support on that view does not establish a product cache lifetime or broad prevalence.

## Product boundaries and proposed ownership

Conceptually place immutable derived artifacts in a user-scoped cache keyed by source SHA plus decoder/contract/format versions, separate from per-run receipts and from the project tree. Specify permissions, storage quota/eviction, concurrent builders and version invalidation before integration. Keep source and artifact validation in the script process; keep pre/post effect observation and final receipt in the external survivor. A minimal receipt needs execution identity/status, artifact built/reused/contact, fallback reason, capture status and validation failure; raw research event streams are unnecessary by default. A package build must decide platform-specific observer artifacts, source-distribution compilation, executable discovery, bootstrap scope and version coupling. No project/package naming change follows from this review.

The next required experiment is semantic, not performance: make the merged-child route fail closed for indirect method access, worksheet dunder calls, aliasing and other object-escape forms, then rerun deterministic adversarial fixtures and frozen 22 correctness before restarting the preregistered 30-script and changed-file validation. Do not broaden the read contract or tune admission for timing.
