from __future__ import annotations
import json
import requests
from typing import Any, Dict, List, Optional
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

from .config import (
    USE_LOCAL_LLM,
    LOCAL_LLM_ENDPOINT,
    SMALL_MODEL_NAME,
    LARGE_MODEL_NAME,
    GROQ_API_KEY,
    GROQ_CLASSIFIER_MODEL,
    GROQ_RESPONSE_MODEL,
)

from .api_utils import with_retry

def _post_json(url: str, payload: dict, headers: dict) -> dict:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = requests.post(url, json=payload, headers=headers, verify=False)
    resp.raise_for_status()
    return resp.json()

class GroqLLM(LLM):
    model: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    @property
    def _identifying_params(self) -> dict:
        return {"model": self.model, "provider": "groq"}

    @property
    def _llm_type(self) -> str:
        return "groq"

    @with_retry(max_retries=5)
    def _call(self, prompt: str, stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> str:
        import groq
        client = groq.Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

class LocalLLM(LLM):
    model: str
    endpoint: str = LOCAL_LLM_ENDPOINT.rstrip("/")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def _identifying_params(self) -> dict:
        return {"model": self.model, "provider": "local"}

    @property
    def _llm_type(self) -> str:
        return "local"

    def _call(self, prompt: str, stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.3,
        }
        if stop:
            payload["stop"] = stop
        headers = {"Content-Type": "application/json"}
        resp = _post_json(f"{self.endpoint}/v1/chat/completions", payload, headers)
        return resp["choices"][0]["message"]["content"].strip()

def get_llm(kind: str = "classifier") -> LLM:
    """
    kind = "classifier" -> small model (intent detection)
    kind = "response"   -> large model (final answer)
    """
    if USE_LOCAL_LLM:
        model = SMALL_MODEL_NAME if kind == "classifier" else LARGE_MODEL_NAME
        return LocalLLM(model=model)
    else:
        model = (
            GROQ_CLASSIFIER_MODEL if kind == "classifier" else GROQ_RESPONSE_MODEL
        )
        return GroqLLM(model=model)


# ── Direct Chat Client Adapter (for backward compatibility in retriever/transcriber/memory) ──

class _OpenAIChoiceMessage:
    def __init__(self, content: str):
        self.content = content

class _OpenAIChoice:
    def __init__(self, content: str):
        self.message = _OpenAIChoiceMessage(content)

class _OpenAIResponse:
    def __init__(self, content: str):
        self.choices = [_OpenAIChoice(content)]

class _LocalChatCompletions:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def create(self, model: str, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.3, **kwargs):
        # Map model name if legacy groq model was passed
        actual_model = model
        if model == GROQ_CLASSIFIER_MODEL:
            actual_model = SMALL_MODEL_NAME
        elif model == GROQ_RESPONSE_MODEL:
            actual_model = LARGE_MODEL_NAME

        payload = {
            "model": actual_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }
        headers = {"Content-Type": "application/json"}
        resp = _post_json(f"{self.endpoint}/v1/chat/completions", payload, headers)
        content = resp["choices"][0]["message"]["content"]
        return _OpenAIResponse(content)

class _LocalChat:
    def __init__(self, endpoint: str):
        self.completions = _LocalChatCompletions(endpoint)

class LocalClient:
    def __init__(self, endpoint: str = LOCAL_LLM_ENDPOINT):
        self.endpoint = endpoint.rstrip("/")
        self.chat = _LocalChat(self.endpoint)

class _GroqChatCompletionsWrapper:
    def __init__(self, client):
        self.client = client
    
    @with_retry(max_retries=5)
    def create(self, *args, **kwargs):
        return self.client.chat.completions.create(*args, **kwargs)

class _GroqChatWrapper:
    def __init__(self, client):
        self.completions = _GroqChatCompletionsWrapper(client)

class GroqClientWrapper:
    def __init__(self, client):
        self.client = client
        self.chat = _GroqChatWrapper(client)
        self.audio = client.audio # directly pass audio

def get_chat_client():
    """Return either Groq client or LocalClient based on USE_LOCAL_LLM toggle."""
    if USE_LOCAL_LLM:
        return LocalClient(LOCAL_LLM_ENDPOINT)
    import groq
    client = groq.Groq(api_key=GROQ_API_KEY)
    return GroqClientWrapper(client)

