"""Edit Plan V1: closed-world set expressions over an immutable workbook DB.

No task semantics, golden data, ranking, or model calls live in this module.
Unstored coordinates within compiled sheet bounds are implicit blank cells.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from collections import defaultdict
import jsonschema
from workbook_spine_sqlite import canonical_cell_id, canonical_sheet_id


def obj(properties, required):
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


STR = {"type": "string", "minLength": 1}
INT = {"type": "integer", "minimum": 1}
EXPR = {"$ref": "#/$defs/set"}


def atom(kind, props, required):
    return obj({"kind": {"const": kind}, **props}, ["kind", *required])


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **obj({"operations": {"type": "array", "items": {"$ref": "#/$defs/operation"}}}, ["operations"]),
    "$defs": {
        "set": {"oneOf": [
            atom("CELL", {"cell_id": STR}, ["cell_id"]),
            atom("SHEET", {"sheet_id": STR}, ["sheet_id"]),
            atom("RECTANGLE", {"sheet_id": STR, **{k: INT for k in ("r1", "c1", "r2", "c2")}}, ["sheet_id", "r1", "c1", "r2", "c2"]),
            atom("ROW_INTERVAL", {"sheet_id": STR, **{k: INT for k in ("row_start", "row_end", "col_start", "col_end")}}, ["sheet_id", "row_start", "row_end"]),
            atom("COLUMN_INTERVAL", {"sheet_id": STR, **{k: INT for k in ("row_start", "row_end", "col_start", "col_end")}}, ["sheet_id", "col_start", "col_end"]),
            atom("TEMPORAL_INTERVAL", {"sheet_id": STR, "axis": {"enum": ["row", "column"]}, "start_coordinate": STR, "end_coordinate": STR,
                 "row_constraint": obj({"r1": INT, "r2": INT}, ["r1", "r2"])}, ["sheet_id", "axis", "start_coordinate", "end_coordinate"]),
            atom("FORMULA_CLASS_MEMBERS", {"fingerprint_id": STR, "sheet_id": STR}, ["fingerprint_id"]),
            *[atom(k, {"sets": {"type": "array", "minItems": 1, "items": EXPR}}, ["sets"]) for k in ("UNION", "INTERSECT")],
            atom("DIFFERENCE", {"sets": {"type": "array", "minItems": 2, "maxItems": 2, "items": EXPR}}, ["sets"]),
        ]},
        "operation": obj({
            "operation_id": STR, "obligation_id": STR,
            "operation_kind": {"enum": ["SET_FORMULA", "FILL_FORMULA", "REPLACE_FORMULA", "CLEAR_CELL"]},
            "target_set": EXPR,
            "occupancy_filter": {"enum": ["BLANK_ONLY", "NONBLANK_ONLY", "FORMULA_ONLY", "NONFORMULA_ONLY"]},
            "source_relation": obj({"entity_ids": {"type": "array", "items": STR}}, ["entity_ids"]),
            "sequencing": obj({"after": {"type": "array", "items": STR, "uniqueItems": True}}, ["after"]),
            "explicit_exceptions": obj({"include": {"type": "array", "maxItems": 16, "items": STR}, "exclude": {"type": "array", "maxItems": 16, "items": STR}}, ["include", "exclude"]),
        }, ["operation_id", "obligation_id", "operation_kind", "target_set"]),
    },
}


class PlanError(ValueError):
    def __init__(self, category, detail):
        self.category = category
        super().__init__(detail)


class World:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        self.sheets = {r["sheet_id"]: dict(r) for r in self.db.execute("SELECT * FROM sheets")}
        self.cells = {r["cell_id"]: dict(r) for r in self.db.execute("SELECT * FROM cells")}
        self.temporal = {r["temporal_id"]: dict(r) for r in self.db.execute("SELECT * FROM temporal_coordinates")}
        self.classes = defaultdict(set)
        for r in self.db.execute("SELECT fingerprint_id,cell_id FROM formulas"):
            self.classes[r["fingerprint_id"]].add(r["cell_id"])
        # Identity namespaces the grounding contract exposes to the model. V1
        # validation ignored these, so plans citing real evidence were rejected.
        self.anchors = {r["anchor_id"]: r["cell_id"] for r in self.db.execute("SELECT anchor_id,cell_id FROM text_anchors")}
        self.rows = {r["row_id"] for r in self.db.execute("SELECT row_id FROM rows")}
        self.cols = {r["col_id"] for r in self.db.execute("SELECT col_id FROM columns")}
        self.workbooks = {r["workbook_id"] for r in self.db.execute("SELECT workbook_id FROM workbooks")}
        # Grounding names a period by its heading cell; the closure names the same
        # period by axis index. One row of temporal_coordinates carries both.
        # A heading cell can carry both a row-axis and a column-axis coordinate,
        # so a period id resolves per axis, never to one arbitrary winner.
        self.contract = "V1"
        self.periods = defaultdict(dict)
        for r in self.db.execute("SELECT temporal_id,cell_id,axis FROM temporal_coordinates"):
            if r["cell_id"]:
                self.periods["period:" + r["cell_id"].split(":", 1)[1]][r["axis"]] = r["temporal_id"]

    def close(self):
        self.db.close()

    def reference(self, eid, contract):
        """Validate one source_relation citation. Returns a canonical identity.

        V1 is the frozen contract: cells, sheets, formula classes, temporal
        coordinates. V2 additionally accepts the text-anchor, row, column,
        workbook and period identities that grounding actually puts in front of
        the model, resolving period ids onto their temporal coordinate.
        """
        if eid.startswith("cell:"):
            return self.cell(eid)
        if eid in self.sheets or eid in self.classes or eid in self.temporal:
            return eid
        if contract == "V2":
            if eid in self.anchors:
                return self.anchors[eid]
            if eid in self.rows or eid in self.cols or eid in self.workbooks:
                return eid
            # The spine mints a period id for every date-valued cell, while the
            # closure derives axis coordinates only where an axis is temporal. A
            # citation names the cell either way; only interval endpoints need
            # the coordinate, and temporal_endpoint still enforces that.
            if eid.startswith("period:"):
                return self.cell("cell:" + eid.split(":", 1)[1])
        raise PlanError("INVALID_ENTITY", f"Unknown source entity {eid}")

    def temporal_endpoint(self, eid, axis, contract):
        """A TEMPORAL_INTERVAL endpoint, accepting grounding's period naming under V2.

        The expression already declares its axis, so a period id that heads both a
        row and a column coordinate resolves without guessing.
        """
        if contract == "V2" and eid not in self.temporal and eid in self.periods:
            return self.periods[eid].get(axis, eid)
        return eid

    def sheet(self, sid):
        sid = canonical_sheet_id(sid)
        if sid not in self.sheets:
            raise PlanError("INVALID_ENTITY", f"Unknown sheet {sid}")
        return sid

    def cell(self, cid):
        cid = canonical_cell_id(cid)
        if not cid:
            raise PlanError("INVALID_ENTITY", "Invalid cell identity")
        _, sid, rr, cc = cid.split(":")
        sid = self.sheet(sid)
        r, c = int(rr[1:]), int(cc[1:])
        s = self.sheets[sid]
        # The persistent world represents implicit blanks by sheet bounds.
        if cid not in self.cells and not (s["used_r1"] <= r <= s["used_r2"] and s["used_c1"] <= c <= s["used_c2"]):
            raise PlanError("INVALID_ENTITY", f"Cell outside compiled world: {cid}")
        return cid

    def rectangle(self, sid, r1, c1, r2, c2):
        sid = self.sheet(sid)
        if r1 > r2 or c1 > c2:
            raise PlanError("UNREPRESENTABLE_EXPRESSION", "Reversed bounds")
        self.cell(f"cell:{sid[6:]}:r{r1}:c{c1}")
        self.cell(f"cell:{sid[6:]}:r{r2}:c{c2}")
        return {f"cell:{sid[6:]}:r{r}:c{c}" for r in range(r1, r2+1) for c in range(c1, c2+1)}

    def expression(self, x, path="target_set"):
        k = x["kind"]
        if k in ("UNION", "INTERSECT", "DIFFERENCE"):
            children = [self.expression(y, f"{path}.sets[{i}]") for i, y in enumerate(x["sets"])]
            result = set(children[0])
            for child in children[1:]:
                result = result | child.keys() if k == "UNION" else result & child.keys() if k == "INTERSECT" else result - child.keys()
            return {cid: sorted({p for ch in children for p in ch.get(cid, [])} | {path}) for cid in result}
        if k == "CELL":
            ids = {self.cell(x["cell_id"])}
        elif k == "FORMULA_CLASS_MEMBERS":
            fp = x["fingerprint_id"]
            if fp not in self.classes:
                raise PlanError("INVALID_ENTITY", f"Unknown fingerprint {fp}")
            ids = self.classes[fp].copy()
            if "sheet_id" in x:
                sid = self.sheet(x["sheet_id"])
                ids = {c for c in ids if c.startswith(f"cell:{sid[6:]}:")}
        else:
            sid = self.sheet(x["sheet_id"])
            s = self.sheets[sid]
            r1, c1, r2, c2 = (s[f"used_{p}"] for p in ("r1", "c1", "r2", "c2"))
            if k == "RECTANGLE":
                r1, c1, r2, c2 = (x[p] for p in ("r1", "c1", "r2", "c2"))
            elif k in ("ROW_INTERVAL", "COLUMN_INTERVAL"):
                r1, r2, c1, c2 = (x.get(p, d) for p, d in zip(("row_start", "row_end", "col_start", "col_end"), (r1, r2, c1, c2)))
            elif k == "TEMPORAL_INTERVAL":
                ends = [self.temporal.get(self.temporal_endpoint(x[p], x["axis"], self.contract)) for p in ("start_coordinate", "end_coordinate")]
                if any(not t or t["sheet_id"] != sid or t["axis"] != x["axis"] for t in ends):
                    raise PlanError("INVALID_ENTITY", "Temporal endpoints must share sheet and axis")
                def period(t):
                    if t["year"] is None:
                        raise PlanError("UNREPRESENTABLE_EXPRESSION", "Temporal endpoint lacks ordered year")
                    return (t["year"], t["month"] or ((t["quarter"]-1)*3+1 if t["quarter"] else 0))
                lo, hi = map(period, ends)
                if lo > hi:
                    raise PlanError("UNREPRESENTABLE_EXPRESSION", "Reversed temporal interval")
                indices = {t["axis_index"] for t in self.temporal.values() if t["sheet_id"] == sid and t["axis"] == x["axis"] and t["year"] is not None and t["axis_index"] is not None and lo <= period(t) <= hi}
                constraint = x.get("row_constraint", {})
                r1, r2 = constraint.get("r1", r1), constraint.get("r2", r2)
                ids = set()
                for i in sorted(indices):
                    ids |= self.rectangle(sid, r1, i, r2, i) if x["axis"] == "column" else self.rectangle(sid, i, c1, i, c2) if r1 <= i <= r2 else set()
                return {cid: [path] for cid in ids}
            ids = self.rectangle(sid, r1, c1, r2, c2)
        return {cid: [path] for cid in ids}

    def filter(self, ids, kind):
        def accept(cid):
            k = self.cells.get(cid, {}).get("kind", "blank")
            return {None: True, "BLANK_ONLY": k == "blank", "NONBLANK_ONLY": k != "blank", "FORMULA_ONLY": k == "formula", "NONFORMULA_ONLY": k != "formula"}[kind]
        return {cid for cid in ids if accept(cid)}


def expand_edit_plan(plan, world, obligation_ids=None, id_contract="V1"):
    """Expand a plan. id_contract selects which citation identities are legal.

    V1 is the frozen contract the primary run validated against. V2 accepts every
    closed-world identity namespace the grounding contract exposes to the model.
    Neither contract changes the target-set algebra or which cells expand.
    """
    world.contract = id_contract
    try:
        jsonschema.Draft202012Validator(SCHEMA).validate(plan)
    except (jsonschema.ValidationError, TypeError) as exc:
        raise PlanError("INVALID_SCHEMA", str(exc)[:1200]) from exc
    ops = plan["operations"]
    opids = [o["operation_id"] for o in ops]
    if len(opids) != len(set(opids)):
        raise PlanError("INVALID_SCHEMA", "Duplicate operation_id")
    done, pending, ordered = set(), list(ops), []
    while pending:
        ready = [o for o in pending if set(o.get("sequencing", {}).get("after", [])) <= done]
        if not ready:
            raise PlanError("INVALID_SCHEMA", "Unknown predecessor or sequencing cycle")
        for o in ready:
            ordered.append(o); pending.remove(o); done.add(o["operation_id"])
    provenance, expansions = defaultdict(list), []
    for o in ordered:
        if obligation_ids is not None and o["obligation_id"] not in obligation_ids:
            raise PlanError("INVALID_ENTITY", "Unknown obligation")
        for eid in o.get("source_relation", {}).get("entity_ids", []):
            world.reference(eid, id_contract)
        ex = o.get("explicit_exceptions", {"include": [], "exclude": []})
        if len(ex["include"]) + len(ex["exclude"]) > 16:
            raise PlanError("EXCESSIVE_EXCEPTION_ENUMERATION", "At most 16 combined exceptions per operation")
        found = world.expression(o["target_set"])
        ids = world.filter(found, o.get("occupancy_filter"))
        include, exclude = ({world.cell(cid) for cid in ex[k]} for k in ("include", "exclude"))
        ids = (ids | include) - exclude
        for cid in sorted(ids):
            provenance[cid].append({"operation_id": o["operation_id"], "target_set_clauses": found.get(cid, []), "filter_clause": o.get("occupancy_filter"), "exception_clause": "include" if cid in include else None})
        expansions.append({"operation_id": o["operation_id"], "obligation_id": o["obligation_id"], "operation_kind": o["operation_kind"], "cell_ids": sorted(ids)})
    return {"status": "VALID_PLAN" if provenance else "EMPTY_EXPANSION", "cell_ids": sorted(provenance), "operations": expansions, "provenance": dict(provenance)}
