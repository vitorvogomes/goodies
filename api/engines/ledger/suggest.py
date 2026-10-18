"""Sugestão híbrida de categoria por similaridade (D).

Despesas que caem em "outros" (categorias de despesa sem match_pattern) recebem uma
sugestão: a categoria do histórico cuja descrição é mais parecida. O usuário confirma
(vira a categoria da transação) e, opcionalmente, salva um match_pattern. Função pura
e testável; não fabrica nada — só propõe com base no que já foi categorizado à mão.
"""

from __future__ import annotations

from difflib import SequenceMatcher


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def suggest_category(
    description: str,
    history: list[tuple[str, str]],
    *,
    threshold: float = 0.6,
) -> tuple[str, float] | None:
    """Categoria do histórico mais similar à descrição (ou None abaixo do threshold).

    `history` = [(descrição, categoria)] já categorizados (idealmente != "outros").
    Similaridade = SequenceMatcher sobre as descrições normalizadas (caixa/espaços).
    """
    target = _norm(description)
    if not target:
        return None
    best_cat: str | None = None
    best_score = -1.0  # garante que o 1º candidato (mesmo score 0) seja selecionado
    for desc, cat in history:
        score = SequenceMatcher(None, target, _norm(desc)).ratio()
        if score > best_score:
            best_score, best_cat = score, cat
    if best_cat is None or best_score < threshold:
        return None
    return best_cat, best_score
