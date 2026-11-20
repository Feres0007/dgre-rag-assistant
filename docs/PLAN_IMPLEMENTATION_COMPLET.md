# Plan complet d’implémentation — RAG DGRE

Date : 12 septembre 2026. Statut : plan de travail proposé ; phases P00 à P12 à réaliser. La création de ce document ne vaut ni démarrage ni validation d’une phase.

## 1. Objectif et état de départ

Construire une application locale Windows, en français, pour rechercher, consulter et comparer les observations des deux annuaires DGRE. Chaque réponse doit présenter sa période, son unité, ses sources et les limites qui changent son interprétation. Les calculs sont exécutés par le programme sur des observations admissibles ; le modèle de langage propose un plan et rédige les explications soutenues par les documents.

Le dossier `RAG_DGRE_Plan_Complet/plan_implementation` constitue la spécification de référence. Ce document en organise l’exécution et ajoute les points repérés pendant la lecture des originaux. En cas de divergence, appliquer la demande actuelle de l’utilisateur puis le plan directeur et les spécifications du dossier de référence.

État observé à la préparation du plan :

- Les spécifications, le guide, les prompts et le schéma SQL sont présents ; ils ne constituent pas une application déjà réalisée.
- Les deux PDF sont dans `donnees_brutes/` ; leurs empreintes concordent avec le manifeste attendu.
- Les fichiers `tmp/pdfs/` servent à la lecture : textes extraits et images de pages. Ils ne sont ni une base validée ni un index métier et ne doivent pas être ingérés comme sources supplémentaires.
- La lecture a couvert les sections des deux documents, les fiches et synthèses, avec examen visuel de pages représentatives. La validation exhaustive des cellules reste un travail d’implémentation et de contrôle.
- Python n’était pas accessible par les commandes essayées pendant la lecture. P00 doit confirmer les installations disponibles, la RAM, le GPU, le stockage et les modèles avant de choisir l’environnement.

### Corpus autorisé

| Document dans `donnees_brutes/` | Pages PDF | SHA-256 vérifié pendant la lecture |
|---|---:|---|
| `ANNUAIRE HYDROLOGIQUE 2022-2023.pdf` | 145 | `78d6cfc8b16fab43c50363eb1853fdb117c6fc13d91352f3de28338ae0b63281` |
| `ANNUAIRE PLUVIOMETRIQUE DE LATUNISIE PUBLICATION 2022-2023.pdf` | 242 | `d62723ab32ced67bed7991365610423795900b4a474230dc8b7afe4de36d899b` |

Utiliser ces chemins par configuration sans déplacer les originaux. Recontrôler les empreintes à l’enregistrement et avant une nouvelle ingestion. Un changement d’empreinte représente une nouvelle version à examiner.

## 2. Résultat attendu et limites de la V1

L’application comporte cinq espaces :

| Espace | Fonction attendue |
|---|---|
| Assistant | Question en français, clarification si nécessaire, réponse citée, distinction publié/calculé, export Markdown. |
| Explorer les données | Filtres réels sur entités, indicateurs et périodes ; tableau des observations validées ; graphiques et export CSV avec provenance. |
| Comparer | Deux sélections compatibles, différence et comparaison relative admissible, sources et couverture de chaque côté. |
| Sources | Page originale rendue à la demande, numéro PDF et imprimé, zoom et surbrillance du bloc cité. |
| Couverture | Pages, tableaux et observations traités, validés ou bloqués ; raisons d’exclusion et conséquences. |

La V1 consulte les données historiques ; elle ne prévoit pas les crues, ne pilote pas les ouvrages et ne complète pas les mesures absentes avec les connaissances du LLM. Les courbes d’étalonnage peuvent être consultées comme tableaux ou figures sourcés ; leur interpolation nécessite une méthode distincte et reste hors V1. Les plans, conversations, rapports, données de test et documents externes sont exclus du corpus métier.

## 3. Architecture et décisions techniques

### Ingestion, exécutée séparément de l’application

`PDF → registre → inventaire des pages → segmentation → extraction brute → candidats normalisés → contrôles → observations publiables et anomalies → release SQLite/index`

Le brut reste immuable. Chaque candidat conserve sa cellule, ses en-têtes et sa preuve. Les observations incertaines restent consultables en audit mais ne participent pas aux calculs. Une release associe une base, ses index et un manifeste cohérent ; une publication interrompue conserve la version active précédente.

### Traitement d’une question

`Question et filtres → résolution des entités → plan typé → validation → recherche documentaire et/ou SQL/calcul → dossier de preuves → rédaction → contrôle final → réponse`

| Composant | Choix de conception | Décision restant à vérifier |
|---|---|---|
| Application | Python modulaire, interface Streamlit, services indépendants de l’UI | Version compatible avec les dépendances et Windows en P00/P01. |
| Données numériques | SQLite ; décimaux canoniques stockés sans perte et calculs `Decimal` | Adapter le schéma fourni par migrations testées. |
| Extraction | Texte natif et coordonnées ; reconstruction des tableaux ; OCR ciblé si nécessaire | Comparer les outils sur le pilote avant choix définitif. |
| Recherche | FTS5/BM25, embeddings locaux, fusion des rangs | Modèle et stockage vectoriel selon matériel et mesure de rappel. |
| Rédaction | Adaptateur de LLM local configurable | Choisir et mesurer le modèle ; ne pas supposer sa disponibilité. |
| Orchestration | États explicites en Python, budgets et erreurs typés | LangGraph facultatif, sans dépendance imposée. |
| Exploitation | Environnement `.venv`, dépendances verrouillées, configuration relative au projet | Vérifier les API officielles des versions retenues à l’implémentation. |

Le fonctionnement hors ligne sera vérifié après mise à disposition des dépendances et modèles. Une panne du LLM doit laisser accessibles l’exploration et les sources d’une release existante. Le mode lexical seul sera affiché comme dégradé si les embeddings manquent.

## 4. Organisation des fichiers à produire

```text
RAG_DGRE/
  donnees_brutes/                  # Deux originaux enregistrés par configuration
  RAG_DGRE_Plan_Complet/           # Références existantes
  pyproject.toml                   # Paquet, dépendances et CLI
  config/                         # Configuration et manifeste des modèles
  src/dgre_rag/
    domain/                       # Types, indicateurs, unités, qualité
    ingestion/                    # Inventaire, segmentation et extraction
    storage/                      # Migrations, dépôts et releases
    retrieval/                    # Recherche lexicale, vectorielle et fusion
    analytics/                    # Opérations et formules Decimal
    query/                        # Résolution, plans et orchestration
    answers/                      # Preuves, gabarits et contrôle final
    providers/                    # Adaptateurs LLM et embeddings
    prompts/                      # R1, R2, R3 versionnés
    cli.py
  app/streamlit_app.py
  app/pages/
  data/runs/<run_id>/              # Brut, candidats, contrôles et images
  data/releases/<release_id>/      # Base, index et manifeste compatibles
  evaluation/                     # Annotations et lots séparés
  tests/unit/                     # Contrats, calendrier et calculs
  tests/integration/              # Jonctions entre composants
  tests/e2e/                      # Questions et parcours réels
  scripts/                        # Diagnostic et lancement Windows
  docs/                           # Plan, suivi et guides
  reports/                        # Rapports de phases et d’acceptation
  tmp/pdfs/                       # Cache de lecture temporaire existant
```

Éviter une seconde racine `RAG_DGRE/RAG_DGRE`. Versionner le code, les configurations sans secrets et les règles ; définir séparément la sauvegarde des données et des modèles volumineux.

## 5. Contrats et règles de données

Reprendre les contrats du guide : `SourceRef`, `CellCandidate`, `EntityResolution`, `Observation`, `Coverage`, `QueryPlan`, `ValidatedPlan`, `EvidenceBundle` et `Answer`.

Pour chaque mesure, conserver : document et empreinte, page PDF à partir de 1, numéro imprimé nullable, rectangle et repère de coordonnées, bloc/table/cellule, en-têtes, texte brut, valeur normalisée, précision, unité, station et code brut, période, granularité, référence climatique éventuelle, qualité et méthode de revue.

Les codes restent des chaînes, sans longueur imposée. Les dates sont réelles et ISO ; les périodes ont des bornes inclusives. L’année principale va du 1er septembre 2022 au 31 août 2023. Les événements historiques conservent leurs dates propres. Ne pas inventer de fuseau horaire absent de la source.

Adapter les tables du schéma initial : documents, sources, cells, entities et mentions/relations, metrics, baselines, observations et evidence, derivations et inputs, quality_issues, observation_selections, coverage, chunks. Compléter par migrations les besoins de suivi des pages, runs, releases et index. Vérifier clés étrangères, dates, unités et rectangles par code ; le schéma seul ne prouve pas une extraction correcte.

Séparer les états d’extraction, de validation et de publication. Un total publié peut être consultable même lorsque sa série quotidienne ne permet pas un recalcul, avec son avertissement de couverture. Deux valeurs contradictoires restent liées à leurs preuves ; aucune priorité automatique entre annuaires. Un doublon confirmé ne compte qu’une fois.

## 6. Contrôles spécifiques issus de la lecture

Les numéros suivants désignent les pages PDF. Ce registre initial doit être complété et vérifié lors de P02–P04.

| Cas | Traitement prévu |
|---|---|
| Pluvio 50 : quatre stations sur une page | Segmenter quatre régions ; rattacher maxima, totaux et nombres de jours à leur propre station. |
| Hydro 18 : plusieurs types de valeurs dans une fiche | Séparer débits journaliers, maximum instantané, record historique, moyenne/volume publiés et étalonnage. |
| Hydro 19 : remarque sur les pompages | Associer la note aux réponses concernées ; ne pas qualifier implicitement le débit de naturel. |
| Pluvio 48 : légende des symboles | Conserver point, vide et gris ; distinguer jour sec, absence et cumul ultérieur selon la légende. Vérifier les tirets réellement rencontrés sans les assimiler automatiquement à zéro. |
| Totaux portant une mention de lacunes | Conserver le libellé publié et le nombre de jours manquants ; bloquer un recalcul complet si les entrées ne couvrent pas la période. |
| Pluvio 144–145 : mêmes quatre stations, certaines cellules différentes | Comparer cellule par cellule ; conserver les deux provenances et les divergences. Ne pas dédupliquer sur le seul nom ou total annuel. |
| Pluvio 48 : effectifs annoncés | Vérifier l’écart entre la somme des effectifs par bassin (728) et le total annoncé (726) ; distinguer ces nombres des effectifs réellement ingérés. |
| Pluvio 6 et 9 : réseau, sélection et historique | Distinguer les 726 stations annoncées des 148 sélectionnées pour la synthèse ; conserver les autres années du tableau historique. |
| Pluvio 24–26 : tableaux de synthèse | Contrôler la géométrie des lignes/colonnes : l’ordre textuel extrait peut décaler les attributions. |
| Coordonnées de stations, notamment pluvio 37 | Vérifier valeur, système de coordonnées et attribution ; exclure des cartes les positions non validées. |
| Hydro : L/s, m³/s, hm³ et codes particuliers | Garder unités et symboles bruts ; examiner notamment `-999`, `9999`, `PE`, « sec » et « STAGNANT » avant interprétation. |
| Hydro 71 et 108 | Revérifier les lacunes, identifiants et dimensions des tableaux de crue signalés pendant la lecture ; isoler toute ambiguïté persistante. |

### Pilote initial proposé : 25 pages

- Hydrologique : 17, 18, 19, 20, 31, 64, 71, 108.
- Pluviométrique : 6, 9, 24, 26, 37, 48, 50, 51, 78, 125, 144, 145, 176, 208, 225, 236, 242.

P02 vérifiera la représentativité réelle, incluant cartes, figures, étalonnage, barrages et formats ponctuels. Toute famille absente ajoutera ses pages au pilote. Le nombre de pages ne constitue pas à lui seul une preuve de couverture.

## 7. Exécution détaillée P00–P12

Une seule phase active. Chaque phase produit `reports/Pxx_report.md` et met à jour `docs/PROGRESS.md`, `docs/DECISIONS.md` et `docs/BLOCKERS.md`. Statuts : à faire, en cours, réalisée à examiner, acceptée pour la suite, bloquée. À la fin d’une phase, présenter les preuves et attendre la demande de poursuite conformément au mode de travail du dossier existant.

### P00 — Diagnostic et préparation

**Travaux :** inspecter les instructions applicables, l’état Git et les fichiers existants ; vérifier Python, outils PDF, RAM, GPU, espace disque et modèles ; enregistrer les deux sources et leurs empreintes ; établir la matrice exigences/composants présents/manquants. Définir les chemins et décisions réversibles.

**Livrables :** `docs/ENVIRONMENT.md`, registre des sources, fichiers de suivi et rapport P00.

**Passage :** environnement décrit par des commandes réellement exécutées, sources localisées, état existant préservé et prérequis manquants nommés. La lecture préalable ne remplace pas ce diagnostic.

### P01 — Paquet, configuration et contrats

**Dépendance :** P00. Créer l’environnement isolé, le paquet installable, la CLI `doctor`, les contrats stricts, leurs JSON Schema et les adaptateurs de modèles. Définir aussi les contrats de services de l’interface.

**Livrables :** `pyproject.toml`, verrouillage des versions, configuration, modules domain/providers, CLI et tests de contrats.

**Passage :** installation et diagnostic exécutables ; rejet des champs supplémentaires, opérations inconnues et périodes invalides ; modèles indisponibles signalés honnêtement.

### P02 — Inventaire des 387 pages

**Dépendance :** P01. Enregistrer pour chaque page ses dimensions, rotation, numéro imprimé, section, familles de blocs, état du texte et besoins d’OCR. Repérer les tableaux et figures, construire le pilote et produire des images avec rectangles superposés.

**Livrables :** `page_inventory.jsonl`, manifeste du pilote, catalogue des familles et images de référence.

**Passage :** 145 + 242 pages suivies sans omission ; repère géométrique vérifié ; familles non prises en charge identifiées.

### P03 — Extraction du pilote

**Dépendance :** P02. Séparer les blocs avant extraction ; reconstruire cellules, lignes, colonnes, en-têtes et notes. Conserver symboles et informations visuelles utiles. Comparer les méthodes natives et structurelles ; réserver l’OCR aux régions défaillantes. Vérifier visuellement les attributions et les cellules de référence.

**Livrables :** brut, cellules candidates, images des blocs et `reports/pilot_extraction.md`.

**Passage :** aucun mélange de stations connu dans le lot accepté ; chaque candidat est localisable ; échecs identifiés par famille et corrigés ou isolés.

### P04 — Normalisation et qualité

**Dépendance :** P03. Construire les registres de stations, alias, indicateurs, unités et références. Normaliser nombres et calendrier ; interpréter les symboles seulement avec preuve. Contrôler sommes, extrema, périodes, doublons, divergences et couverture. Définir des tolérances à partir de la précision source, sans les ajuster pour faire disparaître un écart.

**Livrables :** registres, candidats normalisés, règles versionnées et rapport qualité.

**Passage :** jours impossibles rejetés, lacunes séparées des zéros, types de maxima distincts, ambiguïtés exclues des calculs et méthodes de revue enregistrées.

### P05 — SQLite, provenance et publication pilote

**Dépendance :** P04. Appliquer les migrations, charger candidats/preuves, sélectionner les observations canoniques admissibles et publier une release pilote. Mettre en place lecture seule, intégrité, idempotence et publication atomique.

**Livrables :** base et manifeste pilote, dépôts de données, commandes `publish`, `coverage`, `inspect-source`.

**Passage :** une valeur réelle est retrouvée avec sa bonne page et son rectangle ; réingestion sans duplication ; publication interrompue sans perte de la release précédente.

### P06 — Recherche documentaire

**Dépendance :** P05. Découper selon sections et stations, relier les passages à leurs parents, indexer FTS5 et vecteurs. Préserver les recherches exactes par code/nom. Fusionner les rangs et dédupliquer ; utiliser les résumés de tableaux pour la découverte, jamais comme entrées de calcul.

**Livrables :** index versionnés, recherche hybride, annotations de développement et rapport comparant lexical, vectoriel et hybride.

**Passage :** rappel mesuré sur les preuves annotées et compatibilité base/index contrôlée. Activer un reranker seulement si son gain est mesuré. Un composant absent reste un blocage explicite.

### P07 — Moteur numérique

**Dépendance :** P05 ; exécution après P06 dans le suivi séquentiel. Implémenter lookup, agrégations admissibles, comparaisons et calculs avec SQL paramétré et Decimal. Les classements interrogent toutes les observations admissibles du périmètre, sans dépendre du top-k documentaire.

**Livrables :** bibliothèque de formules, dérivations et entrées sourcées, tests indépendants synthétiques et réels.

**Passage :** gestion correcte des unités, périodes, lacunes, ex æquo et références nulles ; chaque résultat indique formule, entrées, arrondi, couverture et origine publiée/calculée.

### P08 — Planificateur et orchestration

**Dépendances :** P06 et P07. Donner au LLM un catalogue borné d’entités et d’opérations. Valider son plan par code avant toute exécution. Gérer questions documentaires, numériques et mixtes avec dépendances explicites. Clarifier les stations, périodes, maxima ambigus et contradictions entre filtres et question.

**Livrables :** prompt R1, validateur, orchestrateur, états et budgets configurables.

**Passage :** identifiants inventés, opérations interdites et contenu parasite rejetés ; chaque sous-question garde son statut ; reprises et délais sont bornés. Valeurs de départ du dossier : une réparation de schéma, une nouvelle recherche, six opérations et délai de 90 secondes, à mesurer.

### P09 — Réponses et validation finale

**Dépendance :** P08. Construire le dossier de preuves avant rédaction. Rendre les chiffres depuis les résultats contrôlés ; utiliser R2 pour les formulations documentaires et R3 pour une réparation ciblée. Construire les citations par code et relier chaque affirmation à ses preuves.

**Livrables :** gabarits, prompts versionnés, contrôle des réponses et services applicatifs.

**Passage :** nombre, unité, date, station ou citation altérés détectés ; causalité sans preuve retirée. Une seule réparation, puis réponse limitée aux faits vérifiés. Une correspondance de nombres seule ne suffit pas à valider une affirmation.

### P10 — Cinq espaces Streamlit et extension à tout le corpus

**Dépendance :** P09. Relier les cinq espaces à la release réelle. Implémenter filtres, clarifications, historique de session, navigation aux preuves, graphiques et exports. Étendre ensuite les extracteurs à toutes les familles et toutes les pages, avec contrôles de régression du pilote ; publier une nouvelle release cohérente.

**Livrables :** application, visualiseur, exports, release issue du corpus entier et rapport de couverture.

**Passage :** toutes les pages ont un état explicite ; liens vers la bonne preuve ; aucune donnée fictive ni réponse en dur ; limites visibles. « Toutes les pages traitées » ne signifie pas « toutes les cellules validées ».

### P11 — Acceptation et corrections

**Dépendance :** P10. Exécuter les tests unitaires, d’intégration, de bout en bout et UI. Évaluer les questions réservées avec les modèles réels. Mesurer qualité, couverture des réponses, abstentions et latence ; corriger les causes racines. Si le lot réservé sert au réglage, l’indiquer et réserver de nouveaux cas.

**Livrables :** résultats détaillés, captures des cinq espaces et des états d’erreur/clarification, rapport des défauts et tests non exécutés.

**Passage :** critères de la section 10 mesurés ; aucun échec critique masqué. Distinguer validation logicielle, conformité d’extraction et validation métier humaine réellement obtenue.

### P12 — Livraison Windows et reprise

**Dépendance :** P11. Vérifier installation dans un environnement propre accessible, lancement, sauvegarde/restauration et reconstruction d’index. Produire les guides et scripts `run_app.ps1` et `doctor.ps1`, ancrés sur `$PSScriptRoot` et utilisant explicitement `.venv/Scripts/python.exe`.

**Livrables :** README, guides installation/utilisation/reprise, modèles et versions documentés, `reports/DELIVERY.md`.

**Passage :** démarrage Windows reproductible avec chemins comportant des espaces ; consultation réelle ; restauration vérifiée ; prérequis d’installation et fonctionnement hors ligne décrits selon les essais. Aucun traitement d’ingestion au démarrage de Streamlit.

## 8. Formules et garde-fous du moteur

| Opération | Définition | Conditions essentielles |
|---|---|---|
| Différence | A − B | Unités, périodes, références et périmètres compatibles. |
| Rapport à une référence | 100 × P/R | R connu, positif et compatible. |
| Anomalie relative | 100 × (P − R)/R | Même référence ; signe expliqué. |
| Déficit | 100 × (R − P)/R | Même référence ; sens du résultat explicite. |
| Cumul de pluie | Somme des observations couvrant la période | Sans doublons, chevauchements de cumuls ou lacunes non résolues. |
| Moyenne temporelle | Somme(valeur × durée) / somme(durée) | Durées et couverture connues ; mois pondérés par leurs jours. |
| Volume de débits moyens journaliers | Somme(Qj × 86400) / 1 000 000 en hm³ | Qj en m³/s, jours couverts et données admissibles. |
| Minimum / maximum | Extrême et toutes ses dates ex æquo | Qualifier la période effectivement couverte. |

Interdire la somme de pluies de stations différentes comme pluie régionale. Conserver séparément valeur publiée et recalculée, avec comparaison selon une tolérance justifiée par les arrondis sources. Interdire SQL, Python ou expressions libres fournis par le modèle ; autoriser uniquement les opérations typées prévues.

## 9. Interface, services et exploitation

Les pages appellent `get_status`, `ask`, `resolve_clarification`, `list_entities`, `list_metrics`, `query_observations`, `compare`, `get_source_page`, `get_coverage`, `export_answer` et `export_rows`. Le moteur métier reste testable sans Streamlit.

L’interface applique la spécification existante : français, fond clair, bleu profond, unités près des valeurs, statuts textuels, navigation clavier et fenêtre étroite utilisables. Une réponse factuelle s’affiche après contrôle final ; aucun streaming de faits non vérifiés.

Garder l’historique en état de session et associer chaque réponse à sa release. Inclure release et filtres dans les clés de cache ; un clic sur une citation ne rappelle pas le LLM. Générer les pages PDF à la demande. Résoudre les sources à partir du registre autorisé, jamais d’un chemin arbitraire proposé par le modèle.

Les graphiques marquent les lacunes par des ruptures. Les exports reprennent valeurs, période, unités, provenance et limites de l’écran. Le CSV est documenté pour Excel Windows et neutralise les cellules textuelles interprétables comme formules ; les exports partageables omettent les chemins privés absolus.

La CLI future comprend : `doctor`, `register`, `inventory`, `extract --scope pilot|all`, `validate --scope pilot|all`, `publish`, `index`, `ask`, `coverage`, `inspect-source`, `evaluate`, `rebuild-index`, `backup`, `restore`. Elle doit avoir une aide et des codes de sortie testés. Ces commandes restent à implémenter.

## 10. Stratégie de tests et critères de livraison

Construire progressivement le jeu de 120 questions prévu : 20 documentaires, 25 lectures numériques, 20 calculs, 15 comparaisons, 15 ambiguïtés/fautes, 15 hors périmètre/non couvertes, 10 anomalies/instructions parasites. Séparer développement et test final par stations/pages lorsque possible. Chaque annotation indique attente, preuves, tolérance, méthode de revue et auteur/processus.

Réexaminer G01–G12 sur les originaux avant annotation définitive, notamment Pont de Bizerte, Amdoun, les quatre tableaux, l’historique et les pompages. Ajouter des régressions pour les symboles, séries lacunaires et fiches répétées signalées dans ce plan.

Tester aussi les jonctions : PDF→cellule→observation ; observation→calcul→preuve ; plan→exécution→réponse ; citation→page/rectangle ; publication→index→cache. Inclure calendrier invalide, unités incompatibles, référence nulle, ex æquo, conflit source, erreur de modèle, mauvaise release et interruption de publication.

| Critère d’acceptation | Preuve attendue |
|---|---|
| 100 % des observations publiées ont une preuve localisable | Audit des liens document/page/bloc et contrôles visuels documentés. |
| Aucun échec critique dates/unités/symboles/stations/maxima | Résultats des tests réellement exécutés. |
| Aucune réponse numérique incorrecte acceptée dans le lot final contrôlé | Valeur, unité, période et effectif du lot publiés. |
| Citations valides et pertinentes dans ce lot | Correspondance entre affirmation et preuve, pas seulement lien ouvrable. |
| Rappel documentaire cible ≥ 95 % | Définition du rang, des preuves attendues et du dénominateur. |
| Questions couvertes correctement résolues : cible ≥ 90 % | Mesure incluant les abstentions injustifiées. |
| 387 pages avec état | Effectifs par document/famille et exclusions motivées. |
| UI et exploitation vérifiées | Navigation, exports, panne modèle, cache, installation et restauration testés. |

Ces seuils décrivent un jeu d’évaluation défini, pas une garantie universelle. Rapporter séparément succès, échec, non testé et blocage. Une couverture faible ne devient pas acceptable simplement en refusant toutes les questions.

## 11. Jalons, risques et reprise

| Jalon | Résultat concret |
|---|---|
| Après P02 | Inventaire intégral et pilote représentatif. |
| Après P05 | Première valeur réellement extraite, consultable avec preuve. |
| Après P07 | Calcul traçable fonctionnant sans LLM. |
| Après P09 | Question → réponse contrôlée de bout en bout. |
| Après P10 | Cinq espaces fonctionnels et couverture de toutes les pages déclarée. |
| Après P12 | Livraison Windows testée et limitations documentées. |

Principaux risques : extraction désalignée, conventions graphiques perdues dans le texte, références incompatibles, codes ou coordonnées douteux, fiches contradictoires et ressources matérielles insuffisantes. Les traiter par segmentation, revue sourcée, quarantaine ciblée, adaptation mesurée des modèles et suivi de couverture. Aucun de ces risques ne se résout en demandant au LLM d’inventer les données manquantes.

Aucun calendrier ferme n’est fixé avant le diagnostic matériel et les mesures du pilote. Réestimer après P03 à partir du nombre de familles, du taux d’échec et du coût de revue, puis après P09 pour l’extension et l’interface.

Pour reprendre après interruption : lire le dernier rapport, la progression, les décisions et les blocages ; vérifier la release et le run concernés ; reprendre la première tâche inachevée de la phase active. Ne pas refaire ni déclarer acceptées des étapes sans preuve.

**Première étape d’exécution prévue : P00, diagnostic et préparation de l’environnement.** Le présent livrable est le plan ; les phases restent à faire.

## 12. Références locales

- [Plan directeur](../RAG_DGRE_Plan_Complet/plan_implementation/specifications/01_PLAN_DIRECTEUR.md)
- [Interface Streamlit](../RAG_DGRE_Plan_Complet/plan_implementation/specifications/02_INTERFACE_STREAMLIT.md)
- [Qualité et acceptation](../RAG_DGRE_Plan_Complet/plan_implementation/specifications/03_QUALITE_ET_ACCEPTATION.md)
- [Guide d’implémentation](../RAG_DGRE_Plan_Complet/plan_implementation/references/Guide_Agent_Implementation_RAG_DGRE.md)
- [Architecture](../RAG_DGRE_Plan_Complet/plan_implementation/references/Architecture_RAG_DGRE.md)
- [Schéma SQL initial](../RAG_DGRE_Plan_Complet/plan_implementation/schemas/001_initial.sql)
- [Cas d’évaluation](../RAG_DGRE_Plan_Complet/plan_implementation/evaluation/CAS_ET_CRITERES.md)
- [Configuration de départ](../RAG_DGRE_Plan_Complet/plan_implementation/configuration/app.example.yaml)
