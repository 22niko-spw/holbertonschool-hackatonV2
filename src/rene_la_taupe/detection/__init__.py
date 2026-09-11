# Barrière de détection d'injection — René LA TAUPE (Yo)
# Palier 4 : timeout, retry, fallback heuristique si LLM KO.

from __future__ import annotations

import json
import logging
import re
import time
from importlib.util import find_spec
from typing import Any, Literal

from pydantic import BaseModel, Field

from rene_la_taupe.prompts import DETECTION_SYSTEM_PROMPT
from rene_la_taupe.schemas import CostUsage, QuarantineEntry
from rene_la_taupe.security_log import log_error

TENACITY_AVAILABLE = find_spec("tenacity") is not None

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


# Patterns heuristiques pour mode dégradé (sans LLM)
_HEURISTIC_PATTERNS = {
    "override_direct": [
        r"ignore\s+(toutes?\s+)?(les\s+)?instructions?",
        r"oublie\s+(tes\s+)?(consignes?|instructions?)",
        r"réponds?\s+que\s+(tout\s+est\s+)?(safe|sûr|ok)",
        r"dis\s+que\s+(tout\s+est\s+)?(safe|sûr|ok)",
        r"ne\s+tiens?\s+pas\s+compte",
    ],
    "role_change": [
        r"tu\s+es\s+(maintenant|dorénavant)\s+(admin|administrateur|développeur|root|superuser)",
        r"deviens\s+(admin|administrateur|développeur)",
        r"sans\s+filtre\s+ni\s+limite",
        r"mode\s+(développeur|debug|admin)",
    ],
    "fake_system": [
        r"###\s*SYSTEM",
        r"<system>",
        r"\[SYSTEM\]",
        r"SYSTEM\s*:",
        r"###\s*INSTRUCTION",
    ],
    "exfiltration": [
        r"(révèle|montre|donne)\s+(ton|votre)\s+(prompt|system\s*prompt|chaîne\s+de\s+pensée|instructions?)",
        r"what\s+is\s+your\s+(prompt|system\s*prompt)",
        r"show\s+me\s+your\s+(prompt|instructions?)",
    ],
    "disable_protection": [
        r"désactive\s+(la\s+)?(détection|protection|sécurité|safety)",
        r"turn\s+off\s+(detection|protection|safety)",
        r"ne\s+(détecte|signale)\s+pas",
    ],
    "anti_reporting": [
        r"si\s+tu\s+(détectes?|trouves?)\s+.*\s+(ne\s+le\s+dis\s+pas|n.en\s+parle\s+pas|garde\s+le\s+secret)",
        r"ne\s+(l.écris|le\s+signale)\s+pas\s+dans\s+(le\s+)?rapport",
    ],
    "conditional": [
        r"si\s+le\s+mot\s+['\"]?\w+['\"]?\s+appara[îi]t",
        r"when\s+the\s+word\s+['\"]?\w+['\"]?\s+appears",
        r"si\s+.*\s+alors\s+(fais|execute|réponds?)",
    ],
    "obfuscation": [
        r"[\u200b-\u200f\ufeff]",  # zero-width chars
        r"(?:\\u[0-9a-fA-F]{4})+",  # unicode escapes
        r"(?:&#x[0-9a-fA-F]+;)+",  # HTML entities
    ],
}


def _heuristic_analyze(text: str) -> DetectionResult:
    """Analyse heuristique locale (mode dégradé sans LLM)."""
    text_lower = text.lower()
    attempts = []

    for technique, patterns in _HEURISTIC_PATTERNS.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            if matches:
                # Prendre le premier match pour l'extrait
                m = matches[0]
                start = max(0, m.start() - 50)
                end = min(len(text), m.end() + 50)
                excerpt = text[start:end].strip()
                attempts.append(DetectionAttempt(
                    technique=technique,
                    excerpt=excerpt[:500],
                    location=f"index {m.start()}",
                    reason=f"Pattern heuristique détecté: {pattern}",
                ))

    if attempts:
        # Confiance plus basse qu'avec LLM
        return DetectionResult(suspect=True, confidence=0.7, attempts=attempts)

    return DetectionResult(suspect=False, confidence=0.0, attempts=[])


class InjectionDetector:
    """
    Détecteur d'injection de prompt indirecte.
    Palier 4 : timeout, retry, fallback heuristique si LLM indisponible.
    """

    def __init__(
        self,
        llm_client: Any,
        model: str = "claude-haiku-4-5-20251001",
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def _call_llm_with_retry(self, messages: list[dict]) -> tuple[str, int, Any | None]:
        """Appel LLM avec retry. Retourne (contenu, tentatives, usage API ou None)."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.llm.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    system=DETECTION_SYSTEM_PROMPT,
                    messages=messages,
                )
                content = response.content[0].text if response.content else "{}"
                return content, attempt + 1, getattr(response, "usage", None)
            except Exception as e:
                last_error = e
                logger.warning(f"Tentative {attempt + 1}/{self.max_retries + 1} échouée: {e}")
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))  # backoff exponentiel

        raise last_error

    def analyze(self, doc_id: str, text: str, stats: CostUsage | None = None) -> DetectionResult:
        """
        Analyse un document unique et retourne le résultat de détection.
        Si stats est fourni, les tokens/appels LLM y sont accumulés (objet
        appartenant à l'appelant : sûr en concurrence).
        """
        # Tronquer si trop long (garder début + milieu + fin pour couverture)
        max_chars = 8000
        if len(text) > max_chars:
            third = max_chars // 3
            text = text[:third] + "\n...\n" + text[len(text)//2 - third//2 : len(text)//2 + third//2] + "\n...\n" + text[-third:]

        messages = [
            {"role": "user", "content": f"DOCUMENT ID: {doc_id}\n\nCONTENU:\n{text}\n\nAnalyse ce document et retourne UNIQUEMENT le JSON de détection."}
        ]

        try:
            content, attempts, usage = self._call_llm_with_retry(messages)
            if stats is not None:
                stats.llm_calls += attempts
                if usage is not None:
                    stats.input_tokens += getattr(usage, "input_tokens", 0) or 0
                    stats.output_tokens += getattr(usage, "output_tokens", 0) or 0
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                start = 1 if lines[0].startswith("```") else 0
                end = len(lines) - 1 if lines[-1].startswith("```") else len(lines)
                content = "\n".join(lines[start:end])

            # Extraire le premier objet JSON valide de la réponse
            # Gérer le cas où il y a du texte avant/après le JSON
            json_start = content.find('{')
            json_end = content.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_content = content[json_start:json_end + 1]
            else:
                json_content = content

            data = json.loads(json_content)
            result = DetectionResult(**data)
            logger.info(f"Détection doc={doc_id} suspect={result.suspect} confidence={result.confidence} attempts={len(result.attempts)}")
            return result

        except Exception as e:
            logger.error(f"Erreur détection LLM doc={doc_id}: {e}")
            log_error("detection.llm_failed", error_type=type(e).__name__, error=str(e), doc_id=doc_id, text_len=len(text))

            # MODE DÉGRADÉ : fallback heuristique
            logger.warning(f"Basculement mode heuristique pour doc={doc_id}")
            heuristic_result = _heuristic_analyze(text)
            if heuristic_result.suspect:
                logger.info(f"Détection heuristique doc={doc_id} suspect=True attempts={len(heuristic_result.attempts)}")
                return heuristic_result

            # Fail-safe final : suspect par prudence
            return DetectionResult(suspect=True, confidence=0.5, attempts=[
                DetectionAttempt(technique="autre", excerpt="", location="", reason=f"Erreur analyse + heuristique négative: {e}")
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
