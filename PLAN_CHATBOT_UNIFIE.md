# Plan d’implémentation — Assistant DGRE unifié

## Résultat attendu

L’interface comporte seulement deux espaces : **Assistant** et **Sources**. Toutes les demandes de consultation, de comparaison, de classement, de graphique, d’export et de disponibilité des données passent par la conversation. L’utilisateur décrit son besoin en langage naturel.

Les entrées « Explorer les données », « Comparer » et « Données disponibles » disparaissent de la navigation. Leurs fonctions utiles sont accessibles depuis le chatbot. La page Sources conserve la consultation des PDF et l’ouverture de la page citée dans une réponse.

## État actuel et écarts

- `app/streamlit_app.py` déclare cinq pages.
- `app/pages/assistant.py` possède encore des filtres de station et d’année. Le contexte conversationnel transmis se limite aux trois derniers échanges.
- Le service possède déjà les fonctions de consultation, de comparaison, de couverture et d’export utilisées par les pages séparées.
- Le planificateur sait comparer certaines paires de valeurs. Il doit être étendu pour reconnaître les demandes plus naturelles et les changements de période dans une conversation.
- Certaines réponses du catalogue de synthèses ne renseignent pas les faits structurés utilisés pour les relances. Leur contexte doit être représenté aussi, sans transformer leurs valeurs en observations canoniques fictives.

## 1. Unifier le résultat et le contexte de conversation

Conserver pour chaque échange les entités résolues, le périmètre géographique, les mesures, les périodes, les sources, les valeurs utilisées et les éventuels résultats calculés. Distinguer les observations publiées des valeurs issues des tableaux de synthèse et des passages documentaires.

Maintenir un état conversationnel explicite : sélection actuelle, dernière comparaison et précision attendue. Une précision complète la demande en attente au lieu de concaténer indéfiniment les messages. Une nouvelle demande remplace le contexte qui la contredit. « Nouvelle conversation » réinitialise cet état.

Fichiers principaux : `src/dgre_rag/domain/models.py`, `src/dgre_rag/answers/service.py`, `src/dgre_rag/answers/reference.py`.

## 2. Comprendre les actions demandées

Faire reconnaître au système les intentions suivantes : chercher une information, consulter une série, comparer, classer, vérifier la disponibilité ou les lacunes, présenter un tableau ou un graphique, exporter et ouvrir une source.

Résoudre les noms de stations et de barrages, les gouvernorats, les régions, les indicateurs et les périodes. Étendre la compréhension des dates naturelles et des expressions comme « la même année », « le mois suivant » et « les deux stations ».

Le modèle local peut proposer une action structurée. L’application vérifie que l’action est autorisée et que ses paramètres correspondent aux données disponibles avant de l’exécuter. Elle demande une précision courte lorsque plusieurs interprétations restent possibles.

Fichiers principaux : `src/dgre_rag/query/planner.py`, `src/dgre_rag/domain/models.py`, `src/dgre_rag/answers/service.py`.

## 3. Effectuer les comparaisons dans le chatbot

Pour une demande de comparaison :

1. Identifier les deux sélections : lieu, mesure et période.
2. Rechercher chaque valeur et sa preuve séparément.
3. Vérifier les unités, les périodes, la qualité et la nature des sélections. Une moyenne de gouvernorat ne remplace pas la mesure d’une station.
4. Calculer l’écart dans le moteur de calcul existant. Calculer un pourcentage seulement si la référence est claire et non nulle.
5. Répondre avec les deux valeurs, la conclusion et les sources. Présenter un petit tableau si cela facilite la lecture.

Exemple de comportement attendu : « Compare les débits moyens annuels de Slouguia et Mejez GP5 en 2022–2023. » L’assistant retrouve 6,083 et 12,45 m³/s, puis indique que Mejez GP5 dépasse Slouguia de 6,367 m³/s, avec les pages justificatives.

Si une valeur manque, présenter celle qui est étayée et expliquer ce qui empêche la comparaison. Ne pas produire un écart à partir d’une estimation non autorisée.

Fichiers principaux : `src/dgre_rag/analytics/engine.py`, `src/dgre_rag/answers/service.py`, `src/dgre_rag/answers/reference.py`.

## 4. Intégrer l’exploration et la disponibilité des données

Rendre les capacités existantes accessibles par des questions comme :

- « Montre les pluies mensuelles à Aïn Draham en 2022–2023. »
- « Quelles stations disposent de débits moyens annuels ? »
- « Pourquoi le débit annuel de Tessa Pont manque-t-il ? »
- « Classe les stations de Béja par débit moyen. »
- « Présente ces valeurs dans un graphique. »
- « Télécharge le tableau de cette comparaison. »

Utiliser les fonctions réelles de consultation et de couverture du service pour déterminer ce qui est disponible. Distinguer une information présente dans un PDF d’une série suffisamment interprétée et complète pour un calcul.

Limiter l’affichage des grands tableaux, annoncer le nombre de lignes et permettre l’export complet de la sélection. Les graphiques utilisent les valeurs sourcées ; les lacunes restent visibles et ne sont pas interpolées automatiquement.

## 5. Simplifier l’interface

- Conserver seulement Assistant et Sources dans `app/streamlit_app.py`.
- Retirer les formulaires de choix de station et de période du chatbot ; obtenir ces précisions dans la conversation.
- Afficher un accueil simple, quelques suggestions de questions et le champ de saisie.
- Présenter la réponse d’abord, puis les tableaux ou graphiques utiles dans le même échange.
- Garder des actions discrètes : consulter les sources et télécharger un résultat.
- Employer des libellés compréhensibles, sans afficher les identifiants internes ou les paramètres du moteur.
- Après migration des fonctions, retirer les anciennes pages et leurs liens résiduels.

Fichiers principaux : `app/streamlit_app.py`, `app/pages/assistant.py`, `app/common.py`, `app/pages/sources.py` ; anciennes pages `explorer.py`, `comparer.py`, `couverture.py`.

## 6. Préserver l’accès aux preuves

Chaque résultat consulté ou calculé conserve ses références. Une comparaison donne accès aux sources des deux sélections. Le bouton d’une référence ouvre la bonne page PDF dans Sources. Le retour au chatbot conserve la conversation et ses résultats.

Les informations contenues dans les tableaux et figures sont utilisées lorsqu’elles sont interprétées de manière fiable. Sinon, l’assistant ouvre la preuve et indique précisément la limite de lecture.

## 7. Vérifier et livrer

Adapter les tests de navigation aux deux espaces et ajouter des scénarios conversationnels :

- comparaison de deux stations dans une seule question ;
- comparaison d’une station sur deux périodes disponibles ;
- relances « Et à Amdoun ? », « Compare les deux » et « Fais un graphique » ;
- précision donnée après une question ambiguë ;
- changement explicite de station, de mesure ou de période ;
- disponibilité et lacunes expliquées dans la conversation ;
- export correspondant exactement au résultat affiché ;
- ouverture d’une source puis retour à une conversation intacte ;
- fonctionnement sans modèle local pour les opérations que le système peut déjà résoudre directement.

Relancer les tests du projet et l’audit des 230 questions dans une nouvelle campagne, en conservant les résultats précédents. Les critères de l’audit contrôlent les réponses documentaires ; les nouveaux scénarios contrôlent les enchaînements de conversation et l’interface.

## Critères de fin

1. Seules les entrées Assistant et Sources sont visibles.
2. Recherche, comparaison, disponibilité, tableau, graphique et export fonctionnent depuis un échange.
3. Une comparaison retrouve les deux valeurs, vérifie leur compatibilité et fournit une conclusion calculée et sourcée.
4. Les relances réutilisent le bon contexte et les précisions manquantes sont demandées dans le chat.
5. Les limites du corpus restent expliquées clairement, sans inventer de valeur.
6. Les tests adaptés et la nouvelle campagne d’audit ne présentent aucune régression inexpliquée.

L’implémentation est documentée dans `reports/CHATBOT_UNIFIE.md`. Ce plan conserve les objectifs et critères qui ont guidé la migration.
