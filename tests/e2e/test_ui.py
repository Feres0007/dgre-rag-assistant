from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from dgre_rag.storage.database import active_release

pytestmark=pytest.mark.skipif(not active_release(),reason='Release nécessaire pour les parcours réels')
APP=Path(__file__).resolve().parents[2]/'app/streamlit_app.py'


@pytest.fixture(autouse=True)
def isolated_history(tmp_path,monkeypatch):
    monkeypatch.setenv('DGRE_UI_HISTORY_PATH',str(tmp_path/'conversations.sqlite'))


@pytest.mark.parametrize('page',['assistant','sources'])
def test_pages_render(page):
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    if page!='assistant':app.switch_page(f'pages/{page}.py').run()
    assert not app.exception,[e.message for e in app.exception]


def test_numeric_chat():
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    app.chat_input[0].set_value('Quel est le maximum journalier de Pont de Bizerte en 2022-2023 ?').run()
    assert not app.exception
    assert any('30,86' in m.value for m in app.markdown)


def test_service_changes_are_watched():
    from streamlit.file_util import file_in_pythonpath
    from dgre_rag.answers import service
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    assert not app.exception
    # The original failure combined a new page with an old cached service.
    # Streamlit must recognize this module outside app/ as a watched source.
    assert file_in_pythonpath(str(Path(service.__file__).resolve()))


def test_annual_rain_chat_readable_answer_and_table():
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    app.chat_input[0].set_value('Quelle est la pluviométrie annuelle de la station Aïn Draham en 2022-2023 ?').run()
    assert not app.exception
    assert any('1\u202f178 mm' in m.value and 'page PDF 59' in m.value for m in app.markdown)
    assert any('page PDF 59' in b.label for b in app.button)
    frame=app.dataframe[0].value
    assert 'Station' in frame.columns and 'Valeur' in frame.columns
    assert 'entity_id' not in frame.columns and 'observation_id' not in frame.columns
    source=next(b for b in app.button if 'page PDF 59' in b.label)
    source.click().run()
    assert not app.exception
    assert app.session_state['selected_source']['page_pdf']==59


def test_unified_chat_series_chart_sources_return():
    app=AppTest.from_file(str(APP),default_timeout=45).run()
    assert not app.selectbox
    if (APP.parent/'history.py').exists():
        assert len(app.text_input)==1 and app.text_input[0].label=='Rechercher une conversation'
    else:assert not app.text_input
    app.chat_input[0].set_value('Montre les pluies mensuelles à Aïn Draham en 2022-2023.').run()
    assert not app.exception
    assert len(app.session_state['messages'][-1]['table'])==12
    app.chat_input[0].set_value('Fais un graphique').run()
    assert not app.exception
    assert app.session_state['messages'][-1]['presentation']=='chart'
    count=len(app.session_state['messages'])
    next(b for b in app.button if 'page PDF 59' in b.label).click().run()
    assert not app.exception
    next(b for b in app.button if b.label=='Retour à la conversation').click().run()
    assert not app.exception and len(app.session_state['messages'])==count
    next(b for b in app.button if b.label=='Nouvelle conversation').click().run()
    assert not app.session_state['messages']


def test_only_chat_and_sources_pages_remain():
    assert {p.stem for p in (APP.parent/'pages').glob('*.py')}=={'assistant','sources'}


@pytest.mark.skipif(not (APP.parent/'history.py').exists(),reason='Interface historique restaurée')
def test_history_reopens_after_restart_and_renames():
    from history import History
    first=AppTest.from_file(str(APP),default_timeout=30).run()
    question='Combien de jours avec une pluie d’au moins 10 mm sont publiés pour Amdoun ?'
    first.chat_input[0].set_value(question).run()
    assert not first.exception
    cid=first.session_state['conversation_id']
    saved=first.session_state['messages'][0]
    assert saved['table'][0]['value_decimal']=='16'
    # A new session finds history without re-executing the saved question.
    second=AppTest.from_file(str(APP),default_timeout=30).run()
    next(b for b in second.button if b.key=='history-'+cid).click().run()
    assert not second.exception
    assert second.session_state['messages'][0]['run_id']==saved['run_id']
    next(t for t in second.text_input if t.label=='Titre').set_value('Analyse Amdoun')
    next(b for b in second.button if b.label=='Renommer').click().run()
    assert History().list('Analyse Amdoun')[0]['id']==cid
    next(c for c in second.checkbox if c.label=='Confirmer la suppression').check().run()
    next(b for b in second.button if b.label=='Supprimer la conversation').click().run()
    assert not second.exception and not second.session_state['messages']
    assert not History().list()


@pytest.mark.skipif(not (APP.parent/'history.py').exists(),reason='Interface historique restaurée')
def test_interrupted_request_not_automatically_executed():
    from history import History
    cid,tid=History().begin('Quel est le total annuel à Amdoun ?',active_release())
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    next(b for b in app.button if b.key=='history-'+cid).click().run()
    assert not app.exception and not app.session_state['messages']
    assert History().load(cid)[0]['answer'] is None
    next(b for b in app.button if b.key=='retry-'+tid).click().run()
    assert not app.exception and len(app.session_state['messages'])==1
    assert History().load(cid)[0]['state']=='complete'


@pytest.mark.skipif(not (APP.parent/'history.py').exists(),reason='Interface historique restaurée')
def test_history_write_failure_keeps_answer(tmp_path,monkeypatch):
    # A directory instead of an SQLite file produces a real storage error.
    monkeypatch.setenv('DGRE_UI_HISTORY_PATH',str(tmp_path))
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    app.chat_input[0].set_value('Quel est le total annuel à Amdoun ?').run()
    assert not app.exception and len(app.session_state['messages'])==1
    assert app.session_state['messages'][0]['status']=='answered'
    assert any('session' in w.value for w in app.warning)


@pytest.mark.skipif(not (APP.parent/'history.py').exists(),reason='Interface historique restaurée')
def test_older_corpus_history_is_displayed_without_context_reuse(monkeypatch):
    from history import History
    from dgre_rag.answers.service import Service
    original=Service.ask
    saved=Service().ask('Quel est le total annuel à Amdoun ?',use_llm=False).model_dump(mode='json')
    saved['release_id']='older-corpus'
    cid,tid=History().begin(saved['question'],'older-corpus')
    History().finish(tid,saved)
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    next(b for b in app.button if b.key=='history-'+cid).click().run()
    assert not app.exception
    assert any('mis à jour' in i.value for i in app.info)
    received=[]
    def checked(self,question,context=None,use_llm=True,history=None):
        received.extend(history or [])
        return original(self,question,context,use_llm=False,history=history)
    monkeypatch.setattr(Service,'ask',checked)
    app.chat_input[0].set_value('Quel est le total annuel à Aïn Draham ?').run()
    assert not app.exception and received==[]


def test_model_unavailable_ui_still_answers(monkeypatch):
    import streamlit as st
    from dgre_rag.providers import local
    st.cache_data.clear()
    monkeypatch.setattr(local,'model_status',lambda:dict(available=False,model='offline',installed=[]))
    app=AppTest.from_file(str(APP),default_timeout=30).run()
    app.chat_input[0].set_value('Quel est le total annuel à Amdoun ?').run()
    assert not app.exception
    assert app.session_state['messages'][0]['status']=='answered'
    assert any('momentanément indisponibles' in c.value for c in app.caption)
    st.cache_data.clear()
