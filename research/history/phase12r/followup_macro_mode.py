"""Single preregistered post-primary config follow-up; no primary artifact mutation."""
import argparse,gc,json,os,resource,shutil,signal,subprocess,sys,time
from pathlib import Path
import replay as r
from bounded_resume import bounded_score,scored_package_identity
from reference_parse_cache import candidate_loader
OUT=r.OUT;DEST=OUT/'followup_macro_mode'
def prepare():
 spec=OUT/'FOLLOWUP_MACRO_MODE_SPEC.md';assert r.sha(spec)==(OUT/'FOLLOWUP_MACRO_MODE_SPEC.sha256').read_text().split()[0]
 main=[json.loads(l) for l in (OUT/'BASELINE_CORRECTION_LEDGER.jsonl').read_text().splitlines()];assert len(main)==len(r.load(OUT/'POPULATION_MANIFEST.json')['eligible'])
 supplement=[json.loads(l) for l in (OUT/'PHASE12_REPLICATION.jsonl').read_text().splitlines() if l.strip()];supplement=[x for x in supplement if not x.get('prevalence_eligible',True)]
 chosen=[x for x in main+supplement if x['stratum']!='P3' and x.get('recalc',{}).get('status')=='RECALC_PASS' and x.get('V1_artifact')];assert len(chosen)<=379
 original=(OUT/'uno_recalc.py').read_text();assert original.count("prop('MacroExecutionMode',4)")==1 and original.count("'macro_execution_mode':4")==1
 helper=original.replace("prop('MacroExecutionMode',4)","prop('MacroExecutionMode',0)").replace("'macro_execution_mode':4","'macro_execution_mode':0")
 DEST.mkdir(exist_ok=True);hp=DEST/'uno_recalc_macro_disabled.py'
 if hp.exists():assert hp.read_text()==helper
 else:hp.write_text(helper)
 qualification=OUT/'FOLLOWUP_EXECUTION_QUALIFICATION.md';assert r.sha(qualification)==(OUT/'FOLLOWUP_EXECUTION_QUALIFICATION.sha256').read_text().split()[0]
 payload={'hypothesis':'macro mode0 vs executed mode4 equivalence in all ordinary RECALC_PASS cases, not outcome-selected','spec_hash':r.sha(spec),'execution_qualification_hash':r.sha(qualification),'scoring_wrapper_hash':r.sha(OUT/'bounded_resume.py'),'scored_object_cache_hash':r.sha(OUT/'scored_object_cache.py'),'source_helper_hash':r.sha(OUT/'uno_recalc.py'),'mode0_helper_hash':r.sha(hp),'implementation_hash':r.sha(Path(__file__)),'primary_ledger_hash':r.sha(OUT/'BASELINE_CORRECTION_LEDGER.jsonl'),'replication_ledger_hash':r.sha(OUT/'PHASE12_REPLICATION.jsonl'),'rows':chosen,'row_count':len(chosen),'maximum_rows':379}
 mp=DEST/'MANIFEST.json'
 if mp.exists():assert r.load(mp)==payload
 else:mp.write_text(json.dumps(payload,indent=2));(DEST/'MANIFEST.sha256').write_text(r.sha(mp)+'  MANIFEST.json\n')
 return payload

def row_job(row,manifest):
 resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3));gc.set_threshold(400,5,2)
 work=DEST/'artifacts'/row['id'];work.mkdir(parents=True,exist_ok=True);v0=r.ROOT/row['V0_artifact'];primary=r.ROOT/row['V1_artifact'];assert r.sha(v0)==row['V0_hash'] and r.sha(primary)==row['V1_hash']
 shared=DEST/'by_source_hash'/row['V0_hash'];shared.mkdir(parents=True,exist_ok=True);mode0=shared/'V1_MACRO_MODE0.xlsx';meta=shared/'recalc.json';t=time.monotonic()
 if not meta.exists():
  cmd=['/usr/bin/python3',str(DEST/'uno_recalc_macro_disabled.py'),str(v0.resolve()),str(mode0.resolve()),str((shared/'profile').resolve())];p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env={**os.environ,'LC_ALL':'C.UTF-8','LANG':'C.UTF-8','TZ':'UTC'})
  try:
   stdout,stderr=p.communicate(timeout=180);rc={**json.loads(stdout.strip().splitlines()[-1]),'helper_command':cmd,'elapsed_seconds':time.monotonic()-t,'stderr':stderr[-1000:]} if p.returncode==0 and mode0.exists() else {'status':'RECALC_FAILED','error':(stdout+stderr)[-4000:],'elapsed_seconds':time.monotonic()-t}
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGTERM);p.communicate();rc={'status':'RECALC_FAILED','error':'TIMEOUT_180_SECONDS','elapsed_seconds':time.monotonic()-t}
  meta.write_text(json.dumps(rc,indent=2));shutil.rmtree(shared/'profile',ignore_errors=True)
 rc=r.load(meta);result={'id':row['id'],'task':row['task'],'run':row['run'],'stratum':row['stratum'],'V0_hash':row['V0_hash'],'mode4_hash':row['V1_hash'],'mode4_artifact':row['V1_artifact'],'mode0_recalc':rc,'classification':'FOLLOWUP_UNRESOLVED','spec_hash':manifest['spec_hash'],'manifest_hash':r.sha(DEST/'MANIFEST.json')}
 if rc['status']=='RECALC_PASS':
  candidate=work/'V1_MACRO_MODE0.xlsx';shutil.copyfile(mode0,candidate);result.update(mode0_hash=r.sha(candidate),mode0_artifact=str(candidate.relative_to(r.ROOT)))
  result['package_diffs']=r.package_diff(primary,candidate)
  if scored_package_identity(primary)==scored_package_identity(candidate):
   # Exact all-part payload identity except the already excluded nonscored core/app properties.
   # This proves complete observed formula/cache/semantic identity without duplicate full parsing.
   c4,_,_=r.xml_cells(primary);result['formula_identity']='FORMULAS_BYTE_IDENTICAL';result['semantics_equal']=True;result['cache_equal']=True;result['cache_summary']=r.cache_summary(c4,c4);del c4
   result['comparison_execution_basis']='all uncompressed XLSX part bytes identical except nonscored core/app properties under existing exact package reuse rule'
  else:
   s4=r.semantic_snapshot(primary);gc.collect();s0=r.semantic_snapshot(candidate);gc.collect();c4,f4,_=r.xml_cells(primary);c0,f0,_=r.xml_cells(candidate)
   result['formula_identity']=r.identity(s4,s0,f4,f0);result['semantics_equal']=s4==s0;result['cache_equal']=c4==c0;result['cache_summary']=r.cache_summary(c4,c0)
   result['comparison_execution_basis']='full frozen semantic snapshot plus raw formula/cache extraction'
   del s4,s0,c4,c0,f4,f0
  gc.collect()
  events=[];native=r.openpyxl.load_workbook;r.openpyxl.load_workbook=candidate_loader(native,work,events)
  try:
   mode4_current=bounded_score(row,primary,work/'score_mode4_current');score=bounded_score(row,candidate,work/'score')
  finally:r.openpyxl.load_workbook=native;shutil.rmtree(work/'.parsed_objects',ignore_errors=True)
  result['mode0_score']=score;result['mode4_score']=mode4_current;result['frozen_primary_mode4_score']=row.get('V1_score');result['candidate_parse_events']=events;result['comparison_basis']='same current unchanged official entrypoint and validated execution wrapper for both mode4/mode0; earlier failures retained separately'
  if score['status']=='SCORE_PASS' and mode4_current['status']=='SCORE_PASS':
   result['delta']={k:score['official'][k]-mode4_current['official'][k] for k in r.KEYS};result['official_tuple_equal']=all(x==0 for x in result['delta'].values())
   result['classification']='MACRO_MODE_EQUIVALENCE_CONFIRMED' if result['semantics_equal'] and result['cache_equal'] and result['formula_identity']=='FORMULAS_BYTE_IDENTICAL' and result['official_tuple_equal'] else 'MACRO_MODE_EQUIVALENCE_NOT_ESTABLISHED'
 result['elapsed_seconds']=time.monotonic()-t;(work/'result.json').write_text(json.dumps(result,indent=2));print(row['id'],result['classification'],flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--row-id');args=ap.parse_args()
 if args.row_id:
  manifest=r.load(DEST/'MANIFEST.json');assert r.sha(DEST/'MANIFEST.json')==(DEST/'MANIFEST.sha256').read_text().split()[0];assert r.sha(DEST/'uno_recalc_macro_disabled.py')==manifest['mode0_helper_hash'];assert r.sha(Path(__file__))==manifest['implementation_hash'];row=next(x for x in manifest['rows'] if x['id']==args.row_id);row_job(row,manifest);return
 manifest=prepare();results=[];start=time.monotonic()
 with (DEST/'STDERR.log').open('a') as err:
  for i,row in enumerate(manifest['rows'],1):
   path=DEST/'artifacts'/row['id']/'result.json'
   if not path.exists():
    p=subprocess.Popen([sys.executable,str(Path(__file__)),'--row-id',row['id']],stdout=subprocess.DEVNULL,stderr=err,start_new_session=True,env={**os.environ,'LC_ALL':'C.UTF-8','LANG':'C.UTF-8','TZ':'UTC'})
    try:code=p.wait(timeout=900)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGTERM);p.wait();code=-15
    if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'id':row['id'],'task':row['task'],'classification':'FOLLOWUP_UNRESOLVED','error':f'PROCESS_EXIT_{code}_OR_TIMEOUT_900S'}))
   results.append(r.load(path));(DEST/'RESULTS.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in results))
   if i%10==0:print('follow-up',i,'/',len(manifest['rows']),flush=True)
 from collections import Counter
 summary={'rows':len(results),'classifications':dict(Counter(x['classification'] for x in results)),'formula_identity':dict(Counter(x.get('formula_identity','UNDETERMINED') for x in results)),'official_outcome_differences':sum(x.get('official_tuple_equal') is False for x in results),'semantics_differences':sum(x.get('semantics_equal') is False for x in results),'cache_differences':sum(x.get('cache_equal') is False for x in results),'elapsed_wall_seconds':time.monotonic()-start,'manifest_hash':r.sha(DEST/'MANIFEST.json'),'results_hash':r.sha(DEST/'RESULTS.jsonl'),'one_bounded_followup_consumed':True};(DEST/'SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
