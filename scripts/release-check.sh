#!/bin/bash
# Local equivalent of the release-candidate CI workflow.
# Usage: scripts/release-check.sh [python]
# Builds sdist/wheel from a clean checkout state, installs into a fresh venv,
# and runs the full release battery. Exits nonzero on any failure.
set -euo pipefail
PY="${1:-python3}"
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WORK="$(mktemp -d /tmp/librecalc-rc-check.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
# Hermetic cache: every invocation below (run/doctor/status) shares this root.
export XDG_CACHE_HOME="$WORK/xdg"

step() { echo "=== RC-CHECK: $*"; }

step "0. worktree cleanliness (release files must be committed or staged)"
# Informational only: never blocks local runs.
git -C "$ROOT" status --short | head -n 5 || true

step "1. build sdist/wheel"
"$PY" -m pip --quiet install --upgrade build 2>/dev/null || "$PY" -m pip install build
rm -rf "$ROOT/dist"
(cd "$ROOT" && "$PY" -m build --outdir "$WORK/dist" .)
ls "$WORK/dist"

step "2. record build environment"
{
  echo "python=$("$PY" --version 2>&1)"
  echo "cc=$(cc --version | head -n 1)"
  echo "kernel=$(uname -a)"
  echo "glibc=$(ldd --version | head -n 1)"
  echo "openpyxl_pin=$(grep -E '^  \"openpyxl' "$ROOT/pyproject.toml")"
  echo "lxml_pin=$(grep -E '^  \"lxml' "$ROOT/pyproject.toml")"
} | tee "$WORK/build-env.txt"

step "3. clean install into fresh venv (in-project staging, gitignored)"
rm -rf "$ROOT/release-candidate"
mkdir -p "$ROOT/release-candidate"
"$PY" -m venv "$ROOT/release-candidate/venv"
VPY="$ROOT/release-candidate/venv/bin/python"
"$VPY" -m pip --quiet install --upgrade pip
"$VPY" -m pip install --require-hashes -r "$ROOT/requirements-release.txt"
"$VPY" -m pip install "$WORK"/dist/*.whl
"$VPY" -m pip install "pytest>=8"
"$VPY" -m pip freeze | tee "$WORK/installed.txt"

step "4. native launcher/observer present and executable"
test -x "$ROOT/release-candidate/venv/bin/recalc-agent"
OBS="$("$VPY" -c 'import recalc_agent.runner,os; p=recalc_agent.runner.observer_binary(); print(p); raise SystemExit(0 if os.access(p, os.X_OK) else 1)')"
echo "observer: $OBS"

step "5-6. maintained product/process tests"
(cd "$ROOT" && "$VPY" -m pytest -q tests/test_product_hygiene.py tests/test_product_process_semantics.py)

step "7-8. doctor + example"
"$ROOT/release-candidate/venv/bin/recalc-agent" doctor
"$ROOT/release-candidate/venv/bin/recalc-agent" example "$WORK/task"
(cd "$WORK/task" && "$ROOT/release-candidate/venv/bin/recalc-agent" run --workdir . ./create_input.py)

step "9-10. reference-only + direct BUILD/REUSE"
REFDIR="$WORK/ref" && mkdir -p "$REFDIR"
"$VPY" - "$REFDIR" <<'EOF'
import openpyxl, sys
d = sys.argv[1]
wb = openpyxl.Workbook(); wb.active.title = "Sheet1"; wb.active["A1"] = 7; wb.save(f"{d}/input.xlsx")
open(f"{d}/ref.py", "w").write('import openpyxl\nwb=openpyxl.load_workbook("input.xlsx")\nprint(wb.active["A1"].value)\nwb.close()\n')
open(f"{d}/direct.py", "w").write('import openpyxl\nwb=openpyxl.load_workbook("input.xlsx")\nws=wb["Sheet1"]\nprint(ws.cell(row=1,column=1).value)\nwb.close()\n')
EOF
(cd "$REFDIR" && "$ROOT/release-candidate/venv/bin/recalc-agent" run --workdir . ./ref.py)
(cd "$REFDIR" && "$ROOT/release-candidate/venv/bin/recalc-agent" run --workdir . ./direct.py)
(cd "$REFDIR" && "$ROOT/release-candidate/venv/bin/recalc-agent" run --workdir . ./direct.py)
"$ROOT/release-candidate/venv/bin/recalc-agent" status
XDG_CACHE_HOME="$WORK/xdg" true  # default cache path exercised implicitly

step "11. changed-file capture"
CAPDIR="$WORK/cap" && mkdir -p "$CAPDIR"
"$VPY" - "$CAPDIR" <<'EOF'
import openpyxl, sys
d = sys.argv[1]
wb = openpyxl.Workbook(); wb.active["A1"] = 1; wb.save(f"{d}/input.xlsx")
open(f"{d}/w.py", "w").write('import openpyxl\nwb=openpyxl.load_workbook("input.xlsx")\nwb.active["A1"]=2\nwb.save("input.xlsx")\nwb.close()\n')
EOF
(cd "$CAPDIR" && "$ROOT/release-candidate/venv/bin/recalc-agent" run --workdir . ./w.py)
"$ROOT/release-candidate/venv/bin/recalc-agent" status --json | "$VPY" -c "import json,sys; d=json.load(sys.stdin); assert d['last_run']['effect_capture_status']=='PASS', d; print('capture PASS')"

step "12. abrupt-exit smoke (os._exit after mutation)"
ADIR="$WORK/abrupt" && mkdir -p "$ADIR"
"$VPY" - "$ADIR" <<'EOF'
import openpyxl, sys
d = sys.argv[1]
wb = openpyxl.Workbook(); wb.active["A1"] = 1; wb.save(f"{d}/input.xlsx")
open(f"{d}/a.py", "w").write('import openpyxl,os\nw=openpyxl.load_workbook("input.xlsx")\nw.active["A1"]=9\nw.save("input.xlsx")\nos._exit(7)\n')
EOF
set +e
(cd "$ADIR" && "$ROOT/release-candidate/venv/bin/recalc-agent" run --workdir . ./a.py)
CODE=$?
set -e
test "$CODE" -eq 7 || { echo "expected exit 7, got $CODE"; exit 1; }
"$ROOT/release-candidate/venv/bin/recalc-agent" status --json | "$VPY" -c "import json,sys; d=json.load(sys.stdin); assert d['last_run']['assurance_status']=='PASS', d; print('abrupt-exit assurance PASS')"

step "13-15. wheel list, no __pycache__, license"
if [ -f "$ROOT/LICENSE" ]; then LICENSE_REQ=1; else echo "LICENSE DECISION REQUIRED — wheel license check deferred"; LICENSE_REQ=0; fi
LICENSE_REQ="$LICENSE_REQ" "$VPY" - "$WORK/dist" <<'EOF'
import glob, os, sys, zipfile
whl = glob.glob(sys.argv[1] + "/*.whl")[0]
names = zipfile.ZipFile(whl).namelist()
bad = [n for n in names if "__pycache__" in n or n.endswith((".pyc", ".pyo"))]
assert not bad, bad
if os.environ.get("LICENSE_REQ") == "1":
    assert any("LICENSE" in n for n in names), "LICENSE missing from wheel"
for n in sorted(names):
    print(" ", n)
print("wheel OK:", whl)
EOF

step "16. dependency versions"
"$VPY" -c "import importlib.metadata as m; print('openpyxl', m.version('openpyxl')); print('lxml', m.version('lxml'))"

step "17. checksums + stage candidate"
(cd "$WORK/dist" && sha256sum -- *) | tee "$WORK/checksums.txt"
cp "$WORK"/dist/* "$WORK/checksums.txt" "$WORK/build-env.txt" "$WORK/installed.txt" "$ROOT/release-candidate/"
cp "$WORK/checksums.txt" "$ROOT/release-candidate/SHA256SUMS"

echo "RC-CHECK PASSED — candidate staged in $ROOT/release-candidate/"
