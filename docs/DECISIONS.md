# Décisions d’implémentation

- Les instructions utilisateur de mise en œuvre globale puis de poursuite autorisent l’enchaînement des phases sans demander une permission à chaque étape. Le suivi ne déclare aucune phase acceptée par un humain.
- Les deux PDF originaux constituent seuls le corpus. Le dossier de plan, les rapports, les tests et `tmp` restent hors index métier.
- PyMuPDF extrait texte, tableaux et géométries. Les familles non reconnues sont conservées sans inventer leur sémantique numérique. Les tirets et symboles non prouvés restent indéterminés.
- SQLite contient candidats, preuves et sélection canonique ; une release publiée se consulte en lecture seule. Publication atomique et empreintes séparent extraction et application.
- Les calculs utilisent Decimal, des observations admissibles et des règles de couverture. Les totaux publiés restent distincts des totaux recalculés. Une incohérence détectée accompagne la valeur publiée d’un avertissement.
- La recherche combine FTS5, pages lexicales et fenêtres contextuelles vectorielles. Les ajustements sur les 120 questions initiales imposent leur classement en développement. Les 24 nouvelles questions réservées portent uniquement sur des valeurs et dates numériques.
- Ollama/Mistral peut planifier ou sélectionner des sources. Les chiffres et citations sont construits par code ; le documentaire restitue des extraits exacts, sans rédaction libre R2/R3. Cette adaptation réduit le périmètre rédactionnel du plan initial.
- Les annotations et contrôles visuels réalisés par l’agent ne sont pas présentés comme une validation scientifique humaine. Les tests AppTest ne remplacent pas une revue visuelle complète dans un navigateur.
