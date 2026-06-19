from __future__ import annotations

from dataclasses import replace
from typing import Any

import httpx

from app.core.config import get_settings


class RerankDisabledError(RuntimeError):
    pass


class RerankService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build_rerank_payload(self, query: str, results: list[Any]) -> dict:
        return {
            "model": self.settings.rerank_model,
            "query": query,
            "documents": [result.chunk_text for result in results],
            "top_n": len(results),
        }

    def normalize_rerank_scores(self, response: dict, candidate_count: int) -> list[tuple[int, float]]:
        raw_items = response.get("results") or response.get("data") or response.get("rankings") or []
        normalized: list[tuple[int, float]] = []
        if isinstance(raw_items, list):
            for position, item in enumerate(raw_items):
                if not isinstance(item, dict):
                    continue
                index = int(item.get("index", item.get("document_index", position)))
                score = float(item.get("relevance_score", item.get("score", item.get("rerank_score", 0.0))))
                if 0 <= index < candidate_count:
                    normalized.append((index, score))
        if not normalized and isinstance(response.get("scores"), list):
            normalized = [
                (index, float(score))
                for index, score in enumerate(response["scores"])
                if index < candidate_count
            ]
        return normalized

    async def rerank_results(self, query: str, results: list[Any], top_n: int) -> list[Any]:
        if not results:
            return []
        if not self.settings.rerank_enabled:
            raise RerankDisabledError("Rerank is disabled by RERANK_ENABLED=false")
        if not self.settings.rerank_base_url or not self.settings.rerank_model:
            raise RerankDisabledError("RERANK_BASE_URL and RERANK_MODEL are required when rerank is enabled")

        candidates = results[:top_n]
        payload = self.build_rerank_payload(query, candidates)
        headers = {}
        if self.settings.rerank_api_key:
            headers["Authorization"] = f"Bearer {self.settings.rerank_api_key}"
        url = f"{self.settings.rerank_base_url.rstrip('/')}/rerank"
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        score_pairs = self.normalize_rerank_scores(response.json(), len(candidates))
        if not score_pairs:
            raise RuntimeError("Rerank response did not include usable scores")
        score_by_index = dict(score_pairs)
        reranked = [
            replace(
                candidate,
                rerank_score=score_by_index[index],
                final_score=score_by_index[index],
            )
            for index, candidate in enumerate(candidates)
            if index in score_by_index
        ]
        missing = [
            replace(candidate, rerank_score=None, final_score=candidate.vector_score)
            for index, candidate in enumerate(candidates)
            if index not in score_by_index
        ]
        return sorted(reranked, key=lambda item: item.final_score or 0.0, reverse=True) + missing
