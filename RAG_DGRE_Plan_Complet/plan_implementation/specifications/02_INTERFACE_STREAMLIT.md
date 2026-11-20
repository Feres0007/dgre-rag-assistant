# Spécification de l’interface Streamlit

## 1. Expérience recherchée

L’utilisateur doit pouvoir poser une question en français, comprendre immédiatement la réponse et ouvrir la preuve sans connaître RAG, SQL ou les embeddings. L’interface doit rendre visibles période, unité et limites utiles. Elle ne doit pas transformer l’utilisateur en administrateur technique pour une simple consultation.

Nom de travail : **DGRE — Assistant des annuaires**. Sous-titre : « Consultez et comparez les observations publiées dans les deux annuaires. » Ne pas présenter le prototype comme une application officielle agréée ni employer un logo institutionnel non fourni.

Cette spécification décrit l’interface à implémenter. Elle ne contient pas de fausses captures d’une application fonctionnelle.

## 2. Navigation et disposition

Cinq entrées visibles dans la barre latérale :

| Espace | But | Action principale |
|---|---|---|
| Assistant | Poser une question et lire une réponse citée | Envoyer la question. |
| Explorer les données | Consulter les mesures validées par indicateur et station | Afficher puis exporter les lignes. |
| Comparer | Construire une comparaison sans ambiguïté | Comparer deux sélections compatibles. |
| Sources | Ouvrir un PDF, une page et un bloc | Vérifier la preuve originale. |
| Couverture | Voir les données disponibles et les limites | Consulter les exclusions et leur impact. |

La barre latérale contient aussi un état bref : corpus disponible, service de rédaction disponible ou indisponible, version de données sous un volet « Informations ». Les paramètres de modèle, top-k et chemins internes sont réservés à une section de diagnostic, hors du parcours courant. Ne pas masquer les limites qui changent la réponse.

Mise en page large sur PC : colonne principale pour la réponse, détails en volets dépliables ; Sources peut utiliser deux colonnes document/détails. Sur une fenêtre étroite, empiler les éléments sans bandeau débordant. Les tableaux restent défilables. Pas de défilement horizontal imposé à toute la page.

## 3. Style visuel à implémenter

| Élément | Proposition |
|---|---|
| Fond | Clair, légèrement grisé `#F5F7FA`. |
| Surfaces | Blanc, bordures discrètes. |
| Couleur principale | Bleu profond `#164E63`. |
| Texte principal | `#172B4D`, tailles lisibles, unités près des nombres. |
| Succès | Vert sombre accompagné du libellé « Vérifié par les contrôles ». |
| Limite | Ambre accompagné d’un texte précis. |
| Erreur | Rouge sombre avec message et action possible. |
| Typographie | Police sans empattement disponible localement, pas de dépendance à une police Web. |

Utiliser en priorité les composants natifs et le thème Streamlit. Éviter les hacks CSS dépendant de sélecteurs internes. Ne pas supprimer les contours de focus. Les statuts ne reposent jamais sur la couleur seule. Tous les boutons ont un libellé français explicite, les icônes restent complémentaires.

Dates affichées en français, valeurs décimales avec virgule à l’écran ; format machine conservé dans l’API. Une approximation est identifiée, sans décimales qui suggèrent une précision absente de la source.

## 4. Espace Assistant

### État initial

Afficher une introduction courte, un champ de saisie et trois exemples sélectionnables dont la disponibilité est confirmée par la release. Exemples à activer seulement après vérification : maximum journalier de Pont de Bizerte pour 2022-2023, méthode de présentation des observations, comparaison régionale issue du tableau historique.

Les exemples remplissent ou soumettent une demande normale ; aucune réponse en dur. Si aucune release n’est active, afficher « Les données ne sont pas encore prêtes » et l’accès à Couverture. Ne pas laisser le modèle répondre depuis sa mémoire.

### Question et filtres

Le champ indique « Posez une question sur les annuaires ». Les filtres facultatifs sont regroupés dans « Préciser la recherche » : période, gouvernorat/station et type de donnée. Par défaut, aucune année silencieusement imposée. Toute sélection active apparaît près de la question.

Priorité : une contradiction entre texte saisi et filtre visible déclenche une clarification, par exemple filtre Béja et question Jendouba. Ne pas laisser un filtre oublié détourner la demande. Une question « même station » peut reprendre une sélection précédente explicitement visible et modifiable.

### Traitement

Afficher des étapes factuelles : « Recherche des informations », « Vérification des données », « Préparation de la réponse ». Pas de pourcentage fictif ni de raisonnement interne. Désactiver l’envoi dupliqué pendant une demande ou attribuer un identifiant de requête garantissant une seule exécution.

Ne pas diffuser une réponse factuelle non vérifiée en streaming. Afficher le résultat une fois le contrôle final terminé. Le statut de progression peut être actualisé indépendamment.

### Carte de réponse

Ordre d’affichage :

1. Réponse courte et directe.
2. Indicateur, station/zone, période et unité.
3. Badge « Valeur publiée » ou « Calcul à partir des données publiées ».
4. Sources numérotées avec boutons « Voir la page ».
5. Limite utile, si présente.
6. Volets « Détail du calcul » et « Données utilisées » lorsqu’applicables.

Un badge « Valeur publiée » décrit l’origine ; il ne signifie pas « validé humainement ». Ne pas afficher de pourcentage de confiance issu d’une similarité vectorielle.

Pour plusieurs sous-questions, des blocs distincts indiquent lesquels sont résolus et lesquels restent sans preuve. Une réponse partielle ne se présente pas comme complète.

### Clarification

Afficher une seule question ciblée et des choix construits depuis le registre réel. Exemple : maximum journalier ou instantané ; année civile ou hydrologique ; station parmi plusieurs candidates. Après choix, conserver la demande d’origine et compléter son plan. Annuler permet de revenir à la saisie sans ajouter un faux résultat à l’historique.

### Historique et export

Historique par session avec question, réponse validée et release. Le bouton « Nouvelle conversation » vide seulement l’état de conversation. Ne pas supprimer les données ou journaux globaux. La persistance après fermeture n’est pas promise si seul Session State est utilisé.

Export Markdown d’une réponse : question, texte, source, page PDF/imprimée, date d’exécution, release, limites et formules. Aucun chemin privé absolu dans les exports partageables. L’export décrit les citations même si un lien local ne peut pas être ouvert sur un autre ordinateur.

## 5. Espace Explorer les données

Filtres en formulaire : indicateur, type d’entité, station/zone, période, publié/recalculé. Les options dépendent de la couverture et non d’une liste fictive. Bouton « Afficher les données » pour éviter des requêtes à chaque changement de filtre.

Tableau : entité, indicateur, début/fin ou date, valeur, unité, origine, qualité, source. Pagination ou limite d’affichage clairement indiquée ; le téléchargement peut porter sur la sélection complète après validation, pas seulement les lignes visibles.

Sélectionner une ligne permet d’ouvrir sa source. Une cellule non validée n’apparaît pas parmi les mesures utilisables ; l’onglet Couverture explique son absence. Un mode d’audit en lecture seule peut afficher le brut et la raison d’exclusion.

Graphiques : uniquement des données structurées validées ; axes et unités explicites. Une absence de donnée produit une rupture, jamais un zéro ou une interpolation invisible. Les lignes temporelles ne traversent pas automatiquement des périodes manquantes. Indiquer la granularité et la période. Pour les coordonnées non validées ou un CRS inconnu, ne pas afficher une position supposée sur carte.

Export CSV : UTF-8 adapté à l’ouverture sous Excel Windows, séparateur et décimales documentés, colonnes de provenance et état conservées. Neutraliser les cellules textuelles pouvant être interprétées comme formules de tableur, sans modifier les données sources en base.

## 6. Espace Comparer

Formulaire A/B : entité, indicateur, période et mode publié/recalculé. Choisir un indicateur commun par défaut. Afficher les conditions de compatibilité avant calcul : unité, référence, période, granularité et périmètre géographique.

Résultat : valeurs A et B, différence absolue, comparaison relative seulement si dénominateur et sens sont admissibles, couverture et sources séparées. Le signe est expliqué. Deux baselines distinctes ne deviennent pas une référence unique.

Si la comparaison est impossible, afficher exactement ce qui manque. Exemple : « La série B est incomplète pour cette période ; un total annuel comparable ne peut pas être recalculé. » Proposer une période commune disponible si le registre le démontre ; ne pas la substituer automatiquement.

Les graphiques comparatifs sont facultatifs quand un tableau de deux valeurs suffit. Pour une comparaison mensuelle, aligner le calendrier réel septembre–août et indiquer l’année de chaque mois.

## 7. Espace Sources

Sélection du document parmi les deux sources autorisées, numéro PDF dans les bornes réelles, numéro imprimé affiché séparément. Afficher la page rendue en image avec zoom, puis les métadonnées du bloc sélectionné et une surbrillance si disponible.

La vue image est la solution de base, indépendante d’une extension de navigateur PDF. Ajouter un téléchargement du PDF original et un lien à la page si le navigateur le permet, sans en faire l’unique voie. Charger les pages à la demande : les deux fichiers n’ont pas besoin d’être encodés en base64 au démarrage.

Les rectangles utilisent le repère défini dans les contrats. Vérifier la surbrillance après rotation. Les boutons de citation transfèrent `document_id`, `page_pdf`, `source_id` et `release_id`, pas un chemin fourni par le modèle.

Un chemin arbitraire ou `../` n’est jamais accepté pour ouvrir un fichier. Le code résout les identifiants dans le registre autorisé. Une source indisponible produit un message précis, pas une autre page ressemblante.

## 8. Espace Couverture

Afficher des effectifs réels : pages inventoriées/traitées/bloquées ; tableaux repérés/extraits/validés ; stations présentes ; observations publiables et exclusions. Les dénominateurs ont une définition. Ne pas comparer sans explication les 148 stations de synthèse au nombre de stations de tout le réseau.

Filtres par document, famille, indicateur et territoire. Tableau des limites : portée, nombre d’éléments, code d’anomalie, conséquence pour les réponses, état de révision. Les détails d’extraction restent dans un volet technique optionnel.

Aucun bouton de correction libre modifiant des mesures n’est requis dans la V1. Les corrections sont faites dans le workflow d’ingestion, tracées puis publiées en nouvelle release. La consultation de Couverture ne déclenche ni OCR ni réindexation.

## 9. État applicatif, cache et architecture UI

Utiliser un point d’entrée `app/streamlit_app.py` et des pages séparées. La navigation native `st.Page`/`st.navigation` est une base à vérifier dans la version installée. L’interface appelle un service applicatif ; aucun calcul métier important n’est placé directement dans un callback de bouton.

État par session : messages, identifiant de conversation, clarification en attente, filtres, source sélectionnée, requête active et release de chaque réponse. Ne pas mettre les historiques dans un cache global partagé.

Les modèles peuvent être chargés comme ressources partagées seulement si leur usage concurrent est sûr. Les résultats de données mis en cache incluent release et filtres. Les connexions SQLite ont une stratégie de durée de vie explicite ; pas de partage entre threads sans contrôle. Une nouvelle release invalide les caches concernés.

Les reruns ne doivent pas relancer le LLM à chaque clic sur une source. Stocker le résultat validé et son identifiant. Le volet de calcul réutilise les dérivations, sans recalcul par le modèle. Ajouter une journalisation technique de latence par phase, hors de l’écran principal.

API de service minimale pour les pages : `get_status`, `ask`, `resolve_clarification`, `list_entities`, `list_metrics`, `query_observations`, `compare`, `get_source_page`, `get_coverage`, `export_answer`, `export_rows`. Les arguments sont typés et validés, sans SQL libre.

## 10. Tests UI obligatoires

| Scénario | Résultat attendu |
|---|---|
| Aucune release | Message utile, aucune réponse non sourcée. |
| Modèle indisponible | Assistant signale l’état ; exploration de données déjà publiées utilisable. |
| Question numérique valide | Valeur, unité, période et bonne page visibles. |
| Clarification | Le choix reprend la demande sans la déformer. |
| Filtre contradictoire | Conflit explicite avant calcul. |
| Clic sur une source | Bonne page et bon bloc ; aucun nouvel appel LLM. |
| Changement de page puis retour | Historique et filtres conservés de façon prévisible. |
| Nouvelle conversation | État conversationnel remis à zéro, base intacte. |
| Série incomplète | Limite affichée ; pas de total complet inventé. |
| Conflit documentaire | Deux affirmations et preuves visibles. |
| Export | Même résultat et mêmes preuves que l’écran. |
| Requête lente ou erreur | État compréhensible, possibilité de réessayer sans doublon. |
| Fenêtre étroite | Contenu lisible, boutons accessibles. |
| Navigation au clavier | Libellés, ordre de focus et contraste utilisables. |

Utiliser les tests Streamlit disponibles et des tests des services ; vérifier réellement la navigation, les téléchargements et les pages sources dans un navigateur sur l’environnement cible. Les tests de composants ne remplacent pas l’inspection visuelle. Garder des captures datées de cinq écrans et des états erreur/clarification dans le rapport P11, sans exposer de secrets.

## 11. Références techniques officielles

Consultées pour la spécification le 12 septembre 2026 ; l’agent vérifiera les API de sa version installée :

- Navigation : https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation
- Widgets entre pages : https://docs.streamlit.io/develop/concepts/multipage-apps/widgets
- État de session : https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state

Ces références servent au développement de l’interface, pas au corpus hydrologique.
