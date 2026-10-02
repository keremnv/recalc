#!/usr/bin/env bash
# Restore private experiment data (research/private-data-manifest.json) into
# this worktree as symlinks, for local reproduction only.
#
#   scripts/restore-private-data.sh          create missing symlinks
#   scripts/restore-private-data.sh --check  report present/missing units
#   scripts/restore-private-data.sh --clean  remove restored symlinks
#
# The private root defaults to the manifest's private_root; override with:
#   RECALC_PRIVATE_DATA=/path/to/private-data scripts/restore-private-data.sh
#
# Restored symlinks are gitignored and must never be committed.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/research/private-data-manifest.json"
MODE="${1---restore}"

PRIV="${RECALC_PRIVATE_DATA:-$(python3 -c "import json;print(json.load(open('$MANIFEST'))['private_root'])")}"
if [ ! -d "$PRIV" ]; then
  echo "private data root not found: $PRIV" >&2
  echo "set RECALC_PRIVATE_DATA to a directory holding the manifest units." >&2
  exit 1
fi

python3 - "$MODE" <<EOF
import json, os, sys
mode = sys.argv[1]
man = json.load(open("$MANIFEST"))
priv = "$PRIV"
root = "$ROOT"
missing_src, linked, present, removed = [], 0, 0, 0
for e in man["entries"]:
    src = os.path.join(priv, e["private_name"])
    dst = os.path.join(root, e["repo_path"])
    if mode == "--clean":
        if os.path.islink(dst):
            os.unlink(dst)
            removed += 1
        continue
    if not os.path.exists(src):
        missing_src.append(e["private_name"])
        continue
    if os.path.lexists(dst):
        present += 1
        continue
    if mode == "--check":
        continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.symlink(src, dst)
    linked += 1
if mode == "--clean":
    print(f"removed {removed} restored symlinks")
elif mode == "--check":
    print(f"present-or-restored: {present}/{len(man['entries'])}")
else:
    print(f"linked {linked} units ({present} already present)")
if missing_src:
    print(f"missing from private root ({len(missing_src)}):")
    for m in missing_src:
        print(f"  {m}")
    sys.exit(2 if mode == "--check" and not linked else 0)
EOF