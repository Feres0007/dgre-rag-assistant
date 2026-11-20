# Cas de test à implémenter et à revérifier sur les PDF

Aucun résultat applicatif n’a encore été mesuré.


### 11.1 Références réelles initiales à revérifier sur les PDF

Ces cas proviennent de l’analyse précédente des fichiers fournis. L’agent doit rouvrir les pages avant d’en faire les annotations de référence. Ils servent aux tests, jamais au code de réponse en production.

| ID | Question ou contrôle | Attendu et preuve |
|---|---|---|
| G01 | Maximum journalier de Pont de Bizerte, 2022-2023 | 30,86 m³/s, 2 juin 2023 ; hydro PDF 18, imprimée 17. |
| G02 | Maximum instantané, même station/période | 32,4 m³/s, 2 juin 2023 à 08:45 ; même fiche. |
| G03 | Crue historique mentionnée | 294 m³/s, 28 février 2012 ; ne pas attribuer à 2022-2023. |
| G04 | Gouvernorat de cette station dans l’annuaire | Ariana ; hydro PDF 17–18. |
| G05 | Minimum journalier de cette station | 0,843 m³/s, 13 septembre 2022 ; hydro PDF 18. |
| G06 | Débit moyen annuel publié | 14,99 m³/s ; hydro PDF 18, distinguer d’un recalcul éventuel. |
| G07 | Volume annuel publié | 471,31 hm³ ; hydro PDF 18, ne pas remplacer par un résultat calculé. |
| G08 | Total annuel publié à Amdoun | 427,5 mm ; pluvio PDF 50, imprimée 47, bloc en haut à gauche. |
| G09 | Séparation de quatre tableaux | Amdoun, Sidi El Barrak, Belif et Bou Brima restent distincts ; pluvio PDF 50. |
| G10 | Peut-on chercher une synthèse 2018-2019 ? | Oui dans le tableau régional historique ; pluvio PDF 9. Pas de refus fondé uniquement sur l’édition. |
| G11 | Couverture annoncée et échantillon national | Distinguer 726 stations observées et 148 sélectionnées ; pluvio PDF 6. Ne pas prétendre avoir extrait ces effectifs sans comptage. |
| G12 | Débit « naturel » à Pont de Bizerte | Mentionner la remarque sur les pompages si pertinente ; hydro PDF 19. Pas d’attribution causale quantitative inventée. |

### 11.2 Cas limites à fabriquer seulement dans les tests

- 29 février 2023, 31 avril, changement décembre/janvier.
- Tiret indéterminé, zéro explicite, cellule manquante et trace éventuelle.
- Deux tableaux voisins avec nombres identiques mais stations différentes.
- Deux noms semblables, code absent, code atypique conservé.
- Deux observations contradictoires et doublon identique entre sources.
- Somme de cumul mensuel, moyenne mensuelle non pondérée, mois manquant.
- Référence nulle, unité incompatible, valeurs non finies, date hors période.
- Maximum ex æquo, classement avec résultat pertinent hors top-k documentaire.
- JSON invalide, opération interdite, nom de colonne injecté, identifiant de source inventé.
- Texte source contenant une instruction parasite ; aucune modification du comportement.
- LLM indisponible, délai dépassé, index d’une autre release.
- Nombre, date ou page modifié après génération ; phrase causale sans preuve.
- Publication interrompue, réingestion répétée et restauration de version.

### 11.3 Jeu de 120 questions

Répartition de départ : 20 documentaires ; 25 lectures numériques ; 20 calculs ; 15 comparaisons ; 15 questions avec fautes ou ambiguïtés ; 15 hors périmètre ou non couvertes ; 10 anomalies/instructions parasites. Éviter les doublons qui ne changent qu’un mot. Les cas synthétiques restent identifiables et n’entrent pas dans l’index métier.

Chaque annotation contient `question_id`, `question`, `split`, `category`, `expected_status`, `expected_facts`, `required_evidence`, `tolerance`, `review_method`, `reviewer_or_process`, `review_date`. Ne pas nommer un jeu « validé humainement » si seulement un agent l’a contrôlé. L’acceptation métier par la DGRE demeure un statut distinct du test logiciel.

### 11.4 Seuils de livraison proposés

| Critère | Exigence |
|---|---|
| Provenance des observations publiées | 100 % avec preuve localisable. |
| Tests critiques calendrier/unités/symboles/stations/maxima | Tous réussis, zéro échec masqué. |
| Réponses numériques acceptées du jeu final | Aucune valeur/unité/période incorrecte dans le lot ; rapporter l’effectif. |
| Citations du jeu final | Toutes les citations valides et soutenant les faits associés. |
| Rappel documentaire des preuves au rang retenu | Cible ≥ 95 %, avec effectif et définition de la métrique. |
| Questions couvertes et répondables | Cible ≥ 90 % résolues correctement ; mesurer les abstentions injustifiées. |
| Ensemble du corpus | Chaque page dispose d’un statut ; couverture par indicateur et entité publiée. |
| Reproductibilité | Installation, ingestion idempotente, démarrage et restauration vérifiés sur l’environnement testé. |

Mesurer exactitude, complétude et abstention séparément. Ces critères sont des objectifs d’acceptation pour un jeu défini, pas une promesse universelle. Un jeu final trop petit ou seulement contrôlé par l’agent doit être décrit comme tel. Si un seuil échoue, livrer l’état réel comme partiel et les corrections nécessaires.

