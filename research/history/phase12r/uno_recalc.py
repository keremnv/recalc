"""One workbook, one isolated LibreOffice process. System Python for UNO."""
import json,os,subprocess,sys,time
from pathlib import Path
import uno
from com.sun.star.beans import PropertyValue

def prop(n,v):
 p=PropertyValue();p.Name=n;p.Value=v;return p
src,dst,profile=map(Path,sys.argv[1:4]);pipe='p12r_'+profile.parent.name[:24].replace('-','_')
cmd=['libreoffice','-env:UserInstallation='+profile.as_uri(),'--headless','--nologo','--nodefault','--nofirststartwizard','--norestore',f'--accept=pipe,name={pipe};urp;StarOffice.ComponentContext']
p=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
doc=None
try:
 local=uno.getComponentContext();resolver=local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',local)
 for _ in range(200):
  try:ctx=resolver.resolve(f'uno:pipe,name={pipe};urp;StarOffice.ComponentContext');break
  except Exception:
   if p.poll() is not None:raise RuntimeError('LibreOffice exited before UNO connection')
   time.sleep(.05)
 else:raise TimeoutError('UNO connection timeout')
 desktop=ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',ctx)
 doc=desktop.loadComponentFromURL(src.as_uri(),'_blank',0,(prop('Hidden',True),prop('ReadOnly',False),prop('MacroExecutionMode',4),prop('UpdateDocMode',0)))
 if doc is None:raise RuntimeError('load returned no document (encrypted or malformed)')
 doc.enableAutomaticCalculation(True);doc.calculateAll()
 doc.storeAsURL(dst.as_uri(),(prop('FilterName','Calc MS Excel 2007 XML'),prop('Overwrite',False)))
 doc.close(True);doc=None;desktop.terminate()
 print(json.dumps({'status':'RECALC_PASS','command':cmd,'force_calculation':'enableAutomaticCalculation(True); calculateAll()','macro_execution_mode':4,'update_doc_mode':0}))
finally:
 if doc:
  try:doc.close(True)
  except Exception:pass
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
