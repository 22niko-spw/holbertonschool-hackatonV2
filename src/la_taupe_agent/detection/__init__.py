# Barrière de détection d'injection — LA TAUPE (Yo)
# Version minimale Palier 2 : détection par LLM-juge avec prompt structuré.
# Remplace plus tard par classifier dédié + règles déterministes.

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from la_taupe_agent.prompts import DETECTION_SYSTEM_PROMPT
from la_taupe_agent.schemas import QuarantineEntry

logger = logging.getLogger(__name__)

Technique = Literal[
    "override_direct",
    "role_change",
    "fake_system",
    "exfiltration",
    "disable_protection",
    "anti_reporting",
    "conditional",
    "obfuscation",
    "autre",
]


class DetectionAttempt(BaseModel):
    technique: Technique
    excerpt: str
    location: str
    reason: str


class DetectionResult(BaseModel):
    suspect: bool
    confidence: float = Field(ge=0.0, le=1.0)
    attempts: list[DetectionAttempt]


class InjectionDetector:
    """
    Détecteur d'injection de prompt indirecte.
    Utilise un LLM-juge avec prompt système strict pour analyser un document.
    """

    def __init__(self, llm_client: Any, model: str = "gpt-4o-mini") -> None:
        self.llm = llm_client
        self.model = model

    def analyze(self, doc_id: str, text: str) -> DetectionResult:
        """
        Analyse un document unique et retourne le résultat de détection.
        """
        # Tronquer si trop long (garder début + milieu + fin pour couverture)
        max_chars = 8000
        if len(text) > max_chars:
            third = max_chars // 3
            text = text[:third] + "\n...\n" + text[len(text)//2 - third//2 : len(text)//2 + third//2] + "\n...\n" + text[-third:]

        messages = [
            {"role": "system", "content": DETECTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"DOCUMENT ID: {doc_id}\n\nCONTENU:\n{text}\n\nAnalyse ce document et retourne UNIQUEMENT le JSON de détection."},
        ]

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
                max_tokens=1000,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            result = DetectionResult(**data)
            logger.info(f"Détection doc={doc_id} suspect={result.suspect} confidence={result.confidence} attempts={len(result.attempts)}")
            return result
        except Exception as e:
            logger.error(f"Erreur détection doc={doc_id}: {e}")
            # Fail-safe : en cas d'erreur, on considère comme suspect par prudence
            return DetectionResult(suspect=True, confidence=0.5, attempts=[
                DetectionAttempt(technique="autre", excerpt="", location="", reason=f"Erreur analyse: {e}")
            ])

    def to_quarantine_entries(self, doc_id: str, result: DetectionResult) -> list[QuarantineEntry]:
        """Convertit un DetectionResult en liste QuarantineEntry pour la BDD."""
        if not result.suspect:
            return []
        entries = []
        for attempt in result.attempts:
            entries.append(QuarantineEntry(
                doc_id=doc_id,
                technique=attempt.technique,
                excerpt=attempt.excerpt[:500],
                confidence=result.confidence,
                detected_at="",  # sera rempli par l'appelant avec datetime.now()
            ))
        return entries
