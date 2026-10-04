# Vignette fonts (vendored build inputs)

Embedded as data URIs in `docs/assets/recalc-performance-vignette.svg` so the
visual language renders identically everywhere, including GitHub's image context
(no external fetches).

- `jost-latin-400-normal.woff2` — Jost Regular (geometric sans for prose/labels/numbers)
- `jost-latin-600-normal.woff2` — Jost SemiBold (headings, primary numbers)
- `spline-sans-mono-latin-400-normal.woff2` — Spline Sans Mono Regular (code, findings)

Source: the sibling `design` project's frontend (`@fontsource` packages, same
faces/weights its typography tokens specify). Both families are SIL Open Font
License 1.1 (Jost © indestructible type*; Spline Sans Mono © Eben Sorkin /
Spline Sans contributors) — see the OFL text in the respective `@fontsource`
packages. Hashes pinned in `expected_hashes.json` and checked by
`generate.py --verify`.
