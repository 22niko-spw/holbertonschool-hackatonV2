# LA TAUPE

Agent capable d'analyser un corpus de documents dont certains peuvent contenir des tentatives d'injection de prompt. Voir [SPEC.md](SPEC.md) pour le cadrage complet et [MENACES.md](MENACES.md) pour le modèle de menace.

## Quickstart (< 5 min)

Prérequis : Python 3.10+, une clé API Anthropic.

```bash
git clone https://github.com/22niko-spw/holbertonschool-hackatonV2.git
cd holbertonschool-hackatonV2

python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# éditer .env et coller votre ANTHROPIC_API_KEY

python app.py
```

Ouvrir [http://localhost:5000](http://localhost:5000), écrire un message, cliquer sur "Envoyer" : la réponse vient d'un vrai appel au modèle Claude, pas d'un mock.

## Backend (Kévin)

Routes exposées par `app.py` :

- `POST /api/ask` : question libre → réponse LLM directe (socle palier 2).
- `POST /ingest` : upload multipart de documents (PDF/DOCX/TXT/MD/JSON) → parsing, normalisation Unicode, découpage en chunks, criblage via le détecteur d'injection, persistance (SQLite) → retourne un `corpus_id`.
- `POST /query` : `corpus_id` + question → exécute l'agent sur le corpus sain, retourne le `Report` complet (réponse citée + quarantaine).
- `GET /report/<report_id>` : relit un rapport déjà généré.

```text
Upload (PDF/DOCX/TXT/MD/JSON)
    │  POST /ingest
    ▼
Pipeline d'ingestion (src/rene_la_taupe/ingestion)
    │  parsing → normalisation Unicode → chunking → détection d'injection
    ▼
SQLite (src/rene_la_taupe/tools/sqlite_store.py)
    │  documents, chunks, quarantine_entries, reports
    ▼
POST /query → moteur agentique → Report (réponse citée + quarantaine)
```

Le moteur agentique (recherche dans le corpus, génération de réponse citée, détection d'injection) est fourni par le module `src/rene_la_taupe/` — implémentation et responsabilité de Yo, le backend s'y branche mais n'en gère pas la logique interne.

Logs de sécurité structurés (JSON) : chaque étape d'ingestion et de détection est tracée, voir `src/rene_la_taupe/security_log.py`.

## Limites connues (palier 2)

- Aucune gestion de l'historique de conversation sur `/api/ask` (chaque message est indépendant).
- Recherche dans le corpus par recouvrement de mots-clés (pas d'embeddings/BM25 pour l'instant).
- Pas de tests automatisés côté backend à ce stade.
- Déploiement : pas encore fait (bonus optionnel).

## Documentation du projet

- [SPEC.md](SPEC.md) : problème, user stories, hors-scope, happy path, répartition du travail.
- [MENACES.md](MENACES.md) : modèle de menace, canaux d'entrée.
- [OUTILS.md](OUTILS.md) : architecture cible et signatures d'outils.
