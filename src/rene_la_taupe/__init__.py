# René LA TAUPE — Moteur Agentique & Sécurité (Yo)

from rene_la_taupe.agent import AgentConfig, ReneLaTaupeAgent, create_test_agent
from rene_la_taupe.detection import DetectionAttempt, DetectionResult, InjectionDetector
from rene_la_taupe.ingestion import (
    DocumentParseError,
    UnsupportedFileTypeError,
    chunk_text,
    new_corpus_id,
    new_doc_id,
    normalize_unicode,
    parse_document,
)
from rene_la_taupe.schemas import (
    Citation,
    CitedAnswer,
    CostUsage,
    DocHit,
    DocMeta,
    QuarantineEntry,
    Report,
)
from rene_la_taupe.security_log import log_event
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
from rene_la_taupe.tools.sqlite_store import SqliteCorpusStore, SqliteDatabase, SqliteReportStore

__all__ = [
    # Agent
    "ReneLaTaupeAgent",
    "AgentConfig",
    "create_test_agent",
    # Ingestion
    "parse_document",
    "normalize_unicode",
    "chunk_text",
    "new_doc_id",
    "new_corpus_id",
    "DocumentParseError",
    "UnsupportedFileTypeError",
    # Security Log
    "log_event",
    # Tools
    "CorpusStore",
    "ReportStore",
    "InMemoryCorpusStore",
    "InMemoryReportStore",
    "SqliteCorpusStore",
    "SqliteDatabase",
    "SqliteReportStore",
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
    "CostUsage",
    "DocHit",
    "DocMeta",
    "QuarantineEntry",
    "Citation",
    "CitedAnswer",
    "Report",
]

__version__ = "0.1.0"
