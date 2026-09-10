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
- `GET /health` : état des dépendances (base, clé API, journal). 503 dès qu'une dépendance manque.
- `POST /admin/shutdown` : interrupteur d'arrêt (voir ci-dessous).

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

## Exploitation : arrêt, journal, pannes (palier 4)

### Interrupteur d'arrêt

L'agent se coupe **depuis l'application**, sans tuer le process de l'extérieur :

```bash
curl -X POST http://localhost:5000/admin/shutdown -H "X-Shutdown-Token: $SHUTDOWN_TOKEN"
```

Le jeton vient de `SHUTDOWN_TOKEN` (`.env`) ; sans jeton configuré l'interrupteur reste désactivé, et un jeton invalide est refusé et journalisé. Séquence exécutée : refus des nouvelles requêtes (503) → attente des requêtes en cours (`SHUTDOWN_GRACE_SECONDS`, 10s par défaut) → fermeture des connexions SQLite → arrêt du serveur. `SIGINT` (Ctrl+C) et `SIGTERM` déclenchent exactement la même séquence.

### Journal

Une ligne JSON par événement, horodatée en UTC, dans `logs/security.log` (`SECURITY_LOG_DIR`) **et** sur stdout. Chaque requête HTTP reçoit un `request_id` propagé à tous ses événements, ce qui permet de rejouer une requête de bout en bout :

```bash
tail -f logs/security.log
grep '"request_id": "d98c1d8c798d"' logs/security.log   # rejoue une requête précise
grep resource.unavailable logs/security.log             # toutes les pannes de dépendance
```

Événements : `app.start` / `app.stop`, `request.start` / `request.end` / `request.refused`, `ingest.*`, `query.*`, `health.changed`, `resource.unavailable`, `agent.loop_error`, `agent.tool_error`, `request.unhandled_error`, `shutdown.*`.

### Réaction quand une dépendance disparaît

| Ressource coupée | Détection | Réaction | Événement journalisé |
|---|---|---|---|
| Réseau / API injoignable | `APIConnectionError` | 503, requête abandonnée | `resource.unavailable reason=connection` |
| Clé API révoquée | `AuthenticationError` | 503 | `resource.unavailable reason=auth` |
| Quota dépassé | `RateLimitError` | 429 | `resource.unavailable reason=rate_limit` |
| Fichier de base supprimé/remplacé | comparaison d'inode | 503, écriture refusée | `resource.unavailable reason=file_missing\|file_replaced` |
| Panne SQLite | `sqlite3.Error` | 503 | `resource.unavailable reason=database` |
| Erreur imprévue | handler global | 500 + trace | `request.unhandled_error` |

Aucun chemin ne renvoie d'erreur sans écrire dans le journal : une panne muette est considérée comme un bug. Quand l'agent enveloppe une panne LLM dans `AgentLoopError`, la cause racine est dépliée pour que le journal indique la vraie ressource perdue et non une erreur générique.

Note : une connexion SQLite ouverte survit à la suppression de son fichier (le descripteur reste valide). C'est pourquoi la disponibilité de la base est vérifiée par l'inode du fichier et pas seulement par une requête de test — sinon la base peut disparaître sans que rien ne le signale.

## Durcissement (palier 5)

### Coût affiché

Chaque réponse de `/api/ask`, `/ingest` et `/query` inclut un champ `usage` (`calls`, `input_tokens`, `output_tokens`, `cost_usd`) calculé sur les vrais appels Anthropic de la requête, sans toucher au code de l'agent ou du détecteur — le client Anthropic est instrumenté une seule fois côté backend (`src/rene_la_taupe/cost_tracking.py`) et compte tout ce qui passe par lui. Le coût est aussi journalisé sur `request.end`. Reste à afficher côté frontend.

### Comportements définis pour entrées absurdes/vides/hostiles

- Fichier vide ou composé uniquement d'espaces → statut `"empty"` explicite (pas d'appel au détecteur gaspillé, pas de faux `"clean"`).
- Question dépassant `MAX_QUESTION_CHARS` (4000 par défaut) sur `/api/ask` ou `/query` → 400.
- Plus de `MAX_FILES_PER_INGEST` (50 par défaut) fichiers en un seul `/ingest` → 400.
- Extension non supportée ou document corrompu (PDF/DOCX illisible) → statut `"error"` pour ce document, le reste du lot est quand même traité.
- `corpus_id` malformé ou tentative d'injection → 404 propre (requêtes SQL déjà paramétrées, jamais de concaténation).
- Question sans rapport avec le corpus ingéré → l'agent l'admet explicitement plutôt que d'inventer une réponse.

### Éval automatisée

`scripts/hardening_test.py` rejoue 16 scénarios distincts (entrées vides, absurdes ou hostiles) contre un serveur réel et vérifie qu'aucun ne produit de crash silencieux ni de réponse inventée :

```bash
python scripts/hardening_test.py
```

Dernier résultat : `hardening_report.json` → 16/16.

## Limites connues

- Aucune gestion de l'historique de conversation sur `/api/ask` (chaque message est indépendant).
- Recherche dans le corpus par recouvrement de mots-clés (pas d'embeddings/BM25 pour l'instant).
- Pas de suite `pytest` sur les fonctions backend pures (parsing, normalisation, chunking, store SQLite) — la résilience et le durcissement sont couverts par `eval_resilience.py` et `hardening_test.py`, pas la logique unitaire.
- `/query` reste bloquant : pas de streaming de la réponse ni des appels d'outils.
- Déploiement : pas encore fait (bonus optionnel).

## Documentation du projet

- [SPEC.md](SPEC.md) : problème, user stories, hors-scope, happy path, répartition du travail.
- [MENACES.md](MENACES.md) : modèle de menace, canaux d'entrée.
- [OUTILS.md](OUTILS.md) : architecture cible et signatures d'outils.
