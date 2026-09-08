#!/usr/bin/env python3
import hashlib
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
import anthropic

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rene_la_taupe import AgentConfig, ReneLaTaupeAgent, InjectionDetector
from rene_la_taupe.ingestion import (
    DocumentParseError,
    UnsupportedFileTypeError,
    chunk_text,
    new_corpus_id,
    new_doc_id,
    normalize_unicode,
    parse_document,
)
from rene_la_taupe.security_log import log_event
from rene_la_taupe.tools.sqlite_store import SqliteCorpusStore, SqliteDatabase, SqliteReportStore

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
DETECTION_MODEL = os.environ.get("DETECTION_MODEL", ANTHROPIC_MODEL)
SEARCH_TOP_K = int(os.environ.get("SEARCH_TOP_K", "5"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "la_taupe.db")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
detector = InjectionDetector(client, model=DETECTION_MODEL) if client else None

db = SqliteDatabase(DATABASE_PATH)
corpus_store = SqliteCorpusStore(db)
report_store = SqliteReportStore(db)

SYSTEM_PROMPT = (
    "Tu réponds toujours en français, sauf si l'utilisateur écrit explicitement "
    "dans une autre langue et te demande d'y répondre. Si son message est ambigu "
    "ou trop court pour être sûr de sa langue, réponds en français par défaut."
)


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

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        reply = response.content[0].text
    except anthropic.APIError:
        return jsonify(error="Erreur lors de l'appel au modèle."), 502

    return jsonify(reply=reply)


@app.route("/ingest", methods=["POST"])
def ingest():
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

        result = detector.analyze(doc_id, normalized_text)
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

    return jsonify(corpus_id=corpus_id, documents=documents, quarantine_count=quarantine_count)


@app.route("/query", methods=["POST"])
def query():
    if client is None:
        return jsonify(error="ANTHROPIC_API_KEY manquante côté serveur (.env)."), 500

    data = request.get_json(silent=True) or {}
    corpus_id = (data.get("corpus_id") or "").strip()
    question = (data.get("question") or "").strip()

    if not corpus_id:
        return jsonify(error="Le champ 'corpus_id' est requis."), 400
    if not question:
        return jsonify(error="Le champ 'question' est requis."), 400
    if not corpus_store.corpus_exists(corpus_id):
        return jsonify(error=f"Corpus inconnu : '{corpus_id}'."), 404

    log_event("query.start", corpus_id=corpus_id, question=question[:200])

    agent = ReneLaTaupeAgent(
        client,
        corpus_store,
        report_store,
        config=AgentConfig(model=ANTHROPIC_MODEL, max_search_results=SEARCH_TOP_K),
    )

    try:
        report = agent.run(corpus_id, question)
    except anthropic.APIError:
        return jsonify(error="Erreur lors de l'appel au modèle."), 502

    corpus_store.mark_processed(corpus_id)
    log_event("query.done", corpus_id=corpus_id, report_id=report.report_id)

    return jsonify(report.model_dump())


@app.route("/report/<report_id>", methods=["GET"])
def get_report(report_id):
    report = report_store.get_report(report_id)
    if report is None:
        return jsonify(error=f"Rapport inconnu : '{report_id}'."), 404
    return jsonify(report.model_dump())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
