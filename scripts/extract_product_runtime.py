"""Reproduce packaging-only extraction from the frozen research sources.

No experimental functions, benchmark imports, or automatic runs are copied.
The extraction manifest enables AST parity checks before sealing a new RC.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'src/librecalc_agent/_frozen'
rows = []


def extract(source, target, names, imports, *, loops=False):
    path = ROOT / source
    text = path.read_text()
    tree = ast.parse(text)
    nodes = []
    selected = []
    for node in tree.body:
        name = getattr(node, 'name', None)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            name = next((t.id for t in targets if isinstance(t, ast.Name)), None)
        if name in names or (loops and isinstance(node, ast.For)):
            nodes.append(ast.get_source_segment(text, node))
            selected.append(name or '<proxy_guard_registration>')
    (DEST / target).write_text('"""Frozen implementation; packaging extraction only. See extraction_manifest.json."""\nfrom __future__ import annotations\n' + imports + '\n\n' + '\n\n\n'.join(nodes) + '\n')
    rows.append({'source': source, 'target': 'src/librecalc_agent/_frozen/' + target,
                 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'definitions': selected,
                 'transformation': 'Selected definitions unchanged; imports redirected within package; no benchmark main.'})


def copy(source, target, replacements=(), remove_main=False):
    path = ROOT / source
    text = path.read_text()
    for a,b in replacements:
        text = text.replace(a,b)
    if remove_main:
        assert text.endswith('main()\n')
        text = text[:-len('main()\n')]
    (DEST / target).write_text(text)
    rows.append({'source':source,'target':'src/librecalc_agent/_frozen/'+target,
                 'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                 'transformation':'Import relocation only' + ('; removed import-time main() (explicit bootstrap calls main)' if remove_main else ''),
                 'replacements':list(replacements),'remove_main':remove_main})


extract('benchmark/run_candidate_a1_classifier_repair.py','eligibility.py',
        {'dotted','const_string','is_true','is_false','base_name','A1Analyzer','classify'},
        'import ast\nimport re\nfrom typing import Any')
extract('benchmark/candidate_a_shadow_interposition.py','reads.py',
        {'MAIN_NS','REL_NS','PKG_REL_NS','observable','WorkbookMetadata','decode_row','CompiledSnapshot','CandidateALoader','ProxyWorkbook','ProxyWorksheet','ProxyCell','_guard_compiled_read'},
        'import datetime as dt\nimport os\nimport re\nimport time\nimport zipfile\nfrom pathlib import Path\nfrom typing import Any\nfrom xml.etree import ElementTree as ET\nfrom . import index',loops=True)
copy('benchmark/inspection_helpers/index.py','index.py')
copy('benchmark/inspection_helpers/substrate.py','substrate.py', [('from benchmark.inspection_helpers import index','from . import index')])
copy('benchmark/candidate_a_live_runtime.py','runtime.py', [('from benchmark.inspection_helpers import index','from . import index'),('from benchmark.candidate_a_shadow_interposition import (','from .reads import (')],remove_main=True)
for name in ('delta','validate'):
    copy(f'benchmark/transparent_runtime/{name}.py',f'{name}.py', [('from benchmark.transparent_runtime.delta import','from .delta import')])
extract('benchmark/representative_checkpoint.py','capture.py',{'snapshot_xlsx','capture_wrap_timed'},
        'import os\nimport time\nfrom pathlib import Path\nfrom .delta import derive_delta, replay_delta, read_parts\nfrom .validate import validate_mechanical')
extract('benchmark/inspection_helpers/api.py','helper_common.py',{'CAP','CELL_CAP','CELL_FIELDS','_compact','_page','_styles'},'from typing import Any')
extract('benchmark/inspection_helpers/index.py','period_constants.py',{'PERIOD_RES'},'import re')
copy('benchmark/inspection_helpers/reference_api.py','helpers.py', [('from benchmark.inspection_helpers.api import (','from .helper_common import ('),('from benchmark.inspection_helpers.index import PERIOD_RES','from .period_constants import PERIOD_RES')])
DEST.joinpath('__init__.py').write_text('"""Internal frozen mechanics; not a model-facing interface."""\n')
(ROOT/'product_hygiene/extraction_manifest.json').write_text(json.dumps(rows,indent=2)+'\n')

if __name__ == '__main__':
    print(f'Extracted {len(rows)} modules without research imports.')
