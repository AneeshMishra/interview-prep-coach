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

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
