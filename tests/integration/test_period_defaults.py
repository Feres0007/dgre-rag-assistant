"""Temporal policy and original-PDF-backed published threshold regression."""
import pytest
from dgre_rag.answers.service import Service
from dgre_rag.query.temporal import resolve_period

QUESTION='Combien de jours avec une pluie d’au moins 10 mm sont publiés pour Amdoun ?'
CAMPAIGN={'start':'2022-09-01','end':'2023-08-31'}


def test_published_amdoun_threshold():
    # Original rainfall PDF p.50 (printed 47), Amdoun summary: 16 Pluies >= 10 mm.
    srv=Service()
    a=srv.ask(QUESTION,use_llm=False)
    b=srv.ask(QUESTION+' en 2022-2023',use_llm=False)
    assert a.status==b.status=='answered'
    assert a.table==b.table
    assert a.table[0]['value_decimal']=='16'
    assert a.table[0]['metric_id']=='rain_days_ge_10'
    assert not a.calculations
    assert a.temporal_resolution['origin']=='default_campaign'
    assert any(c['document_id']=='pluvio_2022_2023' and c['page_pdf']==50 for c in a.citations)


@pytest.mark.parametrize('phrase',['au moins 12 mm','plus de 10 mm'])
def test_free_threshold_calculated_partial(phrase):
    a=Service().ask('Combien de jours avec une pluie de '+phrase+' à Amdoun ?',use_llm=False)
    assert a.status=='partial'
    assert a.calculations[0]['formula_id']=='threshold_count'
    assert a.calculations[0]['period']==CAMPAIGN


def test_recalculation_not_published():
    a=Service().ask('Recalcule combien de jours avec une pluie d’au moins 10 mm à Amdoun.',use_llm=False)
    assert a.calculations[0]['formula_id']=='threshold_count'
    assert a.status=='partial'


def test_month_and_context_reset():
    srv=Service()
    first=srv.ask('Combien de jours avec une pluie d’au moins 10 mm à Amdoun en mai ?',use_llm=False)
    assert first.status=='partial'
    assert first.calculations[0]['period']=={'start':'2023-05-01','end':'2023-05-31'}
    follow=srv.ask('Et à Aïn Draham ?',history=[first.model_dump(mode='json')],use_llm=False)
    assert follow.temporal_resolution['period']==first.temporal_resolution['period']
    fresh=srv.ask('Quel est le total annuel à Amdoun ?',history=[first.model_dump(mode='json')],use_llm=False)
    assert fresh.status=='answered'
    assert fresh.temporal_resolution['period']==CAMPAIGN


def test_explicit_unavailable_not_replaced():
    a=Service().ask(QUESTION+' en 2020-2021',use_llm=False)
    assert a.status not in ('answered','partial')
    assert a.temporal_resolution['period']=={'start':'2020-09-01','end':'2021-08-31'}


def test_comparison_default():
    a=Service().ask('Compare la pluie annuelle à Amdoun et Aïn Draham.',use_llm=False)
    assert a.status=='answered'
    assert len(a.table)==2
    assert all(r['period_start']=='2022-09-01' for r in a.table)


def test_definition_history_and_rating():
    srv=Service()
    assert resolve_period('Que signifie une année hydrologique ?',srv.release_id) is None
    assert resolve_period('Quel est le débit maximal historique ?',srv.release_id) is None
    a=srv.ask('Estime par interpolation le débit pour une hauteur de 102,5 cm à BOU BRIMA.',use_llm=False)
    assert a.status=='ambiguous'
    assert not a.calculations


def test_invalid_day_and_explicit_precedence():
    srv=Service()
    assert srv.ask('Montre la pluie à Amdoun le 31 février',use_llm=False).status=='ambiguous'
    a=srv.ask(QUESTION+' en 2022-2023',context={'period':{'start':'2020-09-01','end':'2021-08-31'}},use_llm=False)
    assert a.status=='answered'
    assert a.temporal_resolution['origin']=='question'


def test_threshold_boundary_and_symbols():
    srv=Service()
    answers=[srv.ask('Recalcule les jours avec une pluie '+op+' 10 mm à Amdoun.',use_llm=False) for op in ('≥','>')]
    assert all(a.status=='partial' for a in answers)
    assert int(answers[0].calculations[0]['value'])-int(answers[1].calculations[0]['value'])==2


def test_plan_metadata_and_incomplete_comparison():
    from dgre_rag.query.planner import plan_query
    srv=Service()
    plan=plan_query('Combien de jours avec plus de 12 mm à Amdoun ?',srv.release_id,use_llm=False)
    assert plan.temporal_resolution['origin']=='default_campaign'
    a=srv.ask('Compare la pluie annuelle à Amdoun entre deux périodes.',use_llm=False)
    assert a.status=='ambiguous'


def test_final_gate_rejects_wrong_period():
    from dgre_rag.answers.validation import finalize
    srv=Service()
    a=srv.ask(QUESTION,use_llm=False)
    a.temporal_resolution['period']={'start':'2020-09-01','end':'2021-08-31'}
    with pytest.raises(ValueError,match='TEMPORAL_EVIDENCE_MISMATCH'):finalize(srv,a)
