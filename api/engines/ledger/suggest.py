"""Sugestão de categoria por similaridade da descrição (Story 3.6 — FR-9).

Toda transação nova sem regra recebe a categoria da transação **confirmada** mais parecida, de
qualquer tipo (receita, gasto, investimento ou transferência) e com o mesmo sinal: Jaccard dos
tokens da descrição normalizada (minúscula, sem acento, sem números) ≥ 0,6; empate → a mais recente.
Sem histórico parecido, fica em "Entrada/Saída a classificar" ("sem sugestão"). Funções puras.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

THRESHOLD = 0.6
_WORD = re.compile(r"[a-z]+")


def tokens(description: str) -> frozenset[str]:
    plain = unicodedata.normalize("NFKD", description.lower())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return frozenset(_WORD.findall(plain))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class HistoryItem:
    tokens: frozenset[str]
    category_id: str
    positive: bool  # sinal do valor: entrada × saída


@dataclass(frozen=True)
class Suggestion:
    category_id: str
    score: float


def best_suggestion(
    description: str,
    amount: Decimal,
    history: Sequence[HistoryItem],
    *,
    threshold: float = THRESHOLD,
) -> Suggestion | None:
    """`history` vem da mais recente para a mais antiga: no empate fica a primeira (a recente)."""
    target = tokens(description)
    if not target:
        return None
    positive = amount > 0
    best: Suggestion | None = None
    for item in history:
        if item.positive != positive:
            continue
        score = jaccard(target, item.tokens)
        if score >= threshold and (best is None or score > best.score):
            best = Suggestion(item.category_id, score)
    return best


def suggest_category(
    description: str,
    history: list[tuple[str, str]],
    *,
    threshold: float = THRESHOLD,
) -> tuple[str, float] | None:
    """Tela v1 de sugestões: categoria do histórico `[(descrição, categoria)]` mais parecida."""
    target = tokens(description)
    if not target:
        return None
    best: tuple[str, float] | None = None
    for desc, cat in history:
        score = jaccard(target, tokens(desc))
        if best is None or score > best[1]:
            best = (cat, score)
    if best is None or best[1] < threshold:
        return None
    return best
