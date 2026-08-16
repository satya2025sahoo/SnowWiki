import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Local LLM Wrapper", version="0.1.0")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    max_tokens: int = 1024
    temperature: float = 0.3

def _call_underlying_llm(model: str, prompt: str) -> str:
    """
    Replace this stub with the real call to your locally-deployed LLM.
    For now it simply echoes the prompt.
    """
    return f"[{model}] Echo: {prompt}"

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    user_prompt = "\n".join(
        m.content for m in req.messages if m.role == "user"
    )
    if not user_prompt:
        raise HTTPException(status_code=400, detail="No user message provided")

    answer = _call_underlying_llm(req.model, user_prompt)

    response_body = {
        "id": "local-llm-req",
        "object": "chat.completion",
        "created": int(__import__("time").time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(user_prompt),
            "completion_tokens": len(answer),
            "total_tokens": len(user_prompt) + len(answer),
        },
    }
    return response_body
