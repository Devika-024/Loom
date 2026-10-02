import json
import os
import re

import httpx

MODEL = os.getenv("LOOM_MODEL", "claude-sonnet-5-5")


def complete(system: str, user: str, max_tokens: int = 1200) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=60,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"])


def complete_json(system: str, user: str, max_tokens: int = 1200):
    text = complete(system + "\nReply with valid JSON only, no prose, no code fences.", user, max_tokens)
    m = re.search(r"[\[{].*[\]}]", text, re.S)
    return json.loads(m.group(0) if m else text)
