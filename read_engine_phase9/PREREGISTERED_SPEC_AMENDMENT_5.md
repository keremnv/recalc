# Phase 9 preregistration amendment 5 — restore assurance-gate order

Status: recorded after aborting an incomplete scored attempt; no scored result from that attempt is eligible for analysis.

The version-1 spec requires changed-workbook `os._exit` and fatal-signal assurance diagnostics before scored timing. The 22 general process fixtures, all 30 representative cold/second gates, and all five changed-file gates passed, but the separate abrupt-exit **with mutation** diagnostics had not run. Scoring was started and then interrupted as soon as the ordering omission was identified. Preserve its partial rows and staging as `score_attempt_1_*` and `runs/scored_attempt_1`; do not analyze them.

Run the two already-frozen Phase-8A changed-workbook abrupt fixtures under Phase-9 H0 and H1. Require target exit/signal fidelity, observer survival, changed-XLSX detection, capture-helper success, effect receipt and equivalent package state. Record results in `abrupt_exit.jsonl`. If both pass, restart the *entire* scored run from fresh private scored/warmup staging with the identical pinned implementation, population, three repetitions, ordering, endpoints and decision rules. No treatment or scoring code changes.
