# Exécuter DGRE dans Docker

L'image `dgre-rag:local` contient l'application Streamlit et le code Python. Elle
réutilise le corpus actif de ce projet. L'interface actuelle est conservée.

## Prérequis

- Docker Desktop avec un moteur Linux opérationnel (`docker version` doit afficher
  les parties Client et Server).
- Les dossiers existants `data/` et `donnees_brutes/`, avec le corpus préparé.
- Pour la rédaction par modèle : Ollama démarré sur l'ordinateur et le modèle
  `mistral:latest` installé. Les modèles Ollama ne sont pas inclus dans l'image.
- Internet pour la première construction (image Python et paquets verrouillés).

## Construire et lancer

Depuis PowerShell, à la racine du projet :

```powershell
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 100 assistant
```

Ouvrir <http://localhost:8501>. Si le port est déjà utilisé :

```powershell
$env:DGRE_PORT = "8502"
docker compose up -d
```

L'adresse devient alors <http://localhost:8502>.

## Vérifier le conteneur

```powershell
docker compose exec assistant python -m dgre_rag.cli doctor
docker compose exec assistant python -m dgre_rag.cli ask "Combien de jours avec une pluie d'au moins 10 mm sont publiés pour Amdoun ?" --no-llm
```

Vérifier également dans l'interface une réponse, l'ouverture de sa source et le
retour à la conversation. Le contrôle de santé HTTP du conteneur vérifie uniquement
que Streamlit répond ; il ne certifie ni le corpus ni la disponibilité du modèle.

## Connexion à Ollama

Compose utilise `http://host.docker.internal:11434`. Les paramètres peuvent être
changés sans modifier `config/app.yaml` :

```powershell
$env:DGRE_LLM_URL = "http://host.docker.internal:11434"
$env:DGRE_LLM_MODEL = "mistral:latest"
docker compose up -d
```

La commande `doctor` indique si le modèle est effectivement accessible depuis le
conteneur. Un Ollama accessible uniquement sur la boucle locale de l'hôte peut
nécessiter une configuration réseau adaptée. Aucun réglage réseau d'Ollama n'est
modifié automatiquement. La connectivité doit être vérifiée avant d'annoncer la
disponibilité des réponses rédigées par le modèle.

## Données persistantes

- `./data` est monté dans `/app/data` en lecture et écriture : corpus actif, index,
  cache des modèles d'embedding et journaux sont conservés après l'arrêt.
- `./donnees_brutes` est monté en lecture seule : les PDF originaux ne sont pas
  incorporés à l'image et ne peuvent pas être modifiés depuis le conteneur.
- Le fichier `.dockerignore` exclut aussi l'environnement Windows, les sauvegardes,
  les rapports et les pièces jointes du contexte de construction.
- L'application tourne sous un utilisateur non administrateur (UID 10001).
  Sur un hôte Linux, cet utilisateur doit pouvoir écrire dans le dossier `data`.
- Sur une autre machine, transférer séparément `data/` et `donnees_brutes/`, en
  conservant leurs noms et leur arborescence. L'image seule ne contient pas le corpus.
- Éviter une reconstruction ou une activation concurrente du corpus depuis
  l'application hôte et le conteneur, puisqu'ils partagent le même dossier.

## Arrêter, reconstruire et exporter

```powershell
docker compose down
docker compose up -d --build
docker save --output dgre-rag-image.tar dgre-rag:local
```

L'arrêt ne supprime pas les dossiers montés. Après export, une autre machine peut
charger l'image avec `docker load --input dgre-rag-image.tar`, puis démarrer avec
`docker compose up -d --no-build` en disposant du fichier Compose et des données.

## Vérifications réalisées lors de la préparation

- `docker compose config --quiet` : réussi.
- `python -m pytest tests/unit -q --junitxml=reports/docker_unit_tests.xml` avec le
  Python de `.venv` : 67 réussis, 1 module ignoré (historique de la refonte retirée).
- `docker compose build` : échec avant la construction, réponse 500 du moteur Docker.
- Journaux Docker Desktop : `HCS_E_HYPERV_NOT_INSTALLED`, moteur arrêté et
  `hasNoVirtualization: true`. Windows indique `HypervisorPresent: False`, alors
  que le processeur indique `VirtualizationFirmwareEnabled: True`.

Il faut donc rétablir le fonctionnement de WSL 2 / de l'hyperviseur Windows pour
Docker Desktop. Les observations ne justifient pas d'affirmer que la virtualisation
est désactivée dans le BIOS. Aucun paramètre système n'a été changé.

**L'image n'a pas encore été construite.** L'installation des dépendances Linux,
le démarrage du conteneur, les sources et la connexion Ollama restent à vérifier
après résolution de ce blocage. Les tests locaux réussis ne remplacent pas ces essais.

Références : [Streamlit dans Docker](https://docs.streamlit.io/deploy/tutorials/docker),
[réseau Docker Desktop](https://docs.docker.com/desktop/features/networking/networking-how-tos/).
