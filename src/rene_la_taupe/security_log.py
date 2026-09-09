# Logs de sécurité structurés — René LA TAUPE (Kévin)
# Chaque événement est émis en JSON (une ligne = un événement), pour être
# grep/parsable par un pipeline de supervision.
# Palier 4 : rotation, correlation ID, timestamp lisible, contexte enrichi.

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

_LOGGER_NAME = "rene_la_taupe.security"
_AUDIT_LOGGER_NAME = "rene_la_taupe.audit"

# Taille max par fichier : 10 Mo, garder 5 fichiers
_MAX_LOG_SIZE = 10 * 1024 * 1024
_BACKUP_COUNT = 5


class _JsonFormatter(logging.Formatter):
    """Formatter JSON avec timestamp ISO lisible et champs standards."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }

        # Correlation ID pour tracer une requête de bout en bout
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = correlation_id

        # Champs additionnels (fields)
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)

        # Exception info si présente
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def _get_correlation_id() -> Optional[str]:
    """Récupère le correlation_id depuis le contexte Flask si disponible."""
    try:
        from flask import g, has_request_context
        if has_request_context() and hasattr(g, "request_id"):
            return g.request_id
    except Exception:
        pass
    return None


def _make_record_factory():
    """Factory pour injecter correlation_id automatiquement dans tous les logs."""
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        cid = _get_correlation_id()
        if cid:
            record.correlation_id = cid
        return record

    return record_factory


def get_security_logger() -> logging.Logger:
    """Logger principal pour les événements de sécurité (ingestion, détection, quarantaine)."""
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    logger.propagate = False

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_JsonFormatter())
    logger.addHandler(console_handler)

    # File handler avec rotation
    log_dir = os.environ.get("SECURITY_LOG_DIR")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "security.log"),
            maxBytes=_MAX_LOG_SIZE,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(_JsonFormatter())
        logger.addHandler(file_handler)

    return logger


def get_audit_logger() -> logging.Logger:
    """Logger dédié pour l'audit des appels d'outils (traçabilité agent)."""
    logger = logging.getLogger(_AUDIT_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    logger.propagate = False

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_JsonFormatter())
    logger.addHandler(console_handler)

    log_dir = os.environ.get("SECURITY_LOG_DIR")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "audit.log"),
            maxBytes=_MAX_LOG_SIZE,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(_JsonFormatter())
        logger.addHandler(file_handler)

    return logger


def log_event(event: str, **fields: Any) -> None:
    """Log un événement de sécurité avec champs enrichis."""
    logger = get_security_logger()
    # Injecter correlation_id si dispo
    extra = {"fields": fields}
    cid = _get_correlation_id()
    if cid:
        extra["correlation_id"] = cid
    logger.info(event, extra=extra)


def log_audit(event: str, **fields: Any) -> None:
    """Log un événement d'audit (appel outil, décision agent)."""
    logger = get_audit_logger()
    extra = {"fields": fields}
    cid = _get_correlation_id()
    if cid:
        extra["correlation_id"] = cid
    logger.info(event, extra=extra)


def log_error(event: str, error: Exception, **fields: Any) -> None:
    """Log une erreur avec traceback."""
    logger = get_security_logger()
    extra = {"fields": fields, "error_type": type(error).__name__, "error_message": str(error)}
    cid = _get_correlation_id()
    if cid:
        extra["correlation_id"] = cid
    logger.error(event, extra=extra, exc_info=error)


def set_correlation_id(correlation_id: str) -> None:
    """Définit le correlation_id pour le contexte courant (middleware Flask)."""
    try:
        from flask import g, has_request_context
        if has_request_context():
            g.request_id = correlation_id
    except Exception:
        pass


def generate_correlation_id() -> str:
    """Génère un nouveau correlation ID."""
    return str(uuid.uuid4())[:8]