# Security / resource-boundary audit

Bounded-behavior review, not a formal certification. Threat model: a technical
user running their own (possibly buggy, possibly adversarial-workbook-touching)
scripts locally. The product is NOT a sandbox (documented): scripts run with
user permissions.

| Category | Verdict | Evidence / notes |
|---|---|---|
| XLSX ZIP expansion (direct path) | SUFFICIENT FOR TECHNICAL PREVIEW | `direct.py:284-287`: ≤10,000 members, ≤512 MiB declared expansion, ≤256 MiB per XML part. Rejection → reference fallback, never a veto. |
| Artifact decompression | SUFFICIENT FOR TECHNICAL PREVIEW | `artifact.py:224-230`: bounded `decompress(..., MAX+1)`, `eof`/`unused_data`/`unconsumed_tail` checks, payload-hash match. 256 MiB compressed / 512 MiB uncompressed ceilings. |
| XML parsing (direct) | SUFFICIENT FOR TECHNICAL PREVIEW | lxml with `resolve_entities=False, no_network=True, huge_tree=False`, both in `_xml_part` and the `iterparse` loop. |
| XML parsing (capture path) | NEEDS HARDENING BEFORE EXTERNAL RELEASE (low priority) | `_frozen/delta.py` + `validate.py` use stdlib `xml.etree` on workbook parts. ET doesn't fetch external entities, but billion-laughs-style entity expansion is a known stdlib weakness. Capture processes the USER'S OWN post-state bytes (not remote input), so exploitability is low — but a bounds note or defusedxml-style guard belongs on the pre-release list. |
| Path traversal | SUFFICIENT FOR TECHNICAL PREVIEW | Observer: `nftw` rooted + prefix check (`observer.c:69`); rel names with `\n`/`\t` rejected; `realpath` on script/workdir. Runner: receipt reader confines run dirs to the cache's `runs/` (`runner.py:90`). Bootstrap writes only into the observer-created run dir. |
| Symlinks | SUFFICIENT FOR TECHNICAL PREVIEW | `FTW_PHYS` (no follow) + cache/run roots + read-engine dir symlink rejection + artifact/sidecar symlink rejection in validation. |
| Cache permissions | SUFFICIENT FOR TECHNICAL PREVIEW | `0700` creation + ownership check + `chmod` repair in both launcher and runner; lock files `0600`. |
| Temp/run directories | SUFFICIENT FOR TECHNICAL PREVIEW | `mkdtemp` run dirs; `mkstemp` + `os.replace` publication; `LIBRECALC_RECEIPT_POINTER` is a uuid-named private file. No `/tmp` shared paths. |
| Executable invocation | SUFFICIENT FOR TECHNICAL PREVIEW | Observer/helper/python paths are exact (no `PATH` search, no shell). Launcher resolves `python`/`python3` beside itself only. Helper argv is fixed-shape. No `shell=True` anywhere in product code. |
| Environment inheritance | SUFFICIENT FOR TECHNICAL PREVIEW | Full inherit (documented: FD/env parity is tested behavior) minus `CANDIDATE_A_*`, run-context, and effective-config keys; helper gets `LIBRECALC_RUN_CONTEXT` unset. PYTHONPATH is prepended, not replaced. |
| Concurrent publication | SUFFICIENT FOR TECHNICAL PREVIEW | Per-key `flock` + revalidate-under-lock + temp+fsync+atomic rename; readers accept only complete verified generations. Local-filesystem scope only. |
| Snapshot limits | SUFFICIENT FOR TECHNICAL PREVIEW | 1,000 files / 512 MiB aggregate, enforced before AND during read (`observer.c:52,71,85`); single-file 512 MiB cap in `read_bytes`. Exceeding fails loudly (125), never truncates silently. |
| Artifact content limits | SUFFICIENT FOR TECHNICAL PREVIEW | 512 sheets, 10M cells, 2M-char scalars, typed-value schema validation on both encode and decode paths. No executable deserialization (JSON/zlib only). |
| Resource exhaustion (no quota) | NEEDS HARDENING BEFORE EXTERNAL RELEASE | No global cache quota (see cache lifecycle audit). Per-artifact bounds cap single-run damage; accumulation over months is the gap. Operational, not exploitable remotely. |
| pyc/cache poisoning | SUFFICIENT FOR TECHNICAL PREVIEW | Stale `__pycache__` in the source tree is a hygiene wart, not a shipped risk (wheels exclude it; verify at release build). |

No BLOCKING ISSUE found. Two NEEDS-HARDENING items, both low-severity and both
scheduled in pre-release cleanup: (1) capture-path XML entity-expansion note/
guard; (2) cache quota or documented retention story. Neither makes initial
external use unsafe for a technical preview audience.
