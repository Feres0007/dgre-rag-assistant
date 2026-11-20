"""Régressions découvertes en confrontant les questions aux PDF originaux."""
import pytest
from dgre_rag.answers.service import Service
from dgre_rag.storage.database import active_release
from dgre_rag.answers.reference import catalog

pytestmark=pytest.mark.skipif(not active_release(),reason='Corpus nécessaire')
CONTEXT={'period':{'start':'2022-09-01','end':'2023-08-31'}}


@pytest.mark.parametrize('question,status,expected,forbidden',[
    ('Quel mois a été le plus arrosé ?','answered',['Mai','52,3'],['Ete :']),
    ('Est-ce que le mois de février a été excédentaire ?','answered',['25,5','113'],['réseau']),
    ('Quelle rivière a eu le débit le plus élevé ?','answered',['868,778','m³/s'],['167 mm']),
    ('Comparez les débits moyens annuels des stations Slouguia et Mejez GP5.','answered',['6,083','12,45','Slouguia','Mejez'],[]),
    ('Quelle station a enregistré le plus grand volume total écoulé : Ghardimaou ou Jendouba ?','answered',['185,67','31,753'],['pluviométrique']),
    ('Quel est le débit moyen annuel de la station Mateur ?','answered',['1,043'],[]),
    ('Quel est le débit moyen annuel de la station Rmel Pont Route ?','answered',['0,221'],[]),
    ('Quel est le débit moyen annuel de la station Tessa Pont ?','unvalidated_data',['lacunes'],['0 m³/s']),
    ('Comparez les crues de mai et juin à la station Mellègue GP17.','answered',['GP17','197,28','193,80'],['868,778']),
    ('Comparez les crues à la station Mellègue GP999.','ambiguous',['identifiant'],['868,778']),
    ('Les barrages ont-ils reçu plus d’eau en 2022-2023 qu’en 2021-2022 ?','not_found',['référence'],[]),
    ('Est-ce que Sidi Bouzid a reçu plus d’eau que Kasserine ?','answered',['Sidi Bouzid','Kasserine'],['Tunisie :']),
    ('Les barrages sont-ils remplis ?','not_found',['stock'],[]),
])
def test_pdf_regressions(question,status,expected,forbidden):
    if not catalog(active_release()):pytest.skip('Catalogue de synthèses nécessaire')
    answer=Service().ask(question,CONTEXT,use_llm=False)
    assert answer.status==status,answer.text
    for text in expected:assert text.lower() in answer.text.lower(),answer.text
    for text in forbidden:assert text.lower() not in answer.text.lower(),answer.text


def test_flood_unit_contradiction_is_visible():
    answer=Service().ask('Quel est le temps de montée de la crue du 14 juin 2023 à Sarrat Pont Route ?',CONTEXT,use_llm=False)
    assert '75' in answer.text and 'unité' in answer.text
    assert '75 heures' not in answer.text
    assert any(c['document_id']=='hydro_2022_2023' and c['page_pdf']==74 for c in answer.citations)
