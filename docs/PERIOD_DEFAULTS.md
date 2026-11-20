# Période par défaut et nombres de jours publiés

Changement du 11 octobre 2026. Corpus actif conservé : `robust-9842f2291922`.

## Comportement

La question explicite est prioritaire sur le contexte. Les suites conversationnelles
compatibles reprennent la période précédente. Une nouvelle demande de mesures sans
période utilise la campagne configurée pour sa version de corpus : du 1er septembre
2022 au 31 août 2023 pour la version active. Un mois sans année est résolu à
l’intérieur de la campagne. Une période explicite indisponible n’est pas remplacée.

Les définitions et demandes historiques conservent leur portée. Les dates invalides,
stations ambiguës, comparaisons incomplètes et tarages nécessitant une date restent
soumis à clarification. La résolution est enregistrée dans la réponse, le plan,
le contexte de conversation et le journal final.

La configuration `release_periods` ne modifie pas les manifestes déjà publiés.
Les futures publications enregistrent une période par défaut si tous leurs
documents déclarent une même campagne. Plusieurs campagnes ne sont pas fusionnées.

## Preuve du cas Amdoun

PDF original : annuaire pluviométrique, page PDF 50, pagination imprimée 47,
tableau Amdoun, code 1483063021. La ligne de synthèse indique 45 pluies > 0 mm,
45 pluies >= 0,5 mm et **16 pluies >= 10 mm**. Texte original et rendu visuel
contrôlés pendant cette intervention. Les deux PDF originaux ne sont pas modifiés.

La question « Combien de jours avec une pluie d’au moins 10 mm sont publiés pour
Amdoun ? » consulte cette statistique annuelle sourcée. Une demande explicite de
recalcul, un seuil libre ou une période mensuelle consulte les observations
journalières. Le résultat calculé est qualifié de partiel si sa couverture est
incomplète. Les seuils stricts et inclusifs sont distincts. Un résultat calculé
ne devient jamais un nombre publié.

## Références et reproductibilité

Le cas 1010 exigeait auparavant une clarification pour absence de période.
Il exige maintenant la valeur annuelle 1178 mm à AIN DRAHAM, page PDF 59,
déjà vérifiée pour le cas 1001. Son ancienne attente est conservée dans la note
de `evaluation/robustness_gold.json`. Les références des 230 questions restent
inchangées : leur conformité ne certifie pas toutes les affirmations.

Depuis la racine du projet, avec Python de `.venv` :

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q --junitxml=reports/period_defaults_final_tests.xml
.\.venv\Scripts\python.exe -X utf8 scripts/audit_questions.py --release-id robust-9842f2291922 --name period_defaults_full_final --mode full
.\.venv\Scripts\python.exe -X utf8 scripts/audit_questions.py --release-id robust-9842f2291922 --name period_defaults_reception_final --mode deterministic --questions evaluation/robustness_test_questions.json --gold evaluation/robustness_gold.json
```

Pour répéter un audit, choisir un nom de dossier inédit. Les manifestes d’audit
enregistrent le corpus, les empreintes du code, des questions et la configuration.
Les premiers rapports intermédiaires ne représentent pas la version finale.

L’interface Assistant + Sources et la signature publique de `Service.ask` sont
conservées. Un redémarrage de Streamlit suffit ; aucune reconstruction du corpus
n’est nécessaire pour cette correction.

## Résultats vérifiés

- Suite finale : 144 tests réussis, aucun échec (`reports/period_defaults_final_tests.xml`).
- Réception annotée : 5 cas sur 5 conformes (`reports/question_audits/period_defaults_reception_final/summary.json`).
- Développement annoté : 5 cas sur 5 conformes (`reports/question_audits/period_defaults_dev_final/summary.json`).
- Audit final avec Ollama : 230 questions exécutées et évaluées, 230 conformes
  aux critères existants (`reports/question_audits/period_defaults_full_final/summary.json`).
  Ce résultat de régression ne constitue pas une certification de toutes les
  affirmations ni un taux de réussite sur des questions nouvelles. Les empreintes
  du code et de la configuration ont été comparées au manifeste de cet audit.
- Réponse finale d’Amdoun, preuve et validation :
  `data/query_logs/7fa3d7fefd8b4e4b921a2496c441e239.final.json`.
- Empreintes des deux PDF comparées au manifeste actif : identiques.

Le premier audit déterministe intermédiaire contenait des régressions de
comparaisons ensuite corrigées et dix questions arabes nécessitant la traduction
locale. Il est conservé pour diagnostic, pas utilisé comme résultat final.
