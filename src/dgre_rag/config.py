from pathlib import Path
import os
import yaml
from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    corpus_dir: str = "donnees_brutes"
    data_dir: str = "data"
    llm_url: str = "http://127.0.0.1:11434"
    llm_model: str = "mistral:latest"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    timeout_seconds: int = Field(default=90, ge=1, le=300)
    max_operations: int = Field(default=6, ge=1, le=12)
    final_passages: int = Field(default=8, ge=1, le=20)
    model_downloads: bool = False
    release_periods: dict[str, dict[str, str]] = Field(default_factory=dict)


def root() -> Path:
    return Path(os.environ.get("DGRE_ROOT", Path(__file__).resolve().parents[2])).resolve()


def settings() -> Settings:
    path = root() / "config/app.yaml"
    values = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
    # Container networking differs from the host; keep the published YAML intact.
    for field in ("llm_url", "llm_model"):
        override = os.environ.get(f"DGRE_{field.upper()}")
        if override:
            values[field] = override
    return Settings.model_validate(values)


def data_dir() -> Path:
    return root() / settings().data_dir
