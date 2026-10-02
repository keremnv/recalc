#!/usr/bin/env python3
"""Phase13: formula-identity check at assessed roots (out vs gold).

For each root mismatch: normalized formula compare. Checkpointed, task-grouped.
ROOT_CAUSE classes: FORMULA_DIFFERS (L5-candidate), FORMULA_SAME_VALUE_DIFF
(L0-suspect/cascade), NO_FORMULA (value cells), UNRESOLVED (load fail).
"""
import json, os, gc
import openpyxl

DATA = 'benchmark-data/SpreadsheetBench-2/data'
DS = {c: {d['id']: d for d in json.load(open(f'{DATA}/{c}/dataset.json'))}
      for c in ('Template', 'Debugging', 'Financial_Model')}
scores = {x['id']: x for x in json.load(open('research/history/phase13/working/popB_scores.json'))}
CKPT = 'research/history/phase13/working/popB_rootcause.json'

def norm(f):
    if not isinstance(f, str) or not f.startswith('='):
        return None
    f = f.replace('$', '').upper()
    if f.startswith('=+'):
        f = '=' + f[2:]
    return f

def main(budget):
    det = json.load(open('research/history/phase13/working/popB_fullerr.json'))
    roots = json.load(open('research/history/phase13/working/popB_roots.json'))
    out = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
    bytask = {}
    for id in det:
        if id not in out:
            bytask.setdefault(det[id]['task'], []).append(id)
    done = 0
    for task in sorted(bytask):
        if done >= budget:
            break
        cat, tid = task.split(':')[0], task.split(':')[1]
        d0 = DS[cat][tid]
        try:
            wg = openpyxl.load_workbook(f"{DATA}/{cat}/{d0['golden_response_path']}", data_only=False)
        except Exception as e:
            for id in bytask[task]:
                out[id] = {'fatal': f'gold-load: {e}'[:80]}
            continue
        for id in bytask[task]:
            if done >= budget:
                break
            d = det[id]
            if d.get('fatal'):
                out[id] = {'fatal': d['fatal']}
                continue
            try:
                wo = openpyxl.load_workbook(scores[id]['V0'], data_only=False)
            except Exception as e:
                out[id] = {'fatal': f'v0-load: {e}'[:80]}
                continue
            r = roots[id]
            rs = [(s, c) for s, c, *_ in r['roots']]
            fd, fs, nf = [], [], []
            for m in d['mm']:
                if (m['sheet'], m['cell']) not in rs and (m['sheet'], m['cell']) not in [(s, c) for s, c, *_ in r['roots']]:
                    continue
                try:
                    gf = wg[m['sheet']][m['cell']].value
                    of = wo[m['sheet']][m['cell']].value
                except Exception:
                    continue
                if hasattr(gf, 'text'):
                    gf = gf.text
                if hasattr(of, 'text'):
                    of = of.text
                ng, no = norm(gf), norm(of)
                rec = (m['sheet'], m['cell'], m['kind'], m['cls'])
                if ng is not None or no is not None:
                    if ng == no:
                        fs.append(rec)
                    else:
                        fd.append(rec)
                else:
                    nf.append(rec)
            out[id] = {'task': task, 'n_root': len(rs),
                       'formula_differs': len(fd), 'formula_same': len(fs), 'no_formula': len(nf),
                       'same_sample': [list(x) for x in fs[:12]]}
            done += 1
            del wo
        del wg
        gc.collect()
        json.dump(out, open(CKPT, 'w'))
        print(f'{task}: ckpt {len(out)}', flush=True)
    pend = sum(1 for id in det if id not in out)
    print('pending:', pend)
    if pend == 0:
        vals = [v for v in out.values() if isinstance(v, dict) and 'n_root' in v]
        print('roots total:', sum(v['n_root'] for v in vals))
        print('formula_differs:', sum(v['formula_differs'] for v in vals))
        print('formula_same:', sum(v['formula_same'] for v in vals))
        print('no_formula:', sum(v['no_formula'] for v in vals))

if __name__ == '__main__':
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10**9)
