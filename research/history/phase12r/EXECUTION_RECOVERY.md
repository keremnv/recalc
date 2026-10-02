# Execution-only recovery amendment (protocol remains frozen)

Two application/host crashes interrupted four-worker official scoring. During the
second attempt, four scoring processes occupied roughly 4.6GB, 4.3GB, 1.4GB and
1.1GB RSS on a 14GiB machine. Neither interruption completed a changed protocol,
evaluator, or treatment. Preserve both attempts and completed per-workbook results.

Resume with one isolated subprocess per workbook. Bound its virtual memory to 7GiB
and wall time to 900s so the UI/host cannot be exhausted. Explicitly collect garbage
after the unchanged official scorer returns; openpyxl workbook cycles need not remain
alive for another scoring call. This changes object lifetimes only. The official
function, workbook bytes, task data, calculation treatment, identity and classification
rules remain frozen. Resource errors are explicit unscorable failures, never scored
as successful zero results. Each workbook process exits after writing its record.

Byte-identical (candidate hash + task/input/golden/evaluator identities) scoring may
be reused, with the original measured scoring result and a reuse flag. This is the
same deterministic computation, not a new evaluation arm. Every cached result is
separately hashed and validates all identity keys. A different score identity never
reuses a score. Recalculation continues to use the frozen helper/config/hash namespace.

The authoritative specification and original implementation hashes remain unchanged.
This supplement only governs execution resources/resumption. Report both failed
attempts, resource limits, unique computations, timing and interruption uncertainty.
No eligibility, outcome threshold, classifier, baseline rule or scored workbook is
changed after seeing results. Completed records are committed once; unfinished
rows remain in the full eligible denominator and are attempted under identical
causal semantics.

The bounded scheduler captures the official comparison function's existing return
values during process_single_item, rather than invoking the same comparison a
second time for counts. The wrapper returns the exact original object unchanged;
process_single_item still executes the original official comparison and scoring
logic once. This removes duplicate reads, CPU and memory without changing workbook
inputs, comparison semantics, returned official scores or classification. No
additional diagnosis is derived. Garbage collection occurs only after return.

Scoring equivalence cache additionally permits identical package-part bytes after
ignoring ZIP order/compression/timestamps and the validated nonscored core/app
properties. Every other package member must have exactly identical content and
name; formula/value/style/relationship/name/calculation parts are never normalized
or omitted. replay() has already parsed the candidate successfully before this
cache is consulted. The scorer never observes core/app properties after parsing.
Input/golden/task/dataset/evaluator identities must also match. Original candidate
and V1 raw SHA256 identities remain distinct, and the reused score record carries
the current candidate hash plus explicit equivalence/reuse provenance. This removes
identical scoring computation; it neither changes XLSX bytes nor infers scores from
formula similarity. A parity test covers distinct valid core-property timestamps.

Disk handling: only redundant staging copies made by this new phase are removed
after scoring/commit and hash verification. Original historical files and the
identified V0/V1/witness artifacts remain. This addresses limited free disk without
changing score computations, causal variants, eligibility or formula/cache proof.

Reference-only parsing cache: unchanged benchmark input/golden workbooks can be
loaded as fresh clones of previously parsed openpyxl objects. The cache key includes
source path/hash, complete requested loading arguments, Python and openpyxl versions.
The original loader creates each cache before the scorer touches its objects;
subsequent reads deserialize a fresh independent object, preserving types, styles,
formulas and graph relationships. Candidates are always parsed normally. No input,
golden or candidate workbook bytes are changed. The unchanged official comparison
and process_single_item consume these equivalent objects. Reference parsing cache
hits/misses/time are recorded, and parity tests compare against fresh official reads.

Repeated candidate parsing within one workbook job also uses fresh clones keyed by
exact full workbook SHA256, complete loading args, Python and openpyxl versions.
Each distinct V0/V1/witness byte sequence first passes the normal parser; caches
never cross different workbook bytes or loading modes. The cache is local to the
isolated job, preserves raw parsed values/formulas/styles/properties, returns a
fresh independent object on every hit, and is discarded at job completion. It
changes repeated parsing cost only, not any workbook or scored value. Normal
parser exceptions remain exceptions. Reference cache and candidate cache scopes
are separate. Native-versus-cloned parity is tested on a complex FM workbook.

Immutable derived storage deduplication: after full byte-hash verification, the
recalculation cache and a committed V1 artifact may share one inode using an atomic
hardlink replacement. Both names retain the same immutable XLSX bytes and hashes;
no original or V0 is linked. Copies made for scoring remain independent. This
removes duplicate derived storage only; DERIVED_STORAGE_AUDIT.jsonl records IDs
and saved bytes. No formula/cache/score, helper or protocol change occurs.

After a server-daemon restart (distinct from the earlier host-memory crashes),
605 committed rows and one surviving child result were preserved. Resume attempts
are now numbered without overwriting any prior attempt log. No duplicate row is
committed. The orphan completed before changing the execution wrapper.

Scorer-only parsed-object scope: the frozen comparison reads only the exact cells
specified by answer_position and worksheet names/order (including golden-first-sheet
fallback). It compares already parsed values/formulas/colors; it never calculates
formulas or reads their precedents. The additional loader preserves every existing
accessed cell object, all sheet names/order and parsed workbook metadata/styles.
Only unobserved in-memory cell objects are omitted. Bytes and the full-workbook
formula/semantic/cache/package inspections remain untouched. Independent cached
clones are keyed by complete file hash, loading mode/arguments, answer positions,
default sheet, evaluator and implementation identities. Reference and candidate
scopes are separate; candidate caches are disposable at job completion.

Five direct native-versus-scoped official-return tests pass across Template,
Financial Model, color, embedded formula and missing-sheet cases. Existing execution
parity continues to require identical official outcomes/counts/modes; its reuse
assertion accepts either the full-reference cache or the new scoped clone cache.
The first rerun failed only that obsolete full-reference-hit assertion; every
compared score/count remained equal. The updated assertion still requires actual
clone reuse. No original scorer source, outcome/materiality threshold, classifier,
eligibility or scored workbook changes. This scope is restricted to the retained
fixed evaluator hash; it is not a general replacement workbook parser.
