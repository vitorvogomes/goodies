"""Termos do orçamento do mês (Story 6.5 — AD-7): funções puras, uma por termo.

- disponível ("Livre para gastos" na tela) = trabalho + resgates − custos fixos − aporte planejado −
  dívidas do mês
- restante ("Sobra do mês") = disponível − consumido; restante sem os resgates = restante − resgates
- consumo financiado por resgate = mín(resgates, máx(0, consumido − disponível sem resgates))
- custos fixos do mês: pago → o valor pago; pendente → o cadastrado
- dívidas do mês: o informado; sem valor, o pré-preenchido (Σ role `divida` não casada)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from engines.common.shares import pcts

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
# Fluxo do mês (v2.2 — Painel): para onde foram as entradas, em fatias que somam 100%
# --------------------------------------------------------------------------------------------

_FLOW_LABELS = {
    "custos_fixos": "Custos fixos",
    "aporte": "Aporte planejado",
    "dividas": "Dívidas",
    "gastos": "Gastos do mês",
    "sobra": "Sobra",
}


@dataclass(frozen=True)
class FlowPart:
    key: str
    label: str
    value: Decimal
    pct: Decimal  # % da barra (2 casas; as fatias somam 100)


@dataclass(frozen=True)
class MonthFlow:
    entradas: Decimal  # trabalho + resgates
    sobra: Decimal  # o restante do orçamento: > 0 sobra, < 0 falta
    parts: list[FlowPart]
    # onde as entradas acabam na barra (100 quando sobra; < 100 quando as saídas passaram)
    limite_pct: Decimal | None


def month_flow(b: Budget) -> MonthFlow:
    """A barra do fluxo do mês a partir dos termos do orçamento (`flow_terms`)."""
    return flow_terms(
        trabalho=b.trabalho,
        resgates=b.resgates_considerados,
        custos_fixos=b.custos_fixos,
        aporte=b.aporte_planejado,
        dividas=b.dividas,
        consumido=b.consumido,
        restante=b.restante,
    )


def flow_terms(
    *,
    trabalho: Decimal,
    resgates: Decimal,
    custos_fixos: Decimal,
    aporte: Decimal,
    dividas: Decimal,
    consumido: Decimal,
    restante: Decimal,
) -> MonthFlow:
    """custos fixos | aporte planejado | dívidas | gastos | sobra. Com sobra, a base é o que
    entrou; com falta, a base é o que saiu e `limite_pct` marca onde as entradas acabaram. Termo
    negativo (ex.: devoluções acima dos gastos) fica fora da barra. Nenhuma conta nova: sobra =
    restante — também num mês fechado, pelos termos congelados."""
    entradas = trabalho + resgates
    saidas = [
        ("custos_fixos", custos_fixos),
        ("aporte", aporte),
        ("dividas", dividas),
        ("gastos", consumido),
    ]
    if restante > 0:
        saidas.append(("sobra", restante))
    items = [(k, v) for k, v in saidas if v > 0]
    base = sum((v for _, v in items), Decimal(0))
    if base <= 0:
        return MonthFlow(entradas, restante, [], None)
    shares = pcts([v for _, v in items])
    # sem falta, as entradas cobrem a barra inteira (mesmo com um termo negativo fora dela)
    limite = (
        _HUNDRED
        if restante >= 0
        else min(entradas / base * _HUNDRED, _HUNDRED).quantize(Decimal("0.01"))
    )
    return MonthFlow(
        entradas=entradas,
        sobra=restante,
        parts=[FlowPart(k, _FLOW_LABELS[k], v, p) for (k, v), p in zip(items, shares, strict=True)],
        limite_pct=limite.quantize(Decimal("0.01")),
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
