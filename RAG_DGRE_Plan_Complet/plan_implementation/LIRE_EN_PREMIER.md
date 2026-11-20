# RAG_DGRE — dossier de préparation à l’implémentation

Destination de travail : `C:\Users\SIGMA IT\Documents\RAG_DGRE`.

Extraire l’archive dans ce dossier. Elle crée uniquement le sous-dossier `plan_implementation`. Le code de l’application sera ensuite développé à la racine `RAG_DGRE`, par l’agent qui a accès à ton ordinateur. Ne pas créer une deuxième racine imbriquée `RAG_DGRE\RAG_DGRE`.

Ce paquet contient des spécifications et des prompts, pas une application RAG déjà développée. Aucun accès au disque Windows de l’utilisateur n’a été effectué depuis la conversation. Les deux PDF ne sont pas dupliqués dans l’archive ; les conserver sur ton ordinateur et les mettre dans `RAG_DGRE\data\raw` ou indiquer leur emplacement à l’agent.

## Démarrage

1. Ouvrir `C:\Users\SIGMA IT\Documents\RAG_DGRE` dans l’environnement de ton agent de développement.
2. Lui donner accès aux deux PDF originaux.
3. Copier le contenu de `prompts/DEMARRER_ICI.txt` dans sa conversation.
4. L’agent réalise P00 et s’arrête avec ses preuves. Après lecture, demander la phase suivante en lui donnant le fichier P01, puis P02, etc.

Aucune confirmation n’est requise pour chaque modification interne à une phase. Le point de contrôle intervient à la fin de la phase, conformément au choix de développement étape par étape.

## Ordre de lecture pour l’agent

1. Instructions applicables du dépôt et demande actuelle de l’utilisateur.
2. `specifications/01_PLAN_DIRECTEUR.md` : périmètre et orchestration du développement.
3. `specifications/02_INTERFACE_STREAMLIT.md` : produit, écrans, états et tests.
4. `specifications/03_QUALITE_ET_ACCEPTATION.md` : critères et preuve de livraison.
5. `references/Guide_Agent_Implementation_RAG_DGRE.md` : détail des contrats et des phases.
6. `references/Architecture_RAG_DGRE.md` : justification des choix.

Le plan directeur et les consignes des prompts de phase remplacent les anciennes consignes de poursuite automatique. Les P00–P12 conservent leur numérotation pour assurer la continuité. Les exigences de Streamlit complètent P01, P09, P10, P11 et P12.

## Ce que tu dois obtenir à la fin

Une application Streamlit locale en français, une base traçable des deux annuaires, un moteur de recherche et de calcul contrôlé, les tests réellement exécutés et un rapport précis des données non validées. La mention « complet » exige les critères de la spécification ; un écran qui s’ouvre ne suffit pas.

Le dossier `suivi` contient des modèles à copier dans `RAG_DGRE\docs` et `RAG_DGRE\reports` lors de P00. Toutes les phases sont initialement « à faire ». Le schéma SQL a été contrôlé comme point de départ, mais ne prouve pas la validité des mesures extraites.
