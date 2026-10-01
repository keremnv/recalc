# Platform feasibility: Linux scope + macOS + Windows audits

## Linux release scope (initial target)

Audited Linux-specific architecture:

| Area | Finding |
|---|---|
| glibc | Binaries dynamically linked (`/lib64/ld-linux-x86-64.so.2`); build host glibc 2.43 (very new). No manylinux baseline; wheel tag is local `linux_x86_64` via sysconfig. Older distros may refuse to run the binaries. |
| Compiler/runtime deps | Build needs `cc`; install from wheel needs none. libc-only native code (no libssl/libffi/etc.). |
| Wheel compatibility | `py3-none-<local platetag>`, `pure_python=False`. NOT manylinux. Single-host artifact. |
| Kernel-specific | `nftw`, `fork/exec/waitpid`, `sigaction`, `mkdtemp`, `realpath` — all POSIX, no io_uring/eBPF/namespaces. |
| `/proc` / Linux-only APIs | ONE hard Linuxism: `launcher.c:79` `readlink("/proc/self/exe")`. Everything else is POSIX C. |
| Signals | SIGINT/SIGTERM ignore-in-parent + restore-in-child + re-raise-on-target-signal. Standard POSIX semantics, Linux-validated. |
| Filesystem | Atomic `os.replace`, `fsync`, `fcntl.flock`, `0700` dirs, symlink rejection. Validated on ext2/3/4. NFS untested. |
| Executable permissions | Build hook `chmod 0o755`; `doctor` checks executability. |
| XDG paths | `XDG_CACHE_HOME` honored, `~/.cache` default. Standard. |
| Python | `requires-python >=3.11,<3.15`; TESTED only 3.13.12. `tomllib` (3.11+) is the floor justifier. |
| `os.getuid`, `os.execve`, `fcntl` in Python | POSIX-only; fine on Linux. |

Recommended honest initial support wording:

> Linux x86_64 with glibc, CPython 3.13, installed from the provided wheel;
> other CPython 3.11–3.14 versions accepted but untested. Built against a
> recent glibc (2.43) — older distributions are untested and may need a
> rebuilt wheel. Local filesystems only.

(`Linux x86_64` alone is NOT precise enough: it omits the glibc recency risk,
the single-Python validation, and the local-filesystem boundary.)

Pre-release engineering required for even this scope: decide a manylinux
baseline (or ship per-distro builds), add release CI that rebuilds + reinstalls
+ runs the 27 product tests on the declared floor.

## macOS feasibility

Component verdicts:

| Component | Verdict | Reason |
|---|---|---|
| Python package (cli/config/diagnostics/runner) | PORTABLE AS IS | Pure Python; `os.getuid`/`execve` exist on macOS. |
| `read_engine` (artifact/cache/direct/runtime) | SMALL PLATFORM ADAPTER | `fcntl.flock` works on macOS; `os.replace`/`fsync` fine. Needs validation only (fsync semantics differ slightly; HFS/APFS atomicity holds for rename). |
| `_bootstrap/sitecustomize` | PORTABLE AS IS | |
| `_capture_helper` + `_frozen/capture/delta/validate` | PORTABLE AS IS | Pure Python + stdlib zip/XML. |
| `_frozen/eligibility`, certificate | PORTABLE AS IS | |
| Observer (`observer.c`) | SMALL PLATFORM ADAPTER | `nftw` exists on macOS (FTW_PHYS supported); fork/exec/wait/sigaction/mkdtemp fine. Needs a macOS build + full process-semantics validation (signal/FD behavior can differ at the edges). |
| Launcher (`launcher.c`) | SMALL PLATFORM ADAPTER | `readlink("/proc/self/exe")` does NOT exist on macOS. Needs `_NSGetExecutablePath` (or `argv[0]`+`$PATH` resolution) + `lib/python*/site-packages` glob check against framework/homebrew layouts. ~30 lines + tests. |
| Wheel packaging (`hatch_build.py`) | SMALL PLATFORM ADAPTER | Build gate rejects non-Linux; needs a macOS branch + macOS wheel tag. No cross-compilation story needed if CI builds per-platform. |
| Cache paths | PORTABLE AS IS | XDG honor + `~/.cache` default works (non-idiomatic on macOS but functional; `~/Library/Caches` mapping is polish, not a blocker). |

Overall: LOW COST. No architectural contract changes; one small launcher
adapter, one build-hook branch, and a validation pass (27 product tests +
install check + abrupt-exit fixtures on macOS). Recommend: fast-follow AFTER
v1, not in v1 — the validation pass is real work and v1 must not slip on it.
Omitting macOS from v1 is acceptable; omitting it forever would be wasteful.

## Windows feasibility

Component verdicts:

| Component | Verdict | Reason |
|---|---|---|
| Python CLI/config/diagnostics | SUBSTANTIAL REIMPLEMENTATION (partial) | `os.getuid`, POSIX permission model (`0700`, uid checks), `os.execve` semantics, `shutil.which` LibreOffice probing — all need Windows interpretations. |
| `read_engine/cache.py` | SUBSTANTIAL REIMPLEMENTATION | `fcntl` does not exist on Windows. Needs `msvcrt.locking`/pywin32 file locking or a lock-file protocol redesign + validation. |
| `read_engine/artifact.py` | SMALL PLATFORM ADAPTER | `os.replace`/`fsync` OK; temp-file + atomic-rename pattern portable with testing. |
| Observer (`observer.c`) | SUBSTANTIAL REIMPLEMENTATION | `fork`/`execv`/`waitpid`/`sigaction`/`nftw` do not exist. Needs a Win32 rewrite (CreateProcess, WaitForSingleObject, exit-code-only status — no POSIX signals, no re-raise semantics). The "survives target death" contract needs a Windows-specific definition (job objects? SEH?). |
| Launcher (`launcher.c`) | SUBSTANTIAL REIMPLEMENTATION | `/proc/self/exe`, `glob`, POSIX perms, `execv` — all need Win32 equivalents (GetModuleFileName, venv layout `Scripts/`, ACLs). |
| Signal/exit-code contract | SUBSTANTIAL REIMPLEMENTATION | No SIGTERM/SIGINT-in-parent model; 128+signo convention is foreign; console control events differ. Receipt `target_signal` field needs a Windows interpretation. |
| File observation | SMALL PLATFORM ADAPTER to SUBSTANTIAL | Recursive snapshot is portable logic, but case-insensitivity, file locking (open XLSX can't be read/replaced the same way), and AV-interference change failure modes. |
| Wheel packaging | SMALL PLATFORM ADAPTER | Needs an MSVC/MinGW build branch; per-platform wheel tags. |

Architecture contracts requiring Windows-specific interpretation:
target-status model (exit code only?), signal vocabulary in receipts,
cache-locking protocol, private-directory ACLs, and the observer-survival
guarantee (what kills the observer on Windows?).

Overall: HIGH COST. A genuine port, not an adapter. Do not attempt before v1;
revisit only with a committed Windows validation host and appetite for a
second observer implementation + a Windows receipt dialect. Windows must not
be a release blocker and must not be promised.
