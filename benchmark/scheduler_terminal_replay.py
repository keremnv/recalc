"""Read-only 04_01 scheduler replay: stored responses only, no workbook writes.

The existing scheduler, group builder, and verifier are reused. Missing responses
are recorded as REPLAY_NO_STORED_RESPONSE, never supplied invented formulas.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import compiled_scheduler
import matched_compiled_treatment as m


def replay(task_dir: Path) -> dict:
    task_dir = task_dir.resolve()
    files = [p for p in task_dir.rglob('*') if p.is_file()]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    result = json.loads((task_dir / 'result.json').read_text())
    archived_state = json.loads((task_dir / 'state.json').read_text())
    key = result['task_id']
    plan = copy.deepcopy(result['edit_plan'])
    archived = result['schedule']
    state = {'replay_stored_sessions_only': True, 'model_call_count': 0, 'provider_cost_usd': 0,
             'scheduler_v3': {'sessions': {p['target']['cell_id']: copy.deepcopy(p) for p in archived['canonical_decisions']},
                              'edits': {}, 'dispositions': {}, 'units': [], 'failures': []}}
    runtime = SimpleNamespace(**{name: getattr(m, name) for name in dir(m) if not name.startswith('__')})
    runtime.write_json = lambda *a, **kw: None
    def no_inference(*args, **kwargs):
        raise AssertionError('ZERO_MODEL_REPLAY forbids inference')
    runtime.retrieval_synthesis = no_inference
    scheduled = compiled_scheduler.schedule(runtime, key, {}, result['compiler'], plan, state, task_dir)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert before == after
    assert sorted(str(p) for p in task_dir.rglob('*') if p.is_file()) == sorted(before)
    meta, cids = m.authorised_cells(plan)
    groups = scheduled['eligible_program_groups']
    canonicals = {tuple(g['canonical_cell']) for g in groups}
    members = {tuple(c) for g in groups for c in g['member_cells']}
    independent = canonicals | (set(meta) - members)
    disposed = set(scheduled['dispositions'])
    assert {cids[c] for c in independent} <= disposed
    assert len(scheduled['canonical_decisions']) == len(archived['canonical_decisions'])
    assert groups == archived['eligible_program_groups']
    assert {tuple(p['seed']) for p in scheduled['canonical_decisions']} <= independent
    outcome = {
        'task': key, 'model_calls': 0, 'workbook_writes': 0,
        'archived_directory': str(task_dir), 'archived_evidence_unchanged': before == after,
        'archive_sha256': before, 'authority_count': len(meta),
        'program_groups_unchanged': groups == archived['eligible_program_groups'],
        'independent_units': len(independent),
        'retained_sessions': len(scheduled['canonical_decisions']),
        'previous_dispositions': len(archived['dispositions']), 'current_dispositions': len(disposed),
        'previous_unresolved_targets': len(archived['unresolved_authorised_targets']),
        'current_unresolved_targets': len(scheduled['unresolved_authorised_targets']),
        'disposition_counts': dict(Counter(r['status'] for r in scheduled['dispositions'].values())),
        'newly_exposed_units': sorted(disposed - set(archived['dispositions'])),
        'failed_group_members_not_promoted': not bool((disposed - set(archived['dispositions'])) & {cids[c] for c in members - canonicals}),
        'scheduled_edits': scheduled['edits'],
        'scheduled_edits_equal_archive': scheduled['edits'] == archived_state.get('completed_edits', []),
        'planning_completeness': m.planning_completeness(result['compiler'], plan),
        'interpretation': 'Coverage replay only. Exposed units lacking saved responses are not actual model attempts or solved cells.',
    }
    return outcome


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_dir', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve().is_relative_to(args.task_dir.resolve()):
        parser.error('Report must be outside the immutable task archive')
    outcome = replay(args.task_dir)
    args.report.write_text(json.dumps(outcome, indent=2) + '\n')
    print(json.dumps({k: v for k, v in outcome.items() if k not in {'archive_sha256', 'scheduled_edits', 'newly_exposed_units', 'planning_completeness'}}, indent=2))
