"""Recover fully written rows after host interruption; never alter frozen protocol."""
import json,hashlib,sys,shutil
from pathlib import Path
from datetime import datetime,timezone
import replay as r
out=r.OUT;freeze=r.load(out/'FREEZE.json')
for name,key in [('PREREGISTERED_REPLAY_SPEC.md','spec_hash'),('POPULATION_MANIFEST.json','population_hash'),('replay.py','replay_hash'),('uno_recalc.py','uno_helper_hash')]:assert r.sha(out/name)==freeze[key]
protected=r.load(out/'PROTECTED_HISTORY_HASHES.json');changed=[p for p,h in protected.items() if not (r.ROOT/p).is_file() or r.sha(r.ROOT/p)!=h];assert not changed,changed
names=r.LEDGERS;ledgers={name:[json.loads(l) for l in (out/(name+'.jsonl')).read_text().splitlines()] for name in names};base=ledgers['BASELINE_CORRECTION_LEDGER'];ids={x['id'] for x in base};assert all([x['id'] for x in v]==[x['id'] for x in base] for v in ledgers.values())
recovered=[]
for p in sorted((out/'artifacts').glob('*/result.json')):
 result=r.load(p)
 if result['id'] in ids:continue
 assert r.sha(r.ROOT/result['V0_source'])==result['V0_hash']
 if result.get('V1_artifact'):assert r.sha(r.ROOT/result['V1_artifact'])==result['V1_hash']
 assert 'total_elapsed_seconds' in result and result['evaluator_hash']==freeze['evaluator_hash']
 r.append_ledgers(result,out);recovered.append(result['id']);ids.add(result['id'])
incomplete=[];namespace=out/'recalc_by_hash'/freeze['uno_helper_hash'][:16]
for p in sorted(namespace.glob('*')):
 if p.is_dir() and not (p/'recalc.json').exists():
  target=out/'interrupted_recalc'/p.name;target.parent.mkdir(exist_ok=True);shutil.move(str(p),str(target));incomplete.append(p.name)
 if (p/'recalc.json').exists() and r.load(p/'recalc.json').get('status')=='RECALC_PASS':assert (p/'V1.xlsx').exists()
previous=r.load(out/'REPLAY_EXECUTION.json');previous.update(interrupted=True,interruption_reason='user reported application/host crash; process absent on resume',last_progress_write_utc=datetime.fromtimestamp((out/'REPLAY_PROGRESS.jsonl').stat().st_mtime,timezone.utc).isoformat(),active_wall_seconds_lower_bound=(out/'REPLAY_PROGRESS.jsonl').stat().st_mtime-datetime.fromisoformat(previous['started_utc']).timestamp())
(out/'REPLAY_EXECUTION_ATTEMPT_1.json').write_text(json.dumps(previous,indent=2));shutil.copyfile(out/'REPLAY_PROGRESS.jsonl',out/'REPLAY_PROGRESS_ATTEMPT_1.jsonl');shutil.copyfile(out/'REPLAY_STDERR.log',out/'REPLAY_STDERR_ATTEMPT_1.log')
record={'utc':datetime.now(timezone.utc).isoformat(),'protected_files_verified':len(protected),'protected_changes':changed,'ledgers_committed_before_resume':len(base),'recovered_complete_row_ids':recovered,'incomplete_execution_dirs_preserved':incomplete,'pending':len(r.load(out/'POPULATION_MANIFEST.json')['eligible'])-len(ids),'protocol_unchanged':True}
(out/'RESUME_AUDIT.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2))
