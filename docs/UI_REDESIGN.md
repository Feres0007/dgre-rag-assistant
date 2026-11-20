# Interface DGRE : historique local et restauration

La refonte utilise un thème clair bleu profond/turquoise, un accueil avec quatre
questions proposées et un en-tête compact pendant la conversation. Les questions
et réponses sont présentées dans des blocs distincts, avec les résultats publiés,
calculés et partiels identifiés lorsque leurs métadonnées le permettent.

La barre latérale permet de démarrer, retrouver, renommer et supprimer une
conversation. Les échanges sont enregistrés dans `data/ui/conversations.sqlite`,
indépendamment des données RAG. Une nouvelle session affiche l’historique, mais
ne recharge ni ne relance automatiquement une ancienne question. Les demandes
interrompues proposent une relance manuelle. Les réponses sauvegardées gardent
leur corpus et leurs preuves d’origine.

L’accès aux sources, aux détails de calcul, aux valeurs et aux exports est
conservé. Le panneau de copie permet de sélectionner le texte et d’utiliser
Ctrl+C/Cmd+C. La page Sources regroupe document, page et zoom dans une barre de
consultation. Les colonnes sont empilées sur écran étroit et les animations sont
désactivées lorsque la réduction des mouvements est demandée.

## Lancer l’application

Depuis `C:\Users\SIGMA IT\Documents\RAG_DGRE` :

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

## Revenir à l’interface précédente

La sauvegarde initiale a été créée **avant toute modification de l’interface** :
`backups/ui/20261011-123353-417644`. Elle contient l’archive `interface.zip` et un
manifeste des empreintes de tous les fichiers d’interface, sans caches Python.

Arrêter Streamlit avec Ctrl+C, puis exécuter depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe scripts/ui_versions.py verify --backup backups/ui/20261011-123353-417644
.\.venv\Scripts\python.exe scripts/ui_versions.py restore --backup backups/ui/20261011-123353-417644 --delivery reports/ui_redesign_delivery.json
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

La restauration remet les fichiers initiaux à l’identique et supprime seulement
les nouveaux modules d’interface enregistrés dans le manifeste de livraison.
Les PDF, les corpus, les journaux et les conversations enregistrées sont conservés.
Le script de restauration et la sauvegarde restent disponibles.

Pour sauvegarder une autre version avant restauration :

```powershell
.\.venv\Scripts\python.exe scripts/ui_versions.py snapshot
```

La même commande `restore`, avec le chemin de cette nouvelle sauvegarde, permet
de remettre cette version. Ne pas modifier manuellement les archives ni les
manifestes.

La nouvelle interface a également été sauvegardée :
`backups/ui/20261011-124320-763528`. Pour la remettre après un retour à l’ancienne :

```powershell
.\.venv\Scripts\python.exe scripts/ui_versions.py restore --backup backups/ui/20261011-124320-763528
```

Redémarrer ensuite Streamlit.

## Vérifications

Commande des tests pertinents :

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/unit/test_ui_history.py tests/e2e/test_ui.py -q --junitxml=reports/ui_redesign_tests.xml
```

Les tests utilisent un historique temporaire pour ne pas polluer les conversations
réelles. Ils couvrent les pages, les réponses et sources, les graphiques, la
réouverture dans une session neuve, le renommage, la suppression confirmée, la
relance manuelle et la conservation en session lors d’un échec d’écriture.

Résultat : **14 tests exécutés, 14 réussis, aucun échec ni test ignoré**.
Les scénarios de changement de corpus et de modèle indisponible sont inclus.
Les contrastes calculés sont de 4,75:1 pour le blanc sur turquoise, 5,02:1
pour le texte de la barre latérale, 6,42:1 pour la mention de résultat et
6,36:1 pour la mention de résultat partiel. Le texte du bandeau a été ajusté
en blanc après cette vérification.

La sauvegarde réelle a aussi été restaurée et vérifiée dans `tmp/ui_restore_check`.
Les captures avant/après et la vérification visuelle dans un navigateur ne sont
pas disponibles : le contrôle du navigateur de cette session ne fournit aucun
navigateur connecté. Les tests Streamlit vérifient les widgets et les parcours,
mais ne prouvent pas l’absence de débordements visuels sur chaque taille d’écran.
