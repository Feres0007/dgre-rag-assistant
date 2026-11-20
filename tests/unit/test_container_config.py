from dgre_rag.config import settings


def test_container_overrides_do_not_modify_host_config(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    path = config / "app.yaml"
    original = "llm_url: http://127.0.0.1:11434\nllm_model: mistral:latest\n"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("DGRE_ROOT", str(tmp_path))
    monkeypatch.delenv("DGRE_LLM_URL", raising=False)
    monkeypatch.delenv("DGRE_LLM_MODEL", raising=False)
    assert settings().llm_url == "http://127.0.0.1:11434"
    monkeypatch.setenv("DGRE_LLM_URL", "http://host.docker.internal:11434")
    monkeypatch.setenv("DGRE_LLM_MODEL", "another-model:latest")
    assert settings().llm_url == "http://host.docker.internal:11434"
    assert settings().llm_model == "another-model:latest"
    assert path.read_text(encoding="utf-8") == original


def test_empty_overrides_preserve_default(tmp_path, monkeypatch):
    monkeypatch.setenv("DGRE_ROOT", str(tmp_path))
    monkeypatch.setenv("DGRE_LLM_URL", "")
    monkeypatch.setenv("DGRE_LLM_MODEL", "")
    assert settings().llm_url == "http://127.0.0.1:11434"
    assert settings().llm_model == "mistral:latest"
