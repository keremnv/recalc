"""Register already-computed score identities, without evaluating or interpreting."""
import json
from pathlib import Path
import replay as r
from bounded_resume import scored_package_identity
n=0
for line in (r.OUT/'BASELINE_CORRECTION_LEDGER.jsonl').read_text().splitlines():
 result=json.loads(line)
 for lab,artifact in [('current_V0_score','V0_artifact'),('V1_score','V1_artifact')]:
  score=result.get(lab);p=result.get(artifact)
  if not score or not p or score['status']!='SCORE_PASS':continue
  identity={'candidate_hash':score['candidate_hash'],'task':result['task'],'input_hash':result['input_hash'],'gold_hash':result['gold_hash'],'evaluator_hash':result['evaluator_hash'],'dataset_hash':r.sha(r.BENCH/'data'/result['category']/'dataset.json')};key=r.digest(identity);package_identity={**identity,'candidate_hash':scored_package_identity(r.ROOT/p)};package_key=r.digest(package_identity);alias=r.OUT/'score_package_aliases'/f'{package_key}.json';alias.parent.mkdir(exist_ok=True)
  if not alias.exists():alias.write_text(json.dumps({'identity':package_identity,'result':score,'execution_key':key}));n+=1
print('registered identical scoring computations',n)
