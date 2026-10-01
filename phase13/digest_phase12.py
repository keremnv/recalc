#!/usr/bin/env python3
"""Phase13: digest phase12 CONTROL runs (ordinary population A) into readable files."""
import json, glob, os

OUT = 'phase13/working/digests'
os.makedirs(OUT, exist_ok=True)

scorer = {}
for line in open('phase12/ledgers/scorer_outcome.jsonl'):
    r = json.loads(line)
    if r['arm'] == 'CONTROL':
        scorer[(r['pop'], r['task_id'])] = r

# recalc-normalized V1 for submitted phase12 finals
rep = {}
try:
    for line in open('phase12r/PHASE12_REPLICATION.jsonl'):
        r = json.loads(line)
        rep[r.get('run', '')] = r
except FileNotFoundError:
    pass

def head(s, n=500):
    s = s if isinstance(s, str) else json.dumps(s)
    s = s.replace('\n', ' ')
    return s[:n] + ('...' if len(s) > n else '')

index = []
for d in sorted(glob.glob('phase12/runs/*/')):
    pop = d.rstrip('/').split('/')[-1]
    for rd in sorted(glob.glob(d + '*_CONTROL')):
        name = os.path.basename(rd)
        # name like Debugging_01_01_CONTROL / Financial_Model_03_02_CONTROL
        parts = name[:-len('_CONTROL')]
        for cat in ('Financial_Model', 'Debugging', 'Template'):
            if parts.startswith(cat + '_'):
                task = parts[len(cat) + 1:]
                break
        task_id = f'{cat}:{task}'
        rr = json.load(open(rd + '/run_record.json'))
        sc = scorer.get((pop, task_id), {})
        lines = []
        lines.append(f'# {pop} {task_id} CONTROL')
        lines.append(f'run_status={rr.get("status")} output_produced={rr.get("output_produced")} model={rr.get("model")}')
        lines.append(f'efficiency={json.dumps(rr.get("efficiency", {}))}')
        lines.append(f'behavior={json.dumps(rr.get("behavior", {}))}')
        lines.append(f'scores: exact={sc.get("official_exact")} mod={sc.get("official_modification")} reg={sc.get("official_regression")} err={sc.get("eval_error")}')
        # replication V1 match
        for k, v in rep.items():
            if task_id.replace(':', '_') in k and 'CONTROL' in k:
                lines.append(f'V1recalc: class={v.get("class")} V0={v.get("V0_exact")}/{v.get("V0_mod")}/{v.get("V0_reg")} V1={v.get("V1_exact")}/{v.get("V1_mod")}/{v.get("V1_reg")} cache_changed={v.get("cache_changed")}')
        lines.append('')
        # compact trajectory
        lines.append('## tool sequence')
        try:
            for line in open(rd + '/trajectory.jsonl'):
                t = json.loads(line)
                if 'error' in t:
                    lines.append(f"  call{t.get('call')} ERROR {head(t['error'],200)}")
                else:
                    lines.append(f"  call{t.get('call')} {t.get('tool')} repair={t.get('repair_mode')} finish={t.get('finish_reason')} cost={t.get('cost')}")
        except FileNotFoundError:
            lines.append('  (no trajectory.jsonl)')
        lines.append('')
        lines.append('## transcript turns')
        try:
            n = 0
            for line in open(rd + '/transcript_full.jsonl'):
                o = json.loads(line)
                role = o.get('role')
                c = o.get('content', '')
                if role == 'system':
                    continue
                n += 1
                if role == 'user' and n <= 3:
                    lines.append(f'--- user msg {n}: {head(c, 800)}')
                elif role == 'assistant':
                    # tool calls?
                    tcs = o.get('tool_calls')
                    txt = head(c if isinstance(c, str) else json.dumps(c), 600)
                    lines.append(f'--- assistant: {txt}')
                    if tcs:
                        for tc in (tcs if isinstance(tcs, list) else [tcs]):
                            fn = (tc.get('function') or {}).get('name', tc.get('name', '?'))
                            args = (tc.get('function') or {}).get('arguments', '')
                            lines.append(f'    TOOL {fn} {head(args, 700)}')
                elif role == 'tool':
                    lines.append(f'    OBS ({len(c) if isinstance(c,str) else 0} chars): {head(c, 400)}')
                else:
                    lines.append(f'--- {role}: {head(c, 300)}')
        except FileNotFoundError:
            lines.append('(no transcript_full.jsonl)')
        out = f'{OUT}/{pop}_{task_id.replace(":","_")}_CONTROL.md'
        open(out, 'w').write('\n'.join(lines))
        index.append({'pop': pop, 'task': task_id, 'digest': out,
                      'status': rr.get('status'), 'output': rr.get('output_produced'),
                      'exact': sc.get('official_exact'), 'mod': sc.get('official_modification'),
                      'reg': sc.get('official_regression')})
json.dump(index, open('phase13/working/popA_index.json', 'w'), indent=1)
print(f'{len(index)} digests')
for i in index:
    print(i['pop'], i['task'], i['status'], 'out' if i['output'] else 'noout', f"exact={i['exact']} mod={i['mod']}")
