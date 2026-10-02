# Temporal reachability study (C4 → TEMP-PERIOD-MAP, D2, CONDITIONAL)

Mechanical definition (gold-blind): date-typed cells in rows 1–8 plus
FY/CY/Q/year/month string matches; period structure = ≥3 mapped columns
on a sheet. No ontology, no intent: pure header→coordinate alignment.

## Prevalence

74/146 readable inputs (51%) carry mechanical period structure. Concentrated
but not exclusive to Financial_Model (Debugging 42, Template 16, FM 16 —
Debugging workbooks inherit FM-style layouts).

## Natural reachability (n=74)

R2=53, R3=9, R4=12. Reach rate R4+: 16%. The modal case: headers visible in
dumps (R2) but never parsed into coordinates. The 9 R3 cases show date/period
tokens in code without a header tie (e.g. hardcoded year in a filter). The
12 R4 cases parse headers explicitly (strptime/dateutil/datetime/FY logic
tied to header rows) — all in runs where period choice was the task's crux.

## Failure linkage / discrimination

- Linkage: PLAUSIBLY_LINKED 35/74 (miss + unreached + failed), UNRELATED 7,
  UNKNOWN 32. No DIRECTLY_LINKED: finding keys are sheet:column labels,
  which cannot overlap miss cells by construction — TEMP's leverage is
  upstream (choosing the right columns), not miss-localization. The
  discrimination column is structurally GENERIC; judge TEMP on decision
  relevance, not overlap.
- Qualitative: in FM runs the agent typically hardcodes period columns from
  eyeballing headers (works when headers are clean) or misaligns when FY
  labels are offset/irregular. 2 sampled FM failures show hardcoded columns
  adjacent to the correct ones — consistent with missing alignment, not
  proof of it.

## Trivial-Python baseline / discovery cost

4–10 lines to parse + align once the header row is known; discovery cost is
finding the header row and the FY anchor across irregular layouts (merged
header bands, multi-row headers). Multi-row/merged headers were observed;
the mechanical detector handles only the clean subset — CONDITIONAL.

## Interpretation

MECHANICALLY VALUABLE but narrow: missed often (84% below R4), exact on the
clean subset, plausibly decision-bearing for CHOOSE_SOURCE_PERIOD in FM
tasks. Weaknesses: (a) no demonstrated discriminator (upstream leverage is
inferred, not shown); (b) irregular layouts need judgment (semantic edge);
(c) agents succeed by eyeballing when headers are clean — the value is
concentrated in irregular cases. Verdict: NEEDS LIVE CAUSAL TEST only if
bundled cheaply with a stronger candidate; alone it does not clear the
discrimination bar. Do not build the ontology; at most surface the
column→period map as evidence on FM tasks.
