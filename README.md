# LA TAUPE

Agent capable d'analyser un corpus de documents dont certains peuvent contenir des tentatives d'injection de prompt. Voir [SPEC.md](SPEC.md) pour le cadrage complet et [MENACES.md](MENACES.md) pour le modèle de menace.

## Quickstart (< 5 min)

Prérequis : Python 3.10+, Node.js 18+, une clé API Anthropic.

```bash
git clone https://github.com/22niko-spw/holbertonschool-hackatonV2.git
cd holbertonschool-hackatonV2

cp .env.example .env
# éditer .env et coller votre ANTHROPIC_API_KEY

cd frontend && npm install && npm run build && cd ..

python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt

python app.py
```

Ouvrir [http://localhost:8000](http://localhost:8000), écrire un message, cliquer sur "Envoyer" : la réponse vient d'un vrai appel au modèle Claude, pas d'un mock. Flask sert directement le build React (`frontend/dist`) — un seul serveur à lancer.

## Développer le frontend (hot reload)

Pour itérer sur l'UI sans rebuilder à chaque changement, lancer le backend et le frontend séparément :

```bash
# terminal 1 — backend
python app.py                 # :8000

# terminal 2 — frontend en mode dev
cd frontend && npm run dev    # :5000, proxy /api vers :8000
```

Ouvrir [http://localhost:5000](http://localhost:5000) pendant le développement ; retourner sur `npm run build` avant de committer pour que `http://localhost:8000` serve la version à jour.

## Architecture (palier 2 — socle)

```text
Frontend (frontend/dist, build React — servi par Flask)
    │  fetch POST /api/ask
    ▼
Backend Flask (app.py)
    │  clé API lue côté serveur uniquement (.env)
    ▼
API Anthropic (appel réel)
    │
    ▼
Backend → Frontend (réponse affichée)
```

Un seul process Python sert à la fois le frontend buildé et la route API — pas de base de données, pas de Docker.

À ce stade, aucun traitement de corpus ni détection d'injection : c'est uniquement le tuyau de bout en bout (frontend → backend → LLM réel → backend → frontend). Voir [SPEC.md](SPEC.md) et [OUTILS.md](OUTILS.md) pour l'architecture cible complète, qui sera construite progressivement aux paliers suivants.

## Choix retenus / écartés

- **Flask plutôt que FastAPI** : un seul fichier, zéro configuration ASGI, suffisant pour une route.
- **Flask sert le build React (`frontend/dist`) plutôt que `static/index.html`** : un seul serveur pour l'expérience complète en démo. Contrepartie assumée : Node/npm redevient un prérequis du quickstart (`npm run build` avant `python app.py`), alors que le socle initial de Kévin visait à l'éviter. `static/index.html` reste dans le dépôt mais n'est plus servi par Flask — c'est le frontend minimal du socle initial, superseded, pas un fallback actif.
- **Pas de Docker** : ajoute une dépendance (le démon Docker) et du temps de build pour un bénéfice nul à ce stade ; un `venv` Python suffit.

## Limites connues (palier 2)

- Aucune gestion de l'historique de conversation (chaque message est indépendant).
- Aucune gestion de corpus, aucune détection, aucune quarantaine — prévu aux paliers suivants.
- Pas de tests automatisés à ce stade.

## Documentation du projet

- [SPEC.md](SPEC.md) — problème, user stories, hors-scope, happy path, répartition du travail.
- [MENACES.md](MENACES.md) — modèle de menace, canaux d'entrée.
- [OUTILS.md](OUTILS.md) — architecture cible et signatures d'outils.
