"""Crash-resilient post-replay stages; independent review gates remain manual."""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
OUT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--replay-pid',type=int,required=True);args=ap.parse_args()
expected=len(json.loads((OUT/'POPULATION_MANIFEST.json').read_text())['eligible']);state=OUT/'POST_REPLAY_STAGE_STATE.json'
with (OUT/'post_replay_stages.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 while True:
  count=sum(1 for _ in open(OUT/'BASELINE_CORRECTION_LEDGER.jsonl'))
  try:os.kill(args.replay_pid,0);alive=True
  except ProcessLookupError:alive=False
  if count==expected and not alive:break
  if not alive and count!=expected:raise RuntimeError(f'replay stopped before completion: {count}/{expected}')
  time.sleep(10)
 stages=['analyze.py','render_tables.py','replicate_phase12.py','enrich_audit.py'];finished=json.loads(state.read_text()).get('completed_stages',[]) if state.exists() else []
 for stage in stages:
  if stage in finished:continue
  state.write_text(json.dumps({'primary_replay_complete':True,'completed_stages':finished,'active_stage':stage,'review_gates':'not automated'},indent=2))
  with (OUT/(stage+'.log')).open('a') as log:subprocess.run([sys.executable,str(OUT/stage)],check=True,stdout=log,stderr=log,env={**os.environ,'LC_ALL':'C.UTF-8','LANG':'C.UTF-8','TZ':'UTC'})
  finished.append(stage);state.write_text(json.dumps({'primary_replay_complete':True,'completed_stages':finished,'active_stage':None,'review_gates':'await independent interpretation review; follow-up not started'},indent=2));print('completed',stage,flush=True)
print('primary stages ready for independent review',flush=True)
