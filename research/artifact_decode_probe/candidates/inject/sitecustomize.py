"""R5 candidate injector (research only): patch artifact._book in-process.

Activated by R5_DECODER=d1|d1b. Prepend this directory to PYTHONPATH so
the child interpreter applies the candidate decoder to all product imports.
"""
import os as _os

_cand = _os.environ.get("R5_DECODER")
if _cand in ("d1", "d1b"):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).parent.parent))
    if _cand == "d1":
        import d1 as _m
    else:
        import d1b as _m
    _m.patch()
