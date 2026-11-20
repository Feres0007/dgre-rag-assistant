import pytest
from dgre_rag.answers.service import Service
from dgre_rag.answers.conversation import export_table
from dgre_rag.storage.database import active_release

pytestmark=pytest.mark.skipif(not active_release(),reason='Corpus nécessaire')


def talk(questions):
    srv=Service();history=[]
    for question in questions:
        answer=srv.ask(question,use_llm=False,history=history)
        history.append(answer.model_dump(mode='json'))
    return history


def test_followup_compare_chart_export():
    h=talk(['Quel est le total annuel à Aïn Draham en 2022-2023 ?', 'Et à Amdoun ?', 'Compare les deux', 'Fais un graphique', 'Télécharge le tableau'])
    assert all(a['status']=='answered' for a in h),[(a['status'],a['text']) for a in h]
    assert h[1]['table'][0]['canonical_name'].lower()=='amdoun'
    assert '750,5' in h[2]['text']
    assert len(h[3]['table'])==2 and h[3]['presentation']=='chart'
    assert h[4]['presentation']=='export' and 'Amdoun' in export_table(h[4]['table'])


def test_series_default_period():
    h=talk(['Montre les pluies mensuelles à Aïn Draham', 'Fais un graphique'])
    assert h[0]['status']=='answered'
    assert len(h[0]['table'])==12,h[0]['text']
    assert h[1]['presentation']=='chart' and len(h[1]['table'])==12


def test_availability_and_new_question_after_ambiguity():
    h=talk(['Montre les pluies mensuelles', 'Quelles stations disposent de débits moyens annuels ?'])
    assert h[0]['status']=='ambiguous'
    assert h[1]['status']=='answered' and h[1]['table']


def test_reference_result_remains_exportable():
    h=talk(['Quelle est la capacité du barrage Sidi Salem ?', 'Télécharge le tableau'])
    assert h[1]['presentation']=='export' and h[1]['table'][0]['value_decimal']=='814'


def test_unknown_place_does_not_reuse_previous_value():
    h=talk(['Quel est le total annuel à Amdoun en 2022-2023 ?', 'Et à Atlantis ?'])
    assert not h[1]['table']


def test_compare_reference_capacities_and_export_sources():
    h=talk(['Quelle est la capacité du barrage Sidi Salem ?', 'Quelle est la capacité du barrage Mellègue ?', 'Compare les deux'])
    assert h[-1]['status']=='answered' and len(h[-1]['table'])==2,h[-1]['text']
    assert '631,80' in h[-1]['text']
    assert 'page PDF 34' in export_table(h[-1]['table'],h[-1]['citations'])


def test_direct_dam_comparison():
    h=talk(['Compare les capacités des barrages Sidi Salem et Mellègue.'])
    assert len(h[0]['table'])==2 and '631,80' in h[0]['text']


def test_followup_next_month_and_sources():
    h=talk(['Montre les pluies mensuelles à Aïn Draham en mai 2023.', 'Et le mois suivant ?', 'Ouvre les sources', 'Fais un graphique'])
    assert h[1]['table'][0]['period_start']=='2023-06-01',h[1]['text']
    assert h[2]['presentation']=='sources' and h[2]['citations']
    assert h[3]['presentation']=='chart' and len(h[3]['table'])==1


def test_different_periods_missing_value_does_not_compare():
    h=talk(['Compare la pluie annuelle à Amdoun en 2021-2022 et 2022-2023.'])
    assert h[0]['status']=='partial' and len(h[0]['table'])==1
    assert not h[0]['calculations']


def test_all_stations_annual_table():
    h=talk(['Affiche les pluies annuelles de toutes les stations en 2022-2023.'])
    assert h[0]['status']=='answered' and len(h[0]['table'])>100
    assert all(r['metric_id']=='rainfall_annual' for r in h[0]['table'])


def test_invalid_natural_date_returns_clarification():
    assert Service().ask('Montre la pluie à Amdoun le 31 février 2023',use_llm=False).status=='ambiguous'
