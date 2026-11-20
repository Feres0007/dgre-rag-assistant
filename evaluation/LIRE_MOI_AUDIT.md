# Vérifier les questions de l’assistant

Les 230 questions fournies sont dans `evaluation/user_questions.json`. Le script appelle le même service de réponses que l’interface, avec Ollama en mode `full`. Il conserve chaque question, sa réponse, ses sources et le résultat de la vérification.

Depuis le dossier du projet, dans PowerShell :

```powershell
.\scripts\auditer_questions.ps1 -Nom mon_audit
```

Le résultat est dans `reports/question_audits/mon_audit/` :

- `rapport.html` : lecture des questions et réponses, filtre par verdict, critères de vérification dépliables.
- `reponses.csv` : les mêmes résultats dans un tableau.
- `answers.jsonl` : réponses originales sauvegardées après chaque question.
- `review.json` : réponses avec l’analyse actualisée.
- `manifest.json` : version du corpus, empreintes du code, des questions et du catalogue, configuration du modèle.
- `summary.json` : nombre de questions traitées et répartition des verdicts.

Pour reprendre un audit interrompu sans modifier le code, les données ou la configuration :

```powershell
.\scripts\auditer_questions.ps1 -Nom mon_audit -Reprendre
```

Après une correction du programme, choisissez un **nouveau nom** pour conserver l’avant/après. L’audit refuse de mélanger des versions lors d’une reprise.

## Fournir d’autres questions

Créez un fichier JSON, par exemple `mes_questions.json` :

```json
[
  "Quelle est la pluviométrie annuelle à Aïn Draham en 2022-2023 ?",
  "Quelle est la capacité du barrage Sidi Salem ?"
]
```

```powershell
.\scripts\auditer_questions.ps1 -Nom nouvelles_questions -Questions mes_questions.json
```

Attention : `--input` remplace la liste de travail `evaluation/user_questions.json`. La liste originale est conservée dans `evaluation/annuaires_230_questions.json`. Les questions sont traitées indépendamment, avec le contexte commun de l’année hydrologique 2022–2023. Les questions historiques ne sont pas réduites à cette seule année.

## Comprendre les verdicts

**Conforme aux critères** signifie que les éléments de référence annotés sont présents, que le statut attendu est respecté et qu’une page de preuve attendue est citée. Cela ne certifie pas automatiquement toutes les phrases, ni l’exhaustivité de toutes les données nationales.

**Problème** signale un résultat ou une réserve manquante, ou une source attendue absente. **À vérifier** signifie qu’aucune référence indépendante n’est annotée. Le simple statut `answered` n’est jamais considéré comme une validation.

Les critères des 230 questions sont dans `evaluation/user_gold.json`, générés par `scripts/build_user_gold.py` à partir de la lecture des PDF. Ils servent uniquement à l’évaluation et ne sont pas utilisés par l’assistant pour répondre. Pour de nouvelles questions, annotez de nouvelles références. Une empreinte du texte empêche le script de réutiliser les critères d’une ancienne question portant le même numéro.

Les réponses utilisent les observations publiées et un catalogue de synthèses extrait des PDF (`scripts/build_reference_catalog.py`). Ce catalogue contient des valeurs et leurs preuves, sans liste de questions ni réponses préenregistrées. Les PDF originaux et la base publiée restent inchangés.

Certaines réponses doivent rester prudentes : Tessa Pont comporte trop de lacunes pour publier le débit moyen annuel ; les apports d’un barrage ne donnent pas son stock ; certaines unités des tableaux de crues se contredisent ; un zéro imprimé ne prouve pas que la fiche est complète. Une demande de précision ou une réserve étayée peut donc constituer le résultat correct.
