# Compact Evidence Delivery

Verdict: `COMPACT_ENCODING_NO_RESOURCE_GAIN`

This is an evidence-transport experiment on frozen `Financial_Model:06_01` O3
targets. Semantic architecture was held fixed. The only experimental variable
is synthesis-evidence representation. No retrieval, planner, scheduler, writes,
LibreOffice, or official scorer ran.

The compact treatment is **not** earned for runtime use. Factual equivalence
passed, and there was no treatment-specific loss of otherwise-correct
synthesis. Provider prompt-token reduction on complete pairs was about
**14.5%**, below a material bar once provider token accounting is used.
Request bytes fell more (~26.5%), but byte savings are not a token claim.
Treatment also timed out on **5/16** pairs against **0/16** control timeouts.
Retain the current full evidence serialization.

## Configuration

- model: `z-ai/glm-5.3-flash`
- reasoning: `high` (not `max`)
- temperature: `0.0`
- top-p: `1.0`
- constructor: `matched_compiled_treatment.request_body` with fail-closed
  `experiment_config.request_identity`
- synthesis timeout: 180s for the first 14 recorded calls; 300s for remainders
  after two treatment timeouts. The two 180s timeouts were not retried.

## Population and equivalence

Requested 16 frozen O3 targets. Included: **16**. Excluded before live calls:
**0**.

CONTROL is the current full `materialize_complete` serialization from the fresh
integrity-verified source → spine → SQLite lineage. TREATMENT is
`columnar_dict_v1`, a deterministic column-major dictionary encoding of the
same tables. A decoder/canonicalizer required
`canonical_facts(CONTROL) == canonical_facts(TREATMENT)` before any provider
call. Witnesses `DCF!C47 = 0.11`, `C48 = 0.25`, and `C51 = 0.15` retained
their values where they occurred.

## Resource

Provider-reported prompt tokens are the resource claim. 11 of 16 pairs
returned tokens on both arms.

| Metric | CONTROL | TREATMENT | Reduction |
|---|---:|---:|---:|
| Median prompt tokens (11 complete pairs) | 527751 | 449719 | 76417 (**14.5%**) |
| Total prompt tokens (those 11 pairs) | 5842363 | 4998231 | 844132 |
| Median request bytes (all 16) | 1397464 | 1026884 | 373572 (**26.5%**) |
| Cost USD (reported) | 0.959 | 0.547 | 0.412 cheaper treatment ledger |
| Provider failures | 0 | 5 | treatment-only timeouts |

The treatment cost ledger is lower partly because timed-out calls report $0.
That is not a demonstrated saving. Control never timed out.

## Semantic preservation

Paired categories:

- both semantically correct: **7**
- treatment correct / control wrong: **4** (control abstained; treatment proposed)
- provider-censored pair: **5** (all treatment timeouts)
- control correct / treatment wrong: **0**

Hard-accept proposals: CONTROL 12, TREATMENT 11. Treatment-specific loss of
otherwise-correct synthesis: **0**. Gold exact match is diagnostic only and
existed only for `DCF!C49` (`=C47*(1-C48)`); both arms matched it. Gold was
never sent to either arm.

| Target | Order | Category | CONTROL | TREATMENT |
|---|---|---|---|---|
| DCF!C49 | CONTROL → TREATMENT | both semantically correct | PROPOSED `=C47*(1-C48)` HARD_ACCEPT gold=True | PROPOSED `=C47*(1-C48)` HARD_ACCEPT gold=True |
| DCF!D49 | TREATMENT → CONTROL | provider-censored pair | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROVIDER_TIMEOUT (300s) |
| DCF!E49 | CONTROL → TREATMENT | provider-censored pair | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROVIDER_TIMEOUT (300s) |
| DCF!F49 | TREATMENT → CONTROL | both semantically correct | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROPOSED `=C47*(1-C48)` HARD_ACCEPT |
| DCF!G49 | CONTROL → TREATMENT | treatment correct / control wrong | ABSTAIN | PROPOSED `=G47*(1-G48)` HARD_ACCEPT |
| DCF!H49 | TREATMENT → CONTROL | treatment correct / control wrong | ABSTAIN | PROPOSED `=C47*(1-C48)` HARD_ACCEPT |
| DCF!I49 | CONTROL → TREATMENT | both semantically correct | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROPOSED `=C47*(1-C48)` HARD_ACCEPT |
| DCF!J49 | TREATMENT → CONTROL | treatment correct / control wrong | ABSTAIN | PROPOSED `=C47*(1-C50)` HARD_ACCEPT |
| DCF!K49 | CONTROL → TREATMENT | provider-censored pair | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROVIDER_TIMEOUT (180s) |
| DCF!L49 | TREATMENT → CONTROL | provider-censored pair | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROVIDER_TIMEOUT (180s) |
| DCF!M49 | CONTROL → TREATMENT | treatment correct / control wrong | ABSTAIN | PROPOSED `=C47*(1-C48)` HARD_ACCEPT |
| DCF!N49 | TREATMENT → CONTROL | both semantically correct | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROPOSED `=C47*(1-C48)` HARD_ACCEPT |
| DCF!O49 | CONTROL → TREATMENT | both semantically correct | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROPOSED `=C47*(1-C48)` HARD_ACCEPT |
| DCF!P49 | TREATMENT → CONTROL | both semantically correct | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROPOSED `=C47*(1-C48)` HARD_ACCEPT |
| DCF!Q49 | CONTROL → TREATMENT | both semantically correct | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROPOSED `=C47*(1-C48)` HARD_ACCEPT |
| DCF!R49 | TREATMENT → CONTROL | provider-censored pair | PROPOSED `=C47*(1-C48)` HARD_ACCEPT | PROVIDER_TIMEOUT (300s) |

## Prospective envelope

Retain the **full** synthesis evidence interface. Freeze GLM 5.3 Flash /
`high`. Proposed next-benchmark envelope: **40 model calls** and **$2.50**.
This is not the historical 150-call 06_01 cap and is not fitted so that
historical residual cells finish.

Measured high-reasoning CONTROL synthesis is about **$0.055–$0.082** per
successful call, typically 20–30s, never timed out here. Historical 06_01
frontend was 7 successful calls at $0.036; retained retrieval was 101 calls
at $0.755. Those retrieval/frontend costs remain the larger paid demand if
the integrated runner is used unchanged.

This envelope would still censor:

- a task that opens an independent full synthesis session for every residual cell
- repeated retrieval rebuilds of the same evidence
- provider timeouts (observed on compact packets even at 300s; not observed on
  full packets in this sample)
- identity mismatch, which invalidates the run

Provider failures stay provider failures, not semantic demand.

## Artifacts

- `compact_evidence_delivery/equivalence.json`
- `compact_evidence_delivery/live.json`
- `compact_evidence_delivery/ledger.json`
- `compact_evidence_delivery/pairs.csv`
- `compact_evidence_delivery/targets/*/canonical_facts.json`
- `benchmark/compact_evidence_delivery.py`
- `benchmark/compact_evidence.py`

No FM20, GPT model swap, old-harness comparison, or published-control rerun
was launched. No new semantic architecture was added.
