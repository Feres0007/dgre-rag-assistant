import pytest
from decimal import Decimal
from dgre_rag.answers.service import Service,validate_answer
from dgre_rag.storage.database import connect,active_release,integrity
from dgre_rag.analytics.engine import calculate,DataError
from dgre_rag.domain.models import Period

pytestmark=pytest.mark.skipif(not active_release(),reason='Une release réelle est nécessaire')


@pytest.mark.parametrize('question,value,metric,page',[
 ('Quel est le maximum journalier de Pont de Bizerte en 2022-2023 ?','30.86','discharge_daily_max',18),
 ('Quel est le maximum instantané de Pont de Bizerte en 2022-2023 ?','32.4','discharge_instant_max',18),
 ('Quel est le minimum journalier de Pont de Bizerte en 2022-2023 ?','0.843','discharge_daily_min',18),
 ('Quel est le débit moyen annuel de Pont de Bizerte en 2022-2023 ?','14.99','discharge_annual_mean',18),
 ('Quel est le volume annuel de Pont de Bizerte en 2022-2023 ?','471.31','volume_annual',18),
 ('Quel est le maximum historique de Pont de Bizerte ?','294','discharge_historical_max',18),
 ('Quel est le total annuel à Amdoun en 2022-2023 ?','427.5','rainfall_annual',50),
 ('Quel est le total annuel à BELIF en 2022-2023 ?','740.4','rainfall_annual',50),
 ('Quel est le total annuel à BOU BRIMA en 2022-2023 ?','677.5','rainfall_annual',50),
])
def test_real_reference(question,value,metric,page):
    answer=Service().ask(question,use_llm=False)
    assert answer.status=='answered',answer.text
    assert len(answer.facts)==1
    assert answer.facts[0]['value_decimal']==value
    assert answer.facts[0]['metric_id']==metric
    assert any(c['page_pdf']==page and c.get('role')=='value' for c in answer.citations)


def test_corpus_count_and_integrity():
    with connect() as db:
        integrity(db)
        assert [r[0] for r in db.execute('SELECT page_count FROM documents ORDER BY document_id')]==[145,242]
        assert db.execute('SELECT count(*) FROM page_inventory').fetchone()[0]==387
        assert not db.execute("SELECT 1 FROM documents WHERE document_id NOT IN ('hydro_2022_2023','pluvio_2022_2023')").fetchall()


def test_conflicting_cells_excluded():
    with connect() as db:
        conflicts=db.execute("SELECT observation_id FROM quality_issues WHERE code='SOURCE_CONFLICT'").fetchall()
        if not conflicts:
            # V2 separates stations sharing a code; their distinct values are not
            # contradictory observations of one station any more.
            assert db.execute("SELECT count(*) FROM quality_issues WHERE code='SHARED_CODE'").fetchone()[0]>0
        for r in conflicts:assert not db.execute('SELECT 1 FROM published_observations WHERE observation_id=?',(r[0],)).fetchone()


def test_database_readonly():
    import sqlite3
    with connect() as db:
        with pytest.raises(sqlite3.OperationalError):db.execute('DELETE FROM documents')


def test_source_page_and_invalid_document():
    srv=Service()
    answer=srv.ask('Quel est le total annuel à Amdoun en 2022-2023 ?',use_llm=False)
    c=answer.citations[0]
    rendered=srv.get_source_page(c['document_id'],c['page_pdf'],c['source_id'])
    assert rendered['image'].startswith(b'\x89PNG')
    with pytest.raises(ValueError):srv.get_source_page('../secrets',1)
    with pytest.raises(ValueError):srv.get_source_page(c['document_id'],500)
    with pytest.raises(ValueError):srv.get_source_page(c['document_id'],1,c['source_id'])


def test_tampered_fact_is_rejected():
    srv=Service();answer=srv.ask('Quel est le total annuel à Amdoun en 2022-2023 ?',use_llm=False)
    fact=answer.facts[0]
    with connect() as db:row=dict(db.execute('SELECT * FROM published_observations WHERE observation_id=?',(fact['observation_id'],)).fetchone())
    answer.facts[0]['value_decimal']='999'
    with pytest.raises(ValueError,match='UNSUPPORTED_CLAIM'):validate_answer(answer,[row])


def test_tampered_text_is_rejected():
    srv=Service();answer=srv.ask('Quel est le total annuel à Amdoun en 2022-2023 ?',use_llm=False)
    with connect() as db:row=dict(db.execute('SELECT * FROM published_observations WHERE observation_id=?',(answer.facts[0]['observation_id'],)).fetchone())
    answer.text=answer.text.replace('427,5','999,9')
    with pytest.raises(ValueError,match='ALTERED_NUMERIC_TEXT'):validate_answer(answer,[row])


def test_default_year_preserves_metric_clarification():
    assert Service().ask('Quel est le total annuel à Amdoun ?',use_llm=False).status=='answered'
    assert Service().ask('Quel est le maximum de Pont de Bizerte en 2022-2023 ?',use_llm=False).status=='ambiguous'


def test_export_has_same_provenance():
    srv=Service();answer=srv.ask('Quel est le total annuel à Amdoun en 2022-2023 ?',use_llm=False)
    text=srv.export_answer(answer)
    assert answer.text in text and answer.citations[0]['source_id'] in text and answer.release_id in text
    assert 'C:\\Users' not in text


@pytest.mark.parametrize('question',[
    'Quelle est la pluviométrie annuelle de la station Aïn Draham en 2022-2023 ?',
    'Quelle est la pluviométrie annuelle de la station Ain-Draham en 2022-2023 ?',
    'Quelles sont les précipitations annuelles à Aïn Draham en 2022-2023 ?',
    'Combien de pluie est tombée à Aïn Draham en 2022-2023 ?',
    'Quelle est la pluviométrie à Aïn Draham en 2022-2023 ?',
])
def test_annual_rain_question_answers_from_table(question,monkeypatch):
    # The reference is printed in the right-hand station table, PDF page 59.
    # Neither a passage title nor an LLM response may substitute for the value.
    def no_documentary_fallback(*args,**kwargs):
        raise AssertionError('Cette question doit consulter la valeur structurée')
    monkeypatch.setattr('dgre_rag.answers.service.retrieve',no_documentary_fallback)
    answer=Service().ask(question,use_llm=False)
    assert answer.status=='answered',answer.text
    assert len(answer.facts)==1
    assert answer.facts[0]['value_decimal']=='1178'
    assert answer.facts[0]['metric_id']=='rainfall_annual'
    assert '1\u202f178 mm' in answer.text
    assert '1 septembre 2022 au 31 août 2023' in answer.text
    assert 'Annuaire pluviométrique de la Tunisie 2022–2023, page PDF 59' in answer.text
    assert any(c.get('role')=='value' and c['raw_text']=='1178' and c['page_pdf']==59 for c in answer.citations)
    assert not any(c['source_id'] in answer.text for c in answer.citations)
    assert 'Extrait du document' not in answer.text


def test_annual_rain_missing_station_and_year():
    assert Service().ask('Quelle est la pluviométrie annuelle en 2022-2023 ?',use_llm=False).status=='ambiguous'
    assert Service().ask('Quelle est la pluviométrie annuelle à Aïn Draham ?',use_llm=False).status=='answered'


def test_rain_definition_remains_documentary():
    from dgre_rag.query.planner import plan_query
    plan=plan_query('Que signifie la pluviométrie annuelle ?',active_release(),use_llm=False)
    assert plan.operations[0].op=='retrieve_text'


def test_conversation_keeps_measure_and_period():
    srv=Service()
    first=srv.ask('Quelle est la pluviométrie annuelle à Aïn Draham en 2022-2023 ?',use_llm=False)
    second=srv.ask('Et à Amdoun ?',use_llm=False,history=[first.model_dump()])
    assert second.status=='answered',second.text
    assert second.facts[0]['value_decimal']=='427.5'
    assert second.facts[0]['metric_id']=='rainfall_annual'
    assert 'Amdoun' in second.text
    unknown=srv.ask('Et à Paris ?',use_llm=False,history=[first.model_dump()])
    assert unknown.status=='ambiguous'


def test_documentary_failure_keeps_source_without_invention(monkeypatch):
    from dgre_rag.answers import service
    def unavailable(*args,**kwargs):raise RuntimeError('MODEL_UNAVAILABLE')
    monkeypatch.setattr('dgre_rag.answers.writing.write_documentary',unavailable)
    with connect() as db:
        passage=dict(db.execute("SELECT * FROM sources WHERE document_id='pluvio_2022_2023' AND page_pdf=48 AND kind='page'").fetchone())
    passage['text']=passage['raw_text']
    monkeypatch.setattr(service,'retrieve',lambda *a,**k:([passage],[]))
    answer=Service().ask('Que signifie la couleur grise ?')
    assert answer.status=='answered'
    assert 'gris' in answer.text.lower() and answer.limits
    assert 'MODEL_UNAVAILABLE' not in answer.text
