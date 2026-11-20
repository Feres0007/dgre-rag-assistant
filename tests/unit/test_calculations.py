from decimal import Decimal
import pytest
from dgre_rag.analytics.engine import calculate,compare_rows,DataError
from dgre_rag.domain.models import Period


def row(value,start='2023-01-01',end=None,**kwargs):
    return dict(observation_id=start,entity_id='synthetic-station',metric_id='discharge_daily_mean',
                period_start=start,period_end=end or start,value_decimal=value,unit='m3/s',missing_days=0,**kwargs)


def test_volume_unit_conversion():
    result=calculate('daily_discharge_volume',[row('10'),row('20','2023-01-02')],Period(start='2023-01-01',end='2023-01-02'))
    assert Decimal(result['value'])==Decimal('2.592') and result['unit']=='hm3'


def test_weighted_mean_not_mean_of_months():
    a=row('10','2023-01-01','2023-01-31');b=row('20','2023-02-01','2023-02-28')
    a['metric_id']=b['metric_id']='discharge_monthly_mean'
    result=calculate('time_weighted_mean',[a,b],Period(start='2023-01-01',end='2023-02-28'))
    assert abs(Decimal(result['value'])-Decimal(870)/59)<Decimal('1e-25')


def test_incomplete_total_rejected():
    with pytest.raises(DataError,match='INCOMPLETE'):
        calculate('daily_discharge_volume',[row('10')],Period(start='2023-01-01',end='2023-01-02'))


def test_duplicate_dates_rejected():
    with pytest.raises(DataError,match='OVERLAPPING'):calculate('maximum',[row('1'),row('2')])


def test_extreme_ties_and_partial_label():
    r=calculate('maximum',[row('3'),row('3','2023-01-03')],Period(start='2023-01-01',end='2023-01-03'))
    assert r['dates']==['2023-01-01','2023-01-03']
    assert not r['coverage']['complete'] and r['limits']


def test_spatial_rainfall_sum_rejected():
    a=row('1');b=row('2','2023-01-02');b['entity_id']='other'
    with pytest.raises(DataError,match='SPATIAL'):calculate('rainfall_sum',[a,b])


@pytest.mark.parametrize('field,value',[('unit','L/s'),('metric_id','rainfall_daily'),('baseline_id','different')])
def test_incompatible_comparison(field,value):
    a=row('1');b=row('2');b[field]=value
    with pytest.raises(DataError):compare_rows(a,b)


def test_reference_must_be_positive_and_sourced():
    with pytest.raises(DataError,match='INVALID_REFERENCE'):compare_rows(row('10'),row('0'),'relative_anomaly')
    with pytest.raises(DataError,match='BASELINE_REQUIRED'):compare_rows(row('10'),row('5'),'relative_anomaly')


def test_decimal_difference_exact():
    assert compare_rows(row('0.3'),row('0.1'))['value']=='0.2'

