import json
from pathlib import Path
import replay as r
rows=json.load(open('research/history/phase12r/POPULATION_MANIFEST.json'))['eligible'];chosen=[];labels={}
for arm,label in [('CONTROL','known_cache_sensitive'),('TREATMENT','known_unaffected')]:
 row=next(x for x in rows if x['run']==f'research/history/phase12/runs/popA/Template_06_05_{arm}');chosen.append(row['id']);labels[label]=row['id']
for i,row in enumerate(sorted(rows,key=lambda x:(x['stratum'],x['run'],x['task']))):
 try:c,_,_=r.xml_cells(r.ROOT/row['V0_source'])
 except Exception:continue
 if 'formula_error' not in labels and any(x['type']=='e' for x in c.values()):labels['formula_error']=row['id'];chosen.append(row['id'])
 if 'no_formula' not in labels and not c:labels['no_formula']=row['id'];chosen.append(row['id'])
 if 'complex_financial_model' not in labels and row['category']=='Financial_Model' and len(c)>1000:labels['complex_financial_model']=row['id'];chosen.append(row['id'])
 if i%100==0:print('inventory-only pilot selection scanned',i,'roles',list(labels),flush=True)
 if len(labels)==5:break
Path('research/history/phase12r/PILOT_MANIFEST.json').write_text(json.dumps({'ids':chosen,'roles':labels,'selection':'known Phase12 06_05 C/T + lexically first retained formula-error/no-formula/complex FM (>1000 formulas); unsupported policy applies unchanged','unavailable_roles':sorted(set(['formula_error','no_formula','complex_financial_model'])-set(labels))},indent=2));print(labels,flush=True)
