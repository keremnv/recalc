# Phase 8A certificate hardening review

Status: pre-implementation semantic architecture decision. Outcome: **A — WHOLE-SCRIPT POSITIVE PROOF IS FAIL-CLOSED for a deliberately restricted source grammar**, not for arbitrary admitted Python. The default is `NOT_CERTIFIED`. The frozen admission classifier remains a separate prerequisite.

## Approaches considered

**A. Positive whole-script static proof — selected for this experiment.** Validate the entire module against a closed grammar of ordinary `import openpyxl`, direct load, literal sheet binding, scalar loops/conditionals/comprehensions, direct `.cell(...).{value,data_type,coordinate,row,column}`, and a few scalar/printing operations. Reject every unrecognized statement, call, attribute, subscript, assignment target, import and binder. Recognize a worksheet only from `ws = wb[<literal sheet>]`; do not permit worksheet aliases, method aliases, dunder access, dynamic attributes, helper calls or object escape. Require at least one positively proven terminal cell call. This can retain the three fixed Phase-7 target scripts because their relevant syntax is simple. It is intentionally much narrower than the frozen admission language.

**B. Per-expression/per-operation certification.** The runtime receives a `.cell()` call before Python performs the later `.value` or `type` observation. Without source rewriting or a new API, it cannot know at that instant how the returned object will be used. A per-expression certificate would need a secure mapping from runtime call site to preproved source expression and must handle dynamic code/frames/aliases. That adds a separate attribution mechanism and is not the smallest safe repair here.

**C. Dynamic capability/fallback object.** A Python proxy can defer named attribute reads to reference, but `type`, `isinstance`, identity, default `repr`, hashing and container escape see the proxy object itself. Dynamic fallback after returning a proxy cannot retroactively make it a real `MergedCell`. It cannot certify this edge under the ordinary interface alone.

**D. Always reference merged children.** Fully safe for the merged edge under existing limits and the fallback if positive proof fails. This remains the default and is preferable to a false positive; it is the contingency if approach A cannot be made sound enough.

## Positive proof invariant

Certification is granted only if every reachable AST statement and expression belongs to the explicitly checked grammar; workbook/worksheet references can occur only in the specific load/sheet-binding/direct-terminal positions; each syntactic `.cell` access has a proved worksheet receiver and an immediate approved terminal field; and at least one such direct terminal call exists. There is no generic `visit_Unknown` fallthrough. Assignments can bind only ordinary names; a reserved workbook/worksheet name cannot be rebound except through its exact allowed constructor. Loop/comprehension targets are ordinary scalar names. Only `openpyxl.load_workbook`, `range`, `print`, `repr`, `type` (on an already safe scalar), and `.append` on a locally initialized list are callable in the positive grammar. Any new Python syntax is rejected until explicitly reviewed.

The proof covers **the merged-child direct route**, not complete openpyxl object equivalence for arbitrary Python. Reference fallback remains the route for any admitted but uncertified program. The known `parent_identity` mismatch is carried as a separate proxy limit. If adversarial testing finds a false-positive direct route, hardening fails and Phase-8 scoring remains stopped.
