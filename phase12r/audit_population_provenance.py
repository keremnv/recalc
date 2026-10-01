"""Check frozen stratum provenance without using scores or workbook outcomes."""
import hashlib,json
from pathlib import Path
from collections import Counter
import yaml
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'phase12r'
manifest=json.loads((OUT/'POPULATION_MANIFEST.json').read_text());runs={};output=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for row in manifest['eligible']:
 proof={'id':row['id'],'task':row['task'],'stratum':row['stratum'],'run':row['run']}
 if row['stratum']=='P2':proof['tool_provenance']='ORDINARY_RESEARCH_RUN_RECORD';proof['qualification']='all arms retained; post-edit research intervention not clean ordinary control'
 else:
  path=ROOT/row['run'];lp=path/'ledger.jsonl'
  if str(lp) not in runs:runs[str(lp)]=[json.loads(l) for l in lp.read_text().splitlines() if l.strip()]
  rec=next((r for r in reversed(runs[str(lp)]) if r.get('task')==row['task']),{})
  names={n for b in rec.get('effective_tool_schema',{}).get('bundles',[]) for n in b.get('tools',{})};proof['arm']=rec.get('arm');proof['harness']=rec.get('harness');proof['ledger_hash']=sha(lp)
  if names:proof['tool_provenance_source']='ledger.effective_tool_schema'
  else:
   paths=sorted((path/row['task'].replace(':','-')/'trajectory').rglob('config.yaml'))
   if paths:
    cp=paths[0];d=yaml.safe_load(cp.read_text());d=json.loads(d) if isinstance(d,str) else d
    names={Path(b['path']).name for b in d.get('agent',{}).get('tools',{}).get('bundles',[]) if b.get('path')};proof['tool_provenance_source']=str(cp.relative_to(ROOT));proof['config_hash']=sha(cp)
  proof['tool_names']=sorted(names)
  if rec.get('arm')=='control' and names and not any(n.startswith('calc_') or 'semantic' in n for n in names):proof['tool_provenance']='ORDINARY_CONTROL_CONFIRMED'
  elif 'librecalc' in names or any(n.startswith('calc_') or 'semantic' in n for n in names):proof['tool_provenance']='STRUCTURED_HARNESS_CONFIRMED'
  else:proof['tool_provenance']='OLD_NONCONTROL_OR_UNKNOWN_CONTEXT'
 output.append(proof)
assert all(r['tool_provenance']=='ORDINARY_CONTROL_CONFIRMED' for r in output if r['stratum']=='P1')
payload={'population_hash':sha(OUT/'POPULATION_MANIFEST.json'),'method':'retained ledger tools; fallback retained trajectory configuration; no outcome selection','counts':dict(Counter(r['stratum']+'/'+r['tool_provenance'] for r in output)),'rows':output,'qualification':'frozen implementation places all older non-control archives in P3; unknown/nonstructured subsets are context-only, not structured-harness prevalence; no P3 pooled into ordinary primary'}
(OUT/'POPULATION_PROVENANCE_AUDIT.json').write_text(json.dumps(payload,indent=2));print(json.dumps(payload['counts'],indent=2))
