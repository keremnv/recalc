#!/bin/bash
# Phase 12 Tranche 2 (primary, Pop A) + sham launcher.
# Sequential per-task arm pairs (CONTROL, TREATMENT, [+ SHAM]) to keep
# pairing tight against provider drift. Continues past runner crashes.
cd "$(dirname "$0")/.." || exit 1
LOG=phase12/runs/tranche2.log
TASKS="Template:01_03 Template:06_05 Template:06_25 Template:10_02 Template:11_03 Template:11_04 Template:14_03 Template:15_02 Debugging:01_01 Debugging:03_03 Debugging:04_06 Debugging:05_04 Debugging:08_03 Debugging:08_06 Debugging:09_08 Debugging:10_03 Financial_Model:03_02 Financial_Model:05_05 Financial_Model:07_01 Financial_Model:07_02 Financial_Model:12_01 Financial_Model:12_05 Financial_Model:14_05 Financial_Model:18_03"
SHAM="Template:01_03 Template:11_04 Template:14_03 Template:15_02 Debugging:01_01 Debugging:08_03 Debugging:08_06 Debugging:09_08 Financial_Model:03_02 Financial_Model:07_02 Financial_Model:12_05 Financial_Model:18_03"
run_one() {
  echo "===== $1 $2 $(date -u +%H:%M:%S) =====" | tee -a "$LOG"
  if python3 phase12/run_ab.py --task "$1" --arm "$2" --pop popA >>"$LOG" 2>&1; then
    tail -n 14 "$LOG" | grep -E '"status"|"output_produced"|"intervened"|"positive"|"calls"' || true
  else
    echo "RUNNER_CRASH rc=$? $1 $2" | tee -a "$LOG"
  fi
}
for t in $TASKS; do
  run_one "$t" CONTROL
  run_one "$t" TREATMENT
  case " $SHAM " in *" $t "*) run_one "$t" SHAM;; esac
done
echo "TRANCHE2_DONE $(date -u +%H:%M:%S)" | tee -a "$LOG"
