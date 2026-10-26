"""Text model providers: Groq (free tier, hosted) and Ollama (local, nothing leaves the machine)."""

from typing import Any

import httpx
from pydantic import SecretStr

from trademind.core.errors import ExplainerError

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MAX_TOKENS = 300
_TEMPERATURE = 0.2


class GroqModel:
    def __init__(
        self,
        api_key: SecretStr | None,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        if api_key is None or not api_key.get_secret_value():
            raise ExplainerError("GROQ_API_KEY is not set. Add it to .env to use Groq.")
        self.name = f"groq:{model}"
        self._key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=30.0)

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": _TEMPERATURE,
            "max_tokens": _MAX_TOKENS,
        }
        headers = {"Authorization": f"Bearer {self._key.get_secret_value()}"}
        try:
            response = self._client.post(_GROQ_URL, json=body, headers=headers)
        except httpx.HTTPError as error:
            raise ExplainerError(f"Could not reach Groq ({type(error).__name__})") from None
        if response.status_code == 429:
            raise ExplainerError("Groq rate limit reached. Try again later.")
        if response.status_code in (401, 403):
            raise ExplainerError("Groq rejected the API key.")
        if response.status_code != 200:
            raise ExplainerError(f"Groq replied HTTP {response.status_code}")
        try:
            content: Any = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ExplainerError("Groq sent a reply we could not read") from None
        return str(content).strip()


class OllamaModel:
    def __init__(self, url: str, model: str, client: httpx.Client | None = None) -> None:
        self.name = f"ollama:{model}"
        self._url = url.rstrip("/")
        self._model = model
        self._client = client or httpx.Client(timeout=120.0)

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": _TEMPERATURE, "num_predict": _MAX_TOKENS},
        }
        try:
            response = self._client.post(f"{self._url}/api/chat", json=body)
        except httpx.HTTPError as error:
            raise ExplainerError(
                f"Could not reach Ollama at {self._url} ({type(error).__name__})"
            ) from None
        if response.status_code != 200:
            raise ExplainerError(f"Ollama replied HTTP {response.status_code}")
        try:
            content: Any = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError):
            raise ExplainerError("Ollama sent a reply we could not read") from None
        return str(content).strip()
