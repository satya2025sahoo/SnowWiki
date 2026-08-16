"""
tests/test_factory.py
=====================
Unit tests for the get_llm() factory function.

Tests verify that the correct wrapper class is returned based on
the USE_LOCAL_LLM config toggle.

NOTE: Because USE_LOCAL_LLM is evaluated at import time in config.py,
we patch the module-level attribute in llm_wrapper directly rather than
setting the env var (which would require re-importing the module).
"""
import pytest
from src.llm_wrapper import get_llm, LocalLLM, GroqLLM
import src.llm_wrapper as llm_wrapper_mod


def test_factory_returns_local(monkeypatch):
    """When USE_LOCAL_LLM is True, get_llm() should return a LocalLLM instance."""
    monkeypatch.setattr(llm_wrapper_mod, "USE_LOCAL_LLM", True)
    llm = get_llm("classifier")
    assert isinstance(llm, LocalLLM), f"Expected LocalLLM, got {type(llm)}"


def test_factory_returns_groq(monkeypatch):
    """When USE_LOCAL_LLM is False, get_llm() should return a GroqLLM instance."""
    monkeypatch.setattr(llm_wrapper_mod, "USE_LOCAL_LLM", False)
    llm = get_llm("classifier")
    assert isinstance(llm, GroqLLM), f"Expected GroqLLM, got {type(llm)}"


def test_factory_small_model_local(monkeypatch):
    """kind='classifier' should use SMALL_MODEL_NAME when local backend is active."""
    monkeypatch.setattr(llm_wrapper_mod, "USE_LOCAL_LLM", True)
    monkeypatch.setattr(llm_wrapper_mod, "SMALL_MODEL_NAME", "my-small-model")
    llm = get_llm("classifier")
    assert llm.model == "my-small-model"


def test_factory_large_model_local(monkeypatch):
    """kind='response' should use LARGE_MODEL_NAME when local backend is active."""
    monkeypatch.setattr(llm_wrapper_mod, "USE_LOCAL_LLM", True)
    monkeypatch.setattr(llm_wrapper_mod, "LARGE_MODEL_NAME", "my-large-model")
    llm = get_llm("response")
    assert llm.model == "my-large-model"
