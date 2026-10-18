"""Termos do orçamento do mês (Story 6.5 — AD-7): funções puras, uma por termo.

- disponível para consumo = trabalho + resgates − custos fixos − aporte planejado − dívidas do mês
- restante = disponível − consumido; restante sem os resgates = restante − resgates
- consumo financiado por resgate = mín(resgates, máx(0, consumido − disponível sem resgates))
- custos fixos do mês: pago → o valor pago; pendente → o cadastrado
- dívidas do mês: o informado; sem valor, o pré-preenchido (Σ role `divida` não casada)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

_HUNDRED = Decimal(100)


def custos_fixos_do_mes(items: Sequence[tuple[Decimal, Decimal | None]]) -> Decimal:
    """`items` = (valor cadastrado, valor pago ou None)."""
    return sum((paid if paid is not None else registered for registered, paid in items), Decimal(0))


def disponivel(
    trabalho: Decimal,
    resgates: Decimal,
    custos_fixos: Decimal,
    aporte_planejado: Decimal | None,
    dividas: Decimal,
) -> Decimal:
    return trabalho + resgates - custos_fixos - (aporte_planejado or Decimal(0)) - dividas


def restante(disponivel_: Decimal, consumido: Decimal) -> Decimal:
    return disponivel_ - consumido


def restante_sem_resgates(restante_: Decimal, resgates: Decimal) -> Decimal:
    return restante_ - resgates


def consumo_financiado(resgates: Decimal, consumido: Decimal, disponivel_: Decimal) -> Decimal:
    return min(resgates, max(Decimal(0), consumido - (disponivel_ - resgates)))


def financiado_split(financiado: Decimal, resgates_objetivo: Decimal) -> tuple[Decimal, Decimal]:
    """Story 8.1: o consumo financiado por resgate, (por objetivo, por resgate da carteira). O
    resgate de ativo vinculado a objetivo cobre primeiro (é dinheiro guardado para gastar); o resto
    é a carteira."""
    por_objetivo = min(financiado, resgates_objetivo)
    return por_objetivo, financiado - por_objetivo


@dataclass(frozen=True)
class BudgetInput:
    trabalho: Decimal
    resgates: Decimal
    custos_fixos: Decimal
    aporte_planejado: Decimal | None  # None = não definido (conta como 0)
    dividas_informadas: Decimal | None  # None = não informado → pré-preenchido
    dividas_prefill: Decimal
    consumido: Decimal


@dataclass(frozen=True)
class Budget:
    trabalho: Decimal
    resgates_considerados: Decimal
    custos_fixos: Decimal
    aporte_planejado: Decimal
    aporte_definido: bool
    dividas: Decimal
    dividas_informadas: bool
    disponivel: Decimal
    consumido: Decimal
    restante: Decimal
    consumo_financiado: Decimal
    restante_sem_resgates: Decimal


def budget(i: BudgetInput) -> Budget:
    dividas = i.dividas_informadas if i.dividas_informadas is not None else i.dividas_prefill
    disp = disponivel(i.trabalho, i.resgates, i.custos_fixos, i.aporte_planejado, dividas)
    rest = restante(disp, i.consumido)
    return Budget(
        trabalho=i.trabalho,
        resgates_considerados=i.resgates,
        custos_fixos=i.custos_fixos,
        aporte_planejado=i.aporte_planejado or Decimal(0),
        aporte_definido=i.aporte_planejado is not None,
        dividas=dividas,
        dividas_informadas=i.dividas_informadas is not None,
        disponivel=disp,
        consumido=i.consumido,
        restante=rest,
        consumo_financiado=consumo_financiado(i.resgates, i.consumido, disp),
        restante_sem_resgates=restante_sem_resgates(rest, i.resgates),
    )


# --------------------------------------------------------------------------------------------
# Alocação × meta (Story 8.3 — AD-11): % na base, meta, desvio em p.p.
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Share:
    atual: Decimal  # % na base
    meta: Decimal | None
    desvio: Decimal | None  # atual − meta, em p.p.


def allocation_shares(values: dict[str, Decimal], targets: dict[str, Decimal]) -> dict[str, Share]:
    """Cada item: o % do valor na base (soma dos valores) × a meta; sem meta, sem desvio."""
    total = sum(values.values(), Decimal(0))
    out: dict[str, Share] = {}
    for key in [*values, *(k for k in targets if k not in values)]:
        atual = values.get(key, Decimal(0)) / total * _HUNDRED if total > 0 else Decimal(0)
        meta = targets.get(key)
        out[key] = Share(atual, meta, atual - meta if meta is not None else None)
    return out


def out_of_band(desvio: Decimal | None, banda: Decimal | None) -> bool:
    return desvio is not None and banda is not None and abs(desvio) > banda


# --------------------------------------------------------------------------------------------
# Andamento do aporte (Story 8.7 — FR-31, AR20)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Progress:
    planned: Decimal
    realizado: Decimal  # realizado total: o investimento do mês (ledger), com o a caminho
    em_ativo: Decimal  # Σ do realizado das linhas: só o que já virou ativo
    a_caminho: Decimal  # realizado − em ativo (saiu da conta, ainda sem classe)
    pendente: Decimal  # planejado − realizado (nunca negativo)
    lines: dict[
        str, tuple[Decimal, Decimal]
    ]  # linha → (realizado, pendente = sugerido − realizado)


def aporte_progress(
    planned: Decimal,
    realizado: Decimal,
    sugerido: dict[str, Decimal],
    line_realizado: dict[str, Decimal],
) -> Progress:
    """Σ pendente das linhas = pendente total + a caminho (o golden dos mockups): o realizado por
    linha só conta o que virou ativo; o que saiu e ainda não tem classe é o a caminho."""
    em_ativo = sum(line_realizado.values(), Decimal(0))
    lines = {
        k: (
            line_realizado.get(k, Decimal(0)),
            sugerido.get(k, Decimal(0)) - line_realizado.get(k, Decimal(0)),
        )
        for k in [*sugerido, *(k for k in line_realizado if k not in sugerido)]
    }
    return Progress(
        planned=planned,
        realizado=realizado,
        em_ativo=em_ativo,
        a_caminho=max(Decimal(0), realizado - em_ativo),
        pendente=max(Decimal(0), planned - realizado),
        lines=lines,
    )
