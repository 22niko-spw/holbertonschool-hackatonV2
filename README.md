# René LA TAUPE — Palier 2 (Yo: Moteur Agentique & Sécurité)

## Quickstart (≤ 5 min)

```bash
# 1. Cloner
git clone https://github.com/22niko-spw/holbertonschool-hackatonV2.git
cd holbertonschool-hackatonV2

# 2. Créer venv + installer
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Configurer .env
cp .env.example .env
# Éditer .env et mettre votre ANTHROPIC_API_KEY

# 4. Tester le détecteur d'injection
python -m scripts.test_agent detection

# 5. Tester l'agent complet (happy path)
python -m scripts.test_agent agent --question "Quels sont les risques chimiques ?"
```

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

- `ANTHROPIC_API_KEY` dans `.env` (obligatoire)
- Backend (Kévin) : fournira `CorpusStore` et `ReportStore` persistants
- Frontend (Niko) : appellera l'API qui utilise `ReneLaTaupeAgent`

## Happy Path (6 étapes)

1. Upload corpus + question
2. Ingestion & criblage (détection → quarantaine)
3. `search_corpus` sur documents **clean uniquement**
4. Génération réponse + `cite_sources`
5. `list_quarantine` + `finalize_report`
6. Affichage dashboard (réponse + citations + panneau quarantaine)
