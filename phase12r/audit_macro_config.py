"""Deterministic package audit of discovered frozen UNO macro-mode deviation."""
import hashlib,json,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'phase12r'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((OUT/'POPULATION_MANIFEST.json').read_text());rows=manifest['eligible'];records=[]
for row in rows:
 p=ROOT/row['V0_source'];found=[]
 try:
  with zipfile.ZipFile(p) as z:
   for n in z.namelist():
    if any(t in n.lower() for t in ['vbaproject','vbadata','macrosheet','dialogsheet','script','basic/']):found.append({'part':n,'kind':'PART_NAME'})
    if n=='[Content_Types].xml' or n.endswith('.rels'):
     root=E.fromstring(z.read(n))
     for node in root:
      for attr in ['ContentType','Type','Target']:
       val=node.get(attr,'')
       if not (attr=='Target' and node.get('TargetMode')=='External') and any(t in val.lower() for t in ['vbaproject','vbadata','macrosheet','dialogsheet','/script','macroenabled','customui']):found.append({'part':n,'attribute':attr,'value':val,'kind':'PACKAGE_DECLARATION'})
 except Exception as e:found.append({'kind':'UNINSPECTABLE','error':str(e)})
 records.append({'id':row['id'],'task':row['task'],'source_hash':sha(p),'macro_indicators':found})
output={'scope':'all frozen eligible sources; package names/content-types/relationship declarations only; not a complete proof against arbitrary hidden executable content','population_hash':sha(OUT/'POPULATION_MANIFEST.json'),'frozen_helper_hash':sha(OUT/'uno_recalc.py'),'actual_macro_mode':4,'actual_macro_mode_name':'ALWAYS_EXECUTE_NO_WARN','specified_disabled_mode':0,'specified_disabled_mode_name':'NEVER_EXECUTE','update_doc_mode':0,'rows':records,'indicator_rows':sum(bool(r['macro_indicators']) for r in records)}
(OUT/'MACRO_CONFIG_PACKAGE_AUDIT.json').write_text(json.dumps(output,indent=2));print('audited',len(records),'indicator rows',output['indicator_rows'])
