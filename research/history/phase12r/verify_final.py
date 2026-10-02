"""Final integrity/completeness check; no scoring or new workbook diagnostics."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'research/history/phase12r'
HEADINGS=['PHASE 12 MECHANISM CARRIED FORWARD','REPLAY QUESTION','PREREGISTRATION','STRONG REVIEW BEFORE REPLAY','POPULATION','RECALC ENVIRONMENT','ORIGINAL SCORE REPRODUCTION','FORMULA IDENTITY','CACHE STATE','PACKAGE PART CHANGES','RECALCULATED SCORE RESULTS','CACHE ONLY SCORE RECOVERY','RECALC ASSOCIATED AMBIGUOUS CASES','RECALC REGRESSIONS','TEMPLATE','FINANCIAL MODEL','DEBUGGING','TASK LEVEL CLUSTERING','PHASE 12 REPLICATION','HISTORICAL FAILURE REINTERPRETATION','PRIOR CLAIM IMPACT','RECALC COST','SURPRISE TRIGGER STATUS','FOLLOW UP PROBE','STRONG REVIEW AFTER REPLAY','RECALC FAIR BASELINE VERDICT','HISTORICAL EVIDENCE VERDICT','SCAFFOLD RECOMMENDATION','EVALUATOR RECOMMENDATION','REBASELINE SCOPE','NEXT STEP']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()]
def main():
 freeze=json.load(open(OUT/'FREEZE.json'));m=json.load(open(OUT/'POPULATION_MANIFEST.json'));protected=json.load(open(OUT/'PROTECTED_HISTORY_HASHES.json'));changed=[p for p,h in protected.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h];assert not changed,changed
 for name,key in [('PREREGISTERED_REPLAY_SPEC.md','spec_hash'),('POPULATION_MANIFEST.json','population_hash'),('replay.py','replay_hash'),('uno_recalc.py','uno_helper_hash')]:assert sha(OUT/name)==freeze[key]
 post=json.load(open(OUT/'POST_REVIEW_EVIDENCE_FREEZE.json'))
 for name,h in post['hashes'].items():
  source=OUT/({'RECALC_FAIR_BASELINE_SPEC.md':'RECALC_FAIR_BASELINE_SPEC_BEFORE_POST_REVIEW.md','HISTORICAL_CLAIM_IMPACT.md':'HISTORICAL_CLAIM_IMPACT_BEFORE_POST_REVIEW.md'}.get(name,name));assert sha(source)==h,(name,source)
 assert sha(OUT/'PRIMARY_ANALYSIS.md')==(OUT/'PRIMARY_ANALYSIS.sha256').read_text().split()[0]
 expected={x['id'] for x in m['eligible']};ledger=rows(OUT/'BASELINE_CORRECTION_LEDGER.jsonl');assert len(ledger)==len(expected) and {x['id'] for x in ledger}==expected
 surprise=json.load(open(OUT/'SURPRISE_EVIDENCE_FREEZE.json'))
 for name,h in surprise.items():
  source=OUT/({'BASELINE_CORRECTION_LEDGER.jsonl':'BASELINE_CORRECTION_LEDGER_HISTORY_QUALIFIED_FIRST_PASS.jsonl','SCORE_REPLAY.jsonl':'SCORE_REPLAY_FIRST_PASS.jsonl'}.get(name,name));assert sha(source)==h,(name,source)
 assert sha(OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl')==json.load(open(OUT/'LEDGER_FREEZE.json'))['ledgers']['BASELINE_CORRECTION_LEDGER.jsonl']
 assert sha(OUT/'SCORE_REPLAY_FIRST_PASS.jsonl')==json.load(open(OUT/'LEDGER_FREEZE.json'))['ledgers']['SCORE_REPLAY.jsonl']
 assert sha(OUT/'SUMMARY.json')==json.load(open(OUT/'LEDGER_FREEZE.json'))['summary_hash']
 for name,key in [('ENVIRONMENT.json','environment_hash'),('test_replay.py','tests_hash'),('PROTECTED_HISTORY_HASHES.json','protected_history_manifest_hash')]:assert sha(OUT/name)==freeze[key]
 assert sha(ROOT/'benchmark-data/SpreadsheetBench-2/evaluation/evaluation.py')==freeze['evaluator_hash']
 for name in ['FORMULA_IDENTITY','CACHE_STATE','PACKAGE_DIFFS','SCORE_REPLAY']:
  rr=rows(OUT/(name+'.jsonl'));assert len(rr)==len(expected) and {x['id'] for x in rr}==expected
 normal=json.load(open(OUT/'scoring_recovery/MANIFEST.json'));assert normal['count']==403
 normalized=rows(OUT/'scoring_recovery/RESULTS.jsonl');assert len(normalized)==403 and {x['id'] for x in normalized}==set(normal['ids'])
 assert all(x['stratum']=='P3' for x in normalized)
 follow=json.load(open(OUT/'followup_macro_mode/SUMMARY.json'));fm=json.load(open(OUT/'followup_macro_mode/MANIFEST.json'));fr=rows(OUT/'followup_macro_mode/RESULTS.jsonl');assert len(fr)==follow['rows']==fm['row_count'];assert follow['one_bounded_followup_consumed'];assert sha(OUT/'followup_macro_mode/MANIFEST.json')==follow['manifest_hash'];assert sha(OUT/'followup_macro_mode/RESULTS.jsonl')==follow['results_hash']
 for x in fr:
  if x.get('mode0_artifact'):assert sha(ROOT/x['mode0_artifact'])==x['mode0_hash']
 for r in ledger+normalized:
  if r.get('NORMALIZED_EXECUTION_RECOVERY'):
   n=r['NORMALIZED_EXECUTION_RECOVERY'];assert sha(ROOT/n['artifact'])==n['hash'];nr=json.load(open(ROOT/n['artifact']));assert nr['V0_hash']==r['V0_hash'] and nr.get('V1_hash')==r.get('V1_hash')
  assert sha(ROOT/r['V0_source'])==r['V0_hash']
  if r.get('V0_artifact'):assert sha(ROOT/r['V0_artifact'])==r['V0_hash']
  if r.get('V1_artifact'):assert sha(ROOT/r['V1_artifact'])==r['V1_hash']
  if r['classification']=='CACHE_ONLY_SCORE_RECOVERY':
   assert r['formula_identity'] in ('FORMULAS_BYTE_IDENTICAL','FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED');assert not r['semantic_differences'];w=r['cache_sufficiency_witness'];assert w['cache_only_proof_pass'] and w['V1_assessed_surface_hash']==w['witness_assessed_surface_hash'];assert sha(ROOT/w['artifact'])==w['hash'];assert any(r['delta'][k]>=.01-1e-12 for k in r['delta'])
 required=['PREREGISTERED_REPLAY_SPEC.md','PREREGISTERED_REPLAY_SPEC.sha256','POPULATION_MANIFEST.json','RECALC_ENVIRONMENT.md','replay.py','test_replay.py','FORMULA_IDENTITY.jsonl','CACHE_STATE.jsonl','PACKAGE_DIFFS.jsonl','SCORE_REPLAY.jsonl','BASELINE_CORRECTION_LEDGER.jsonl','HISTORICAL_CLAIM_IMPACT.md','RECALC_FAIR_BASELINE_SPEC.md','STRONG_REVIEW_PREREG.md','STRONG_REVIEW_POST.md']
 assert all((OUT/p).exists() for p in required)
 report=ROOT/'research/reports/PHASE12R_RECALC_FAIR_REPLAY_REPORT.md';headings=[l[3:] for l in report.read_text().splitlines() if l.startswith('## ')];assert headings==HEADINGS,(len(headings),headings)
 artifacts=[OUT/p for p in required]+[report]+list(OUT.glob('*REVIEW*.md'))+[OUT/'SUMMARY.json',OUT/'FREEZE.json',OUT/'LEDGER_FREEZE.json',OUT/'EXECUTION_RECOVERY.md',OUT/'REPLAY_EXECUTION.json',OUT/'PRIMARY_ANALYSIS.md',OUT/'PRIMARY_ANALYSIS.sha256',OUT/'PHASE12_REPLICATION_MANIFEST.json',OUT/'PHASE12_REPLICATION.jsonl']
 artifacts+=[OUT/'POST_REVIEW_EVIDENCE_FREEZE.json',OUT/'SCORE_REPLAY_FIRST_PASS.jsonl',OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl',OUT/'SCORING_RECOVERY_OPTIMIZATION_PARITY.json',OUT/'QUALIFIED_HISTORY_CLAIM_LINKS.jsonl',OUT/'FOLLOWUP_COST_ACCOUNTING.json',OUT/'P1_HARM_EXISTING_CELL_INSPECTION.json',OUT/'AUXILIARY_SOURCE_VERSION_ARCHIVE.json']
 artifacts+=list(OUT.glob('*.md'))+list(OUT.glob('*.sha256'))+[OUT/'scoring_recovery'/n for n in ['MANIFEST.json','MANIFEST.sha256','IMPLEMENTATION_AMENDMENT.json','IDENTITY.json','RESULTS.jsonl','SUMMARY.json','EXECUTION.json']]+[OUT/'followup_macro_mode'/n for n in ['MANIFEST.json','MANIFEST.sha256','SUMMARY.json','RESULTS.jsonl','uno_recalc_macro_disabled.py']]
 results={'normalized_context_rows':len(normalized),'bounded_followup_rows':len(fr),'protected_original_files_verified':len(protected),'protected_changes':changed,'eligible_primary_replayed':len(ledger),'ledger_ids_consistent':True,'all_strong_recoveries_have_witness_identity_proof':True,'required_final_sections_exact':headings,'frozen_protocol_unchanged':True,'deliverable_hashes':{str(p.relative_to(ROOT)):sha(p) for p in sorted(set(artifacts)) if p.exists()}}
 (OUT/'FINAL_VALIDATION.json').write_text(json.dumps(results,indent=2));print(json.dumps({k:v for k,v in results.items() if k not in ('deliverable_hashes','required_final_sections_exact')},indent=2))
if __name__=='__main__':main()
