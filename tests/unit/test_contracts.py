from datetime import date
import pytest
from pydantic import ValidationError
from dgre_rag.domain.models import Period,QueryPlan,Operation,SourceRef,number,Coverage


@pytest.mark.parametrize('start,end',[('2023-02-29','2023-03-01'),('2023-04-31','2023-05-01'),('2023-01-02','2023-01-01')])
def test_invalid_calendar(start,end):
    with pytest.raises(ValidationError):Period(start=start,end=end)


@pytest.mark.parametrize('raw,value,status', [('1,25','1.25','numeric'),('0','0','numeric'),('- ',None,'ambiguous_symbol'),('',None,'missing'),('-999',None,'special_code'),('NaN',None,'unparsed'),('Infinity',None,'unparsed')])
def test_symbols_are_not_guessed(raw,value,status):
    assert number(raw)==(value,status)


@pytest.mark.parametrize('payload',[{'sql':'DELETE FROM documents'},{'operations':[{'op':'shell'}]},{'operations':[{'op':'lookup'}]}, {'operations':[{'op':'retrieve_text','python':'print(1)'}]}])
def test_forbidden_plans(payload):
    with pytest.raises(ValidationError):QueryPlan.model_validate(payload)


@pytest.mark.parametrize('bbox',[(-1,0,2,2),(1,1,0,2),(0,0,float('inf'),2),(0,2,1,1)])
def test_invalid_source_geometry(bbox):
    with pytest.raises(ValidationError):SourceRef(source_id='x',document_id='y',page_pdf=1,bbox=bbox,raw_text='',block_type='cell')


def test_coverage_cannot_overstate():
    with pytest.raises(ValidationError):Coverage(expected=30,available=20,valid=25,unresolved=0)

