import json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
p=Path(__file__).resolve().parent;start=time.monotonic();record={'started_utc':datetime.now(timezone.utc).isoformat(),'trajectory_model_calls':0,'trajectory_model_cost_usd':0,'model_use':'independent reviews only, outside scored treatment'}
(p/'REPLAY_EXECUTION.json').write_text(json.dumps(record,indent=2))
with (p/'REPLAY_PROGRESS.jsonl').open('w') as out,(p/'REPLAY_STDERR.log').open('w') as err:
 proc=subprocess.run([sys.executable,str(p/'replay.py')],stdout=out,stderr=err,env={**os.environ,'LC_ALL':'C.UTF-8','LANG':'C.UTF-8','TZ':'UTC'})
record.update(ended_utc=datetime.now(timezone.utc).isoformat(),total_replay_wall_seconds=time.monotonic()-start,return_code=proc.returncode)
(p/'REPLAY_EXECUTION.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2));raise SystemExit(proc.returncode)
