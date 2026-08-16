"""
tests/test_local_llm.py
=======================
Unit tests for the LocalLLM LangChain wrapper.

Mocks requests.post so that no real HTTP call is made.
Verifies that:
  - The correct URL is targeted (/v1/chat/completions)
  - The OpenAI-compatible response format is parsed correctly
  - The extracted text is returned by .invoke()
"""
import pytest
import requests
import src.llm_wrapper as llm_wrapper_mod
from src.llm_wrapper import LocalLLM, get_llm


# ── Shared mock factory ────────────────────────────────────────────────────────

class _FakeResponse:
    """Minimal response object that mimics requests.Response for our use case."""

    def __init__(self, content: str):
        self._content = content

    def json(self):
        return {
            "choices": [
                {"message": {"content": self._content}}
            ]
        }

    def raise_for_status(self):
        pass  # No error


def _make_fake_post(expected_content: str):
    """Return a fake requests.post that asserts URL shape and returns expected_content."""
    def fake_post(url, json, headers, verify):
        assert "/v1/chat/completions" in url, f"Unexpected URL: {url}"
        # Echo the user message back so tests can verify round-trip
        user_msg = json["messages"][0]["content"]
        return _FakeResponse(f"Echo: {user_msg}")
    return fake_post


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_local_llm_calls_correct_url(monkeypatch):
    """LocalLLM._call should POST to the /v1/chat/completions endpoint."""
    posted_urls = []

    def capture_post(url, json, headers, verify):
        posted_urls.append(url)
        return _FakeResponse("ok")

    monkeypatch.setattr(requests, "post", capture_post)
    llm = LocalLLM(model="test-model", endpoint="https://127.0.0.1:8000")
    llm.invoke("ping")
    assert any("/v1/chat/completions" in u for u in posted_urls)


def test_local_llm_parses_openai_format(monkeypatch):
    """LocalLLM should parse the choices[0].message.content field from the response."""
    monkeypatch.setattr(requests, "post", _make_fake_post("parsed-content"))
    llm = LocalLLM(model="test-model", endpoint="https://127.0.0.1:8000")
    reply = llm.invoke("Hello world")
    assert reply == "Echo: Hello world"


def test_local_llm_ssl_verify_disabled(monkeypatch):
    """LocalLLM should pass verify=False to requests.post (self-signed cert support)."""
    verify_values = []

    def capture_verify(url, json, headers, verify):
        verify_values.append(verify)
        return _FakeResponse("ok")

    monkeypatch.setattr(requests, "post", capture_verify)
    llm = LocalLLM(model="test-model", endpoint="https://127.0.0.1:8000")
    llm.invoke("test")
    assert verify_values[0] is False, "verify should be False for self-signed cert support"


def test_get_llm_local_mode_invokes_local_server(monkeypatch):
    """get_llm() in local mode should use LocalLLM and successfully parse a mock response."""
    monkeypatch.setattr(llm_wrapper_mod, "USE_LOCAL_LLM", True)
    monkeypatch.setattr(requests, "post", _make_fake_post("greet"))

    llm = get_llm(kind="classifier")
    assert isinstance(llm, LocalLLM)
    result = llm.invoke("Hello world")
    assert result == "Echo: Hello world"
