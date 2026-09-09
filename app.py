#!/usr/bin/env python3
# Palier 4 : graceful shutdown, health check, correlation ID, resilience

import atexit
import hashlib
import os
import signal
import sys
import threading
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request, g
import anthropic

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rene_la_taupe import AgentConfig, ReneLaTaupeAgent, InjectionDetector
from rene_la_taupe.agent import AgentLoopError, ToolExecutionError
from rene_la_taupe.ingestion import (
    DocumentParseError,
    UnsupportedFileTypeError,
    chunk_text,
    new_corpus_id,
    new_doc_id,
    normalize_unicode,
    parse_document,
)
from rene_la_taupe.security_log import log_event, log_error, generate_correlation_id, set_correlation_id
from rene_la_taupe.tools.sqlite_store import SqliteCorpusStore, SqliteDatabase, SqliteReportStore

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
DETECTION_MODEL = os.environ.get("DETECTION_MODEL", ANTHROPIC_MODEL)
SEARCH_TOP_K = int(os.environ.get("SEARCH_TOP_K", "5"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "la_taupe.db")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "30.0"))

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# État global pour shutdown
_shutdown_event = threading.Event()
_shutdown_lock = threading.Lock()
_is_shutting_down = False

# Clients globaux
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=LLM_TIMEOUT_SECONDS) if ANTHROPIC_API_KEY else None
detector = InjectionDetector(client, model=DETECTION_MODEL) if client else None

db = SqliteDatabase(DATABASE_PATH)
corpus_store = SqliteCorpusStore(db)
report_store = SqliteReportStore(db)

SYSTEM_PROMPT = (
    "Tu réponds toujours en français, sauf si l'utilisateur écrit explicitement "
    "dans une autre langue et te demande d'y répondre. Si son message est ambigu "
    "ou trop court pour être sûr de sa langue, réponds en français par défaut."
)


# ─── Middleware : Correlation ID ───
@app.before_request
def inject_correlation_id():
    """Génère ou propage un correlation ID pour tracer la requête."""
    cid = request.headers.get("X-Correlation-ID") or generate_correlation_id()
    set_correlation_id(cid)
    g.correlation_id = cid
    g.start_time = datetime.now(timezone.utc)


@app.after_request
def add_correlation_header(response):
    """Ajoute le correlation ID dans les headers de réponse."""
    if hasattr(g, "correlation_id"):
        response.headers["X-Correlation-ID"] = g.correlation_id
    return response


# ─── Graceful Shutdown ───
def _shutdown_handler(signum, frame):
    """Handler pour SIGTERM/SIGINT : arrête proprement."""
    global _is_shutting_down
    with _shutdown_lock:
        if _is_shutting_down:
            return
        _is_shutting_down = True

    log_event("shutdown.initiated", signal=signum, pid=os.getpid())
    _shutdown_event.set()

    # Donner le temps aux requêtes en cours de finir (max 10s)
    import time
    time.sleep(0.1)

    # Fermer connexions DB
    try:
        db.connection().close()
        log_event("shutdown.db_closed")
    except Exception as e:
        log_error("shutdown.db_close_failed", e)

    log_event("shutdown.completed", pid=os.getpid())
    sys.exit(0)


def _cleanup_at_exit():
    """Cleanup via atexit (pour tuer proprement si pas de signal)."""
    if not _is_shutting_down:
        _shutdown_handler(signal.SIGTERM, None)


signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)
atexit.register(_cleanup_at_exit)


def _check_shutdown() -> bool:
    """Vérifie si un shutdown est en cours."""
    return _shutdown_event.is_set()


# ─── Routes ───
@app.route("/")
def index():
    if _check_shutdown():
        return jsonify(error="Service shutting down"), 503
    return app.send_static_file("index.html")


@app.route("/health", methods=["GET"])
def health():
    """Health check pour load balancer / orchestrateur."""
    if _check_shutdown():
        return jsonify(status="shutting_down"), 503

    # Vérifier DB accessible
    try:
        db.connection().execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    # Vérifier clé API
    api_ok = client is not None

    status = "healthy" if (db_ok and api_ok) else "degraded"
    code = 200 if status == "healthy" else 503

    return jsonify(
        status=status,
        database=db_ok,
        api_key_configured=api_ok,
        shutdown=_check_shutdown(),
    ), code


@app.route("/api/ask", methods=["POST"])
def ask():
    if _check_shutdown():
        return jsonify(error="Service shutting down"), 503
    if client is None:
        return jsonify(error="ANTHROPIC_API_KEY manquante côté serveur (.env)."), 500

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="Le champ 'message' est requis."), 400

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        reply = response.content[0].text
    except anthropic.APIError as e:
        log_error("api.ask.llm_error", e, message_len=len(message))
        return jsonify(error="Erreur lors de l'appel au modèle."), 502

    return jsonify(reply=reply)


@app.route("/ingest", methods=["POST"])
def ingest():
    if _check_shutdown():
        return jsonify(error="Service shutting down"), 503
    if detector is None:
        return jsonify(error="ANTHROPIC_API_KEY manquante côté serveur (.env)."), 500

    files = request.files.getlist("files")
    if not files:
        return jsonify(error="Aucun fichier reçu (champ multipart 'files' attendu)."), 400

    corpus_id = new_corpus_id()
    corpus_store.create_corpus(corpus_id)
    log_event("ingest.start", corpus_id=corpus_id, file_count=len(files))

    documents = []
    quarantine_count = 0

    for file in files:
        if _check_shutdown():
            log_event("ingest.interrupted", corpus_id=corpus_id, reason="shutdown")
            break

        filename = file.filename or "sans_nom"
        raw = file.read()
        sha256 = hashlib.sha256(raw).hexdigest()

        try:
            raw_text = parse_document(filename, raw)
        except (UnsupportedFileTypeError, DocumentParseError) as exc:
            log_event("ingest.parse_error", corpus_id=corpus_id, filename=filename, error=str(exc))
            documents.append({"filename": filename, "status": "error", "error": str(exc)})
            continue

        normalized_text = normalize_unicode(raw_text)
        chunks = chunk_text(normalized_text)
        doc_id = new_doc_id()

        try:
            result = detector.analyze(doc_id, normalized_text)
        except Exception as e:
            log_error("ingest.detection_error", e, corpus_id=corpus_id, doc_id=doc_id)
            # Fail-safe : quarantaine par prudence
            result = type("obj", (object,), {
                "suspect": True,
                "confidence": 0.5,
                "attempts": [type("obj", (object,), {
                    "technique": "autre",
                    "excerpt": "",
                    "location": "",
                    "reason": f"Erreur détection: {e}"
                })()]
            })()

        status = "quarantined" if result.suspect else "clean"

        try:
            corpus_store.add_document(corpus_id, doc_id, filename, status, sha256, chunks)
        except Exception as e:
            log_error("ingest.db_error", e, corpus_id=corpus_id, doc_id=doc_id)
            documents.append({"doc_id": doc_id, "filename": filename, "status": "error", "error": str(e)})
            continue

        if result.suspect:
            quarantine_count += 1
            entries = detector.to_quarantine_entries(doc_id, result)
            now = datetime.now(timezone.utc).isoformat()
            for entry in entries:
                entry.detected_at = now
            try:
                corpus_store.add_quarantine_entries(corpus_id, entries)
            except Exception as e:
                log_error("ingest.quarantine_db_error", e, corpus_id=corpus_id, doc_id=doc_id)
            log_event(
                "ingest.quarantined",
                corpus_id=corpus_id,
                doc_id=doc_id,
                filename=filename,
                confidence=result.confidence,
                techniques=[a.technique for a in result.attempts],
            )
        else:
            log_event("ingest.clean", corpus_id=corpus_id, doc_id=doc_id, filename=filename)

        documents.append({"doc_id": doc_id, "filename": filename, "status": status})

    log_event(
        "ingest.done",
        corpus_id=corpus_id,
        document_count=len(documents),
        quarantine_count=quarantine_count,
    )

    return jsonify(corpus_id=corpus_id, documents=documents, quarantine_count=quarantine_count)


@app.route("/query", methods=["POST"])
def query():
    if _check_shutdown():
        return jsonify(error="Service shutting down"), 503
    if client is None:
        return jsonify(error="ANTHROPIC_API_KEY manquante côté serveur (.env)."), 500

    data = request.get_json(silent=True) or {}
    corpus_id = (data.get("corpus_id") or "").strip()
    question = (data.get("question") or "").strip()
    enabled_tools = data.get("enabled_tools")
    if not isinstance(enabled_tools, list) or not all(isinstance(t, str) for t in enabled_tools):
        enabled_tools = None

    if not corpus_id:
        return jsonify(error="Le champ 'corpus_id' est requis."), 400
    if not question:
        return jsonify(error="Le champ 'question' est requis."), 400
    if not corpus_store.corpus_exists(corpus_id):
        return jsonify(error=f"Corpus inconnu : '{corpus_id}'."), 404

    log_event("query.start", corpus_id=corpus_id, question=question[:200], enabled_tools=enabled_tools)

    agent = ReneLaTaupeAgent(
        client,
        corpus_store,
        report_store,
        config=AgentConfig(
            model=ANTHROPIC_MODEL,
            max_search_results=SEARCH_TOP_K,
            enabled_tools=enabled_tools,
        ),
    )

    try:
        report = agent.run(corpus_id, question)
    except anthropic.APIError as e:
        log_error("query.llm_error", e, corpus_id=corpus_id)
        return jsonify(error="Erreur lors de l'appel au modèle."), 502
    except AgentLoopError as exc:
        log_error("query.agent_loop_error", exc, corpus_id=corpus_id)
        return jsonify(error=f"Erreur dans la boucle de l'agent : {exc}"), 502
    except ToolExecutionError as exc:
        log_error("query.tool_execution_error", exc, corpus_id=corpus_id, tool=exc.tool_name)
        return jsonify(error=f"Erreur d'exécution d'outil : {exc}"), 502
    except Exception as e:
        log_error("query.unexpected_error", e, corpus_id=corpus_id)
        return jsonify(error="Erreur interne du serveur."), 500

    try:
        corpus_store.mark_processed(corpus_id)
    except Exception as e:
        log_error("query.mark_processed_error", e, corpus_id=corpus_id)

    log_event("query.done", corpus_id=corpus_id, report_id=report.report_id)

    def _make_serializable(obj):
        """Convertit récursivement en types JSON-serialisables."""
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, (list, tuple)):
            return [_make_serializable(v) for v in obj]
        if isinstance(obj, dict):
            return {k: _make_serializable(v) for k, v in obj.items()}
        if hasattr(obj, "__dict__"):
            return _make_serializable(obj.__dict__)
        return obj

    trace = [_make_serializable(t.__dict__) for t in agent.get_traces()]

    return jsonify(**report.model_dump(), trace=trace)


@app.route("/report/<report_id>", methods=["GET"])
def get_report(report_id):
    if _check_shutdown():
        return jsonify(error="Service shutting down"), 503
    report = report_store.get_report(report_id)
    if report is None:
        return jsonify(error=f"Rapport inconnu : '{report_id}'."), 404
    return jsonify(report.model_dump())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    log_event("server.starting", port=port, pid=os.getpid())
    try:
        app.run(host="0.0.0.0", port=port, debug=debug)
    finally:
        _cleanup_at_exit()