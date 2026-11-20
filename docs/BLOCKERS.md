# Limites et travail restant

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
