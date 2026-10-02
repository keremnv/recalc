"""Freeze supplemental retained nonsubmitted Phase12 final files, outside prevalence."""
import hashlib,json
from pathlib import Path
import replay as r
out=r.OUT;m=r.load(out/'POPULATION_MANIFEST.json');runs={x['run'] for x in m['eligible']};scores=[json.loads(l) for l in (r.ROOT/'research/history/phase12/ledgers/scorer_outcome.jsonl').read_text().splitlines()];extra=[]
for src in sorted((r.ROOT/'research/history/phase12/runs').glob('*/*/output.xlsx')):
 rd=src.parent;run=str(rd.relative_to(r.ROOT))
 if run in runs:continue
 rec=r.load(rd/'run_record.json');task=rec['task_id'];cat,tid=task.split(':');pop=rec['pop'];arm=rec['arm']
 if arm not in ('CONTROL','TREATMENT','SHAM'):continue
 old=next(x for x in scores if x['pop']==pop and x['task_id']==task and x['arm']==arm);stage=r.ROOT/'research/history/phase12/score_staging'/pop/arm/cat/f'{tid}_output.xlsx';source=stage if stage.exists() else src
 d=next(x for x in r.load(r.BENCH/'data'/cat/'dataset.json') if str(x['id'])==tid);inp=r.BENCH/'data'/cat/d['spreadsheet_path'];gold=r.BENCH/'data'/cat/d['golden_response_path'];sf=r.ROOT/'research/history/phase12/ledgers/scorer_outcome.jsonl'
 extra.append({'id':hashlib.sha256((run+'|'+task).encode()).hexdigest()[:16],'run':run,'task':task,'category':cat,'stratum':'P2_PHASE12_NON_SUBMITTED_SUPPLEMENT','status':rec['status'],'V0_source':str(source.relative_to(r.ROOT)),'V0_hash':r.sha(source),'input':str(inp.relative_to(r.ROOT)),'input_hash':r.sha(inp),'gold':str(gold.relative_to(r.ROOT)),'gold_hash':r.sha(gold),'original_score':{'accuracy':old['official_exact'],'modification_accuracy':old['official_modification'],'regression_accuracy':old['official_regression'],'error_message':old.get('eval_error','')},'score_reference':str(sf.relative_to(r.ROOT)),'score_reference_hash':r.sha(sf),'agent_output':str(src.relative_to(r.ROOT)),'agent_output_hash':r.sha(src),'historical_byte_linkage':'ARCHIVED_SUBMISSION' if stage.exists() else 'RUN_LOCAL_UNVERIFIED','historical_evaluator_identity':'UNAVAILABLE_UNLESS_REPRODUCED','historical_report_references':['PHASE12_POST_EDIT_VERIFICATION_AB_REPORT.md'],'phase12_discovery':True,'prevalence_eligible':False,'supplement_reason':'user requires all relevant Phase12 C/T final files; retained nonsubmitted candidates are not historical submissions'})
p=out/'PHASE12_REPLICATION_MANIFEST.json';p.write_text(json.dumps({'primary_phase12_ids':[x['id'] for x in m['eligible'] if x['run'].startswith('research/history/phase12/')],'supplement':extra,'separate_from_primary':True},indent=2));(out/'PHASE12_REPLICATION_MANIFEST.sha256').write_text(r.sha(p)+'  '+p.name+'\n');print('supplemental nonsubmitted files',len(extra))
