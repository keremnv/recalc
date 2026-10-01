# Phase 6 architecture decision — before H2 implementation

Status: offline experiment design, **not** product architecture or public claim. Written after inspecting the frozen Phase-1–5 reports/ledgers, Phase-4/5 harnesses, Phase-3 runtime/bootstrap/artifact, and frozen capture code, and **before** writing H2 treatment code or running a scored Phase-6 command. No model calls.

## The observed constraint

On the exact 22, Phase-5 one-interpreter H1 warm H1/H0 was 0.793 (22/22 faster) and H1/PY was 0.633, but it lost post-run capture after `os._exit`/fatal death and changed `__main__` at atexit. The three tiny Templates were PY ~88–89 ms, H0 ~139–140 ms, H1 ~99–100 ms. An observer that adds tens of milliseconds could erase most of their recovered headroom. The external survivor is a **semantic requirement** if abrupt termination must still be observed; a heavy Python observer is not necessarily required.

Diagnostic, **unscored**, fresh-process probes on this host (30 launches each, uncontrolled cache): `/bin/true` median 1.08 ms, `/bin/sh -c :` 1.12 ms, RC-venv `python -c pass` 18.44 ms, RC-venv Python importing `pathlib,json,subprocess` 40.26 ms. These do not predict complete command speed; they show that another fresh Python interpreter consumes roughly the entire 10–12 ms H1 Template gap *before* observation work. A shell is cheap but cannot distinguish `exit(143)` from death by SIGTERM from its usual `wait` status alone.

## Candidate architectures

| Candidate | Startup and artifact ownership | Failure/output/exit/FD semantics | Capture/diagnostic and risk | Decision |
|---|---|---|---|---|
| Thin **fresh Python** supervisor | Still pays Python startup/import; can keep decoder/artifact entirely in child. | Can `subprocess.Popen`/wait and preserve raw bytes if streams inherited; parent can survive child death. Must propagate negative signal by re-signalling itself rather than `sys.exit(-signal)`. Default `close_fds` changes inherited FDs unless configured. | Easiest reuse of frozen capture. Measured bare/stdlib startup is already material to tiny scripts. Good correctness fallback, weak performance discriminator. | Not scored H2. |
| **Tiny native POSIX C** observer | ~native launch scale; child bootstrap owns config/classifier, source SHA, artifact build/reuse/decode, proxy and openpyxl. | `fork/execve` real `python workload.py`; inherited stdout/stderr and non-CLOEXEC FDs; `waitpid` distinguishes exit from signal. Re-raise child signal after receipt for external status fidelity. | Hold pre-XLSX bytes externally; compare post bytes. When unchanged, no Python observer import. When changed, launch frozen Python capture/validation helper *after* child death, including abrupt death. More low-level code and POSIX-only. | **Selected H2.** |
| Persistent Python supervisor | Amortizes import/startup over many invocations, launches fresh child. | Can preserve assurance and script semantics, but client/IPC/service lifecycle are new. | Must charge daemon startup/shutdown over N=1,2,3,5 and handle ownership/crash/restart. Larger product architecture; less discriminating about minimum per-invocation observer. | Defer; candidate if native fresh observer still too costly or portability demands it. |
| Shell/minimal wrapper | Cheap command launch, can run script normally. | Shell `wait` normally folds signalled child and ordinary `128+signal` exit, making exact distinction and forwarding ambiguous. FD behavior depends on shell. | Recursive exact pre/post XLSX bytes and safe changed-package validation require multiple utilities/processes or substantial shell code; error handling brittle. | Reject for scored H2. |
| Pure one-interpreter plus in-process hooks | Fastest observed normal-exit arm. | Cannot run hooks after `os._exit` or fatal process death; runpy changes `__main__`. | Fails current assurance requirement. | H1 remains performance reference only. |
| Python observer plus native fast client / OS watcher | Can amortize Python or move capture out of invocation. | Adds service/process ownership and IPC; watcher may miss exact synchronous post-state or need wait coordination. | Higher complexity than direct native observer. | Defer. |

## Selected boundary

**H2 is a small compiled C observer that starts one real fresh Python script interpreter** using `execve(python, [python, workload.py], env)`. It does not import Python/openpyxl, parse OOXML, classify source, hash source for artifact identity, or decode artifacts. The observer:

1. validates bounded CLI paths and creates its own run directory;
2. snapshots exact bytes of all `.xlsx` files under the workdir using the frozen capture discovery rule (recursive, skip names containing `.tmp`);
3. writes a compact immutable launch context and starts the normal Python script process with a guarded Phase-6 `sitecustomize` on `PYTHONPATH`;
4. waits for the target, preserving whether it exited normally or by signal and inheriting its stdout/stderr directly;
5. takes a post-snapshot and compares exact bytes, including created/deleted files;
6. if package state changed, invokes a separate **post-termination capture helper** using the unchanged frozen `capture_wrap_timed` on the saved pre bytes; this helper is charged in the command timer and runs even after `os._exit` or fatal signal;
7. writes a compact receipt/profile, then returns the exact normal exit code or re-raises the signal against itself after persisting receipt.

The script's own interpreter owns unchanged config/classifier, workbook discovery, whole-file SHA, Phase-4 integrity/build gate, full `safe_artifact.load` before direct serving, frozen Runtime/proxy/fallback and runtime events. The child bootstrap writes its prepared artifact status before executing user source. A final `REUSED` witness still requires actual direct-serving event after full semantic decode; abrupt death may leave contact unknown, never falsely successful. The old parent→child source recheck is retained through frozen Runtime code for this experiment. No observer semantic artifact materialization occurs.

Pre/post capture stays external. Exact byte equality lets an unchanged workbook avoid a Python post helper; the frozen capture routine would also emit no delta for byte-equal files. On changed files, the helper receives the observer's **actual pre bytes** and executes frozen delta/validation. This is a scoped implementation of the same mechanical effect contract, not task correctness. The observer cannot promise perfect observation if it itself is killed, the host crashes, or the script races with another actor; the same limitation applies to H0.

## Expected semantic advantage and risk

A normal script interpreter naturally supplies direct Python `__main__`, loader/package/spec, argv/path, script atexit, traceback, signal and subprocess behavior. The observer survives child death and captures package effects after it. `waitpid` retains signal versus ordinary exit distinction; after receipt it re-signals itself, preserving the platform-visible negative signal result. Inherited stdout/stderr are not buffered by an observer; extra descriptors follow normal `fork/exec` inheritance unless marked close-on-exec.

The main risks are C snapshot fidelity, path/symlink/FD handling, source/workbook mutation during bootstrap, event loss on abrupt child death, post-helper work on changed packages, POSIX portability and cold construction in the script startup. All must be tested before scored timing. The H2 performance hypothesis is **not** guaranteed: child-side admission/build plus `sitecustomize` may relocate work and make warm startup too expensive even if the observer itself is cheap.

## Why this experiment now

Merged-cell repair addresses three fallback losers and leaves the fixed overhead on short scripts unexplained. H2 tests whether the product can **keep Phase-5's fast real-script path and regain Phase-4's external assurance**. A positive or negative result decides process ownership for every admitted workload. It has greater current architecture decision value than another local proxy change. No favorable timing is assumed.
