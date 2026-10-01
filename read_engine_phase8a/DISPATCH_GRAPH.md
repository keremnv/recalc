# Phase 8A cell dispatch graph

Status: implementation inspection before hardening. Sources: frozen `read_engine_phase3/runtime.py`, Phase-7 `merge_runtime.py`, Phase-7 overlay bootstrap/certificate, and frozen `eligibility.py`. The classifier decides admission only; it is not an escape proof.

## Runtime path

`sitecustomize → Runtime.install → openpyxl.load_workbook = Runtime.load`. For admitted, supported loads, `Runtime.load` validates source SHA/artifact and returns `ProxyWorkbook`; otherwise it invokes saved reference openpyxl. `ProxyWorkbook.__getitem__(sheet)` returns `ProxyWorksheet`. That object has:

- `.cell(row,column)` — patched by Phase-7 `install_cell_route`; covered merged child returns `ProxyCell` when whole-script `merged_terminal_certified`, otherwise `_real_sheet().cell(...)` and reference parse. Non-covered coordinates return `ProxyCell`.
- `.__getitem__(coordinate)` — for a single coordinate parses it, then calls **`self.cell`**. This internal edge bypassed the old literal `.cell` AST scan.
- `.__iter__`, `.iter_rows` and unknown attributes — materialize/delegate to real reference sheet. A real cell can then coexist with proxy worksheet identity.

`ProxyCell.value/data_type` read frozen direct state; `.coordinate/.row/.column` come from requested coordinates; unknown attributes delegate to a real cell. The temporary proxy object's class, repr, identity and parent relationship are not interchangeable with an openpyxl `Cell`/`MergedCell`.

## Source syntax and reachability

| Source route | Frozen admission can allow? | Reaches patched `ProxyWorksheet.cell`? | Phase-7 certificate behavior | Safe proof requirement |
|---|---|---|---|---|
| `ws.cell(...).value` and other five terminal fields | Yes | Yes | Certifies | Only when `ws` is a proved proxy worksheet and returned object is immediately consumed. |
| `ws.cell(...)` object, `type`, `repr`, storage or passing | Yes in several shapes | Yes | Usually rejects literal `.cell` | Reject whole script for merged direct route. |
| `ws["B1"]` | Yes | Yes via `__getitem__` | Rejects only if `ws` is a tracked worksheet name | Reject unless a separate positive proof exists. |
| `wb["Sheet"]["B1"]` | Can be allowed | Yes via nested `__getitem__` | May evade named-worksheet check | Reject sheet objects not assigned through proved binder. |
| `ws.__getitem__("B1")` | Yes | Yes | **False positive**, zero literal `.cell` calls | Reject dunder/unknown attributes. |
| `ws.__getattribute__("cell")(...)` | Yes | Yes | **False positive**, zero literal `.cell` calls | Reject dunder/unknown attributes. |
| `getattr(ws,"cell")`, `operator.attrgetter`, dynamic string | Some forms blocked by classifier; indirect forms can evade | Potentially | Not exhaustive | Do not allow unproved call/attribute dispatch. |
| `f=ws.cell; f(...)`, method in list/tuple/dict | Some forms allowed | Yes | Literal `.cell` usually rejected, but other acquisition paths evade | Reject method-as-value and indirect calls. |
| `ws2=ws`, nested alias or closure | Some forms admitted; functions often blocked lexically | Potentially | Name tracking incomplete | Reject aliases unless positively bound and analyzed. |
| Helper receiving/returning worksheet/cell/method | Functions blocked in many simple cases, but dynamic callbacks are not an admission guarantee | Potentially | Syntax scan incomplete | Reject functions and calls outside the closed grammar. |
| Comprehension with direct terminal `.cell` | Yes; three target scripts use it | Yes | Certifies | Permit only controlled scalar iterator, no object escape. |
| Generator, lambda, nested function, walrus, ternary | Some are blocked lexically, not all possible variants | Potentially | Incomplete | Reject unless separately proved. |
| Rebinding `ws.cell`, class monkeypatch, module manipulation | Classifier handles some writes, not a complete proof | Potentially | Incomplete | Reject all assignment targets beyond scalar names, and imports/calls outside closed grammar. |
| `eval`, `exec` | Common forms blocked lexically | Arbitrary | Not a proof | Reject all dynamic execution/call indirection. |

The graph has two independent proof obligations: **(A)** every route that can reach the patched `.cell` path is known; **(B)** every returned object from those routes is consumed through an earned terminal field. The old certificate checked B on recognized literal syntax while silently assuming A. Zero recognized calls is no evidence of A. The Phase-8 diagnostic demonstrates the resulting false positive.

## Current known identity boundary

Even a reference fallback can yield `cell.parent is ws == False`, because the cell belongs to a real worksheet while `ws` remains a proxy. This remains a known semantic limit rather than a fixture counted as a passed direct observation. Phase 8A must not claim to repair general proxy identity.
