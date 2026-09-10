# Suivi du coût des appels Anthropic — René LA TAUPE (Kévin) — Palier 5
#
# Le client Anthropic est instrumenté une seule fois au démarrage (voir
# instrument_client). Tous les appels passant par ce client sont comptés,
# qu'ils viennent de app.py, de l'agent (Yo) ou du détecteur (Yo) — sans
# toucher à leur code : on n'intercepte que la méthode `messages.create` de
# l'instance de client qu'on leur fournit.

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

# Tarifs Anthropic (USD / million de tokens). Le préfixe suffit : les IDs de
# modèle portent une date ("claude-haiku-4-5-20251001") qu'on ignore.
_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-fable-5-1": (10.00, 50.00),
}
# Tarif appliqué quand le modèle n'est pas reconnu : celui du modèle par
# défaut du projet, pour ne jamais afficher un coût à zéro par erreur.
_FALLBACK_PRICING = _PRICING_PER_MTOK["claude-haiku-4-5"]


def _pricing_for(model: str) -> tuple[float, float]:
    for prefix, prices in _PRICING_PER_MTOK.items():
        if model.startswith(prefix):
            return prices
    return _FALLBACK_PRICING


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = _pricing_for(model)
    return (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price


@dataclass
class CallUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class _Accumulator:
    calls: list[CallUsage] = field(default_factory=list)


_current: ContextVar[_Accumulator | None] = ContextVar("cost_tracking_accumulator", default=None)


def start_tracking() -> None:
    """À appeler en début de requête pour repartir d'un compteur vide."""
    _current.set(_Accumulator())


def get_usage() -> dict[str, Any]:
    """Résumé du coût accumulé depuis le dernier start_tracking()."""
    acc = _current.get()
    calls = acc.calls if acc else []
    return {
        "calls": len(calls),
        "input_tokens": sum(c.input_tokens for c in calls),
        "output_tokens": sum(c.output_tokens for c in calls),
        "cost_usd": round(sum(c.cost_usd for c in calls), 6),
    }


def _record(model: str, input_tokens: int, output_tokens: int) -> None:
    acc = _current.get()
    if acc is None:
        return
    acc.calls.append(
        CallUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=compute_cost_usd(model, input_tokens, output_tokens),
        )
    )


def instrument_client(client: Any) -> Any:
    """
    Enveloppe `client.messages.create` pour comptabiliser chaque appel sans
    modifier le code appelant (agent.py, detection/__init__.py). Idempotent :
    rappeler sur un client déjà instrumenté ne double pas le comptage.
    """
    original_create = client.messages.create
    if getattr(original_create, "_cost_tracking_wrapped", False):
        return client

    def wrapped_create(*args: Any, **kwargs: Any) -> Any:
        response = original_create(*args, **kwargs)
        usage = getattr(response, "usage", None)
        if usage is not None:
            _record(
                model=getattr(response, "model", kwargs.get("model", "unknown")),
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
            )
        return response

    wrapped_create._cost_tracking_wrapped = True  # type: ignore[attr-defined]
    client.messages.create = wrapped_create
    return client
