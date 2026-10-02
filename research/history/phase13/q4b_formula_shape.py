#!/usr/bin/env python3
"""Phase13 Q4b: classify cache-suspect same-formula roots by formula shape.

VOLATILE / NAMED-RANGE / POSITIONAL / PLAIN-divergence. Checkpointed.
Only runs with cache_suspect>0 in popB_q4.json are loaded.
"""
import json, os, gc, re
import openpyxl

DATA = 'benchmark-data/SpreadsheetBench-2/data'
DS = {c: {d['id']: d for d in json.load(open(f'{DATA}/{c}/dataset.json'))}
      for c in ('Template', 'Debugging', 'Financial_Model')}
scores = {x['id']: x for x in json.load(open('research/history/phase13/working/popB_scores.json'))}
CKPT = 'research/history/phase13/working/popB_q4b.json'
VOL = re.compile(r'\b(TODAY|NOW|RAND|RANDBETWEEN|OFFSET|INDIRECT|CELL|INFO)\s*\(', re.I)
POS = re.compile(r'\b(ROW|COLUMN|ROWS|COLUMNS)\s*\(', re.I)
REF = re.compile(r"(?:'[^']+'!)?\$?[A-Z]{1,3}\$?\d+")
FUNC = re.compile(r'\b([A-Z][A-Z0-9\.]*)\s*\(', re.I)
BARE = re.compile(r'(?<![A-Z0-9_\.\$])([A-Z][A-Z0-9_\.]{1,30})(?![A-Z0-9_\(\.])')

def main(budget):
    det = json.load(open('research/history/phase13/working/popB_fullerr.json'))
    roots = json.load(open('research/history/phase13/working/popB_roots.json'))
    q4 = json.load(open('research/history/phase13/working/popB_q4.json'))
    out = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
    want = [id for id in det if id in q4 and q4[id].get('cache_suspect', 0) > 0 and id not in out]
    bytask = {}
    for id in want:
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
                out[id] = {'fatal': str(e)[:80]}
            continue
        names = set()
        try:
            for dn in wg.defined_names.values():
                names.add(dn.name.upper())
            for ws in wg.worksheets:
                for dn in getattr(ws, 'defined_names', {}).values() if hasattr(ws, 'defined_names') else []:
                    names.add(getattr(dn, 'name', '').upper())
        except Exception:
            pass
        for id in bytask[task]:
            if done >= budget:
                break
            try:
                wo = openpyxl.load_workbook(scores[id]['V0'], data_only=False)
            except Exception as e:
                out[id] = {'fatal': str(e)[:80]}
                continue
            rs = set((s, c) for s, c, *_ in roots[id]['roots'])
            mm_by_cell = {(m['sheet'], m['cell']): m for m in det[id]['mm']}
            vol = named = pos = plain = other = 0
            examples = []
            for (sh, cell) in rs:
                m = mm_by_cell.get((sh, cell))
                if not m or m['cls'] == 'COLOR_ONLY':
                    continue
                try:
                    of = wo[sh][cell].value
                    gf = wg[sh][cell].value
                except Exception:
                    continue
                if hasattr(of, 'text'):
                    of = of.text
                if hasattr(gf, 'text'):
                    gf = gf.text
                def norm(f):
                    if not isinstance(f, str) or not f.startswith('='):
                        return None
                    return f.replace('$', '').upper()
                if norm(of) is None or norm(of) != norm(gf):
                    continue
                f = of
                if VOL.search(f):
                    vol += 1
                    kind = 'VOL'
                elif POS.search(f):
                    pos += 1
                    kind = 'POS'
                else:
                    bare = set(t.upper() for t in BARE.findall(f)) - names
                    # remove function names and known constants
                    funcs = set(t.upper() for t in FUNC.findall(f))
                    bare -= funcs
                    bare -= {'TRUE', 'FALSE', 'NULL', 'AND', 'OR', 'NOT', 'IF', 'IN'}
                    # remove sheet-qualified and ref-like tokens
                    bare = {t for t in bare if not re.fullmatch(r'[A-Z]{1,3}\d+', t)}
                    # tokens that are defined names?
                    toks = set(t.upper() for t in BARE.findall(f))
                    if toks & names:
                        named += 1
                        kind = 'NAMED'
                    elif bare:
                        # bare words that are not names/functions: table parts?
                        named += 1
                        kind = 'BARE?'
                    else:
                        plain += 1
                        kind = 'PLAIN'
                if len(examples) < 6:
                    examples.append([kind, sh, cell, f[:100]])
            out[id] = {'task': task, 'volatile': vol, 'named': named,
                       'positional': pos, 'plain': plain, 'examples': examples}
            done += 1
            del wo
        del wg
        gc.collect()
        json.dump(out, open(CKPT + '.tmp', 'w'))
        os.replace(CKPT + '.tmp', CKPT)
        print(f'{task}: ckpt {len(out)}', flush=True)
    pend = sum(1 for id in want if id not in out)
    print('pending:', pend)
    if pend == 0:
        vals = [v for v in out.values() if 'volatile' in v]
        print('volatile=%d named=%d positional=%d plain=%d' % (
            sum(v['volatile'] for v in vals), sum(v['named'] for v in vals),
            sum(v['positional'] for v in vals), sum(v['plain'] for v in vals)))

if __name__ == '__main__':
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10**9)
