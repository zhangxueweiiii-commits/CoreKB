import httpx
import json

from app.core.config import get_settings


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def chat(self, messages: list[dict[str, str]]) -> str:
        if not self.settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required for chat")
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        payload = {
            "model": self.settings.llm_chat_model,
            "messages": messages,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    async def stream_chat(self, messages: list[dict[str, str]]):
        if not self.settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required for chat")
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        payload = {
            "model": self.settings.llm_chat_model,
            "messages": messages,
            "temperature": 0.2,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = payload.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content")
                    if text:
                        yield text
