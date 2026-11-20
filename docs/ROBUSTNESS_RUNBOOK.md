# RAG DGRE : reconstruction et réception de la version renforcée

Toutes les commandes ci-dessous s'exécutent dans la racine du projet, en PowerShell.
Les PDF originaux ne sont ni corrigés ni réécrits. Le registre vérifie leurs empreintes.

## Reconstruction reproductible

```powershell
.\.venv\Scripts\python.exe -m dgre_rag.cli register
.\.venv\Scripts\python.exe -m dgre_rag.cli extract --scope all
.\.venv\Scripts\python.exe -m dgre_rag.cli validate --run-id <identifiant-retourné>
.\.venv\Scripts\python.exe -m dgre_rag.cli publish --run-id <identifiant-retourné> --label robust --no-activate
.\.venv\Scripts\python.exe -m dgre_rag.cli index --release-id <version-candidate>
```

L'identifiant du run dépend des empreintes des PDF et du code/configuration. Une nouvelle
version du programme peut donc produire un nouvel identifiant. L'extraction conserve son
empreinte de construction dans `run_metadata` et le manifeste publié. Les releases existantes
restent immuables. La migration SQL 002 s'applique aux nouvelles bases ; elle ne modifie pas
les anciennes versions. Les lecteurs gardent un accès compatible au catalogue JSON des
anciennes versions ; les nouvelles utilisent `structured_records` dans SQLite.

Les modèles doivent déjà être présents localement. L'indexation ne télécharge rien sans
`--allow-download`. L'index enregistre le modèle, la dimension, le découpage et les empreintes.

## Contrôler une version avant activation

```powershell
.\.venv\Scripts\python.exe -m pytest -q --release-id <version-candidate> --junitxml=reports/reception.xml
.\.venv\Scripts\python.exe scripts/audit_questions.py --release-id <version-candidate> --name nouvelle_campagne --mode full
.\.venv\Scripts\python.exe scripts/audit_questions.py --release-id <version-candidate> --questions evaluation/robustness_dev_questions.json --gold evaluation/robustness_gold.json --name nouveaux_cas_dev --mode deterministic
.\.venv\Scripts\python.exe scripts/audit_questions.py --release-id <version-candidate> --questions evaluation/robustness_test_questions.json --gold evaluation/robustness_gold.json --name nouveaux_cas_reception --mode deterministic
.\.venv\Scripts\python.exe -m dgre_rag.cli evaluate --release-id <version-candidate> --split test
```

Chaque campagne exige un nom neuf ; les résultats antérieurs ne sont pas écrasés.
`--resume` refuse de mélanger des codes, configurations ou données différents.
Le dernier outil `evaluate` conserve sa portée historique : recherche documentaire et
contrôles déterministes, et non évaluation complète de la rédaction libre.

Les 230 questions historiques constituent une régression ajustée au projet. Leur verdict
« conforme aux critères » contrôle les annotations existantes et ne certifie pas chaque
phrase. Les dix nouveaux cas comportent des références vérifiées dans les pages originales,
avec cinq cas de développement et cinq cas de réception séparés. Ils ne représentent pas
une validation exhaustive des 52 familles.

Le taux de conformité est `conformes / verdicts exploitables`. Les questions non annotées
ou dont la référence ne correspond plus à la question restent `a_verifier`, hors dénominateur.
Aucune Precision@k, Recall@k ou fidélité globale des citations n'est déduite de ce taux.

## Activation et retour arrière

```powershell
.\.venv\Scripts\python.exe -m dgre_rag.cli activate <version-candidate>
# Revenir à la version précédente si nécessaire :
.\.venv\Scripts\python.exe -m dgre_rag.cli restore corpus-c60e4a25cec4
# Lancer l'interface :
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

L'activation contrôle l'intégrité de la base et de l'index avant le remplacement atomique
du pointeur. L'historique du chatbot n'est réutilisé que pour sa version de corpus.

## Fonctionnement et limites explicites

- Identités internes par occurrence puis rapprochement strict nom/code ; un code partagé
  produit plusieurs identités et une clarification. Ce n'est pas un registre géographique
  universel : les variantes non rapprochées restent distinctes.
- Les nombres passent par les contrôles de disposition, calendrier, unités et preuves.
  La validation est applicative et ne remplace pas la validation scientifique des publications.
- Jaugeages, résidu sec et états textuels : seules les dispositions reconnues sont structurées.
  Les heures et unités non reconnues restent bloquées, sans zéro de substitution.
- Tarage : exact ou interpolation linéaire à l'intérieur d'une courbe unique reconnue,
  dans sa validité publiée. La mention « jusqu'à nos jours » est bornée à la fin de la
  campagne du document, sans supposer une validité actuelle.
- Lame d'eau : primitive de calcul testée, mais son emploi nécessite une superficie et
  un bassin validés. Les superficies candidates ne sont pas admises arbitrairement.
- Sommes partielles et seuils : les cellules utilisables sont comptées ; les lacunes
  restent visibles. Les séquences s'interrompent à une lacune. Un classement ne garantit
  pas l'exhaustivité du réseau. Les filtres territoriaux non pris en charge ne sont pas ignorés.
- Figures : légendes localisées et liens vers les tableaux de la même page ; pas de mesure
  numérique tirée des pixels, ni modèle visuel déployé.
- Les réponses passent par une sortie commune contrôlant les références, les valeurs
  structurées et les calculs rejoués. La prose libre n'est pas certifiée par ces seuls
  contrôles ; le vérificateur du modèle est un contrôle complémentaire.
- Les journaux `*.final.json` décrivent la réponse après le contrôle commun. Les journaux
  `*.json` produits dans `_ask` portent le stade `execution_before_common_validation`.
- Le fonctionnement sans modèle couvre les voies déterministes. La traduction arabe
  requiert le modèle local ; un modèle installé peut néanmoins nécessiter un démarrage lent.

Voir `ROBUSTNESS_COVERAGE.md` pour les 52 familles et les limites par famille.
