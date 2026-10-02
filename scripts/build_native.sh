#!/bin/sh
# Build the native observer + launcher in-tree (dev checkout / CI).
# The wheel build hook (hatch_build.py) runs the same commands.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
NATIVE="$ROOT/src/recalc_agent/native"
cc -std=c11 -O2 -Wall -Wextra -Werror "$NATIVE/observer.c" -o "$NATIVE/observer"
cc -std=c11 -O2 -Wall -Wextra -Werror "$NATIVE/launcher.c" -o "$NATIVE/launcher"
chmod 755 "$NATIVE/observer" "$NATIVE/launcher"
echo "built: $NATIVE/observer $NATIVE/launcher"
