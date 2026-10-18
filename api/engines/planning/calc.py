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
