"""Resource-only scheduler; frozen replay/scorer/treatment functions remain intact."""
import argparse,copy,gc,hashlib,json,os,resource,signal,subprocess,sys,time,shutil,zipfile
from datetime import datetime,timezone
from pathlib import Path
import replay as r
from reference_parse_cache import loader as reference_loader, candidate_loader
from scored_object_cache import loader as scored_object_loader
OUT=r.OUT

def write_json_atomic(path,payload):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.part');tmp.write_text(json.dumps(payload,indent=2));os.replace(tmp,path)

def scored_package_identity(path):
 # Scorer never observes docProps; replay has already validated candidate parsing.
 # Every other package part is content-hashed, independent of ZIP compression/order.
 with zipfile.ZipFile(path) as z:
  return r.digest({n:hashlib.sha256(z.read(n)).hexdigest() for n in sorted(z.namelist()) if n not in ('docProps/core.xml','docProps/app.xml')})

def bounded_score(row,path,stage):
 # Identical official entrypoints and data to replay.score; GC only changes lifetimes.
 identity={'candidate_hash':r.sha(path),'task':row['task'],'input_hash':row['input_hash'],'gold_hash':row['gold_hash'],'evaluator_hash':r.sha(r.BENCH/'evaluation/evaluation.py'),'dataset_hash':r.sha(r.BENCH/'data'/row['category']/'dataset.json')}
 key=r.digest(identity);cache=OUT/'score_by_identity'/key;meta=cache.with_suffix('.json')
 package_identity={**identity,'candidate_hash':scored_package_identity(path)};package_key=r.digest(package_identity);alias=OUT/'score_package_aliases'/f'{package_key}.json'
 if alias.exists() and not meta.exists() and r.load(alias)['result']['status']=='SCORE_PASS':
  old=r.load(alias);assert old['identity']==package_identity
  result=old['result'];return {**result,'candidate_hash':identity['candidate_hash'],'scoring_reused_identical_identity':True,'score_reuse_basis':'all XLSX package part bytes identical except validated nonscored docProps/core.xml and docProps/app.xml; ZIP packaging ignored','scoring_execution_identity':old['execution_key'],'scoring_package_identity':package_key,'elapsed_seconds':0.0,'original_execution_seconds':result['elapsed_seconds']}
 if meta.exists() and r.load(meta)['result']['status']=='SCORE_PASS':
  payload=r.load(meta);assert payload['identity']==identity
  result=payload['result'];alias.parent.mkdir(exist_ok=True);write_json_atomic(alias,{'identity':package_identity,'result':result,'execution_key':key});return {**result,'scoring_reused_identical_identity':True,'scoring_execution_identity':key,'elapsed_seconds':0.0,'original_execution_seconds':result['elapsed_seconds']}
 t=time.monotonic();cat,tid=row['task'].split(':');stage.mkdir(parents=True,exist_ok=True);dst=stage/f'{tid}_output.xlsx';shutil.copyfile(path,dst)
 d=next(x for x in r.load(r.BENCH/'data'/cat/'dataset.json') if str(x['id'])==tid)
 color=cat=='Debugging' and 'Color' in d['spreadsheet_path'];formula=cat=='Debugging' and 'Embedded' in d['spreadsheet_path']
 original_compare=r.EVAL.compare_workbooks_with_regression;observed=[]
 def capture_existing_counts(*args,**kwargs):
  detail=original_compare(*args,**kwargs);observed.append(detail);return detail
 r.EVAL.compare_workbooks_with_regression=capture_existing_counts
 original_load=r.EVAL.openpyxl.load_workbook;reference_events=[];scoped_events=[];full_reference_loader=reference_loader(original_load,{(r.ROOT/row['input']).resolve():row['input_hash'],(r.ROOT/row['gold']).resolve():row['gold_hash']},reference_events);r.EVAL.openpyxl.load_workbook=scored_object_loader(full_reference_loader,row,d['answer_position'],scoped_events)
 try:result,_=r.EVAL.process_single_item(d,str(r.BENCH/'data'/cat),str(stage),{},cat)
 finally:
  r.EVAL.compare_workbooks_with_regression=original_compare;r.EVAL.openpyxl.load_workbook=original_load
 gc.collect()
 detail=observed[0] if observed else (False,result.get('error_message',''),0,0,{'correct':0,'total':0},{'correct':0,'total':0})
 dst.unlink(missing_ok=True)
 score={'official':result,'status':'SCORE_PASS' if detail[3]>0 else 'SCORE_UNSCORABLE','assessed_cells':detail[3],'correct_cells':detail[2],'regression_counts':detail[4],'modification_counts':detail[5],'mode':{'with_font_color':color,'with_formula':formula},'elapsed_seconds':time.monotonic()-t,'candidate_hash':r.sha(path),'scoring_reused_identical_identity':False,'scoring_execution_identity':key,'reference_parse_cache_events':reference_events,'scored_object_cache_events':scoped_events,'scored_object_cache_hash':r.sha(OUT/'scored_object_cache.py')}
 cache.parent.mkdir(parents=True,exist_ok=True);write_json_atomic(meta,{'identity':identity,'result':score});alias.parent.mkdir(exist_ok=True);write_json_atomic(alias,{'identity':package_identity,'result':score,'execution_key':key});return score

def seed_scores(rows):
 for result in rows:
  for lab,artifact in [('current_V0_score','V0_artifact'),('V1_score','V1_artifact')]:
   s=result.get(lab);p=result.get(artifact)
   if not s or not p:continue
   identity={'candidate_hash':s['candidate_hash'],'task':result['task'],'input_hash':result['input_hash'],'gold_hash':result['gold_hash'],'evaluator_hash':result['evaluator_hash'],'dataset_hash':r.sha(r.BENCH/'data'/result['category']/'dataset.json')};key=r.digest(identity);meta=OUT/'score_by_identity'/f'{key}.json';meta.parent.mkdir(exist_ok=True)
   if not meta.exists():meta.write_text(json.dumps({'identity':identity,'result':s},indent=2))

def verify():
 f=r.load(OUT/'FREEZE.json')
 for name,key in [('PREREGISTERED_REPLAY_SPEC.md','spec_hash'),('POPULATION_MANIFEST.json','population_hash'),('replay.py','replay_hash'),('uno_recalc.py','uno_helper_hash')]:assert r.sha(OUT/name)==f[key]
 assert r.sha(r.BENCH/'evaluation/evaluation.py')==f['evaluator_hash']
 return f

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--row-id');args=ap.parse_args();freeze=verify();manifest=r.load(OUT/'POPULATION_MANIFEST.json');rows=manifest['eligible']
 if args.row_id:
  resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3));gc.set_threshold(400,5,2)
  row=next((x for x in rows if x['id']==args.row_id),None)
  if row is None:
   row=next(x for x in r.load(OUT/'PHASE12_REPLICATION_MANIFEST.json')['supplement'] if x['id']==args.row_id)
  r.score=bounded_score;work=OUT/'artifacts'/row['id'];candidate_events=[];original_load=r.openpyxl.load_workbook;r.openpyxl.load_workbook=candidate_loader(original_load,work,candidate_events)
  try:result=r.replay(row,OUT/'artifacts')
  finally:
   r.openpyxl.load_workbook=original_load;shutil.rmtree(work/'.parsed_objects',ignore_errors=True)
   for parsed_cache in work.rglob('.scored_objects'):shutil.rmtree(parsed_cache,ignore_errors=True)
  result['candidate_parse_cache_events']=candidate_events;result['execution_wrapper_hash']=r.sha(Path(__file__));result['reference_parse_cache_implementation_hash']=r.sha(OUT/'reference_parse_cache.py');result['execution_supplement_hash']=r.sha(OUT/'EXECUTION_RECOVERY.md');(OUT/'artifacts'/row['id']/'result.json').write_text(json.dumps(result,indent=2));print(result['id'],result['classification'],flush=True);return
 scheduler_lock=(OUT/'scheduler.lock').open('w');r.fcntl.flock(scheduler_lock,r.fcntl.LOCK_EX|r.fcntl.LOCK_NB)
 ledgers={n:[json.loads(l) for l in (OUT/(n+'.jsonl')).read_text().splitlines()] for n in r.LEDGERS};committed=ledgers['BASELINE_CORRECTION_LEDGER'];ids={x['id'] for x in committed};assert all([x['id'] for x in v]==[x['id'] for x in committed] for v in ledgers.values())
 recovered=[]
 for p in sorted((OUT/'artifacts').glob('*/result.json')):
  result=r.load(p)
  if result['id'] in ids:continue
  assert r.sha(r.ROOT/result['V0_source'])==result['V0_hash'] and result['evaluator_hash']==freeze['evaluator_hash']
  if result.get('V1_artifact'):assert r.sha(r.ROOT/result['V1_artifact'])==result['V1_hash']
  r.append_ledgers(result,OUT);recovered.append(result['id']);ids.add(result['id']);committed.append(result)
 seed_scores(committed)
 old=r.load(OUT/'REPLAY_EXECUTION.json');old['interrupted']=True;old['interruption_reason']=os.environ.get('PHASE12R_RESUME_REASON','scheduler interrupted; completed results preserved');old['last_progress_write_utc']=datetime.fromtimestamp((OUT/'REPLAY_PROGRESS.jsonl').stat().st_mtime,timezone.utc).isoformat();old['active_wall_seconds_lower_bound']=max(0,(OUT/'REPLAY_PROGRESS.jsonl').stat().st_mtime-datetime.fromisoformat(old['started_utc']).timestamp())
 attempts=[int(p.stem.rsplit('_',1)[1]) for p in OUT.glob('REPLAY_EXECUTION_ATTEMPT_*.json')];attempt=max(attempts,default=0)+1
 (OUT/f'REPLAY_EXECUTION_ATTEMPT_{attempt}.json').write_text(json.dumps(old,indent=2));shutil.copyfile(OUT/'REPLAY_PROGRESS.jsonl',OUT/f'REPLAY_PROGRESS_ATTEMPT_{attempt}.jsonl');shutil.copyfile(OUT/'REPLAY_STDERR.log',OUT/f'REPLAY_STDERR_ATTEMPT_{attempt}.log')
 start=time.monotonic();record={'started_utc':datetime.now(timezone.utc).isoformat(),'trajectory_model_calls':0,'trajectory_model_cost_usd':0,'model_use':'independent reviews only','scheduler':'one workbook subprocess at a time','memory_limit_GiB_per_workbook':7,'workbook_timeout_seconds':900,'recovered_row_ids':recovered,'execution_amendment_hash':r.sha(OUT/'EXECUTION_RECOVERY.md')};(OUT/'REPLAY_EXECUTION.json').write_text(json.dumps(record,indent=2))
 pending=sorted([x for x in rows if x['id'] not in ids],key=lambda x:(x['stratum'],x['run'],x['task']));print('pending',len(pending),'recovered',recovered,flush=True)
 with (OUT/'REPLAY_PROGRESS.jsonl').open('a') as progress,(OUT/'REPLAY_STDERR.log').open('a') as err:
  for i,row in enumerate(pending,1):
   path=OUT/'artifacts'/row['id']/'result.json';t=time.monotonic();p=subprocess.Popen([sys.executable,str(Path(__file__)), '--row-id',row['id']],stdout=subprocess.DEVNULL,stderr=err,start_new_session=True,env={**os.environ,'LC_ALL':'C.UTF-8','LANG':'C.UTF-8','TZ':'UTC'})
   try:code=p.wait(timeout=900)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGTERM);p.wait();code=-15
   if path.exists():result=r.load(path)
   else:
    result={**row,'classification':'UNSCORABLE','formula_identity':'UNDETERMINED','interpretation_impact':'UNKNOWN','replay_error':f'WORKBOOK_PROCESS_EXIT_{code}_OR_TIMEOUT_900S','recalc':{'status':'RECALC_FAILED','error':'workbook execution failed; no unrecalculated fallback','elapsed_seconds':time.monotonic()-t},'total_elapsed_seconds':time.monotonic()-t,'evaluator_hash':freeze['evaluator_hash']};path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(result,indent=2))
   r.append_ledgers(result,OUT);status={'progress':f'{i}/{len(pending)}','id':row['id'],'stratum':row['stratum'],'task':row['task'],'classification':result['classification'],'error':result.get('replay_error'),'seconds':time.monotonic()-t};progress.write(json.dumps(status)+'\n');progress.flush()
   if i%10==0 or result.get('replay_error'):print(json.dumps({'completed_since_resume':i,'pending_total':len(pending),'technical_error':result.get('replay_error')}),flush=True)
 record.update(ended_utc=datetime.now(timezone.utc).isoformat(),total_replay_wall_seconds=time.monotonic()-start,return_code=0);(OUT/'REPLAY_EXECUTION.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2),flush=True)
if __name__=='__main__':main()
