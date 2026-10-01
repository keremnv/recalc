"""Terminal work must release independent work without splitting failed groups."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import compiled_scheduler
import matched_compiled_treatment as m
import pytest
from test_integration_repairs import fixture_runtime, run


def test_archived_fm_04_01_exhausts_independent_units_after_three_provider_failures(tmp_path):
    fixture = json.loads((Path(__file__).parent / 'fixtures/fm_04_01_scheduler.json').read_text())
    meta = {tuple(a['cell']): a for a in fixture['authority']}
    cids = {c: a['cell_id'] for c, a in meta.items()}
    runtime, _, calls = fixture_runtime(tmp_path, groups=fixture['groups'])
    runtime.authorised_cells = lambda p: (meta, cids)
    runtime.retrieval_synthesis = lambda *a, **k: pytest.fail('Mechanical replay cannot infer')
    state = {'replay_stored_sessions_only': True, 'scheduler_v3': {
        'sessions': {p['target']['cell_id']: p for p in fixture['stored_sessions']},
        'edits': {}, 'dispositions': {}, 'units': [], 'failures': [],
    }}
    obligations = sorted({a['obligation_id'] for a in meta.values()})
    plan = {'expansion': {'operations': fixture['operations']}, 'packets': {o: {} for o in obligations}}
    result = compiled_scheduler.schedule(runtime, 'Financial_Model:04_01', {},
        {'obligations': [{'id': o} for o in obligations]}, plan, state, tmp_path)
    canonicals = {tuple(g['canonical_cell']) for g in fixture['groups']}
    members = {tuple(c) for g in fixture['groups'] for c in g['member_cells']}
    independent = canonicals | (set(meta) - members)
    assert set(result['dispositions']) == {cids[c] for c in independent}
    assert {tuple(p['seed']) for p in result['canonical_decisions']} == {tuple(p['seed']) for p in fixture['stored_sessions']}
    assert result['dispositions']['cell:s03:r6:c4']['status'] == 'PROVIDER_TIMEOUT'
    assert result['dispositions']['cell:s02:r141:c11']['status'] == 'PROVIDER_TIMEOUT'
    assert result['dispositions']['cell:s05:r12:c5']['status'] == 'SESSION_RESOURCE_LIMIT'
    assert result['dispositions']['cell:s05:r12:c6']['status'] == 'REPLAY_NO_STORED_RESPONSE'
    assert set(result['unresolved_authorised_targets']) == {cids[c] for c in members - canonicals}
    assert result['edits'] == []
    assert calls == []


@pytest.mark.parametrize(('parsed', 'failure', 'expected'), [
    ({'status': 'ABSTAIN', 'formula': None}, None, 'ABSTAIN'),
    (None, 'PROVIDER_TIMEOUT', 'PROVIDER_TIMEOUT'),
    (None, 'MODEL_ACCESS_FAILURE', 'MODEL_ACCESS_FAILURE'),
    (None, 'SESSION_RESOURCE_LIMIT', 'SESSION_RESOURCE_LIMIT'),
    ({'status': 'PROPOSED', 'formula': None}, None, 'INVALID_RESPONSE'),
    (['unexpected', 'array'], None, 'INVALID_RESPONSE'),
    ({'status': 'PROPOSED', 'formula': 123}, None, 'INVALID_RESPONSE'),
])
def test_unsuccessful_residual_allows_later_independent_writes(tmp_path, parsed, failure, expected):
    runtime, _, calls = fixture_runtime(tmp_path)
    original = runtime.retrieval_synthesis
    def synth(*args, **kwargs):
        result = original(*args, **kwargs)
        if len(calls) == 1:
            return {'synthesis': {'parsed': parsed}, 'failure_class': failure}
        return result
    runtime.retrieval_synthesis = synth
    result = run(runtime, tmp_path)
    assert calls == ['cell:s00:r10:c3', 'cell:s00:r10:c4', 'cell:s00:r10:c5']
    assert result['dispositions'][calls[0]]['status'] == expected
    assert [f['failure_class'] for f in result['failures']] == ([] if expected == 'ABSTAIN' else [expected])
    assert {e['address'] for e in result['edits']} == {'D10', 'E10'}


@pytest.mark.parametrize('first_exit', ['HARD_REJECT', 'INVALID_ENTITY', 'CLEAR_CELL'])
def test_other_terminal_paths_release_independent_work(tmp_path, first_exit):
    runtime, _, calls = fixture_runtime(tmp_path)
    if first_exit == 'HARD_REJECT':
        runtime.validate_formula = lambda *a: {'hard_verifier_result': 'HARD_REJECT' if len(calls) == 1 else 'HARD_ACCEPT'}
    elif first_exit == 'INVALID_ENTITY':
        target = runtime.target_from_id
        runtime.target_from_id = lambda sp, cid, k, oid: None if cid.endswith('c3') else target(sp, cid, k, oid)
    else:
        meta, cids = runtime.authorised_cells({})
        meta[('S', 10, 3)]['operation_kind'] = 'CLEAR_CELL'
        runtime.authorised_cells = lambda p: (meta, cids)
    result = run(runtime, tmp_path)
    assert {e['address'] for e in result['edits']} == {'D10', 'E10'}
    assert calls[-2:] == ['cell:s00:r10:c4', 'cell:s00:r10:c5']


def test_replay_misses_are_terminal_and_do_not_starve_later_units(tmp_path):
    runtime, _, calls = fixture_runtime(tmp_path)
    result = run(runtime, tmp_path, {'replay_stored_sessions_only': True})
    assert len(result['dispositions']) == 3
    assert {r['status'] for r in result['dispositions'].values()} == {'REPLAY_NO_STORED_RESPONSE'}
    assert calls == []


def test_failed_group_members_not_promoted_by_later_dependency_or_resume(tmp_path):
    group = {'canonical_cell': ['S', 10, 3], 'member_cells': [['S', 10, 3], ['S', 10, 4]]}
    runtime, _, calls = fixture_runtime(tmp_path, groups=[group], precedents=[('S', 10, 4)])
    original = runtime.retrieval_synthesis
    def synth(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[3]['cell_id'].endswith('c3'):
            return {'synthesis': {'parsed': None}, 'failure_class': 'PROVIDER_TIMEOUT'}
        return result
    runtime.retrieval_synthesis = synth
    first = run(runtime, tmp_path)
    state = json.loads((tmp_path / 'state.json').read_text())
    second = run(runtime, tmp_path, state)
    assert calls == ['cell:s00:r10:c3', 'cell:s00:r10:c5']
    assert first['edits'] == second['edits']
    assert first['unresolved_authorised_targets'] == ['cell:s00:r10:c4']
    assert 'cell:s00:r10:c4' not in first['dispositions']


def test_budget_stop_does_not_dispose_unattempted_work(tmp_path):
    runtime, _, calls = fixture_runtime(tmp_path)
    runtime.TaskBudget = lambda state: SimpleNamespace(failure=lambda: 'TASK_MODEL_CALL_LIMIT' if calls else None)
    result = run(runtime, tmp_path)
    assert len(calls) == 1
    assert result['unresolved_authorised_targets'] == ['cell:s00:r10:c4', 'cell:s00:r10:c5']
    assert result['failures'][-1]['failure_class'] == 'TASK_MODEL_CALL_LIMIT'


def test_unexpected_exception_does_not_activate_further_provider_work(tmp_path):
    runtime, _, calls = fixture_runtime(tmp_path)
    original = runtime.retrieval_synthesis
    def synth(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('simulated integration failure')
    runtime.retrieval_synthesis = synth
    with pytest.raises(RuntimeError, match='simulated integration failure'):
        run(runtime, tmp_path)
    assert calls == ['cell:s00:r10:c3']


def test_completeness_metadata_does_not_widen_partial_plan_or_claim_semantics():
    compiler = {'obligations': [{'id': 'O1'}, {'id': 'O2'}, {'id': 'O3'}]}
    plan = {'status': 'VALID_PLAN', 'fragments': [
        {'obligation_id': 'O1', 'status': 'PROVIDER_TIMEOUT'},
        {'obligation_id': 'O2', 'status': 'EMPTY_EXPANSION'},
        {'obligation_id': 'O3', 'status': 'VALID_PLAN'}],
        'expansion': {'operations': [{'obligation_id': 'O3', 'cell_ids': ['cell:s00:r1:c1']}]}}
    before = copy.deepcopy(plan)
    result = m.planning_completeness(compiler, plan)
    assert result['schema_valid_authority'] is True
    assert result['all_obligations_successfully_planned'] is False
    assert result['obligations_without_authority'] == ['O1', 'O2']
    assert result['status'] == 'PARTIAL'
    assert plan == before
    complete = m.planning_completeness({'obligations': [{'id': 'O3'}]}, plan)
    assert complete['status'] == 'COMPLETE'
    assert complete['semantic_completeness'] == 'NOT_ESTABLISHED'


def test_plan_task_persists_completeness_as_additive_metadata(monkeypatch, tmp_path):
    plan = {'status': 'VALID_PLAN', 'expansion': {'operations': [{'obligation_id': 'O1', 'cell_ids': ['cell:s00:r1:c1']}]}}
    monkeypatch.setattr(m, '_plan_task', lambda *a, **k: copy.deepcopy(plan))
    result = m.plan_task('task', {}, {'obligations': [{'id': 'O1'}, {'id': 'O2'}]}, {}, tmp_path, stub=False)
    assert result['planning_completeness']['status'] == 'PARTIAL'
    assert {k: v for k, v in result.items() if k != 'planning_completeness'} == plan


def test_accounting_failure_does_not_discard_a_returned_usable_proposal():
    session = {'failure_class': 'TASK_COST_LIMIT', 'synthesis': {'parsed': {'status': 'PROPOSED', 'formula': '=1'}}}
    assert compiled_scheduler.synthesis_outcome(session) == 'PROPOSED'


def test_provider_error_finish_is_not_a_model_parse_failure(monkeypatch):
    from io import BytesIO

    body = {'choices': [{'finish_reason': 'error', 'message': {'content': None}}], 'usage': {}}
    monkeypatch.setattr(m, 'provider_key', lambda: 'test-only-not-a-credential')
    monkeypatch.setattr(m.urllib.request, 'urlopen', lambda *a, **k: BytesIO(json.dumps(body).encode()))
    state = {}
    call = m.model_call('test', 'edit_plan', 'system', 'user', state)
    assert call['raw_response_body'] == body
    assert call['failure_class'] == 'PROVIDER_ERROR'
    assert call['truncation_class'] is None
    assert state['model_call_count'] == 1
    old_session = {'synthesis': {'parsed': None}, 'calls': [{'stage': 'synthesis', 'finish_reason': 'error'}]}
    assert compiled_scheduler.synthesis_outcome(old_session) == 'PROVIDER_ERROR'
