#!/bin/bash
# Reproducible LibreCalc rc2 demo.
#
#   ordinary Python -> LibreCalc first run (BUILT) -> second run (REUSED)
#   -> unsupported operation on the reference path. Identical results.
#
# Usage: scripts/demo.sh [--check] [--keep]
#   --check  assertion-only mode; quiet unless a check fails
#   --keep   keep the fresh temp cache after the run (prints its path)
#
# Every displayed line comes from a real invocation in this run. Timings are
# wall clock on this machine only, not a benchmark. "Read phase" is time
# inside the script (parse + reads), printed by the script itself on stderr;
# "total" is the whole invocation including interpreter startup.
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEMO="$ROOT/examples/demo"
CHECK=0
KEEP=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    --keep) KEEP=1 ;;
    *) echo "FAIL: unknown arg: $arg" >&2; exit 2 ;;
  esac
done

PY="${PYTHON:-python3}"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if ! "$PY" -c "import librecalc_agent" 2>/dev/null; then
  echo "FAIL: librecalc_agent not importable with $PY (PYTHONPATH=$PYTHONPATH)" >&2
  exit 2
fi

CACHE="$(mktemp -d /tmp/librecalc-demo.XXXXXX)"
if [ "$KEEP" -eq 0 ]; then
  trap 'rm -rf "$CACHE"' EXIT
fi
export XDG_CACHE_HOME="$CACHE"
OUT="$CACHE/outputs"
mkdir -p "$OUT"

say() { if [ "$CHECK" -eq 0 ]; then echo "$*"; fi; }
fail() { echo "FAIL: $*" >&2; exit 1; }

now_ns() { date +%s%N; }
ms() { echo $((($2 - $1) / 1000000)); }

# receipt_field <json-file> <field> — reads last_run compact fields.
receipt_field() { "$PY" -c "
import json,sys
d = json.load(open('$1'))
r = d.get('last_run') or {}
v = r.get('$2')
print('' if v is None else (','.join(v) if isinstance(v, list) else v))
"; }

cd "$DEMO"

say "=== LibreCalc demo (rc2) ==="
say "workdir: examples/demo | cache: $CACHE (fresh)"
say ""

# ---- Beat A: ordinary Python ----
say "--- [1/4] ordinary Python ---"
say "\$ python read.py"
start=$(now_ns)
"$PY" read.py >"$OUT/plain.out" 2>"$OUT/plain.err" || fail "plain read.py exited nonzero"
end=$(now_ns)
PLAIN_MS=$(ms "$start" "$end")
say "$(cat "$OUT/plain.out")"
say "read phase: $(grep -o '[0-9.]* ms' "$OUT/plain.err") (in-script) | total: ${PLAIN_MS} ms"
say ""

# ---- Beat B1: first LibreCalc run -> BUILT ----
say "--- [2/4] LibreCalc, first run: decode once, then serve ---"
say "\$ librecalc-agent run --workdir . ./read.py"
start=$(now_ns)
"$PY" -m librecalc_agent run --workdir . ./read.py >"$OUT/built.out" 2>"$OUT/built.err" \
  || fail "first librecalc run exited nonzero"
end=$(now_ns)
BUILT_MS=$(ms "$start" "$end")
"$PY" -m librecalc_agent status --json >"$OUT/built.status.json" 2>/dev/null || true
[ -s "$OUT/built.status.json" ] || fail "no status JSON after first run"
say "$(cat "$OUT/built.out")"
say "path: direct read, decoded state $(receipt_field "$OUT/built.status.json" artifact) (route=$(receipt_field "$OUT/built.status.json" route), served_loads=$(receipt_field "$OUT/built.status.json" direct_served_loads))"
say "read phase: $(grep -o '[0-9.]* ms' "$OUT/built.err") (in-script) | total: ${BUILT_MS} ms"
say ""

# ---- Beat B2: second LibreCalc run -> REUSED ----
say "--- [3/4] LibreCalc, second run: reuse decoded state ---"
say "\$ librecalc-agent run --workdir . ./read.py"
start=$(now_ns)
"$PY" -m librecalc_agent run --workdir . ./read.py >"$OUT/reused.out" 2>"$OUT/reused.err" \
  || fail "second librecalc run exited nonzero"
end=$(now_ns)
REUSED_MS=$(ms "$start" "$end")
"$PY" -m librecalc_agent status --json >"$OUT/reused.status.json" 2>/dev/null || true
[ -s "$OUT/reused.status.json" ] || fail "no status JSON after second run"
say "$(cat "$OUT/reused.out")"
say "path: direct read, decoded state $(receipt_field "$OUT/reused.status.json" artifact) (route=$(receipt_field "$OUT/reused.status.json" route), served_loads=$(receipt_field "$OUT/reused.status.json" direct_served_loads))"
say "read phase: $(grep -o '[0-9.]* ms' "$OUT/reused.err") (in-script) | total: ${REUSED_MS} ms"
say ""

# ---- Beat C: unsupported operation -> reference path ----
say "--- [4/4] outside the supported surface: ordinary openpyxl ---"
say "\$ librecalc-agent run --workdir . ./unsupported.py"
"$PY" unsupported.py >"$OUT/ref-plain.out" 2>"$OUT/ref-plain.err" \
  || fail "plain unsupported.py exited nonzero"
start=$(now_ns)
"$PY" -m librecalc_agent run --workdir . ./unsupported.py >"$OUT/ref.out" 2>"$OUT/ref.err" \
  || fail "reference-path run exited nonzero"
end=$(now_ns)
REF_MS=$(ms "$start" "$end")
"$PY" -m librecalc_agent status --json >"$OUT/ref.status.json" 2>/dev/null || true
[ -s "$OUT/ref.status.json" ] || fail "no status JSON after reference run"
say "$(cat "$OUT/ref.out")"
say "path: ordinary openpyxl (route=$(receipt_field "$OUT/ref.status.json" route)) — iteration is outside the supported surface"
say "read phase: $(grep -o '[0-9.]* ms' "$OUT/ref.err") (in-script) | total: ${REF_MS} ms"
say ""

# ---- Validation (always enforced) ----
cmp -s "$OUT/plain.out" "$OUT/built.out" || fail "stdout differs: plain vs first LibreCalc run"
cmp -s "$OUT/plain.out" "$OUT/reused.out" || fail "stdout differs: plain vs second LibreCalc run"
cmp -s "$OUT/ref-plain.out" "$OUT/ref.out" || fail "stdout differs: plain vs reference-path run"
[ "$(receipt_field "$OUT/built.status.json" route)" = "DIRECT_RUNTIME" ] || fail "first run route != DIRECT_RUNTIME"
[ "$(receipt_field "$OUT/built.status.json" artifact)" = "BUILT" ] || fail "first run artifact != BUILT"
[ "$(receipt_field "$OUT/reused.status.json" route)" = "DIRECT_RUNTIME" ] || fail "second run route != DIRECT_RUNTIME"
[ "$(receipt_field "$OUT/reused.status.json" artifact)" = "REUSED" ] || fail "second run artifact != REUSED"
[ "$(receipt_field "$OUT/reused.status.json" direct_served_loads)" -ge 1 ] || fail "reuse served no loads"
[ "$(receipt_field "$OUT/ref.status.json" route)" = "REFERENCE_FAST_PATH" ] || fail "unsupported run unexpectedly took the direct path"
[ "$(receipt_field "$OUT/built.status.json" assurance_status)" = "PASS" ] || fail "first run assurance != PASS"
[ "$(receipt_field "$OUT/reused.status.json" assurance_status)" = "PASS" ] || fail "second run assurance != PASS"

# ---- Summary ----
HOST="$("$PY" -c "import platform; print('CPython ' + platform.python_version() + ', ' + platform.platform())")"
say "result: identical output across [1][2][3]; reference run matches plain Python"
say "timings: this demo / this machine only ($HOST) — not a benchmark."
say "read phase = time inside the script (parse + reads). First run builds the"
say "reusable decode once (cached); later runs reuse it. Totals include"
say "interpreter startup, which dominates at this size."
if [ "$KEEP" -eq 1 ]; then
  say "cache kept at: $CACHE"
fi
if [ "$CHECK" -eq 1 ]; then
  echo "demo --check: PASS"
fi
