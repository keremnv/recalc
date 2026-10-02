# Linux release baseline — librecalc-agent 0.2.0rc2

## Declared floor

- Architecture: x86_64 only.
- libc floor: glibc >= 2.34, established by symbol audit of both shipped
  binaries (`objdump -T` max requirement: `GLIBC_2.34`; build host glibc 2.43
  does not leak newer symbols into the binaries).
- Python: CPython 3.13 tested; 3.11–3.14 accepted by metadata, untested.
- Filesystem: local POSIX filesystem with atomic rename, `fsync`, advisory
  `flock`, and POSIX permissions. Network filesystems untested.
- Build image: any Linux x86_64 with `cc` (C11), Python 3.11+, pip, and index
  access for `hatchling` + pinned runtime deps. Reference build: Ubuntu 26.04,
  gcc 15.2, CPython 3.13.12.
- Test image: same floor; CI reference `ubuntu-24.04` + CPython 3.13.
- Wheel tag: `py3-none-linux_x86_64` (local platform tag, NOT manylinux).
- manylinux path (deferred, defined): rebuild in an official
  `manylinux_2_34_x86_64` image and run `auditwheel repair`; the symbol audit
  shows no blocker, but the label must not be claimed without that pipeline.
  This RC deliberately does not claim it.

## Unsupported environments

glibc < 2.34; non-x86_64; musl/Alpine (untested dynamic loader/permissions);
Windows; macOS; remote filesystems for cache; Python < 3.11 or >= 3.15;
unpinned openpyxl/lxml versions.

## Reproducibility notes

- Runtime closure locked in `requirements-release.txt` (pins + hashes for the
  cp313 floor set).
- Build backend version-pinned in the same file (hash recorded for audit).
- Release battery: `scripts/release-check.sh` (also run by
  `.github/workflows/release-candidate.yml`).
- Candidate archives + `SHA256SUMS` staged under `release-candidate/`
  (gitignored) and recorded in `phase10c_b/RELEASE_CANDIDATE_MANIFEST.json`.
