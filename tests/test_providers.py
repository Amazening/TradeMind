"""Provider tests use mock transports. No internet and no real keys."""

import json

import httpx
import pytest
from pydantic import SecretStr

from trademind.core.errors import ExplainerError
from trademind.reporting import GroqModel, OllamaModel

KEY = SecretStr("test-secret-key")


def _groq(handler: httpx.MockTransport) -> GroqModel:
    return GroqModel(KEY, "test-model", client=httpx.Client(transport=handler))


def test_groq_sends_the_prompts_and_key_and_reads_the_reply() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": " Hello. "}}]})

    reply = _groq(httpx.MockTransport(handler)).complete("be brief", "explain this")

    assert reply == "Hello."
    request = seen[0]
    assert request.headers["authorization"] == "Bearer test-secret-key"
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert body["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "explain this"},
    ]
    assert body["temperature"] <= 0.3


def test_groq_needs_a_key() -> None:
    with pytest.raises(ExplainerError, match="GROQ_API_KEY"):
        GroqModel(None, "m")
    with pytest.raises(ExplainerError, match="GROQ_API_KEY"):
        GroqModel(SecretStr(""), "m")


def test_groq_model_name_includes_the_provider() -> None:
    assert _groq(httpx.MockTransport(lambda r: httpx.Response(200))).name == "groq:test-model"


@pytest.mark.parametrize(
    ("status", "message"),
    [(429, "rate limit"), (401, "rejected"), (403, "rejected"), (500, "HTTP 500")],
)
def test_groq_errors_become_explainer_errors(status: int, message: str) -> None:
    model = _groq(httpx.MockTransport(lambda request: httpx.Response(status)))

    with pytest.raises(ExplainerError, match=message):
        model.complete("s", "u")


def test_groq_network_failure_does_not_leak_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline: Bearer test-secret-key")

    with pytest.raises(ExplainerError) as error:
        _groq(httpx.MockTransport(handler)).complete("s", "u")

    assert "test-secret-key" not in str(error.value)
    assert "ConnectError" in str(error.value)


def test_groq_garbled_reply_is_an_explainer_error() -> None:
    model = _groq(httpx.MockTransport(lambda request: httpx.Response(200, json={"oops": 1})))

    with pytest.raises(ExplainerError, match="could not read"):
        model.complete("s", "u")


def test_ollama_posts_to_the_local_chat_endpoint() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "Hi"}})

    model = OllamaModel(
        "http://localhost:11434/",
        "tiny",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert model.complete("s", "u") == "Hi"
    assert str(seen[0].url) == "http://localhost:11434/api/chat"
    body = json.loads(seen[0].content)
    assert body["model"] == "tiny"
    assert body["stream"] is False
    assert model.name == "ollama:tiny"


def test_ollama_not_running_is_an_explainer_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    model = OllamaModel(
        "http://localhost:11434",
        "tiny",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ExplainerError, match="Could not reach Ollama"):
        model.complete("s", "u")
