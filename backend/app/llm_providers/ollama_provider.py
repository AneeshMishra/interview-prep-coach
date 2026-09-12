import json
from typing import Iterator

import httpx

from app.llm_providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": self._messages(system_prompt, user_prompt),
                "stream": False,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        # Ollama's streaming format is NDJSON: one complete JSON object per
        # line, each carrying an incremental content fragment, terminated
        # by a line with "done": true.
        with httpx.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": self._messages(system_prompt, user_prompt),
                "stream": True,
            },
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                content = data.get("message", {}).get("content")
                if content:
                    yield content
