#!/usr/bin/env python3
"""Phase13 analysis: root-vs-cascade attribution for fullerr mismatches.

A mismatched cell is ROOT if none of its formula precedents (within the
assessed workbook) also mismatch; otherwise CASCADE. Precedents are parsed
from formula text with a conservative regex (same-sheet + cross-sheet refs,
ranges expanded on the assessed sheets only). Cells with no formula or no
parseable refs default to ROOT. Read-only; runs on probe output.
"""
import json, re, sys
from collections import Counter
from openpyxl.utils import column_index_from_string, get_column_letter

REF = re.compile(r"(?:'([^']+)'!)?\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?")

def refs_of(formula, own_sheet):
    if not isinstance(formula, str) or not formula.startswith('='):
        return set()
    out = set()
    for m in REF.finditer(formula.upper()):
        sh, c1, r1, c2, r2 = m.group(1), m.group(2), int(m.group(3)), m.group(4), m.group(5)
        sh = (sh or own_sheet).casefold()
        if c2 and r2:
            r2 = int(r2)
            try:
                lo, hi = column_index_from_string(c1), column_index_from_string(c2)
            except Exception:
                continue
            if (hi - lo + 1) * (abs(r2 - r1) + 1) > 20000:
                continue
            for cc in range(min(lo, hi), max(lo, hi) + 1):
                for rr in range(min(r1, r2), max(r1, r2) + 1):
                    out.add((sh, f'{get_column_letter(cc)}{rr}'))
        else:
            out.add((sh, f'{c1}{r1}'))
    out.discard((own_sheet, None))
    return out

def main(path):
    det = json.load(open(path))
    summary = {}
    for id, d in det.items():
        mm = d.get('mm', [])
        # stored mm may be capped; roots computed over stored set (noted)
        mism = set((m['sheet'].casefold(), m['cell']) for m in mm if m['cell'] != '*')
        roots, casc = [], []
        for m in mm:
            if m['cell'] == '*':
                roots.append(m)
                continue
            f = m.get('out_f', '')
            # out_f is repr()'d; strip quotes
            if len(f) >= 2 and f[0] in "'\"" and f[-1] == f[0]:
                f = f[1:-1]
            if f.startswith('='):
                prefs = refs_of(f, m['sheet'])
                if prefs & mism:
                    casc.append(m)
                    continue
            roots.append(m)
        summary[id] = {'task': d['task'], 'n_mm': d['n_mm'],
                       'n_stored': len(mm), 'n_root': len(roots),
                       'n_cascade': len(casc),
                       'root_classes': Counter((m['kind'], m['cls']) for m in roots),
                       'roots': [(m['sheet'], m['cell'], m['cls'], m['ans'][:40], m['out'][:40]) for m in roots]}
    json.dump({k: {**v, 'root_classes': [ [list(kk), vv] for kk, vv in v['root_classes'].items() ]}
               for k, v in summary.items()},
              open('research/history/phase13/working/popB_roots.json', 'w'), indent=1)
    # aggregate root classes
    agg = Counter()
    for v in summary.values():
        for kk, vv in v['root_classes'].items():
            agg[kk] += vv
    print('=== ROOT classes ===')
    for k in sorted(agg, key=lambda k: -agg[k])[:25]:
        print(agg[k], k)
    # runs by root count
    rc = Counter(v['n_root'] for v in summary.values())
    print('root-count distribution:', dict(sorted(rc.items())[:15]))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'research/history/phase13/working/popB_fullerr.json')
