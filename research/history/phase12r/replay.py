"""Frozen deterministic replay. No runtime imports, model calls, repairs or verifier."""
from __future__ import annotations
import argparse,copy,fcntl,hashlib,importlib.util,json,math,os,platform,re,shutil,signal,subprocess,sys,time,zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from pathlib import Path
import openpyxl
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'phase12r';BENCH=ROOT/'benchmark-data/SpreadsheetBench-2'
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main';Q='{'+NS+'}'
RNS='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
KEYS=('accuracy','modification_accuracy','regression_accuracy')
LEDGERS=('FORMULA_IDENTITY','CACHE_STATE','PACKAGE_DIFFS','SCORE_REPLAY','BASELINE_CORRECTION_LEDGER')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def official_module():
 p=BENCH/'evaluation/evaluation.py';spec=importlib.util.spec_from_file_location('phase12r_official',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
EVAL=official_module()
def scalar(v):
 if hasattr(v,'isoformat'):return {'type':type(v).__name__,'value':v.isoformat()}
 if isinstance(v,float) and not math.isfinite(v):return {'type':'float','value':str(v)}
 return {'type':type(v).__name__,'value':v}
def formula_text(v):return v.text if hasattr(v,'text') else str(v)
def sheet_parts(z):
 wb=ET.fromstring(z.read('xl/workbook.xml'));rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
 targets={r.attrib['Id']:r.attrib['Target'] for r in rels}
 out={}
 for s in wb.find(Q+'sheets'):
  t=targets[s.attrib[RNS+'id']];p=t.lstrip('/') if t.startswith('/') else 'xl/'+t
  out[s.attrib['name']]=p
 return out

def xml_cells(path):
 with zipfile.ZipFile(path) as z:
  ss=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   for si in ET.fromstring(z.read('xl/sharedStrings.xml')):ss.append(''.join(t.text or '' for t in si.iter(Q+'t')))
  out={};raw={};parts=sheet_parts(z)
  for name,part in parts.items():
   root=ET.fromstring(z.read(part))
   for c in root.iter(Q+'c'):
    f=c.find(Q+'f')
    if f is None:continue
    key=name+'!'+c.attrib['r'];v=c.find(Q+'v');t=c.attrib.get('t','n');val=v.text if v is not None else None
    # Empty string cached as t=str with <v/> is present; empty numeric cache is missing.
    present=v is not None and (val is not None or t=='str')
    if t=='s' and val is not None:val=ss[int(val)];t='str'
    if t=='inlineStr':val=''.join(n.text or '' for n in c.iter(Q+'t'));t='str';present=True
    out[key]={'present':present,'type':t,'value':val if val is not None else ('' if present else None)}
    raw[key]={'text':f.text or '', 'attributes':dict(sorted(f.attrib.items()))}
 return out,raw,parts

def semantic_snapshot(path):
 w=openpyxl.load_workbook(path,data_only=False);formulas={};literals={};sheets=[];font={}
 for s in w:
  sheets.append({'name':s.title,'state':s.sheet_state,'merged':sorted(str(x) for x in s.merged_cells.ranges),'tables':{n:ET.tostring(t.to_tree(),encoding='unicode') for n,t in s.tables.items()} if False else {n:ET.tostring(s.tables[n].to_tree(),encoding='unicode') for n in s.tables}})
  for c in list(s._cells.values()):
   k=s.title+'!'+c.coordinate
   if c.data_type=='f' or hasattr(c.value,'text'):formulas[k]={'text':formula_text(c.value),'array_ref':getattr(c.value,'ref',None)}
   elif c.value is not None:literals[k]=scalar(c.value)
   if c.value is not None:font[k]=EVAL._get_color_rgb(c.font.color)
 calc=w.calculation
 settings={'iterate':bool(getattr(calc,'iterate',False)),'iterateCount':getattr(calc,'iterateCount',None) if getattr(calc,'iterate',False) else None,'iterateDelta':getattr(calc,'iterateDelta',None) if getattr(calc,'iterate',False) else None,'fullPrecision':getattr(calc,'fullPrecision',None) is not False}
 names=sorted(ET.tostring(x.to_tree(),encoding='unicode') for x in w.defined_names.values())
 # sheet-local defined names also affect semantics.
 local={s.title:sorted(ET.tostring(x.to_tree(),encoding='unicode') for x in s.defined_names.values()) for s in w}
 result={'formulas':formulas,'literals':literals,'sheets':sheets,'defined_names':names,'local_defined_names':local,'epoch':str(w.epoch),'calculation':settings,'font_colors':font}
 w.close();return result

def norm_function_case(f):
 # Only function identifiers before '(' outside double/single quoted spans.
 chunks=re.split(r'("(?:[^"]|"")*"|\'(?:[^\']|\'\')*\')',f)
 for i in range(0,len(chunks),2):chunks[i]=re.sub(r'\b([A-Za-z_][A-Za-z0-9_.]*)(?=\s*\()',lambda m:m[1].upper(),chunks[i])
 return ''.join(chunks)
def identity(a,b,ra,rb):
 if a['formulas']==b['formulas'] and ra==rb:return 'FORMULAS_BYTE_IDENTICAL'
 na={k:{**v,'text':norm_function_case(v['text'])} for k,v in a['formulas'].items()};nb={k:{**v,'text':norm_function_case(v['text'])} for k,v in b['formulas'].items()}
 if na==nb:return 'FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED'
 return 'FORMULAS_CHANGED_BY_LIBREOFFICE'
def semantic_diff(a,b,category):
 # Styles may change; interpreted literals and scorer-used font colors must not.
 fields=['literals','sheets','defined_names','local_defined_names','epoch','calculation']
 if category=='Debugging':fields.append('font_colors')
 return {k:{'V0_hash':digest(a[k]),'V1_hash':digest(b[k])} for k in fields if a[k]!=b[k]}
def cache_summary(a,b):
 c=Counter();changed=[]
 for k in sorted(set(a)|set(b)):
  x=a.get(k);y=b.get(k)
  if x is None or y is None:c['formula_membership_changed']+=1;continue
  c['formula_cells']+=1
  if not x['present']:c['CACHE_MISSING']+=1
  if x==y:c['CACHE_UNCHANGED']+=1
  else:
   c['changed_cached_value']+=1;changed.append(k)
   if y['present']:c['CACHE_REFRESHED']+=1
   if x['present']:c['CACHE_STALE_RELATIVE_TO_REPLAY']+=1
 for lab,data in [('V0',a),('V1',b)]:
  for x in data.values():
   c[lab+'_formula_present']+=1
   c[lab+'_cache_present' if x['present'] else lab+'_cache_absent']+=1
   if x['present']:c[lab+'_cache_'+{'e':'error','n':'numeric','str':'string','b':'boolean','d':'date'}.get(x['type'],x['type'])]+=1
 return {'counts':dict(c),'changed_cells':changed,'stale_definition':'changed present cache relative to fixed LO replay, not correctness inference'}
def package_diff(a,b):
 with zipfile.ZipFile(a) as za,zipfile.ZipFile(b) as zb:
  aa={n:hashlib.sha256(za.read(n)).hexdigest() for n in za.namelist()};bb={n:hashlib.sha256(zb.read(n)).hexdigest() for n in zb.namelist()};out=[]
  for n in sorted(set(aa)|set(bb)):
   if aa.get(n)==bb.get(n):continue
   if n.startswith('xl/worksheets/'):kind='worksheet_formulas_values_and_metadata'
   elif 'calcChain' in n:kind='calcChain'
   elif n=='xl/workbook.xml':kind='workbook_and_calculation_metadata'
   elif 'styles' in n:kind='styles'
   elif n=='docProps/core.xml':kind='core_properties'
   elif '.rels' in n:kind='relationships'
   elif n.startswith('docProps/'):kind='other_properties'
   else:kind='other_package_part'
   out.append(dict(part=n,type=kind,V0_hash=aa.get(n),V1_hash=bb.get(n),change='added' if n not in aa else 'removed' if n not in bb else 'changed'))
  return out

def unsupported(path,raw,snap):
 with zipfile.ZipFile(path) as z:
  names=z.namelist();reasons=[]
  if any('vbaProject' in n for n in names):reasons.append('MACROS')
  if any(n.startswith('xl/externalLinks/') or n=='xl/connections.xml' for n in names):reasons.append('EXTERNAL_LINKS_OR_CONNECTIONS')
  for v in snap['formulas'].values():
   f=re.sub(r'"(?:[^"]|"")*"','',v['text'])
   if re.search(r'(?i)(?:^|[^A-Z0-9_])(?:_xlfn\.)?(NOW|TODAY|RAND|RANDBETWEEN|OFFSET|INDIRECT|CELL|INFO)\s*\(',f):reasons.append('VOLATILE_FUNCTION');break
  if any(re.search(r'(?i)(_xll\.|_xludf\.|com\.microsoft\.|WEBSERVICE\s*\(|RTD\s*\()',v['text']) for v in snap['formulas'].values()):reasons.append('UDF_OR_EXTERNAL_FUNCTION')
  return sorted(set(reasons))

def score(row,path,stage):
 t=time.monotonic();cat,tid=row['task'].split(':');stage.mkdir(parents=True,exist_ok=True);dst=stage/f'{tid}_output.xlsx';shutil.copyfile(path,dst)
 d=next(x for x in load(BENCH/'data'/cat/'dataset.json') if str(x['id'])==tid)
 result,_=EVAL.process_single_item(d,str(BENCH/'data'/cat),str(stage),{},cat)
 color=cat=='Debugging' and 'Color' in d['spreadsheet_path'];formula=cat=='Debugging' and 'Embedded' in d['spreadsheet_path']
 detail=EVAL.compare_workbooks_with_regression(str(ROOT/row['input']),str(ROOT/row['gold']),str(dst),d['answer_position'],color,formula)
 status='SCORE_PASS' if detail[3]>0 else 'SCORE_UNSCORABLE'
 return {'official':result,'status':status,'assessed_cells':detail[3],'correct_cells':detail[2],'regression_counts':detail[4],'modification_counts':detail[5],'mode':{'with_font_color':color,'with_formula':formula},'elapsed_seconds':time.monotonic()-t,'candidate_hash':sha(path)}

def observed_surface(row,path,mode):
 # Complete typed/formula/color equality at the scorer's answer positions.
 cat,tid=row['task'].split(':');d=next(x for x in load(BENCH/'data'/cat/'dataset.json') if str(x['id'])==tid)
 wf=openpyxl.load_workbook(path,data_only=False);wv=openpyxl.load_workbook(path,data_only=not mode['with_formula']);wg=openpyxl.load_workbook(ROOT/row['gold'],data_only=False);out=[]
 for rng in EVAL.parse_answer_position(d['answer_position']):
  name,cells=rng.split('!') if '!' in rng else (wg.sheetnames[0],rng);name=name.strip("'").strip();cells=cells.strip("'").strip();sv=EVAL._find_sheet(wv,name);sf=EVAL._find_sheet(wf,name)
  for coord in EVAL.generate_cell_names(cells):
   if sv is None:out.append([name,coord,'MISSING_SHEET']);continue
   c=sv[coord];f=sf[coord];v=formula_text(c.value) if c.data_type=='f' or hasattr(c.value,'text') else c.value
   out.append([name,coord,scalar(v),formula_text(f.value) if f.data_type=='f' or hasattr(f.value,'text') else None,EVAL._get_color_rgb(c.font.color) if mode['with_font_color'] else None])
 for w in (wf,wv,wg):w.close()
 return digest(out)

def error_fallback_census(row,v0,v1,mode):
 cat,tid=row['task'].split(':');d=next(x for x in load(BENCH/'data'/cat/'dataset.json') if str(x['id'])==tid)
 books=[openpyxl.load_workbook(p,data_only=True) for p in (ROOT/row['gold'],v0,v1)];counts=Counter()
 for rng in EVAL.parse_answer_position(d['answer_position']):
  name,cells=rng.split('!') if '!' in rng else (books[0].sheetnames[0],rng);name=name.strip("'").strip();cells=cells.strip("'").strip();sheets=[EVAL._find_sheet(w,name) for w in books]
  if any(s is None for s in sheets):continue
  for coord in EVAL.generate_cell_names(cells):
   g,a,b=[s[coord] for s in sheets];ea=EVAL._has_excel_error(a);eb=EVAL._has_excel_error(b);eg=EVAL._has_excel_error(g)
   if eg:counts['golden_error_trigger']+=1
   if not mode['with_formula']:
    fa=eg or ea;fb=eg or eb;counts['V0_fallback_cells']+=int(fa);counts['V1_fallback_cells']+=int(fb)
    if not fa and fb:counts['entered_formula_fallback']+=1
    if fa and not fb:counts['left_formula_fallback']+=1
   if ea!=eb:counts['candidate_error_state_changed']+=1
 for w in books:w.close()
 return dict(counts)

def transplant(v0,v1,dst):
 cache,_,_=xml_cells(v1)
 with zipfile.ZipFile(v0) as z,zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as zo:
  parts={v:k for k,v in sheet_parts(z).items()}
  for n in z.namelist():
   data=z.read(n)
   if n in parts:
    root=ET.fromstring(data)
    for c in root.iter(Q+'c'):
     if c.find(Q+'f') is None:continue
     k=parts[n]+'!'+c.attrib['r'];new=cache.get(k)
     if new is None:continue
     for child in list(c):
      if child.tag in (Q+'v',Q+'is'):c.remove(child)
     c.attrib.pop('t',None)
     if new['present']:
      if new['type']!='n':c.set('t',new['type'])
      v=ET.SubElement(c,Q+'v');v.text=new['value']
    data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
   zo.writestr(n,data)
 return sha(dst)

def recalc(v0,dst,profile):
 t=time.monotonic();cmd=['/usr/bin/python3',str(OUT/'uno_recalc.py'),str(v0.resolve()),str(dst.resolve()),str(profile.resolve())]
 env={**os.environ,'LC_ALL':'C.UTF-8','LANG':'C.UTF-8','TZ':'UTC'}
 p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,start_new_session=True)
 try:
  stdout,stderr=p.communicate(timeout=180)
  if p.returncode or not dst.exists():return {'status':'RECALC_FAILED','error':(stdout+stderr)[-4000:],'elapsed_seconds':time.monotonic()-t,'command':cmd}
  return {**json.loads(stdout.strip().splitlines()[-1]),'elapsed_seconds':time.monotonic()-t,'helper_command':cmd,'stderr':stderr[-1000:]}
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGTERM);p.communicate();return {'status':'RECALC_FAILED','error':'TIMEOUT_180_SECONDS','elapsed_seconds':time.monotonic()-t,'command':cmd}

def replay(row,root):
 start=time.monotonic();rid=row['id'];work=root/rid;work.mkdir(parents=True,exist_ok=True)
 source=ROOT/row['V0_source'];assert sha(source)==row['V0_hash'],'original workbook mutated'
 assert sha(ROOT/row['input'])==row['input_hash'] and sha(ROOT/row['gold'])==row['gold_hash'],'input/golden drift'
 v0=work/'V0_ORIGINAL.xlsx';v1=work/'V1_RECALCULATED.xlsx';shutil.copyfile(source,v0)
 result={**row,'V0_artifact':str(v0.relative_to(ROOT)),'evaluator_hash':sha(BENCH/'evaluation/evaluation.py'),'formula_identity':'UNDETERMINED','classification':'UNSCORABLE','interpretation_impact':'UNKNOWN'}
 try:
  s0=semantic_snapshot(v0);c0,r0,_=xml_cells(v0);result['current_V0_score']=score(row,v0,work/'score/V0');result['original_score_reproduced']=all(result['current_V0_score']['official'][k]==row['original_score'][k] for k in KEYS)
  result['V0_cache_counts']=cache_summary(c0,c0)['counts'];result['formula_counts']={'V0':len(s0['formulas']),'V1':None};reasons=unsupported(v0,r0,s0)
  if reasons:
   result['recalc']={'status':'RECALC_UNSUPPORTED','reasons':reasons,'elapsed_seconds':0};return result
  # Reuse byte-identical execution results without turning repeated runs into independent evidence.
  shared=OUT/'recalc_by_hash'/sha(OUT/'uno_recalc.py')[:16]/row['V0_hash'];shared.mkdir(parents=True,exist_ok=True);cached=shared/'V1.xlsx';meta=shared/'recalc.json'
  with (shared/'execution.lock').open('w') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   if meta.exists():rc=load(meta);result['recalc_reused_identical_bytes']=True
   else:
    rc=recalc(v0,cached,shared/'profile');meta.write_text(json.dumps(rc,indent=2));result['recalc_reused_identical_bytes']=False
    shutil.rmtree(shared/'profile',ignore_errors=True)
  result['recalc']=rc
  if rc['status']!='RECALC_PASS':return result
  shutil.copyfile(cached,v1);result['V1_hash']=sha(v1);result['V1_artifact']=str(v1.relative_to(ROOT))
  s1=semantic_snapshot(v1);c1,r1,_=xml_cells(v1);fid=identity(s0,s1,r0,r1);result['formula_identity']=fid
  result['formula_counts']={'V0':len(s0['formulas']),'V1':len(s1['formulas'])};result['formula_text_changed_cells']=[k for k in sorted(set(s0['formulas'])|set(s1['formulas'])) if s0['formulas'].get(k)!=s1['formulas'].get(k)]
  result['semantic_differences']=semantic_diff(s0,s1,row['category']);result['semantic_fingerprints']={'V0':digest(s0),'V1':digest(s1)}
  result['cache_summary']=cache_summary(c0,c1);result['package_diffs']=package_diff(v0,v1)
  result['V1_score']=score(row,v1,work/'score/V1');v0s=result['current_V0_score'];v1s=result['V1_score'];result['delta']={k:v1s['official'][k]-v0s['official'][k] for k in KEYS}
  if v0s['status']!='SCORE_PASS' or v1s['status']!='SCORE_PASS':return result
  delta=result['delta'];harm=delta['accuracy']<0 or any(delta[k]<=-.01+1e-12 for k in KEYS[1:]);gain=delta['accuracy']>0 or any(delta[k]>=.01-1e-12 for k in KEYS[1:]);result['mixed_gain_and_harm']=gain and harm;result['mixed_signed_changes']=any(v>0 for v in delta.values()) and any(v<0 for v in delta.values())
  if harm:result['classification']='RECALC_REGRESSION'
  elif not gain:result['classification']='RECALC_NO_MATERIAL_EFFECT';result['interpretation_impact']='UNAFFECTED'
  else:
   result['classification']='RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN'
   if fid in ('FORMULAS_BYTE_IDENTICAL','FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED') and not result['semantic_differences'] and not s0['calculation']['iterate'] and result['cache_summary']['changed_cells']:
    witness=work/'CACHE_SUFFICIENCY_WITNESS.xlsx';wh=transplant(v0,v1,witness);ws=score(row,witness,work/'score/WITNESS')
    sf1=observed_surface(row,v1,v1s['mode']);sfw=observed_surface(row,witness,ws['mode']);sw=semantic_snapshot(witness);cw,rw,_=xml_cells(witness)
    equal=all(ws['official'][k]==v1s['official'][k] for k in KEYS) and sf1==sfw and sw['formulas']==s0['formulas'] and rw==r0 and not semantic_diff(s0,sw,row['category'])
    result['scorer_error_fallback_census']=error_fallback_census(row,v0,v1,v1s['mode'])
    result['cache_sufficiency_witness']={'hash':wh,'score':ws,'V1_assessed_surface_hash':sf1,'witness_assessed_surface_hash':sfw,'cache_only_proof_pass':equal,'artifact':str(witness.relative_to(ROOT))}
    if equal:result['classification']='CACHE_ONLY_SCORE_RECOVERY';result['interpretation_impact']='BOUNDARY MOVED' if result['original_score_reproduced'] and row['historical_byte_linkage']=='ARCHIVED_SUBMISSION' else 'UNKNOWN'
  result['historical_cache_recovery_proven']=result['classification']=='CACHE_ONLY_SCORE_RECOVERY' and result['original_score_reproduced'] and row['historical_byte_linkage']=='ARCHIVED_SUBMISSION'
  if result['historical_cache_recovery_proven']:result['prior_failure_interpretation']='PRIOR_FAILURE_INTERPRETATION_CACHE_SENSITIVE' if row['historical_report_references'] else 'NO_LINKED_FAILURE_ANALYSIS'
  return result
 except Exception as e:result['replay_error']=type(e).__name__+': '+str(e);return result
 finally:
  result['total_elapsed_seconds']=time.monotonic()-start
  assert sha(source)==row['V0_hash'],'original mutated during replay'
  (work/'result.json').write_text(json.dumps(result,indent=2,default=str))

def append_ledgers(r,destination):
 base={'id':r['id'],'task':r['task'],'run':r['run'],'stratum':r['stratum'],'category':r['category']}
 entries={
 'FORMULA_IDENTITY':{**base,**{k:r.get(k) for k in ('V0_hash','V1_hash','formula_identity','formula_counts','formula_text_changed_cells','semantic_differences','semantic_fingerprints')}},
 'CACHE_STATE':{**base,'V0_counts':r.get('V0_cache_counts'),'transition':r.get('cache_summary'),'scorer_error_fallback':r.get('scorer_error_fallback_census'),'recalc_status':r.get('recalc')},
 'PACKAGE_DIFFS':{**base,'parts':r.get('package_diffs',[])},
 'SCORE_REPLAY':{**base,**{k:r.get(k) for k in ('original_score','current_V0_score','V1_score','delta','original_score_reproduced','replay_error','cache_sufficiency_witness')}},
 'BASELINE_CORRECTION_LEDGER':r}
 for name,entry in entries.items():
  with (destination/(name+'.jsonl')).open('a') as f:f.write(json.dumps(entry,default=str)+'\n')

def work_item(item):return replay(*item)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true');ap.add_argument('--limit',type=int);args=ap.parse_args()
 manifest=load(OUT/'POPULATION_MANIFEST.json');rows=manifest['eligible']
 if args.pilot:rows=[next(r for r in rows if r['id']==rid) for rid in load(OUT/'PILOT_MANIFEST.json')['ids']];dest=OUT/'pilot';artifact=dest/'artifacts'
 else:
  expected=(OUT/'PREREGISTERED_REPLAY_SPEC.sha256').read_text().split()[0];assert sha(OUT/'PREREGISTERED_REPLAY_SPEC.md')==expected
  freeze=load(OUT/'FREEZE.json');assert sha(OUT/'POPULATION_MANIFEST.json')==freeze['population_hash'];assert sha(Path(__file__))==freeze['replay_hash'];dest=OUT;artifact=OUT/'artifacts'
 dest.mkdir(parents=True,exist_ok=True);existing=set()
 if (dest/'BASELINE_CORRECTION_LEDGER.jsonl').exists():existing={loadrow['id'] for loadrow in (json.loads(l) for l in (dest/'BASELINE_CORRECTION_LEDGER.jsonl').read_text().splitlines())}
 rows=sorted(rows,key=lambda r:(r['stratum'],r['run'],r['task']))
 if args.limit:rows=rows[:args.limit]
 rows=[r for r in rows if r['id'] not in existing]
 with ProcessPoolExecutor(max_workers=1 if args.pilot else 4) as executor:
  for i,r in enumerate(executor.map(work_item,[(row,artifact) for row in rows]),1):
   append_ledgers(r,dest)
   print(json.dumps({'progress':f'{i}/{len(rows)}','stratum':r['stratum'],'task':r['task'],'classification':r['classification'],'recalc':r.get('recalc',{}).get('status'),'exact_delta':r.get('delta',{}).get('accuracy'),'error':r.get('replay_error')}),flush=True)
if __name__=='__main__':main()
