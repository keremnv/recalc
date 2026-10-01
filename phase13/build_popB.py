#!/usr/bin/env python3
"""Phase13: build Population-B (P1 archived ordinary controls) score census.
Joins POPULATION_MANIFEST (original scores) with SCORE_REPLAY (recalc class)
and official score error messages. Read-only."""
import json
from collections import Counter

m = json.load(open('phase12r/POPULATION_MANIFEST.json'))
p1 = [e for e in m['eligible'] if e['stratum'] == 'P1']
replay = {}
for line in open('phase12r/SCORE_REPLAY.jsonl'):
    r = json.loads(line)
    replay[r['id']] = r

rows = []
for e in p1:
    r = replay.get(e['id'], {})
    rows.append({
        'id': e['id'], 'task': e['task'], 'category': e['category'],
        'run': e['run'], 'status': e.get('status'),
        'exact': e['original_score']['accuracy'],
        'mod': e['original_score']['modification_accuracy'],
        'reg': e['original_score']['regression_accuracy'],
        'err': (e['original_score'].get('error_message') or '')[:300],
        'recalc_class': r.get('classification'),
        'recalc_status': r.get('recalc_status'),
        'score_repro': r.get('score_reproduction'),
        'V0': e.get('V0_source'),
    })
json.dump(rows, open('phase13/working/popB_scores.json', 'w'), indent=1)
print('n=', len(rows))
print('exact:', Counter(x['exact'] for x in rows))
print('recalc_class:', Counter(x['recalc_class'] for x in rows))
print('by category exact1:', Counter((x['category'], x['exact']) for x in rows))
# error message taxonomy (first error only)
def etype(s):
    if not s:
        return 'NONE(exact=1?)'
    if s.startswith('Modification error'):
        return 'MOD:' + ('output=None' if 'output=None' in s else 'valued')
    if s.startswith('Regression error'):
        return 'REG:' + ('output=None' if 'output=None' in s else 'valued')
    return s[:40]
print(Counter(etype(x['err']) for x in rows))
# mod loss mass
import statistics
fails = [x for x in rows if x['exact'] != 1.0]
print('exact-fail n=', len(fails), 'summed mod loss=', round(sum(1 - x['mod'] for x in fails), 4))
print('summed reg loss=', round(sum(1 - x['reg'] for x in fails), 4))
for cat in ('Template', 'Financial_Model', 'Debugging'):
    f = [x for x in fails if x['category'] == cat]
    print(cat, 'fails=', len(f), 'modloss=', round(sum(1 - x['mod'] for x in f), 3),
          'regloss=', round(sum(1 - x['reg'] for x in f), 3))
