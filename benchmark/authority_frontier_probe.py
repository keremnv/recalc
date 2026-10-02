"""Offline field/compiled-world lineage probe. No provider or workbook writes.

Archived authority and model responses stay fixed. Counterfactual packets reuse
the existing grounder over the repaired temporal world; scope-label shadow hits
are measured as evidence only, never converted into edit authority.
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import matched_compiled_treatment as m
import workbook_grounding as g
from openpyxl.utils.cell import coordinate_to_tuple


def run(destination: Path, baseline_grounder: Path):
    spec = importlib.util.spec_from_file_location('pre_frontier_grounder', baseline_grounder)
    before = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before)
    live = m.RUN_ROOT / 'resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge'
    repaired = m.RUN_ROOT / 'integration_autopsy/repaired_db'
    csv.field_size_limit(100_000_000)
    with (m.ROOT / 'research/history/loose_evidence/authority_loss_by_obligation.csv').open() as handle:
        annotations = {(r['task'], r['obligation_id']): r for r in csv.DictReader(handle) if r['row_type'] == 'OBLIGATION'}
    hashes = {}
    def read(path):
        data = path.read_bytes()
        hashes[str(path.resolve())] = hashlib.sha256(data).hexdigest()
        return json.loads(data)
    rows, task_rows, shadows = [], [], []
    for result_path in sorted(live.glob('*/result.json')):
        result = read(result_path)
        task = result['task_id']
        slug = task.replace(':', '-')
        base = read(m.SPINES / f'{slug}.json')
        old_db, new_db = m.DATABASES / f'{slug}.sqlite', repaired / f'{slug}.sqlite'
        for path in (old_db, new_db):
            hashes[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
        original_world, world = m.World(old_db), m.World(new_db)
        try:
            temporal_spine = m.planning_spine_for(task, world)
            compiler, plan = result['compiler'], result['edit_plan']
            fragments = {f['obligation_id']: f for f in plan.get('fragments', [])}
            parsed = plan.get('parsed')
            expansion_replay = {}
            for label, w in [('original_database', original_world), ('repaired_database', world)]:
                if not isinstance(parsed, dict):
                    expansion_replay[label] = {'status': 'NO_PARSED_PLAN'}
                    continue
                try:
                    exp = m.expand_edit_plan(parsed, w, {o['id'] for o in compiler.get('obligations', [])}, id_contract='V2')
                    expansion_replay[label] = {'status': exp['status'], 'cell_ids': exp['cell_ids']}
                except m.PlanError as exc:
                    expansion_replay[label] = {'status': exc.category, 'error': str(exc)}
            task_rows.append({'task': task, 'obligations': len(compiler.get('obligations', [])),
                              'legacy_periods': len(base.get('periods', [])), 'default_db_temporal': len(original_world.temporal),
                              'repaired_db_temporal': len(world.temporal), 'plan_status': plan.get('status'),
                              'planning_completeness': m.planning_completeness(compiler, plan),
                              'same_response_expansion': expansion_replay})
            for ob in compiler.get('obligations', []):
                oid = ob['id']
                packet = plan['packets'][oid]
                replayed = before.project_obligation(base, ob)
                # Extensional targets can match despite old set-iteration order.
                # Retain any bounded-fact membership differences separately.
                assert set(replayed['target_cell_ids']) == set(packet['target_cell_ids']), (task, oid, 'target set mismatch')
                unordered = lambda xs: sorted(json.dumps(x, sort_keys=True) for x in xs)
                replay_differences = [k for k in ('locus', 'subject', 'scope', 'source', 'formula_class_facts', 'dependency_facts')
                                      if unordered(replayed[k]) != unordered(packet[k])]
                temporal_only = before.project_obligation(temporal_spine, ob)
                repaired_packet = g.project_obligation(temporal_spine, ob)
                fragment = fragments.get(oid, {})
                context = fragment.get('context', {})
                context_ids = {o['id'] for o in context.get('GENERATED_TASK_IR', {}).get('obligations', [])}
                edges = ob.get('then_after') or []
                annotation = annotations.get((task, oid))
                gold = set()
                if annotation:
                    for cell in json.loads(annotation['gold_target_cells']):
                        sheet, address = cell.rsplit('!', 1)
                        row, col = coordinate_to_tuple(address)
                        gold.add(f'cell:s{base["title_to_index"][sheet]:02d}:r{row}:c{col}')
                variants = {'archived': packet, 'temporal_only': temporal_only, 'temporal_and_percentage_fix': repaired_packet}
                metrics = {}
                for name, value in variants.items():
                    targets = set(value['target_cell_ids'])
                    metrics[name] = {'scope_candidates': len(value['scope']), 'target_candidates': len(targets),
                                     'gold_candidate_intersection': len(targets & gold) if annotation else None}
                row = {'task': task, 'obligation_id': oid, 'raw_obligation': ob,
                       'archived_packet_replay_membership_differences': replay_differences,
                       'fragment_status': fragment.get('status'), 'raw_task_in_context': context.get('RAW_TASK') == compiler.get('raw_task'),
                       'then_after': edges, 'then_after_ids_absent_from_shard': sorted(set(edges) - context_ids),
                       'scope_spec_before': before.parse_scope_spec(ob), 'scope_spec_after': g.parse_scope_spec(ob),
                       'gold_annotation_present': bool(annotation), 'gold_count': len(gold) if annotation else None,
                       'metrics': metrics, 'scope_ids_added_by_temporal': sorted({x['id'] for x in temporal_only['scope']} - {x['id'] for x in packet['scope']}),
                       'targets_added_by_temporal': sorted(set(temporal_only['target_cell_ids']) - set(packet['target_cell_ids'])),
                       'targets_removed_by_temporal': sorted(set(packet['target_cell_ids']) - set(temporal_only['target_cell_ids'])),
                       'authority_count': int(annotation['authority_count']) if annotation else None,
                       'prior_missed_gold_classification': json.loads(annotation['missed_gold_cause_counts']) if annotation else None}
                rows.append(row)
                # Reuse frozen lexical matching, with exact existing scope spans.
                # Do not union hits into subjects or expand a hypothetical plan.
                scope_queries = [g.field_text(s) for s in ob.get('scope', [])]
                hits = g.retrieve_text(base, scope_queries, sheet_ids={h['sheet_id'] for h in packet['locus']} or None)
                subject_ids = {h['cell_id'] for h in packet['subject']}
                extra = [h for h in hits if h['cell_id'] not in subject_ids]
                gold_rows = {c.rsplit(':c', 1)[0] for c in gold}
                shadows.append({'task': task, 'obligation_id': oid, 'scope': scope_queries,
                                'extra_scope_label_hits': extra, 'extra_hit_count': len(extra),
                                'extra_rows': len({h['row_id'] for h in extra}),
                                'gold_rows_with_extra_label': sorted({h['cell_id'].rsplit(':c', 1)[0] for h in extra} & gold_rows) if annotation else None,
                                'caveat': 'Lexical evidence opportunity only. A hit is not proof of target role or authority.'})
        finally:
            original_world.close()
            world.close()
        del base, temporal_spine, result
        gc.collect()
        print(task, 'complete', flush=True)
    historical = read(m.ROOT / 'benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-compile-probe/parses_glm.json')
    scope_changes = []
    for record in historical['calls']:
        for ob in record.get('obligations', []):
            a, b = before.parse_scope_spec(ob), g.parse_scope_spec(ob)
            if a != b:
                scope_changes.append({'task': record['task'], 'obligation_id': ob['id'], 'scope': ob.get('scope'), 'before': a, 'after': b})
    summary = {'model_calls': 0, 'workbook_writes': 0, 'tasks': len(task_rows), 'obligations': len(rows),
               'all_archived_target_sets_reproduced': True,
               'packet_replay_membership_differences': [{'task': r['task'], 'obligation_id': r['obligation_id'], 'fields': r['archived_packet_replay_membership_differences']} for r in rows if r['archived_packet_replay_membership_differences']],
               'fragment_status_counts': dict(Counter(r['fragment_status'] for r in rows)),
               'obligations_with_then_after': sum(bool(r['then_after']) for r in rows),
               'obligations_with_dangling_shard_edges': sum(bool(r['then_after_ids_absent_from_shard']) for r in rows),
               'obligations_with_temporal_scope_change': sum(bool(r['scope_ids_added_by_temporal']) for r in rows),
               'obligations_with_target_change': sum(bool(r['targets_added_by_temporal'] or r['targets_removed_by_temporal']) for r in rows),
               'obligations_with_percentage_year_change': sum(r['scope_spec_before'] != r['scope_spec_after'] for r in rows),
               'scope_shadow_obligations_with_extra_hits': sum(bool(r['extra_hit_count']) for r in shadows),
               'historical_percentage_changes': scope_changes, 'task_rows': task_rows}
    for path, expected in hashes.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path
    summary['source_hashes_unchanged'] = True
    destination.mkdir(parents=True, exist_ok=True)
    m.write_csv(destination / 'obligation_lineage.csv', rows)
    m.write_json(destination / 'scope_label_shadow.json', shadows)
    m.write_json(destination / 'summary.json', summary)
    m.write_json(destination / 'source_hashes.json', hashes)
    print(json.dumps({k: v for k, v in summary.items() if k not in {'task_rows', 'historical_percentage_changes'}}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-grounder', type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.baseline_grounder)
