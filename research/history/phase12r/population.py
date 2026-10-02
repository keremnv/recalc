"""Deterministic historical population inventory; no model or evaluator calls."""
import hashlib,json,re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/history/phase12r'
BENCH=ROOT/'benchmark-data/SpreadsheetBench-2'
CATS=('Template','Financial_Model','Debugging')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text())
def norm(d):
 def get(*ks): return next((d[k] for k in ks if k in d),None)
 a=get('accuracy','official_exact','official_accuracy','acc');m=get('modification_accuracy','official_modification','modification','mod');r=get('regression_accuracy','official_regression','regression','reg')
 if all(isinstance(x,(int,float)) for x in (a,m,r)):return dict(accuracy=a,modification_accuracy=m,regression_accuracy=r,error_message=get('error_message','eval_error') or '')
def main():
 datasets={c:{str(d['id']):d for d in load(BENCH/'data'/c/'dataset.json')} for c in CATS}
 rows=[];ex=[];aliases=[]
 reports=list(ROOT.glob('*.md'))+list((ROOT/'research/evidence').glob('*.md'))
 def add(run,task,src,score,scorepath,stratum,status,agent=None):
  cat,tid=task.split(':',1); why=None
  if cat not in datasets or tid not in datasets[cat]:why='TASK_NOT_IN_CURRENT_DATASET'
  elif not src or not src.is_file():why='NO_ATTRIBUTABLE_SUBMITTED_WORKBOOK'
  elif norm(score) is None:why='NO_OFFICIAL_NUMERIC_SCORE'
  if why:ex.append(dict(run=run,task=task,reason=why,stratum=stratum));return
  d=datasets[cat][tid];inp=BENCH/'data'/cat/d['spreadsheet_path'];gold=BENCH/'data'/cat/d['golden_response_path']
  if not inp.exists() or not gold.exists():ex.append(dict(run=run,task=task,reason='MISSING_INPUT_OR_GOLD'));return
  rid=hashlib.sha256((run+'|'+task).encode()).hexdigest()[:16]
  refs=[str(p.relative_to(ROOT)) for p in reports if run.split('/')[0].lower() in p.read_text(errors='replace').lower() or (run.startswith('benchmark-data') and run.split('/')[-1] in p.read_text(errors='replace'))]
  rows.append(dict(id=rid,run=run,task=task,category=cat,stratum=stratum,status=status,V0_source=str(src.relative_to(ROOT)),V0_hash=sha(src),input=str(inp.relative_to(ROOT)),input_hash=sha(inp),gold=str(gold.relative_to(ROOT)),gold_hash=sha(gold),original_score=norm(score),score_reference=str(scorepath.relative_to(ROOT)),score_reference_hash=sha(scorepath),agent_output=str(agent.relative_to(ROOT)) if agent and agent.exists() else None,agent_output_hash=sha(agent) if agent and agent.exists() else None,historical_byte_linkage='ARCHIVED_SUBMISSION' if 'submission/outputs' in str(src) or 'score_staging' in str(src) else 'RUN_LOCAL_UNVERIFIED',historical_evaluator_identity='UNAVAILABLE_UNLESS_REPRODUCED',historical_report_references=refs,phase12_discovery=run.startswith('research/history/phase12/')))
 # All archived openrouter scores; provenance from ledger tool schemas.
 for sf in sorted((BENCH/'benchmark-runs/openrouter').glob('*/official_scores.json')):
  root=sf.parent;scores=load(sf).get('tasks',{});ledger=root/'ledger.jsonl';records=[]
  if ledger.exists():
   for l in ledger.read_text().splitlines():
    try:records.append(json.loads(l))
    except ValueError:pass
  for task,score in sorted(scores.items()):
   if ':' not in task or task.split(':')[0] not in CATS:continue
   rec=next((r for r in reversed(records) if r.get('task')==task),{})
   schema=rec.get('effective_tool_schema',{});bundles=schema.get('bundles',[])
   names={n for b in bundles for n in b.get('tools',{})}
   # Older control ledgers lack explicit schema; frozen arm=control provides provenance,
   # independently checked against retained config/trajectory in inventory coverage audit.
   ordinary=rec.get('arm')=='control' and (not names or not any(n.startswith('calc_') for n in names))
   stratum='P1' if ordinary else 'P3'
   cat,tid=task.split(':');agent=root/f'{cat}-{tid}'/'output.xlsx';submitted=root/'submission/outputs'/cat/f'{tid}_output.xlsx'
   src=submitted if submitted.exists() else agent
   add(str(root.relative_to(ROOT)),task,src,score,sf,stratum,rec.get('status','UNKNOWN'),agent)
 # All research run_record files and their experiment-local official score families.
 for exp in sorted(ROOT.iterdir()):
  if not exp.is_dir() or exp.name.startswith('.') or exp.name in ('benchmark-data','phase12r','src','tests'):continue
  records=list(exp.rglob('run_record.json'))
  if not records:continue
  scorefiles=sorted({*exp.glob('*score*.json'),*exp.glob('*scores*.json'),*exp.glob('score_staging/**/official_scores.json'),*exp.glob('runs/*/official_scores.json')})
  candidates=[]
  def walk(d,sf,arm=None):
   if isinstance(d,list):
    for x in d:walk(x,sf,arm)
   elif isinstance(d,dict):
    if norm(d) and (d.get('task_id') or d.get('task')):candidates.append((d.get('task_id') or d['task'],d.get('arm',arm),d,sf))
    if isinstance(d.get('tasks'),dict):
     for t,x in d['tasks'].items():
      if norm(x):candidates.append((t,arm,x,sf))
    if isinstance(d.get('rows'),list):walk(d['rows'],sf,arm)
    if 'arms' in d:
     for a,x in d['arms'].items():walk(x,sf,a)
    for k,x in d.items():
     if re.match(r'^(Template|Debugging|Financial_Model)[_:]',k) and isinstance(x,dict) and norm(x):
      m=re.match(r'^(Template|Debugging|Financial_Model)_(\d+_\d+)_(.+)',k)
      if m:candidates.append((m[1]+':'+m[2],m[3],x,sf))
  for sf in scorefiles:
   try:walk(load(sf),sf,sf.parent.name if sf.parent.name in ('H0','H1','A','B','C','D','CONTROL','TREATMENT') else None)
   except (ValueError,TypeError):pass
  if exp.name=='phase12':
   sf=exp/'ledgers/scorer_outcome.jsonl'
   for l in sf.read_text().splitlines():
    d=json.loads(l);candidates.append((d['task_id'],d['arm'],d,sf))
  for rp in sorted(records):
   rec=load(rp);rd=rp.parent;run=str(rd.relative_to(ROOT));task=rec.get('task_id') or rec.get('task');arm=rec.get('arm')
   if not task or ':' not in task or task.split(':')[0] not in CATS:ex.append(dict(run=run,reason='NO_TASK_ID'));continue
   status=rec.get('status','UNKNOWN')
   if status not in ('SUBMITTED','SUBMITTED_AFTER_REPAIR_WINDOW','completed'):
    ex.append(dict(run=run,task=task,reason='NOT_SUBMITTED',status=status,stratum='P2'));continue
   if 'preserved_infra' in run:ex.append(dict(run=run,task=task,reason='INFRA_DUPLICATE'));continue
   matches=[c for c in candidates if c[0]==task and (c[1]==arm or c[1]==arm+'_R1' and rd.name.endswith('_R1'))]
   # Enforce repetition/run/pop linkage where available; distinct official files for r2.
   rid=rec.get('run_id');pop=rec.get('pop')
   # Directory identity disambiguates primary versus replication scores.
   repnum=re.search(r'_rep(\d+)_',rd.name)
   if repnum:matches=[c for c in matches if str(c[2].get('rep','')).lstrip('r')==repnum[1]]
   if not re.search(r'(?:_|/)(r2)(?:/|$)',run):matches=[c for c in matches if 'r2' not in c[3].stem]
   if rid:matches=[c for c in matches if c[2].get('run_id',rid)==rid]
   if pop:matches=[c for c in matches if c[2].get('pop',pop)==pop]
   repm=re.search(r'(?:_|/)(r[12])(?:/|$)',run)
   if repm:
    suffix='r2' if repm[1]=='r2' else ''
    ms=[c for c in matches if ('r2' in c[3].stem)==bool(suffix)]
    if ms:matches=ms
   if rec.get('rep'):
    matches=[c for c in matches if str(c[2].get('rep',rec['rep'])).lstrip('r')==str(rec['rep']).lstrip('r')]
   agent=rd/'output.xlsx'
   if not agent.exists() and (rd/'work/output.xlsx').exists():agent=rd/'work/output.xlsx'
   cat,tid=task.split(':');src=agent
   # Prefer archived score-stage bytes only when score row uniquely attributable.
   if len(matches)==1 and exp.name in ('phase12','token_affordance_discovery','token_claim_discovery','candidate_a_live','candidate_a_a1_checkpoint_rerun_01'):
    sf=matches[0][3]
    paths=[sf.parent/'submission/outputs'/cat/f'{tid}_output.xlsx',exp/'score_staging'/arm/cat/f'{tid}_output.xlsx']
    if exp.name=='phase12':paths=[exp/'score_staging'/pop/arm/cat/f'{tid}_output.xlsx']
    src=next((p for p in paths if p.exists()),agent)
   # Scores repeated without run identifier are not safe joins.
   unique={json.dumps(norm(c[2]),sort_keys=True) for c in matches}
   if not matches or len(unique)>1:
    ex.append(dict(run=run,task=task,reason='MISSING_OR_AMBIGUOUS_OFFICIAL_SCORE',candidates=len(matches),stratum='P2'));continue
   add(run,task,src,matches[0][2],matches[0][3],'P2',status,agent)
 # Same physical submission source + task is an alias; prefer direct run over staging.
 seen={};dedup=[]
 for r in rows:
  key=(r['V0_source'],r['task'])
  if key in seen:aliases.append(dict(alias=r['run'],canonical=seen[key]));continue
  seen[key]=r['id'];dedup.append(r)
 manifest=dict(protocol='draft pending review',eligible=dedup,excluded=ex,aliases=aliases,counts=dict(Counter(r['stratum'] for r in dedup)),category_counts=dict(Counter(r['stratum']+'/'+r['category'] for r in dedup)),scope='all retained openrouter official score files + repository research run_record directories; no outcome selection')
 (OUT/'POPULATION_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
 print(json.dumps({k:manifest[k] for k in ('counts','category_counts')},indent=2));print('exclusions',Counter(r['reason'] for r in ex))
if __name__=='__main__':main()
