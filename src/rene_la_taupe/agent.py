# Moteur agentique — René LA TAUPE (Yo)
# Palier 3 : Boucle de décision LLM avec tool use réel, traçage, gestion d'erreurs.

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic

from rene_la_taupe.prompts import SYSTEM_PROMPT
from rene_la_taupe.schemas import CitedAnswer, CostUsage, DocHit, Report
from rene_la_taupe.tools import (
    CorpusStore,
    ReportStore,
    cite_sources,
    finalize_report,
    get_doc_metadata,
    list_quarantine,
    read_quarantine_excerpt,
    search_corpus,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    model: str = "claude-haiku-4-5-20251001"
    temperature: float = 0.0
    max_search_results: int = 5
    max_tokens: int = 1500
    max_tool_turns: int = 10
    enabled_tools: list[str] | None = None  # None = tous les outils actifs


@dataclass
class ToolCallTrace:
    """Traçage d'un appel d'outil pour audit visuel."""
    turn: int
    tool_name: str
    arguments: dict
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class ToolExecutionError(Exception):
    """Erreur lors de l'exécution d'un outil (côté agent, pas LLM)."""
    def __init__(self, tool_name: str, message: str, original: Exception | None = None):
        self.tool_name = tool_name
        self.message = message
        self.original = original
        super().__init__(f"[{tool_name}] {message}")


class AgentLoopError(Exception):
    """Erreur dans la boucle d'agent (max tours, LLM error, etc.)."""
    pass


TOOL_DEFINITIONS = [
    {
        "name": "search_corpus",
        "description": "Recherche vectorielle/BM25 dans le corpus SAIN uniquement. Retourne les k passages les plus pertinents avec doc_id, chunk_id, score, text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Requête de recherche en langage naturel"},
                "k": {"type": "integer", "description": "Nombre de résultats à retourner", "minimum": 1, "maximum": 20},
                "corpus_id": {"type": "string", "description": "Identifiant du corpus"},
            },
            "required": ["query", "k", "corpus_id"],
        },
    },
    {
        "name": "get_doc_metadata",
        "description": "Récupère les métadonnées d'un document (filename, status, upload_ts, sha256).",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Identifiant du document"},
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "list_quarantine",
        "description": "Liste les documents en quarantaine pour un corpus (technique, excerpt, confidence, detected_at).",
        "input_schema": {
            "type": "object",
            "properties": {
                "corpus_id": {"type": "string", "description": "Identifiant du corpus"},
            },
            "required": ["corpus_id"],
        },
    },
    {
        "name": "read_quarantine_excerpt",
        "description": "Retourne l'extrait exact mis en quarantaine (pour affichage audit). Lecture seule, jamais injecté dans la génération.",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Identifiant du document"},
                "chunk_id": {"type": "string", "description": "Identifiant du chunk"},
            },
            "required": ["doc_id", "chunk_id"],
        },
    },
    {
        "name": "cite_sources",
        "description": "Attache les citations aux segments de la réponse. Retourne answer + citations[{doc_id, chunk_id, span_start, span_end}].",
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "Réponse en langage naturel"},
                "hits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "doc_id": {"type": "string"},
                            "chunk_id": {"type": "string"},
                            "score": {"type": "number"},
                            "text": {"type": "string"},
                        },
                        "required": ["doc_id", "chunk_id", "score", "text"],
                    },
                },
            },
            "required": ["answer", "hits"],
        },
    },
    {
        "name": "finalize_report",
        "description": "Écrit le rapport final en BDD — SEUL outil à effet de bord. Persiste réponse, citations, quarantaine, horodatage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "corpus_id": {"type": "string", "description": "Identifiant du corpus"},
                "answer": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "doc_id": {"type": "string"},
                                    "chunk_id": {"type": "string"},
                                    "span_start": {"type": "integer"},
                                    "span_end": {"type": "integer"},
                                },
                                "required": ["doc_id", "chunk_id", "span_start", "span_end"],
                            },
                        },
                    },
                    "required": ["answer", "citations"],
                },
                "quarantine": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "doc_id": {"type": "string"},
                            "technique": {"type": "string"},
                            "excerpt": {"type": "string"},
                            "confidence": {"type": "number"},
                            "detected_at": {"type": "string"},
                        },
                        "required": ["doc_id", "technique", "excerpt", "confidence", "detected_at"],
                    },
                },
            },
            "required": ["corpus_id", "answer", "quarantine"],
        },
    },
]


TOOL_IMPL: dict[str, Callable] = {
    "search_corpus": lambda args, store: search_corpus(args["query"], args["k"], args["corpus_id"], store),
    "get_doc_metadata": lambda args, store: get_doc_metadata(args["doc_id"], store),
    "list_quarantine": lambda args, store: list_quarantine(args["corpus_id"], store),
    "read_quarantine_excerpt": lambda args, store: read_quarantine_excerpt(args["doc_id"], args["chunk_id"], store),
    "cite_sources": lambda args, store: cite_sources(args["answer"], [DocHit(**h) for h in args["hits"]]),
    "finalize_report": lambda args, store: finalize_report(args["corpus_id"], CitedAnswer(**args["answer"]), [__import__("rene_la_taupe.schemas", fromlist=["QuarantineEntry"]).QuarantineEntry(**q) for q in args["quarantine"]], store),  # type: ignore[arg-type]
}


class ReneLaTaupeAgent:
    """
    Agent principal avec boucle de décision LLM (tool use).
    Orchestre : recherche → génération → citations → quarantaine → rapport final.
    """

    def __init__(
        self,
        llm_client: anthropic.Anthropic,
        corpus_store: CorpusStore,
        report_store: ReportStore,
        config: AgentConfig | None = None,
        trace_callback: Callable[[ToolCallTrace], None] | None = None,
    ):
        self.llm = llm_client
        self.corpus_store = corpus_store
        self.report_store = report_store
        self.config = config or AgentConfig()
        self.trace_callback = trace_callback
        self._traces: list[ToolCallTrace] = []
        self._usage: CostUsage = CostUsage()
        self._collected_hits: list[DocHit] = []

    def run(self, corpus_id: str, question: str) -> Report:
        """
        Exécute la boucle d'agent complète pour une question sur un corpus.
        Retourne le rapport final persisté.
        """
        logger.info(f"Démarrage agent corpus={corpus_id} question={question[:80]}")
        self._traces.clear()
        self._usage = CostUsage()
        self._collected_hits.clear()

        messages: list[dict] = [
            {"role": "user", "content": f"Corpus ID: {corpus_id}\nQuestion: {question}"}
        ]

        system_prompt = SYSTEM_PROMPT
        final_answer: str | None = None
        cited_answer: CitedAnswer | None = None
        quarantine: list = []
        loop_broken = False

        if self.config.enabled_tools is None:
            active_tools = TOOL_DEFINITIONS
        else:
            active_tools = [t for t in TOOL_DEFINITIONS if t["name"] in self.config.enabled_tools]

        for turn in range(1, self.config.max_tool_turns + 1):
            try:
                kwargs = {
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "system": system_prompt,
                    "messages": messages,
                }
                if active_tools:
                    kwargs["tools"] = active_tools
                if self.config.temperature > 0:
                    kwargs["temperature"] = self.config.temperature
                response = self.llm.messages.create(**kwargs)
            except anthropic.APIError as e:
                logger.error(f"Erreur API LLM tour {turn}: {e}")
                raise AgentLoopError(f"Erreur appel LLM: {e}") from e

            api_usage = getattr(response, "usage", None)
            if api_usage is not None:
                self._usage.input_tokens += getattr(api_usage, "input_tokens", 0) or 0
                self._usage.output_tokens += getattr(api_usage, "output_tokens", 0) or 0
            self._usage.llm_calls += 1

            # Traiter la réponse
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            text_blocks = [block for block in response.content if block.type == "text"]

            # Ajouter la réponse de l'assistant à l'historique
            messages.append({"role": "assistant", "content": response.content})

            if not tool_uses:
                # LLM a répondu sans appeler d'outil
                if text_blocks:
                    final_answer = text_blocks[0].text
                    logger.info(f"Réponse finale sans outil (tour {turn}): {final_answer[:100]}...")
                break

            # Exécuter chaque outil demandé
            tool_results = []
            for tool_use in tool_uses:
                trace = self._execute_tool(tool_use, turn, corpus_id)
                self._traces.append(trace)
                if self.trace_callback:
                    self.trace_callback(trace)

                if trace.error is not None:
                    content = [{"type": "text", "text": f"ERREUR: {trace.error}"}]
                else:
                    content = [{"type": "text", "text": json.dumps(trace.result, ensure_ascii=False)}]

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": content,
                    "is_error": trace.error is not None,
                })

            if not tool_results:
                break

            # Ajouter les résultats d'outils à l'historique
            messages.append({"role": "user", "content": tool_results})

            # Collecter les hits pour citation finale
            for tool_use, trace in zip(tool_uses, self._traces[-len(tool_results):]):
                raw = getattr(trace, '_raw_result', None)
                if tool_use.name == "search_corpus" and raw:
                    self._collected_hits.extend(raw)
                elif tool_use.name == "cite_sources" and raw:
                    cited_answer = raw
                elif tool_use.name == "list_quarantine" and raw:
                    quarantine = raw
                elif tool_use.name == "finalize_report" and raw:
                    logger.info(f"Rapport finalisé: {raw.report_id}")
                    raw.question = question
                    raw.answer.confidence = self._verified_confidence(raw.answer, self._collected_hits)
                    self._persist_question(raw.report_id, question)
                    return raw

            # Disjoncteur : 3 échecs identiques consécutifs = boucle enlisée,
            # inutile de brûler les tours restants (vu : 9× KeyError 'hits').
            recent = self._traces[-3:]
            if (
                len(recent) == 3
                and all(t.error is not None for t in recent)
                and len({(t.tool_name, t.error) for t in recent}) == 1
            ):
                logger.warning(
                    f"Disjoncteur : 3 échecs identiques "
                    f"({recent[0].tool_name}: {recent[0].error}) — arrêt de la boucle."
                )
                loop_broken = True
                break

        # Si on sort de la boucle sans finalize_report, on finalise nous-mêmes.
        # Le texte distingue les deux situations : aucune preuve trouvée VS
        # preuves trouvées mais inexploitées (disjoncteur) — affirmer « rien
        # trouvé » dans le second cas serait un mensonge (cas observé).
        if cited_answer is not None:
            cited_answer.confidence = self._verified_confidence(cited_answer, self._collected_hits)
        if cited_answer is None and final_answer:
            cited_answer = cite_sources(final_answer, self._collected_hits)
        elif cited_answer is None:
            if loop_broken and self._collected_hits:
                cited_answer = cite_sources(
                    "J'ai retrouvé des passages potentiellement pertinents dans le corpus sain, "
                    "mais je n'ai pas réussi à les exploiter pour construire une réponse citée. "
                    "Relancez la question : un nouvel essai emprunte un autre chemin.",
                    [],
                )
            else:
                cited_answer = cite_sources(
                    "Je n'ai pas trouvé d'information pertinente dans les documents sains du corpus.",
                    [],
                )

        if not quarantine:
            quarantine = list_quarantine(corpus_id, self.corpus_store)

        report = finalize_report(corpus_id, cited_answer, quarantine, self.report_store)
        report.question = question
        self._persist_question(report.report_id, question)
        logger.info(f"Rapport finalisé (fallback): {report.report_id}")
        return report

    def _persist_question(self, report_id: str, question: str) -> None:
        """Réécrit la question dans le rapport persisté (best-effort).

        finalize_report sauvegarde AVANT que l'appelant attache la question :
        sans cette réécriture, la colonne reste vide et un audit ne peut plus
        relier rapport ↔ question. Un échec ici ne doit pas invalider un
        rapport par ailleurs complet : on journalise et on continue.
        """
        try:
            self.report_store.update_question(report_id, question)
        except Exception:
            logger.warning(f"Question non persistée pour {report_id}", exc_info=True)

    @staticmethod
    def _verified_confidence(cited: CitedAnswer, hits: list[DocHit]) -> float:
        """Recalcule la confiance depuis les scores de recherche observés.

        Le LLM fournit les citations (et parfois leurs scores) : on ne le croit
        pas sur parole. Seuls les chunks retournés par search_corpus comptent ;
        un chunk cité mais jamais retrouvé vaut 0 (extrait possiblement inventé).
        """
        if not cited.citations:
            return 0.0
        observed = {(h.doc_id, h.chunk_id): h.score for h in hits}
        scores = [observed.get((c.doc_id, c.chunk_id), 0.0) for c in cited.citations]
        return min(1.0, max(0.0, sum(scores) / len(scores)))

    def _execute_tool(self, tool_use: anthropic.types.ToolUseBlock, turn: int, corpus_id: str) -> ToolCallTrace:
        """Exécute un outil avec traçage et gestion d'erreurs."""
        tool_name = tool_use.name
        args = tool_use.input
        start_time = time.perf_counter()

        if tool_name == "cite_sources" and not args.get("hits") and self._collected_hits:
            # Réparation : le LLM omet souvent le paramètre hits (KeyError 'hits'
            # en boucle jusqu'à épuisement des tours, cas observé). Le serveur
            # connaît les passages retrouvés : on les injecte au lieu d'échouer.
            args = {**args, "hits": [h.model_dump() for h in self._collected_hits]}
            logger.info(f"[TOOL REPAIR] tour={turn} tool=cite_sources hits injectés ({len(self._collected_hits)})")

        trace = ToolCallTrace(
            turn=turn,
            tool_name=tool_name,
            arguments=args,
        )

        logger.info(f"[TOOL CALL] tour={turn} tool={tool_name} args={json.dumps(args, ensure_ascii=False)}")

        try:
            impl = TOOL_IMPL.get(tool_name)
            if impl is None:
                raise ToolExecutionError(tool_name, f"Outil inconnu: {tool_name}")

            # Injecter corpus_id pour search_corpus si manquant
            if tool_name == "search_corpus" and "corpus_id" not in args:
                args = {**args, "corpus_id": corpus_id}

            result = impl(args, self.corpus_store if tool_name != "finalize_report" else self.report_store)

            # Conserver l'objet brut pour usage interne
            trace._raw_result = result

            # Convertir en types sérialisables pour le LLM
            if isinstance(result, list):
                serializable = [r.model_dump() if hasattr(r, "model_dump") else r for r in result]
            elif hasattr(result, "model_dump"):
                serializable = result.model_dump()
            else:
                serializable = result

            trace.result = serializable
            duration_ms = (time.perf_counter() - start_time) * 1000
            trace.duration_ms = duration_ms

            logger.info(f"[TOOL RESULT] tour={turn} tool={tool_name} duration_ms={duration_ms:.1f} result_type={type(serializable).__name__}")
            return trace

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            trace.duration_ms = duration_ms
            trace.error = str(e)
            logger.error(f"[TOOL ERROR] tour={turn} tool={tool_name} duration_ms={duration_ms:.1f} error={e}")
            return trace

    def get_traces(self) -> list[ToolCallTrace]:
        """Retourne la liste complète des traces d'appels d'outils."""
        return self._traces.copy()

    @property
    def last_usage(self) -> CostUsage:
        """Coût LLM du dernier run (tokens/appels, sans la durée).

        Même motif que get_traces() : la durée est mesurée par l'appelant
        (route HTTP), qui remplit duration_ms avant de répondre.
        """
        return CostUsage(
            input_tokens=self._usage.input_tokens,
            output_tokens=self._usage.output_tokens,
            llm_calls=self._usage.llm_calls,
        )


def create_test_agent() -> ReneLaTaupeAgent:
    """Crée un agent avec stores en mémoire pour tests locaux."""
    import os

    from dotenv import load_dotenv

    from rene_la_taupe.tools import InMemoryCorpusStore, InMemoryReportStore

    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY manquant dans .env")

    llm = anthropic.Anthropic(api_key=api_key)
    corpus_store = InMemoryCorpusStore()
    report_store = InMemoryReportStore()

    return ReneLaTaupeAgent(llm, corpus_store, report_store)
