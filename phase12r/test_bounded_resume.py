"""Parity check for execution-only official-return observation and GC."""
import json,tempfile,unittest,zipfile,shutil
from pathlib import Path
import bounded_resume as b
import replay as r
class ExecutionParity(unittest.TestCase):
 def test_official_capture_equals_frozen_scoring(self):
  m=r.load(r.OUT/'POPULATION_MANIFEST.json');row=next(x for x in m['eligible'] if x['run']=='phase12/runs/popA/Template_06_05_CONTROL');p=r.ROOT/row['V0_source']
  with tempfile.TemporaryDirectory() as temp:
   candidate=Path(temp)/'candidate.xlsx';shutil.copyfile(p,candidate)
   with zipfile.ZipFile(candidate,'a') as z:z.writestr('phase12r_test_only.txt',temp)
   old=r.score(row,candidate,Path(temp)/'frozen');new=b.bounded_score(row,candidate,Path(temp)/'bounded')
   self.assertFalse(new['scoring_reused_identical_identity'])
  for key in ['official','status','assessed_cells','correct_cells','regression_counts','modification_counts','mode','candidate_hash']:self.assertEqual(old[key],new[key],key)
 def test_core_metadata_equivalence_preserves_official_scores(self):
  m=r.load(r.OUT/'POPULATION_MANIFEST.json');row=next(x for x in m['eligible'] if x['run']=='phase12/runs/popA/Template_06_05_CONTROL');p=r.ROOT/row['V0_source']
  with tempfile.TemporaryDirectory() as temp:
   a=Path(temp)/'a.xlsx';c=Path(temp)/'c.xlsx';shutil.copyfile(p,a)
   with zipfile.ZipFile(a,'a') as z:z.writestr('unique_test_payload.txt',temp)
   with zipfile.ZipFile(a) as za,zipfile.ZipFile(c,'w') as zc:
    for n in za.namelist():
     data=za.read(n)
     if n=='docProps/core.xml':
      root=r.ET.fromstring(data);modified=root.find('{http://purl.org/dc/terms/}modified')
      if modified is not None:modified.text='2001-01-01T00:00:00Z'
      data=r.ET.tostring(root)
     zc.writestr(n,data)
   r.semantic_snapshot(a);r.semantic_snapshot(c)
   self.assertNotEqual(r.sha(a),r.sha(c));self.assertEqual(b.scored_package_identity(a),b.scored_package_identity(c))
   first=b.bounded_score(row,a,Path(temp)/'first');second=b.bounded_score(row,c,Path(temp)/'second');official=r.score(row,c,Path(temp)/'official')
   self.assertTrue(second['scoring_reused_identical_identity']);self.assertEqual(second['candidate_hash'],r.sha(c))
   for key in ['official','status','assessed_cells','correct_cells','regression_counts','modification_counts','mode']:self.assertEqual(second[key],official[key],key)
 def test_financial_reference_clones_equal_fresh_official_reads(self):
  m=r.load(r.OUT/'POPULATION_MANIFEST.json');pilot=r.load(r.OUT/'PILOT_MANIFEST.json');row=next(x for x in m['eligible'] if x['id']==pilot['roles']['supported_complex_financial_model']);source=r.ROOT/row['V0_source']
  with tempfile.TemporaryDirectory() as temp:
   candidate=Path(temp)/'candidate.xlsx';shutil.copyfile(source,candidate)
   with zipfile.ZipFile(candidate,'a') as z:z.writestr('reference_clone_test_payload.txt',temp)
   official=r.score(row,candidate,Path(temp)/'official');first=b.bounded_score(row,candidate,Path(temp)/'bounded')
   for key in ['official','status','assessed_cells','correct_cells','regression_counts','modification_counts','mode','candidate_hash']:self.assertEqual(first[key],official[key],key)
   # Different candidate identity forces a second actual scorer call with cloned refs.
   with zipfile.ZipFile(candidate,'a') as z:z.writestr('reference_clone_second_test_payload.txt',temp)
   second=b.bounded_score(row,candidate,Path(temp)/'second')
   self.assertTrue(any(e.get('reused') for e in second['reference_parse_cache_events']+second.get('scored_object_cache_events',[])))
   for key in ['official','status','assessed_cells','correct_cells','regression_counts','modification_counts','mode']:self.assertEqual(second[key],official[key],key)
 def test_candidate_clones_preserve_semantic_snapshot_and_official_score(self):
  from reference_parse_cache import candidate_loader
  m=r.load(r.OUT/'POPULATION_MANIFEST.json');pilot=r.load(r.OUT/'PILOT_MANIFEST.json');row=next(x for x in m['eligible'] if x['id']==pilot['roles']['supported_complex_financial_model']);source=r.ROOT/row['V0_source']
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);candidate=root/'candidate.xlsx';shutil.copyfile(source,candidate)
   native=r.semantic_snapshot(candidate);official=r.score(row,candidate,root/'native_score');events=[];original=r.openpyxl.load_workbook;r.openpyxl.load_workbook=candidate_loader(original,root,events)
   try:
    first=r.semantic_snapshot(candidate);second=r.semantic_snapshot(candidate);cloned=r.score(row,candidate,root/'cloned_score')
   finally:r.openpyxl.load_workbook=original
   self.assertEqual(native,first);self.assertEqual(first,second);self.assertTrue(any(x['reused'] for x in events))
   for key in ['official','status','assessed_cells','correct_cells','regression_counts','modification_counts','mode','candidate_hash']:self.assertEqual(cloned[key],official[key],key)
if __name__=='__main__':unittest.main()
