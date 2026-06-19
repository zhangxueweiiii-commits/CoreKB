import httpx

from app.core.config import get_settings


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required for embedding")
        url = f"{self.settings.llm_base_url.rstrip('/')}/embeddings"
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        payload = {"model": self.settings.llm_embedding_model, "input": texts}
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda item: item.get("index", 0))]

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self.embed_texts([query])
        return embeddings[0]
