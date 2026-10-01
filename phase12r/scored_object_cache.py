"""Exact scored-cell parsed objects for the fixed unchanged official comparator.

Only its loader is wrapped. All workbook bytes/full phase inspections remain intact.
The fixed comparator reads named cells in answer_position, never evaluates formulas.
"""
import gc,gzip,hashlib,json,os,pickle,sys,time
from pathlib import Path
import openpyxl
import workbook_pickle_compat
import replay as r

def prune(wb,answer_position,default_sheet):
 keep={s.title:set() for s in wb}
 for position in r.EVAL.parse_answer_position(answer_position):
  name,cells=position.split('!') if '!' in position else (default_sheet,position);name=name.strip("'").strip();cells=cells.strip("'").strip();ws=r.EVAL._find_sheet(wb,name)
  if ws is None:continue
  keep[ws.title].update(openpyxl.utils.cell.coordinate_to_tuple(c) for c in r.EVAL.generate_cell_names(cells))
 removed=0
 for ws in wb:
  allowed=keep[ws.title];old=ws._cells;retained={coord:cell for coord,cell in old.items() if coord in allowed}
  # Every existing accessed cell retains precisely its original parsed object.
  assert all(retained[c] is old[c] for c in allowed if c in old)
  removed+=len(old)-len(retained);ws._cells=retained
 return removed

def loader(original,row,answer_position,events):
 with r.zipfile.ZipFile(r.ROOT/row['gold']) as z:default_sheet=next(iter(r.sheet_parts(z)))
 known={(r.ROOT/row['input']).resolve():row['input_hash'],(r.ROOT/row['gold']).resolve():row['gold_hash']}
 def load(*args,**kwargs):
  filename=kwargs.get('filename',args[0] if args else None)
  if filename is None or kwargs.get('read_only',False):return original(*args,**kwargs)
  path=Path(filename).resolve();source_hash=known.get(path) or r.sha(path)
  identity={'source_hash':source_hash,'source_path':str(path) if path in known else 'EXACT_CANDIDATE_CONTENT','answer_position':answer_position,'default_sheet':default_sheet,'args':str(args[1:]),'kwargs':{k:v for k,v in kwargs.items() if k!='filename'},'Python':sys.version,'openpyxl':openpyxl.__version__,'serialization_hash':hashlib.sha256(Path(workbook_pickle_compat.__file__).read_bytes()).hexdigest(),'evaluator_hash':r.sha(r.BENCH/'evaluation/evaluation.py'),'implementation_hash':r.sha(Path(__file__))}
  key=r.digest(identity);root=r.OUT/'reference_score_objects' if path in known else path.parent/'.scored_objects';root.mkdir(parents=True,exist_ok=True);data=root/(key+'.pickle.gz');meta=root/(key+'.json');start=time.monotonic()
  if data.exists() and meta.exists():
   assert r.load(meta)['identity']==identity
   try:
    with gzip.open(data,'rb') as f:wb=pickle.load(f)
    events.append({'identity':key,'reused':True,'elapsed_seconds':time.monotonic()-start,'basis':'same complete bytes/loading mode; every existing answer-position cell and workbook metadata retained'});return wb
   except (EOFError,pickle.UnpicklingError,OSError):data.unlink(missing_ok=True);meta.unlink(missing_ok=True);gc.collect()
  wb=original(*args,**kwargs);removed=prune(wb,answer_position,default_sheet);gc.collect();tmp=data.with_name(data.name+'.'+str(os.getpid())+'.part')
  try:
   with gzip.open(tmp,'wb',compresslevel=1) as f:pickle.dump(wb,f,protocol=5)
   os.replace(tmp,data);mt=meta.with_name(meta.name+'.'+str(os.getpid())+'.part');mt.write_text(json.dumps({'identity':identity,'only_unobserved_in_memory_cells_omitted':True}));os.replace(mt,meta)
  except (pickle.PicklingError,TypeError,AttributeError,OSError) as e:tmp.unlink(missing_ok=True);events.append({'cache_error':type(e).__name__})
  events.append({'identity':key,'reused':False,'unobserved_parsed_cells_released':removed,'elapsed_seconds':time.monotonic()-start});return wb
 return load
