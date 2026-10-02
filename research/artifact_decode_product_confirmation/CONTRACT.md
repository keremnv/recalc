# R6 D1 contract (frozen before scoring)

Source: exact semantic delta of R5 commit `be806c3`
(`src/recalc_agent/read_engine/artifact.py` only).

## What changes

In `_book`, per-cell typed reconstruction replaces:

```python
value = _value_from_json(canonical(typed).decode())
```

with:

```python
value = _direct_value(typed)
```

plus a module-level `_direct_value` helper (+ `math`, `datetime`,
`ArrayFormula`/`DataTableFormula` imports; `_value_from_json` import
removed). Rationale: `typed` already passed `_check_typed`
(structural/type validation), so re-serializing to a JSON string and
re-parsing it is redundant. Non-finite floats are rejected explicitly
(`math.isfinite` on scalar floats and timedelta seconds), preserving
the previous `canonical(allow_nan=False)` rejection side effect.

## What remains invariant

- Artifact format `JSONZ_MEMORY_V1`, bytes, layout, compression.
- All validation: header/envelope/checksum/identity checks,
  `_check_typed`, COORD, dtype set, bounds, dupe/cell caps —
  unchanged and still executed before reconstruction.
- Encode/build path: untouched.
- Admission, routing, serving, observer, assurance, capture: untouched.
- Agent-facing API: untouched. No new dependency (stdlib-only).
- Exception contract: corrupt input still raises `ArtifactError`
  (same fail-closed policy; messages may differ in the explicit
  non-finite cases, both `ArtifactError`).

## Explicitly excluded

D1b (manual coord validator) and everything in R5 §21 non-goals:
codecs, binary formats, segmentation, lazy decode, persistence,
mmap, new formats, build laziness, read shapes, dependency/recalc,
CLI startup, inspection APIs.
