# Bilan de l’audit des 230 questions

Campagne finale : `controle_final`, exécutée avec le même service que l’interface et le mode `full` (modèle local disponible). Les 230 questions ont été traitées indépendamment, avec le contexte hydrologique 2022–2023 annoncé par la liste.

| Résultat | Nombre |
|---|---:|
| Réponse obtenue | 210 |
| Question nécessitant une précision | 8 |
| Information non établie par les documents consultés | 11 |
| Résultat non publié en raison de lacunes | 1 |
| Erreur technique pendant la campagne finale | 0 |

Les **230 cas satisfont les critères annotés**, y compris ceux où la bonne conduite consiste à demander une précision ou à expliquer une limite. Ce résultat ne signifie pas que les 230 questions ont reçu une valeur numérique, ni que toutes les phrases et toutes les données nationales sont certifiées exactes. Les critères sont visibles dans le rapport HTML et le CSV.

Le premier passage complet conservé (`verification_complete`), réévalué avec les mêmes critères finaux, présente **166 cas conformes et 64 problèmes**. La campagne finale présente **230 cas conformes et aucun problème détecté par ces critères**. Ce sont des mesures sur cette liste précise, pas sur des questions nouvelles.

## Corrections appliquées

- Séparation de la pluie, des débits et des hauteurs d’eau : une question sur une rivière ne reçoit plus le cumul national de pluie par confusion avec le mot « plus ».
- Distinction entre le verbe « a été » et la saison « été ».
- Exploitation des bilans régionaux, des moyennes par gouvernorat, des tableaux mensuels et saisonniers et de l’historique des huit années.
- Lecture des capacités et apports des barrages sans les confondre avec leur stock ou leur remplissage.
- Reconnaissance améliorée des stations, notamment Rmel Pont Route, Mateur et Sidi Bouzid. Mellègue GP17 et Mellègue K13 restent distinctes.
- Récupération des événements de crue dont les dates sont décalées dans le texte extrait. Les unités contradictoires restent signalées.
- Comparaisons affichant les valeurs et les noms des stations, en plus de leur différence.
- Réponses sur les jours de pluie, les coordonnées, les méthodes de mesure et les responsabilités indiquées dans les publications.
- Traduction locale des questions arabes avec conservation des noms géographiques du corpus.
- Audit reprenable, réponses conservées individuellement, empreintes des versions et protection contre la réutilisation de critères après modification d’une question.

Les données de synthèse sont extraites des PDF et accompagnées de leurs preuves. Les références d’évaluation sont séparées du système de réponse. Les originaux et la base publiée n’ont pas été modifiés.

## Cas nécessitant une réserve

Les questions **23, 30, 38, 63, 64, 65, 78 et 127** nécessitent de préciser un poste, un périmètre ou une mesure. L’assistant ne remplace pas une ville par un gouvernorat, une station par une autre, ou une hauteur d’eau par un débit.

Les questions **16, 19, 20, 88, 183, 187, 188, 213, 221, 222 et 224** ne disposent pas d’une preuve suffisante pour la conclusion demandée : remplissage, recharge des nappes, satisfaction des besoins agricoles, comparaisons absentes ou informations extérieures au corpus.

Pour la question **158**, la fiche de Tessa Pont indique trop de lacunes pour publier le débit moyen annuel. Aucun chiffre n’a été inventé pour combler ce manque.

Un total nul imprimé ne suffit pas à établir la complétude d’une fiche. Les classements sont explicitement limités aux observations disponibles. Les incohérences d’unités des tableaux de crues ne sont pas corrigées silencieusement.

## Vérification du logiciel

**89 tests réussis**, dont les régressions détectées par cet audit, l’importation sûre des questions, le contrôle des preuves et les tests de l’interface Streamlit. Le lancement PowerShell et la reprise d’une campagne terminée ont également été vérifiés.

- [Rapport complet](controle_final/rapport.html)
- [Tableau des réponses](controle_final/reponses.csv)
- [Résumé mesuré](controle_final/summary.json)
- [Versions utilisées](controle_final/manifest.json)
- [Guide pour relancer](../../evaluation/LIRE_MOI_AUDIT.md)
