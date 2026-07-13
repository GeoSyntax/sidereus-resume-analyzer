import json
import re
from typing import Any

import httpx

from app.config import settings


JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class AIClient:
    def __init__(self) -> None:
        self.enabled = settings.llm_enabled
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.api_key = settings.openai_api_key

    async def chat_json(self, system_prompt: str, user_prompt: str, timeout: float = 20.0) -> dict[str, Any] | None:
        if not self.enabled or not self.api_key:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return parse_json_content(content)
        except Exception:
            return None


def parse_json_content(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    match = JSON_FENCE.search(content)
    if match:
        content = match.group(1)
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None

