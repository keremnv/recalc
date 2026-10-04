# Side-by-side race GIF evidence

`docs/assets/recalc-side-by-side.gif` replays the frozen FM_08_02 Line-01
scan (same script + workbook as the README vignette) as a BASE vs warm-Recalc
race. Nothing is acted: output bytes, pacing, timers, and line counts are
sampled frame-by-frame from real `script --log-timing` recordings.

- `capture.py` — records 3 reps/arm in fresh workdirs (RECALC: fresh cache +
  1 discarded warmup), checks exits/routes/REUSED/output parity, keeps the
  median rep per arm. Clean-room venv (CPython 3.13, openpyxl 3.1.5,
  recalc-agent 0.2.0, no numpy), same protocol family as the vignette timing.
- `captures/captures.json` — all reps' walls, hashes, routes; selected medians.
- `captures/base.typescript`, `captures/base.timing`,
  `captures/recalc.typescript`, `captures/recalc.timing` — the kept recordings
  (raw `script` output incl. header/footer; stripped at render/hash time).
- `render_gif.py` — replays the timing curves at 12 fps, renders DNA-styled
  frames (PIL), encodes with ffmpeg palettegen/paletteuse. Fonts convert from
  the vendored vignette woff2 at build time (`/tmp` only, not committed).

Recorded numbers (this GIF): BASE 2.35 s, Recalc 0.41 s, 1.94 s saved —
single recorded runs (median of 3 measured reps each), shown in-GIF. Published
vignette medians from a different window are 3.69 s / 0.73 s; both show ~5×.
Phase labels ("reading + parsing", "loading validated state", "streaming
findings") are derived from each arm's first-output byte in the timing data.

Regenerate: `python3 docs/evidence/side_by_side_race/capture.py --venv VENV`
then `python3 docs/evidence/side_by_side_race/render_gif.py`.
