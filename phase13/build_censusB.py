#!/usr/bin/env python3
"""Phase13: Population-B census records (183 P1 runs) + loss allocation.

Inputs: popB_scores, popB_fullerr, popB_roots, popB_footprints,
popB_rootcause, BASELINE_CORRECTION_LEDGER (recalc classes).
Appends to FAILURE_CENSUS.jsonl (population B) and writes
working/popB_lossalloc.json (per-run mod/reg loss split).
Rerunnable (rewrites B section: rebuilds file from A records + new B).
"""
import json
from collections import Counter

A = [json.loads(l) for l in open('phase13/FAILURE_CENSUS.jsonl') if json.loads(l).get('population') == 'A']
scores = json.load(open('phase13/working/popB_scores.json'))
det = json.load(open('phase13/working/popB_fullerr.json'))
roots = json.load(open('phase13/working/popB_roots.json'))
fp = json.load(open('phase13/working/popB_footprints.json'))
cause = json.load(open('phase13/working/popB_rootcause.json'))
led = {}
for line in open('phase12r/BASELINE_CORRECTION_LEDGER.jsonl'):
    r = json.loads(line)
    if r.get('stratum') == 'P1':
        led[r['id']] = r.get('classification')

L0CELLS = {('Debugging:06_02', 'DCF', 'J6'),
           ('Debugging:06_07', 'Revenue Build', 'AC41'),
           ('Debugging:06_07', 'Revenue Build', 'AC43'),
           ('Financial_Model:19_05', 'Summary Valuation', 'D6'),
           ('Financial_Model:19_05', 'Summary Valuation', 'E6')}

TRAJ = {  # hand-classified sampled trajectories (id prefix -> fields)
    # filled below by task+run matching
}

def run_key(x):
    return x['run'].split('/')[-1] + '|' + x['task']

# sampled-traj overrides: (runfrag, task) -> (primary, secondary, conf, div, ev, rec, notes)
SAMPLED = {
    ('census-sixty-1', 'Debugging:05_08'): ('L0', None, 'DIRECT',
        'scored bytes: assessed MOD set empty (formula fixes value-invisible under data_only); exact unpassable as scored',
        'n_mm=0 with mod=0.0/reg=1.0; TRANSCRIPT shows agent fixed L12+L14 exactly as gold (verified via LO) but scorer cannot see formula-only fixes; run-dir copy has None caches (red herring — scored submission copy was recalced)',
        'no: task unpassable as scored', 'agent blameless; L0 benchmark/evaluator artifact'),
    ('census-sixty-1', 'Debugging:10_05'): ('L5', 'L4', 'STRONGLY_SUPPORTED',
        'partial fix: corrected M10/N13 CAGR cells; remaining assessed bugs unaddressed',
        'THINK claims seeded bugs found in P&L Summary; 177 mm with mod 0.26 — fixed 2 cells of a large bug set', 'partially',
        'representative partial-fix Debugging failure'),
    ('eight-2', 'Debugging:09_09'): ('L5', None, 'STRONGLY_SUPPORTED',
        'relative-chain refs where gold uses absolute anchors (09_09 LBO H107:M107, H163:M163)',
        'gold $F$106/$N$12 vs agent left-neighbor chain; gold row values prove non-equivalence', 'no: reasoning',
        'wrong-ref-style systematic error'),
    ('fifteen-2', 'Debugging:02_09'): ('L5', None, 'STRONGLY_SUPPORTED',
        'formula-content residual at mod 0.91', 'near-miss residual; formula differs at roots', 'no', ''),
    ('eight-2', 'Debugging:01_02'): ('L5', 'L0', 'STRONGLY_SUPPORTED',
        'retained embedded hardcodes (0.04 vs $C$47) + wrong ref ($C$20 vs C18); C36 D8:D8 formula-text artifact noted',
        'FORMULA-mode roots show hardcodes; D8:D8-vs-D8 first error is normalization artifact (1 cell)', 'partially',
        'primary is genuine hardcode retention, not the artifact'),
    ('census-sixty-1', 'Debugging:04_01'): ('L5', None, 'STRONGLY_SUPPORTED',
        'single-residual near-miss (mod 0.99)', 'balance-sheet/double-count fixes verified; one cell remains', 'no', ''),
    ('census-sixty-1', 'Financial_Model:06_01'): ('L0', None, 'DIRECT',
        'benchmark input malformed (undeclared dc prefix, col 574); scorer cannot load input; agent work (LO-repaired output) unscored',
        'input fails strict parse in current env (FINAL_ARCHITECTURE_FREEZE Q1 known case); retained output loads cleanly; THINK shows balance checks passed',
        'no: data defect', 'agent blameless; scaffold/data issue'),
    ('census-sixty-1', 'Financial_Model:10_01'): ('L5', None, 'STRONGLY_SUPPORTED',
        'YoY formula block wrong (mod 0.51)', 'THINK shows column-ref bug found+fixed mid-run; residual is formula content', 'no', ''),
    ('census-sixty-1', 'Financial_Model:05_01'): ('L5', None, 'STRONGLY_SUPPORTED',
        'IRR/model-component formula residual (mod 0.73)', 'LO-verified but values differ; formula differs at roots', 'no', ''),
    ('index-control-2', 'Financial_Model:18_02'): ('L5', None, 'STRONGLY_SUPPORTED',
        'Milestones-mapping residual after thorough self-debugging (mod 0.93)',
        'THINK shows script-bug found+fixed, LO output used as final (good hygiene); residual is formula content', 'no',
        'model-reasoning near-miss despite exemplary process'),
    ('repl-control-4', 'Financial_Model:11_02'): ('L5', None, 'STRONGLY_SUPPORTED',
        'upstream input error with identical downstream formulas (mod 0.98)',
        'assessed formulas identical to gold; fresh caches (NO_EFFECT) prove upstream inputs wrong', 'no',
        'cascade-symptom near-miss; true root outside assessed range'),
    ('index-control-1', 'Financial_Model:08_03'): ('L5', None, 'STRONGLY_SUPPORTED',
        'terminal-value/formula residual (mod 0.9955)', 'reverse-engineered TV verified vs sensitivity tables; small residual', 'no', ''),
    ('census-sixty-1', 'Template:16_12'): ('L5', 'L4', 'DIRECT',
        'systematic missing x12 annualization in 5-call rush (mod 0.0)',
        'out =E10*C10 vs gold =E10*C10*12 across I10:L13; labels carried units; verification checked consistency not semantics',
        'no: reasoning', 'reasoning-dominated: evidence in single view, wrong scale choice'),
    ('fifteen-2', 'Template:04_04'): ('L5', None, 'STRONGLY_SUPPORTED',
        'formula-content residual (mod 0.56)', 'formula differs at roots', 'no', ''),
    ('census-sixty-1', 'Template:06_12'): ('L5', None, 'STRONGLY_SUPPORTED',
        'formula-content residual (mod 0.67)', 'formula differs at roots', 'no', ''),
    ('census-sixty-1', 'Template:01_07'): ('L5', 'L0', 'STRONGLY_SUPPORTED',
        'formula residual + regression blemish (mod 0.91/reg 0.98)', 'mixed content residual', 'no', ''),
    ('census-sixty-1', 'Debugging:07_03'): ('L4', 'L3', 'STRONGLY_SUPPORTED',
        'wrong bug theory: fixed salient #REF!s; gold 1101 silent off-by-one refs untouched (recall 0.014)',
        'traj: found #REF!s via grep, fixed, LO-verified, balance ties — all outside scored bug set; gold = systematic F48->F49 shifts + structural inserts',
        'no: reasoning', 'salience-driven debugging vs systematic auditing; purest L4 in corpus'),
}

alloc = {}
out_recs = []
for x in scores:
    id = x['id']
    r = {'population': 'B', 'task': x['task'], 'category': x['category'],
         'model': 'z-ai/glm-5.3-flash', 'scaffold': 'swe-agent-1.1.0-ordinary-controls',
         'run': x['run'].split('/')[-1], 'run_status': 'SUBMITTED', 'submitted': True,
         'exact': x['exact'], 'mod': x['mod'], 'reg': x['reg'],
         'recalc_class': led.get(id)}
    r['recalc_fair'] = ('ALREADY_RECALC_FAIR' if led.get(id) == 'RECALC_NO_MATERIAL_EFFECT'
                        else ('INCOMPATIBLE_UNSUPPORTED' if led.get(id) in ('UNSCORABLE', 'RECALC_REGRESSION') else 'UNKNOWN'))
    if x['exact'] == 1.0:
        r.update({'primary': 'SUCCESS', 'secondary': None, 'confidence': 'DIRECT',
                  'first_divergence': 'none: exact 1', 'transcript_evidence': '', 'workbook_evidence': '',
                  'recoverable': 'n/a', 'prior_targeted': 'n/a', 'mech_status': 'n/a',
                  'notes': 'matched-success pool for §13 comparison'})
        alloc[id] = {'mod_loss': 0.0, 'reg_loss': 0.0, 'split': {}}
        out_recs.append(r)
        continue
    d = det[id]
    mod_loss = round(1 - x['mod'], 4)
    reg_loss = round(1 - x['reg'], 4) if x['reg'] is not None else 0.0
    # sampled override?
    ov = None
    for (frag, t), v in SAMPLED.items():
        if frag in x['run'] and t == x['task']:
            ov = v
            break
    if ov:
        p, s, conf, div, ev, rec, notes = ov
        r.update({'primary': p, 'secondary': s, 'confidence': conf, 'first_divergence': div,
                  'transcript_evidence': 'traj-sample: ' + ev, 'workbook_evidence': '',
                  'recoverable': rec, 'prior_targeted': ('yes: Ph12R/policy' if p == 'L0' else 'no'),
                  'mech_status': ('closed' if p == 'L0' and 'unpassable' in div or 'malformed' in div else 'open'),
                  'notes': notes})
        # loss split for sampled
        if p == 'L0':
            alloc[id] = {'mod_loss': mod_loss, 'reg_loss': reg_loss, 'split': {'L0': mod_loss}}
        elif p == 'L4':
            alloc[id] = {'mod_loss': mod_loss, 'reg_loss': reg_loss, 'split': {'L4': mod_loss}}
        else:
            alloc[id] = {'mod_loss': mod_loss, 'reg_loss': reg_loss, 'split': {'L5': mod_loss}}
        out_recs.append(r)
        continue
    # ---- rule-based classification from root/cause/footprint evidence ----
    c = cause.get(id, {})
    f = fp.get(id, {})
    rr = roots.get(id, {})
    if not c or 'n_root' not in c:
        r.update({'primary': 'L0' if 'dc on creator' in str(c.get('fatal', '')) else 'UNKNOWN',
                  'secondary': None, 'confidence': 'DIRECT' if 'dc on creator' in str(c.get('fatal', '')) else 'UNKNOWN',
                  'first_divergence': 'scorer XML parse failure: ' + str(c.get('fatal', ''))[:150],
                  'transcript_evidence': '', 'workbook_evidence': 'fatal=' + str(c.get('fatal', ''))[:150],
                  'recoverable': 'no', 'prior_targeted': 'yes: freeze Q1', 'mech_status': 'closed',
                  'notes': 'malformed-input class' if 'dc on creator' in str(c.get('fatal', '')) else ''})
        alloc[id] = {'mod_loss': mod_loss, 'reg_loss': reg_loss,
                     'split': {'L0': mod_loss} if r['primary'] == 'L0' else {'UNALLOCATED': mod_loss}}
        out_recs.append(r)
        continue
    rs = [(s_, c_) for s_, c_, *_ in rr.get('roots', [])]
    l0n = sum(1 for (s_, c_) in rs if (x['task'], s_, c_) in L0CELLS)
    D, S, N = c['formula_differs'], c['formula_same'], c['no_formula']
    miss_u = f.get('miss_untouched', 0) if isinstance(f, dict) else 0
    miss_p = f.get('miss_partial', 0) if isinstance(f, dict) else 0
    reg_ov = f.get('reg_overwrite', 0) if isinstance(f, dict) else 0
    # color-only?
    mm = d.get('mm', [])
    rset = set(rs)
    color_roots = sum(1 for m in mm if (m['sheet'], m['cell']) in rset and m['cls'] == 'COLOR_ONLY')
    n_root = c['n_root'] or 1
    if l0n == len(rs) and len(rs) > 0:
        p, s, conf = 'L0', None, 'DIRECT'
        div = f'all {len(rs)} assessed roots are proven formula-equivalent (RRI/sheet-prefix/range-cell); evaluator normalization artifact'
        ev = f'L0 cells: {sorted((x["task"],s_,c_) for s_,c_ in rs)}'
        split = {'L0': mod_loss}
        rec, ms, notes = 'no: evaluator artifact', 'closed', 'deduct from reasoning mass'
    elif color_roots == len(rs) and len(rs) > 0:
        p, s, conf = 'L5', None, 'STRONGLY_SUPPORTED'
        div = 'color-application residual: values/formulas match, font colors differ (color-task convention not applied)'
        ev = f'{color_roots} COLOR_ONLY roots'
        split = {'L5': mod_loss}
        rec, ms, notes = 'no: reasoning/convention', 'open', 'model-capability on color conventions'
    elif D > 0:
        p, conf = 'L5', 'STRONGLY_SUPPORTED'
        s = 'L4' if miss_u > 0 and miss_p == 0 else ('L0' if (led.get(id) != 'RECALC_NO_MATERIAL_EFFECT' and S > 0) else None)
        if s == 'L0':
            conf = 'STRONGLY_SUPPORTED'
        div = (f'{D} assessed roots with formulas differing from gold'
               + (f'; {miss_u} untouched-block omissions (implicit targets never attempted)' if miss_u else '')
               + (f'; {l0n} proven-equivalent cells (evaluator artifact, minor)' if l0n else '')
               + (f'; {S} same-formula cascade symptoms' if S else ''))
        ev = f'rootcause differs={D} same={S} noformula={N}; footprints recall={f.get("recall") if isinstance(f, dict) else "?"}'
        # split: L4 share by untouched-missing fraction, L0 share tiny, rest L5
        l4 = round(mod_loss * miss_u / n_root, 4) if miss_u else 0.0
        # L0-equivalent cells: noted, not subtracted (conservative: keep in L5)
        un = 0.0
        if led.get(id) != 'RECALC_NO_MATERIAL_EFFECT' and S > 0:
            un = round(mod_loss * S / n_root, 4)  # unverified same-formula share: cache vs cascade undecidable
        split = {'L5': round(mod_loss - l4 - un, 4)}
        if l4:
            split['L4'] = l4
        if un:
            split['UNALLOCATED'] = un
        rec, ms, notes = 'no: reasoning', 'open', 'formula-choice residual with evidence in context'
    elif S > 0:
        if led.get(id) == 'RECALC_NO_MATERIAL_EFFECT':
            p, s, conf = 'L5', None, 'STRONGLY_SUPPORTED'
            div = ('assessed roots are cascade symptoms (formulas gold-identical, caches fresh-consistent): '
                   'true root is an upstream content error outside the assessed range or behind dynamic refs')
            ev = f'same={S}; recalc-no-effect proves caches fresh → upstream inputs wrong'
            split = {'L5': mod_loss}
            rec, ms, notes = 'no: reasoning', 'open', 'upstream L5; assessed cells are symptoms'
        else:
            p, s, conf = 'L5', 'L0', 'PLAUSIBLE'
            div = ('formulas gold-identical at assessed roots but caches unverified (row UNSCORABLE): '
                   'upstream content error vs stale-cache artifact undecidable')
            ev = f'same={S}; recalc {led.get(id)}'
            split = {'UNALLOCATED': mod_loss}
            rec, ms, notes = 'unknown', 'unknown', 'conservative: unallocated (L5-upstream vs L0-cache)'
    else:
        # no_formula only
        if miss_u > 0 and (miss_p == 0):
            p, s, conf = ('L4', None, 'STRONGLY_SUPPORTED') if f.get('recall', 1) < 0.5 else ('L5', 'L4', 'STRONGLY_SUPPORTED')
            div = f'{miss_u} untouched-block omissions (recall {f.get("recall") if isinstance(f, dict) else "?"})'
        else:
            p, s, conf = 'L5', None, 'STRONGLY_SUPPORTED'
            div = f'{N} value-cell roots (omissions/overfills/wrong values, no formulas)'
        ev = f'noformula={N} miss_u={miss_u} miss_p={miss_p}'
        split = {'L4' if p == 'L4' else 'L5': mod_loss}
        rec, ms, notes = 'no: reasoning', 'open', ''
    r.update({'primary': p, 'secondary': s, 'confidence': conf, 'first_divergence': div,
              'transcript_evidence': '', 'workbook_evidence': ev,
              'recoverable': rec, 'prior_targeted': 'no', 'mech_status': ms, 'notes': notes})
    alloc[id] = {'mod_loss': mod_loss, 'reg_loss': reg_loss, 'split': split}
    out_recs.append(r)

# rewrite census: A records preserved + B records
with open('phase13/FAILURE_CENSUS.jsonl', 'w') as fh:
    for r in A:
        fh.write(json.dumps(r) + '\n')
    for r in out_recs:
        fh.write(json.dumps(r) + '\n')
json.dump(alloc, open('phase13/working/popB_lossalloc.json', 'w'), indent=1)
from collections import Counter as C
print('B records:', len(out_recs), '| fails:', sum(1 for r in out_recs if r['primary'] != 'SUCCESS'))
print(C((r['primary'], r['secondary']) for r in out_recs if r['primary'] != 'SUCCESS'))
print(C(r['confidence'] for r in out_recs if r['primary'] != 'SUCCESS'))
tot = {}
for v in alloc.values():
    for k, vv in v['split'].items():
        tot[k] = round(tot.get(k, 0) + vv, 4)
print('mod-loss split:', tot, 'total:', round(sum(tot.values()), 4))
