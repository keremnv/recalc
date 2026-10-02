"""Share immutable identical derived-cache/V1 storage; originals never linked."""
import hashlib,json,os
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
helper_hash=hashlib.sha256((OUT/'uno_recalc.py').read_bytes()).hexdigest()[:16]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[json.loads(l) for l in (OUT/'BASELINE_CORRECTION_LEDGER.jsonl').read_text().splitlines()];saved=0;linked=[]
for row in records:
 if not row.get('V1_artifact'):continue
 artifact=ROOT/row['V1_artifact'];cache=OUT/'recalc_by_hash'/helper_hash/row['V0_hash']/'V1.xlsx'
 if not cache.exists() or cache.stat().st_ino==artifact.stat().st_ino:continue
 assert artifact.is_relative_to(OUT/'artifacts') and cache.is_relative_to(OUT/'recalc_by_hash')
 assert sha(cache)==sha(artifact)==row['V1_hash']
 size=cache.stat().st_size;temp=cache.with_name('V1.storage_link.'+str(os.getpid())+'.part');os.link(artifact,temp);os.replace(temp,cache)
 assert sha(cache)==row['V1_hash'];saved+=size;linked.append(row['id'])
log=OUT/'DERIVED_STORAGE_AUDIT.jsonl'
with log.open('a') as f:f.write(json.dumps({'mode':'atomic hardlink deduplication of immutable derived cache and committed V1 only; no original or V0 linked','bytes_redundant_storage_removed':saved,'committed_ids':linked})+'\n')
print('derived duplicates shared',len(linked),'storage saved bytes',saved)
