import json
import pytest
from dgre_rag.answers.writing import write_documentary


def passage(text='La couleur grise indique un cumul ultérieur.'):
    return {'source_id':'source-test','text':text,'page_pdf':48}


def replies(monkeypatch,draft,check=True):
    values=iter([json.dumps(draft),json.dumps({'supported':check})])
    monkeypatch.setattr('dgre_rag.answers.writing.generate',lambda *a,**k:next(values))


def test_grounded_paraphrase(monkeypatch):
    replies(monkeypatch,{'sentences':[{'text':'Le gris signale un cumul reporté ultérieurement.','source':1}]})
    text,sources=write_documentary('Que signifie le gris ?',[passage()])
    assert 'Le gris signale' in text and sources[0]['source_id']=='source-test'


@pytest.mark.parametrize('sentence',[
    {'text':'Le cumul est de 900 mm.','source':1},
    {'text':'Le gris signifie une absence de pluie.','source':8},
    {'text':'Consultez https://example.com','source':1},
])
def test_invented_value_or_source_rejected(monkeypatch,sentence):
    replies(monkeypatch,{'sentences':[sentence]})
    with pytest.raises(ValueError):write_documentary('Que signifie le gris ?',[passage()])


def test_semantic_contradiction_rejected(monkeypatch):
    replies(monkeypatch,{'sentences':[{'text':'Le gris signifie une absence de pluie.','source':1}]},check=False)
    with pytest.raises(ValueError,match='UNSUPPORTED_CLAIM'):write_documentary('Que signifie le gris ?',[passage()])


def test_no_current_waiting_claim_from_historical_legend(monkeypatch):
    replies(monkeypatch,{'sentences':[{'text':'Le gris indique un cumul ultérieur.','source':1},
        {'text':'Ces données sont encore en attente.','source':1}]})
    text,_=write_documentary('Que signifie le gris ?',[passage()])
    assert text=='Le gris indique un cumul ultérieur.'
