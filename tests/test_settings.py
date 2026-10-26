from pathlib import Path

import pytest

from trademind.core.settings import Settings


def test_defaults_when_nothing_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.groq_api_key is None
    assert settings.price_cache_dir == Path(".cache/prices")


def test_reads_key_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("GROQ_API_KEY=test-key\nUNRELATED_KEY=ignored\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.groq_api_key is not None
    assert settings.groq_api_key.get_secret_value() == "test-key"


def test_secret_is_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    settings = Settings(_env_file=None)

    assert "test-key" not in repr(settings)
    assert "test-key" not in str(settings.model_dump())
