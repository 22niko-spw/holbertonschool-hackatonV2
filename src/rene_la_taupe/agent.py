# Moteur agentique — René LA TAUPE (Yo)
# Boucle de décision LLM avec outils typés et étanchéité données/instructions.

from __future__ import annotations

import logging
from dataclasses import dataclass

import anthropic

from rene_la_taupe.prompts import ANSWER_GENERATION_PROMPT, SYSTEM_PROMPT
from rene_la_taupe.schemas import CitedAnswer, DocHit, Report
from rene_la_taupe.tools import (
    CorpusStore,
    ReportStore,
    cite_sources,
    finalize_report,
    list_quarantine,
    search_corpus,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    model: str = "claude-haiku-4-5-20251001"
    temperature: float = 0.0
    max_search_results: int = 5
    max_tokens: int = 1500


class ReneLaTaupeAgent:
    """
    Agent principal qui orchestre :
    1. Recherche dans le corpus sain
    2. Génération de réponse citée
    3. Récupération quarantaine
    4. Finalisation rapport
    """

    def __init__(
        self,
        llm_client: anthropic.Anthropic,
        corpus_store: CorpusStore,
        report_store: ReportStore,
        config: AgentConfig | None = None,
    ):
        self.llm = llm_client
        self.corpus_store = corpus_store
        self.report_store = report_store
        self.config = config or AgentConfig()

    def run(self, corpus_id: str, question: str) -> Report:
        """
        Exécute le happy path complet pour une question sur un corpus.
        Retourne le rapport final persisté.
        """
        logger.info(f"Démarrage agent corpus={corpus_id} question={question[:80]}")

        # 1. Recherche dans le corpus SAIN uniquement
        hits = search_corpus(question, self.config.max_search_results, corpus_id, self.corpus_store)
        logger.info(f"Recherche: {len(hits)} hits trouvés")

        # 2. Génération de la réponse basée UNIQUEMENT sur les hits
        if not hits:
            answer_text = "Je n'ai pas trouvé d'information pertinente dans les documents sains du corpus."
            cited_answer = CitedAnswer(answer=answer_text, citations=[])
        else:
            answer_text = self._generate_answer(question, hits)
            cited_answer = cite_sources(answer_text, hits)

        # 3. Récupération de la quarantaine pour le rapport
        quarantine = list_quarantine(corpus_id, self.corpus_store)
        logger.info(f"Quarantaine: {len(quarantine)} entrées")

        # 4. Finalisation du rapport (SEUL effet de bord)
        report = finalize_report(corpus_id, cited_answer, quarantine, self.report_store)
        report.question = question  # compléter la question
        logger.info(f"Rapport finalisé: {report.report_id}")

        return report

    def _generate_answer(self, question: str, hits: list[DocHit]) -> str:
        """Génère la réponse en langage naturel basée sur les hits."""
        hits_text = "\n\n".join(
            f"[DOC:{h.doc_id} CHUNK:{h.chunk_id}] {h.text}"
            for h in hits
        )

        response = self.llm.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": ANSWER_GENERATION_PROMPT.format(
                    question=question,
                    hits=hits_text,
                )}
            ],
        )
        # Anthropic response: content is a list of blocks, extract text from TextBlock
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        return "".join(text_parts).strip()


# ─── Fonction helper pour test standalone ───

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
