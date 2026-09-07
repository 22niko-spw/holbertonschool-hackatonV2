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


class Report(BaseModel):
    report_id: str
    corpus_id: str
    question: str
    answer: CitedAnswer
    quarantine: list[QuarantineEntry]
    created_at: str
