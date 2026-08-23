#!/usr/bin/env bash
set -euo pipefail

TARGET_BASE="${1:-/home/kerem/Desktop/Personal Projects}"
TARGET="$TARGET_BASE/librecalc-mcp"

mkdir -p "$TARGET_BASE"
if [[ -e "$TARGET" ]]; then
  echo "Refusing to overwrite existing $TARGET" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cp -a "$SCRIPT_DIR" "$TARGET"
rm -f "$TARGET/librecalc-mcp.zip" 2>/dev/null || true
cd "$TARGET"
git init
printf '\nCreated: %s\n' "$TARGET"
printf 'Next: cd %q && uv sync --extra dev\n' "$TARGET"
