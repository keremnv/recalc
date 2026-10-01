"""Add post-replay historical qualifications and raw calculation metadata.

Never edits original history or scored workbooks; preserves raw replay ledger.
"""
import json,hashlib,re,shutil,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'phase12r';Q='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def calc(path):
 if not path or not (ROOT/path).exists():return None
 try:
  with zipfile.ZipFile(ROOT/path) as z:
   wb=ET.fromstring(z.read('xl/workbook.xml'));elem=wb.find(Q+'calcPr');props=wb.find(Q+'workbookPr')
   return {'calcPr':elem.attrib if elem is not None else None,'workbookPr':props.attrib if props is not None else None}
 except (zipfile.BadZipFile,KeyError,ET.ParseError) as e:return {'status':'CALCULATION_METADATA_UNINSPECTABLE','error':type(e).__name__+': '+str(e)}
def main():
 manifest=json.load(open(OUT/'POPULATION_MANIFEST.json'));rows=[json.loads(l) for l in (OUT/'BASELINE_CORRECTION_LEDGER.jsonl').read_text().splitlines()];assert len(rows)==len(manifest['eligible'])
 raw=OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl'
 if raw.exists():assert sha(raw)==sha(OUT/'BASELINE_CORRECTION_LEDGER.jsonl'),'Already enriched; preserve audit'
 else:shutil.copyfile(OUT/'BASELINE_CORRECTION_LEDGER.jsonl',raw)
 freeze=json.load(open(OUT/'LEDGER_FREEZE.json'));assert freeze['ledgers']['BASELINE_CORRECTION_LEDGER.jsonl']==sha(raw)
 out=[];failure_entries=[]
 for r in rows:
  r['interpretation_impact_current_pair_preliminary']=r.get('interpretation_impact');r['prior_failure_interpretation_preliminary']=r.pop('prior_failure_interpretation',None)
  r['ORIGINAL_SCORE']=r['original_score'];r['CURRENT_V0_SCORE']=r.get('current_V0_score',{}).get('official');r['RECALC_SCORE']=r.get('V1_score',{}).get('official');r['cache_change_summary']=r.get('cache_summary');r['historical_evaluator_version_status']='UNAVAILABLE';r['comparison_basis']='current retained official evaluator, normalized V0/V1; historical score stored separately'
  r['calculation_settings']={'V0':calc(r.get('V0_artifact') or r['V0_source']),'V1':calc(r.get('V1_artifact'))}
  historical=r.get('historical_cache_recovery_proven',False);status=r['classification']
  if historical:r['interpretation_impact']='BOUNDARY MOVED'
  elif status=='RECALC_NO_MATERIAL_EFFECT' and r.get('original_score_reproduced') and r['historical_byte_linkage']=='ARCHIVED_SUBMISSION':r['interpretation_impact']='NUMERICALLY CHANGED, INTERPRETATION SAME' if any(v!=0 for v in r.get('delta',{}).values()) else 'UNAFFECTED'
  elif r.get('original_score_reproduced') and r['historical_byte_linkage']=='ARCHIVED_SUBMISSION' and status=='RECALC_REGRESSION':
   r['interpretation_impact']='UNKNOWN';r['regression_interpretation_qualification']='sensitivity under executed recalculation; direction alone does not establish an incorrect original semantic-failure attribution or require historical rebaseline' 
  else:r['interpretation_impact']='UNKNOWN'
  refs=r.get('historical_report_references',[]);specific=[]
  cat,tid=r['task'].split(':');needles=(r['task'],cat+'_'+tid,cat+'-'+tid)
  for ref in refs:
   p=ROOT/ref
   if not p.exists():continue
   lines=p.read_text(errors='replace').splitlines()
   for i,line in enumerate(lines):
    if any(n in line for n in needles):
     context='\n'.join(lines[max(0,i-2):min(len(lines),i+3)])
     if re.search(r'(?i)(semantic|model|formula).{0,70}(fail|wrong|incorrect)|(fail|wrong|incorrect).{0,70}(semantic|model|formula)',context):specific.append({'report':ref,'line':i+1,'context':context})
  # Explicit task-level historical failure ledgers, if retained. No label is inferred
  # from a general report reference or a score-zero by itself.
  experiment=r['run'].split('/')[0]
  if experiment!='benchmark-data':
   for failure in (ROOT/experiment).glob('*failure*.json'):
    try:document=json.loads(failure.read_text())
    except ValueError:continue
    def visit(value):
     if isinstance(value,list):
      for item in value:visit(item)
     elif isinstance(value,dict):
      task=value.get('task_id') or value.get('task')
      text=json.dumps(value)
      if task==r['task'] and re.search(r'(?i)SEMANTIC[_ -]?FAIL|MODEL[_ -]?ERROR|INCORRECT[_ -]?FORMULA|FORMULA[_ -]?ERROR',text):specific.append({'report':str(failure.relative_to(ROOT)),'historical_failure_record':value,'hash':sha(failure)})
      for item in value.values():
       if isinstance(item,(dict,list)):visit(item)
    visit(document)
  if historical:
   r['prior_failure_interpretation']='PRIOR_FAILURE_INTERPRETATION_CACHE_SENSITIVE' if specific else 'SCORE_FAILURE_CACHE_SENSITIVE; PRIOR_SEMANTIC_ATTRIBUTION_NOT_ESTABLISHED'
   r['exact_failure_resolved_by_recalc']=r['original_score']['accuracy']==0 and r['V1_score']['official']['accuracy']==1
   r['remaining_exact_failure_after_recalc']=r['V1_score']['official']['accuracy']==0
   r['historical_recovery_scope']='official exact failure resolved' if r['exact_failure_resolved_by_recalc'] else 'material score-component recovery; does not establish that remaining task failure was cache-only'
   failure_entries.append({'id':r['id'],'run':r['run'],'task':r['task'],'old_score':r['original_score'],'new_score':r['V1_score']['official'],'formula_identity':r['formula_identity'],'impact':r['interpretation_impact'],'prior_failure_interpretation':r['prior_failure_interpretation'],'exact_failure_resolved_by_recalc':r['exact_failure_resolved_by_recalc'],'remaining_exact_failure_after_recalc':r['remaining_exact_failure_after_recalc'],'historical_recovery_scope':r['historical_recovery_scope'],'task_specific_claim_evidence':specific,'broader_report_references':refs,'qualification':'current official reproduces original numeric scores; historical evaluator source identity unavailable'})
  r['historical_claim_evidence']=specific;r['audit_method']='post-replay additive history qualification; classifier, scores, treatment and primary summary unchanged'
  out.append(r)
 (OUT/'BASELINE_CORRECTION_LEDGER.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in out));(OUT/'HISTORICAL_FAILURE_CORRECTIONS.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in failure_entries))
 (OUT/'HISTORICAL_AUDIT_IDENTITY.json').write_text(json.dumps({'raw_ledger_hash':sha(raw),'authoritative_enriched_ledger_hash':sha(OUT/'BASELINE_CORRECTION_LEDGER.jsonl'),'failure_corrections_hash':sha(OUT/'HISTORICAL_FAILURE_CORRECTIONS.jsonl'),'note':'raw replay frozen first; no original historical file changed; primary classifier/score outputs unchanged'},indent=2))
 print('history qualification added',len(out),'proven historical cache-sensitive scores',len(failure_entries))
if __name__=='__main__':main()
