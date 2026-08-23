#!/usr/bin/env bash
set -euo pipefail

HOST="${LIBRECALC_HOST:-localhost}"
PORT="${LIBRECALC_PORT:-2021}"

exec libreoffice \
  --headless \
  --nologo \
  --nodefault \
  --norestore \
  "--accept=socket,host=${HOST},port=${PORT};urp;StarOffice.ServiceManager"
