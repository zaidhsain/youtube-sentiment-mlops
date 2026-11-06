"""Schémas Pydantic : validation automatique des entrées / sorties de l'API."""
from typing import List

from pydantic import BaseModel, Field, field_validator

MAX_BATCH = 500
MAX_COMMENT_CHARS = 5000


class BatchRequest(BaseModel):
    comments: List[str] = Field(
        ..., min_length=1, max_length=MAX_BATCH,
        description=f"Liste de 1 à {MAX_BATCH} commentaires",
        examples=[["I love this video!", "This is the worst tutorial ever", "Posted at 10am"]],
    )

    @field_validator("comments")
    @classmethod
    def truncate_long_comments(cls, v: List[str]) -> List[str]:
        # On tronque plutôt que de rejeter : un commentaire très long reste analysable.
        return [c[:MAX_COMMENT_CHARS] for c in v]


class Prediction(BaseModel):
    text: str
    sentiment: int = Field(..., description="-1 négatif, 0 neutre, 1 positif")
    label: str
    confidence: float
    probabilities: dict


class Stats(BaseModel):
    total: int
    positive: int
    neutral: int
    negative: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    average_confidence: float
    sentiment_score: float = Field(..., description="Moyenne des sentiments, entre -1 et 1")


class BatchResponse(BaseModel):
    predictions: List[Prediction]
    stats: Stats
    processing_time_ms: float
    model_version: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str
    uptime_seconds: float
