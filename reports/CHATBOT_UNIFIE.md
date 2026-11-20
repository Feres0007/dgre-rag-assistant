# Livraison — Assistant DGRE unifié

La navigation comporte maintenant deux pages : **Assistant** et **Sources**. Les trois anciennes pages ont été retirées. Le chatbot demande les précisions utiles directement dans la conversation.

## Capacités intégrées

- Consultation des observations, séries mensuelles ou journalières, et tableaux annuels pour une station ou toutes les stations.
- Comparaison de deux observations et de valeurs issues des notices, dont les capacités de barrages. Les différences sont calculées par le moteur existant, avec contrôle des unités, du périmètre et des périodes.
- Comparaison d’une station sur deux années lorsqu’elles sont disponibles ; réponse partielle si une valeur manque.
- Questions sur les données disponibles, les anomalies et les lacunes, ainsi que les classements déjà pris en charge par le service.
- Tableaux, graphiques et téléchargements CSV dans les messages. Les fichiers incluent les références disponibles. Les grands tableaux sont limités à 500 lignes à l’écran, avec la sélection complète dans le téléchargement.
- Consultation des preuves PDF puis retour à la conversation conservée.
- Relances : autre station, comparaison des deux valeurs précédentes, mois suivant, graphique, téléchargement et sources. Les données d’une ancienne version du corpus ne sont pas reprises silencieusement.

## Exemples à essayer

1. « Quel est le total annuel à Aïn Draham en 2022–2023 ? »
2. « Et à Amdoun ? »
3. « Compare les deux. »
4. « Fais un graphique. »
5. « Télécharge le tableau. »

Autres demandes :

- « Montre les pluies mensuelles à Aïn Draham. », puis « 2022–2023 ».
- « Montre les pluies mensuelles à Aïn Draham en mai 2023. », puis « Et le mois suivant ? ».
- « Compare les capacités des barrages Sidi Salem et Mellègue. »
- « Quelles stations disposent de débits moyens annuels ? »
- « Pourquoi le débit annuel de Tessa Pont manque-t-il ? »
- « Affiche les pluies annuelles de toutes les stations en 2022–2023. »

## Organisation du code

`answers/conversation.py` prépare les demandes, conserve le contexte, exécute les consultations et prépare les présentations. `answers/reference_values.py` expose les valeurs des synthèses avec leur provenance, sans les faire passer pour de nouvelles observations de la base. `Service.ask()` est le point d’entrée commun de l’interface et des audits.

Le modèle local reste utilisé par les fonctions de compréhension et de rédaction qui en ont besoin. Les parcours déterministes testés fonctionnent aussi sans lui. Les graphiques n’interpolent pas les lacunes. Les demandes ambiguës et les informations absentes restent signalées.

## Vérification

Résultat final : **99 tests réussis** et **230 cas conformes aux critères de l’audit**, réserves documentaires comprises. La reprise de la campagne vérifie que ses empreintes correspondent au code livré. L’application a été redémarrée ; son endpoint de santé répond `ok` sur `127.0.0.1:8501`.

La suite de tests couvre les anciens contrôles et les nouveaux parcours de conversation. Les tests Streamlit vérifient également l’absence de filtres manuels dans le chatbot, le graphique, l’ouverture d’une page PDF, le retour à la conversation et sa réinitialisation.

L’audit complet est conservé dans [chatbot_unifie_livraison](question_audits/chatbot_unifie_livraison/rapport.html), avec ses réponses, critères et empreintes de versions. Les contrôles des 230 questions restent des vérifications ciblées, et non une certification scientifique générale.
