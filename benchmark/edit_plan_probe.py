"""Frozen Edit Plan representability and matched composition experiment."""
from __future__ import annotations
import argparse
import hashlib
import json
import statistics
import os
import concurrent.futures
import time
from collections import Counter, defaultdict
from pathlib import Path
import end_to_end_composition_probe as old
from edit_plan import SCHEMA, World, PlanError, expand_edit_plan

OUT = old.MECHANICAL / "edit-plan-composition-probe"
POP = old.OUT / "end_to_end_population.json"
CONTRACT = Path(__file__).with_name("edit_plan_contract.md")
PLAN_PROMPT = "Produce a compact Edit Plan describing the workbook regions that should be modified to satisfy the raw task. Do not enumerate target cell IDs. One proposal only.\n\n" + CONTRACT.read_text() + "\n\nEXACT JSON SCHEMA:\n" + json.dumps(SCHEMA,separators=(",",":"))
LIMITS = {"workers":2,"plan_output_tokens":6000,"max_sql_calls":8,"downstream_sessions":24,"per_task_sessions":2,"total_downstream_input_soft_cap":3000000,"target_gate_micro_recall":.10,"target_gate_micro_precision":.10,"model":"z-ai/glm-5.3-flash","temperature":0,"reasoning":"medium","retries":0}


def save(name, data):
    old.write(OUT / name, data)


def tokens(x):
    return old.token_estimate(json.dumps(x, ensure_ascii=False, separators=(",", ":")))


def gold_ids(task, world):
    names = {s["name"]: sid for sid, s in world.sheets.items()}
    return {f"cell:{names[c['sheet']][6:]}:r{c['row']}:c{c['col']}" for c in old.formula_gold_changes(task)}


def coord(cid):
    _, s, r, c = cid.split(":")
    return s, int(r[1:]), int(c[1:])


def rectangle_cover(ids):
    """Two deterministic run-merge covers; smallest clause count wins.

    Evaluator witnesses may use this on gold. Runtime uses it only to losslessly
    describe *existing grounding candidates* in model context.
    """
    options = []
    for transpose in (False, True):
        rows = defaultdict(list)
        for cid in ids:
            s, r, c = coord(cid)
            rows[(s, c if transpose else r)].append(r if transpose else c)
        runs = defaultdict(list)
        for (s, r), cs in sorted(rows.items()):
            cs = sorted(set(cs))
            start = last = cs[0]
            for c in cs[1:] + [cs[-1]+2]:
                if c != last + 1:
                    runs[(s, start, last)].append(r)
                    start = c
                last = c
        result = []
        for (s, c1, c2), rs in sorted(runs.items()):
            start = last = rs[0]
            for r in rs[1:] + [rs[-1]+2]:
                if r != last + 1:
                    a,b,c,d = (c1,start,c2,last) if transpose else (start,c1,last,c2)
                    result.append({"kind":"RECTANGLE", "sheet_id":f"sheet:{s}", "r1":a,"c1":b,"r2":c,"c2":d})
                    start = r
                last = r
        options.append(result)
    return min(options, key=lambda x:(len(x),json.dumps(x,sort_keys=True)))


def witness(ids, world):
    """Exact safe cover, with occupancy/bounding candidates. Not an optimality proof."""
    candidates = []
    regions = rectangle_cover(ids)
    bysheet, byrow, bycol = defaultdict(set), defaultdict(set), defaultdict(set)
    for cid in ids:
        s,r,c = coord(cid)
        bysheet[s].add(cid);byrow[(s,r)].add(cid);bycol[(s,c)].add(cid)
    for cells in [*bysheet.values(),*byrow.values(),*bycol.values()]:
        positions = [coord(c) for c in cells]
        regions.append({"kind":"RECTANGLE","sheet_id":f"sheet:{positions[0][0]}","r1":min(p[1] for p in positions),"r2":max(p[1] for p in positions),"c1":min(p[2] for p in positions),"c2":max(p[2] for p in positions)})
    for region in regions:
        try:
            full = world.expression(region)
        except PlanError:
            continue
        for filt in (None,"BLANK_ONLY","NONBLANK_ONLY","FORMULA_ONLY","NONFORMULA_ONLY"):
            covered = world.filter(full, filt)
            if covered and covered <= ids:
                candidates.append((region, filt, covered))
    remaining = set(ids)
    groups = defaultdict(list)
    while remaining:
        choices = [(len(c & remaining), -tokens(r), r, f, c) for r,f,c in candidates if c & remaining]
        if not choices:
            break
        _,_,r,f,c = max(choices,key=lambda x:(x[0],x[1],json.dumps(x[2],sort_keys=True),str(x[3])))
        groups[f].append(r)
        remaining -= c
    operations = []
    for i,(f,rs) in enumerate(sorted(groups.items(),key=lambda x:str(x[0]))):
        op = {"operation_id":f"op{i+1}","obligation_id":"EVALUATOR_WITNESS_ONLY","operation_kind":"SET_FORMULA","target_set":rs[0] if len(rs)==1 else {"kind":"UNION","sets":rs}}
        if f: op["occupancy_filter"] = f
        operations.append(op)
    return {"operations":operations}, remaining


def phase_a():
    rows = []
    for taskrow in old.load(POP)["rows"]:
        task = taskrow["task"]
        w = World(old.relational.db_path(task))
        gold = gold_ids(task,w)
        plan, missing = witness(gold,w)
        expansion = expand_edit_plan(plan,w)
        found = set(expansion["cell_ids"])
        size, enum = tokens(plan), tokens(sorted(gold))
        clauses = sum(len(o["target_set"].get("sets",[o["target_set"]])) for o in plan["operations"])
        row = {"task":task,"gold_target_count":len(gold),"represented_target_count":len(found & gold),"false_target_count":len(found-gold),"target_recall":len(found & gold)/len(gold),"target_precision":len(found & gold)/len(found) if found else 0,"exact_set_match":found==gold,"operation_count":len(plan["operations"]),"clause_count":clauses,"exception_count":0,"plan_tokens":size,"enumeration_tokens":enum,"compression_ratio":enum/size,"counterexamples":sorted(missing)}
        save(f"phase_a/{task}.json",{"metrics":row,"gold_plan_evaluator_only":plan,"expansion":expansion})
        rows.append(row); w.close()
    recall = sum(r["represented_target_count"] for r in rows)/sum(r["gold_target_count"] for r in rows)
    exact = sum(r["exact_set_match"] for r in rows)/len(rows)
    result = {"rows":rows,"micro_recall":recall,"micro_precision":sum(r["represented_target_count"] for r in rows)/sum(r["represented_target_count"]+r["false_target_count"] for r in rows),"task_exact_rate":exact,"median_compression_ratio":statistics.median(r["compression_ratio"] for r in rows),"p95_plan_tokens":sorted(r["plan_tokens"] for r in rows)[-1],"gate_pass":recall>=.95 and exact>=.9,"language_version":"EDIT_PLAN_V1","earned_revisions":[],"search_limitation":"Constructive exact witnesses, greedy clause reduction; no minimum-clause optimality claim. CELL/rectangle algebra can trivially encode finite sets, so compactness is essential evidence."}
    save("phase_a.json",result);save("edit_plan_schema.json",SCHEMA)
    save("counterexample_ledger.json",{"version":"EDIT_PLAN_V1","misses":[{"task":r["task"],"cells":r["counterexamples"]} for r in rows if r["counterexamples"]],"earned_primitives":[],"scope":"Formula-producing target sets only; value-setting operations remain outside frozen actuator scope."})
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2),flush=True)


def compact_table(records):
    if not records: return {"columns":[],"rows":[]}
    columns=sorted({k for r in records for k in r})
    return {"columns":columns,"rows":[[r.get(k) for k in columns] for r in records]}


def plan_context(task,compiler,packets,w):
    # Lossless table encoding, no top-k or semantic retrieval additions.
    grounding={}
    for oid,packet in packets.items():
        grounding[oid]={k:compact_table(packet.get(k,[])) for k in ("locus","subject","scope","source")}
        ids={old.hybrid.canonical_id(c) if hasattr(old.hybrid,'canonical_id') else c for c in packet.get('target_cell_ids',[])}
        from workbook_spine_sqlite import canonical_cell_id
        ids={canonical_cell_id(c) for c in ids if canonical_cell_id(c)}
        grounding[oid]['target_candidate_rectangles']=rectangle_cover(ids)
        grounding[oid]['candidate_count']=len(ids)
        grounding[oid]['fields']=packet.get('fields')
    return {"RAW_TASK":compiler['raw_task'],"GENERATED_TASK_IR":{'obligations':compiler['obligations']},"SHEETS":compact_table(list(w.sheets.values())),"GROUNDING":grounding,
            "NOTE":"Grounding candidate regions are evidence, not a whitelist. Specify task-supported coordinates within compiled sheet bounds. All candidate records retained; tables are lossless serialization."}


def freeze():
    a=old.load(OUT/'phase_a.json')
    if not a['gate_pass']:raise RuntimeError('Phase A gate failed')
    if (OUT/'freeze.json').exists():raise RuntimeError('Already frozen')
    save('population.json',old.load(POP));save('edit_plan_prompt.txt',PLAN_PROMPT)
    save('edit_plan_contract.md',CONTRACT.read_text())
    paths=[Path(__file__),Path(__file__).with_name('edit_plan.py'),CONTRACT,Path(old.__file__),*map(lambda p:old.ROOT/p,old.load(old.OUT/'freeze.json')['component_sha256'])]
    freeze_data={'limits':LIMITS,'sha256':{str(p.relative_to(old.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'population_sha256':hashlib.sha256(POP.read_bytes()).hexdigest(),'plan_prompt_sha256':hashlib.sha256(PLAN_PROMPT.encode()).hexdigest(),
        'prior_compiler_reuse':'Reuse every preserved parse-valid original composition compiler output; compile once otherwise. No oracle context.',
        'target_gate':'All 18 attempted; micro recall >= 10%, precision >= 10% (material versus .24%/7.3%). Strong generation gate remains >=75% recall.',
        'downstream_selection':'Before synthesis: mandatory task IDs first, then population order; round-robin up to 2 distinct target cells/task, 24 total. Operation order, each first/last address (sheet index,row,col). No evaluator gold used.',
        'execution_mode':'PER_CELL_SYNTHESIS unless a generated FILL_FORMULA rectangle has a fully occupied single input fingerprint class with mechanically equal translated formulas. Blank heterogeneous regions cannot establish homogeneity; no gold grouping.',
        'resource_policy':'At most 24 target sessions; stop starting new sessions after 3M measured downstream input tokens. In-flight session completes; all other cells explicitly censored. No retries; provider failures excluded.',
        'frozen_downstream':'Direct reuse of old.run_target and old.validate_and_apply; no prompt changes.',
        'caveats':['Grounding metric inherited from old run can pass on sheet retention alone.','Formula target ceiling does not imply representability of required literal value edits.','Old downstream protocol replaces chat state with deterministic summaries and materializes evidence at transition; reused exactly for matching.']}
    save('freeze.json',freeze_data)
    print('Frozen',flush=True)


def check_freeze():
    f=old.load(OUT/'freeze.json')
    for name,digest in f['sha256'].items():
        # Reporting/orchestration may be extended; representation and all prior
        # components are byte-frozen before calls.
        if name==str(Path(__file__).relative_to(old.ROOT)):continue
        if hashlib.sha256((old.ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError(f'Frozen component changed: {name}')
    if hashlib.sha256(PLAN_PROMPT.encode()).hexdigest()!=f['plan_prompt_sha256']:raise RuntimeError('Prompt changed')
    old.guard(LIMITS['model'])


def phase_b_task(taskrow,key):
    task=taskrow['task'];dest=OUT/f'phase_b/{task}.json'
    if dest.exists():return old.load(dest)
    start=time.perf_counter();prior=old.all_runs().get(task,{})
    reused=bool(prior.get('compiler',{}).get('parse_valid'))
    checkpoint=OUT/f'compiler/{task}.json'
    if checkpoint.exists():
        saved=old.load(checkpoint);compiler=saved['compiler'];reused=saved['reused_prior']
    else:
        compiler=prior['compiler'] if reused else old.compile_task(old.task_map()[task],key)
    save(f'compiler/{task}.json',{'reused_prior':reused,'compiler':compiler})
    if not compiler.get('response',{}).get('http_ok'):
        row={'task':task,'status':'MODEL_ACCESS_FAILURE','compiler_reused':reused,'compiler':compiler}
        save(f'phase_b/{task}.json',row);return row
    spine=old._load_spine(task);w=World(old.relational.db_path(task))
    obs=compiler['obligations'];packets={ob['id']:old.project_obligation(spine,ob) for ob in obs}
    context=plan_context(task,compiler,packets,w)
    save(f'contexts/{task}.json',context)
    response=old.call_glm(key,PLAN_PROMPT,json.dumps(context,ensure_ascii=False,separators=(',',':')),'librecalc-edit-plan-generation',LIMITS['plan_output_tokens'])
    parsed=old.extract_json_object(response.get('text','')) if response.get('http_ok') else None
    expansion=None;error=None
    if not response.get('http_ok'):status='MODEL_ACCESS_FAILURE'
    elif parsed is None:status='INVALID_SCHEMA'
    else:
        try:
            expansion=expand_edit_plan(parsed,w,{o['id'] for o in obs});status=expansion['status']
        except PlanError as exc:
            status=exc.category;error=str(exc)
    gold=gold_ids(task,w);found=set(expansion['cell_ids']) if expansion else set()
    evaluation=old.task_ir_eval(task,obs,compiler['raw_task'])
    row={'task':task,'status':status,'error':error,'compiler_reused':reused,'compiler':compiler,'compiler_eval':evaluation,'grounding':{'packets':packets,'evaluation':old.grounding_eval(task,obs,packets,spine)},'response':response,'parsed':parsed,'expansion':expansion,
        'metrics':{'gold_count':len(gold),'expanded_count':len(found),'true_targets':len(found&gold),'false_targets':len(found-gold),'missed_targets':len(gold-found),'precision':len(found&gold)/len(found) if found else 0,'recall':len(found&gold)/len(gold),'plan_tokens':tokens(parsed) if parsed else None,'context_tokens_estimate':tokens(context),'enumeration_tokens':tokens(sorted(found))},'elapsed_s':time.perf_counter()-start}
    save(f'phase_b/{task}.json',row);w.close()
    print(json.dumps({'task':task,'status':status,**row['metrics']}),flush=True)
    return row


def phase_b():
    check_freeze();old.load_dotenv();key=os.environ['OPENROUTER_API_KEY']
    with concurrent.futures.ThreadPoolExecutor(max_workers=LIMITS['workers']) as pool:
        futures={pool.submit(phase_b_task,r,key):r['task'] for r in old.load(POP)['rows']}
        for f in concurrent.futures.as_completed(futures):
            # Persist implementation exceptions separately; no automatic retry.
            try:f.result()
            except Exception as exc:
                task=futures[f];save(f'phase_b/{task}.json',{'task':task,'status':'INTEGRATION_FAILURE','error':f'{type(exc).__name__}: {exc}'})
                print(task,type(exc).__name__,str(exc),flush=True)
    frontend_report()


def frontend_report():
    rows=[old.load(p) for p in sorted((OUT/'phase_b').glob('*.json'))]
    quality=[r for r in rows if r['status'] not in ('MODEL_ACCESS_FAILURE','INTEGRATION_FAILURE')]
    m=[r['metrics'] for r in quality]
    ntrue=sum(x['true_targets'] for x in m);ngold=sum(x['gold_count'] for x in m);nfound=sum(x['expanded_count'] for x in m)
    precision=ntrue/nfound if nfound else 0;recall=ntrue/ngold if ngold else 0
    prior=old.all_runs();matched=[r for r in quality if prior.get(r['task'],{}).get('compiler')]
    matched_counts=Counter()
    for r in matched:
        w=World(old.relational.db_path(r['task']));g=gold_ids(r['task'],w);w.close()
        previous={t['cell_id'] for t in prior[r['task']].get('targets',[])}
        matched_counts.update({'old_found':len(previous),'old_true':len(previous&g),'gold':len(g),'new_found':r['metrics']['expanded_count'],'new_true':r['metrics']['true_targets']})
    report={'attempted_tasks':len(rows),'quality_tasks':len(quality),'status_counts':dict(Counter(r['status'] for r in rows)),'micro_precision':precision,'micro_recall':recall,'true_targets':ntrue,'expanded_targets':nfound,'gold_targets':ngold,
        'valid_plan_rate':sum(r['status'] in ('VALID_PLAN','EMPTY_EXPANSION') for r in quality)/len(quality) if quality else None,'parse_rate':sum(r.get('parsed') is not None for r in quality)/len(quality) if quality else None,
        'matched_previous_valid_tasks':len(matched),'matched_counts':dict(matched_counts),'gate_b1_pass':len(rows)==18 and precision>=LIMITS['target_gate_micro_precision'] and recall>=LIMITS['target_gate_micro_recall'],
        'rows':[{'task':r['task'],'status':r['status'],**r.get('metrics',{})} for r in rows]}
    save('frontend_report.json',report);print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2),flush=True)
    return report


def execution_groups(row,w):
    """Conservative reuse: only demonstrably identical input programs may fill."""
    from openpyxl.formula.translate import Translator
    forms={r['cell_id']:dict(r) for r in w.db.execute('SELECT * FROM formulas')}
    result=[];claimed=set()
    for op in row['expansion']['operations']:
        ids=sorted(set(op['cell_ids'])-claimed,key=coord);claimed.update(ids)
        if not ids:continue
        homogeneous=False
        if op['operation_kind']=='FILL_FORMULA' and all(c in forms for c in ids):
            fp={forms[c]['fingerprint_id'] for c in ids}
            if len(fp)==1 and None not in fp and not any(forms[c]['opaque'] for c in ids):
                seed=ids[0];homogeneous=True
                for cid in ids:
                    try:
                        translated=Translator(forms[seed]['formula_text'],origin=w.cells[seed]['address']).translate_formula(w.cells[cid]['address'])
                        homogeneous &= old.synth_tools._canonical_formula(translated)==old.synth_tools._canonical_formula(forms[cid]['formula_text'])
                    except Exception:homogeneous=False
        result.append({**op,'cell_ids':ids,'mode':'SYNTHESIZE_ONCE_TRANSLATE' if homogeneous else 'PER_CELL_SYNTHESIS','homogeneity_evidence':'All input members share fingerprint and exact mechanical translation' if homogeneous else 'No complete input-program proof; blank or heterogeneous region not assumed homogeneous'})
    return result


def select_downstream():
    if (OUT/'downstream_selection.json').exists():return old.load(OUT/'downstream_selection.json')
    front=old.load(OUT/'frontend_report.json')
    if not front['gate_b1_pass']:raise RuntimeError('Gate B1 failed: no synthesis authorized by experiment')
    pop=old.load(POP)['rows'];order=[r['task'] for r in pop if r['task'] in old.KNOWN_TASKS]+[r['task'] for r in pop if r['task'] not in old.KNOWN_TASKS]
    candidates={};audits={}
    for task in order:
        r=old.load(OUT/f'phase_b/{task}.json')
        if not r.get('expansion'):continue
        w=World(old.relational.db_path(task));groups=execution_groups(r,w);w.close();audits[task]=groups
        queue=[]
        for endpoint in (0,-1):
            for op in groups:
                if op['operation_kind']=='CLEAR_CELL':continue
                cid=op['cell_ids'][endpoint]
                if any(x['cell_id']==cid for x in queue):continue
                if endpoint==-1 and op['mode']=='SYNTHESIZE_ONCE_TRANSLATE':continue
                queue.append({'task':task,'cell_id':cid,'obligation_id':op['obligation_id'],'operation_id':op['operation_id'],'mode':op['mode'],'execution_cell_ids':op['cell_ids'] if op['mode']=='SYNTHESIZE_ONCE_TRANSLATE' else [cid],'selection_reason':'operation-first/last-address round robin; evaluator blind'})
        candidates[task]=queue[:LIMITS['per_task_sessions']]
    selected=[]
    for i in range(LIMITS['per_task_sessions']):
        for task in order:
            if i<len(candidates.get(task,[])) and len(selected)<LIMITS['downstream_sessions']:
                selected.append(candidates[task][i])
    for i,x in enumerate(selected):x['session_id']=f'session{i+1:02d}'
    censored={}
    for task,groups in audits.items():
        allids={cid for op in groups for cid in op['cell_ids']}
        executed={cid for x in selected if x['task']==task for cid in x['execution_cell_ids']}
        censored[task]=sorted(allids-executed,key=coord)
    data={'selected':selected,'execution_audit':audits,'censored_target_ids':censored,'gold_used_for_selection':False}
    save('downstream_selection.json',data)
    save('downstream_freeze.json',{'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'selection_sha256':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),'original_workbook_sha256':{t:hashlib.sha256(old.synth_tools._input_path(t).read_bytes()).hexdigest() for t in order},'limits':LIMITS})
    return data


def downstream_session(job,key):
    path=OUT/f"sessions/{job['session_id']}.json"
    if path.exists():return old.load(path)
    task=job['task'];r=old.load(OUT/f'phase_b/{task}.json');spine=old._load_spine(task)
    ob=next(o for o in r['compiler']['obligations'] if o['id']==job['obligation_id'])
    target=old.target_address(spine,job['cell_id']);info=old.input_cell_info(task,target['sheet'],target['address'])
    target.update({'target_id':job['cell_id'],'current_input_content':info['raw_value'],'current_input_kind':info['kind']})
    start=time.perf_counter()
    try:
        session=old.run_target(task,r['compiler']['raw_task'],ob,target,r['grounding']['packets'][ob['id']],spine,key)
    except Exception as exc:
        session={'status':'INTEGRATION_FAILURE','error':f'{type(exc).__name__}: {exc}','target':target}
    session['job']=job;session['wall_seconds']=time.perf_counter()-start
    save(f"sessions/{job['session_id']}.json",session)
    print(json.dumps({'session':job['session_id'],'task':task,'target':target['address'],'status':session['status'],'proposal':session.get('synthesis',{}).get('parsed'),'input_tokens':session.get('retrieval_input_tokens',0)+session.get('synthesis_input_tokens',0)}),flush=True)
    return session


def downstream():
    check_freeze();selection=select_downstream();old.load_dotenv();key=os.environ['OPENROUTER_API_KEY']
    # Small batches bound in-flight spend; each completed episode is durable.
    spent=sum(old.load(p).get('retrieval_input_tokens',0)+old.load(p).get('synthesis_input_tokens',0) for p in (OUT/'sessions').glob('*.json')) if (OUT/'sessions').exists() else 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[j for j in selection['selected'] if not (OUT/f"sessions/{j['session_id']}.json").exists()]
        for i in range(0,len(jobs),2):
            if spent>=LIMITS['total_downstream_input_soft_cap']:
                for job in jobs[i:]:save(f"sessions/{job['session_id']}.json",{'job':job,'status':'RESOURCE_CENSORED_NOT_RUN'})
                break
            futures=[pool.submit(downstream_session,j,key) for j in jobs[i:i+2]]
            for f in futures:
                r=f.result();spent+=r.get('retrieval_input_tokens',0)+r.get('synthesis_input_tokens',0)
    actuate()


def actuate():
    from openpyxl.formula.translate import Translator
    grouped=defaultdict(list)
    for p in sorted((OUT/'sessions').glob('*.json')):
        r=old.load(p);grouped[r['job']['task']].append(r)
    for task,sessions in grouped.items():
        if (OUT/f'actuation/{task}.json').exists():continue
        wb=old.openpyxl.load_workbook(old.synth_tools._input_path(task),data_only=False)
        spine=old._load_spine(task);cache={};writes=[]
        for session in sessions:
            parsed=session.get('synthesis',{}).get('parsed') or {}
            formula=parsed.get('formula') if parsed.get('status')=='PROPOSED' else None
            if formula and parsed.get('target_id')!=session['job']['cell_id']:
                writes.append({'session_id':session['job']['session_id'],'status':'INVALID_TARGET_ID','applied':False});continue
            if not isinstance(formula,str) or not formula.startswith('='):continue
            for cid in session['job']['execution_cell_ids']:
                target=old.target_address(spine,cid)
                translated=formula
                if cid!=session['job']['cell_id']:
                    translated=Translator(formula,origin=session['target']['address']).translate_formula(target['address'])
                validation=old.validate_and_apply(task,target,translated,cache,wb)
                writes.append({'session_id':session['job']['session_id'],'target':target,'formula':translated,**validation})
        output=OUT/f'scoring/Financial_Model-{task}/output.xlsx';output.parent.mkdir(parents=True,exist_ok=True)
        wb.save(output);wb.close()
        save(f'actuation/{task}.json',{'task':task,'writes':writes,'output':str(output),'bounded_partial_workbook':True})


def score():
    """Normal benchmark scoring path on the bounded partial workbooks. Not a model call."""
    import subprocess,sys
    run_root=OUT/'scoring'
    if not run_root.is_dir():raise SystemExit('no actuated workbooks to score')
    command=[sys.executable,str(old.ROOT/'benchmark/score_openrouter_run.py'),str(run_root),'--model-name','edit-plan-glm-5.3-flash','--metadata-tolerant']
    subprocess.run(command,cwd=old.ROOT/'benchmark-data/SpreadsheetBench-2/evaluation',check=False)


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=["phase-a","freeze","phase-b","frontend-report","select-downstream","downstream","actuate","score"])
    args=parser.parse_args()
    {'phase-a':phase_a,'freeze':freeze,'phase-b':phase_b,'frontend-report':frontend_report,'select-downstream':select_downstream,'downstream':downstream,'actuate':actuate,'score':score}[args.command]()
