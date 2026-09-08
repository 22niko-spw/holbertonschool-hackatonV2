# Logs de sécurité structurés — René LA TAUPE (Kévin)
# Chaque événement est émis en JSON (une ligne = un événement), pour être
# grep/parsable par un pipeline de supervision.

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

_LOGGER_NAME = "rene_la_taupe.security"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def get_security_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)

    log_dir = os.environ.get("SECURITY_LOG_DIR")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(log_dir, "security.log"))
        file_handler.setFormatter(_JsonFormatter())
        logger.addHandler(file_handler)

    return logger


def log_event(event: str, **fields: Any) -> None:
    get_security_logger().info(event, extra={"fields": fields})
