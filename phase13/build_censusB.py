#!/usr/bin/env python3
"""Phase13: Population-B census records v2 (Gate-A remediated).

Classification systems (disclosed):
  T trajectory records (19 sampled .traj): earliest-divergence PRIMARY.
  S score-only records: MASS-DOMINANT PRIMARY (largest allocated share;
    ties -> attempted-error L5 with note). Loss shares computed over
    FULL uncapped root sets; no sampling, no caps.

Share key (per run, over n_root uncapped):
  L0CELLS (proven formula-equivalent incl. C36; 19_05 D6/E6 error-valued
    noted separately) -> L0
  MISSING untouched-block -> L4 ; MISSING partial-block -> L5
  COLOR missed -> L5 ; COLOR tooling (pipeline-destroyed, official
    comparator) -> L6
  formula-differs (non-L0) -> L5
  same-formula: NO_EFFECT plain+upstream-proven -> L5-upstream ;
    named/dynamic/OFFSET -> UNALLOCATED ; UNSCORABLE same -> UNALLOCATED ;
    time-volatile -> L0 (zero found in Pop B)
  REG loss partitioned by REG-root classes (overfill/differs->L5,
    color split exact, same follows MOD rule, fatal->L0).
Fully-unallocated runs -> PRIMARY UNKNOWN (never L5).
"""
import json
from collections import Counter

A = [json.loads(l) for l in open('phase13/FAILURE_CENSUS.jsonl') if json.loads(l).get('population') == 'A']
scores = json.load(open('phase13/working/popB_scores.json'))
det = json.load(open('phase13/working/popB_fullerr.json'))
roots = json.load(open('phase13/working/popB_roots.json'))
fp = json.load(open('phase13/working/popB_footprints.json'))
cause = json.load(open('phase13/working/popB_rootcause.json'))
q4 = json.load(open('phase13/working/popB_q4.json'))
q4b = json.load(open('phase13/working/popB_q4b.json'))
missD = json.load(open('phase13/working/popB_miss_in_D.json'))
led = {}
for line in open('phase12r/BASELINE_CORRECTION_LEDGER.jsonl'):
    r = json.loads(line)
    if r.get('stratum') == 'P1':
        led[r['id']] = r.get('classification')

L0CELLS = {('Debugging:06_02', 'DCF', 'J6'),
           ('Debugging:06_07', 'Revenue Build', 'AC41'),
           ('Debugging:06_07', 'Revenue Build', 'AC43'),
           ('Financial_Model:19_05', 'Summary Valuation', 'D6'),
           ('Financial_Model:19_05', 'Summary Valuation', 'E6'),
           ('Debugging:01_02', 'Ex 1 - LBO', 'C36')}
L0_ERRVAL = {('Financial_Model:19_05', 'Summary Valuation', 'D6'),
             ('Financial_Model:19_05', 'Summary Valuation', 'E6')}

SAMPLED_T = {
    ('census-sixty-1', 'Debugging:05_08'): ('L0', None, 'DIRECT',
        'scored bytes: assessed MOD set empty (formula fixes value-invisible under data_only); exact unpassable as scored',
        'traj: agent fixed L12+L14 exactly as gold (LO-verified) but scorer cannot see formula-only fixes; n_mm=0 with mod=0.0/reg=1.0',
        'no: task unpassable as scored', 'agent blameless; L0 evaluator artifact'),
    ('census-sixty-1', 'Debugging:07_03'): ('L4', 'L3', 'STRONGLY_SUPPORTED',
        'earliest divergence (traj step 11): wrong bug theory — fixed salient #REF!s; gold 1101 silent off-by-one refs untouched (recall 0.014)',
        'traj: grepped #REF!, fixed, LO-verified, balance ties — all outside scored bug set; gold = systematic F48->F49 shifts + structural inserts',
        'no: reasoning', 'salience-driven debugging; cell mix L5-heavy but decision is L4 (trajectory rule)'),
    ('census-sixty-1', 'Financial_Model:06_01'): ('L0', None, 'DIRECT',
        'benchmark input malformed (undeclared dc prefix, col 574); scorer cannot load input; agent work (LO-repaired output) unscored',
        'input fails strict parse (freeze Q1 known case); retained output loads cleanly; traj balance checks passed',
        'no: data defect', 'agent blameless; scaffold/data issue'),
    ('census-sixty-1', 'Template:16_12'): ('L5', 'L4', 'DIRECT',
        'earliest divergence (traj step 2): systematic missing x12 annualization in 5-call rush; labels carried units',
        'out =E10*C10 vs gold =E10*C10*12 across I10:L13; verification checked consistency not semantics',
        'no: reasoning', 'reasoning-dominated; split follows computed shares'),
    ('census-sixty-1', 'Debugging:10_05'): ('L5', 'L4', 'STRONGLY_SUPPORTED',
        'earliest divergence: partial fix — corrected M10/N13; remaining assessed bugs unaddressed',
        'traj claims seeded bugs found in P&L Summary; mod 0.26 over large bug set', 'partially',
        'representative partial-fix Debugging failure'),
    ('eight-2', 'Debugging:09_09'): ('L5', None, 'STRONGLY_SUPPORTED',
        'relative-chain refs where gold uses absolute anchors (LBO H107:M107, H163:M163)',
        'gold $F$106/$N$12 vs agent left-neighbor chain; gold row values prove non-equivalence', 'no: reasoning',
        'wrong-ref-style systematic error'),
    ('fifteen-2', 'Debugging:02_09'): ('L5', None, 'STRONGLY_SUPPORTED',
        'formula-content residual at mod 0.91', 'near-miss residual; formula differs at roots', 'no', ''),
    ('eight-2', 'Debugging:01_02'): ('L5', 'L0', 'STRONGLY_SUPPORTED',
        'retained embedded hardcodes (0.04 vs $C$47) + wrong ref ($C$20 vs C18); C36 D8:D8 text artifact (1 cell, L0)',
        'FORMULA-mode roots show hardcodes; C36 proven-equivalent L0 cell', 'partially',
        'primary is genuine hardcode retention, not the artifact'),
    ('census-sixty-1', 'Debugging:04_01'): ('L5', None, 'STRONGLY_SUPPORTED',
        'single-residual near-miss (mod 0.99)', 'balance-sheet/double-count fixes verified; one cell remains', 'no', ''),
    ('census-sixty-1', 'Financial_Model:10_01'): ('L5', None, 'STRONGLY_SUPPORTED',
        'YoY formula block wrong (mod 0.51)', 'traj column-ref bug found+fixed mid-run; residual is formula content', 'no', ''),
    ('census-sixty-1', 'Financial_Model:05_01'): ('L5', None, 'STRONGLY_SUPPORTED',
        'IRR/model-component formula residual (mod 0.73)', 'LO-verified but values differ; formula differs at roots', 'no', ''),
    ('index-control-2', 'Financial_Model:18_02'): ('L5', None, 'STRONGLY_SUPPORTED',
        'residual after thorough self-debugging (mod 0.93)',
        'traj script-bug found+fixed, LO output used as final (good hygiene); residual is formula content', 'no',
        'model-reasoning near-miss despite exemplary process'),
    ('repl-control-4', 'Financial_Model:11_02'): ('L5', None, 'STRONGLY_SUPPORTED',
        'upstream input error with identical downstream formulas (mod 0.98)',
        'assessed formulas identical to gold; fresh caches (NO_EFFECT) prove upstream inputs wrong', 'no',
        'cascade-symptom near-miss; true root outside assessed range'),
    ('index-control-1', 'Financial_Model:08_03'): ('L5', None, 'STRONGLY_SUPPORTED',
        'terminal-value/formula residual (mod 0.9955)', 'TV verified vs sensitivity tables; small residual', 'no', ''),
    ('fifteen-2', 'Template:04_04'): ('L5', None, 'STRONGLY_SUPPORTED',
        'formula-content residual (mod 0.56)', 'formula differs at roots', 'no', ''),
    ('census-sixty-1', 'Template:06_12'): ('L5', None, 'STRONGLY_SUPPORTED',
        'formula-content residual (mod 0.67)', 'formula differs at roots', 'no', ''),
    ('census-sixty-1', 'Template:01_07'): ('L5', 'L0', 'STRONGLY_SUPPORTED',
        'formula residual + regression blemish (mod 0.91/reg 0.98)', 'mixed content residual', 'no', ''),
}

def shares_for(id, x, d, c, f, qv, qb):
    """Return (mod_shares dict, reg_shares dict, notes list). Full-set counts."""
    notes = []
    n_root = c['n_root'] or 1
    rlist = roots[id]['roots']
    rset = set((s_, c_) for s_, c_, *_ in rlist)
    mm = d.get('mm', [])
    l0n = sum(1 for (s_, c_) in rset if (x['task'], s_, c_) in L0CELLS)
    l0err = sum(1 for (s_, c_) in rset if (x['task'], s_, c_) in L0_ERRVAL)
    if l0err:
        notes.append(f'{l0err} L0-equivalent cells are error-valued (#DIV/0! both sides): comparison artifact, no score recovery implied')
    D, S, N = c['formula_differs'], c['formula_same'], c['no_formula']
    # MISSING roots with gold formulas sit in D: move them to miss buckets
    # (omission, not wrong-choice); proven-equivalent cells to L0.
    D5 = D - l0n - missD.get(id, 0)
    miss_u = f.get('miss_untouched', 0) if isinstance(f, dict) else 0
    miss_p = f.get('miss_partial', 0) if isinstance(f, dict) else 0
    fair = (led.get(id) == 'RECALC_NO_MATERIAL_EFFECT')
    cm, ct = qv.get('color_missed', 0), qv.get('color_tooling', 0)
    C = cm + ct
    mD = missD.get(id, 0)  # MISSING roots with gold formulas (live in D)
    missN = miss_u + miss_p - mD  # MISSING roots living in N
    # separate color roots from S/N buckets (color spans both)
    Cn_nf = max(0, min(N - missN, C))  # color no-formula roots
    C_f = max(0, C - Cn_nf)  # color formula roots (inside S)
    S_nc = max(0, S - C_f)
    N_other = max(0, N - missN - Cn_nf)  # other value-cell roots -> L5
    # same-formula split via q4/q4b (per-run counts, full-set; color excluded)
    up = qv.get('upstream', 0)
    dyn = qv.get('dynamic', 0)
    b = qb.get(id, {})
    named = b.get('named', 0)
    volshape = b.get('volatile', 0)  # OFFSET/INDIRECT/array (timevol proven zero)
    plain = b.get('positional', 0) + b.get('plain', 0)
    same_l5up, same_un, same_l5unloc = 0, 0, 0
    if fair:
        # R5: fresh caches prove UPSTREAM CONTENT (not cache); family=L5-upstream.
        # Localized (proven-upstream + plain w/ 22/30 agent-scale sample) vs
        # unlocalized (named/dynamic/OFFSET channel) tracked separately.
        loc = min(up + plain, S_nc)
        same_l5up = loc
        same_l5unloc = S_nc - loc
        if dyn or named or volshape:
            notes.append(f'same-formula interior: localized-upstream {loc}->L5; unlocalized(named {named}/dyn {dyn}/offset {volshape})->L5-unloc[PLAUSIBLE]')
    else:
        same_un = S_nc  # caches unverifiable
        if S_nc:
            notes.append('row UNSCORABLE: non-color same-formula share UNALLOCATED (cache-vs-cascade undecidable)')
    # rootcause-skipped roots (output-side absence: deleted sheet/cell) -> L5
    skipped = max(0, n_root - (D + S + N))
    if skipped:
        notes.append(f'{skipped} roots absent output-side (deleted sheet/cell)->L5')
    # KIND-PURE denominators: MOD shares over MOD-kind roots, REG over REG.
    # Fallback: M==0 with mod_loss>0 (MOD mismatches all cascade) -> whole-set mix.
    mod_roots = [m for m in mm if (m['sheet'], m['cell']) in rset and m['kind'] == 'MOD']
    _fallback = (len(mod_roots) == 0 and round(1 - x['mod'], 4) > 0)
    if _fallback:
        mod_roots = [m for m in mm if (m['sheet'], m['cell']) in rset]
        notes.append('M==0 with mod_loss>0 (MOD cells all cascade): MOD split mirrors whole-root cause mix')
    M = len(mod_roots)
    m_l0 = sum(1 for m in mod_roots if (x['task'], m['sheet'], m['cell']) in L0CELLS)
    m_col = sum(1 for m in mod_roots if m['cls'] == 'COLOR_ONLY')
    m_miss = sum(1 for m in mod_roots if m['cls'] == 'MISSING_OUTPUT_NONE')
    m_miss_u = min(miss_u, m_miss)  # MISSING roots are MOD-kind except <=4 REG corpus-wide
    m_miss_p = max(0, m_miss - m_miss_u)
    # interior proportions from run cause counts (non-color, non-miss, non-L0)
    m_rest = M - m_l0 - m_col - m_miss
    mod_loss = round(1 - x['mod'], 4)
    interior = {'L5': D5 + same_l5up + N_other + skipped, 'L5unloc': same_l5unloc,
                'UNALLOCATED': same_un}
    itot = sum(interior.values()) or 1
    parts = {'L0': m_l0, 'L4': m_miss_u + m_miss_p * 0,  # (miss_p added to L5 below)
             'L5': m_miss_p + m_rest * (interior['L5'] + interior['L5unloc']) / itot + (m_col * cm / C if C else 0),
             'L6': (m_col * ct / C if C else 0),
             'UNALLOCATED': m_rest * interior['UNALLOCATED'] / itot}
    unloc_frac = (m_rest * interior['L5unloc'] / itot) / (M or 1)  # L5 share resting on unlocalized upstream
    cover = M
    if abs(sum(parts.values()) - M) > 1e-6:
        notes.append('cover-check: MOD parts do not sum to MOD roots')
    tot = M or 1
    shares = {k: v / tot for k, v in parts.items() if v}
    if cm or ct:
        notes.append(f'color roots: missed {cm}->L5, pipeline-destroyed {ct}->L6 (official comparator)')
    # normalize + scale
    stot = sum(shares.values()) or 1
    mshares = {k: round(mod_loss * v / stot, 4) for k, v in shares.items() if v > 0}
    # fix rounding drift on largest
    drift = round(mod_loss - sum(mshares.values()), 4)
    if drift and mshares:
        mshares[max(mshares, key=mshares.get)] = round(mshares[max(mshares, key=mshares.get)] + drift, 4)
    # REG shares by REG-root classes (exact from mm)
    reg_loss = round(1 - x['reg'], 4) if x['reg'] is not None else 0.0
    rshares = {}
    if reg_loss > 0:
        reg_roots = [m for m in mm if (m['sheet'], m['cell']) in rset and m['kind'] == 'REG']
        rc = Counter()
        for m in reg_roots:
            if (x['task'], m['sheet'], m['cell']) in L0CELLS:
                rc['L0'] += 1
            elif m['cls'] == 'COLOR_ONLY':
                rc['COLOR'] += 1
            elif m['cls'] in ('OVERFILL', 'MISSING_OUTPUT_NONE'):
                rc['L5'] += 1
            else:
                rc['FOLLOW'] += 1  # follows MOD-rule family
        # color split by run ratio
        if rc['COLOR'] and (cm or ct):
            rc['L5'] += rc['COLOR'] * cm / C
            rc['L6'] = rc.get('L6', 0) + rc['COLOR'] * ct / C
            del rc['COLOR']
        elif rc['COLOR']:
            rc['L5'] += rc.pop('COLOR')
        # FOLLOW: interior proportions (differs/same interior of REG roots)
        if rc['FOLLOW']:
            _it = (interior['L5'] + interior['L5unloc'] + interior['UNALLOCATED']) or 1
            rc['L5'] = rc.get('L5', 0) + rc['FOLLOW'] * (interior['L5'] + interior['L5unloc']) / _it
            rc['UNALLOCATED'] = rc.get('UNALLOCATED', 0) + rc['FOLLOW'] * interior['UNALLOCATED'] / _it
            del rc['FOLLOW']
        rtot = sum(rc.values()) or 1
        rshares = {k: round(reg_loss * v / rtot, 4) for k, v in rc.items() if v > 0}
        drift = round(reg_loss - sum(rshares.values()), 4)
        if drift and rshares:
            rshares[max(rshares, key=rshares.get)] = round(rshares[max(rshares, key=rshares.get)] + drift, 4)
    return mshares, rshares, notes, {'unloc_l5': round(mod_loss * unloc_frac, 4),
                                            'mshares': mshares, 'rshares': rshares}

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
                  'notes': 'matched-success pool for S13 comparison'})
        alloc[id] = {'mod_loss': 0.0, 'reg_loss': 0.0, 'mod_split': {}, 'reg_split': {}}
        out_recs.append(r)
        continue
    d = det[id]
    ov = None
    for (frag, t), v in SAMPLED_T.items():
        if frag in x['run'] and t == x['task']:
            ov = v
            break
    c = cause.get(id, {})
    f = fp.get(id, {})
    qv = q4.get(id, {})
    if not c or 'n_root' not in c:
        is_xml = 'dc on creator' in str(c.get('fatal', ''))
        r.update({'primary': 'L0' if is_xml else 'UNKNOWN', 'secondary': None,
                  'confidence': 'DIRECT' if is_xml else 'UNKNOWN',
                  'first_divergence': ('scorer XML parse failure (malformed benchmark input): ' if is_xml else 'unresolved load failure: ') + str(c.get('fatal', ''))[:150],
                  'transcript_evidence': '', 'workbook_evidence': 'fatal=' + str(c.get('fatal', ''))[:150],
                  'recoverable': 'no', 'prior_targeted': 'yes: freeze Q1' if is_xml else 'no',
                  'mech_status': 'closed' if is_xml else 'unknown', 'notes': 'malformed-input class' if is_xml else ''})
        ml = round(1 - x['mod'], 4)
        rl = round(1 - x['reg'], 4) if x['reg'] is not None else 0.0
        alloc[id] = {'mod_loss': ml, 'reg_loss': rl,
                     'mod_split': {'L0' if is_xml else 'UNALLOCATED': ml},
                     'reg_split': {'L0' if is_xml else 'UNALLOCATED': rl}}
        out_recs.append(r)
        continue
    mshares, rshares, notes, meta = shares_for(id, x, d, c, f, qv, q4b)
    ml = round(1 - x['mod'], 4)
    rl = round(1 - x['reg'], 4) if x['reg'] is not None else 0.0
    if c['n_root'] == 0:
        # 05_08 empty-set (or sampled L0): full L0
        r.update({'primary': 'L0', 'secondary': None, 'confidence': 'DIRECT',
                  'first_divergence': ov[3] if ov else 'assessed MOD set empty: exact unpassable as scored',
                  'transcript_evidence': ('traj: ' + ov[4]) if ov else '', 'workbook_evidence': 'n_mm=0 with mod=0.0',
                  'recoverable': 'no', 'prior_targeted': 'yes: Ph12R/policy', 'mech_status': 'closed',
                  'notes': (ov[6] if ov else '') + ' ' + ' '.join(notes)})
        alloc[id] = {'mod_loss': ml, 'reg_loss': rl, 'mod_split': {'L0': ml}, 'reg_split': rshares}
        out_recs.append(r)
        continue
    if ov:
        p, s, conf, div, ev, rec, nts = ov
        r.update({'primary': p, 'secondary': s, 'confidence': conf,
                  'first_divergence': '[T:earliest-divergence] ' + div,
                  'transcript_evidence': 'traj: ' + ev,
                  'workbook_evidence': f'split computed over {c["n_root"]} roots: ' + json.dumps(mshares),
                  'recoverable': rec, 'prior_targeted': 'yes: Ph12R/policy' if p == 'L0' else 'no',
                  'mech_status': 'closed' if p == 'L0' else 'open', 'notes': nts + ' ' + ' '.join(notes)})
    else:
        # S: mass-dominant PRIMARY over COMBINED mod+reg loss (ties -> L5).
        _rank = {'L5': 0, 'L4': 1, 'L0': 2, 'L6': 3, 'UNALLOCATED': 4}
        _pool = {}
        for k, v in list(mshares.items()) + list(rshares.items()):
            _pool[k] = _pool.get(k, 0) + v
        order = sorted(_pool.items(), key=lambda kv: (-kv[1], _rank.get(kv[0], 9)))
        p = order[0][0]
        if p == 'UNALLOCATED':
            p = 'UNKNOWN'
            _att = [(k, v) for k, v in order[1:] if v > 0 and k != 'UNALLOCATED']
            s = _att[0][0] if _att else None  # largest attributed share as secondary
            conf = 'PLAUSIBLE' if _att else 'UNKNOWN'
        else:
            rest = [(k, v) for k, v in order[1:] if v > 0]
            s = rest[0][0] if rest else None
            # PLAUSIBLE cap when the L5 primary rides on unlocalized upstream
            _l5loc = mshares.get('L5', 0) - meta['unloc_l5']
            _other = max([v for k, v in order if k != 'L5'] + [0])
            if p == 'L5' and meta['unloc_l5'] > 0 and _l5loc < _other:
                conf = 'PLAUSIBLE'
                notes.append('confidence PLAUSIBLE: L5 primary rests on unlocalized-upstream share (family proven, site unverified)')
            else:
                conf = 'STRONGLY_SUPPORTED'
        div = (f'[S:mass-dominant over {c["n_root"]} roots] differs={c["formula_differs"]} same={c["formula_same"]} '
               f'nf={c["no_formula"]} miss_u={f.get("miss_untouched", 0) if isinstance(f, dict) else "?"} '
               f'up={qv.get("upstream", 0)} colorT={qv.get("color_tooling", 0)}')
        r.update({'primary': p, 'secondary': s, 'confidence': conf, 'first_divergence': div,
                  'transcript_evidence': '',
                  'workbook_evidence': 'mod_split=' + json.dumps(mshares) + ' reg_split=' + json.dumps(rshares),
                  'recoverable': 'no: reasoning' if p in ('L5', 'L4') else ('unknown' if p == 'UNKNOWN' else 'no'),
                  'prior_targeted': 'no', 'mech_status': 'open' if p not in ('L0',) else 'closed',
                  'notes': ' '.join(notes)})
    alloc[id] = {'mod_loss': ml, 'reg_loss': rl, 'mod_split': mshares, 'reg_split': rshares}
    out_recs.append(r)

with open('phase13/FAILURE_CENSUS.jsonl', 'w') as fh:
    for r in A:
        fh.write(json.dumps(r) + '\n')
    for r in out_recs:
        fh.write(json.dumps(r) + '\n')
json.dump(alloc, open('phase13/working/popB_lossalloc.json', 'w'), indent=1)
print('B records:', len(out_recs), '| fails:', sum(1 for r in out_recs if r['primary'] != 'SUCCESS'))
print(Counter((r['primary'], r['secondary']) for r in out_recs if r['primary'] != 'SUCCESS'))
print(Counter(r['confidence'] for r in out_recs if r['primary'] != 'SUCCESS'))
tot, rtot = {}, {}
for v in alloc.values():
    for k, vv in v['mod_split'].items():
        tot[k] = round(tot.get(k, 0) + vv, 4)
    for k, vv in v['reg_split'].items():
        rtot[k] = round(rtot.get(k, 0) + vv, 4)
print('mod-loss split:', tot, 'total:', round(sum(tot.values()), 4))
print('reg-loss split:', rtot, 'total:', round(sum(rtot.values()), 4))
