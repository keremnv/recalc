# Phase 9 architecture decision

Status: selected before Phase-9 treatment implementation or scoring.

## Selected H1

Use an **early definite-reference branch inside the guarded script-process bootstrap**. Read the same config and script bytes; call the same frozen whole-script classifier. If the decision is anything other than `A1_ADMIT`, write a compact setup/route receipt, leave `openpyxl` unpatched, and let the genuine Python script import and use reference openpyxl normally. Keep the unchanged native observer around that process, including pre/post snapshot, changed-file helper, exit/signal handling and final receipt.

If the classifier returns `A1_ADMIT`, execute the frozen Phase-8A path: merged certificate, workbook discovery, SHA freshness, artifact ensure/load, Phase-7 merged route, `Runtime.install`, proxy/fallback and diagnostics. No script names, task families, historic outcome labels, workbook-size rules or timing prediction enter the decision.

The negative decision is authoritative for **absence of direct serving under the existing runtime**: Phase-8A itself refuses direct serving whenever the same classifier rejects. It is not an assertion that a workbook has no useful reads. Uncertain classification remains reference, exactly as before. H1 does not make a positive direct decision on new evidence.

## Work omitted and retained

On the proven reference branch H1 omits the parent-artifact module and workbook artifact discovery, the merged certificate, Phase-3 runtime/merge imports, early `openpyxl` import, load_workbook patch, proxy construction and direct-runtime event machinery. It retains the guarded sitecustomize entry, config/classifier read, source identity check in the observer's launch contract, ordinary script interpreter, normal openpyxl import at the script's chosen point, native observer, effect capture and final route witness. The experiment records `FAST_PATH_PROVEN_REFERENCE`; it must not invent a count of reference load calls that it no longer intercepts.

The first command still pays classifier/config startup. The isolated import probes show why this is a meaningful falsifier: the measured 91 ms `runtime_import_install` phase includes openpyxl import that an ordinary script still needs, while the roughly 22 ms `pre_runtime` work may remain. A small or absent full-command gain is entirely plausible. A later negative-admission cache or first-contact hook would be a **different** experiment.

## Alternatives considered

- **Lazy first-contact activation:** reasonable for scripts without workbook loads, but the frozen 22 reference-only scripts call openpyxl and still need the unchanged classifier before deciding a direct route. It introduces import-hook and module-identity risks to answer this narrower causal question.
- **Import-time deferred interposition:** could preserve reference imports until contact but alters the successful direct path and saved-reference ownership. It is unnecessary after an authoritative negative classifier result.
- **Persistent negative-decision cache:** could remove classifier/import cost on subsequent commands, but adds a new identity, invalidation and trust contract. It would bundle persistence with this early-bypass test.
- **Observer-side classification:** would make the native observer import/implement Python analysis or add IPC, undoing the thin-observer architecture.

## Trust and semantic risk

The path is safe only when the unchanged classifier's negative result is honored. A false positive direct classification still takes the frozen Phase-8A path; a negative result executes normal reference openpyxl as Phase-8A already did. On the fast path the script receives genuine reference workbook, worksheet and cell objects, so it also avoids some proxy identity exposures. No conclusion about broad direct-path equivalence follows.

The main integration risk is **diagnostic equivalence**: the fast path intentionally cannot observe each `load_workbook` call without reintroducing interception. It will report the proven source route and observer outcome, not an invented parse count. Process/module and changed-file fixtures must establish that the changed import timing and absence of a patch introduce no new product-contract violation.
