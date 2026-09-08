# René LA TAUPE — Moteur Agentique & Sécurité (Yo)

from rene_la_taupe.agent import AgentConfig, ReneLaTaupeAgent, create_test_agent
from rene_la_taupe.detection import DetectionAttempt, DetectionResult, InjectionDetector
from rene_la_taupe.schemas import (
    Citation,
    CitedAnswer,
    DocHit,
    DocMeta,
    QuarantineEntry,
    Report,
)
from rene_la_taupe.tools import (
    CorpusStore,
    InMemoryCorpusStore,
    InMemoryReportStore,
    ReportStore,
    cite_sources,
    finalize_report,
    get_doc_metadata,
    list_quarantine,
    read_quarantine_excerpt,
    search_corpus,
)

__all__ = [
    # Agent
    "ReneLaTaupeAgent",
    "AgentConfig",
    "create_test_agent",
    # Tools
    "CorpusStore",
    "ReportStore",
    "InMemoryCorpusStore",
    "InMemoryReportStore",
    "search_corpus",
    "get_doc_metadata",
    "list_quarantine",
    "read_quarantine_excerpt",
    "cite_sources",
    "finalize_report",
    # Detection
    "InjectionDetector",
    "DetectionResult",
    "DetectionAttempt",
    # Schemas
    "DocHit",
    "DocMeta",
    "QuarantineEntry",
    "Citation",
    "CitedAnswer",
    "Report",
]

__version__ = "0.1.0"
