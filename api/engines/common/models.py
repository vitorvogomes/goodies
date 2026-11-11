"""Modelos compartilhados do contrato HTTP (AD-15 — Story 2.1)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator


def _canonical_uuid(value: object) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise ValueError("identificador inválido") from None


# Id de entrada (corpo ou caminho): malformado vira 422 na validação, não DataError → 500.
Uuid = Annotated[str, BeforeValidator(_canonical_uuid)]

# Motivos canônicos de "sem valor" (AD-15); novos motivos entram aqui, nunca texto livre.
UnavailableReason = Literal[
    "nao_definido",
    "aguardando_ipca",
    "antes_do_primeiro_fechamento",
    "sem_preco",
    "sem_metas",
    "sem_receita",
    "fora_do_resumo",
]


class Valued[T](BaseModel):
    """Termo de dinheiro ou total de painel: `value` null quando não há dado, com o motivo."""

    value: T | None = None
    unavailable_reason: UnavailableReason | None = None
    as_of: date | None = None
    source: str | None = None
    stale: bool = False
    # Valor com um insumo estimado (ex.: o IPCA do mês ainda não saiu e vale o último publicado).
    estimated: bool = False
