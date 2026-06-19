from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    api: bool
    postgres: bool
    redis: bool
    qdrant: bool
    celery: bool
    timestamp: datetime
