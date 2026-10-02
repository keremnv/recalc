#!/usr/bin/env python3
"""Frozen-trajectory attribution. No inference, source writes, or gold-based policy.

Run: PYTHONPATH=benchmark:src:benchmark/sweagent/formula_index/lib \
     python benchmark/resource_demand_autopsy.py
Outputs are confined to research/history/resource_demand_autopsy/. Archived inputs are hash-checked.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import clean_integrated_feasibility as c
import compiled_scheduler
import matched_compiled_treatment as m
import xlsx_cell_writer as writer

ROOT = c.ROOT
OUT = ROOT / 'research/history/resource_demand_autopsy'
TASK = 'Financial_Model:06_01'
TD = c.LIVE_ROOT / 'Financial_Model-06_01'
TD7 = c.LIVE_ROOT / 'Financial_Model-07_01'
CELL = re.compile(r'cell:s\d+:r\d+:c\d+')
PROVIDER_FAILURES = {'PROVIDER_TIMEOUT', 'PROVIDER_ERROR', 'MODEL_ACCESS_FAILURE'}


def compact(v):
    return json.dumps(v, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def digest(v):
    return hashlib.sha256(compact(v).encode()).hexdigest()


def file_hash(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def emit(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def table(name, rows):
    with (OUT / name).open('w', newline='') as f:
        keys = list(dict.fromkeys(k for row in rows for k in row))
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows({k: compact(v) if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()} for row in rows)


def cell_tuple(cid, spine):
    _, sid, row, col = cid.split(':')
    title = next(t for t, i in spine['title_to_index'].items() if i == int(sid[1:]))
    return title, int(row[1:]), int(col[1:])


def display(cell):
    return f'{cell[0]}!{m.closure.a1(cell[1], cell[2])}'


def cost(calls):
    return sum(float(x.get('provider_cost_usd') or 0) for x in calls)


def message(call):
    return call['request_body']['messages'][1]['content']


def records(evidence):
    """Exact table-row records; schema is part of identity, not just cell ID."""
    for namespace in ('entities', 'relations'):
        for name, tab in evidence[namespace].items():
            for row in tab['rows']:
                yield compact([namespace, name, tab['columns'], row])


def run():
    OUT.mkdir(exist_ok=True)
    archive_files = sorted(set([TD / 'state.json', TD / 'result.json', TD7 / 'result.json',
        TD / 'output.xlsx', TD7 / 'output.xlsx', c.LIVE_ROOT / 'official_scores.json',
        ROOT / 'INTEGRATED_FEASIBILITY_REPORT.md', ROOT / 'INTEGRATED_FEASIBILITY_COST_REPORT.md']
        + list((TD / 'calls').glob('*.json'))))
    manifest = {str(p.relative_to(ROOT)): file_hash(p) for p in archive_files}
    state = c.read_json(TD / 'state.json')
    cp = state['scheduler_v3']
    spine = m.spine_for(TASK)
    plan = state['edit_plan']
    auth = set(plan['expansion']['cell_ids'])
    assert len(auth) == 78777
    sessions = cp['sessions']
    accepted = cp['edits']
    calls = [c.read_json(p) for p in sorted((TD / 'calls').glob('*.json'))]
    by_index = {a['call_index_within_task']: a for a in calls}
    memberships = defaultdict(list)
    for op in plan['expansion']['operations']:
        for cid in op['cell_ids']:
            memberships[cid].append(op['operation_id'])
    owner = {cid: ops[0] for cid, ops in memberships.items()}
    groups = state['schedule']['eligible_program_groups']
    cid_of = {cell_tuple(cid, spine): cid for cid in auth}
    grouped = {cid_of[tuple(x)] for g in groups for x in g['member_cells']}
    canonicals = {cid_of[tuple(g['canonical_cell'])] for g in groups}
    residual = auth - grouped
    assert len(residual) == 76961
    session_ids = set(sessions)
    referenced = set()
    accepted_references = {}
    for cid, rec in accepted.items():
        refs = m.proposal_precedents(rec['formula'], tuple(rec['cell']))
        accepted_references[cid] = sorted(display(x) for x in refs)
        referenced.update(cid_of[x] for x in refs if x in cid_of)

    # Provider requests, including discarded/replayed requests, are authoritative
    # for billing. Embedded session copies additionally retain SQL results.
    call_owner = {}
    call_working_sets = {}
    all_request_auth, accepted_request_auth = set(), set()
    seen_ws, seen_record_keys = set(), set()
    evidence_dictionary = {}
    evidence_manifests = []
    session_rows, slices = [], []
    accepted_call_indices = set()
    total_record_bytes = unique_record_bytes = 0
    bootstrap_field_sources = {}
    ordered_sessions = sorted(sessions.items(), key=lambda item: min(
        x['call_index_within_task'] for x in item[1]['session']['calls']))
    for cid, proposal in ordered_sessions:
        se = proposal['session']
        indices = [x['call_index_within_task'] for x in se['calls']]
        for idx in indices:
            assert idx not in call_owner
            call_owner[idx] = cid
        ws = set(se['working_set_ids'])
        boot = set(se['bootstrap']['bootstrap_entity_ids']) | {cid}
        new = ws - boot
        retained_calls = [by_index[i] for i in indices]
        request_auth = set().union(*(set(CELL.findall(message(a))) & auth for a in retained_calls))
        all_request_auth |= request_auth
        if cid in accepted:
            accepted_request_auth |= request_auth
            accepted_call_indices.update(indices)
        added_lists = [x.get('new_working_set_ids', []) for x in se['calls']]
        assert ws == boot | set().union(*(set(x) for x in added_lists))
        cumulative_ws = set(boot)
        for step in se['calls']:
            delta_ids = set(step.get('new_working_set_ids', [])) - cumulative_ws
            call_working_sets[step['call_index_within_task']] = {
                'working_set_ids_before': len(cumulative_ws),
                'working_set_ids_added': len(delta_ids),
                'working_set_ids_after': len(cumulative_ws | delta_ids),
                'new_evidence_ids': sorted(delta_ids),
                'sql_result_bytes': len(compact(step['result']).encode()) if 'result' in step else None,
                'working_set_observation': 'retained session; SQL delta is IDs, not all information',
            }
            cumulative_ws.update(delta_ids)
        assert cumulative_ws == ws
        packet = plan['packets'][proposal['target']['obligation_id']]
        oid = proposal['target']['obligation_id']
        if oid not in bootstrap_field_sources:
            bootstrap_field_sources[oid] = {
                key: {'entity_ids': len(m.prior.projection.packet_ids({key: value})),
                      'authorised_cell_ids': len(m.prior.projection.packet_ids({key: value}) & auth)}
                for key, value in packet.items()}
        recs = list(records(se['evidence']))
        keys = [hashlib.sha256(x.encode()).hexdigest() for x in recs]
        repeat_bytes = sum(len(r.encode()) for k, r in zip(keys, recs) if k in seen_record_keys)
        new_record_bytes = sum(len(r.encode()) for k, r in zip(keys, recs) if k not in seen_record_keys)
        total_record_bytes += sum(len(r.encode()) for r in recs)
        unique_record_bytes += new_record_bytes
        for key, record in zip(keys, recs):
            if key in evidence_dictionary:
                assert evidence_dictionary[key] == record
            evidence_dictionary[key] = record
        assert [evidence_dictionary[k] for k in keys] == recs
        evidence_manifests.append({'session': cid, 'record_keys': keys, 'evidence_sha256': digest(se['evidence'])})
        fresh_sql = [a for a in se['calls'] if 'result' in a]
        row = {
            'cell_id': cid, 'target': display(proposal['seed']), 'operation': owner[cid],
            'activation': 'UNGROUPED_RESIDUAL', 'program_group': cid in grouped,
            'outcome': se['status'], 'accepted': cid in accepted,
            'call_indices': indices, 'retrieval_calls': sum(a['stage'] == 'retrieval' for a in retained_calls),
            'synthesis_calls': sum(a['stage'] == 'synthesis' for a in retained_calls),
            'provider_failures': sum(a.get('failure_class') in PROVIDER_FAILURES for a in retained_calls),
            'cost_usd': cost(retained_calls), 'bootstrap_ids': len(boot), 'final_ws_ids': len(ws),
            'new_sql_ids': len(new), 'ws_ids_in_prior_sessions': len(ws & seen_ws),
            'ws_ids_new_to_task': len(ws - seen_ws),
            'authorised_cells_in_ws': len(ws & auth), 'authorised_cells_in_requests': len(request_auth),
            'bootstrap_bytes': len(compact(se['bootstrap']).encode()),
            'recorded_bootstrap_token_estimate': se['bootstrap']['bootstrap_tokens'],
            'serialized_bootstrap_chars_div_4': len(compact(se['bootstrap'])) // 4,
            'evidence_bytes': len(compact(se['evidence']).encode()),
            'record_count': len(recs), 'records_repeated_from_prior_sessions': sum(k in seen_record_keys for k in keys),
            'repeat_record_bytes': repeat_bytes, 'new_record_bytes': new_record_bytes,
            'synthesis_prompt_tokens_billed': sum((a.get('usage') or {}).get('prompt_tokens', 0) for a in retained_calls if a['stage'] == 'synthesis'),
            'all_request_bytes': sum(len(message(a).encode()) for a in retained_calls),
            'sql_queries': len(fresh_sql),
            'sql_no_new_ids': sum(not a.get('new_working_set_ids') for a in fresh_sql),
            'sql_statuses': dict(Counter(a['result'].get('status') for a in fresh_sql)),
            'explicit_formula_references': accepted_references.get(cid, []),
            'proposal_evidence_citations': (se['synthesis'].get('parsed') or {}).get('evidence_ids'),
            'inference_necessary_records': None,
        }
        session_rows.append(row)
        if cid in accepted:
            slices.append({**row, 'formula': accepted[cid]['formula'],
                'source_operation': next(o for o in plan['parsed']['operations'] if o['operation_id'] == owner[cid]),
                'hard_verifier': proposal['validation']['hard_verifier_result'],
                'validation': proposal['validation'], 'authority_references': sorted(ws & auth),
                'full_evidence_ids': sorted(ws), 'evidence_record_manifest_session': cid,
                'archive_synthesis_request_sha256': retained_calls[-1]['request_sha256'],
                'formula_precedents_in_authority': sorted(referenced),
                'necessity_scope': 'Exact persisted input to this response; minimal model-reasoning evidence is unobservable.'})
        seen_ws |= ws
        seen_record_keys.update(keys)

    call_rows = []
    for call in calls:
        idx = call['call_index_within_task']
        cid = call_owner.get(idx)
        stage = call['stage']
        failure = call.get('failure_class')
        if failure in PROVIDER_FAILURES:
            bucket = 'PROVIDER_FAILURE'
        elif stage in ('task_ir', 'edit_plan'):
            bucket = 'FRONTEND'
        elif cid is None:
            bucket = 'RESUME_DISCARDED_RETRIEVAL'
        elif stage == 'synthesis':
            bucket = 'SEMANTIC_DECISION'
        else:
            bucket = 'RETRIEVAL_FOR_SEMANTIC_DECISION'
        payload = json.loads(message(call)) if stage in ('retrieval', 'synthesis') else {}
        inferred_target = (payload.get('TARGET') or (payload.get('SESSION_STATE') or {}).get('target') or {}).get('cell_id')
        ids_in_request = set(CELL.findall(message(call))) & auth
        all_request_auth |= ids_in_request if stage in ('retrieval', 'synthesis') else set()
        call_rows.append({'index': idx, 'stage': stage, 'session': cid,
            'target_from_request': inferred_target, 'operation': owner.get(cid or inferred_target),
            'exclusive_bucket': bucket, 'failure_class': failure,
            'accepted_edit_path': idx in accepted_call_indices,
            'cost_usd': call.get('provider_cost_usd', 0),
            'prompt_tokens': (call.get('usage') or {}).get('prompt_tokens'),
            'completion_tokens': (call.get('usage') or {}).get('completion_tokens'),
            'user_prompt_bytes': len(message(call).encode()),
            'request_sha256': call['request_sha256'],
            'authorised_ids_in_request': len(ids_in_request),
            'retrieval_uses_existing_handle': 'working_set_handle' in compact(payload),
            'action': (call.get('parsed_response') or {}).get('action'),
            'sql': (call.get('parsed_response') or {}).get('sql'),
            **call_working_sets.get(idx, {
                'working_set_observation': 'not retained in a work session; no state fabricated'})})

    # Expansion replay uses the same repaired database and exact stored plan.
    db = c.feasibility.REPAIRED_DATABASES / 'Financial_Model-06_01.sqlite'
    world = m.World(db)
    expanded = m.expand_edit_plan(plan['parsed'], world, {o['id'] for o in state['compiler']['obligations']}, id_contract='V2')
    assert set(expanded['cell_ids']) == auth
    operation_rows = []
    for op in plan['parsed']['operations']:
        exp = next(x for x in expanded['operations'] if x['operation_id'] == op['operation_id'])
        raw = set(world.expression(op['target_set']))
        cells = set(exp['cell_ids'])
        owned = {cid for cid in cells if owner[cid] == op['operation_id']}
        operation_rows.append({'operation': op['operation_id'], 'obligation': op['obligation_id'],
            'kind': op['operation_kind'], 'intensional_target': op['target_set'],
            'occupancy_filter': op.get('occupancy_filter'), 'raw_expansion': len(raw),
            'filtered_cells': len(cells), 'ownership_after_overlap': len(owned),
            'occupancy_counts': dict(Counter(world.cells.get(cid, {}).get('kind', 'blank') for cid in cells)),
            'implicit_blank_count': len(cells - world.cells.keys()),
            'group_members': len(cells & grouped), 'group_canonicals': len(cells & canonicals),
            'sessions': len(cells & session_ids), 'accepted': len(cells & accepted.keys()),
            'in_any_work_request': len(cells & all_request_auth),
            'in_accepted_work_requests': len(cells & accepted_request_auth)})
    sheet = dict(world.sheets['sheet:s13'])
    world.close()

    # Use the actual scheduler and hard verifier with stored responses only.
    # A ceiling at first missing session prevents exploring unobserved residuals.
    runtime = SimpleNamespace(**{name: getattr(m, name) for name in dir(m) if not name.startswith('__')})
    runtime.db_for = lambda _task: db
    runtime.write_json = lambda *args, **kwargs: None
    runtime.TaskBudget = lambda _state: SimpleNamespace(failure=lambda: 'TASK_MODEL_CALL_LIMIT')
    runtime.program_group = SimpleNamespace(groups_for=lambda *args, **kwargs: (groups, state['schedule']['group_refusals']), translate=m.program_group.translate)
    def no_inference(*args, **kwargs):
        raise AssertionError('Inference is prohibited during autopsy')
    runtime.retrieval_synthesis = no_inference
    replay_state = {'scheduler_v3': {'sessions': dict(sessions), 'edits': {}, 'dispositions': {}, 'units': [], 'failures': []}}
    replay_plan = dict(plan)
    replay = compiled_scheduler.schedule(runtime, TASK, {}, state['compiler'], replay_plan, replay_state, TD)
    assert replay['edits'] == state['completed_edits']
    # The archived writer adds writer_result after scheduling. This replay
    # deliberately stops before writing and compares the scheduler fields.
    scheduler_dispositions = {key: {k: v for k, v in rec.items() if k != 'writer_result'}
                              for key, rec in cp['dispositions'].items()}
    assert replay['dispositions'] == scheduler_dispositions
    assert set(replay['unresolved_authorised_targets']) == set(state['unresolved_authorised_targets'])
    assert replay['authorized_targets'] == len(auth)
    # Exact posterior slice: evaluate saved accepted proposals in isolation.
    cache = {}
    sliced_edits = []
    for cid, rec in accepted.items():
        proposal = sessions[cid]
        checked = runtime.validate_formula(TASK, proposal['target'], rec['formula'], cache, spine)
        assert checked['hard_verifier_result'] == 'HARD_ACCEPT'
        sliced_edits.append({'sheet': rec['cell'][0], 'address': m.closure.a1(*rec['cell'][1:]), 'formula': rec['formula']})
    assert sorted(sliced_edits, key=compact) == sorted(state['completed_edits'], key=compact)

    accepted_calls = [by_index[i] for i in sorted(accepted_call_indices)]
    first_per_op = {}
    for row in session_rows:
        first_per_op.setdefault(row['operation'], row['cell_id'])
    initial_rule_survivors = set(first_per_op.values()) & accepted.keys()
    buckets = Counter(row['exclusive_bucket'] for row in call_rows)
    partition = []
    for cid in sorted(auth):
        if cid in accepted:
            category = 'ACTIVATED_ACCEPTED'
        elif cid in session_ids:
            category = 'ACTIVATED_WITHOUT_EDIT'
        elif cid in canonicals:
            category = 'UNACTIVATED_GROUP_CANONICAL'
        elif cid in grouped:
            category = 'UNACTIVATED_GROUP_NONCANONICAL'
        else:
            category = 'UNACTIVATED_RESIDUAL'
        partition.append({'cell_id': cid, 'address': display(cell_tuple(cid, spine)),
            'operations': memberships[cid], 'owner': owner[cid], 'exclusive_partition': category,
            'program_group_member': cid in grouped, 'canonical': cid in canonicals,
            'session_started': cid in session_ids, 'in_any_work_request': cid in all_request_auth,
            'in_accepted_work_request': cid in accepted_request_auth,
            'in_accepted_formula_precedents': cid in referenced,
            'no_direct_accepted_path_evidence': cid not in accepted_request_auth and cid not in accepted and cid not in referenced,
            'semantic_irrelevance_proven': False})

    # Reproduce the writer guards in memory against the exact source XML.
    r7 = c.read_json(TD7 / 'result.json')
    source7 = m.task_source('Financial_Model:07_01')
    rejection_rows = []
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(source7) as z, zipfile.ZipFile(TD7 / 'output.xlsx') as out7:
        parts = writer.sheet_parts(z)
        for rejection in r7['write_audit']['rejected']:
            xml = z.read(parts[rejection['sheet']]).decode()
            root = ET.fromstring(xml)
            original = root.find(f'.//s:c[@r="{rejection["address"]}"]', ns)
            form = original.find('s:f', ns)
            siblings = [x for x in root.findall('.//s:c', ns) if (f := x.find('s:f', ns)) is not None and f.get('si') == form.get('si') and x.get('r') != rejection['address']]
            try:
                writer._patch_cell(xml, rejection['address'], rejection['formula'])
                raise AssertionError('Expected shared master guard did not fire')
            except writer.SharedMasterError as exc:
                guard = str(exc)
            actual = ET.fromstring(out7.read(parts[rejection['sheet']])).find(f'.//s:c[@r="{rejection["address"]}"]/s:f', ns)
            assert actual is not None and actual.text == form.text and actual.attrib == form.attrib
            applied = {x['address'] for x in r7['write_audit']['applied'] if x['sheet'] == rejection['sheet']}
            rejection_rows.append({**rejection, 'classification': 'EXPECTED_WRITER_SAFETY_REJECTION',
                'source_master_formula': form.text, 'source_master_attributes': form.attrib,
                'shared_followers': len(siblings), 'followers_individually_rewritten': sum(x.get('r') in applied for x in siblings),
                'guard_reproduced': guard, 'master_preserved_in_output': True,
                'interpretation': 'Verifier permits formula semantics; writer refuses shared-master replacement to avoid orphaning followers. Explicit current contract, not stale instrumentation.'})

    # Metadata labels are not the provider request. Audit the comparison's wire identity.
    probe = c.AUDIT_ROOT / 'model_swap_gpt56_sol_high/Financial_Model-06_01'
    probe_calls = [c.read_json(p) for p in sorted((probe / 'calls').glob('*.json'))]
    routing = {'ledger_labels': dict(Counter(a['model'] for a in probe_calls)),
        'request_models': dict(Counter(a['request_body']['model'] for a in probe_calls)),
        'request_reasoning': dict(Counter(a['request_body']['reasoning']['effort'] for a in probe_calls)),
        'response_models': dict(Counter((a.get('raw_response_body') or {}).get('model', 'NO_RESPONSE_MODEL') for a in probe_calls)),
        'cost_usd': cost(probe_calls), 'valid_GPT_comparison': False,
        'cause': 'feasibility.treatment_request_body uses its own MODEL/REASONING constants; overriding runtime.MODEL did not override wire request.'}

    summary = {
        'verdict': 'MULTIPLE_RESOURCE_LOSSES', 'model_calls': 0, 'workbook_writes': 0,
        'authority': len(auth), 'authority_sha256': digest(sorted(auth)), 'sheet': sheet,
        'operations': operation_rows, 'unique_group_members': len(grouped), 'program_groups': len(groups),
        'residual_cells': len(residual), 'potential_independent_units': len(residual) + len(groups),
        'initial_queued_units': cp['demand_accounting']['initial_stochastic_work_items'],
        'observed_distinct_decisions': len(sessions), 'accepted_decisions': len(accepted),
        'terminal_outcomes': dict(Counter(x['session']['status'] for x in sessions.values())),
        'partition_counts': dict(Counter(row['exclusive_partition'] for row in partition)),
        'in_any_work_request': len(all_request_auth), 'in_accepted_work_requests': len(accepted_request_auth),
        'accepted_formula_authority_precedents': len(referenced),
        'not_on_direct_accepted_path': sum(x['no_direct_accepted_path_evidence'] for x in partition),
        'call_buckets': dict(buckets), 'provider_failures_by_stage': dict(Counter(a['stage'] for a in calls if a.get('failure_class') in PROVIDER_FAILURES)),
        'total_calls': len(calls), 'total_cost_usd': cost(calls),
        'resume_discarded_indices': [row['index'] for row in call_rows if row['exclusive_bucket'] == 'RESUME_DISCARDED_RETRIEVAL'],
        'resume_discarded_cost_usd': sum(row['cost_usd'] for row in call_rows if row['exclusive_bucket'] == 'RESUME_DISCARDED_RETRIEVAL'),
        'bootstrap_field_sources': bootstrap_field_sources,
        'working_set_unique_ids': len(seen_ws), 'working_set_id_occurrences': sum(r['final_ws_ids'] for r in session_rows),
        'evidence_record_bytes': total_record_bytes, 'unique_record_bytes': unique_record_bytes,
        'duplicate_record_bytes': total_record_bytes - unique_record_bytes,
        'lossless_record_pool_reconstruction': True,
        'scheduler_replay': {'authority_unchanged': True, 'edits_equal': True, 'dispositions_equal': True, 'unresolved_equal': True, 'model_calls': 0},
        'accepted_path_slice': {'posthoc_response_conditioned': True, 'deployable_selector': False,
            'sessions': len(accepted), 'calls': len(accepted_calls),
            'retrieval': sum(a['stage'] == 'retrieval' for a in accepted_calls),
            'synthesis': sum(a['stage'] == 'synthesis' for a in accepted_calls),
            'cost_usd': cost(accepted_calls), 'call_indices': sorted(accepted_call_indices),
            'omitted_post_frontend_calls': len([a for a in calls if a['stage'] in ('retrieval','synthesis')]) - len(accepted_calls),
            'authority_unchanged': True, 'six_formulas_reverified': True,
            'model_choice_under_changed_prompts': 'UNMEASURED'},
        'first_unit_plus_dependencies_counterfactual': {'authority_unchanged': True,
            'retained_accepted_cells': sorted(initial_rule_survivors),
            'lost_accepted_cells': sorted(accepted.keys() - initial_rule_survivors),
            'accepted_dependency_units': len(referenced), 'valid_six_edit_preserving_rule': False,
            'unsampled_initial_units': 'No stored responses; cannot evaluate their outcomes.'},
        'writer_side_audit': rejection_rows, 'comparison_routing_correction': routing,
    }
    # Audit the precise evidence frontier, without making claims about what
    # hidden model reasoning needed. Row-byte metrics exclude repeated schemas.
    row_seen = set()
    all_row_bytes = new_row_bytes = 0
    for manifest_rec in evidence_manifests:
        for key in manifest_rec['record_keys']:
            record = json.loads(evidence_dictionary[key])
            nbytes = len(compact(record[3]).encode())
            all_row_bytes += nbytes
            if key not in row_seen:
                new_row_bytes += nbytes
            row_seen.add(key)
    summary['serialization'] = {
        'full_work_request_bytes_retained_sessions': sum(x['all_request_bytes'] for x in session_rows),
        'synthesis_evidence_bytes': sum(x['evidence_bytes'] for x in session_rows),
        'initial_bootstrap_bytes': sum(x['bootstrap_bytes'] for x in session_rows),
        'table_row_bytes': all_row_bytes, 'unique_table_row_bytes': new_row_bytes,
        'duplicate_table_row_bytes': all_row_bytes - new_row_bytes,
        'model_token_savings_from_handle_only': None,
        'runtime_retrieval_already_uses_delta_handles': sum(x['retrieval_uses_existing_handle'] for x in call_rows),
        'sql_calls_no_new_ids': sum(x['sql_no_new_ids'] for x in session_rows),
        'sql_calls_with_results': sum(x['sql_queries'] for x in session_rows),
        'no_new_ids_is_not_no_information': True,
    }
    accepted_ws = set().union(*(set(sessions[cid]['session']['working_set_ids']) for cid in accepted))
    summary['accepted_path_slice']['union_evidence_ids'] = len(accepted_ws)
    summary['accepted_path_slice']['request_bytes'] = sum(len(message(a).encode()) for a in accepted_calls)
    summary['accepted_path_slice']['provider_failures_in_kept_paths'] = sum(a.get('failure_class') in PROVIDER_FAILURES for a in accepted_calls)
    summary['accepted_path_slice']['removed_retrieval'] = sum(a['stage'] == 'retrieval' for a in calls) - summary['accepted_path_slice']['retrieval']
    summary['accepted_path_slice']['removed_synthesis'] = sum(a['stage'] == 'synthesis' for a in calls) - summary['accepted_path_slice']['synthesis']
    summary['accepted_path_slice']['kept_frontend_plus_slice_calls'] = sum(a['stage'] in ('task_ir', 'edit_plan') for a in calls) + len(accepted_calls)
    # Retained numeric payloads directly used by the accepted formula family.
    # Read source cells only; never create a new workbook or cache here.
    numeric_rows = []
    numeric_ids = {'cell:s01:r47:c3','cell:s01:r48:c3','cell:s01:r51:c3'}
    for serialized in evidence_dictionary.values():
        _, name, cols, vals = json.loads(serialized)
        if name != 'cells':
            continue
        rec = dict(zip(cols, vals))
        if rec.get('cell_id') not in numeric_ids:
            continue
        source_value = m.cell_info(m.task_source(TASK), 'DCF', rec['address'])
        numeric_rows.append({'cell': 'DCF!' + rec['address'], 'source': source_value,
                             'archived_evidence': rec})
    summary['numeric_fidelity_observations'] = numeric_rows
    stage_rows = [
        {'stage': 'intensional_plan_to_expanded_memberships', 'entering': 7, 'leaving': sum(x['filtered_cells'] for x in operation_rows), 'representation': 'set expressions -> cell memberships', 'why': 'SHEET/RECTANGLE/UNION expansion and occupancy filters'},
        {'stage': 'operation_memberships_to_unique_authority', 'entering': sum(x['filtered_cells'] for x in operation_rows), 'leaving': len(auth), 'representation': 'cell sets', 'why': '16 O6 cells overlap O5; runtime first-owner mapping gives O6 zero owned cells'},
        {'stage': 'authority_to_potential_semantic_units', 'entering': len(auth), 'leaving': len(residual) + len(groups), 'representation': 'witnessed groups plus residual cell list', 'why': '1816 members -> 50 canonicals; 76961 residuals stay cells'},
        {'stage': 'potential_units_to_initial_active_queue', 'entering': len(residual) + len(groups), 'leaving': 6, 'representation': 'one candidate per owned operation', 'why': 'operation-order lazy activation'},
        {'stage': 'queue_replenishment_to_observed_sessions', 'entering': 6, 'leaving': len(sessions), 'representation': 'single-cell seeds', 'why': 'five O2 then sixteen O3 residuals; earlier operation sorts first each turn'},
        {'stage': 'observed_sessions_to_retrieval_attempts', 'entering': len(sessions), 'leaving': 121, 'representation': 'bootstrap then up to eight SQL decisions/session', 'why': '116 retained retrievals plus five discarded on resume'},
        {'stage': 'observed_sessions_to_synthesis_attempts', 'entering': len(sessions), 'leaving': 21, 'representation': 'complete evidence table per target', 'why': 'one synthesis per observed seed'},
        {'stage': 'synthesis_to_accepted_edits', 'entering': 21, 'leaving': 6, 'representation': 'concrete formulas', 'why': '12 provider timeouts; three explicit abstentions; six hard accepts'},
        {'stage': 'accepted_to_writer', 'entering': 6, 'leaving': 6, 'representation': 'explicit cells/formulas', 'why': 'no translations or dependency additions for these six seeds'},
    ]
    table('stages.csv', stage_rows)
    summary['stages'] = stage_rows
    table('operations.csv', operation_rows)
    table('authority_cells.csv', partition)
    table('sessions.csv', session_rows)
    table('calls.csv', call_rows)
    emit('accepted_edit_slices.json', slices)
    emit('evidence_record_pool.json', evidence_dictionary)
    emit('evidence_manifests.json', evidence_manifests)
    emit('writer_rejections.json', rejection_rows)
    emit('summary.json', summary)
    for relative, old in manifest.items():
        assert file_hash(ROOT / relative) == old, f'Frozen input modified: {relative}'
    emit('frozen_sources.json', {'sha256': manifest, 'unchanged_after_autopsy': True})
    print(json.dumps({k: v for k, v in summary.items() if k not in {'operations','bootstrap_field_sources','sheet','writer_side_audit'}}, indent=2), flush=True)


if __name__ == '__main__':
    run()
