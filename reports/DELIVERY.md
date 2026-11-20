# Livraison de la V1 locale DGRE

Bilan du 13 septembre 2026, release `corpus-c60e4a25cec4`. **L’application fonctionne ; l’intégralité du plan et la validation scientifique ne sont pas terminées.**

## Utilisation

Ouvrir http://127.0.0.1:8501 lorsque le serveur local est démarré. Pour le lancer depuis la racine :

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

Les cinq espaces consultent les données réelles : assistant, exploration, comparaison, sources PDF avec rectangles et couverture. [Guide utilisateur](../docs/GUIDE_UTILISATEUR.md) ; [installation et reprise](../README.md).

## Couverture mesurée

- 2 PDF, 387 pages inventoriées et 1050 tableaux conservés.
- 280903 observations candidates ; 38265 observations canoniques consultables après contrôles applicatifs.
- 242464 observations bloquées, distinctes des zéros. Des doublons identiques sont également éliminés de la sélection canonique : les nombres ne s’additionnent pas comme deux catégories exhaustives.
- 742 identifiants de stations/entités et 16004 blocs textuels stockés ; index contextuel décrit dans [les métriques](delivery_metrics.json).

309 tableaux restent bruts. La consultation documentaire couvre les pages disponibles, mais ne rend pas toutes leurs cellules utilisables dans un calcul. Les familles pluie et débit reconnues disposent de preuves localisables ; les incohérences signalées restent visibles. Le statut interne `validated` désigne un contrôle logiciel, jamais une validation humaine implicite.

## Vérifications exécutées

| Contrôle | Résultat | Portée |
|---|---|---|
| Tests automatisés | 62 tests, 0 échec, 0 erreur, 0 ignoré | Contrats, calculs, corpus réel, publication, cinq espaces AppTest |
| Développement | 120/120 | Questions utilisées pour régler le système |
| Numérique réservé | 24/24 | 12 stations, totaux et maxima/date ; pas un lot documentaire indépendant |
| Recherche documentaire développement | lexical 18/20, vectoriel 16/20, hybride 20/20 | Page attendue parmi 12 résultats ; pas une certification de synthèse |
| Modèle local réel | answered, 41.2 s | Un extrait de légende, PDF pluviométrique page 48 |
| Sauvegarde / réactivation | True | Copie et vérification de la release locale |
| Service Streamlit | HTTP 200 lors de l’essai | Disponibilité HTTP, pas une revue visuelle |

Preuves : [tests](pytest.xml), [développement](evaluation_dev.json), [lot réservé](evaluation_test.json), [essai modèle](model_smoke.json), [opérations](operations.json), [environnement](environment.json).

## Écarts à clôturer

Extracteurs des familles restantes, OCR de secours, références et relations géographiques, évaluation indépendante documentaire/mixte, revue scientifique, revue visuelle UI et installation sur un second poste. Les réponses documentaires sont extractives ; la rédaction libre prévue initialement n’est pas activée. Le détail et les prochaines actions figurent dans [BLOCKERS.md](../docs/BLOCKERS.md).

Les [rapports P00–P12](../docs/PROGRESS.md) distinguent réalisations et travail restant. Aucun score ci-dessus ne signifie que toutes les valeurs des deux PDF sont correctes ou que toutes les exigences sont acceptées.
