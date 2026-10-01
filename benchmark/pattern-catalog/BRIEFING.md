# Pattern catalog briefing

Read `METHOD.md` before proposing design. This file is the grid, not a chat recap.

**The gate is closed at n=2/n=2 for every case: `python benchmark/catalog_gate.py`
returns 0 of 14 patterns surviving, and that is the finding, not an unfinished step.**
Of 12 cases: 6 `shared` (both arms always miss), 4 `noise` (our own repeat runs get that
exact cell right), 1 `refuted-lever` (real delta, but its only lever has a measured
zero-exact-conversion record), 1 `far` (task carries too many other misses to matter).
**Zero cases both hold under repeat and have a live lever.** Read the grid as a closed
collection, not as a punch list, and do not reopen a case's verdict without new runs --
every verdict here already survived one repeat that changed the answer
(`t-16-12-j10`, `d-01-05-d53`) or confirmed it (`d-02-05-d7`).

**Stance:** GLM 5.3 Flash. Gather, do not design. Do not rerun 297. Hybrid is dropped.
Do not add tools from these autopsies. n=15 exact is noise. First-miss is per run.

**Where:** `benchmark/pattern-catalog/`. Census:
`census/glm-5.3-flash-nonvisual-297-1.json` (autopsy v2: boundary counts as named;
failed oversize is not a read). Control-arm coverage: `arms.yaml`.

## The result, plainly

Fourteen pattern names collapse into six mechanisms (`surface.yaml`). None survives:

| mechanism | cases | verdict | why |
|---|---|---|---|
| `identity-choice` | t-16-12-j10 | noise | our arm gets it right 2/6 repeats |
| `sign-convention` | t-09-03-d24, t-14-05-m35 | far, shared | control misses it too; no separating fact |
| `run-boundary` | t-04-04-d13, fm-03-02-m4, fm-01-02-m3, t-10-02-e10 | noise, shared, shared, noise | control misses the shared ones too; ours is unstable on the rest |
| `representative-selection` | d-02-05-d7, d-09-09-h107 | **refuted-lever**, shared | see below |
| `error-token-policy` | d-01-05-d53 | noise | both repeats left the cell untouched, no wipe to catch |
| `instruction-scope` | t-09-01-c8 | shared | control follows the same on-sheet instruction |
| `serialization` | d-01-02-c36 | shared | control's save path collapses it too |

**The one case with a real, repeat-stable delta is `d-02-05-d7`, and it is blocked by
lever, not by evidence.** Control gets `WACC!D7` right in 2/2 runs; our arm gets it
wrong in 2/2. But across all three of our trajectories (the 297 run plus two repeats),
the read windows converge *next to* D7 -- row 7, or rows 10-16 -- and never once include
it. That is not a shortlist that drowned the cell; it looks like bash + openpyxl letting
the model scan the whole workbook for silent-wrong formulas, a capability class our
interface does not expose. It does not fit any of the four levers (nothing tells,
decides, refuses, or ranks). `arms.yaml` names it `agent_scan` and marks it a
**candidate, not a lever** -- one case does not establish a family. See `METHOD.md`.

## Open claims (filename + `answer=` leak, no golden)

- d-02-05-d7: whether D7's AVERAGE *is* the planted Incorrect Average. Now also whether
  the read-side miss on this cell is a policy defect or a capability gap -- see above.
- fm-01-02-m3: observation note "Not requirements" vs evaluator wanting 2031-03-31.

## Next

Not more visits, and not a redesign from this grid alone -- it has nothing left to
design against. In order:

1. **Test whether `agent_scan` repeats.** One case is not a lever. The cheapest test is
   n>=3 more Debugging tasks whose planted class is a silent formula (no error token) run
   through both arms, watching only whether our read windows keep landing adjacent to the
   miss without including it. If they do, that is the redesign's actual starting point --
   not information delivery, but giving the agent (or the world) a way to scan the whole
   workbook for anomalies with no error token to anchor a shortlist on.
2. **If it does not repeat, this catalog is finished.** Twelve cases, four arms
   (control x2, ours x1 original + x2 repeat, 15-slice x4, ladder x4), zero surviving
   patterns is a real result: on this model and this slice, the interface is not where
   the failures live. Say that plainly in the next design conversation rather than
   re-deriving it from the same twelve cases again.

Standing: the grid is closed as a *collection*. Do not visit more Template wrote-wrong
blanks. Do not open goldens into `cases/`.
