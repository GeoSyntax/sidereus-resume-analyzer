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

    async def ocr_images(self, images_b64: list[str], timeout: float = 60.0) -> str | None:
        """OCR one or more page images with the vision model.

        Each item in ``images_b64`` is a base64-encoded PNG. Returns the
        concatenated plain text, or None if OCR is unavailable or fails so the
        caller can fall back gracefully.
        """
        if not settings.ocr_enabled or not self.api_key or not images_b64:
            return None

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Extract all text from these resume page images exactly as written, "
                    "preserving reading order and line breaks. Output only the raw text, "
                    "no commentary, no markdown."
                ),
            }
        ]
        for image_b64 in images_b64:
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
            )

        payload = {
            "model": settings.openai_vision_model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
            return text.strip() or None
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

