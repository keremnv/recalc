#!/bin/bash
# Phase 12 Phase 12 Tranche 3 (enriched, Pop B) launcher.
# Sequential per-task arm pairs (CONTROL, TREATMENT, [+ SHAM]) to keep
# pairing tight against provider drift. Continues past runner crashes.
cd "$(dirname "$0")/.." || exit 1
LOG=phase12/runs/tranche3.log
TASKS="Template:16_02 Template:06_16 Template:06_09 Template:16_05 Debugging:10_01 Debugging:10_04 Debugging:10_05 Debugging:10_06 Financial_Model:08_03 Financial_Model:08_04 Financial_Model:08_05 Financial_Model:17_05"
run_one() {
  echo "===== $1 $2 $(date -u +%H:%M:%S) =====" | tee -a "$LOG"
  if python3 phase12/run_ab.py --task "$1" --arm "$2" --pop popB >>"$LOG" 2>&1; then
    tail -n 14 "$LOG" | grep -E '"status"|"output_produced"|"intervened"|"positive"|"calls"' || true
  else
    echo "RUNNER_CRASH rc=$? $1 $2" | tee -a "$LOG"
  fi
}
for t in $TASKS; do
  run_one "$t" CONTROL
  run_one "$t" TREATMENT
    :
done
echo "TRANCHE3_DONE $(date -u +%H:%M:%S)" | tee -a "$LOG"
