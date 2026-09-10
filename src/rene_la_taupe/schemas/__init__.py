from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DocHit(BaseModel):
    doc_id: str
    chunk_id: str
    score: float
    text: str


class DocMeta(BaseModel):
    doc_id: str
    filename: str
    status: Literal["clean", "quarantined"]
    upload_ts: str
    sha256: str


class QuarantineEntry(BaseModel):
    doc_id: str
    technique: str
    excerpt: str
    confidence: float = Field(ge=0.0, le=1.0)
    detected_at: str


class Citation(BaseModel):
    doc_id: str
    chunk_id: str
    span_start: int
    span_end: int


class CitedAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CostUsage(BaseModel):
    """Coût mesuré d'une requête : tokens, appels LLM, durée, estimation $.

    Renseigné depuis response.usage de l'API (jamais deviné). estimated_cost_usd
    est indicatif (barème codé côté backend) et None si le modèle est inconnu.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    duration_ms: float = 0.0
    estimated_cost_usd: float | None = None


class Report(BaseModel):
    report_id: str
    corpus_id: str
    question: str
    answer: CitedAnswer
    quarantine: list[QuarantineEntry]
    created_at: str
