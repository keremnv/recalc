#!/usr/bin/env python3
"""Digest swe-agent .traj files into compact action sketches."""
import json, sys, os

def digest(traj_path, out_path):
    t = json.load(open(traj_path))
    tr = t.get('trajectory', [])
    info = t.get('info', {})
    lines = [f'# {traj_path}', f"exit={info.get('exit_status')} submission={str(info.get('submission'))[:120]}",
             'model_stats=' + json.dumps(info.get('model_stats', {}), default=str)[:400]]
    for i, e in enumerate(tr, 1):
        a = (e.get('action') or '').replace('\n', ' ')
        o = (e.get('observation') or '')
        th = (e.get('thought') or e.get('response') or '').replace('\n', ' ')[:200]
        flag = ' ERR' if any(k in o for k in ('Error', 'Traceback', 'TraceBack')) else ''
        lines.append(f'--- step{i}: ACT {a[:500]}')
        if th.strip():
            lines.append(f'    THINK: {th}')
        lines.append(f'    OBS{flag} ({len(o)}ch): {o.replace(chr(10)," ")[:350]}')
    open(out_path, 'w').write('\n'.join(lines))
    print(out_path, len(lines), 'lines')

if __name__ == '__main__':
    os.makedirs('research/history/phase13/working/traj', exist_ok=True)
    for p in sys.argv[1:]:
        tag = p.replace('benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/', '').replace('/', '__')
        digest(p, f'research/history/phase13/working/traj/{tag}.md')
