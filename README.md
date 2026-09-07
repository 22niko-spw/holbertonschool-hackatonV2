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

## Architecture (palier 2 — socle)

```text
Frontend (static/index.html, vanilla JS)
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

Pas de base de données, pas de Docker : un seul process Python sert à la fois la page statique et la route API. Choisi pour un clone-and-run garanti en moins de 5 minutes sans dépendance supplémentaire (pas de Node/npm, pas de conteneur).

À ce stade, aucun traitement de corpus ni détection d'injection : c'est uniquement le tuyau de bout en bout (frontend → backend → LLM réel → backend → frontend). Voir [SPEC.md](SPEC.md) et [OUTILS.md](OUTILS.md) pour l'architecture cible complète, qui sera construite progressivement aux paliers suivants.

## Choix retenus / écartés

- **Flask plutôt que FastAPI** : un seul fichier, zéro configuration ASGI, suffisant pour une route.
- **Frontend statique vanilla JS plutôt que React/Vite** : aucune étape de build, aucune dépendance Node — réduit le risque d'échec du quickstart sur une machine inconnue.
- **Pas de Docker** : ajoute une dépendance (le démon Docker) et du temps de build pour un bénéfice nul à ce stade ; un `venv` Python suffit.

## Limites connues (palier 2)

- Aucune gestion de l'historique de conversation (chaque message est indépendant).
- Aucune gestion de corpus, aucune détection, aucune quarantaine — prévu aux paliers suivants.
- Pas de tests automatisés à ce stade.

## Documentation du projet

- [SPEC.md](SPEC.md) — problème, user stories, hors-scope, happy path, répartition du travail.
- [MENACES.md](MENACES.md) — modèle de menace, canaux d'entrée.
- [OUTILS.md](OUTILS.md) — architecture cible et signatures d'outils.
