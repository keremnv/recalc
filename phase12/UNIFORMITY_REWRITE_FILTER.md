# Uniformity rewrite filter v1

Goal: report `localized accidental break`, suppress `broad intentional
restructuring`. Conservative: when mechanical evidence cannot distinguish,
stay silent.

## Definitions

- Family: relative-fingerprint group in the INPUT workbook (≥3 members).
- Post-edit break: formula cell whose fingerprint differs from its
  row/column family's input pattern, where the input cell matched.
- Affected block: the minimal row-span × col-span rectangle covering the
  break cell plus its input family neighbors on the same row/column.

## Suppression rules (any one suppresses the break cell)

1. **Broad rewrite**: changed footprint (added/changed/removed formulas +
   emptied/filled cells) covers ≥50% of the affected block's input
   formula cells.
2. **New coherence**: the break cell shares its OUTPUT fingerprint with ≥2
   other output cells in the same block whose input fingerprints also
   changed (the edit installed a new consistent pattern).
3. **Scale cap**: total post-edit break cells across the workbook exceed
   30 → suppress ALL UNIF items (too broad to be "localized accidental";
   the change itself is the story, carried by CHG context).
4. **Edge exemption**: break cells in the first/last row or column of a
   family band are suppressed (legitimate total/seed positions) UNLESS the
   break cell's formula was directly modified by the edit (in CHG set).

## Report rule

Surviving break cells are reported with their input pattern description
(row-pattern/col-pattern + neighbor count). Presentation sample capped at
10 cells; full list in machine detail.

## Version

Filter v1, frozen with verifier 1.0.0. Changes require version bump +
re-validation + preregistered amendment.
