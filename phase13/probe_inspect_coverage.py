#!/usr/bin/env python3
"""Phase13 permitted deterministic probe P13-INSPECT-01.

Question: for ordinary no-submit runs, did the agent ever inspect the
gold-modification region before its budget expired?

Method: parse each CONTROL transcript for inspected (sheet,row-range) from
view_xlsx content calls + openpyxl iter_rows/range loops in bash commands;
compare against gold footprint (input-vs-gold value/formula diff).
No model calls. Read-only.
"""
import json, glob, os, re
import openpyxl
from openpyxl.utils import column_index_from_string

DATA = 'benchmark-data/SpreadsheetBench-2/data'

_DS = {}

def ds_paths(cat, task):
    if cat not in _DS:
        try:
            _DS[cat] = {d['id']: d for d in json.load(open(f'{DATA}/{cat}/dataset.json'))}
        except FileNotFoundError:
            _DS[cat] = {}
    d = _DS[cat].get(task)
    if not d:
        return None, None
    return f"{DATA}/{cat}/{d['spreadsheet_path']}", f"{DATA}/{cat}/{d['golden_response_path']}"

def gold_footprint(cat, task):
    pats = glob.glob(f'{DATA}/{cat}/spreadsheet/*/{task}_input.xlsx')
    patg = glob.glob(f'{DATA}/{cat}/spreadsheet/*/{task}_golden.xlsx')
    if pats and patg:
        pi, pg = pats[0], patg[0]
    else:
        pi, pg = ds_paths(cat, task)
    if not pi or not pg:
        return None
    wi = openpyxl.load_workbook(pi, data_only=False)
    wg = openpyxl.load_workbook(pg, data_only=False)
    fp = {}
    for ws in wg.worksheets:
        if ws.title not in wi.sheetnames:
            continue
        wsi = wi[ws.title]
        rows = set()
        for row in ws.iter_rows():
            for c in row:
                if c.value != wsi[c.coordinate].value:
                    rows.add(c.row)
        if rows:
            fp[ws.title] = {'min': min(rows), 'max': max(rows), 'n': len(rows)}
    return fp

def inspected_ranges(transcript_path):
    """Return {sheet: set(rows)} inspected. Conservative: view_xlsx content w/o
    row args = whole sheet; iter_rows(min_row,max_row) = that span."""
    insp = {}
    whole = set()
    try:
        lines = open(transcript_path)
    except FileNotFoundError:
        return insp, whole, 0
    n = 0
    for line in lines:
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get('role') != 'assistant':
            continue
        for tc in (o.get('tool_calls') or []):
            fn = ((tc.get('function') or {}).get('name'))
            args = ((tc.get('function') or {}).get('arguments', ''))
            if fn == 'view_xlsx':
                n += 1
                try:
                    a = json.loads(args)
                except Exception:
                    continue
                if a.get('mode') == 'content' and a.get('sheet'):
                    whole.add(a['sheet'])
            elif fn == 'bash':
                # find sheet selections + iter_rows spans
                for m in re.finditer(r"\['([^'\]]+)'\]|\"([^\"\]]+)\"\]|sheet[=\"']([\w .+\-&()]+)[\"']", args):
                    pass
                sheets = set(re.findall(r"wb\[['\"]([^'\"]+)['\"]\]", args))
                for m in re.finditer(r"min_row=(\d+)\s*,\s*max_row=(\d+)", args):
                    lo, hi = int(m.group(1)), int(m.group(2))
                    for s in (sheets or ['*']):
                        insp.setdefault(s, set()).update(range(lo, min(hi, lo + 500) + 1))
                    n += 1
                for m in re.finditer(r"range\((\d+)\s*,\s*(\d+)\)", args):
                    lo, hi = int(m.group(1)), int(m.group(2))
                    if hi - lo < 2000:
                        for s in (sheets or ['*']):
                            insp.setdefault(s, set()).update(range(lo, hi))
                        n += 1
    return insp, whole, n

results = []
for rd in sorted(glob.glob('phase12/runs/*/*_CONTROL')):
    pop = rd.split('/')[2]
    name = os.path.basename(rd)[:-len('_CONTROL')]
    for cat in ('Financial_Model', 'Debugging', 'Template'):
        if name.startswith(cat + '_'):
            task = name[len(cat) + 1:]
            break
    task_id = f'{cat}:{task}'
    rr = json.load(open(rd + '/run_record.json'))
    fp = gold_footprint(cat, task)
    insp, whole, nspans = inspected_ranges(rd + '/transcript_full.jsonl')
    # coverage: fraction of gold-mod rows ever inspected (per sheet)
    cov = {}
    for sheet, f in (fp or {}).items():
        if sheet in whole:
            cov[sheet] = 1.0
        else:
            rows = insp.get(sheet, set()) | insp.get('*', set())
            hit = sum(1 for r in range(f['min'], f['max'] + 1) if r in rows)
            span = f['max'] - f['min'] + 1
            cov[sheet] = round(hit / span, 3) if span else 0
    results.append({'pop': pop, 'task': task_id, 'status': rr.get('status'),
                    'output': rr.get('output_produced'), 'footprint': fp,
                    'whole_sheets': sorted(whole), 'n_spans': nspans, 'coverage': cov})

json.dump(results, open('phase13/working/inspect_coverage.json', 'w'), indent=1)
print(f'{len(results)} runs')
for r in results:
    if not r['output']:
        print(r['pop'], r['task'], r['status'], 'cov=', r['coverage'])
