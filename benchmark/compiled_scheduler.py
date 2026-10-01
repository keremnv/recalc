"""Gold-blind composition repair: durable sessions and witnessed group actuation.

The same earned grouping, closure, translation and hard verifier are used.
Membership in a dependency unit is never completion of a target.
"""
from __future__ import annotations

from collections import defaultdict


def synthesis_outcome(session):
    """Label the retained response without treating provider failure as abstention."""
    parsed = (session.get("synthesis") or {}).get("parsed")
    if isinstance(parsed, dict) and parsed.get("status") == "PROPOSED" and isinstance(parsed.get("formula"), str) and parsed["formula"]:
        # A returned proposal still gets verified, including when accounting
        # reports that the response crossed the task's cost ceiling.
        return "PROPOSED"
    failure = session.get("failure_class")
    if not failure:
        call = next((c for c in reversed(session.get("calls") or []) if c.get("stage") == "synthesis"), {})
        failure = call.get("failure_class") or ("PROVIDER_ERROR" if call.get("finish_reason") == "error" else None)
    if failure:
        return failure
    if isinstance(parsed, dict) and parsed.get("status") == "ABSTAIN":
        return "ABSTAIN"
    return "INVALID_RESPONSE"


def schedule(runtime, task_key, task, compiler, plan, state, task_dir, *, stub=False):
    m = runtime
    plan["spine"] = m.spine_for(task_key)
    meta, cids = m.authorised_cells(plan)
    auth = set(meta)
    if not auth:
        state["unresolved_authorised_targets"] = []
        return {"authorized_targets": 0, "canonical_decisions": [], "translated_formula_instances": [], "groups": [], "eligible_program_groups": [], "group_refusals": [], "failures": [], "dispositions": {}, "unresolved_authorised_targets": [], "edits": [], "stochastic_formula_decisions": 0, "translated_count": 0}
    forms = m.formula_forms(m.task_source(task_key))
    kinds = m.input_kinds(m.task_source(task_key))
    graph = m.db_precedent_graph(m.db_for(task_key))
    obs = {o["id"]: o for o in compiler.get("obligations", [])}
    # Keep the old durable key readable, but store the operation-preserving
    # queue under v3.  A resumed pre-v3 state is migrated without re-opening a
    # provider session or discarding any completed disposition.
    if "scheduler_v3" not in state and "scheduler_v2" in state:
        state["scheduler_v3"] = state["scheduler_v2"]
    checkpoint = state.setdefault("scheduler_v3", {"sessions": {}, "edits": {}, "dispositions": {}, "units": [], "failures": []})
    sessions = checkpoint["sessions"]
    edits = {tuple(v["cell"]): v["formula"] for v in checkpoint["edits"].values()}
    done = {tuple(v["cell"]) for v in checkpoint["dispositions"].values()}
    failures = checkpoint["failures"]
    # Repetition witnesses are about authorized peers, not dependency ancestry.
    # Restrict to the same operation as the earned groups_for contract requires.
    eligible = sorted(c for c in auth if meta[c]["operation_kind"] != "CLEAR_CELL")
    groups, refused = m.program_group.groups_for(eligible, meta, task_key, forms=forms, kinds=kinds)
    group_by_cell = {tuple(c): g for g in groups for c in g["member_cells"]}
    operations = (plan.get("expansion") or {}).get("operations", [])
    op_order = {o["operation_id"]: i for i, o in enumerate(operations)}
    operation_cells: dict[str, list[tuple]] = defaultdict(list)
    for cell in sorted(auth, key=lambda c: (op_order.get(meta[c]["operation_id"], 0), c)):
        operation_cells[meta[cell]["operation_id"]].append(cell)
    # Authority is retained extensionally for safety and verifier checks, but
    # it is no longer lowered to one eager stochastic session per cell.
    group_by_operation: dict[str, list[dict]] = defaultdict(list)
    for group in groups:
        members = {tuple(c) for c in group.get("member_cells", [])}
        op_ids = {meta[c]["operation_id"] for c in members if c in meta}
        if len(op_ids) == 1:
            group_by_operation[next(iter(op_ids))].append(group)
    residuals: dict[str, list[tuple]] = {
        op_id: [c for c in cells if c not in group_by_cell]
        for op_id, cells in operation_cells.items()
    }
    queue: list[tuple] = []
    queued: set[tuple] = set()

    prefer_groups = state.get("scheduler_activation") == "prefer_earned_program_groups"

    def enqueue(cell: tuple) -> None:
        # Dependency requests address the existing semantic unit. A failed
        # canonical must not turn its members into fresh independent sessions.
        group = group_by_cell.get(cell)
        if group:
            cell = tuple(group["canonical_cell"])
        if cell in done or cell in queued:
            return
        queued.add(cell)
        queue.append(cell)

    def activate_available() -> None:
        """Expose only earned units and the next residual member per operation."""
        for op_id in sorted(operation_cells, key=lambda x: op_order.get(x, 0)):
            group_candidates = []
            for group in sorted(group_by_operation.get(op_id, []), key=lambda g: tuple(g["canonical_cell"])):
                canonical = tuple(group["canonical_cell"])
                if canonical not in done and canonical not in queued:
                    group_candidates.append(canonical)
                    break
            residual_candidates = []
            # Residual work stays latent while a known group in the same
            # operation is unresolved.  Once groups have been processed, only
            # the next residual member is exposed; later members are deferred.
            groups_done = all(tuple(g["canonical_cell"]) in done for g in group_by_operation.get(op_id, []))
            if groups_done:
                for residual in residuals.get(op_id, []):
                    if residual not in done and residual not in queued:
                        residual_candidates.append(residual)
                        break
            elif not prefer_groups:
                # Preserve the old stable first-cell order when a residual
                # precedes the first witnessed canonical.  This is still one
                # active unit only; the remaining residual tail stays latent.
                first_group = group_candidates[0] if group_candidates else None
                for residual in residuals.get(op_id, []):
                    if residual not in done and residual not in queued and (first_group is None or residual < first_group):
                        residual_candidates.append(residual)
                        break
            candidates = group_candidates + residual_candidates
            # Preserve the historical stable cell order within an operation
            # while exposing only one unit.  This keeps deterministic replay
            # intact and still prevents an authority-sized eager queue.
            # Group-first activation still exposes one unit, but will not let a
            # residual outrank an earned ProgramGroup canonical.
            if prefer_groups and group_candidates:
                enqueue(group_candidates[0])
            elif candidates:
                enqueue(min(candidates))
        if prefer_groups:
            queue.sort(key=lambda c: (0 if c in group_by_cell else 1, op_order.get(meta[c]["operation_id"], 0), c))
        else:
            queue.sort(key=lambda c: (op_order.get(meta[c]["operation_id"], 0), c))
    cache = {}

    def key(c):
        return cids[c]

    def flush():
        checkpoint["edits"] = {key(c): {"cell": list(c), "formula": f} for c, f in edits.items()}
        state["completed_edits"] = [{"sheet": c[0], "address": m.closure.a1(c[1], c[2]), "formula": f} for c, f in sorted(edits.items())]
        state["unresolved_authorised_targets"] = [key(c) for c in sorted(auth - done)]
        state["scheduler_v3"] = checkpoint
        # Compatibility alias for archived diagnostics and replay readers.
        state["scheduler_v2"] = checkpoint
        m.write_json(task_dir / "state.json", state)

    def disposition(c, status, **detail):
        checkpoint["dispositions"][key(c)] = {"cell": list(c), "status": status, **detail}
        done.add(c)

    def finish_turn():
        # All terminal paths, not just accepted formulas, replenish work.
        # activate_available only exposes canonicals and genuine residuals;
        # members of a failed group remain unresolved, not reclassified.
        activate_available()
        flush()

    activate_available()
    initial_active = len(queue)
    deferred_residuals = sum(len(v) for v in residuals.values())
    amortized_members = sum(max(0, len(g.get("member_cells", [])) - 1) for g in groups)
    checkpoint.setdefault("demand_accounting", {
        "scheduler_activation": "prefer_earned_program_groups" if prefer_groups else "operation_order",
        "initial_stochastic_work_items": initial_active,
        "latent_residual_authorised_cells": deferred_residuals,
        "maximum_immediately_required_semantic_decisions": initial_active,
        "eliminated_decisions": 0,
        "amortized_decisions": amortized_members,
        "deferred_decisions": deferred_residuals,
        "operation_count": len(operation_cells),
    })
    while queue:
        candidate = queue.pop(0)
        queued.discard(candidate)
        if candidate in done:
            finish_turn()
            continue
        if meta[candidate]["operation_kind"] == "CLEAR_CELL":
            failures.append({"cell": list(candidate), "failure_class": "UNSUPPORTED_EDIT_KIND"})
            disposition(candidate, "UNSUPPORTED_EDIT_KIND")
            finish_turn(); continue
        group = group_by_cell.get(candidate)
        canon = tuple(group["canonical_cell"]) if group else candidate
        seed = canon
        if seed in edits:
            # Atomic checkpoints normally make this redundant with done.
            # Recover an already scheduled write without synthesizing again.
            disposition(seed, "WRITES_SCHEDULED")
            finish_turn()
            continue
        if key(seed) not in sessions:
            if state.get("replay_stored_sessions_only"):
                disposition(seed, "REPLAY_NO_STORED_RESPONSE")
                finish_turn()
                continue
            blocked = m.TaskBudget(state).failure()
            if blocked:
                failures.append({"failure_class": blocked, "scope": "remaining_authorized_targets", "remaining_count": len(auth - done)})
                break
            target = m.target_from_id(plan["spine"], key(seed), task_key, meta[seed]["obligation_id"])
            if target is None:
                failures.append({"cell": list(seed), "failure_class": "INVALID_ENTITY"})
                disposition(seed, "INVALID_ENTITY"); finish_turn(); continue
            session = m.retrieval_synthesis(task_key, task, obs[meta[seed]["obligation_id"]], target, plan["packets"][meta[seed]["obligation_id"]], state, task_dir, stub=stub)
            parsed = session["synthesis"].get("parsed")
            f = parsed.get("formula") if synthesis_outcome(session) == "PROPOSED" else None
            sessions[key(seed)] = {"seed": list(seed), "target": target, "session": session, "formula": f}
            # Crash between the provider return and this checkpoint is recovered
            # through the immutable request/response ledger, not a new call.
            flush()
        proposal = sessions[key(seed)]
        f = proposal.get("formula")
        if not f:
            outcome = synthesis_outcome(proposal["session"])
            disposition(seed, outcome, failure=None if outcome == "ABSTAIN" else outcome)
            if outcome != "ABSTAIN":
                failures.append({"cell": list(seed), "stage": "synthesis", "failure_class": outcome})
            finish_turn(); continue
        validation = m.validate_formula(task_key, proposal["target"], f, cache, plan["spine"])
        proposal["validation"] = validation
        if validation.get("hard_verifier_result") != "HARD_ACCEPT":
            disposition(seed, "REJECTED_HARD")
            failures.append({"cell": list(seed), "failure_class": "HARD_VERIFIER_REJECT", "validation": validation})
            finish_turn(); continue
        # A valid seed is always an edit, even when its prerequisites form
        # another ProgramGroup that needs its own canonical inference.
        if forms.get(seed) == f:
            disposition(seed, "NO_SEMANTIC_CHANGE")
        else:
            edits[seed] = f
            disposition(seed, "WRITES_SCHEDULED")
        closure_members = m.proposal_precedents(f, seed) & auth
        closure_members |= set(m.closure.ancestors_within(seed, graph, auth))
        unit = {"seed": list(seed), "execution_members": [list(c) for c in sorted({seed} | closure_members)], "groups": [], "refused": []}
        assert {seed} | closure_members <= auth
        if group and seed in {tuple(c) for c in group["member_cells"]}:
            unit["groups"].append(group)
            unit["execution_members"] = [list(c) for c in sorted({seed} | closure_members | {tuple(c) for c in group["member_cells"]})]
            for raw in group["member_cells"]:
                member = tuple(raw)
                if member == seed or member in done:
                    continue
                try:
                    translated = m.program_group.translate(f, seed, member)
                except Exception as exc:
                    disposition(member, "TRANSLATION_FAILURE", origin=list(seed))
                    failures.append({"cell": list(member), "failure_class": "TRANSLATION_FAILURE", "detail": str(exc)})
                    continue
                target = m.target_from_id(plan["spine"], key(member), task_key, meta[member]["obligation_id"])
                check = m.validate_formula(task_key, target, translated, cache, plan["spine"])
                if check.get("hard_verifier_result") == "HARD_ACCEPT":
                    if forms.get(member) == translated:
                        disposition(member, "NO_SEMANTIC_CHANGE", origin=list(seed))
                    else:
                        edits[member] = translated
                        disposition(member, "TRANSLATED_WRITE_SCHEDULED", origin=list(seed))
                else:
                    disposition(member, "REJECTED_HARD_TRANSLATION", origin=list(seed))
                    failures.append({"cell": list(member), "failure_class": "HARD_VERIFIER_REJECT", "validation": check})
        checkpoint["units"].append(unit)
        # Dependency membership schedules work; it never marks it solved.
        for member in sorted(closure_members - done):
            enqueue(member)
        finish_turn()
    flush()
    demand = checkpoint.get("demand_accounting", {})
    return {"authorized_targets": len(auth), "canonical_decisions": list(sessions.values()), "translated_formula_instances": [{"cell": list(c), "formula": f} for c, f in sorted(edits.items())], "groups": checkpoint["units"], "eligible_program_groups": groups, "group_refusals": refused, "failures": failures, "dispositions": checkpoint["dispositions"], "unresolved_authorised_targets": state["unresolved_authorised_targets"], "edits": state["completed_edits"], "stochastic_formula_decisions": len(sessions), "translated_count": sum(v["status"] == "TRANSLATED_WRITE_SCHEDULED" for v in checkpoint["dispositions"].values()), **demand}
