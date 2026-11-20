# Guide utilisateur

## Poser une question

Dans Assistant, indiquez une station et une période : « Quel est le maximum journalier de Pont de Bizerte en 2022-2023 ? ». Le calendrier 2022-2023 désigne septembre 2022 à août 2023. Une date ISO telle que `2023-06-02` permet une consultation journalière. Pour un intervalle, indiquez deux dates ISO.

« Quelle est la pluviométrie annuelle de la station Aïn Draham en 2022-2023 ? » donne directement le cumul publié dans le tableau, avec son unité, sa période et une référence lisible. Le bouton source ouvre la page du tableau pour vérification ; il n’est pas nécessaire de lire soi-même l’image pour retrouver la valeur demandée. « Valeurs lues dans les tableaux » détaille les observations utilisées.

Précisez journalier, instantané ou historique pour un maximum de débit. Si le nom correspond à plusieurs stations, sélectionnez la station dans les filtres ou utilisez son code exact. L’assistant demande une précision lorsque l’identification ou la période n’est pas résolue. Les filtres actifs apparaissent près de la saisie.

Une réponse « Valeur publiée » restitue une observation du document. Une demande telle que « Calcule la somme des pluies mensuelles de Amdoun du 2022-09-01 au 2023-08-31 » utilise le moteur de calcul. Un calcul complet est refusé lorsque sa série ne satisfait pas les conditions de couverture.

L’historique est limité à la session du navigateur. Une nouvelle conversation efface cet historique, pas les données. Exportez une réponse en Markdown pour conserver sa release, ses valeurs et ses preuves.

## Explorer

Choisissez station, indicateur et intervalle, puis cliquez sur « Afficher les données ». Le tableau affiche au maximum 500 lignes, avec le nombre total de la sélection. « Préparer le CSV » porte sur toute la sélection. Le CSV contient le point décimal, le séparateur point-virgule et des colonnes de provenance ; il est encodé en UTF-8 avec BOM pour Excel Windows.

Les graphiques représentent des points observés. Une absence n’est pas remplacée par une valeur nulle et aucune interpolation n’est effectuée.

## Comparer

Choisissez un indicateur commun et les périodes A et B. Chaque sélection doit produire une valeur validée. La différence est A − B ; un signe positif signifie que A dépasse B. L’écart relatif utilise B comme dénominateur lorsqu’il est positif. Des données lacunaires, périodes de durées différentes, unités ou références incompatibles bloquent la comparaison.

## Vérifier une source

Cliquez sur « Voir … page PDF … ». Sources affiche la page avec le bloc cité encadré et le numéro imprimé lorsqu’il a été identifié. Le numéro PDF commence à 1 et peut différer du numéro imprimé. Vous pouvez changer de page, ajuster le zoom et préparer le téléchargement du document original.

## Comprendre la couverture

Couverture distingue pages inventoriées, tableaux extraits, observations retenues et observations exclues. Les tableaux bruts non interprétés restent accessibles par la page source. Les mentions de lacunes et les anomalies ne sont pas corrigées automatiquement. Un total publié peut être consultable malgré l’impossibilité de recomposer une somme quotidienne fiable.

Cette application ne prévoit pas le temps ou les crues, et ne propose pas de décision automatique de gestion d’ouvrage. Les résultats restent accompagnés des limites de la source et de l’extraction.
