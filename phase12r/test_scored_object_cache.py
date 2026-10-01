"""Official return parity, including color/formula/error modes and missing sheets."""
import tempfile,unittest,zipfile,shutil
from pathlib import Path
import replay as r
import scored_object_cache as c
class ScopedParity(unittest.TestCase):
 def parity(self,row):
  with tempfile.TemporaryDirectory() as temp:
   candidate=Path(temp)/'candidate.xlsx';shutil.copyfile(r.ROOT/row['V0_source'],candidate)
   with zipfile.ZipFile(candidate,'a') as z:z.writestr('scoped_parity_nonce.txt',temp)
   native=r.score(row,candidate,Path(temp)/'native');self.assertEqual(native['status'],'SCORE_PASS');self.assertGreater(native['assessed_cells'],0);cat,tid=row['task'].split(':');d=next(x for x in r.load(r.BENCH/'data'/cat/'dataset.json') if str(x['id'])==tid);events=[];original=r.EVAL.openpyxl.load_workbook;r.EVAL.openpyxl.load_workbook=c.loader(original,row,d['answer_position'],events)
   try:scoped=r.score(row,candidate,Path(temp)/'scoped');again=r.score(row,candidate,Path(temp)/'again')
   finally:r.EVAL.openpyxl.load_workbook=original
   for key in ['official','status','assessed_cells','correct_cells','regression_counts','modification_counts','mode','candidate_hash']:self.assertEqual(native[key],scoped[key],key);self.assertEqual(native[key],again[key],key)
   self.assertTrue(any(x.get('reused') for x in events))
 def test_template_official_parity(self):
  m=r.load(r.OUT/'POPULATION_MANIFEST.json');self.parity(next(x for x in m['eligible'] if x['run']=='phase12/runs/popA/Template_06_05_CONTROL'))
 def test_financial_official_parity(self):
  m=r.load(r.OUT/'POPULATION_MANIFEST.json');pilot=r.load(r.OUT/'PILOT_MANIFEST.json');self.parity(next(x for x in m['eligible'] if x['id']==pilot['roles']['supported_complex_financial_model']))
 def test_color_official_parity(self):
  m=r.load(r.OUT/'POPULATION_MANIFEST.json');self.parity(next(x for x in m['eligible'] if x['stratum']=='P1' and x['category']=='Debugging' and 'Color' in x['input']))
 def test_embedded_formula_official_parity(self):
  m=r.load(r.OUT/'POPULATION_MANIFEST.json');self.parity(next(x for x in m['eligible'] if x['stratum']=='P1' and x['category']=='Debugging' and 'Embedded' in x['input']))
 def test_missing_named_sheet_and_target_object_identity(self):
  w=r.openpyxl.Workbook();s=w.active;s.title='Sheet';s['A1']='=1/0';s['Z99']=42;target=s['A1'];names=w.sheetnames[:];c.prune(w,"'Sheet'!A1,'Missing'!B2",'Sheet');self.assertIs(target,s['A1']);self.assertNotIn((99,26),s._cells);self.assertEqual(names,w.sheetnames)
if __name__=='__main__':unittest.main()
