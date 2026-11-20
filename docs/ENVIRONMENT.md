# Environnement vérifié

Poste Windows, dossier `C:\Users\SIGMA IT\Documents\RAG_DGRE`, Python 3.11.9 dans `.venv` et SQLite 3.45.1. Diagnostic détaillé : [environment.json](../reports/environment.json).

Le diagnostic initial a identifié 16 Go de RAM et une NVIDIA RTX 3050 Laptop de 6 Go. Les dépendances exactes sont dans [requirements.lock.txt](../requirements.lock.txt). Ollama fournit `mistral:latest` ; son identité disponible au diagnostic est conservée dans le JSON. Les embeddings utilisent `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` avec FastEmbed/ONNX et cache dans `data/models`.

Consultation locale : Streamlit sur `127.0.0.1:8501`, Ollama sur `127.0.0.1:11434`. L’installation et le premier téléchargement nécessitent le réseau. Aucun essai de poste physiquement déconnecté n’est déclaré. Le mode applicatif interdit le téléchargement implicite des embeddings.

Les chemins contenant des espaces ont été utilisés dans les essais. Le contrôle par navigateur automatisé était indisponible ; AppTest a exercé les cinq espaces et le service HTTP a répondu 200. Les PDF ont été inspectés séparément par extraction et rendus de pages représentatives.
