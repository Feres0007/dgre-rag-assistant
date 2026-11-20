# Qualité, tests et acceptation

## Trois validations distinctes

1. Logiciel : contrats, calculs, états, intégration, sources et interface.
2. Extraction : conformité des valeurs et de leur rattachement aux PDF.
3. Métier : interprétation des conventions ambiguës et usage hydrologique, éventuellement par un expert humain.

Un agent peut tester le logiciel et comparer visuellement des cellules. Il ne doit pas déclarer une approbation humaine ou institutionnelle. Le suivi indique la méthode et l’auteur/processus de chaque revue.

## Exigences traçables

| ID | Exigence | Phase | Preuve requise |
|---|---|---|---|
| COR-01 | Seulement deux PDF autorisés | P00/P05 | Manifeste d’empreintes et test d’exclusion. |
| EXT-01 | Attribution correcte des quatre tableaux | P03/P04 | Image, cellules et cas de la page pluviométrique 50. |
| EXT-02 | Journalier/instantané/historique séparés | P04 | Cas Pont de Bizerte revérifiés sur le PDF. |
| DAT-01 | Dates, symboles et unités | P04/P07 | Tests de jours inexistants, tirets et conversions. |
| DAT-02 | Provenance et conflits | P05/P09 | Preuves par observation et test de conflit. |
| CAL-01 | Calcul déterministe | P07 | Tests indépendants et dérivations traçables. |
| RET-01 | Recherche mesurée | P06 | Comparaison lexical/vectoriel/hybride et rappel. |
| PLN-01 | Plans admissibles et clarification | P08 | Schémas rejetés, entités ambiguës et demandes mixtes. |
| ANS-01 | Contrôle après rédaction | P09 | Valeurs altérées et affirmation sans preuve détectées. |
| UI-01 | Cinq espaces complets | P10/P11 | Tests UI et inspection visuelle. |
| UI-02 | Navigation vers les preuves | P10/P11 | Bonne page, bon rectangle, pas d’appel LLM supplémentaire. |
| UI-03 | Erreurs, limites et exports | P10/P11 | États contrôlés et export fidèle. |
| OPS-01 | Versionnement et restauration | P05/P12 | Échec atomique et retour à une release précédente. |
| WIN-01 | Windows et chemins avec espaces | P00/P12 | Commandes réellement exécutées sur le poste cible. |
| COV-01 | Toutes les pages suivies | P10/P11 | Effectifs et exclusions par famille. |

## Règles de tests

Les exemples réels G01–G12 du guide doivent être confirmés sur les fichiers originaux avant annotation. Les tests synthétiques utilisent des noms et statuts explicites ; ils ne sont jamais indexés comme mesures DGRE. Éviter les tests qui reproduisent l’algorithme à l’identique plutôt que de vérifier une propriété ou un résultat indépendant.

Développement et test final ont des groupes séparés de stations/pages quand possible. Si un test final sert à corriger le système, le signaler et réserver de nouveaux cas pour l’évaluation suivante. Les prompts et modèles ont une version dans chaque résultat. Tester les liens entre modules autant que les modules.

Enregistrer pour chaque question : attente, résultat, statut, précision des chiffres, preuve de source, couverture de la réponse, latence et échec éventuel. Un système qui refuse tout ne satisfait pas le critère de réponse utile.

## Portes d’acceptation

- 100 % des observations publiées avec preuve localisable.
- Aucun test critique de dates, unités, attribution de station et maximum en échec.
- Aucune réponse numérique incorrecte acceptée dans le lot final contrôlé, avec effectif publié.
- Citations valides et soutenant les faits sur le lot contrôlé.
- Cible de rappel documentaire ≥ 95 % et taux de résolution correcte des questions couvertes ≥ 90 %, mesurés et non supposés.
- Toutes les pages disposent d’un état et les exclusions restent visibles.
- Navigation, clarifications, panne de modèle, exports et changements de release vérifiés.
- Installation, démarrage et restauration reproductibles dans l’environnement effectivement testé.

Ces seuils sont des objectifs pour un jeu défini, pas une garantie universelle. Si un critère échoue ou ne peut être testé, le rapport dit « partiel », « bloqué » ou « non testé ».

## Rapport de fin de phase

Utiliser le modèle fourni dans `suivi/RAPPORT_PHASE_MODELE.md`. La décision de passage n’est pas préremplie. À la fin de chaque phase, l’agent annonce : ce qui est prêt, preuves des vérifications, défauts connus, impact sur la suite et phase suivante proposée. Il attend la demande de poursuite.

## Livraison attendue

Code installable, configuration sans secrets, dépendances verrouillées, manifeste des modèles, base/release, index reconstructibles, rapports d’extraction, jeu d’évaluation, captures UI, guide utilisateur et procédures Windows. Ne pas déposer une base gigantesque dans Git sans décision ; versionner code et contrats, documenter les sauvegardes de données.

Le rapport final distingue : composants réalisés, critères vérifiés, couverture du corpus, validations humaines réellement effectuées, défauts résiduels, commandes de lancement et éventuelle restriction d’usage liée aux sources. La documentation d’installation ne doit pas être présentée comme testée sur Windows si seul Linux était accessible.
