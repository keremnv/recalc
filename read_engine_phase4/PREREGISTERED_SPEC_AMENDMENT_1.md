# Phase 4 preregistration amendment 1 — effective v2

This amendment is recorded during implementation review, before any correctness gate, import diagnostic, or scored benchmark. It does not change the population, protocol, treatment, endpoints, decisions, or stopping rules. The original `PREREGISTERED_SPEC.md` remains immutable with SHA-256 `0162f197c89c37ee63bafb5cfbbbc65f3e030eb830bd945ddffa042c560019ea`.

The v1 text accidentally inserted an extra `5c` in the written SHA-256 for `rc_acceleration_validation/eligible_population.json`. The actual pre-existing file SHA-256, also recorded correctly in the frozen Phase-3 preregistration and observed before Phase-4 implementation, is:

`b6be87f570bfd33c499038526a45b8624d7752531a79dda29a55bd9cddbcf1a8`

The exact 22 identities still come from `read_engine_phase3/population.json` SHA-256 `ea83d4f603430d78b30b8b85b70bb5a8ee9ef916350060bbf52c8f67701651dc`. This amendment only corrects the literal identity check. Effective preregistration is v1 plus this amendment; both hashes must verify before any Phase-4 execution.
