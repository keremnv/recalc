# P5 disposition after the CPU-pinned score

The one bounded P5 treatment was implemented, separately installed, scored, and tested. Its complete experimental bootstrap is preserved as `p5_sitecustomize_snapshot.py` (SHA-256 `92f6dadcd54cf2d8de58f381fedd7d121d9ac1a641d5381a5ec1cca857bbc826`); its installed wheel and venv identities remain recorded in preregistration amendment 3. The original Phase-10 installed P4 environment was never changed.

Under the preregistered CPU-pinned rerun, unchanged P4 already met the frozen +10 ms budget: median P4−P0 was +6.39 ms, and the independent same-run P4−PY_OLD bridge was +6.47 ms. P5 reduced raw P5−P4 wall by a median 2.99 ms, but its environment-adjusted median was −1.81 ms with a workload bootstrap interval spanning zero. The shortcut duplicates a subset of frozen classifier lexical rules in startup code, creating a maintenance coupling for a small gain that is unnecessary to resolve the blocker.

The maintained `src/librecalc_agent/_bootstrap/sitecustomize.py` was therefore restored to the exact installed Phase-10 source (SHA-256 `f4a64dcb0706a0670675502fba4663eba7b2519dbd197bdfe744d33ed5ee177b`). P5 remains experimental evidence, not a production change. No frozen Phase-10 or research file was edited.
