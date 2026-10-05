import json
import os
import re
import time

import httpx

# The Gemini API key lives in LOOM_MODEL (project convention); the model name is fixed here.
# Tried in order; quotas are per model, so a 429/5xx on one falls through to the next.
MODELS = [os.getenv("LOOM_MODEL_NAME", "gemini-3.8-flash"), "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest"]


def _call(system: str, user: str, max_tokens: int, json_mode: bool) -> str:
    cfg = {"maxOutputTokens": max_tokens * 4}  # headroom for the model's internal thinking
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": cfg,
    }
    r = None
    for rnd in range(2):
        for model in MODELS:
            r = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": os.environ["LOOM_MODEL"]},
                json=body,
                timeout=60,
            )
            if r.status_code not in (404, 429, 500, 502, 503, 504):
                r.raise_for_status()
                return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
        time.sleep(2)
    r.raise_for_status()


def complete(system: str, user: str, max_tokens: int = 1200) -> str:
    return _call(system, user, max_tokens, json_mode=False)


def complete_json(system: str, user: str, max_tokens: int = 1200):
    text = _call(system, user, max_tokens, json_mode=True)
    m = re.search(r"[\[{].*[\]}]", text, re.S)
    return json.loads(m.group(0) if m else text)
