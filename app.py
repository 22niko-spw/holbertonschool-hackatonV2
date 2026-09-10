#!/usr/bin/env python3
import hashlib
import hmac
import os
import signal
import sqlite3
import sys
import threading
import time
import traceback
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
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
from rene_la_taupe.security_log import (
    flush as flush_journal,
    get_journal_path,
    log_error,
    log_event,
    set_request_id,
)
from rene_la_taupe.cost_tracking import get_usage as get_cost_usage, instrument_client, start_tracking as start_cost_tracking
from rene_la_taupe.tools.sqlite_store import SqliteCorpusStore, SqliteDatabase, SqliteReportStore

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
DETECTION_MODEL = os.environ.get("DETECTION_MODEL", ANTHROPIC_MODEL)
SEARCH_TOP_K = int(os.environ.get("SEARCH_TOP_K", "5"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "la_taupe.db")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))
SHUTDOWN_TOKEN = os.environ.get("SHUTDOWN_TOKEN", "")
SHUTDOWN_GRACE_SECONDS = float(os.environ.get("SHUTDOWN_GRACE_SECONDS", "10"))
MAX_QUESTION_CHARS = int(os.environ.get("MAX_QUESTION_CHARS", "4000"))
MAX_FILES_PER_INGEST = int(os.environ.get("MAX_FILES_PER_INGEST", "50"))

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
if client is not None:
    instrument_client(client)
detector = InjectionDetector(client, model=DETECTION_MODEL) if client else None

db = SqliteDatabase(DATABASE_PATH)
corpus_store = SqliteCorpusStore(db)
report_store = SqliteReportStore(db)

SYSTEM_PROMPT = (
    "Tu réponds toujours en français, sauf si l'utilisateur écrit explicitement "
    "dans une autre langue et te demande d'y répondre. Si son message est ambigu "
    "ou trop court pour être sûr de sa langue, réponds en français par défaut."
)

# ─── État d'arrêt ────────────────────────────────────────────────────────────
_shutting_down = threading.Event()
_inflight = 0
_inflight_lock = threading.Lock()
_server = None  # renseigné dans __main__, permet un arrêt sans tuer le process
_last_health_status: str | None = None


def _begin_shutdown(source: str, **context) -> bool:
    """Déclenche l'arrêt propre. Retourne False si un arrêt est déjà en cours."""
    if _shutting_down.is_set():
        return False
    _shutting_down.set()
    log_event("shutdown.requested", source=source, **context)
    threading.Thread(target=_drain_and_stop, args=(source,), daemon=True).start()
    return True


def _drain_and_stop(source: str) -> None:
    """Attend la fin des requêtes en vol, ferme les ressources, arrête le serveur."""
    deadline = time.monotonic() + SHUTDOWN_GRACE_SECONDS
    while time.monotonic() < deadline:
        with _inflight_lock:
            if _inflight == 0:
                break
        time.sleep(0.05)

    with _inflight_lock:
        remaining = _inflight

    if remaining:
        log_event("shutdown.grace_expired", inflight=remaining, grace_seconds=SHUTDOWN_GRACE_SECONDS)
    else:
        log_event("shutdown.drained")

    closed = db.close_all()
    log_event("shutdown.complete", source=source, db_connections_closed=closed)
    flush_journal()

    if _server is not None:
        _server.shutdown()
    else:
        log_error("shutdown.no_server_handle", detail="lancer via 'python app.py' pour un arrêt piloté")


def _handle_signal(signum, _frame) -> None:
    _begin_shutdown("signal", signal=signal.Signals(signum).name)


# ─── Réaction aux ressources disparues ───────────────────────────────────────
def _require_database(route: str):
    """Refuse d'écrire si le fichier de base a disparu ou été remplacé.

    Sans ce garde, l'écriture réussirait dans un inode supprimé : donnée perdue,
    aucune trace. On préfère un refus explicite et journalisé.
    """
    status = db.file_status()
    if status == "ok":
        return None
    log_error(
        "resource.unavailable",
        resource="database",
        reason=f"file_{status}",
        path=db.db_path,
        route=route,
    )
    return jsonify(
        error=f"Base de données indisponible (fichier {status}).",
        resource="database",
        reason=f"file_{status}",
    ), 503


def _resource_failure(exc: Exception, resource: str, **context):
    """Classe la panne, la journalise avec son horodatage, renvoie une réponse explicite."""
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        reason, status, message = "auth", 503, "Clé API refusée ou révoquée."
    elif isinstance(exc, anthropic.APIConnectionError):
        reason, status, message = "connection", 503, "API du modèle injoignable (réseau)."
    elif isinstance(exc, anthropic.RateLimitError):
        reason, status, message = "rate_limit", 429, "Quota du modèle dépassé."
    elif isinstance(exc, sqlite3.Error):
        reason, status, message = "database", 503, "Base de données indisponible."
    else:
        reason, status, message = "api_error", 502, "Erreur de l'API du modèle."

    log_error(
        "resource.unavailable",
        resource=resource,
        reason=reason,
        error_type=type(exc).__name__,
        error=str(exc),
        **context,
    )
    return jsonify(error=message, resource=resource, reason=reason), status


# ─── Cycle de vie des requêtes ───────────────────────────────────────────────
@app.before_request
def _before_request():
    set_request_id(uuid.uuid4().hex[:12])
    start_cost_tracking()
    g.started_at = time.perf_counter()
    g.counted = False

    if _shutting_down.is_set() and request.path != "/health":
        log_event("request.refused", path=request.path, reason="shutting_down")
        return jsonify(error="Arrêt en cours, nouvelles requêtes refusées.", reason="shutting_down"), 503

    global _inflight
    with _inflight_lock:
        _inflight += 1
    g.counted = True

    log_event("request.start", method=request.method, path=request.path, remote_addr=request.remote_addr)
    return None


@app.after_request
def _after_request(response):
    if getattr(g, "counted", False):
        duration_ms = (time.perf_counter() - g.started_at) * 1000
        usage = get_cost_usage()
        log_event(
            "request.end",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
            **({"llm_calls": usage["calls"], "cost_usd": usage["cost_usd"]} if usage["calls"] else {}),
        )
    return response


@app.teardown_request
def _teardown_request(_exc):
    global _inflight
    if getattr(g, "counted", False):
        with _inflight_lock:
            _inflight -= 1
    set_request_id(None)


@app.errorhandler(Exception)
def _unhandled(exc):
    """Filet de sécurité : rien ne doit échouer sans laisser de trace."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, sqlite3.Error):
        return _resource_failure(exc, "database", route=request.path)
    log_error(
        "request.unhandled_error",
        path=request.path,
        error_type=type(exc).__name__,
        error=str(exc),
        traceback=traceback.format_exc(limit=5),
    )
    return jsonify(error="Erreur interne.", reason="unhandled"), 500


# ─── Supervision ─────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    global _last_health_status
    checks = {}
    healthy = True

    file_status = db.file_status()
    try:
        db.ping()
        checks["database"] = "ok" if file_status == "ok" else f"file_{file_status}"
        healthy = healthy and file_status == "ok"
    except sqlite3.Error as exc:
        checks["database"] = f"unavailable: {exc}"
        healthy = False

    checks["anthropic_key"] = "present" if ANTHROPIC_API_KEY else "missing"
    if not ANTHROPIC_API_KEY:
        healthy = False

    checks["journal"] = get_journal_path()

    if _shutting_down.is_set():
        status = "shutting_down"
    else:
        status = "ok" if healthy else "degraded"

    if status != _last_health_status:
        log_event("health.changed", status=status, previous=_last_health_status, checks=checks)
        _last_health_status = status

    return jsonify(status=status, checks=checks), 200 if healthy else 503


@app.route("/admin/shutdown", methods=["POST"])
def shutdown():
    """Interrupteur d'arrêt : coupe l'agent proprement, sans tuer le process de l'extérieur."""
    if not SHUTDOWN_TOKEN:
        log_error("shutdown.refused", reason="token_not_configured", remote_addr=request.remote_addr)
        return jsonify(error="Interrupteur désactivé : SHUTDOWN_TOKEN non configuré."), 403

    provided = request.headers.get("X-Shutdown-Token") or (request.get_json(silent=True) or {}).get("token") or ""
    if not hmac.compare_digest(str(provided), SHUTDOWN_TOKEN):
        log_error("shutdown.refused", reason="bad_token", remote_addr=request.remote_addr)
        return jsonify(error="Token invalide."), 403

    started = _begin_shutdown("http", remote_addr=request.remote_addr)
    return jsonify(
        status="shutting_down",
        already_in_progress=not started,
        grace_seconds=SHUTDOWN_GRACE_SECONDS,
        journal=get_journal_path(),
    ), 202


# ─── Routes applicatives ─────────────────────────────────────────────────────
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/ask", methods=["POST"])
def ask():
    if client is None:
        return jsonify(error="ANTHROPIC_API_KEY manquante côté serveur (.env)."), 500

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="Le champ 'message' est requis."), 400
    if len(message) > MAX_QUESTION_CHARS:
        return jsonify(error=f"Message trop long (max {MAX_QUESTION_CHARS} caractères)."), 400

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        reply = response.content[0].text
    except anthropic.APIError as exc:
        return _resource_failure(exc, "anthropic_api", route="/api/ask")

    return jsonify(reply=reply, usage=get_cost_usage())


@app.route("/ingest", methods=["POST"])
def ingest():
    if detector is None:
        return jsonify(error="ANTHROPIC_API_KEY manquante côté serveur (.env)."), 500

    files = request.files.getlist("files")
    if not files:
        return jsonify(error="Aucun fichier reçu (champ multipart 'files' attendu)."), 400
    if len(files) > MAX_FILES_PER_INGEST:
        return jsonify(error=f"Trop de fichiers (max {MAX_FILES_PER_INGEST} par ingestion)."), 400

    unavailable = _require_database("/ingest")
    if unavailable:
        return unavailable

    corpus_id = new_corpus_id()
    corpus_store.create_corpus(corpus_id)
    log_event("ingest.start", corpus_id=corpus_id, file_count=len(files))

    documents = []
    quarantine_count = 0

    for file in files:
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
        doc_id = new_doc_id()

        if not normalized_text.strip():
            # Rien à cribler ni à indexer : statut explicite plutôt qu'un
            # appel de détection sur une chaîne vide ou un doc "clean" fantôme
            # sans aucun chunk retrouvable par la recherche.
            corpus_store.add_document(corpus_id, doc_id, filename, "empty", sha256, [])
            log_event("ingest.empty", corpus_id=corpus_id, doc_id=doc_id, filename=filename)
            documents.append({"doc_id": doc_id, "filename": filename, "status": "empty"})
            continue

        chunks = chunk_text(normalized_text)

        try:
            result = detector.analyze(doc_id, normalized_text)
        except anthropic.APIError as exc:
            log_event("ingest.aborted", corpus_id=corpus_id, filename=filename, processed=len(documents))
            return _resource_failure(exc, "anthropic_api", route="/ingest", corpus_id=corpus_id, filename=filename)

        status = "quarantined" if result.suspect else "clean"
        corpus_store.add_document(corpus_id, doc_id, filename, status, sha256, chunks)

        if result.suspect:
            quarantine_count += 1
            entries = detector.to_quarantine_entries(doc_id, result)
            now = datetime.now(timezone.utc).isoformat()
            for entry in entries:
                entry.detected_at = now
            corpus_store.add_quarantine_entries(corpus_id, entries)
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

    return jsonify(
        corpus_id=corpus_id,
        documents=documents,
        quarantine_count=quarantine_count,
        usage=get_cost_usage(),
    )


@app.route("/query", methods=["POST"])
def query():
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
    if len(question) > MAX_QUESTION_CHARS:
        return jsonify(error=f"Question trop longue (max {MAX_QUESTION_CHARS} caractères)."), 400

    unavailable = _require_database("/query")
    if unavailable:
        return unavailable

    if not corpus_store.corpus_exists(corpus_id):
        return jsonify(error=f"Corpus inconnu : '{corpus_id}'."), 404

    log_event("query.start", corpus_id=corpus_id, question=question[:200], enabled_tools=enabled_tools)

    agent = ReneLaTaupeAgent(
        client,
        corpus_store,
        report_store,
        config=AgentConfig(model=ANTHROPIC_MODEL, max_search_results=SEARCH_TOP_K, enabled_tools=enabled_tools),
    )

    try:
        report = agent.run(corpus_id, question)
    except anthropic.APIError as exc:
        return _resource_failure(exc, "anthropic_api", route="/query", corpus_id=corpus_id)
    except AgentLoopError as exc:
        # L'agent encapsule les pannes LLM : on remonte la cause racine dans le journal.
        cause = exc.__cause__
        if isinstance(cause, anthropic.APIError):
            return _resource_failure(
                cause, "anthropic_api", route="/query", corpus_id=corpus_id, raised_as="AgentLoopError"
            )
        log_error("agent.loop_error", corpus_id=corpus_id, error=str(exc))
        return jsonify(error=f"Erreur dans la boucle de l'agent : {exc}", reason="agent_loop"), 502
    except ToolExecutionError as exc:
        log_error(
            "agent.tool_error",
            corpus_id=corpus_id,
            tool=getattr(exc, "tool_name", None),
            error=str(exc),
        )
        return jsonify(error=f"Erreur d'exécution d'outil : {exc}", reason="tool_execution"), 502

    corpus_store.mark_processed(corpus_id)
    log_event("query.done", corpus_id=corpus_id, report_id=report.report_id)

    trace = [asdict(t) for t in agent.get_traces()]
    return jsonify(**report.model_dump(), trace=trace, usage=get_cost_usage())


@app.route("/report/<report_id>", methods=["GET"])
def get_report(report_id):
    report = report_store.get_report(report_id)
    if report is None:
        return jsonify(error=f"Rapport inconnu : '{report_id}'."), 404
    return jsonify(report.model_dump())


if __name__ == "__main__":
    from werkzeug.serving import make_server

    port = int(os.environ.get("PORT", 5000))
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    _server = make_server("0.0.0.0", port, app, threaded=True)
    log_event(
        "app.start",
        port=port,
        model=ANTHROPIC_MODEL,
        detection_model=DETECTION_MODEL,
        database=DATABASE_PATH,
        journal=get_journal_path(),
        shutdown_switch="armed" if SHUTDOWN_TOKEN else "disabled",
        pid=os.getpid(),
    )
    try:
        _server.serve_forever()
    finally:
        log_event("app.stop", pid=os.getpid())
        flush_journal()
