"""Remove only redundant new scoring copies after a row has committed."""
import json,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
rows=[json.loads(l) for l in (OUT/'BASELINE_CORRECTION_LEDGER.jsonl').read_text().splitlines()];count=0;size=0
for r in rows:
 root=OUT/'artifacts'/r['id'];scores={'V0':r.get('current_V0_score'),'V1':r.get('V1_score'),'WITNESS':r.get('cache_sufficiency_witness',{}).get('score')}
 for label,score in scores.items():
  if not score:continue
  for p in (root/'score'/label).glob('*.xlsx'):
   assert hashlib.sha256(p.read_bytes()).hexdigest()==score['candidate_hash'],p
   size+=p.stat().st_size;p.unlink();count+=1
print('redundant committed scoring copies removed',count,'bytes freed',size)
