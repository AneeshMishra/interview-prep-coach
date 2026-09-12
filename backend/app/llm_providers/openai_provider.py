import json
from typing import Iterator

import httpx

from app.llm_providers.base import LLMProvider

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None, model: str, base_url: str = DEFAULT_BASE_URL):
        if not api_key:
            raise ValueError(
                "OpenAI provider selected (IPC_LLM_PROVIDER=openai) but IPC_OPENAI_API_KEY is not set."
            )
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": self._messages(system_prompt, user_prompt),
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        # OpenAI streams Server-Sent Events: "data: {...}" lines, each with
        # an incremental content delta, terminated by a literal "data: [DONE]".
        with httpx.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": self._messages(system_prompt, user_prompt),
                "stream": True,
            },
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                data = json.loads(payload)
                content = data["choices"][0]["delta"].get("content")
                if content:
                    yield content
