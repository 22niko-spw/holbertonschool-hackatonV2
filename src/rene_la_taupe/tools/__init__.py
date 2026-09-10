# Outils typés pour l'agent René LA TAUPE — Yo
# Implémentations minimales (in-memory) pour Palier 2.
# Le backend réel (Kévin) fournira les implémentations persistantes.

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from rene_la_taupe.schemas import CitedAnswer, DocHit, DocMeta, QuarantineEntry, Report


class CorpusStore(ABC):
    """Interface du store de corpus (fourni par le backend Kévin)."""

    @abstractmethod
    def search(self, corpus_id: str, query: str, k: int) -> list[DocHit]:
        pass

    @abstractmethod
    def get_metadata(self, doc_id: str) -> DocMeta | None:
        pass

    @abstractmethod
    def list_quarantine(self, corpus_id: str) -> list[QuarantineEntry]:
        pass

    @abstractmethod
    def get_quarantine_excerpt(self, doc_id: str, chunk_id: str) -> str | None:
        pass


class ReportStore(ABC):
    """Interface du store de rapports (fourni par le backend Kévin)."""

    @abstractmethod
    def save_report(self, report: Report) -> Report:
        pass

    @abstractmethod
    def update_question(self, report_id: str, question: str) -> None:
        """Réécrit la question après coup (le rapport est persisté avant)."""
        pass


class InMemoryCorpusStore(CorpusStore):
    """Implémentation temporaire en mémoire pour tests standalone."""

    def __init__(self) -> None:
        self._corpora: dict[str, dict[str, Any]] = {}

    def add_corpus(self, corpus_id: str, documents: list[dict], quarantine: list[QuarantineEntry]) -> None:
        """Méthode helper pour peupler le store (utilisée en test)."""
        self._corpora[corpus_id] = {
            "documents": {d["doc_id"]: d for d in documents},
            "quarantine": quarantine,
        }

    def search(self, corpus_id: str, query: str, k: int) -> list[DocHit]:
        corpus = self._corpora.get(corpus_id)
        if not corpus:
            return []
        # Recherche naïve : filtre documents clean + matching mot-clé simple
        hits = []
        for doc in corpus["documents"].values():
            if doc.get("status") != "clean":
                continue
            for i, chunk in enumerate(doc.get("chunks", [])):
                if query.lower() in chunk["text"].lower():
                    hits.append(DocHit(
                        doc_id=doc["doc_id"],
                        chunk_id=chunk["chunk_id"],
                        score=1.0,
                        text=chunk["text"],
                    ))
        return hits[:k]

    def get_metadata(self, doc_id: str) -> DocMeta | None:
        for corpus in self._corpora.values():
            doc = corpus["documents"].get(doc_id)
            if doc:
                return DocMeta(**doc)
        return None

    def list_quarantine(self, corpus_id: str) -> list[QuarantineEntry]:
        corpus = self._corpora.get(corpus_id)
        if not corpus:
            return []
        quarantine: list[QuarantineEntry] = corpus.get("quarantine", [])
        return quarantine

    def get_quarantine_excerpt(self, doc_id: str, chunk_id: str) -> str | None:
        for corpus in self._corpora.values():
            doc = corpus["documents"].get(doc_id)
            if doc and doc.get("status") == "quarantined":
                for chunk in doc.get("chunks", []):
                    if chunk["chunk_id"] == chunk_id:
                        text: str = chunk["text"]
                        return text
        return None


class InMemoryReportStore(ReportStore):
    """Implémentation temporaire en mémoire pour tests standalone."""

    def __init__(self) -> None:
        self._reports: dict[str, Report] = {}

    def save_report(self, report: Report) -> Report:
        self._reports[report.report_id] = report
        return report

    def update_question(self, report_id: str, question: str) -> None:
        report = self._reports.get(report_id)
        if report is not None:
            report.question = question


# ─── Outils ───

def search_corpus(query: str, k: int, corpus_id: str, store: CorpusStore) -> list[DocHit]:
    """Recherche vectorielle/BM25 dans le corpus SAIN uniquement."""
    return store.search(corpus_id, query, k)


def get_doc_metadata(doc_id: str, store: CorpusStore) -> DocMeta | None:
    """Récupère métadonnées d'un document."""
    return store.get_metadata(doc_id)


def list_quarantine(corpus_id: str, store: CorpusStore) -> list[QuarantineEntry]:
    """Liste les documents en quarantaine pour un corpus."""
    return store.list_quarantine(corpus_id)


def read_quarantine_excerpt(doc_id: str, chunk_id: str, store: CorpusStore) -> str | None:
    """Retourne l'extrait exact mis en quarantaine (pour affichage audit)."""
    return store.get_quarantine_excerpt(doc_id, chunk_id)


def cite_sources(answer: str, hits: list[DocHit]) -> CitedAnswer:
    """
    Attache les citations aux segments de la réponse.
    Version simplifiée : associe chaque hit à une citation span approximative.
    La confiance reflète la force probante de la récupération (score moyen
    des hits) : 0.0 sans passage pertinent, pour que l'UI n'affiche jamais
    une réponse inventée avec assurance.
    """
    from rene_la_taupe.schemas import Citation

    citations = []
    for i, hit in enumerate(hits):
        # Heuristique simple : on suppose que la réponse cite les hits dans l'ordre
        # Le span est approximatif — en production, utiliser un alignement plus précis
        span_start = i * 100
        span_end = span_start + min(len(hit.text), 200)
        citations.append(Citation(
            doc_id=hit.doc_id,
            chunk_id=hit.chunk_id,
            span_start=span_start,
            span_end=span_end,
        ))
    confidence = sum(h.score for h in hits) / len(hits) if hits else 0.0
    return CitedAnswer(answer=answer, citations=citations, confidence=min(1.0, max(0.0, confidence)))


def finalize_report(
    corpus_id: str,
    answer: CitedAnswer,
    quarantine: list[QuarantineEntry],
    store: ReportStore,
) -> Report:
    """Écrit le rapport final en BDD — SEUL outil à effet de bord."""
    report = Report(
        report_id=str(uuid.uuid4()),
        corpus_id=corpus_id,
        question="",  # sera rempli par l'appelant
        answer=answer,
        quarantine=quarantine,
        created_at=datetime.utcnow().isoformat() + "Z",
    )
    return store.save_report(report)
