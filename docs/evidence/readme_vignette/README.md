# README vignette evidence — FM:08_02 Line-01 scan

Read-only inspection step from public benchmark task
Financial_Model:08_02 (Project Seafood Model), SpreadsheetBench-2.

- `prompt.txt` — full 5-part instruction, byte copy from
  `benchmark-data/SpreadsheetBench-2/data/Financial_Model/dataset.json`.
- `code_excerpt.py` — frozen executed scan (`script_sha256 4ca3ae…`), also the
  R3 population-A workload `Financial_Model_08_02__4ca3ae46295d`.
- `timing.json` — faithful R3-protocol paired reproduction on released 0.2.0
  (clean install): BASE 3× bare python; RECALC fresh cache + 1 discarded warmup
  + 3× full `recalc-agent run`; same window. Medians 3.6866 s → 0.7320 s
  (2.9546 s saved, 80.14% lower). Route DIRECT_RUNTIME ×3, artifact REUSED ×3,
  address-normalized stdout identical (raw differs only in `0x` object
  addresses, which differ between any two runs). R3 frozen medians retained
  inside as cross-check (different window).
- `scenario.json` — workload identity, hashes, routing, read pattern.
- `expected_hashes.json` — hash/derivation provenance pointers.
- `sheet_crop.png` — LibreOffice headless render of the real
  `'Assumptions - Line 01'!A1:H24` (render copy; measured bytes hashed).
- `generate.py` — `--verify` recomputes medians/derivations and checks
  hashes, prompt, exits, routes, reuse, parity; `--build` also re-renders the
  crop and composes `docs/assets/recalc-performance-vignette.svg`.

No writes occur in this step (input sha identical before/after every measured
workdir). Selection rationale, rejected candidates, and limitations:
`docs/evidence/README_VIGNETTE_SELECTION.md`.
