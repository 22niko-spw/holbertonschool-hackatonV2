# LA TAUPE

Agent IA qui répond à une question à partir d'un corpus documentaire, en détectant et isolant les tentatives d'injection de prompt cachées dans les documents avant qu'elles n'influencent la réponse.

**Statut actuel (Palier 2)** : deux briques existent en parallèle, pas encore branchées ensemble —
- l'**app web** (Kévin + Niko) : une question part vers un vrai modèle Claude et la réponse s'affiche dans le dashboard.
- le **moteur agentique** (Yo) : outils typés, détection d'injection, boucle de décision — testable en standalone, pas encore relié à l'app web (attend un corpus/store persistant côté backend).

## Quickstart — App web (≤ 5 min)

Prérequis : Python 3.10+, Node.js 18+, une clé API Anthropic.

```bash
git clone https://github.com/22niko-spw/holbertonschool-hackatonV2.git
cd holbertonschool-hackatonV2

cp .env.example .env
# éditer .env et coller votre ANTHROPIC_API_KEY

cd frontend && npm install && npm run build && cd ..

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python app.py
```

Ouvrir [http://localhost:8000](http://localhost:8000), écrire un message, cliquer sur "Envoyer" : la réponse vient d'un vrai appel au modèle Claude, pas d'un mock.

## Quickstart — Moteur agentique standalone (Yo)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# éditer .env et mettre votre ANTHROPIC_API_KEY

# Tester le détecteur d'injection
python -m scripts.test_agent detection

# Tester l'agent complet
python -m scripts.test_agent agent --question "Quels sont les risques chimiques ?"
```

## Architecture

```text
Frontend (frontend/dist, build React — servi par Flask)
    │  fetch POST /api/ask { message }
    ▼
Backend Flask (app.py)
    │  clé API lue côté serveur uniquement, jamais exposée au frontend
    ▼
API Anthropic (appel réel)
    │
    ▼
Backend → Frontend (réponse affichée)
```

Un seul process Python sert à la fois le frontend buildé et la route API — pas de base de données, pas de Docker.

À ce stade, aucun traitement de corpus ni détection d'injection dans l'app web : c'est uniquement le tuyau de bout en bout (frontend → backend → LLM réel → backend → frontend). Le moteur agentique de Yo (ci-dessous) implémente la partie détection/quarantaine/citations visée par [OUTILS.md](OUTILS.md), mais tourne pour l'instant en dehors de l'app web.

## Structure (Yo)

```
src/rene_la_taupe/
├── agent.py           # Boucle de décision LLM (moteur principal)
├── detection/         # Barrière détection injection (LLM-juge)
├── prompts/           # Prompts système avec séparation données/instructions
├── schemas/           # Modèles Pydantic (DocHit, QuarantineEntry, Report, etc.)
└── tools/             # 6 outils typés (search_corpus, cite_sources, finalize_report, etc.)
```

## Rôle de Yo (Palier 2)

- **Moteur agentique** : `ReneLaTaupeAgent.run(corpus_id, question)` → `Report`
- **6 outils typés** : signatures conformes à `OUTILS.md`
- **Détection injection** : `InjectionDetector.analyze(doc_id, text)` → `DetectionResult`
- **Prompts système** : séparation stricte données vs instructions
- **Tests standalone** : `scripts/test_agent.py` (detection + agent)

## Dépendances externes

- `ANTHROPIC_API_KEY` dans `.env` (obligatoire, pour l'app web et le moteur agentique)
- Backend (Kévin) : fournira `CorpusStore` et `ReportStore` persistants, et la route qui appellera `ReneLaTaupeAgent`
- Frontend (Niko) : appellera cette route une fois exposée par le backend

## Happy Path cible (6 étapes)

1. Upload corpus + question
2. Ingestion & criblage (détection → quarantaine)
3. `search_corpus` sur documents **clean uniquement**
4. Génération réponse + `cite_sources`
5. `list_quarantine` + `finalize_report`
6. Affichage dashboard (réponse + citations + panneau quarantaine)

C'est l'architecture cible complète, construite progressivement — pas encore la réalité du Palier 2 (voir [Limites connues](#limites-connues)).

## Choix retenus et écartés

- **Flask plutôt que FastAPI** (app web) : un seul fichier, zéro configuration ASGI, suffisant pour une route.
- **Flask sert le build React (`frontend/dist`) plutôt que `static/index.html`** : un seul serveur pour l'expérience complète en démo. Contrepartie assumée : Node/npm redevient un prérequis du quickstart web. `static/index.html` reste dans le dépôt mais n'est plus servi par Flask — c'est le frontend minimal du socle initial, superseded, pas un fallback actif.
- **Pas de Docker** : ajoute une dépendance (le démon Docker) et du temps de build pour un bénéfice nul à ce stade ; un `venv` Python suffit.
- **Deux dépendances Python séparées (`requirements.txt` pour l'app web, `pyproject.toml` pour le moteur agentique)** : pas encore unifiées — chaque brique s'installe indépendamment pour l'instant, à consolider quand le moteur sera branché à l'app web.

## Limites connues

- L'app web et le moteur agentique de Yo ne sont **pas encore branchés ensemble** : l'app web répond via un appel LLM direct (pas d'outils, pas de corpus, pas de détection) ; le moteur agentique tourne en standalone via `scripts/test_agent.py`.
- Aucune gestion de l'historique de conversation dans l'app web (chaque message est indépendant).
- Aucune ingestion de corpus persistante, aucune quarantaine réelle — `CorpusStore`/`ReportStore` restent à construire côté backend (Kévin).
- Les fichiers déposés via le dashboard React sont stagés visuellement côté frontend uniquement ; ils ne sont pas envoyés au backend (pas de route d'ingestion à ce stade).
- Pas de tests automatisés pour l'app web à ce stade (le moteur agentique de Yo a les siens, voir `scripts/test_agent.py`).

## Documentation du projet

- [SPEC.md](SPEC.md) — problème, user stories, hors-scope, happy path, répartition du travail.
- [MENACES.md](MENACES.md) — modèle de menace, canaux d'entrée.
- [OUTILS.md](OUTILS.md) — architecture cible et signatures d'outils.
