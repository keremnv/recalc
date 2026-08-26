#!/usr/bin/env bash
set -euo pipefail

tool_root=${LIBRECALC_TOOL_ROOT:-/opt/librecalc-tools/librecalc}
profile_dir=/tmp/librecalc-benchmark-profile
mkdir -p "$profile_dir"

libreoffice \
  --headless \
  --nologo \
  --nodefault \
  --nofirststartwizard \
  "-env:UserInstallation=file://$profile_dir" \
  "--accept=socket,host=127.0.0.1,port=2021;urp;StarOffice.ServiceManager" \
  >/tmp/librecalc-benchmark-libreoffice.log 2>&1 &

for _ in $(seq 1 50); do
  if python3 "$tool_root/lib/calc_tool.py" health >/dev/null 2>&1; then
    return 0
  fi
  sleep 0.2
done

cat /tmp/librecalc-benchmark-libreoffice.log >&2
return 1
