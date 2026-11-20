import importlib.util
import json
import hashlib
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('audit',Path(__file__).parents[2]/'scripts/audit_questions.py')
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_user_pseudopython_is_parsed_without_execution(tmp_path):
    path=tmp_path/'questions.txt'
    path.write_text('questions = [\n1. Combien a-t-il plu ?\n2. Quel débit ?\n]\nraise RuntimeError()',encoding='utf8')
    assert [r['question'] for r in audit.import_questions(path)]==['Combien a-t-il plu ?','Quel débit ?']


def test_duplicate_ids_rejected(tmp_path):
    path=tmp_path/'questions.json'
    path.write_text(json.dumps([{'id':1,'question':'A'},{'id':1,'question':'B'}]),encoding='utf8')
    with pytest.raises(ValueError):audit.import_questions(path)


def test_answered_does_not_mean_verified():
    answer={'status':'answered','text':'Une réponse sans preuve','citations':[]}
    assert audit.assess(answer,None)[0]=='a_verifier'
    assert audit.assess(answer,{'required':['167']})[0]=='probleme'
    assert audit.assess(answer,{'question_sha256':hashlib.sha256(b'ancienne question').hexdigest()})[0]=='a_verifier'


def test_accents_spaces_and_required_source():
    answer={'status':'answered','text':'Août : 1\u202f178 mm','citations':[{'document_id':'rain','page_pdf':59}]}
    assert audit.assess(answer,{'required':['aout','1178'],'pages':[['rain',59]]})[0]=='conforme_aux_criteres'
    assert audit.assess(answer,{'required':['1178'],'pages':[['rain',60]]})[0]=='probleme'
