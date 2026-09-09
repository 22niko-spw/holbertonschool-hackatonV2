# Logs de sécurité structurés — René LA TAUPE (Kévin)
# Chaque événement est émis en JSON (une ligne = un événement), pour être
# grep/parsable par un pipeline de supervision.

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_LOGGER_NAME = "rene_la_taupe.security"
_DEFAULT_LOG_DIR = "logs"

# Identifiant de la requête en cours, propagé automatiquement à chaque événement
# émis pendant son traitement (y compris depuis les couches basses).
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> None:
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        request_id = _request_id.get()
        if request_id:
            payload["request_id"] = request_id
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def get_journal_path() -> str:
    log_dir = os.environ.get("SECURITY_LOG_DIR", _DEFAULT_LOG_DIR)
    return os.path.join(log_dir, "security.log")


def get_security_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)

    # Journal fichier actif par défaut : sans lui, une coupure brutale emporte
    # toute la trace avec le process.
    journal_path = get_journal_path()
    os.makedirs(os.path.dirname(journal_path) or ".", exist_ok=True)
    file_handler = logging.FileHandler(journal_path, encoding="utf-8")
    file_handler.setFormatter(_JsonFormatter())
    logger.addHandler(file_handler)

    return logger


def log_event(event: str, **fields: Any) -> None:
    get_security_logger().info(event, extra={"fields": fields})


def log_error(event: str, **fields: Any) -> None:
    get_security_logger().error(event, extra={"fields": fields})


def flush() -> None:
    """Vide les buffers : appelé avant un arrêt pour ne rien perdre."""
    for handler in get_security_logger().handlers:
        handler.flush()
