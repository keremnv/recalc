"""Exact parsed-reference cloning for unchanged official scorer execution.
Only benchmark input/golden reads are cached, never candidate reads.
"""
import gc,gzip,hashlib,json,os,pickle,platform,sys,time
from pathlib import Path
import openpyxl
import workbook_pickle_compat
OUT=Path(__file__).resolve().parent

def loader(original,allowed,events,cache_root=None,content_identity=False):
 def load(*args,**kwargs):
  filename=kwargs.get('filename',args[0] if args else None)
  if filename is None:return original(*args,**kwargs)
  path=Path(filename).resolve()
  if path not in allowed:return original(*args,**kwargs)
  identity={'path':'EXACT_CONTENT_IDENTITY' if content_identity else str(path),'hash':allowed[path],'args':str(args[1:]),'kwargs':{k:v for k,v in kwargs.items() if k!='filename'},'Python':sys.version,'openpyxl':openpyxl.__version__,'serialization_hash':hashlib.sha256(Path(workbook_pickle_compat.__file__).read_bytes()).hexdigest()}
  key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();root=Path(cache_root) if cache_root is not None else OUT/'reference_parse_cache';root.mkdir(parents=True,exist_ok=True);data=root/(key+'.pickle.gz');meta=root/(key+'.json');start=time.monotonic()
  if data.exists() and meta.exists():
   stored=json.loads(meta.read_text());assert stored['identity']==identity
   try:
    with gzip.open(data,'rb') as f:wb=pickle.load(f)
    events.append({'identity':key,'reused':True,'elapsed_seconds':time.monotonic()-start});return wb
   except (EOFError,pickle.UnpicklingError,OSError):data.unlink(missing_ok=True);meta.unlink(missing_ok=True);gc.collect()
  wb=original(*args,**kwargs);tmp=data.with_name(data.name+'.'+str(os.getpid())+'.part')
  try:
   with gzip.open(tmp,'wb',compresslevel=1) as f:pickle.dump(wb,f,protocol=5)
   os.replace(tmp,data);mtemp=meta.with_name(meta.name+'.'+str(os.getpid())+'.part');mtemp.write_text(json.dumps({'identity':identity,'parsed_reference_only':True},indent=2));os.replace(mtemp,meta)
   events.append({'identity':key,'reused':False,'elapsed_seconds':time.monotonic()-start})
  except (pickle.PicklingError,TypeError,AttributeError,OSError) as e:
   tmp.unlink(missing_ok=True);events.append({'identity':key,'reused':False,'cache_error':type(e).__name__,'elapsed_seconds':time.monotonic()-start})
  return wb
 return load

def candidate_loader(original,workspace,events):
 workspace=Path(workspace).resolve()
 def load(*args,**kwargs):
  filename=kwargs.get('filename',args[0] if args else None)
  if filename is None:return original(*args,**kwargs)
  path=Path(filename).resolve()
  if not path.is_relative_to(workspace) or kwargs.get('read_only',False):return original(*args,**kwargs)
  checksum=hashlib.sha256(path.read_bytes()).hexdigest()
  return loader(original,{path:checksum},events,workspace/'.parsed_objects',True)(*args,**kwargs)
 return load
