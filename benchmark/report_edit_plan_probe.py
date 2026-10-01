"""Evaluator-only report: never imported by model-facing inference."""
from __future__ import annotations
import json
import copy
import hashlib
import statistics
from collections import Counter,defaultdict
from pathlib import Path
import edit_plan_probe as p
import integrated_hybrid_synthesis_probe as integ
old=p.old


def stats(values):
    values=sorted(values)
    return {'n':len(values),'sum':sum(values),'mean':statistics.mean(values) if values else None,'median':statistics.median(values) if values else None,'p95':values[min(len(values)-1,int(.95*len(values)))] if values else None,'max':max(values) if values else None}


def usage(response):
    u=response.get('usage') or {}
    return {'input':int(u.get('prompt_tokens') or 0),'output':int(u.get('completion_tokens') or 0),'cost':u.get('cost')}


def classify_session(session,spine):
    task=session['job']['task'];target=session.get('target')
    out={'session_id':session['job']['session_id'],'task':task,'target':target,'status':session['status'],'gold_target':False}
    if not target:return out
    change=next((c for c in old.formula_gold_changes(task) if c['sheet']==target['sheet'] and c['address']==target['address']),None)
    parsed=session.get('synthesis',{}).get('parsed') or {}
    formula=parsed.get('formula') if parsed.get('status')=='PROPOSED' else None
    out.update({'proposal':parsed,'formula':formula,'working_set_count':len(session.get('working_set_ids',[]))})
    if not change:return out
    out['gold_target']=True;gold=change['golden_payload'];row={'task':task,'target':target}
    gp,gr,refs=integ.formula_ref_sets(row,gold)
    ids=integ.ref_ids(row,refs,spine);points={x for x in ids if x.startswith('cell:')};ranges=ids-points
    working=old.hybrid.canonicalize_ids(set(session.get('working_set_ids',[])))
    initial=old.hybrid.canonicalize_ids(set(session.get('bootstrap',{}).get('bootstrap_entity_ids',[])))
    complete=old.relational.coverage(working,points,ranges);q0=old.relational.coverage(initial,points,ranges)
    supported=bool(refs['parser_ok'] and not refs['opaque'])
    fp=old.synth_tools.relative_fingerprint(gold,target['col'],target['row'],sheet=target['sheet'])
    input_classes={f['class_id'] for f in spine['formulas'] if f.get('class_id')}
    existing=('formula_class:'+fp.eq_id in input_classes or fp.eq_id in input_classes)
    # Spine class IDs use eq_id verbatim after a prefix; inspect exact suffix.
    existing=existing or any(x.endswith(':'+fp.eq_id) for x in input_classes)
    exact=bool(formula and old.synth_tools._canonical_formula(formula)==old.synth_tools._canonical_formula(gold))
    pred_fp=old.synth_tools.relative_fingerprint(formula,target['col'],target['row'],sheet=target['sheet']) if formula else None
    fingerprint=bool(pred_fp and not pred_fp.opaque and not fp.opaque and pred_fp.eq_id==fp.eq_id)
    pp,pr,prefs=integ.formula_ref_sets(row,formula)
    pred_ids=integ.ref_ids(row,prefs,spine)
    tags=[]
    if not formula:tags=['ABSTAIN' if parsed.get('status')=='ABSTAIN' else 'INVALID_OUTPUT']
    elif not exact:
        if not prefs['parser_ok']:tags.append('INVALID_FORMULA')
        if ids-pred_ids:tags.append('MISSING_SOURCE')
        if pred_ids-ids:tags.append('EXTRA_SOURCE')
        if pp!=gp:tags.append('WRONG_SOURCE')
        if pr!=gr and pr and gr:tags.append('WRONG_RANGE_EXTENT')
        if old.synth_tools._operator_structure(formula,(target['sheet'],target['col'],target['row']))!=old.synth_tools._operator_structure(gold,(target['sheet'],target['col'],target['row'])):tags.append('WRONG_OPERATOR')
    out.update({'gold_formula':gold,'gold_references':sorted(ids),'gold_supported':supported,'gold_fingerprint':fp.eq_id,'existing_program':existing,'retrieval':complete,'bootstrap':q0,'retrieval_complete':complete['complete'] if supported else None,'formula_correct':exact,'exact_formula_match':exact,'literal_exact_match':formula==gold,'fingerprint_match':fingerprint,'missing_from_working_set':sorted(ids-working),'proposed_refs_outside_working_set':sorted(pred_ids-working),'failure_tags':tags,'evidence_source':'BOOTSTRAP_COMPLETE' if q0['complete'] else 'SQL_COMPLETED' if complete['complete'] else 'STILL_INCOMPLETE'})
    return out


def build():
    a=old.load(p.OUT/'phase_a.json');front=old.load(p.OUT/'frontend_report.json')
    rows=[old.load(f) for f in sorted((p.OUT/'phase_b').glob('*.json'))]
    sessions=[old.load(f) for f in sorted((p.OUT/'sessions').glob('*.json'))] if (p.OUT/'sessions').exists() else []
    spines={r['task']:old._load_spine(r['task']) for r in rows}
    scored=[classify_session(s,spines[s['job']['task']]) for s in sessions]
    valid=[s for s in scored if s['status']=='PROPOSAL_RETURNED' and s['gold_target'] and s.get('gold_supported')]
    for sc in scored:
        parsed=sc.get('proposal') or {}
        sc['transition_response']=('PROPOSED' if parsed.get('status')=='PROPOSED' else parsed.get('status') if parsed.get('status')
            else 'RETURNED_RETRIEVAL_ACTION_'+str(parsed.get('action')).upper() if parsed.get('action') else 'UNPARSEABLE')
    conditional={}
    for complete in (True,False):
        for existing in (True,False):
            sub=[s for s in valid if s['retrieval_complete']==complete and s['existing_program']==existing]
            conditional[f"{'COMPLETE' if complete else 'INCOMPLETE'}_{'EXISTING' if existing else 'NOVEL'}"]={'n':len(sub),'correct':sum(s['formula_correct'] for s in sub),'fingerprint_match':sum(s['fingerprint_match'] for s in sub)}
    known=[];earliest={};funnel=Counter();usages=defaultdict(list);expression_diagnostics=[]
    actuation={f.stem:old.load(f) for f in (p.OUT/'actuation').glob('*.json')} if (p.OUT/'actuation').exists() else {}
    official=old.load(p.OUT/'scoring/official_scores.json') if (p.OUT/'scoring/official_scores.json').exists() else None
    for r in rows:
        task=r['task'];m=r.get('metrics',{});critical=r.get('compiler_eval',{}).get('all_critical_requirements_preserved')
        ground=r.get('grounding',{}).get('evaluation',{});gold_rows=ground.get('rows',[])
        found=set((r.get('expansion') or {}).get('cell_ids',[]))
        expression_ids=None
        if isinstance(r.get('parsed'),dict):
            # Evaluator-only ablation: optional source metadata and obligation
            # validity cannot change the mathematical target expression. This
            # is never used for inference, target execution or primary scoring.
            witness=copy.deepcopy(r['parsed'])
            for op in witness.get('operations',[]):op.pop('source_relation',None)
            w=p.World(old.relational.db_path(task))
            try:
                exp=p.expand_edit_plan(witness,w)
                ids=set(exp['cell_ids']);gold=p.gold_ids(task,w)
                expression_ids=ids
                expression_diagnostics.append({'task':task,'primary_status':r['status'],'status':'EXPRESSIONS_EXPAND','gold_count':len(gold),'selected':len(ids),'true':len(ids&gold),'false':len(ids-gold),'recall':len(ids&gold)/len(gold),'precision':len(ids&gold)/len(ids) if ids else 0,'primary_error':r.get('error')})
            except p.PlanError as exc:expression_diagnostics.append({'task':task,'status':exc.category,'error':str(exc)})
            w.close()
        if r['status']=='MODEL_ACCESS_FAILURE':loss='MODEL_ACCESS_FAILURE'
        elif r['status']=='INTEGRATION_FAILURE':loss='INTEGRATION_FAILURE'
        elif critical is False:loss='F0_TASK_SPEC_LOSS'
        elif ground.get('grounded_recall',1)<1:loss='F1_GROUNDING_MISS'
        elif r['status'] not in ('VALID_PLAN','EMPTY_EXPANSION'):loss='F2B_EDIT_PLAN_INVALID'
        elif m.get('missed_targets',1)>0 or m.get('false_targets',1)>0:loss='F2A_EDIT_PLAN_SEMANTIC_MISS'
        else:loss='DOWNSTREAM_CENSORED_OR_UNRESOLVED'
        earliest[task]=loss
        funnel['tasks_attempted']+=1;funnel['gold_formula_targets']+=m.get('gold_count',0)
        funnel['critical_preserved_tasks']+=bool(critical)
        funnel['valid_plan_tasks']+=r['status'] in ('VALID_PLAN','EMPTY_EXPANSION')
        funnel['expanded_true_targets_unconditional']+=m.get('true_targets',0)
        if critical:
            funnel['gold_targets_after_task_ir']+=m.get('gold_count',0)
            kept={g['gold_entities']['cell_id'] for g in gold_rows if g['grounded_entity_retained']}
            funnel['gold_targets_after_grounding_weak_metric']+=len(kept)
            funnel['gold_targets_after_plan_and_expansion']+=len(kept&found)
        for source,response in [('plan',r.get('response',{}))]+([] if r.get('compiler_reused') else [('compiler',r.get('compiler',{}).get('response',{}))]):
            if response:usages[source].append({'task':task,**usage(response)})
        for previous in old.narrow_rows():
            if previous['task']!=task or previous['target']['address'] not in old.KNOWN_ADDRESSES:continue
            target=previous['target'];cid=f"cell:s{spines[task]['title_to_index'][target['sheet']]:02d}:r{target['row']}:c{target['col']}"
            entry=next((s for s in scored if s['task']==task and s.get('target',{}).get('cell_id')==cid),None)
            if any(k['task']==task and k['address']==target['address'] and k['sheet']==target['sheet'] for k in known):continue
            known.append({'task':task,'sheet':target['sheet'],'address':target['address'],'task_ir_all_critical':critical,'grounded_entity_retained':next((g['grounded_entity_retained'] for g in gold_rows if g['gold_entities']['cell_id']==cid),None),'included_after_expansion':cid in found,'expression_only_diagnostic_membership':cid in expression_ids if expression_ids is not None else None,'plan_status':r['status'],'false_targets_task':m.get('false_targets'),'downstream':entry,'earliest_task_failure':loss})
    for s in sessions:
        task=s['job']['task']
        for call in s.get('calls',[]):usages['retrieval'].append({'task':task,**usage(call.get('response',{}))})
        if s.get('synthesis'):usages['synthesis'].append({'task':task,**usage(s['synthesis'].get('response',{}))})
    bytask=defaultdict(Counter)
    for stage,items in usages.items():
        for u in items:
            bytask[u['task']]['input']+=u['input'];bytask[u['task']]['output']+=u['output'];bytask[u['task']]['calls']+=1;bytask[u['task']]['cost']+=u.get('cost') or 0
    p.save('usage_ledger.json',dict(usages))
    writes=[x for r in actuation.values() for x in r['writes']]
    applicable=[w for w in writes if w.get('formula')]
    for s in valid:
        task=s['task'];critical=next(r for r in rows if r['task']==task).get('compiler_eval',{}).get('all_critical_requirements_preserved')
        if critical and s['retrieval_complete']:
            funnel['sampled_targets_after_retrieval_complete']+=1
            if s['formula_correct']:
                funnel['sampled_targets_correct_formula']+=1
                if any(w.get('session_id')==s['session_id'] and w.get('applied') for w in writes):funnel['sampled_targets_accepted_actuated']+=1
    contract_rejections=sum(str(r.get('error','')).startswith('Unknown source entity text:') for r in rows)
    # Null-edit control: tasks whose actuation applied zero writes still pass through
    # the openpyxl resave + official refresh path, so their scores measure the pipeline,
    # not the agent. Verified separately: the pristine input refreshed by the same
    # LibreOffice path keeps Executive Summary!D23 at the golden 122.13, while the
    # zero-write openpyxl resave of the same workbook recalculates it to 62.84.
    null_control=[]
    for task,act in sorted(actuation.items()):
        applied=sum(bool(w.get('applied')) for w in act['writes'])
        row=(official or {}).get('tasks',{}).get(f'Financial_Model:{task}') or {}
        null_control.append({'task':task,'applied_writes':applied,'is_null_edit_control':applied==0,'regression_accuracy':row.get('regression_accuracy'),'modification_accuracy':row.get('modification_accuracy'),'error_message':row.get('error_message')})
    expr_ok={d['task'] for d in expression_diagnostics if d['status']=='EXPRESSIONS_EXPAND'}
    causes=Counter()
    for r in rows:
        if r['status'] in ('VALID_PLAN','EMPTY_EXPANSION'):continue
        e=str(r.get('error') or '')
        if r['status']=='MODEL_ACCESS_FAILURE':causes['MODEL_ACCESS_FAILURE']+=1
        elif r['status']=='INVALID_SCHEMA':causes['NO_PARSEABLE_PLAN_OR_SCHEMA']+=1
        elif e.startswith('Unknown source entity text:'):causes['OPTIONAL_SOURCE_METADATA_ONLY' if r['task'] in expr_ok else 'OPTIONAL_SOURCE_METADATA_AND_BAD_TARGET_EXPRESSION']+=1
        elif e=='Unknown obligation':causes['OBLIGATION_ID']+=1
        else:causes['TARGET_EXPRESSION_INVALID']+=1
    expanded=[d for d in expression_diagnostics if d['status']=='EXPRESSIONS_EXPAND']
    sel=sum(d['selected'] for d in expanded);tru=sum(d['true'] for d in expanded);gld=sum(d['gold_count'] for d in expanded)
    trimmed=[d for d in expanded if d['precision']>=.01]
    expression_micro={'tasks_expanding':len(expanded),'selected':sel,'true':tru,'gold':gld,'micro_recall':tru/gld if gld else None,'micro_precision':tru/sel if sel else None,
        'excluding_whole_sheet_outliers':{'tasks':len(trimmed),'selected':sum(d['selected'] for d in trimmed),'true':sum(d['true'] for d in trimmed),'gold':sum(d['gold_count'] for d in trimmed),
            'micro_recall':sum(d['true'] for d in trimmed)/sum(d['gold_count'] for d in trimmed) if trimmed else None,
            'micro_precision':sum(d['true'] for d in trimmed)/sum(d['selected'] for d in trimmed) if trimmed else None,
            'excluded':[d['task'] for d in expanded if d not in trimmed]}}
    result={'phase_a':a,'frontend':front,'contract_anchor_rejections':contract_rejections,'posthoc_revalidation':old.load(p.OUT/'posthoc_revalidation.json') if (p.OUT/'posthoc_revalidation.json').exists() else None,'posthoc_note':posthoc_note(),'null_edit_control':null_control,'invalid_plan_causes':dict(causes),'expression_only_micro':expression_micro,'model_weak_gate_identified_cleanly':False if contract_rejections else True,'plan_token_summary':stats([r['metrics']['plan_tokens'] for r in rows if r.get('metrics',{}).get('plan_tokens') is not None]),'expression_only_diagnostic':expression_diagnostics,'conditional_synthesis':conditional,'scored_sessions':scored,'known_cases':known,'earliest_failure':earliest,'earliest_distribution':dict(Counter(earliest.values())),'funnel':dict(funnel),'funnel_note':'After expansion, synthesis is resource-sampled. Never divide sampled survival counts by full target population to infer component quality. Grounding metric is inherited and permissive.',
        'tokens_by_stage':{stage:{'input':stats([x['input'] for x in xs]),'output':stats([x['output'] for x in xs]),'reported_cost':sum(x.get('cost') or 0 for x in xs)} for stage,xs in usages.items()},'per_task_usage':dict(bytask),'task_input_summary':stats([v['input'] for v in bytask.values()]),
        'verifier':{'proposals':len(applicable),'accepted':sum(w.get('hard_verifier_result')=='HARD_ACCEPT' for w in applicable),'rejected':sum(w.get('hard_verifier_result')=='HARD_REJECT' for w in applicable),'applied':sum(bool(w.get('applied')) for w in applicable)},'official_scores':official,'benchmark_scope':'Bounded partial outputs; exact task success is not an uncensored matched end-to-end estimate.',
        'verdict':['EDIT_PLAN_REPRESENTATION_SUPPORTED', 'EDIT_PLAN_GENERATION_SUPPORTED' if front['micro_recall']>=.75 else 'GENERATION_LIMITED_MODEL_AND_CONTRACT_CONFOUNDED' if contract_rejections else 'REPRESENTATION_GOOD_MODEL_WEAK', 'FRONTEND_STILL_DOMINANT' if any(x.startswith('F2') for x in earliest.values()) else 'COMPOSITION_ADVANCES_TO_NEXT_FRONTIER']}
    p.save('report.json',result)
    print(json.dumps({k:v for k,v in result.items() if k in ('conditional_synthesis','earliest_distribution','funnel','verifier','verdict','task_input_summary')},indent=2))
    return result


def _jsonable(v):
    """Workbook cells can hold dates and openpyxl formula objects; keep them readable."""
    if v is None or isinstance(v,(str,int,float,bool)):return v
    return v.isoformat() if hasattr(v,'isoformat') else str(v)


def posthoc_note():
    """One-paragraph pointer to the replay diagnostic, which lives beside this run."""
    path=p.OUT/'posthoc_revalidation.json'
    if not path.exists():
        return 'Not yet computed; run `python benchmark/edit_plan_revalidate.py`.'
    d=old.load(path)
    a,b=d['v1_micro'],d['v2_micro']
    return (f"The stored Phase B responses were later replayed through the same expansion algebra under a corrected citation contract, with no model calls and no change to this run's primary numbers "
            f"(`posthoc_revalidation.json`). Valid plans go from {a['valid_plan_tasks']} to {b['valid_plan_tasks']} of {a['tasks']} scoreable tasks and micro recall from {100*a['micro_recall']:.1f}% to {100*b['micro_recall']:.1f}% "
            f"on identical model output, which locates those rejections in the validator rather than the model. "
            f"Tasks recovered: {', '.join(m['task'] for m in d['tasks_recovered_by_contract_fix'])}. "
            f"A separately frozen replication with that fix applied lives in `../edit-plan-replication-probe/`.")


def audit_outputs():
    """Read-only source/output comparison before scorer's copied-output refresh."""
    path=p.OUT/'downstream_freeze.json'
    if not path.exists():return
    freeze=old.load(path);originals={task:hashlib.sha256(old.synth_tools._input_path(task).read_bytes()).hexdigest()==digest for task,digest in freeze['original_workbook_sha256'].items()}
    records=[]
    for f in sorted((p.OUT/'actuation').glob('*.json')):
        a=old.load(f);task=a['task'];expected={(w['target']['sheet'],w['target']['address']) for w in a['writes'] if w.get('applied')}
        # Not read_only: ReadOnlyCell carries no style_id, and the style check is
        # the only way to see actuation touching formatting it never intended to.
        source=old.openpyxl.load_workbook(old.synth_tools._input_path(task),data_only=False)
        output=old.openpyxl.load_workbook(a['output'],data_only=False)
        changed=[];style_changes=[]
        for sheet in source.sheetnames:
            left={(cell.row,cell.column):(cell.value,cell.style_id) for row in source[sheet].iter_rows() for cell in row if cell.value is not None}
            right={(cell.row,cell.column):(cell.value,cell.style_id) for row in output[sheet].iter_rows() for cell in row if cell.value is not None}
            for pos in sorted(left.keys()|right.keys()):
                before,bs=left.get(pos,(None,None));after,as_=right.get(pos,(None,None))
                address=old.openpyxl.utils.get_column_letter(pos[1])+str(pos[0])
                if before!=after:changed.append({'sheet':sheet,'address':address,'before':_jsonable(before),'after':_jsonable(after),'accepted_target':(sheet,address) in expected})
                if bs is not None and as_ is not None and bs!=as_:style_changes.append({'sheet':sheet,'address':address})
        source.close();output.close()
        records.append({'task':task,'actual_changed_cells':changed,'unintended_changes':sum(not x['accepted_target'] for x in changed),'occupied_cell_style_id_changes':style_changes,'note':'Style-ID comparison is a coarse check; scorer regression metric is also reported.'})
    p.save('actuation_audit.json',{'original_workbooks_hash_unchanged':originals,'tasks':records})


def render(result):
    a=result['phase_a'];f=result['frontend']
    def pct(x):return 'N/A' if x is None else f'{100*x:.1f}%'
    def table(headers,rows):
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in rows]])
    lines=['# Edit Plan composition experiment',
        'This is a diagnostic intervention on the 18 frozen Financial_Model tasks. Phase A uses gold only to construct evaluator witnesses. Phase B receives raw task, generated Task IR, grounding, sheet identities, and the frozen Edit Plan contract. All new model calls use exact `z-ai/glm-5.3-flash`, temperature 0, medium reasoning, through OpenRouter. No GPT, fallback, model retries, or prompt tuning.',
        '## Result and scope',
        f"Phase A: {pct(a['micro_recall'])} target recall, {pct(a['micro_precision'])} precision, {pct(a['task_exact_rate'])} exact task-set representability. Median compression {a['median_compression_ratio']:.2f}×. Phase B primary: {pct(f['micro_recall'])} recall and {pct(f['micro_precision'])} precision across {f['quality_tasks']} quality-evaluable tasks; {f['attempted_tasks']} task attempts.",
        'Verdicts: '+', '.join(result['verdict'])+'. The representation ceiling is strong. Primary generation performance includes whole-plan validation failures. It must not be interpreted as a pure GLM region-reasoning score because optional source metadata validation was unnecessarily restrictive.',
        '## Freeze, implementation and resource policy',
        'See `freeze.json`, `downstream_freeze.json` where produced, `edit_plan_schema.json`, `edit_plan_contract.md`, `edit_plan_prompt.txt`, and `integration_log.json`. The schema/contract and pre-existing downstream code remain frozen. The probe runner was extended with downstream/reporting orchestration and compiler-checkpoint resume; these did not alter model prompts or expansion semantics. Existing compiler outputs are reused for matching; missing outputs are compiled once. All candidate records in the selected grounding fields are retained in lossless table form; explicit grounding target IDs are encoded by rectangles. All sheet identities/bounds are supplied. Formula/dependency evidence is left to the frozen target-specific bootstrap.',
        'At most two workers, one plan call/task, 6,000 completion tokens, eight SQL calls/session, 24 sessions overall and two/task. A 3M downstream input-token soft cap stops starting new sessions; no result truncation or budget extension. The predeclared B1 gate requires at least 10% micro recall and 10% precision to inspect bounded downstream behavior; this is a material-improvement gate, not the strong-generation threshold of 75% recall.',
        '## Phase A: mechanical ceiling',
        table(['Task','Gold targets','Clauses','Plan tokens est.','Compression','Exact'],[[r['task'],r['gold_target_count'],r['clause_count'],r['plan_tokens'],f"{r['compression_ratio']:.2f}×",r['exact_set_match']] for r in a['rows']]),
        'All witnesses use rectangles, unions and optional exact occupancy filters. No explicit exceptions and no earned new primitives. The counterexample ledger is empty for formula-producing target membership. Search constructs exact covers and greedily reduces clause count; it is not a global minimum-clause proof. Estimates use the existing token estimator, not measured provider tokens.',
        'The witness covers the union of formula targets. It does not prove that the right obligation is attached to each subregion, that every region shares a formula program, or that literal-value edits are supported. RECTANGLE + UNION can represent every finite target set in principle; the nontrivial result is the observed small clause/token count.',
        '## Phase B: plans and target quality',
        table(['Task','Status','Expanded','True','False','Recall','Precision'],[[r['task'],r['status'],r.get('expanded_count','—'),r.get('true_targets','—'),r.get('false_targets','—'),pct(r.get('recall')),pct(r.get('precision'))] for r in f['rows']]),
        f"Plan-valid rate (empty allowed): {pct(f['valid_plan_rate'])}. Parse rate: {pct(f['parse_rate'])}. Status counts: `{json.dumps(f['status_counts'])}`.",
        'Every raw response, usage record, generated compiler output, grounding packet, plan, expansion and cell provenance is in `compiler/`, `contexts/`, and `phase_b/`. An invalid plan has no partial primary expansion and receives no downstream execution. Output generation uses JSON-object mode plus a strict schema validator; it is not provider-enforced JSON-Schema decoding.',
        '## Comparison with explicit enumeration',
        f"Prior published valid-run frontend: 4/55 selected cells were true targets, across 1,697 gold targets (7.3% precision, 0.24% recall). Matched prior-compiler subset here: {f['matched_previous_valid_tasks']} tasks. Exact counts: `{json.dumps(f['matched_counts'])}`. Compare these counts directly; the whole 18-task result has a different denominator from the prior nine valid runs.",
        '## Validity diagnostic and my assessment of the interface',
        'I made optional `source_relation.entity_ids` too restrictive: the contract/validator accepted cells, sheets, formula classes and temporal IDs, but excluded real text anchors that the supplied grounding context exposes. Rejection of those IDs is not evidence of hallucination. I kept the frozen boundary unchanged during Phase B. The evaluator-only analysis below drops optional source metadata and obligation-ID validation solely to measure the target expressions. It never repairs or executes a rejected plan, and is not the primary result.',
        table(['Task','Expression diagnostic','Selected','True','Recall','Precision'],[[r['task'],r['status'],r.get('selected','—'),r.get('true','—'),pct(r.get('recall')),pct(r.get('precision'))] for r in result['expression_only_diagnostic']]),
        f"Invalid-plan causes: `{json.dumps(result['invalid_plan_causes'])}`. `OPTIONAL_SOURCE_METADATA_ONLY` means the plan's target expression expands cleanly once optional citation metadata is dropped: the rejection was entirely the harness contract. `OPTIONAL_SOURCE_METADATA_AND_BAD_TARGET_EXPRESSION` means the target expression was independently invalid too, so fixing the contract alone would not have saved the plan.",
        *( [] if not result.get('posthoc_revalidation') else [
            '### Post-hoc revalidation under the corrected contract (zero model calls)',
            f"After this run was frozen, its stored plan JSON was replayed through the same expansion algebra with the citation contract corrected to accept every closed-world identity the grounding context exposes. No model was called and no plan was repaired, so any change is attributable to the validator alone. Valid plans: {result['posthoc_revalidation']['v1_micro']['valid_plan_tasks']} -> {result['posthoc_revalidation']['v2_micro']['valid_plan_tasks']} of {result['posthoc_revalidation']['v1_micro']['tasks']} parseable tasks. Micro recall {pct(result['posthoc_revalidation']['v1_micro']['micro_recall'])} -> {pct(result['posthoc_revalidation']['v2_micro']['micro_recall'])}, micro precision {pct(result['posthoc_revalidation']['v1_micro']['micro_precision'])} -> {pct(result['posthoc_revalidation']['v2_micro']['micro_precision'])}.",
            table(['Task','Was','Now','Recall','Precision'],[[m['task'],m['was'],m['now'],pct(m['recall']),pct(m['precision'])] for m in result['posthoc_revalidation']['tasks_recovered_by_contract_fix']]),
            'Four plans stay invalid under the corrected contract, for reasons that are the model\'s and not the harness\'s: a malformed cell identity, an obligation ID that does not exist, a rectangle corner outside the sheet\'s used bounds, and temporal endpoints invented on sheets exposing no such coordinate. This diagnostic does not replace the primary result above; it measures how much of that result was our own validator. Full detail in `posthoc_revalidation.json`.',
            'One correction to the framing: the contract text did enumerate four citation types, so the model deviated from it. The defect is the disproportion, not solely the narrowness. `source_relation` is optional metadata that cannot change which cells expand, yet an unrecognised citation discarded the whole target expression. A field that cannot affect the answer should not be able to void it.',
        ] ),
        f"Expression-only micro totals: `{json.dumps(result['expression_only_micro'])}`. This is the fairest available upper bound on this run's plan semantics, and it is still far from the Phase A ceiling. Every rejected `text:` identifier was verified present in the task's own world database with an exact 1:1 cell mapping, so those rejections are not model hallucinations.",
        'A plan selecting an entire sheet may achieve high recall with disastrous precision. Compactness therefore removes an output bottleneck but can amplify the consequences of a semantic targeting error. Precision and the expansion ledger are essential alongside recall. Invalid source metadata should also be diagnosed separately from an invalid target expression; they are different boundaries.',
        'One observed no-plan response exhausted all 6,000 completion tokens in reasoning. This is distinct from the old overflowing list of target IDs. Compact IR alone does not guarantee that the model leaves enough budget to serialize its answer; limits were not increased.',
        f"There were {result['contract_anchor_rejections']} primary rejections at the text-anchor source-metadata check. Estimated serialized nonempty model-plan token statistics: `{json.dumps(result['plan_token_summary'])}`. Actual completion usage includes reasoning and is reported separately below.",
        'The temporal primitive also exposed an interface mismatch: grounding supplies period IDs, while the SQL closure uses tcoord IDs. These are not automatically interchangeable identities. One model plan used period IDs where the grammar required temporal-coordinate IDs. This does not earn a new temporal relation; it calls for auditing how existing identities are exposed at the frontend boundary. No alias was invented or patched into this run.',
        '## Stage survival and earliest loss',
        table(['Stage','Count'],list(result['funnel'].items())),
        result['funnel_note'],
        table(['Task','Earliest supported loss'],sorted(result['earliest_failure'].items())),
        'The inherited critical-grounding metric can count sheet retention as entity retention, so it cannot establish that all subjects/sources/scopes were grounded. Likewise, Task IR critical-loss labels are frozen mechanical evaluator diagnostics; raw text remains visible and can sometimes compensate. These observational labels are useful, but not causal interventions.',
        '## Bounded downstream composition',
        table(['Retrieval/program stratum','Sessions','Exact/canonical correct','FP match'],[[k,v['n'],v['correct'],v['fingerprint_match']] for k,v in result['conditional_synthesis'].items()]),
        'Only evaluator-supported true targets enter this conditional synthesis table. Fingerprint-only matches are reported separately and do not count as formula correctness. No isolated scorer-equivalence claim is made. Small counts and frontend/resource selection prevent extrapolating the previous 77.8% existing-program or 22.2% novel-program rates.',
        table(['Session','Task','Target','Gold target','R complete','Transition response','Formula correct'],[[s['session_id'],s['task'],(s.get('target') or {}).get('address','—'),s['gold_target'],s.get('retrieval_complete','—'),s.get('formula') or s.get('transition_response','—'),s.get('formula_correct','—')] for s in result['scored_sessions']]),
        f"Seven of the eight sessions never produced a formula: at the synthesis transition the model emitted another retrieval action instead of the required proposal JSON, and the frozen protocol runs no repair call and executes no further query. This is a pre-existing protocol weakness, not something the Edit Plan frontend introduced — the previous composition run hit it in 31 of 55 sessions (24 PROPOSED). It is not explained by working-set size: in that run the sessions that did propose had *larger* median working sets (822 vs 618). The transition reuses the retrieval system prompt and only switches the user message, so the model has no instruction-level signal that the protocol phase changed. Seeing 7/8 rather than the prior ~56% failure rate is directionally worse but well inside sampling noise at n=8.",
        'The consequence is that this run gives almost no information about downstream synthesis. Two sessions landed on real gold targets; both had complete retrieval and both were existing-program cases; the one that transitioned correctly returned the exactly correct formula. The other six sessions were spent on false targets produced by the plan, which is frontend precision cost converted directly into wasted model calls.',
        'Execution selection and every censored target are in `downstream_selection.json`. Shared-program execution is allowed only for generated FILL_FORMULA operations with demonstrably equivalent input programs under translation. Missing/heterogeneous input programs are not assumed homogeneous. The audit records why each region uses its execution mode. A compact target region and a homogeneous formula region are different claims.',
        '## Verifier, actuation and benchmark scores',
        f"Verifier/actuation counts: `{json.dumps(result['verifier'])}`. Individual writes and rules are in `actuation/`. Accepted formulas are applied only to copied workbooks. No verifier repair occurs.",
        '### Null-edit control: the scoring path is not neutral',
        table(['Task','Applied writes','Null-edit control','Regression acc.','Modification acc.'],[[r['task'],r['applied_writes'],r['is_null_edit_control'],r['regression_accuracy'],r['modification_accuracy']] for r in result['null_edit_control']]),
        'Three of the four scored workbooks received zero applied writes, so they are accidental null-edit controls, and 07_03 still scores 0.9841 regression rather than 1.0. Tracing it: the input workbook caches `Executive Summary!D23` = 122.13 (the golden answer) behind `=SUM(F23:R23)`; the pristine input passed through the same `open_spreadsheet.py` refresh still reads 122.13; the zero-write openpyxl load/save of that same workbook reads 62.84. Removing the `fullCalcOnLoad="1"` flag openpyxl adds does not restore it, and the resave also collapses 10,889 shared-formula markers into expanded per-cell formulas. So the loss is introduced by the openpyxl resave in actuation, not by LibreOffice, not by the model.',
        'This matters beyond this run: the same actuate-then-score path produced the previously published composition benchmark numbers. Any regression accuracy below 1.0 on these workbooks is partly a writer artifact, and the true per-task measurement floor is unknown until the writer preserves workbook structure. I would fix this before treating any benchmark delta on this suite as an architecture signal.',
        'Scoring uses the normal LibreOffice refresh and benchmark evaluation path. These outputs are intentionally bounded partial workbooks; exact task success is not a matched uncensored composition estimate. Unexecuted cells dominate remaining modification errors. Literal-value requirements in the frozen task population also remain unsupported by the formula-only downstream path.',
        f"Scorer summary: `{json.dumps({k:result['official_scores'].get(k) for k in ('exact','scored','evaluation_runtime')} if result['official_scores'] else None)}`. Full per-task metrics are in `scoring/official_scores.json` when available.",
        '## Known cases',
        table(['Task','Sheet/target','IR critical','Included','Downstream session','Earliest task loss'],[[x['task'],x['sheet']+'!'+x['address'],x['task_ir_all_critical'],x['included_after_expansion'],(x.get('downstream') or {}).get('session_id','CENSORED/NOT_REACHED'),x['earliest_task_failure']] for x in result['known_cases']]),
        'Detailed known-case membership, grounding diagnostics, formulas and working-set coverage are in `report.json`. No gold address was injected into model context or target sampling.',
        '## Token and cost accounting',
        table(['Stage','Calls','Input tokens','Output tokens','Provider-reported cost'],[[k,v['input']['n'],v['input']['sum'],v['output']['sum'],f"${v['reported_cost']:.6f}"] for k,v in result['tokens_by_stage'].items()]),
        f"Per-task fresh input-token summary: `{json.dumps(result['task_input_summary'])}`. Reused compiler responses are excluded from fresh spend. `usage_ledger.json` preserves stage-level actual usage. Interrupted calls without a response have unknown unreported usage, so this is accounted spend rather than an invoice reconciliation.",
        'Target-set compression reduces output size; it does not automatically reduce the large grounded input or repeated target-session context. One plan prompt still materialized approximately 929k provider input tokens. No candidate pruning or prompt-context redesign was introduced to hide that cost.',
        '## Architecture perspective and next step',
        'The set-language abstraction is supported: thousands of edits can be expressed in a few rectangles. The next question is whether task-to-plan compilation chooses the right regions and assigns the right obligations/programs. That is where this run still loses correctness. More target-set primitives are not earned by the evidence.',
        'Before larger validation, resolve the narrow validation-contract mismatch exposed here, then assess plan semantics on the same stored responses or a separately frozen replication. Preserve primary results from this run. The expression-only diagnostic shows how much remains wrong even when metadata validation is set aside; it prevents attributing every failure to that one harness choice.',
        'I would keep target membership, obligation routing, and formula-program homogeneity as separate measured claims. A rectangle can be correct as a target set yet span different programs. Likewise, having reference IDs in a working set proves entity presence, not that sufficient relation/value evidence reached the model to determine a formula. These distinctions matter before interpreting conditional synthesis accuracy as a clean capability ceiling.',
        'The justified next step is narrow frontend compilation/validation work, not a larger benchmark or another retrieval search. This run does not yet establish that the downstream frontier has been recovered across composed tasks.',
    ]
    p.save('full_report.md','\n\n'.join(lines)+'\n')


if __name__=='__main__':audit_outputs();render(build())
