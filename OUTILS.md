# OUTILS — Signatures typées (LA TAUPE)

Chaque outil est une fonction pure (sans effet de bord) sauf mention explicite. L'agent ne peut invoquer que ces outils via un schéma JSON strict validé côté backend.

| Outil | Signature | Effet de bord | Description |
|-------|-----------|---------------|-------------|
| `search_corpus` | `search_corpus(query: str, k: int, corpus_id: str) -> list[DocHit]` | Non | Recherche vectorielle (ou BM25) dans le corpus sain uniquement. Retourne les `k` passages les plus pertinents avec `doc_id`, `chunk_id`, `score`, `text`. |
| `get_doc_metadata` | `get_doc_metadata(doc_id: str) -> DocMeta` | Non | Récupère métadonnées d'un document : `doc_id`, `filename`, `status` (`clean` \| `quarantined`), `upload_ts`, `sha256`. |
| `list_quarantine` | `list_quarantine(corpus_id: str) -> list[QuarantineEntry]` | Non | Liste les documents en quarantaine pour un corpus : `doc_id`, `technique`, `excerpt`, `confidence`, `detected_at`. |
| `read_quarantine_excerpt` | `read_quarantine_excerpt(doc_id: str, chunk_id: str) -> str` | Non | Retourne l'extrait exact mis en quarantaine (pour affichage audit). Ne renvoie jamais le document complet. |
| `cite_sources` | `cite_sources(answer: str, hits: list[DocHit]) -> CitedAnswer` | Non | Attache les citations aux segments de la réponse. Retourne `answer` + `citations: list[{doc_id, chunk_id, span_start, span_end}]`. |
| `finalize_report` | `finalize_report(corpus_id: str, answer: CitedAnswer, quarantine: list[QuarantineEntry]) -> Report` | **Oui** | Écrit le rapport final en BDD (table `reports`), marque le corpus comme `processed`. Point de non-retour : déclenche l'envoi vers le frontend. |

## Types auxiliaires
```python
DocHit = {
    "doc_id": str,
    "chunk_id": str,
    "score": float,
    "text": str
}

DocMeta = {
    "doc_id": str,
    "filename": str,
    "status": "clean" | "quarantined",
    "upload_ts": str,  # ISO8601
    "sha256": str
}

QuarantineEntry = {
    "doc_id": str,
    "technique": str,          # ex: "override_direct", "role_change", "exfiltration", ...
    "excerpt": str,            # extrait déclencheur (≤ 500 chars)
    "confidence": float,       # 0.0 - 1.0
    "detected_at": str         # ISO8601
}

CitedAnswer = {
    "answer": str,
    "citations": list[{"doc_id": str, "chunk_id": str, "span_start": int, "span_end": int}]
}

Report = {
    "report_id": str,
    "corpus_id": str,
    "question": str,
    "answer": CitedAnswer,
    "quarantine": list[QuarantineEntry],
    "created_at": str
}
```

## Règles d'étanchéité
- `search_corpus` **ne cherche jamais** dans les documents quarantainés.
- `read_quarantine_excerpt` est **lecture seule** pour l'audit ; son contenu n'est jamais injecté dans le prompt de génération de réponse.
- `finalize_report` est le **seul** outil à effet de bord (écriture BDD). Tous les autres sont idempotents.