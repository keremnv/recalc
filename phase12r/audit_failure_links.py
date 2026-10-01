"""Qualify retained claim links only; no scored treatment or primary class changes."""
import json
from pathlib import Path
import replay as r
OUT=r.OUT

def main():
 entries=[json.loads(l) for l in (OUT/'BASELINE_CORRECTION_LEDGER.jsonl').read_text().splitlines()];qualified=[]
 for x in entries:
  if x['classification']!='CACHE_ONLY_SCORE_RECOVERY':continue
  candidates=x.get('historical_claim_evidence',[]);dispositions=[]
  for c in candidates:
   if c['report']=='research/evidence/FINAL_ARCHITECTURE_FREEZE.md':
    reason='Negated semantic-failure phrase concerns malformed input; matched task concerns transient UnicodeDecodeError/runtime fallback, not spreadsheet semantic error.'
   elif c['report']=='research/evidence/ASTRA_TOKEN_DIAGNOSIS_PACKET.md':
    reason='Task co-occurs with token/call ratios and completion discordances; failed helper concerns another task; no run-linked spreadsheet semantic-failure attribution.'
   else:raise RuntimeError('Unreviewed claim candidate: '+str(c))
   dispositions.append({'report':c['report'],'line':c.get('line'),'semantic_failure_attribution_verified':False,'reason':reason})
  qualified.append({'id':x['id'],'task':x['task'],'run':x['run'],'classification':x['classification'],'historical_byte_linkage':x['historical_byte_linkage'],'historical_score_recovery_compatible':x.get('historical_cache_recovery_proven',False),'historical_report_references':x['historical_report_references'],'retained_explicit_semantic_failure_attribution_verified':False,'candidate_link_dispositions':dispositions,'interpretation':'SCORE_BOUNDARY_CACHE_SENSITIVE' if x.get('historical_cache_recovery_proven') else 'NORMALIZED_CANDIDATE_CACHE_SENSITIVE; HISTORICAL_SCORED_BYTES_UNVERIFIED','scope':'absence of a verified link in retained searched evidence, not proof no such claim exists'})
 assert len(qualified)==46
 (OUT/'QUALIFIED_HISTORY_CLAIM_LINKS.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in qualified));print('qualified46links; rejected8 keyword co-occurrences, no verified semantic attribution')
if __name__=='__main__':main()
