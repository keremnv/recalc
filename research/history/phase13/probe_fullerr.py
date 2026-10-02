#!/usr/bin/env python3
"""Phase13 permitted deterministic probe P13-FULLERR-02.

Question: for each P1 exact-failure, what are ALL mismatching cells
(the official scorer reports only the first), and what error classes
do they fall into?

Method: import the official evaluator's comparison helpers; run the
same classification+comparison over every assessed cell; dump every
mismatch with answer/output values and formula views. Read-only.
"""
import json, os, sys, math
sys.path.insert(0, 'benchmark-data/SpreadsheetBench-2/evaluation')
import openpyxl
from evaluation import (classify_cells_by_modification,
                        parse_answer_position, _find_sheet, _has_excel_error,
                        compare_cell_formula, _compare_cells, compare_cell_value,
                        compare_font_color)

DATA = 'benchmark-data/SpreadsheetBench-2/data'
DS = {c: {d['id']: d for d in json.load(open(f'{DATA}/{c}/dataset.json'))}
      for c in ('Template', 'Debugging', 'Financial_Model')}

def flags(cat, data):
    fc = ff = False
    if cat == 'Debugging':
        gp = data.get('spreadsheet_path', '')
        if 'Color' in gp:
            fc = True
        if 'Embedded' in gp:
            ff = True
    return fc, ff

def cell_class(ans_v, out_v, ans_f, out_f):
    """Classify one mismatch."""
    avis_num = isinstance(ans_v, (int, float)) and not isinstance(ans_v, bool)
    ovis_num = isinstance(out_v, (int, float)) and not isinstance(out_v, bool)
    if out_v is None and ans_v is not None:
        # did the agent write a formula with empty cache?
        if isinstance(out_f, str) and out_f.startswith('='):
            return 'FORMULA_NOCACHE'
        return 'MISSING_OUTPUT_NONE'
    if ans_v is None and out_v is not None:
        return 'OVERFILL'
    if avis_num and ovis_num:
        if ans_v == 0 and out_v == 0:
            return 'NUMERIC_ZERO_MISMATCH?'
        denom = max(abs(ans_v), abs(out_v), 1e-12)
        rel = abs(ans_v - out_v) / denom
        if rel < 1e-6:
            return 'NUMERIC_TINY'
        if abs(abs(ans_v) - abs(out_v)) / denom < 1e-9:
            return 'SIGN_FLIP'
        return 'NUMERIC_VALUE'
    if isinstance(ans_v, str) and isinstance(out_v, str) and ans_v.startswith('=') is False and out_v.startswith('=') is False:
        if ans_v.strip() == out_v.strip():
            return 'STRING_WS'
        return 'STRING_VALUE'
    if isinstance(ans_f, str) and isinstance(out_f, str) and ans_f.startswith('=') and out_f.startswith('='):
        return 'FORMULA_TEXT'
    return f'TYPE_OTHER({type(ans_v).__name__}/{type(out_v).__name__})'

def full_errors(cat, task_id, proc_file):
    data = DS[cat][task_id]
    fc, ff = flags(cat, data)
    input_file = f"{DATA}/{cat}/{data['spreadsheet_path']}"
    gt_file = f"{DATA}/{cat}/{data['golden_response_path']}"
    need_raw = ff
    try:
        wb_in = openpyxl.load_workbook(input_file, data_only=not need_raw)
        wb_gt = openpyxl.load_workbook(gt_file, data_only=not need_raw)
        wb_pr = openpyxl.load_workbook(proc_file, data_only=not need_raw)
        if not ff:
            wb_in_f = openpyxl.load_workbook(input_file, data_only=False)
            wb_gt_f = openpyxl.load_workbook(gt_file, data_only=False)
            wb_pr_f = openpyxl.load_workbook(proc_file, data_only=False)
        else:
            wb_in_f = wb_gt_f = wb_pr_f = None
    except Exception as e:
        return {'fatal': str(e)[:200]}
    out = {'fatal': None, 'with_formula': ff, 'with_font_color': fc, 'mm': [],
           'reg_total': 0, 'mod_total': 0, 'reg_correct': 0, 'mod_correct': 0}
    for scr in parse_answer_position(data['answer_position']):
        if '!' in scr:
            sheet, crange = scr.split('!')
        else:
            sheet, crange = wb_gt.sheetnames[0], scr
        sheet = sheet.strip("'").strip()
        crange = crange.strip("'").strip()
        reg, mod = classify_cells_by_modification(
            wb_in, wb_gt, sheet, crange, fc, ff,
            wb_input_formula=wb_in_f, wb_answer_formula=wb_gt_f)
        ws_a = _find_sheet(wb_gt, sheet)
        ws_o = _find_sheet(wb_pr, sheet)
        ws_af = _find_sheet(wb_gt_f, sheet) if wb_gt_f else None
        ws_of = _find_sheet(wb_pr_f, sheet) if wb_pr_f else None
        if ws_o is None:
            out['mm'].append({'sheet': sheet, 'cell': '*', 'kind': 'REG+MOD',
                               'cls': 'SHEET_MISSING', 'ans': None, 'out': None})
            out['reg_total'] += len(reg)
            out['mod_total'] += len(mod)
            continue
        out['reg_total'] += len(reg)
        out['mod_total'] += len(mod)
        for cells, label in ((reg, 'REG'), (mod, 'MOD')):
            for name in cells:
                ca, co = ws_a[name], ws_o[name]
                if (not ff and ws_af is not None and ws_of is not None
                        and (_has_excel_error(ca) or _has_excel_error(co))):
                    ok = compare_cell_formula(ws_af[name], ws_of[name])
                    fb = 'ERRFB'
                else:
                    ok = _compare_cells(ca, co, fc, ff)
                    fb = 'NORM'
                if ok:
                    if label == 'REG':
                        out['reg_correct'] += 1
                    else:
                        out['mod_correct'] += 1
                if not ok:
                    av, ov = ca.value, co.value
                    af = ws_af[name].value if ws_af is not None else av
                    of = ws_of[name].value if ws_of is not None else ov
                    if hasattr(av, 'text'):
                        av = av.text
                    if hasattr(ov, 'text'):
                        ov = ov.text
                    try:
                        value_ok = compare_cell_value(av, ov)
                    except Exception:
                        value_ok = None
                    try:
                        color_ok = compare_font_color(ca.font, co.font)
                    except Exception:
                        color_ok = None
                    cls = cell_class(av, ov, af, of)
                    if value_ok and not color_ok:
                        cls = 'COLOR_ONLY'
                    out['mm'].append({
                        'sheet': sheet, 'cell': name, 'kind': label,
                        'mode': ('FORMULA' if ff else 'VALUE') + ('+' + fb if fb == 'ERRFB' else ''),
                        'cls': cls, 'value_ok': value_ok, 'color_ok': color_ok,
                        'ans': repr(av)[:120], 'out': repr(ov)[:120],
                        'ans_f': repr(af)[:120], 'out_f': repr(of)[:120]})
    return out

def main():
    import os, sys
    # Resume mode: rerun ids in RESUME file (one per line) uncapped with
    # self-check fields, merging into the canonical archive. Budget = max runs.
    # Full mode (no args): original behavior over all fails.
    rows = json.load(open('research/history/phase13/working/popB_scores.json'))
    byid = {x['id']: x for x in rows}
    if len(sys.argv) > 1:
        want = [l.strip() for l in open(sys.argv[1]) if l.strip()]
        budget = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
        det = json.load(open('research/history/phase13/working/popB_fullerr.json'))
        done_ids = set()
        try:
            done_ids = set(json.load(open('research/history/phase13/working/fullerr_resume_done.json')))
        except Exception:
            pass
        n = 0
        for id in want:
            if id in done_ids:
                continue
            if n >= budget:
                break
            x = byid[id]
            r = full_errors(x['category'], x['task'].split(':')[1], x['V0'])
            det[id] = {'task': x['task'], 'run': x['run'], 'fatal': r.get('fatal'),
                       'flags': (r.get('with_formula'), r.get('with_font_color')),
                       'reg': (r.get('reg_correct'), r.get('reg_total')),
                       'mod': (r.get('mod_correct'), r.get('mod_total')),
                       'official': (x['reg'], x['mod']),
                       'n_mm': len(r.get('mm', [])), 'mm': r.get('mm', [])}
            done_ids.add(id)
            n += 1
            json.dump(det, open('research/history/phase13/working/popB_fullerr.json', 'w'))
            json.dump(sorted(done_ids), open('research/history/phase13/working/fullerr_resume_done.json', 'w'))
            print(f'{x["task"]} mm={len(r.get("mm", []))} ({len(done_ids)}/{len(want)})', flush=True)
        print(f'resumed {n}; remaining: {len(want) - len(done_ids)}')
        return
    fails = [x for x in rows if x['exact'] != 1.0]
    agg = {}
    det = {}
    for i, x in enumerate(fails):
        cat = x['category']
        tid = x['task'].split(':')[1]
        r = full_errors(cat, tid, x['V0'])
        det[x['id']] = {'task': x['task'], 'run': x['run'], 'fatal': r.get('fatal'),
                        'flags': (r.get('with_formula'), r.get('with_font_color')),
                        'reg': (r.get('reg_correct'), r.get('reg_total')),
                        'mod': (r.get('mod_correct'), r.get('mod_total')),
                        'official': (x['reg'], x['mod']),
                        'n_mm': len(r.get('mm', [])), 'mm': r.get('mm', [])}
        for m in r.get('mm', []):
            k = (m['kind'], m['cls'], m.get('mode'))
            agg[k] = agg.get(k, 0) + 1
        if (i + 1) % 30 == 0:
            print(f'{i+1}/{len(fails)}', flush=True)
    json.dump(det, open('research/history/phase13/working/popB_fullerr.json', 'w'), indent=1)
    print('=== mismatch class counts (kind, class, mode) ===')
    for k in sorted(agg, key=lambda k: -agg[k]):
        print(agg[k], k)

if __name__ == '__main__':
    main()
