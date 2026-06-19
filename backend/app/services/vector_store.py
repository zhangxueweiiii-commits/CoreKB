from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings
from app.services.query_metadata_extractor import sanitize_metadata_filter


def build_qdrant_metadata_filter(metadata_filter: dict | None) -> list[qmodels.FieldCondition]:
    sanitized = sanitize_metadata_filter(metadata_filter)
    return [
        qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))
        for key, value in sanitized.items()
    ]


class VectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncQdrantClient(
            url=self.settings.qdrant_url,
            api_key=self.settings.qdrant_api_key,
        )

    async def ensure_collection(self) -> None:
        collections = await self.client.get_collections()
        names = {collection.name for collection in collections.collections}
        if self.settings.qdrant_collection in names:
            return
        await self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(
                size=self.settings.embedding_dimension,
                distance=qmodels.Distance.COSINE,
            ),
        )

    async def upsert_chunks(self, points: list[tuple[str, list[float], dict]]) -> None:
        if not points:
            return
        await self.ensure_collection()
        await self.client.upsert(
            collection_name=self.settings.qdrant_collection,
            points=[
                qmodels.PointStruct(id=point_id, vector=vector, payload=payload)
                for point_id, vector, payload in points
            ],
        )

    async def search(
        self,
        query_vector: list[float],
        knowledge_base_ids: list[str],
        top_k: int,
        score_threshold: float | None,
        metadata_filter: dict | None = None,
    ):
        await self.ensure_collection()
        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="knowledge_base_id",
                    match=qmodels.MatchAny(any=knowledge_base_ids),
                )
            ]
            + build_qdrant_metadata_filter(metadata_filter)
        )
        return await self.client.search(
            collection_name=self.settings.qdrant_collection,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

    async def delete_document(self, document_id: str) -> None:
        await self.ensure_collection()
        await self.client.delete(
            collection_name=self.settings.qdrant_collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id", match=qmodels.MatchValue(value=document_id)
                        )
                    ]
                )
            ),
        )
