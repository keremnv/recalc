#!/usr/bin/env python3
"""Phase13: Population-A census records (40 phase-12 CONTROL runs).

Classifications were produced by direct transcript + workbook forensics
(see working/digests, inspect_coverage.json, phase12r/PHASE12_REPLICATION).
This script assembles the JSONL from evidence joins + the hand classification
table below. Rerunnable.
"""
import json, glob, os

idx = { (i['pop'], i['task']): i for i in json.load(open('phase13/working/popA_index.json')) }
cov = { (r['pop'], r['task']): r for r in json.load(open('phase13/working/inspect_coverage.json')) }
rep = {}
for line in open('phase12r/PHASE12_REPLICATION.jsonl'):
    r = json.loads(line)
    if r.get('run', '').endswith('_CONTROL'):
        rep[r['task']] = r

# (pop, task) -> (primary, secondary, confidence, divergence, evidence, wb_evidence,
#                 recoverable, prior_targeted, mech_status, notes)
C = {
 # ---- submitted, recalc-recovered: stale cache + wrong-artifact verification ----
 ('popA','Template:06_05'): ('L0','L7','DIRECT','submit-boundary: verified /tmp LO copy, submitted stale output.xlsx',
  'recalced to /tmp/lo_check, read back correct values 14697..., submitted original; V1 exact=1.0',
  'formulas gold-correct (06_05 CONTROL=TREATMENT byte-identical per Ph12 §22); V0 caches None','yes: recalc-before-submit','yes: Ph12 D-demote scaffold fix','closed',
  'canonical submit-hygiene failure'),
 ('popA','Template:06_25'): ('L0','L7','DIRECT','submit-boundary: verified /tmp recalc, submitted stale',
  'self-corrected row-32 via /tmp readback, submitted stale; V1 mod=0.9643',
  'residual B31 label mismatch is pre-existing input/gold inconsistency (input has "%" suffix, gold lacks it)','yes: recalc-before-submit','yes: Ph12','closed',
  'residual after recalc is benchmark-state, agent blameless'),
 ('popA','Template:10_02'): ('L5','L0','STRONGLY_SUPPORTED','build script omitted EPS_Accretion!E10 (answer=265.52); stale cache on top',
  'verified /tmp/lo_out values, submitted stale; V1 mod=0.963 with E10 residual: V1 still fails -> L5 primary per taxonomy precedence',
  'E10 never filled; all other formulas gold-correct','partially: recalc recovers 0.963; residual needs reasoning','no','open',
  'Gate-A fix 4: was L0/L7; V1-fails => L5 primary'),
 ('popA','Template:11_03'): ('L5','L0','STRONGLY_SUPPORTED','build script: terminal value written to D19 instead of C19 (overfill+omission pair) + C35/D35 echo omissions',
  'V1 mod=0.6471/reg=0.9965: V1 first error D19 answer=None output=522.92 (overfill); C19 empty; residual is formula content + placement, not cache',
  'TV value correct but placed in D19 (gold blank) while C19 (gold 522.92) left empty; C22 reads D19 so downstream chain is self-consistent; C35/D35 implicit echo cells never written',
  'partially: recalc recovers 0.6471; residual needs reasoning','no','open',
  'C19/D19 = target-placement error (L5; discovery-adjacent); C35/D35 = implicit-target discovery (L4 PLAUSIBLE)'),
 ('popA','Template:11_04'): ('L5','L0','STRONGLY_SUPPORTED','build script: systematic wrong-row refs (24 vs 26), sign, circular C30',
  'V1 mod=0.3571/reg=0.9509: residual is formula content',
  'D26:H26 omitted; D30:H30 circular =$C$30 vs gold =-C14/C29; C33 sign; C34/C35 cascade from wrong rows','partially: residual is reasoning','no','open',
  'row-semantics misunderstanding (L3 PLAUSIBLE) behind wrong-row refs'),
 ('popA','Template:14_03'): ('L5',None,'DIRECT','build script: C48 sign error (=C47*C44 vs gold =-C47*C44)',
  'properly recalced (copied LO output back); single-cell residual mod=0.9818; V1=V0',
  'C48 formula text directly shows missing negation; independent check shared the same sign assumption','no: single reasoning slip','no','open',
  'model-capability slip; verification compared against own (same-assumption) check'),
 ('popB','Template:06_09'): ('L0','L7','DIRECT','submit-boundary: verified /tmp/recalc, submitted stale',
  'V1 exact=1.0 (CACHE_ONLY_SCORE_RECOVERY)','formulas gold-correct; V0 caches None','yes: recalc-before-submit','yes: Ph12','closed',''),
 ('popB','Template:06_16'): ('L0','L7','DIRECT','submit-boundary: verified /tmp/conv, submitted stale',
  'V1 exact=1.0 (CACHE_ONLY_SCORE_RECOVERY)','formulas gold-correct; V0 caches None','yes: recalc-before-submit','yes: Ph12','closed',''),
 ('popB','Template:16_02'): ('L0','L9','PLAUSIBLE','submit-boundary: submitted stale caches; V1 UNSCORABLE (volatility policy)',
  'recalced to /tmp/conv, read values, submitted stale; V1 unscorable so formula correctness unverified',
  'RentRoll!B4 =TODAY(): input cache 2026-03-01, gold 2026-05-27 — volatile vs frozen gold, unmatchable by any agent action; mod-cell formula correctness UNKNOWN','unknown: formulas unverified','partially: Ph12R volatility policy','unknown',
  'B4 cell is DIRECT L9; overall run PLAUSIBLE L0 (stale mod caches, formulas unproven)'),
 ('pilot_ext','Template:11_01'): ('L5','L0','STRONGLY_SUPPORTED','build script hardcoded K8=1 (gold 0.1428); stale cache on top',
  'verified /tmp copy, submitted stale; V1 mod=0.9792 with agent-caused K8 residual: V1 still fails -> L5 primary per taxonomy precedence',
  'K8 output=1 vs gold 0.1428 (agent edit); all else gold-correct','partially: recalc recovers 0.9792; residual needs reasoning','no','open',
  'Gate-A fix 4: was L0/L7; V1-fails => L5 primary; non-inferential pilot_ext'),
 # ---- output on disk but never submitted / corrupt ----
 ('popA','Financial_Model:12_01'): ('L7','L8','STRONGLY_SUPPORTED','post-build: over-verification loop instead of submit; wall-time death with V1-exact workbook on disk (ambiguous recalc class)',
  '30 calls; wrote output via XML surgery; verified formulas in place; LO-recalced; kept verifying instead of submitting until wall death; V1 exact/mod/reg=1.0 under RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN (FM: cache-only proof blocked by formula/package changes)',
  'V1 full-score recovery; cache-only mechanism unproven (ambiguous class) — "perfect work" hedged per Gate-A fix 8',
  'yes: submit-on-complete','no','open',
  'L7 primary by earliest-divergence (chose Nth verification over submit ~call 22, long before wall death) + S33 exact match (never-submit-despite-valid-workbook); counterargument noted: death was wall-time with budget unspent and LO-reported inconsistency genuine-looking -> L8 reading defensible, kept as secondary'),
 ('popB','Financial_Model:17_05'): ('L6','L8','STRONGLY_SUPPORTED','chart-XML authoring corrupted drawing1.xml; 40-call namespace-debug saga to call cap',
  'output exists but scorer XML parse fails (namespace prefix); V1 UNSCORABLE; transcript shows anchor-namespace patch loop',
  'openpyxl-stripped namespace prefixes + prefixed anchor insertion = invalid drawing XML','partially: needed XML fix + budget','no','open',
  'execution-mechanics failure on chart authoring; budget consumed by debugging'),
 # ---- empty submits ----
 ('popA','Debugging:04_06'): ('L7',None,'DIRECT','call 1: submit with zero inspection, no output',
  'api_calls=1, opens=0, submit only; coverage 0.0 on all 6 mod sheets','no output produced','no: degenerate','no','open','degenerate premature submit'),
 ('popA','Debugging:08_06'): ('L7',None,'DIRECT','call 1: submit with zero inspection, no output',
  'api_calls=1, opens=0, submit only; coverage 0.0 on all 3 mod sheets','no output produced','no: degenerate','no','open','degenerate premature submit'),
}

# ---- no-submit / truncated without output: L8 primary ----
# (status, key behavior) -> notes; secondaries from coverage probe
L8 = {
 ('pilot','Debugging:09_09'): ('L3','STRONGLY_SUPPORTED','wall-time death after full-sheet inspection + 4 rambles; coverage 1.0 on all 3 mod sheets — saw targets, never acted','wall-time 1061s, 27 calls, saves=0, full mod-region coverage','unknown; category evidence says budget-sensitive','yes: inspection helpers (Stage B, neutral verdict)','closed',
   'saw-but-never-acted; comprehension/action-initiation gap, not discovery'),
 ('pilot','Financial_Model:14_01'): ('L2','STRONGLY_SUPPORTED','wall-time death mid-inspection; partial coverage (DCF 0.0, Product Pricing 0.0, NCD/TL ~0)',
  'wall-time 1026s, 18 calls, saves=0','unknown','yes: inspection helpers','closed','discovery gaps on assumption/appendix sheets'),
 ('pilot','Template:03_01'): (None,'DIRECT','ramble trap: 5 NO_TOOL_CALL (finish=length), 6 real actions, wall-time death; coverage 1.0 (saw sheet)',
  'wall-time 970s, 11 calls, 5 max-length rambles','maybe: scaffold nudge/limits','no','open','reasoning runaway; model emitted no actionable tool call'),
 ('popA','Debugging:01_01'): ('L3','STRONGLY_SUPPORTED','cost-cap death ($0.257) after 39-call inspect loop; coverage 1.0 on mod sheets; never wrote',
  '1.70M tokens, 18 opens + 21 inspect scripts, saves=0','unknown','yes: inspection helpers','closed','canonical inspect-until-cap Debugging loop'),
 ('popA','Debugging:03_03'): ('L2','STRONGLY_SUPPORTED','call-cap death (40 calls, 26 view_xlsx); LBO covered but Valuation Bridge/Ex8/Ex9 at 0.0',
  '1.32M tokens, view_xlsx-heavy loop, saves=0','unknown','yes: inspection helpers','closed','view-loop never reached 3 mod sheets'),
 ('popA','Debugging:05_04'): ('L3','PLAUSIBLE','call-cap death on color-coding task; inspected Model sheet; footprint unmeasurable (font-color-only diff)',
  '40 calls, 1.61M tokens, saves=0','unknown','yes: inspection helpers','closed','color-task; comprehension of color convention unobservable'),
 ('popA','Debugging:08_03'): ('L3','STRONGLY_SUPPORTED','cost-cap death ($0.256); coverage 1.0 on mod sheets; never wrote',
  '36 calls, 1.65M tokens, saves=0','unknown','yes: inspection helpers','closed','saw-but-never-acted'),
 ('popA','Debugging:09_08'): ('L3','STRONGLY_SUPPORTED','cost-cap death ($0.260) in 81s wall (fast API burn); coverage 1.0; never wrote',
  '34 calls, 1.72M tokens, saves=0','unknown','yes: inspection helpers','closed','fastest budget burn in corpus'),
 ('popA','Debugging:10_03'): ('L2','STRONGLY_SUPPORTED','cost-cap death; Model covered but ~70 FY/subsidiary mod sheets at 0.0 (2300-row footprint)',
  '33 calls, 1.65M tokens, saves=0','unknown','yes: inspection helpers','closed','scale overwhelm: giant multi-sheet footprint, never reached most'),
 ('popA','Financial_Model:03_02'): ('L3','STRONGLY_SUPPORTED','wall-time death (893s); coverage 1.0 on all 3 mod sheets; never wrote',
  '32 calls, 1.08M tokens, saves=0','unknown','yes: inspection helpers','closed','saw-but-never-acted'),
 ('popA','Financial_Model:05_05'): ('L2','STRONGLY_SUPPORTED','wall-time death (922s); IS-Mgmt Co + PreOp partial gaps; never wrote',
  '27 calls, 1.05M tokens, saves=0','unknown','yes: inspection helpers','closed',''),
 ('popA','Financial_Model:07_01'): ('L2','STRONGLY_SUPPORTED','cost-cap death ($0.251, 38 calls); Construction Schedule sheets at 0.0; never wrote',
  '1.66M tokens, saves=0','unknown','yes: inspection helpers','closed','never reached construction inputs'),
 ('popA','Financial_Model:07_02'): ('L2','STRONGLY_SUPPORTED','wall-time death (1031s, only 16 calls — slow calls); partial coverage (Sales 0.62, Cashflow 0.37)',
  '0.39M tokens, saves=0','unknown','yes: inspection helpers','closed','slow-call wall death, not token burn'),
 ('popA','Financial_Model:12_05'): ('L2','STRONGLY_SUPPORTED','wall-time death (918s); Valuation sheet 0.0 (never inspected the key mod sheet)',
  '28 calls, 0.68M tokens, saves=0','unknown','yes: inspection helpers','closed','never opened Valuation'),
 ('popA','Financial_Model:14_05'): ('L2','STRONGLY_SUPPORTED','wall-time death (956s); Peers/NCD/TL/Anns gaps; never wrote',
  '30 calls, 1.08M tokens, saves=0','unknown','yes: inspection helpers','closed',''),
 ('popA','Financial_Model:18_03'): (None,'STRONGLY_SUPPORTED','wall-time death (908s) mid-build: actively writing + self-debugging (found O30=N32 self-ref bug, fixing); work only in /tmp',
  '21 calls, real progress, found+fixed own formula bug just before death','yes: more time very likely submits','no','open','work-in-progress death, not a loop'),
 ('popA','Template:01_03'): (None,'DIRECT','ramble trap: 7 NO_TOOL_CALL (finish=length), 3 real actions, wall-time death; saw sheet (coverage 1.0)',
  'wall-time 936s, 10 calls','maybe: scaffold nudge/limits','no','open','reasoning runaway'),
 ('popA','Template:15_02'): ('L2','DIRECT','ramble trap: 7 NO_TOOL_CALL, 3 real actions, wall-time death; LoanSizing coverage 0.0 (never inspected target)',
  'wall-time 930s, 10 calls','maybe: scaffold nudge/limits','no','open','ramble + discovery gap combined'),
 ('popB','Debugging:10_01'): ('L2','STRONGLY_SUPPORTED','wall-time death (slow LO tool call); Model covered, ~70 FY sheets mostly 0.0 (2014-row footprint)',
  '20 calls, 0.49M tokens, saves=0','unknown','yes: inspection helpers','closed','scale overwhelm + slow tool'),
 ('popB','Debugging:10_04'): ('L2','STRONGLY_SUPPORTED','cost-cap death; Model covered, FY sheets 0.0 (2009-row footprint)',
  '30 calls, 1.62M tokens, saves=0','unknown','yes: inspection helpers','closed','scale overwhelm'),
 ('popB','Debugging:10_05'): ('L2','STRONGLY_SUPPORTED','call-cap death; ~35-45% coverage across ~70 FY sheets (2014-row footprint); never wrote',
  '40 calls, 1.47M tokens, saves=0','unknown','yes: inspection helpers','closed','broad-but-shallow sweep of giant footprint, no action'),
 ('popB','Debugging:10_06'): ('L3','STRONGLY_SUPPORTED','wall-time death (396s, slow calls); ~80%+ coverage of 2012-row footprint incl BBC sheet; never wrote',
  '27 calls, 0.81M tokens, saves=0','unknown','yes: inspection helpers','closed','covered the haystack, never pulled the needle'),
 ('popB','Financial_Model:08_03'): ('L2','STRONGLY_SUPPORTED','cost-cap death; DCF/BS covered but all 3 Assumptions sheets 0.0; never wrote',
  '38 calls, 1.70M tokens, saves=0','unknown','yes: inspection helpers','closed','never found assumption drivers'),
 ('popB','Financial_Model:08_04'): ('L2','STRONGLY_SUPPORTED','cost-cap death; Assumptions sheets ~0.0-0.05; never wrote',
  '36 calls, 1.65M tokens, saves=0','unknown','yes: inspection helpers','closed','never found assumption drivers'),
 ('popB','Financial_Model:08_05'): ('L2','STRONGLY_SUPPORTED','wall-time death; Assumptions ~0.0; drifted to grepping phase11/mine.py (off-task)',
  '26 calls, 0.76M tokens, saves=0; final action greps research code','unknown','yes: inspection helpers','closed','off-task drift at end (confusion), not just looping'),
 ('popB','Template:16_05'): ('L2','PLAUSIBLE','wall-time death (888s, 16 calls); DirectCap covered; drifted to repo-grep for Riverside',
  '0.23M tokens, saves=0; final actions grep repo, not workbook','unknown','yes: inspection helpers','closed','off-task drift; slow/stalling rather than burning'),
}

out = open('phase13/FAILURE_CENSUS.jsonl', 'w')
n = 0
for (pop, task), i in sorted(idx.items()):
    r = {}
    r['population'] = 'A'
    r['task'] = task
    r['category'] = task.split(':')[0]
    r['model'] = 'z-ai/glm-5.3-flash'
    r['scaffold'] = 'phase12-custom-harness(bash/view_xlsx/submit)'
    r['pop'] = pop
    rr_status = i['status']
    r['run_status'] = rr_status
    r['submitted'] = rr_status == 'SUBMITTED'
    r['exact'] = i['exact']
    r['mod'] = i['mod']
    r['reg'] = i['reg']
    v = rep.get(task)
    if v:
        r['recalc_fair'] = 'NEEDS_NORMALIZED_RECALC'
        r['V1_class'] = v.get('classification')
        try:
            o = v['V1_score']['official']
            r['V1'] = {'exact': o['accuracy'], 'mod': o['modification_accuracy'],
                       'reg': o['regression_accuracy'], 'err': (o.get('error_message') or '')[:200]}
        except Exception:
            r['V1'] = None
    elif i.get('output') if False else False:
        r['recalc_fair'] = 'NEEDS_NORMALIZED_RECALC'
    else:
        # output on disk?
        import os as _os
        cat, tid = task.split(':')[0], task.split(':')[1]
        rd = f"phase12/runs/{pop}/{cat}_{tid}_CONTROL"
        has_out = _os.path.exists(rd + '/output.xlsx')
        r['recalc_fair'] = 'NEEDS_NORMALIZED_RECALC' if has_out else 'NOT_SCORE_BEARING'
        if has_out and not v:
            r['V1_class'] = 'UNREPLICATED' if task not in ('Financial_Model:12_01',) else 'RECALC_ASSOCIATED_AMBIGUOUS_V1exact1'
    key = (pop, task)
    if key in C:
        p, s, conf, div, ev, wb, rec, prior, ms, notes = C[key]
    else:
        s, conf, div, ev, wb, rec, prior, ms, notes = L8[key][0], L8[key][1], 'budget/cap/wall death with zero state movement: ' + L8[key][2], L8[key][3], 'coverage probe: ' + str(cov[key]['coverage'])[:200], L8[key][4], L8[key][5], L8[key][6], L8[key][7]
        p = 'L8'
    r['primary'] = p
    r['secondary'] = s
    r['confidence'] = conf
    r['first_divergence'] = div
    r['transcript_evidence'] = ev
    r['workbook_evidence'] = wb
    r['recoverable'] = rec
    r['prior_targeted'] = prior
    r['mech_status'] = ms
    r['notes'] = notes
    out.write(json.dumps(r) + '\n')
    n += 1
out.close()
print(n, 'Pop-A records')
