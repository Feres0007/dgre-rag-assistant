import pytest
from dgre_rag.storage.database import active_release,connect
from dgre_rag.answers.service import Service
from dgre_rag.answers.validation import finalize
from dgre_rag.retrieval.search import retrieve


pytestmark=pytest.mark.skipif(not active_release(),reason='Corpus nécessaire')


def test_free_threshold_is_not_regional_superlative():
    from dgre_rag.query.planner import controlled_request
    assert not controlled_request('Quelle région a eu le plus de pluie ?')
    assert controlled_request('Combien de jours avec plus de 90 mm ?')
    assert not controlled_request('Quel mois a été le plus déficitaire ?')


def test_filtered_retrieval_never_returns_other_document():
    passages,_=retrieve('pluie méthode',active_release(),mode='lexical',filters={'document_id':'pluvio_2022_2023'},limit=3)
    assert passages and all(p['document_id']=='pluvio_2022_2023' for p in passages)
    missing,warnings=retrieve('pluie',active_release(),mode='lexical',filters={'document_id':'absent'})
    assert not missing and warnings


def test_common_gate_rejects_forged_source():
    answer=Service().ask('Quel est le total annuel à Amdoun en 2022-2023 ?',use_llm=False)
    answer.citations[0]['page_pdf']=1
    with pytest.raises(ValueError,match='INVALID_CITATION'):finalize(Service(),answer)


def test_common_gate_replays_calculation():
    answer=Service().ask('Calcule la somme des pluies journalières à Aïn Draham du 2023-05-20 au 2023-05-22.',use_llm=False)
    assert answer.status=='partial' and answer.calculations[0]['value']=='97'
    answer.calculations[0]['value']='999'
    with pytest.raises(ValueError,match='UNSUPPORTED_CALCULATION'):finalize(Service(),answer)


def test_historical_and_current_values_can_have_distinct_valid_proofs():
    answer=Service().ask('Comment se compare cette année par rapport aux 8 dernières années ?',
        {'period':{'start':'2022-09-01','end':'2023-08-31'}},use_llm=False)
    assert answer.status=='answered',answer.validation
    assert any(c['page_pdf']==9 for c in answer.citations)
    assert answer.validation['accepted']


def test_filter_table_contains_only_selected_observations():
    answer=Service().ask('Quelles stations dépassent 1000 mm de pluie annuelle en 2022-2023 ?',use_llm=False)
    from decimal import Decimal
    assert answer.status=='partial',answer.text
    assert answer.table and all(Decimal(row['value_decimal'])>1000 for row in answer.table)
    assert len(answer.table)==int(answer.calculations[0]['value'])


def test_empty_filter_does_not_show_all_input_rows():
    answer=Service().ask('Quelles stations dépassent 100000 mm de pluie annuelle en 2022-2023 ?',use_llm=False)
    assert answer.calculations[0]['value']=='0'
    assert answer.table==[]
    from dgre_rag.answers.conversation import result_rows
    assert result_rows(answer.model_dump())==[]


def test_no_llm_arabic_does_not_claim_a_random_excerpt_answers_question():
    answer=Service().ask('كم يوماً أمطرت في عين دراهم؟',use_llm=False)
    assert answer.status=='ambiguous' and not answer.citations
