from datetime import date
from decimal import Decimal
import json
import pytest
import pymupdf
from pydantic import ValidationError
from dgre_rag.analytics.engine import calculate,DataError,interpolate_rating,runoff_depth
from dgre_rag.domain.models import Operation,QueryPlan,Period
from dgre_rag.storage.database import initialize,publish,active_release,restore
from dgre_rag.ingestion.pipeline import Extractor,month_period


def row(day,value='10',**extra):
    return dict(observation_id=day,entity_id='station',metric_id='rainfall_daily',
        period_start=day,period_end=day,value_decimal=value,unit='mm',quality_status='validated',**extra)


def test_partial_sum_is_explicit_not_extrapolated():
    result=calculate('rainfall_sum',[row('2024-02-28'),row('2024-02-29','20')],
        Period(start='2024-02-28',end='2024-03-01'),allow_partial=True)
    assert Decimal(result['value'])==30
    assert result['coverage']=={'expected':3,'available':2,'valid':2,'complete':False,'missing':1}
    assert result['limits'] and result['input_ids']==['2024-02-28','2024-02-29']


@pytest.mark.parametrize('comparator,expected',[('gt',1),('ge',2),('lt',1),('le',2),('eq',1)])
def test_free_threshold_boundary(comparator,expected):
    result=calculate('threshold_count',[row('2023-01-01','9'),row('2023-01-02','10'),row('2023-01-03','11')],
        options={'threshold':'10','comparator':comparator})
    assert Decimal(result['value'])==expected


def test_gap_breaks_dry_sequence_and_preserves_ties():
    rows=[row(d,'0') for d in ('2023-01-01','2023-01-02','2023-01-04','2023-01-05')]
    result=calculate('longest_run',rows,Period(start='2023-01-01',end='2023-01-05'),options={'threshold':'0','comparator':'eq'})
    assert result['value']=='2'
    assert result['dates']==[('2023-01-01','2023-01-02'),('2023-01-04','2023-01-05')]
    assert not result['coverage']['complete']


def test_empty_and_outside_window_blocked():
    with pytest.raises(DataError,match='NOT_FOUND'):calculate('rainfall_sum',[],allow_partial=True)
    with pytest.raises(DataError,match='OUTSIDE_PERIOD'):
        calculate('rainfall_sum',[row('2023-01-01')],Period(start='2023-01-02',end='2023-01-03'),allow_partial=True)


def test_rank_across_stations_does_not_sum_values():
    a=row('2023-01-01','2');b=dict(row('2023-01-01','5'),entity_id='other',observation_id='other')
    result=calculate('rank',[a,b])
    assert result['selected_ids']==['other','2023-01-01']
    assert result['coverage']['kind']=='available_catalogue' and result['value']=='2'
    with pytest.raises(DataError,match='SPATIAL'):calculate('rainfall_sum',[a,b])


def test_monthly_mean_with_unknown_daily_coverage_is_blocked():
    r=dict(row('2023-01-01'),metric_id='discharge_monthly_mean',unit='m3/s',period_end='2023-01-31',missing_days=2)
    with pytest.raises(DataError,match='UNKNOWN_MEAN_DURATION'):
        calculate('time_weighted_mean',[r],allow_partial=True)


def test_campaign_calendar_leap_year():
    assert month_period(5,2023)==('2024-02-01','2024-02-29')


@pytest.mark.parametrize('payload',[
    {'op':'calculate','entity_id':'e','metric_id':'rainfall_daily','period':{'start':'2023-01-01','end':'2023-01-02'},'formula_id':'threshold_count'},
    {'op':'retrieve_text','evidence_required':False},
    {'op':'retrieve_text','filters':{'sql':'DROP TABLE observations'}},
])
def test_plan_rejects_missing_parameters_and_escape_hatches(payload):
    with pytest.raises(ValidationError):Operation.model_validate(payload)


@pytest.mark.parametrize('operations',[
    [dict(op='retrieve_text',step_id='a',depends_on=['a'])],
    [dict(op='retrieve_text',step_id='a',depends_on=['b']),dict(op='retrieve_text',step_id='b',depends_on=['a'])],
    [dict(op='retrieve_text',step_id='a'),dict(op='retrieve_text',step_id='a')],
])
def test_dependency_cycles_duplicates_and_forward_references_rejected(operations):
    with pytest.raises(ValidationError):QueryPlan(operations=operations)


def test_ordered_dependencies_allowed():
    assert QueryPlan(operations=[Operation(op='retrieve_text',step_id='a'),Operation(op='retrieve_text',depends_on=['a'])])


def test_numeric_metadata_filter_cannot_be_silently_ignored():
    with pytest.raises(ValidationError,match='UNSUPPORTED_NUMERIC_FILTER'):
        Operation(op='lookup',entity_id='e',metric_id='rainfall_daily',period=Period(start='2023-01-01',end='2023-01-01'),filters={'basin':'another basin'})


def points():
    return [dict(curve_id='curve',height=h,discharge=q,height_unit='m',discharge_unit='m3/s',
        quality_status='validated',evidence_ids=[h],valid_from='2022-09-01',valid_to='2023-08-31') for h,q in [('1','2'),('2','6')]]


def test_rating_estimate_exact_and_outside_range():
    result=interpolate_rating('1.5',points(),'2023-01-01','curve')
    assert result['value']=='4.0' and result['origin']=='estimated' and len(result['evidence_ids'])==2
    assert interpolate_rating('1',points(),'2023-01-01','curve')['origin']=='published'
    with pytest.raises(DataError,match='EXTRAPOLATION'):interpolate_rating('3',points(),'2023-01-01','curve')
    with pytest.raises(DataError,match='VALIDITY'):interpolate_rating('1.5',points(),'2024-01-01','curve')


def test_rating_ambiguous_branch_rejected():
    p=points();p[1]['height']='1'
    with pytest.raises(DataError,match='AMBIGUOUS_CURVE'):interpolate_rating('1',p,'2023-01-01','curve')


def test_runoff_requires_validated_area_and_matching_basin():
    v=dict(observation_id='v',value_decimal='6.333',unit='hm3',basin_id='b',quality_status='validated',evidence_ids=['pv'])
    a=dict(observation_id='a',value_decimal='748.3',unit='km2',basin_id='b',quality_status='validated',evidence_ids=['pa'])
    assert abs(Decimal(runoff_depth(v,a)['value'])-Decimal('8.46318'))<Decimal('.00001')
    a['basin_id']='other'
    with pytest.raises(DataError,match='BASIN'):runoff_depth(v,a)
    a['basin_id']='b';a['quality_status']='candidate'
    with pytest.raises(DataError,match='UNVALIDATED'):runoff_depth(v,a)


def test_shared_code_is_not_identity_and_duplicate_keeps_proofs(tmp_path):
    db=initialize(tmp_path/'db.sqlite')
    document={'document_id':'p','original_name':'2022-2023.pdf'}
    db.execute("INSERT INTO documents VALUES ('p','2022-2023.pdf',?,1,'2022-2023')",('a'*64,))
    with pymupdf.open() as pdf:
        page=pdf.new_page();worker=Extractor(db,document,page,1)
        s1=worker.source((0,0,50,20),'OULED BOUSAAD','table');s2=worker.source((0,30,50,50),'OULED HADJ','table')
        a=worker.entity('1488496361','OULED BOUSAAD',s1,'rain_station')
        b=worker.entity('1488496361','OULED HADJ',s2,'rain_station')
        assert a!=b
        assert worker.entity('1488496361','OULED BOUSAAD',s2,'rain_station')==a
        assert db.execute("SELECT count(*) FROM quality_issues WHERE code='SHARED_CODE'").fetchone()[0]
    db.close()


def test_candidate_publication_preserves_active_release(tmp_path,monkeypatch):
    monkeypatch.setenv('DGRE_ROOT',str(tmp_path))
    for run in ('first','candidate'):
        db=initialize(tmp_path/f'data/runs/{run}/database.sqlite')
        db.execute("INSERT INTO run_metadata VALUES ('validated','true')")
        db.execute("INSERT INTO run_metadata VALUES ('test',?)",(run,));db.commit();db.close()
    first=publish('first');second=publish('candidate',activate=False)
    assert active_release()==first and first!=second
    restore(second);assert active_release()==second
    restore(first);assert active_release()==first


def test_conflicting_measurements_still_block_after_identity_fix(tmp_path,monkeypatch):
    monkeypatch.setenv('DGRE_ROOT',str(tmp_path))
    db=initialize(tmp_path/'data/runs/conflict/database.sqlite')
    db.execute("INSERT INTO documents VALUES ('p','2022-2023.pdf',?,1,'2022-2023')",('a'*64,))
    db.execute("INSERT INTO metrics VALUES ('rainfall_daily','Pluie','mm','daily','[]')")
    with pymupdf.open() as pdf:
        page=pdf.new_page();worker=Extractor(db,{'document_id':'p','original_name':'2022-2023.pdf'},page,1)
        t1=worker.source((0,0,100,20),'table one','table');t2=worker.source((0,30,100,50),'table two','table')
        eid=worker.entity('1480000000','SAME STATION',t1,'rain_station')
        worker.observation(eid,'rainfall_daily','10',(0,0,30,20),t1,'2023-01-01','2023-01-01')
        worker.observation(eid,'rainfall_daily','20',(0,30,30,50),t2,'2023-01-01','2023-01-01')
    db.commit();db.close()
    from dgre_rag.ingestion.pipeline import validate
    report=validate('conflict')
    assert report['conflicts']==2 and report['published']==0 and report['blocked']==2
