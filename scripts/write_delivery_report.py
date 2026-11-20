"""Régénérer le bilan à partir des contrôles enregistrés, sans modifier le corpus."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from dgre_rag.config import root
from dgre_rag.storage.database import connect, release_path, active_release, dump
from dgre_rag.domain.models import QueryPlan, Answer
from dgre_rag.cli import doctor


def main():
    project = root()
    reports = project / 'reports'
    def read(name):
        return json.loads((reports / name).read_text(encoding='utf-8'))
    def write(path, text):
        (project / path).write_text(text.strip() + '\n', encoding='utf-8')
    dev, test = read('evaluation_dev.json'), read('evaluation_test.json')
    smoke, operations = read('model_smoke.json'), read('operations.json')
    suites = ET.parse(reports / 'pytest.xml').getroot().findall('.//testsuite')
    tests = {key: sum(int(s.get(key, '0')) for s in suites)
             for key in ('tests', 'failures', 'errors', 'skipped')}
    with connect() as db:
        counts = {name: db.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                  for name in ('documents', 'page_inventory', 'table_extractions', 'observations',
                               'published_observations', 'entities', 'chunks')}
        counts['table_states'] = dict(db.execute('SELECT state,count(*) FROM table_extractions GROUP BY state'))
        counts['page_states'] = dict(db.execute('SELECT state,count(*) FROM page_inventory GROUP BY state'))
        counts['quality_states'] = dict(db.execute('SELECT quality_status,count(*) FROM observations GROUP BY quality_status'))
        counts['issues'] = dict(db.execute('SELECT code,count(*) FROM quality_issues GROUP BY code'))
    index = json.loads((release_path() / 'index.json').read_text(encoding='utf-8'))
    environment = doctor()
    dump(reports / 'environment.json', environment)
    dump(project / 'config/query_plan.schema.json', QueryPlan.model_json_schema())
    dump(project / 'config/answer.schema.json', Answer.model_json_schema())
    measured = {'generated_at': datetime.now(timezone.utc).isoformat(), 'release_id': active_release(),
                'counts': counts, 'tests': tests, 'index': index}
    dump(reports / 'delivery_metrics.json', measured)
    docs = [r for r in dev['results'] if r['category'] == 'documentary']
    recall = {mode: sum(r['retrieval'][mode]['hit'] for r in docs) for mode in ('lexical', 'vector', 'hybrid')}
    phases = [
        ('P00', 'Diagnostic et préparation', 'réalisée à examiner',
         'Python isolé, dépendances, Ollama et corpus diagnostiqués ; les deux originaux sont enregistrés avec empreintes.',
         'environment.json ; ../data/registry.json', 'Aucune certification sur un second poste Windows.'),
        ('P01', 'Paquet et contrats', 'réalisée à examiner',
         'Paquet src installable, CLI, configuration, modèles stricts et schémas JSON exportés. Contrats et erreurs testés.',
         '../pyproject.toml ; ../requirements.lock.txt ; pytest.xml', 'Versions testées consignées ; installation sur un autre poste à vérifier.'),
        ('P02', 'Inventaire', 'réalisée à examiner',
         'Les 387 pages ont dimensions, géométrie, état et tables détectées dans page_inventory. Texte natif conservé.',
         'delivery_metrics.json ; ../data/registry.json', 'Classification automatique, pas une annotation humaine exhaustive des figures.'),
        ('P03', 'Extraction', 'en cours',
         'Pilote puis corpus complet extraits ; tableaux bruts et géométries conservés ; grilles pluie/débit reconnues.',
         'delivery_metrics.json ; ../src/dgre_rag/ingestion/pipeline.py', '309 tableaux restent bruts. OCR de secours et familles restantes à implémenter.'),
        ('P04', 'Normalisation et qualité', 'en cours',
         'Calendrier, Decimal, symboles, doublons, divergences, couverture et cohérence des résumés contrôlés. Tirets non convertis en zéro.',
         'delivery_metrics.json ; ../tests/unit/test_contracts.py', 'Normalisation géographique, références et revue scientifique à compléter.'),
        ('P05', 'Publication et provenance', 'réalisée à examiner',
         'SQLite en lecture seule, sélection canonique, preuves et rectangles, publication atomique et contrôle des empreintes.',
         '../tests/integration/test_publication.py ; operations.json', 'Statut validated = admissibilité applicative, pas approbation métier.'),
        ('P06', 'Recherche', 'réalisée à examiner',
         f'FTS5, recherche lexicale par page, embeddings multilingues et fusion avec priorités de stations. Rappel de développement : {recall}.',
         'evaluation_dev.json ; ../src/dgre_rag/retrieval/search.py', '20 questions documentaires utilisées pour régler la recherche ; aucun lot documentaire indépendant.'),
        ('P07', 'Moteur numérique', 'réalisée à examiner',
         'Consultations, sommes, moyennes pondérées, volumes, extrema et comparaisons avec unités/périodes/lacunes contrôlées ; entrées sourcées.',
         '../tests/unit/test_calculations.py ; evaluation_test.json', 'Références régionales incomplètes ; dérivations conservées dans les journaux de requêtes, pas dans les tables canoniques de dérivations.'),
        ('P08', 'Planification', 'en cours',
         'Résolution déterministe puis plan JSON borné via Ollama ; identifiants et opérations validés ; clarification des ambiguïtés.',
         '../src/dgre_rag/query/planner.py ; pytest.xml', 'Questions mixtes complexes et robustesse linguistique à évaluer sur un lot indépendant plus large.'),
        ('P09', 'Réponses', 'réalisée à examiner',
         'Chiffres rendus depuis les résultats vérifiés ; citations construites par code ; sélection documentaire assistée puis extraits exacts.',
         'model_smoke.json ; ../src/dgre_rag/answers/service.py', 'R2/R3 de rédaction libre remplacés par une réponse extractive contrôlée ; aucune synthèse hydrologique libre.'),
        ('P10', 'Interface et corpus', 'en cours',
         'Cinq espaces Streamlit reliés au corpus réel : assistant, exploration, comparaison, sources et couverture ; graphiques et exports CSV.',
         '../tests/e2e/test_ui.py ; delivery_metrics.json', 'Extension numérique à toutes les familles non terminée ; contrôle visuel complet dans un navigateur non exécuté.'),
        ('P11', 'Acceptation', 'en cours',
         f"{tests['tests']} tests automatisés, {dev['passed']}/{dev['cases']} cas de développement et {test['passed']}/{test['cases']} cas numériques réservés réussis ; un essai documentaire réel avec Mistral.",
         'pytest.xml ; evaluation_dev.json ; evaluation_test.json ; model_smoke.json', 'Pas de validation métier humaine ; pas de captures UI complètes ; lot réservé limité aux valeurs numériques.'),
        ('P12', 'Livraison Windows', 'réalisée à examiner',
         'Lancement local, environnement isolé, versions verrouillées, scripts, guide, sauvegarde et réactivation vérifiés sur ce poste.',
         '../README.md ; ../docs/GUIDE_UTILISATEUR.md ; operations.json', 'Installation sur second poste et reprise après perte totale du poste non testées.'),
    ]
    rows = []
    for code, title, status, work, evidence, limits in phases:
        links = ', '.join(f'[{p}]({p})' for p in evidence.split(' ; '))
        write(f'reports/{code}_report.md', f'# {code} — {title}\n\nStatut : **{status}**. Bilan du 13 septembre 2026.\n\n{work}\n\nPreuves : {links}.\n\nLimites : {limits}\n\nCe bilan décrit le travail réalisé ; il ne constitue pas une acceptation humaine de la phase.')
        rows.append(f'| [{code}](../reports/{code}_report.md) | {title} | {status} |')
    write('docs/PROGRESS.md', '# Progression de l’implémentation\n\nMise à jour : 13 septembre 2026. Une V1 locale fonctionne ; le plan intégral n’est pas entièrement accepté. Les phases « en cours » signalent un périmètre restant, sans signifier qu’un processus tourne en arrière-plan.\n\n| Phase | Objet | État |\n|---|---|---|\n' + '\n'.join(rows) + '\n\nLes demandes successives de mise en œuvre et de poursuite autorisent l’enchaînement du travail. Aucune acceptation scientifique ou humaine n’est déduite de cette autorisation. Voir le [bilan](../reports/DELIVERY.md) et les [limites](BLOCKERS.md).')
    write('docs/ENVIRONMENT.md', f'''# Environnement vérifié

Poste Windows, dossier `C:\\Users\\SIGMA IT\\Documents\\RAG_DGRE`, Python 3.11.9 dans `.venv` et SQLite {environment['sqlite']}. Diagnostic détaillé : [environment.json](../reports/environment.json).

Le diagnostic initial a identifié 16 Go de RAM et une NVIDIA RTX 3050 Laptop de 6 Go. Les dépendances exactes sont dans [requirements.lock.txt](../requirements.lock.txt). Ollama fournit `mistral:latest` ; son identité disponible au diagnostic est conservée dans le JSON. Les embeddings utilisent `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` avec FastEmbed/ONNX et cache dans `data/models`.

Consultation locale : Streamlit sur `127.0.0.1:8501`, Ollama sur `127.0.0.1:11434`. L’installation et le premier téléchargement nécessitent le réseau. Aucun essai de poste physiquement déconnecté n’est déclaré. Le mode applicatif interdit le téléchargement implicite des embeddings.

Les chemins contenant des espaces ont été utilisés dans les essais. Le contrôle par navigateur automatisé était indisponible ; AppTest a exercé les cinq espaces et le service HTTP a répondu 200. Les PDF ont été inspectés séparément par extraction et rendus de pages représentatives.
''')
    write('docs/DECISIONS.md', '''# Décisions d’implémentation

- Les instructions utilisateur de mise en œuvre globale puis de poursuite autorisent l’enchaînement des phases sans demander une permission à chaque étape. Le suivi ne déclare aucune phase acceptée par un humain.
- Les deux PDF originaux constituent seuls le corpus. Le dossier de plan, les rapports, les tests et `tmp` restent hors index métier.
- PyMuPDF extrait texte, tableaux et géométries. Les familles non reconnues sont conservées sans inventer leur sémantique numérique. Les tirets et symboles non prouvés restent indéterminés.
- SQLite contient candidats, preuves et sélection canonique ; une release publiée se consulte en lecture seule. Publication atomique et empreintes séparent extraction et application.
- Les calculs utilisent Decimal, des observations admissibles et des règles de couverture. Les totaux publiés restent distincts des totaux recalculés. Une incohérence détectée accompagne la valeur publiée d’un avertissement.
- La recherche combine FTS5, pages lexicales et fenêtres contextuelles vectorielles. Les ajustements sur les 120 questions initiales imposent leur classement en développement. Les 24 nouvelles questions réservées portent uniquement sur des valeurs et dates numériques.
- Ollama/Mistral peut planifier ou sélectionner des sources. Les chiffres et citations sont construits par code ; le documentaire restitue des extraits exacts, sans rédaction libre R2/R3. Cette adaptation réduit le périmètre rédactionnel du plan initial.
- Les annotations et contrôles visuels réalisés par l’agent ne sont pas présentés comme une validation scientifique humaine. Les tests AppTest ne remplacent pas une revue visuelle complète dans un navigateur.
''')
    write('docs/BLOCKERS.md', '''# Limites et travail restant

L’application est exploitable localement, mais la conformité complète au plan n’est pas acquise.

| Priorité | Écart | Prochaine action vérifiable |
|---|---|---|
| Haute | 309 tableaux conservés bruts sans interprétation numérique | Ajouter des extracteurs par famille et des références indépendantes ; republier après contrôle de régression |
| Haute | Symboles et observations bloqués ; revue métier absente | Vérifier les légendes et divergences avec les pages sources, puis soumettre un lot annoté à une revue scientifique |
| Haute | Références régionales, relations géographiques et coordonnées incomplètes | Normaliser les identifiants, périodes de référence et systèmes de coordonnées avec preuves |
| Moyenne | OCR de secours absent | Ajouter un traitement des régions natives défaillantes avec contrôle géométrique et audit |
| Moyenne | Évaluation réservée limitée au numérique | Construire un nouveau lot documentaire et mixte indépendant, puis mesurer réponse, abstention et latence avec le modèle réel |
| Moyenne | Revue visuelle complète UI non exécutée, navigateur d’automatisation indisponible | Vérifier les cinq espaces dans un navigateur disponible et conserver les captures, notamment erreur et clarification |
| Moyenne | Dérivations dans les journaux, pas dans les tables canoniques | Définir un stockage séparé append-only des calculs, lié à la release consultée |
| Moyenne | Installation et reprise intégrale sur second poste non testées | Rejouer le guide avec les originaux, les modèles et une sauvegarde externe |

Un essai documentaire précédent a dépassé le délai et utilisé le repli explicite. Après réduction de la sortie du modèle à une sélection d’identifiants, un essai a réussi en environ 41 secondes. Cela ne constitue pas une garantie générale de latence.
''')
    write('reports/DELIVERY.md', f'''# Livraison de la V1 locale DGRE

Bilan du 13 septembre 2026, release `{active_release()}`. **L’application fonctionne ; l’intégralité du plan et la validation scientifique ne sont pas terminées.**

## Utilisation

Ouvrir http://127.0.0.1:8501 lorsque le serveur local est démarré. Pour le lancer depuis la racine :

```powershell
.\\.venv\\Scripts\\python.exe -m streamlit run app/streamlit_app.py
```

Les cinq espaces consultent les données réelles : assistant, exploration, comparaison, sources PDF avec rectangles et couverture. [Guide utilisateur](../docs/GUIDE_UTILISATEUR.md) ; [installation et reprise](../README.md).

## Couverture mesurée

- {counts['documents']} PDF, {counts['page_inventory']} pages inventoriées et {counts['table_extractions']} tableaux conservés.
- {counts['observations']} observations candidates ; {counts['published_observations']} observations canoniques consultables après contrôles applicatifs.
- {counts['quality_states'].get('blocked', 0)} observations bloquées, distinctes des zéros. Des doublons identiques sont également éliminés de la sélection canonique : les nombres ne s’additionnent pas comme deux catégories exhaustives.
- {counts['entities']} identifiants de stations/entités et {counts['chunks']} blocs textuels stockés ; index contextuel décrit dans [les métriques](delivery_metrics.json).

309 tableaux restent bruts. La consultation documentaire couvre les pages disponibles, mais ne rend pas toutes leurs cellules utilisables dans un calcul. Les familles pluie et débit reconnues disposent de preuves localisables ; les incohérences signalées restent visibles. Le statut interne `validated` désigne un contrôle logiciel, jamais une validation humaine implicite.

## Vérifications exécutées

| Contrôle | Résultat | Portée |
|---|---|---|
| Tests automatisés | {tests['tests']} tests, {tests['failures']} échec, {tests['errors']} erreur, {tests['skipped']} ignoré | Contrats, calculs, corpus réel, publication, cinq espaces AppTest |
| Développement | {dev['passed']}/{dev['cases']} | Questions utilisées pour régler le système |
| Numérique réservé | {test['passed']}/{test['cases']} | 12 stations, totaux et maxima/date ; pas un lot documentaire indépendant |
| Recherche documentaire développement | lexical {recall['lexical']}/20, vectoriel {recall['vector']}/20, hybride {recall['hybrid']}/20 | Page attendue parmi 12 résultats ; pas une certification de synthèse |
| Modèle local réel | {smoke['status']}, {smoke['elapsed_seconds']:.1f} s | Un extrait de légende, PDF pluviométrique page 48 |
| Sauvegarde / réactivation | {operations['restore_verified']} | Copie et vérification de la release locale |
| Service Streamlit | HTTP {smoke['streamlit_health']['status_code']} lors de l’essai | Disponibilité HTTP, pas une revue visuelle |

Preuves : [tests](pytest.xml), [développement](evaluation_dev.json), [lot réservé](evaluation_test.json), [essai modèle](model_smoke.json), [opérations](operations.json), [environnement](environment.json).

## Écarts à clôturer

Extracteurs des familles restantes, OCR de secours, références et relations géographiques, évaluation indépendante documentaire/mixte, revue scientifique, revue visuelle UI et installation sur un second poste. Les réponses documentaires sont extractives ; la rédaction libre prévue initialement n’est pas activée. Le détail et les prochaines actions figurent dans [BLOCKERS.md](../docs/BLOCKERS.md).

Les [rapports P00–P12](../docs/PROGRESS.md) distinguent réalisations et travail restant. Aucun score ci-dessus ne signifie que toutes les valeurs des deux PDF sont correctes ou que toutes les exigences sont acceptées.
''')
    print(json.dumps(measured, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
