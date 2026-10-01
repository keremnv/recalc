# Product anatomy audit — `librecalc-agent 0.2.0rc1` (read-only)

Source: implementation files under `src/librecalc_agent/` only. No research
document was used as authority. No code was changed. Line references are to the
audited tree.

Scope files: `runner.py`, `config.py`, `_bootstrap/sitecustomize.py`,
`_frozen/{eligibility,index,substrate,runtime,reads,capture,delta,validate}.py`,
plus `cli.py`, `diagnostics.py` where needed to trace the invocation path.

---

## 1. Exact lifecycle of `librecalc-agent run --workdir <dir> task.py`

Two OS processes are involved: the **parent** (`librecalc-agent` CLI process) and
the **child** (plain `sys.executable task.py` subprocess). The phases below are in
exact code order (`cli.py:main` → `config.load` → `runner.run` → subprocess →
post-processing).

### Parent, pre-execution

1. **Config loading** (`cli.py:53`, `config.py:load`). Defaults first
   (`enabled/substrate/candidate_a/capture=True`, `verbosity=normal`,
   `cache_dir=$XDG_CACHE_HOME/librecalc-agent` or `~/.cache/librecalc-agent`).
   If `--config`/`LIBRECALC_CONFIG` is set, the TOML must contain exactly one
   `[runtime]` table with known keys and bool/enum-typed values; any failure
   yields `enabled=False` plus a WARNING issue (fail closed). `--no-runtime`
   forces `enabled=False`. Derived properties: `reads = enabled ∧ substrate ∧
   candidate_a`; `assurance = enabled ∧ capture`.
2. **Preflight gates** (`runner.py:25-33`). Resolve script/workdir; both must
   exist (`ProductError` otherwise — nothing runs). `openpyxl` must import in
   the parent environment. `--require-libreoffice` checks for a
   `libreoffice`/`soffice` binary via `--version` (detection only).
3. **Cache/run-directory creation** (`runner.py:36-49`). `run_id = uuid4hex`;
   `writable(cache)` mkdirs the cache and probes it with a temp file. On
   success, `run_dir = <cache>/runs/<run_id>/` is created. On any failure,
   `cache_ok=False`, `substrate` is forced off for this run, and a
   `{"stage": "cache"}` fallback record is added. Every invocation gets a fresh
   UUID directory; no prior run directory is ever consulted.
4. **Environment scrub** (`runner.py:51`). The child environment is copied from
   `os.environ` minus every `CANDIDATE_A_*` variable and `LIBRECALC_RUN_CONTEXT`.
   No inherited research treatment can leak into the child.
5. **Script eligibility/classification** (`runner.py:54-57`). Only if
   `config.reads and cache_ok`. The script source is read as UTF-8 and passed to
   `_frozen.eligibility.classify()` (pure static analysis; never executes the
   script). Decision is `A1_ADMIT`, `PREDECLARED_REAL_OPENPYXL`, or `DISABLED`
   (when the whole block is skipped). Non-admit decisions skip steps 6–9
   silently — no index, no env, no bootstrap.
6. **Index/substrate preparation** (`runner.py:58-77`). Only on `A1_ADMIT`:
   `index.reset()` clears all in-process parent index state; index-module logging
   is silenced unless verbose; then `substrate.prepare(workdir, run_dir/"index",
   "product_run", ["CANDIDATE_A"])` (see §3). Per-workbook failures are recorded
   into `manifest["failures"]` and copied into the run's `fallback` list; they
   do not abort the run. Any exception in the whole setup block is caught,
   recorded as `{"stage": "runtime_setup"}`, and `LIBRECALC_RUN_CONTEXT` is
   removed from the child env.
7. **Environment variables created** (`runner.py:78-84`). Only on the admit path:
   `CANDIDATE_A_ARM="H1"`, `CANDIDATE_A_SUBSTRATE_MANIFEST=<run_dir>/index/manifest.json`,
   `LIBRECALC_RUN_CONTEXT={"script": <resolved script>, "events":
   <run_dir>/runtime.jsonl, "verbose": bool}`. If publication failed,
   `CANDIDATE_A_SUBSTRATE_DISABLED` is forwarded so the child ignores the manifest.
8. **PYTHONPATH modification** (`runner.py:83-84`). The child's `PYTHONPATH` is
   prefixed with `<pkg>/_bootstrap` then `<pkg>/..` (i.e. `src/`), preserving any
   existing value. This makes `sitecustomize` importable and `librecalc_agent`
   importable in the child.
9. **Pre-execution capture snapshot** (`runner.py:90-100`). Independent of the
   read path: if `config.assurance`, `capture.snapshot_xlsx(workdir)` reads the
   full bytes of every `*.xlsx` under workdir **recursively** (skipping `*.tmp`
   names and unreadable files) into a `{relpath: bytes}` dict held in parent
   memory. Failure → `{"stage": "capture_setup"}` fallback; the script still runs.
10. **Child launch** (`runner.py:104-105`). Exactly one
    `subprocess.run([sys.executable, script, *args], cwd=workdir, env=env)`.
    stdout/stderr/exit code are the script's own. Nothing is rerun.

### Child process

11. **Child startup + `sitecustomize` activation**
    (`_bootstrap/sitecustomize.py:boot()`, executed at interpreter startup because
    `_bootstrap` is on `PYTHONPATH` and Python auto-imports `sitecustomize`). If
    `LIBRECALC_RUN_CONTEXT` is absent/unparseable → silent return (pure reference
    Python). **Script-identity guard**: if `Path(sys.argv[0]).resolve()` != the
    classified script path → silent return. This is what confines interposition to
    the one launched file: nested interpreters and child scripts that inherit the
    environment still execute plain openpyxl.
12. **openpyxl interception** (`sitecustomize.py:20-36`, `runtime.py:main` →
    `install()`). `import openpyxl` runs now (inside the child, at startup);
    the original `openpyxl.load_workbook` is saved; `runtime.emit` is replaced
    with a filtering file-appender bound to `run_dir/runtime.jsonl`; then
    `runtime.main()` runs. Since the parent always sets `CANDIDATE_A_ARM="H1"`,
    `install()` executes: it reads the manifest (unless disabled/corrupt, in
    which case manifest={} plus a `manifest_initialization` fallback event), builds
    a `SharedLoader`, and **rebinds the module attribute
    `openpyxl.load_workbook`** process-globally. Every subsequent import of
    openpyxl in this process sees the interposed loader, including the task
    script's own `import openpyxl` and any library it imports.
13. **Admitted read execution** (`runtime.py:SharedLoader.load_workbook`).
    Per call, the loader admits only: `filename` is str/PathLike, no positional
    extras, `data_only/read_only/write_only` all absent-or-False, suffix
    `.xlsx`/`.xlsm`, no other kwargs, and `CANDIDATE_A_FORCE_REAL` unset. On
    admit, the resolved absolute path is looked up in the manifest; a
    `PersistentCompiledSnapshot` attaches the parent-published SQLite file
    read-only plus a freshness handshake (see §4); a `ProxyWorkbook` is returned.
    Anything else → the original loader is called with the **exact original
    arguments** after emitting a `PREDECLARED_FALLBACK` witness event.
14. **Fallback/escape inside reads** (`reads.py`). Proxy objects serve a narrow
    read surface from the snapshot; every other attribute/method escapes to a
    lazily materialized real openpyxl workbook (`_real_workbook()`, loaded once
    with `(path, data_only=False)`). A module-level guard loop wraps every
    proxied member: any exception during an indexed read retires the snapshot
    (invalidates handle, closes the DB, records workbook path in
    `loader.disabled`, emits `substrate_fallback`) and the same operation is
    retried against the real object. Retirement is one-way and per-workbook-path
    within the child process.
15. **Workbook writes**. Nothing in the read path intercepts writes. `wb.save()`
    and cell assignment always execute against real openpyxl objects — either
    because the script was never admitted (any save/assignment text blocks
    admission, see §5) or because write-shaped access escapes the proxy to the
    real workbook. The runtime never writes workbook bytes itself pre- or
    mid-execution.

### Parent, post-execution

16. **Post-execution capture** (`runner.py:106-114`). If the pre-snapshot exists,
    `capture.capture_wrap_timed(workdir, pre, run_id, "PRODUCT", 1)` re-snapshots
    workdir bytes, diffs per relative path, derives a `WorkbookDelta` per changed
    file, rewrites the identical post bytes atomically (tmp + `os.replace`),
    validates mechanically, and replays the delta as a self-check (see §9).
    Byte-identical files are skipped; deleted files yield a telemetry row without
    a delta. Any exception → `{"stage": "capture"}` fallback; **Python-produced
    files are always retained, never reverted, never repaired, script never
    rerun.**
17. **Event collection** (`runner.py:115-125`). The parent reads
    `run_dir/runtime.jsonl` line by line (tolerating absence/corruption) and folds
    child `substrate_fallback` events into the run's `fallback` list. A single
    WARNING is printed if any child fallback occurred.
18. **Summary generation** (`runner.py:126-131`). `summary` dict: `run_id`,
    `returncode`, `runtime_enabled`, `read_gate` (classifier decision),
    `accelerated_loads` (count of `status == "ACCELERATED"` events — only
    `load_workbook` accelerations survive the child's emit filter, so this is a
    load count), `compiled_workbooks` (manifest entry count), `capture_enabled`,
    `capture_records`, `capture_failures`, `fallback` (full list), `log_dir`.
19. **Diagnostic persistence** (`runner.py:132-145`). `summary.json` and
    `capture.json` are written into the run dir; `last_run.json` is written
    atomically (temp file + `os.replace`) at the cache root, last-writer-wins.
    Write failure only warns; task output and exit code are unaffected.
20. **Lifetime/cleanup of derived state**. Nothing is cleaned up by the product:
    the run dir (manifest, SQLite files, logs) persists in the cache
    indefinitely; the parent's in-memory index is dropped on process exit; the
    child's read-only SQLite handles close on process exit (proxies never close
    them explicitly). Cache retention is manual; there is no eviction code.

---

## 2. The computed substrate (state materialized before execution)

Built by `substrate.prepare()` in the parent, only on the admit path.

### Workbook discovery

`sorted(workdir.glob("*.xlsx"))`, skipping names containing `".tmp"`. Top level
only (non-recursive), `.xlsx` only. Each path is resolved to an absolute string;
that string is the manifest key and the child's lookup key.

### Per-workbook materialization

For each discovered workbook, `index.ensure_fresh(resolved)` runs. Because the
parent always calls `index.reset()` first, `_state` is empty, so `build_index()`
always runs (`rebuilt=True`):

1. `generation = sha256(entire file bytes)`.
2. Tombstone check: a recorded `_failures[path]` entry for this generation (or
   unknown generation) vetoes the build (`SubstrateDisabled`).
3. All prior in-process snapshots/handles for the path are retired and closed.
4. The workbook is parsed with **reference openpyxl itself**:
   `openpyxl.load_workbook(path, data_only=False, read_only=True)`.
5. An **in-memory** SQLite database is populated (see schema below).
6. A `substrate_identity` completion row is committed **with** the data rows.
7. The file is re-hashed; any mid-build byte change aborts the build.
8. The in-memory DB is published to `<run_dir>/index/<sha256>.sqlite` via
   `sqlite3.Connection.backup()` to a temp file + atomic `os.replace` (skipped
   only if `rebuilt` is False and the file already exists — unreachable in the
   public lifecycle since every run rebuilds into a fresh directory).

Any exception at any stage calls `index.disable()`: state/handles dropped and
closed, a `substrate_fallback` event recorded in `manifest["failures"]` and the
module tombstone map, and preparation continues with the next workbook.

### SQLite schema (all four tables, both indexes)

| Table | Columns | Contents | Consumed in product by |
| ----- | ------- | -------- | ---------------------- |
| `cells` | `sheet TEXT, addr TEXT, row INT, col INT, value TEXT, formula TEXT, dtype TEXT` | One row per non-empty cell: value stringified (`str(v)`), formula text for `data_type=="f"` cells (array-formula objects via their `.text`), openpyxl dtype string | `snapshot.row/value/dtype` — the only tables the read path queries |
| `anchors` | `term TEXT, sheet TEXT, addr TEXT` | Lowercased alphanumeric tokens of every value/formula string | **Nobody in product** (built, never queried) |
| `temporal` | `label TEXT, sheet TEXT, addr TEXT, row INT, col INT` | Regex matches (FY/CY/Q/month/year patterns) over string values | **Nobody in product** (built, never queried) |
| `substrate_identity` | `workbook_hash TEXT, index_generation INT` | Single completion-marker row: source file hash + per-path build counter | Child attach handshake (`runtime.py:45-46`) |

Indexes: `ia ON anchors(term)`, `ic ON cells(sheet, row, col)`.
(`ic` exists but the product query filters on `(sheet, addr)` — the index does
not cover the actual lookup columns.)

### Manifest (`<run_dir>/index/manifest.json`)

Written twice, atomically (temp + replace) both times: first as an empty
revocation record **before** any build (so a crash can never leave a stale
publication behind), then with the final content: `workbooks{resolved_path:
{path, db_path, workbook_hash, index_generation, rebuilt, ensure_s, backup_s,
freshness_s}}`, `refreshes[]` (same entry objects), `failures[]` (fallback
events), `phase` (`"product_run"`), `serves_roles` (`["CANDIDATE_A"]`), totals
(`total_s/ensure_s/backup_s`, `n_workbooks`, `n_rebuilt`, `db_bytes`).

### Determinism, storage, lifetime, authority

- **Deterministic**: yes for all semantic content — row contents/order derive from
  openpyxl's parse order and fixed SQL; hashes are SHA-256. Only the `*_s`
  timing fields are non-deterministic (diagnostic only).
- **Stored**: parent memory (in-memory SQLite, dropped at exit) + `<run_dir>/index/`
  (`manifest.json`, `<sha>.sqlite` files; persisted indefinitely, never evicted).
- **Lifetime**: one invocation. Recomputed from scratch every run (fresh UUID dir
  + `index.reset()`).
- **Authority**: never authoritative. The `.xlsx` file bytes are the authority;
  the substrate is a derived, hash-pinned copy that is discarded on any mismatch.
- **Consumers**: the child process only (`PersistentCompiledSnapshot` attach +
  `cells` queries). The parent never serves reads from it.

### Per-snapshot child-side state (not precomputed; parsed in the child)

`WorkbookMetadata` is constructed per snapshot **in the child** by parsing the
workbook's raw zip XML directly (`xl/workbook.xml`, rels, each sheet XML) — not
from SQLite. It holds `sheetnames`, per-sheet `(min_col,min_row,max_col,max_row)`
bounds derived from actual `<c>` refs plus merged refs (mirroring openpyxl's
materialized-cell rule, not the XML dimension declaration), `dimension_text`,
merged ranges, and per-cell raw XML types. It raises `NotImplementedError` on
non-worksheet parts, which routes into snapshot-init failure → disable + fallback.

---

## 3. Workbook identity and freshness

- **Identity** = resolved absolute path string (manifest/dict key) **plus**
  SHA-256 over the complete file bytes (`workbook_hash`). No path-only trust, no
  mtime/size shortcut: every freshness decision re-reads and re-hashes the whole
  file (`index.workbook_hash`).
- **Fresh** = current file bytes hash equals the generation the derived state was
  built from. Checked at four points: parent pre-build (`ensure_fresh`), parent
  post-build ("workbook changed during index construction"), child attach
  (pre-hash, `substrate_identity` row equality, post-hash), and per child load
  for already-attached snapshots (rehash vs snapshot handle).
- **Invalidation** = any byte change, any read/parse/SQLite failure, any
  `substrate_identity` mismatch, any missing manifest entry, or any exception
  inside a proxied read (guard retirement). All roads lead to `index.disable()`,
  which drops/closes state, plants a tombstone keyed by path+generation, and
  emits `substrate_fallback`.
- **Freshness unestablishable** (file unreadable, hash raises) → `SubstrateDisabled`
  → ordinary openpyxl for that scope. The tombstone with `workbook_generation=None`
  vetoes all future attempts for that path in the process.
- **Surviving workbook mutation**: no. Mutation changes bytes → hash mismatch →
  fallback (child) or rebuild (parent `ensure_fresh`, reachable only within one
  parent process lifetime).
- **Surviving another product invocation**: no. Fresh UUID run dir + `index.reset()`
  + unconditional rebuild; the child never consults a previous run's manifest
  (its manifest path points at the current run dir by construction).
- **Deliberate rebuild vs accident**: the *mechanism* (fresh dir + reset +
  rebuild) is explicit code, so per-run rebuild is the implemented lifecycle;
  whether it is *intended policy* is not stated anywhere in the implementation.
- **Reuse capability in the code**: yes, unexercised. `ensure_fresh` returns the
  existing handle with `rebuilt=False` when the hash matches; `prepare` skips the
  SQLite backup when not rebuilt and the file exists; generations and tombstones
  are designed for a persistent shared directory. The public lifecycle never uses
  any of this: parent state starts empty every run, and the child never calls
  `ensure_fresh` — it only attaches to the exact published generation or falls back.

Implementation capability (incremental in-process / persistent-dir reuse exists) vs
public product lifecycle (always rebuild, never reuse) must not be conflated in
public wording.

---

## 4. Eligibility / admission (`eligibility.py`)

`classify(source)` runs `A1Analyzer(source).analyze()` — pure `ast` static
analysis plus preserved lexical rules. It never imports, executes, or rewrites code.

### What it examines

1. **Name-flow tracking** (`_walk_statements`, single pass over module-level
   statements, descending into `for/while/if/with/try` bodies, `orelse`,
   handlers, `finalbody`): builds proven-name sets — `workbooks` (assigned from
   any `*.load_workbook(...)` call), `worksheets` (proven-workbook subscripted by
   string literal), `cells` (proven-worksheet subscripted by colon-free string
   literal), `cell_functions` (proven-worksheet `.cell` bound method). Name
   aliases propagate (`wb2 = wb`). `FunctionDef/AsyncFunctionDef` anywhere →
   `OBJECT_ESCAPE_BOUNDARY` blocker (never descended into).
2. **Load-mode blockers**: any `load_workbook` call with `data_only/read_only/
   write_only=True`, any other keyword, or more than one positional arg.
3. **Full-tree operation scan**: subscripts on proven worksheets (const string
   without colon = admitted single-cell; colon/`Slice` = `RANGE_OBJECT_BOUNDARY`;
   dynamic = uncertainty); subscripts on proven workbooks (const string = sheet
   lookup; dynamic = uncertainty); `ws.cell(...)` calls; `iter_rows` (only
   literal `values_only=True` admitted, anything else =
   `CELL_OBJECT_ITERATION_BOUNDARY`); `iter_cols` (always blocked); `dir/getattr/
   eval/exec` applied to proven objects; **any call receiving a proven object as
   a positional argument** (`OBJECT_ESCAPE_BOUNDARY`); `wb.worksheets` /
   `wb.active` / rich-style attributes on proven objects; `ws.sheet_state`;
   **any** call whose function leaf name is `save` (`WRITE_BOUNDARY`, regardless
   of receiver); attribute/subscript assignment into proven objects
   (`READ_WRITE_MIXED_BOUNDARY`); returning a proven object.
4. **Preserved A0 lexical rules** (case-insensitive substring/regex over raw
   source; all become blockers except the range/slice regex, which the AST proof
   supersedes): `.save(`, `data_only=true`, `read_only=true`, `write_only`,
   `zipfile`, all rich-object attributes, `.worksheets`, `.active`,
   **`.iter_rows(`, `.iter_cols(`, `.values`**, `.value =`, `eval(`, `exec(`,
   `def `, `lambda`, bracket-colon regex, `wb/ws/cell/c[…]=` regex.

Any single blocker → `PREDECLARED_REAL_OPENPYXL` (with the first blocker's reason).
No source / no `openpyxl` substring / syntax error → `PREDECLARED_REAL_OPENPYXL`
with `STATIC_ANALYSIS_UNCERTAINTY`. Otherwise → `A1_ADMIT`.

### The property actually established

A **syntactic confinement** property, approximated: *every statically visible
workbook-object flow in the module stays within the proxy-supported read surface —
default-mode loads, literal sheet lookup, literal single-cell or int row/col reads,
`.value/.data_type/max_row/max_column/dimensions` reads — and no workbook object
crosses an unobservable boundary (function definition, call argument, return,
dynamic subscript/inspection, write, save, iteration text, rich attribute).* It
proves nothing about runtime values: file paths, sheet names, and coordinates are
all resolved dynamically and re-checked by the proxy at runtime (`KeyError` parity
for unknown sheets).

### Granularity and blind spots (code-visible)

- Admission is **whole-script**: one decision gates interposition for the entire
  child process. Per-load/per-operation fallback still applies at runtime.
- Applies to the launched script file only. Imported modules are not classified;
  they execute under whatever loader is installed process-wide.
- Child/nested processes are explicitly **not** authorized (argv-identity guard).
- Notable consequence of the lexical layer: **any source text containing
  `.iter_rows(` is rejected**, so the runtime's indexed `iter_rows(values_only=True)`
  path is unreachable for scripts admitted through this classifier. `ClassDef`
  bodies are neither name-tracked nor blocked as a construct (only their lexical
  contents can trip rules) — an uncertain case.
- Assumptions: single-pass name resolution is sound; attribute/subscript stores
  cover all mutation shapes; anything unrecognized fails closed via lexical rules.

---

## 5. Runtime injection mechanism

The child environment carries three things: `CANDIDATE_A_ARM="H1"`,
`CANDIDATE_A_SUBSTRATE_MANIFEST=<run_dir>/index/manifest.json`, and
`LIBRECALC_RUN_CONTEXT={script, events, verbose}` (+ optionally
`CANDIDATE_A_SUBSTRATE_DISABLED`), with `PYTHONPATH` prefixed by
`<pkg>/_bootstrap` and `<pkg>/..`.

At interpreter startup, Python auto-imports `sitecustomize` from the first
`PYTHONPATH` entry; `boot()` runs before the task script. After the context/identity
checks it imports openpyxl (first import happens here, in the child), saves
`openpyxl.load_workbook`, overrides `runtime.emit` with the filtering
`runtime.jsonl` appender, and calls `runtime.main()` → `install()`, which rebinds
the **module attribute** `openpyxl.load_workbook` to `SharedLoader.load_workbook`.

Properties (all code-visible):

- Replacement is **global within the child process**: any module — script or
  library — that calls `openpyxl.load_workbook` (or `from openpyxl import
  load_workbook` executed after install) gets the interposed loader.
- The original is kept as `SharedLoader.real_loader` and as a closure/local for
  exact-argument fallback; it is restored only on bootstrap/install failure
  (sitecustomize restores on exception; `runtime.main` restores if `install()`
  raises mid-rebind). On success it is never restored.
- Imported modules see the interposed version. Nested Python processes inherit the
  environment (including `PYTHONPATH`) but the argv-identity guard returns early,
  so they run pure reference openpyxl. Child *scripts* (a different `sys.argv[0]`)
  are never authorized.
- No bytecode rewriting, no import hooks, no `sys.modules` patching, no
  sitecustomize installed outside this process (the file lives in the package and
  is reachable only via the constructed `PYTHONPATH`).

**Recommended label: process-local interface-preserving interposition** (short form:
*process-local interposition*). Why: the mechanism is exactly one module-attribute
rebind (`openpyxl.load_workbook`) confined to a single OS process by construction
(env scrub + argv guard), preserving the callee's interface (identical call
signature, openpyxl-compatible return objects, exact-argument fallback). "Library
interposition" is accurate but less precise about scope; "transparent" is accurate
operationally (no caller change required) but "transparent" alone doesn't convey the
process boundary that is the mechanism's main safety property; "instrumentation"
undersells it (it serves values, not just observes). Avoid "compiled" and
"candidate" in public wording (see §8).

---

## 6. Read-path mechanics

`SharedLoader.load_workbook` gate (per call): str/PathLike filename, no extra
positionals, `data_only/read_only/write_only` all absent-or-False, suffix
`.xlsx`/`.xlsm`, no other kwargs, `CANDIDATE_A_FORCE_REAL` unset, path present in
manifest, path not in per-process `disabled`, snapshot attach handshake passes.
Note the suffix asymmetry: the loader accepts `.xlsm`, but `prepare()` only globs
`*.xlsx`, so **`.xlsm` loads can never find a manifest entry and always fall back**.

Per-operation support (traced through `reads.py` + the guard loop at `reads.py:357`):

| Operation | Original | Runtime behavior | Mark |
| --------- | -------- | ---------------- | ---- |
| `load_workbook(path)` default flags, indexed `.xlsx` | full openpyxl parse | manifest lookup + read-only SQLite attach + `ProxyWorkbook` | `INDEXED` |
| `load_workbook` with `data_only/read_only/write_only=True`, extra args/kwargs, non-xlsx suffix, unknown path, stale bytes, prior failure | same | exact-argument call to saved original; `PREDECLARED_FALLBACK` witness | `REFERENCE` |
| `wb.sheetnames` | workbook property | served from child-parsed `WorkbookMetadata` | `INDEXED` |
| `wb["Sheet"]` (str, known) | worksheet | `ProxyWorksheet` | `INDEXED` |
| `wb["Nope"]` / non-str | `KeyError` | `KeyError(name)` (parity) | `INDEXED` |
| `wb.worksheets`, `wb.active`, any other attr | objects | escape to lazily materialized real workbook | `REFERENCE` |
| Workbook iteration (`for ws in wb`, `len(wb)`, etc.) | openpyxl dunders | **ProxyWorkbook defines no `__iter__`/`__len__`; implicit dunder lookup bypasses `__getattr__` fallback** | `KNOWN_EDGE_CASE` |
| `ws.max_row/max_column` | int | served from metadata bounds | `INDEXED` |
| `ws.dimensions` / `calculate_dimension()` | str | served from metadata text | `INDEXED` |
| `ws["A1"]` (colon-free coordinate) | cell | `ProxyCell` via `.cell()` | `INDEXED` |
| `ws["A1:B2"]`, slices, unparseable keys | range/cell | escape to real sheet (`__getitem__`) | `REFERENCE` |
| `ws.cell(row, col)` ints ≥ 1, non-merged | cell | `ProxyCell` | `INDEXED` |
| `ws.cell(...)` in merged range / bad args | cell / `ValueError` | merged → real cell object (escape); bad args → `ValueError` parity | `CONDITIONAL` |
| `cell.value` | value or formula str | single `cells` query + `decode_row` (`n`→int/float, `b`→bool, `d`→datetime/date/time tried in order, `f`→formula text, missing→None) | `INDEXED` |
| `cell.data_type` | str | `cells` query, falling back to raw-XML type map, default `"n"` | `INDEXED` |
| `cell.<anything else>` | styles, font, etc. | escape to real cell | `REFERENCE` |
| `iter_rows(values_only=True)` bounded or full | generator of tuples | indexed generator; **per-cell merged check routes merged cells to real reads mid-stream** (mixed serving) | `CONDITIONAL` |
| `iter_rows` unbounded on empty sheet | openpyxl semantics | forced real ("empty unbounded iterator" — deliberate parity escape) | `REFERENCE` |
| `iter_rows(values_only≠True)`, `iter_cols` | cell tuples | forced real | `REFERENCE` |
| (script-level) any `iter_rows` text | — | classifier rejects the whole script (lexical rule), so indexed `iter_rows` is unreachable via admitted scripts | `KNOWN_EDGE_CASE` |
| `data_only=True` | cached values | never indexed; loader-level fallback (and classifier-level rejection) | `REFERENCE` |
| writes (`save`, cell assignment) | mutation | always real openpyxl (never served, never intercepted) | `REFERENCE` |
| array-formula cells | openpyxl `ArrayFormula` objects | index build reads `.text`; served as formula strings | `KNOWN_EDGE_CASE` |

Fallback granularity: per **operation** for unsupported members (escape to the
shared lazily-built real workbook — one real parse per proxy, reused afterwards);
per **workbook path** for retirement (guard failure → `disabled` set → all future
loads of that path in the process go real); per **process** for manifest/bootstrap
failure. Fallback is one-way; nothing re-admits a retired path.

---

## 7. Reference fallback, mechanically

"Fallback to ordinary openpyxl" means: call the saved original
`openpyxl.load_workbook` and return whatever it returns. Three distinct sites:

1. **Load-time** (`SharedLoader`, `PREDECLARED_FALLBACK`): original called with
   the **exact** `(filename, *args, **kwargs)` the caller passed. A witness event
   is emitted *before* the call so a reference-side exception still leaves a trace.
2. **Escape-time** (`ProxyWorkbook._real_workbook`): the real workbook is loaded
   once per proxy as `original(path, data_only=False)` — kwargs normalized, not
   forwarded. Equivalent here only because the load gate already excluded every
   non-default flag; worth noting as the one place fallback is *not* literally
   argument-identical (plus `PathLike` becomes `str`, same file).
3. **Guard-time** (`_guard_compiled_read`): on any indexed-read exception the
   snapshot is retired (handle invalidated, DB closed, path disabled process-wide,
   `substrate_fallback` emitted) and the identical member is invoked on the real
   object.

Yes, fallback can occur after partial indexed execution (per-operation escape and
mid-stream guard retirement, including inside `iter_rows` generators). A proxy never
*becomes* real — it holds a `_real` peer it delegates to; previously returned
`ProxyCell`/`ProxyWorksheet` objects keep working through delegation. Fallback is
one-way. Writes are always reference openpyxl. Indexed-setup failure before launch
(no manifest/env published, or exception) yields a child with no interposition at
all. Bootstrap failure inside the child restores the original loader and records
`product_bootstrap` fallback. Unsupported behavior mid-operation retires the
workbook's indexed path for the rest of the process.

Weaker-than-equivalence points (code-visible): the `_real_workbook` kwarg
normalization above; `ProxyWorkbook.close()` closes only the materialized real
workbook (the read-only SQLite handle stays open to process exit — a resource-lifetime
difference, not a semantic one); missing proxy dunders (`__iter__` et al.) raise
instead of delegating — the one place "fallback" does not happen at all.

---

## 8. Capture subsystem

Independent of the read path; gated only by `config.assurance`. Record-only:
it observes bytes, never influences them.

- **Pre-state**: `snapshot_xlsx(workdir)` — full bytes of every `*.xlsx` found by
  **recursive** `rglob` (note: index discovery is top-level-only; capture covers
  subdirectories too), keyed by workdir-relative path, held in parent memory.
  `.tmp` names and unreadable files skipped silently.
- **Post-state**: same snapshot function re-run after the child exits.
  Byte-identical paths are skipped entirely (no record). Paths present only in
  post are `created`; only in pre are `deleted` (telemetry row, no delta).
- **Delta** (`derive_delta`): a **zip-part-level** diff. Changed parts store full
  post bytes + pre/post hashes + `normalized` flag + `deleted` flag; unchanged
  part names listed; `opaque_preserved` = unchanged non-`is_normalized_part`
  parts. `cell_effects` exists in the dataclass but is **always empty in
  product** (the single call site passes no effects). Captured categories in
  practice: workbook/package part inventory only — no cell values, formulas,
  styles, dimensions, or sheet structure are captured as such.
- **Normalization**: none is performed. `is_normalized_part` merely *labels*
  `xl/workbook.xml`, `xl/worksheets/*`, `xl/sharedStrings.xml`, `xl/styles.xml`;
  all comparisons (`f1`, `captured_equals_committed`) are byte-exact part
  equality. (`NORMALIZED_SUFFIXES` is defined but never referenced.)
- **Validation** (`validate_mechanical`, six checks): `exists` (non-empty),
  `readable` (zip opens with entries), `persisted` (committed hash ==
  Python-produced post hash), `serialization_valid` (`testzip` clean +
  `[Content_Types].xml` parses), `relationships_preserved` (every internal
  `.rels` target resolves), `captured_equals_committed` (delta replayed onto
  pre-state reproduces committed bytes part-for-part). `passed = all(checks)`.
  No formula/task/target semantics anywhere (stated in the module docstring).
- **Replay**: `replay_delta` exists in product code and genuinely reconstructs
  post bytes (changed parts from stored images, all other pre parts carried over;
  rebuilt with sorted names + `ZIP_DEFLATED`, so the *bytes* differ from the
  original zip even when parts match — comparisons are part-wise for this reason).
  It is used **only as a self-check** (`f1_part_exact`); replay is not exposed,
  served, or applied to any user-visible file.
- **Failure semantics**: output is always retained; nothing is reverted, repaired,
  or rerun. `runtime_failure = (not f1) or (committed_b != b)` is recorded in the
  row. The "commit" step itself only rewrites the identical post bytes atomically
  (tmp + `os.replace`) — a durability no-op, not a semantic commit.

---

## 9. Provenance and diagnostics

| Artifact | Contents | Values? | Audience | Lifetime | Authority | Affects execution? |
| -------- | -------- | ------- | -------- | -------- | --------- | ------------------ |
| `runs/<id>/runtime.jsonl` | Child events: `bootstrap/INSTALLED`, per-load `ACCELERATED` / `PREDECLARED_FALLBACK` (with reason, flags, generations, durations), `substrate_fallback` records. Per-operation accelerations are filtered out; `result/value/repr` keys stripped | No | Operator / parent summary | Indefinite (manual cleanup) | Telemetry | No (parent only counts) |
| `runs/<id>/capture.json` | Per changed/deleted workbook: ids, pre/post hashes, `created`, `f1` flags, preserved-part names, validation dict + pass, `runtime_failure` | No (hashes + part names only) | Operator | Indefinite | Provenance record | No (written, never read back in product) |
| `runs/<id>/summary.json` | Run roll-up: returncode, gate decision, accelerated-load count, manifest workbook count, capture counts, full fallback list | No | Operator / `status` | Indefinite | Telemetry | No |
| `<cache>/last_run.json` | Atomic copy of the latest summary | No | `status` command | Until next run (last-writer-wins, no locking) | Telemetry cache | No |
| `runs/<id>/index/manifest.json` | Publication record: per-workbook paths/hashes/generations/timings, failures, totals | No | Child runtime + operator | Indefinite | Derived state | **Yes — the only diagnostic-ish file the child consults** |
| `runs/<id>/index/*.sqlite` | Derived cell/anchor/temporal tables + identity row | Yes (cell values/formulas as text) | Child runtime | Indefinite | Derived, hash-pinned | Yes (serves indexed reads) |

Distinctions: **workbook state** = the `.xlsx` bytes in workdir (sole authority,
only ever written by the user's script and the atomic capture rewrite of identical
bytes). **Derived state** = SQLite + manifest + in-memory handles (hash-pinned,
discarded on mismatch). **Execution telemetry** = runtime.jsonl/summary/last_run
(counts, timings, fallback reasons; never workbook content). **Evidence/provenance**
= capture.json rows + validation reports (hashes and part names witnessing what the
script produced; not correctness verdicts).

---

## 10. What the model actually sees

The model generates plain openpyxl Python before `librecalc-agent run` executes it.

Model-specific knowledge required: **none**. Concretely:

- Is any computed substrate inserted into the LLM prompt/context? **No.**
- Does the model receive a custom spreadsheet representation? **No.**
- Does the model call a LibreCalc-specific workbook API? **No** (`lx_helpers`
  exists as an optional import but is reference-openpyxl only, never required).
- Must the model choose indexed vs reference reads? **No** — admission is static
  and invisible; per-operation routing is automatic.
- Must the model reason about freshness? **No.**
- Must the model create an edit plan? **No.**
- Must the model describe mutations before executing them? **No.**

Invisible to the model (all computed/done by the product): eligibility
classification, per-run index build + manifest publication, `PYTHONPATH`/env
construction, `sitecustomize` boot + loader rebind, proxy serving, guard
retirement, escape-to-real fallback, pre/post byte snapshots, delta derivation,
mechanical validation, replay self-check, and all telemetry. The only channel by
which runtime existence can leak to the model is incidental: parent `WARNING`
lines on stderr (visible only if the invoking agent surfaces stderr) and timing.

---

## 11. Product anatomy table

| Component | Computed from | Produced state | Consumer | Model-visible? | Can affect semantics? | Fallback |
| --------- | ------------- | -------------- | -------- | -------------- | --------------------- | -------- |
| Eligibility classifier | Script source text (AST + lexical) | `A1_ADMIT` / `PREDECLARED_REAL_OPENPYXL` + reasons | `runner` (gate) | No | No (routing only; admit enables interposition, never changes script) | Non-admit → pure reference run |
| Index builder | Workdir `*.xlsx` bytes via reference openpyxl parse | In-memory SQLite + `<sha>.sqlite` files | Child snapshots | No | No (derived copy; mismatches discarded) | Per-workbook failure → real loads |
| Substrate manifest | Build outcomes | `manifest.json` (paths, hashes, generations, failures) | Child loader | No | Yes (drives attach-or-fallback) | Missing/corrupt → all-real |
| Bootstrap (`sitecustomize`) | Env context + argv identity | Loader rebind in child | Child process | No | Yes (installs interposition) | Any failure → original restored |
| Read interposition (proxies) | Manifest + SQLite + raw package XML | Served values / bounds / names | Task script | No (interface-identical objects) | Yes (serves values; edge cases known) | Per-op escape, per-path retirement, one-way |
| Freshness logic | Full-file SHA-256 rehashes | Fresh/stale verdicts + tombstones | Loader, guards | No | Yes (gates serving) | Stale/unprovable → real |
| Capture snapshot | Workdir `*.xlsx` bytes (recursive) | In-memory `{relpath: bytes}` × 2 | Delta/validate | No | No (observation only) | Failure → script output kept, warning |
| Delta computation | Pre/post bytes | `WorkbookDelta` (part diff, in-memory; summary persisted) | Validate + `capture.json` | No | No | Failure → output kept |
| Validation | Pre/post/committed bytes + delta | 6-check report per workbook | `capture.json` | No | No (no gate consumes `passed`) | Failure recorded, output kept |
| Runtime telemetry | Loader/proxy/guard events | `runtime.jsonl`, `summary.json`, `last_run.json` | Operator, `status` | No (stderr warnings aside) | No | Lossy-tolerant (missing file = no events) |

---

## 12. Current vs historical terminology

| Identifier (where) | Actual current meaning | Public-facing? | Neutral replacement |
| ------------------ | ---------------------- | -------------- | ------------------- |
| `candidate_a` (config key, `CANDIDATE_A_*` env, `serves_roles`, code names) | The indexed-read interposition feature | Yes (config file, env, diagnostics strings) | `indexed_reads` / `read_index` |
| `substrate` (config key, module, manifest, events) | Derived per-run SQLite index + manifest + snapshot handles | Yes (config, `CANDIDATE_A_SUBSTRATE_MANIFEST`, fallback events) | `read_index` / `derived_index` |
| `compiled` (`compiled_substrate_available`, "Compiled reads", `compiled_workbooks`, `effective_compiled_serving…`) | Index-served (nothing is compiled to code) | Yes (CLI output, JSON) | `indexed` |
| `ACCELERATED` / `accelerated_loads` / `accelerated_served` | Served from the index (a routing label, not a speed measurement) | Yes (JSON, status text) | `index_served` / `served_loads` |
| `H1` (`CANDIDATE_A_ARM="H1"`) | "Interposition installed" — the only arm the product ever sets | No (child env only) | `interpose` / `standard` |
| `install_h0_spy`, `H0_COUNTERFACTUAL_*`, `CANDIDATE_A_A1_DECISION/REASON` | Dead control-instrumentation path: wraps loads with telemetry but always calls real openpyxl. Unreachable in product (runner always sets `H1`) | No | Remove or clearly mark experimental |
| `A1_ADMIT` / `PREDECLARED_REAL_OPENPYXL` (+ `read_gate`) | Classifier admit/reject decisions | Partially (`read_gate` in summary JSON) | `admitted` / `reference_only` |
| `CANDIDATE_A_FORCE_REAL`, `CANDIDATE_A_EXEC_TELEMETRY`, `CANDIDATE_A_TASK/RUN_ID` | Research-harness remnants honored by `_frozen` code (force-real short-circuits the load gate; telemetry path is the pre-override emit target) but never set by the product; runner strips inherited values | No | Remove or namespace as unsupported |
| `serves_roles`, `arm: "PRODUCT"`, `call_idx`, `task_id` | Experiment-telemetry field names reused in product records (always `"PRODUCT"`/`1`/`run_id`) | Partially (JSON records) | `context` / drop fixed fields |
| `optical`… n/a | — | — | — |

Also: `TelemetryPlaceholder` references a `telemetry.py` that does not exist in the
product; `runtime.observable_result` has no callers; base `CandidateALoader.
load_workbook` and base `CompiledSnapshot.__init__` are overridden/never invoked on
the product path (only `SharedLoader` + `PersistentCompiledSnapshot` execute).

---

## 13. Product reality vs architectural interpretation

## DIRECTLY IMPLEMENTED

- Whole-script static classifier (AST name-flow + lexical rules) gating
  interposition (`A1_ADMIT` / `PREDECLARED_REAL_OPENPYXL`).
- Per-run, top-level-`*.xlsx`, full-rebuild SQLite cell index + atomic
  `manifest.json` publication into a fresh UUID run directory.
- SHA-256 whole-file identity + rehash freshness checks (parent pre/post-build,
  child attach ×2, per-load rehash) with tombstoned fail-closed disable.
- Child-process loader rebind via `PYTHONPATH`-injected `sitecustomize` +
  argv-identity guard + env context; global `openpyxl.load_workbook` replacement
  within that one process.
- Proxy workbook/worksheet/cell objects serving sheet names, literal sheet/cell
  lookup, bounds, `.value`, `.data_type` from SQLite + child-parsed package
  metadata; guarded members with retire-and-delegate fallback; lazy real-workbook
  peer for everything else.
- Exact-argument reference fallback at load time; normalized (`path,
  data_only=False`) real-load fallback mid-flight.
- Post-hoc byte-snapshot capture (recursive `*.xlsx`), zip-part delta derivation,
  six-check mechanical validation, replay-as-self-check; record-only, output
  always retained.
- JSONL/JSON telemetry + provenance records (`runtime.jsonl`, `capture.json`,
  `summary.json`, `last_run.json`) with value-stripped child events.
- Optional reference-only helpers (`lx_helpers` → `_frozen.helpers`, fresh
  openpyxl read per call, no index contact).

## ARCHITECTURAL INTERPRETATION

Labels below are descriptive interpretations, not implementation identifiers:

- *Process-local interface-preserving interposition* — accurate gloss of the
  loader-rebind mechanism (§5).
- *Deterministic derived read index* — accurate gloss of the SQLite substrate
  (deterministic content, hash-pinned, non-authoritative).
- *Effect capture* — gloss of byte-snapshot + part-delta + validation (observes
  package-level effects only; captures no cell-level semantics in product).
- *Operator observability* — gloss of the telemetry/provenance files (counts,
  hashes, reasons — never workbook values except inside the derived SQLite files
  themselves).
- *Fail-closed freshness* — accurate gloss of the rehash + tombstone design.

---

## 14. Implementation-visible limitations

### CODE-VISIBLE LIMITATION

- Per-run index lifetime: fresh UUID dir + `index.reset()` + unconditional
  rebuild every invocation; no cross-invocation reuse on the public path (reuse
  machinery exists but is never exercised).
- Script-wide admission: one blocker anywhere (including any `.iter_rows` text,
  any `def`, any `.save(` text) disables interposition for the whole run.
- Indexed `iter_rows(values_only=True)` is unreachable via admitted scripts
  (lexical rejection); `.xlsm` is accepted by the loader gate but never indexed
  (`prepare` globs `*.xlsx` only) so always falls back.
- Proxy dunders missing: `ProxyWorkbook`/`ProxyWorksheet`/`ProxyCell` define no
  `__iter__`/`__len__`/etc.; implicit dunder use bypasses `__getattr__` escape
  (workbook iteration cannot delegate).
- Fallback is per-operation escape / per-path retirement / per-process disable,
  all one-way; guards close the SQLite handle on retirement.
- Merged cells always escape to real reads (including per-cell mid-`iter_rows`);
  empty-sheet unbounded `iter_rows` always real; all writes always real.
- Index discovery is top-level `*.xlsx` only; capture snapshots recursively —
  subdirectory workbooks are never indexed but are captured.
- No concurrency control: simultaneous writers, mid-run external mutation (hash
  mismatch → fallback, but TOCTOU windows exist between snapshot and use), and
  `last_run.json` last-writer-wins.
- No cache lifecycle: run dirs accumulate forever; no eviction code.
- `ProxyWorkbook.close()` never closes the read-only SQLite handle (lives to
  process exit).
- Capture observes package parts only (`cell_effects` always empty; no
  normalization performed despite the `normalized` flag); deleted files yield no
  delta; validation `passed` gates nothing.
- Dead weight / dead code in product: `anchors`/`temporal` tables built but never
  queried; `ic` index doesn't cover the actual `(sheet, addr)` lookup;
  `NORMALIZED_SUFFIXES` unreferenced; H0 spy, base loader/snapshot paths,
  `observable_result`, and `TelemetryPlaceholder` unexecuted.
- `CANDIDATE_A_FORCE_REAL`, if set inside the child at runtime by the script
  itself, is honored by the load gate (runner only strips inherited values).

### EMPIRICALLY OBSERVED LIMITATION

Per instructions, no new empirical claims are introduced here. The authoritative
record of observed limitations (packaged speed, admitted-read semantic edges in
workbook iteration and array-formula handling, warm reuse) is
`FINAL_CLAIM_REGISTRY.md` and the validation reports under `research/evidence/`;
several code-visible items above (proxy dunders, array-formula `.text` handling)
are consistent with those records but this audit asserts only their code presence.

---

## 15. Front-page factual building blocks

### ONE-SENTENCE PHYSICAL DESCRIPTION

`librecalc-agent run` executes an ordinary Python/openpyxl script in a subprocess,
optionally serving a narrow class of reads from a freshly built per-run workbook
index while everything else runs on real openpyxl, and afterwards records
byte-level observations of what the script produced.

### RUNTIME LIFECYCLE

Classify script (static) → build per-run index for top-level `.xlsx` files →
snapshot workdir bytes → launch one child Python with a startup hook that rebinds
`openpyxl.load_workbook` for that process only → run script once → diff bytes,
derive part-level deltas, validate mechanically → write run diagnostics. Derived
state lives exactly one invocation and is never reused.

### WHAT GETS COMPUTED

Per workbook: whole-file SHA-256 identity; an in-memory-then-file SQLite copy of
non-empty cells (address, stringified value, formula text, dtype) plus unqueried
token/temporal tables and an identity row; a JSON manifest binding paths to hashes
and generations; per-snapshot sheet names, bounds, merged ranges, and raw cell
types parsed from package XML in the child.

### HOW IT ENTERS EXECUTION

Via `PYTHONPATH` + environment into exactly one child process: a `sitecustomize`
startup hook verifies it is running the classified script file, then replaces the
`openpyxl.load_workbook` module attribute process-wide. No caller changes, no
import hooks, no bytecode changes; nested processes are neutralized by an
argv-identity guard.

### WHAT THE AGENT SEES

Nothing LibreCalc-specific: plain openpyxl scripts, plain openpyxl objects and
return values, ordinary stdout/stderr/exit codes. No prompt-inserted substrate, no
custom API to call, no read-mode choices, no freshness or planning obligations.

### WHAT THE OPERATOR CAN OBSERVE

Per-run directory with the publication manifest, derived SQLite files, a
value-stripped JSONL event log, per-workbook capture rows (hashes, part names,
six-check validation verdicts), and a JSON summary (also atomically copied to
`last_run.json`); `doctor`/`status` report configuration, dependencies, cache, and
the last run. No workbook values appear in any log except inside the derived
SQLite files.

### WHAT FALLS BACK

Non-admitted scripts (whole run); non-default load flags, unknown/stale/failed
workbooks (per load, exact-argument real call); unsupported members, merged cells,
ranges, iterations, writes (per operation, via a lazily built real workbook); any
indexed-read exception (per workbook path, one-way retirement for the process).

### WHAT IS NOT CLAIMED

No packaged speed claim; no broad exactness claim (known edges in workbook
iteration and array-formula handling); no token/cost/capability claims; capture is
mechanical observation, not a correctness verdict. (Boundary: `FINAL_CLAIM_REGISTRY.md`.)

---

*Read-only audit end. No product-improvement notes are offered — none were requested
beyond a separated section, and there is nothing that needs saying here that the
limitations section does not already state as fact.*
