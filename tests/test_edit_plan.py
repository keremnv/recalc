import sqlite3
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
from workbook_spine_sqlite import SCHEMA_SQL
from edit_plan import World, PlanError, expand_edit_plan


@pytest.fixture
def world(tmp_path):
    path = tmp_path / "world.sqlite"
    db = sqlite3.connect(path)
    db.executescript(SCHEMA_SQL)
    db.execute("INSERT INTO sheets VALUES ('sheet:s00','wb',0,'Test','test','visible',1,1,5,5)")
    for r,c,k in [(1,1,'text'),(2,2,'formula'),(3,2,'numeric')]:
        db.execute("INSERT INTO cells VALUES (?,?,?,?,?,?,?,?,?,?)",(f'cell:s00:r{r}:c{c}','sheet:s00',f'row:s00:r{r}',f'col:s00:c{c}',r,c,f'B{r}',k,None,None))
    db.execute("INSERT INTO formulas VALUES ('formula:s00:r2:c2','cell:s00:r2:c2','=1','fp1',0)")
    for idx, year in [(2,2023),(4,2024)]:
        db.execute("INSERT INTO temporal_coordinates (temporal_id,sheet_id,axis,axis_index,year) VALUES (?,?,?,?,?)",(f't{idx}','sheet:s00','column',idx,year))
    db.commit();db.close()
    w=World(path)
    yield w
    w.close()


def plan(expr, **extra):
    return {'operations':[{'operation_id':'op1','obligation_id':'O1','operation_kind':'SET_FORMULA','target_set':expr,**extra}]}


def test_sparse_blank_filter_and_exceptions(world):
    p=plan({'kind':'RECTANGLE','sheet_id':'sheet:s00','r1':1,'c1':1,'r2':3,'c2':2},occupancy_filter='BLANK_ONLY',explicit_exceptions={'include':['cell:sheet:s00:r3:c2'],'exclude':['cell:s00:r1:c2']})
    result=expand_edit_plan(p,world,{'O1'})
    assert set(result['cell_ids'])=={'cell:s00:r2:c1','cell:s00:r3:c1','cell:s00:r3:c2'}
    assert result['provenance']['cell:s00:r3:c2'][0]['exception_clause']=='include'
    assert result==expand_edit_plan(p,world,{'O1'})


def test_set_algebra_matches_independent_enumeration(world):
    a={'kind':'ROW_INTERVAL','sheet_id':'sheet:s00','row_start':2,'row_end':3}
    b={'kind':'COLUMN_INTERVAL','sheet_id':'sheet:s00','col_start':2,'col_end':3}
    x={'kind':'DIFFERENCE','sets':[{'kind':'INTERSECT','sets':[a,b]},{'kind':'FORMULA_CLASS_MEMBERS','fingerprint_id':'fp1'}]}
    assert set(expand_edit_plan(plan(x),world)['cell_ids'])=={'cell:s00:r2:c3','cell:s00:r3:c2','cell:s00:r3:c3'}


def test_temporal_is_materialized_identity_not_between_column_fill(world):
    x={'kind':'TEMPORAL_INTERVAL','sheet_id':'sheet:s00','axis':'column','start_coordinate':'t2','end_coordinate':'t4','row_constraint':{'r1':3,'r2':3}}
    assert expand_edit_plan(plan(x),world)['cell_ids']==['cell:s00:r3:c2','cell:s00:r3:c4']


@pytest.mark.parametrize('expr',[
    {'kind':'CELL','cell_id':'cell:s99:r1:c1'},
    {'kind':'CELL','cell_id':'cell:s00:r99:c1'},
    {'kind':'RECTANGLE','sheet_id':'sheet:s00','r1':3,'c1':1,'r2':2,'c2':2},
    {'kind':'UNION','sets':[]},
    {'kind':'LIKELY_FORECAST'},
])
def test_invalid_never_partially_expands(world,expr):
    with pytest.raises(PlanError): expand_edit_plan(plan(expr),world)


def test_exception_cap_and_sequence_cycle(world):
    p=plan({'kind':'SHEET','sheet_id':'sheet:s00'}, explicit_exceptions={'include':['cell:s00:r1:c1']*9,'exclude':['cell:s00:r1:c2']*8})
    with pytest.raises(PlanError,match='16 combined'):expand_edit_plan(p,world)
    p=plan({'kind':'SHEET','sheet_id':'sheet:s00'},sequencing={'after':['op1']})
    with pytest.raises(PlanError,match='cycle'):expand_edit_plan(p,world)


def test_model_guard():
    from end_to_end_composition_probe import guard
    guard('z-ai/glm-5.3-flash')
    for model in ['openai/gpt-5.6','GPT-5.6 Sol','z-ai/glm-5','other']:
        with pytest.raises(RuntimeError): guard(model)


def test_rectangle_cover_roundtrip_random_masks():
    import random
    from edit_plan_probe import rectangle_cover
    rng=random.Random(712)
    for _ in range(100):
        cells={f'cell:s00:r{r}:c{c}' for r in range(1,12) for c in range(1,9) if rng.random()<.4}
        rectangles=rectangle_cover(cells)
        reconstructed={f"cell:{x['sheet_id'][6:]}:r{r}:c{c}" for x in rectangles for r in range(x['r1'],x['r2']+1) for c in range(x['c1'],x['c2']+1)}
        assert reconstructed==cells
