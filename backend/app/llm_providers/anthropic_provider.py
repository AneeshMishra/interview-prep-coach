import httpx

from app.llm_providers.base import LLMProvider

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None, model: str, base_url: str = DEFAULT_BASE_URL):
        if not api_key:
            raise ValueError(
                "Anthropic provider selected (IPC_LLM_PROVIDER=anthropic) but "
                "IPC_ANTHROPIC_API_KEY is not set."
            )
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": DEFAULT_MAX_TOKENS,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        # Messages API returns a list of content blocks; the structuring
        # prompt (see app/ingestion/structurer.py) asks for a single JSON
        # array with no prose, so concatenating text blocks is enough here.
        blocks = response.json()["content"]
        return "".join(block["text"] for block in blocks if block.get("type") == "text")
