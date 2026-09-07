import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
import anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
