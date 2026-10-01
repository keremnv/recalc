# Forced compiled-context sidecar: Financial_Model:05_01

Generated at: 2026-09-16T13:48:34.286643+00:00

This is not the optional C0/C1 A/B. C1F **requires** a first-pass `calc_query` on the official scaffold. Control is the frozen sidecar C0 run, not rerun.

## Why this task

- Optional C1 on `05_01` adopted `calc_query` then died on the Docker `parents[5]` wrapper crash, so that trajectory is not a model result.
- C0 hit the 40-call envelope.
- `13_05` is the wrong forced candidate: all four optional pairs already matched gold `I20:M20` without `calc_query`.
- `15_05` is a negative-structure task. `09_04` C0 failed, but optional C1 was still running on that task id.

## Identity

- Declared/request: `meta/muse-spark-1.3-contributor` / `openrouter/meta/muse-spark-1.3-contributor`
- Generation: temp 0, top_p 1, tool_choice auto, reasoning_effort unset. Envelope 40/$2.50.
- Identity ok: `True`
- Source: `official-score-spark-1.3-contributor-fm-02_01`

## Scores

| Arm | run | modification | regression | exact | usable | calls | calc_query |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | `spark-sidecar-c0-Financial_Model-05_01-r1` | 0.999 | 0.9973 | False | True | 40 | n/a |
| C1F | `spark-sidecar-c1f-Financial_Model-05_01-r1` | 0.998 | 1.0 | False | True | 40 | 5 USED |

C1F modes: `['periods', 'search', 'search', 'inspect', 'formula_pattern']` first_turn=1 uptake=True

C0 first miss: `Regression error at Dashboard!G46: answer=None, output=2`. C1F first miss: `Regression error at Dashboard!G46: answer=None, output=2`.

## Prompt hashes

- C0 system: `0c36c45319b387fbdb58a3c899c1d8d0beed4d5426f0aa80422114165930b24b`
- C1 optional instance: `088238307584b443653efc2a8bcd83ba794288fa5126cff9238279dc9ae45f1b`
- C1F config present: `True`
- Forced prompt requires calc_query before edits: `True`

Causal claim is only this C0/C1F pair on `Financial_Model:05_01`.
