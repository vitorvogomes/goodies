"""Caixa em corretora e dinheiro a caminho (Story 7.7 — FR-4, FR-25): por trilho de corretora
(`transit.RAILS`), o resíduo saiu + proventos − aplicado numa data, separado por `calc.broker_split`
em caixa (no patrimônio) e a caminho (fora, até o relatório cobrir a transferência).

Quem diz até quando a corretora está "vista": B3 e Tesouro pelo relatório B3 importado (o
"atualizado até" das fontes B3 no `ingest`); caixinhas/CDB e debêntures nascem da própria transação
(derivação), então estão sempre cobertas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import asyncpg

from engines.common.alerts import Alert, AlertAction, AlertContext, brl, fingerprint
from engines.common.dates import today_brt
from engines.ingest import service as ingest_service
from engines.ledger import queries as ledger_queries

from . import calc
from .transit import RAILS, Rail

# Nome curto da corretora nas mensagens ("a caminho da B3").
BROKER_NAME = {
    "B3 (corretoras)": "B3",
    "Tesouro Direto": "Tesouro Direto",
    "Renda Fixa Nubank": "Renda Fixa Nubank",
    "Debêntures Flash": "Flash",
}
_REPORTED_BY_B3 = {"B3 (corretoras)", "Tesouro Direto"}
_B3_SOURCES = ("b3_movimentacao", "b3_negociacao")
DIVERGENCE_TOLERANCE = Decimal("1.00")


class FutureCheckError(ValueError):
    """Saldo informado com data depois de hoje."""


@dataclass(frozen=True)
class BrokerCash:
    rail: str
    name: str
    saiu: Decimal
    proventos: Decimal
    aplicado: Decimal
    caixa: Decimal  # no patrimônio
    a_caminho: Decimal  # fora do patrimônio
    covered_until: date | None  # o relatório da corretora cobre até
    informed: Decimal | None = None  # "Saldo que vejo na corretora" (o mais recente até a data)
    informed_at: date | None = None
    caixa_at_check: Decimal | None = None  # o caixa calculado na data do saldo informado

    @property
    def import_from(self) -> date | None:
        """A partir de quando importar o relatório para a transferência sair de "a caminho"."""
        return self.covered_until + timedelta(days=1) if self.covered_until else None

    @property
    def divergent(self) -> bool:
        if self.informed is None or self.caixa_at_check is None:
            return False
        return abs(self.caixa_at_check - self.informed) > DIVERGENCE_TOLERANCE


async def _b3_covered(conn: asyncpg.Connection) -> date | None:
    rows = await ingest_service.sources(conn, today_brt(), with_balances=False)
    dates = [s.updated_until for s in rows if s.key in _B3_SOURCES and s.updated_until]
    return max(dates) if dates else None


async def _rail_transactions(conn: asyncpg.Connection, rail: Rail) -> list[asyncpg.Record]:
    """Saídas e resgates do trilho (o par investimento ↔ resgate, pelas chaves do ledger)."""
    categories = list(rail.ledger_keys)
    rows: list[asyncpg.Record] = await ledger_queries.transactions_by_category_keys(
        conn, categories, with_pairs=True
    )
    return rows


async def _rail_ops(
    conn: asyncpg.Connection, owner: str, rail: Rail, as_of: date
) -> tuple[Decimal, Decimal]:
    rows = await conn.fetch(
        "SELECT tipo, quantidade, valor_unitario FROM asset_operations WHERE user_id = $1 "
        "AND asset_category = ANY($2::text[]) AND data_operacao <= $3 "
        "AND ($4::text[] IS NULL OR broker = ANY($4::text[]))",
        owner,
        list(rail.asset_categories),
        as_of,
        list(rail.asset_brokers) if rail.asset_brokers is not None else None,
    )
    return calc.net_contributed(rows), calc.income_received(rows)


async def _rail_cash(
    conn: asyncpg.Connection,
    owner: str,
    rail: Rail,
    rail_rows: list[asyncpg.Record],
    as_of: date,
    b3_until: date | None,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, date | None]:
    """(saiu, proventos, aplicado, caixa, a caminho, coberto até) do trilho numa data."""
    txs = [r for r in rail_rows if r["date"] <= as_of]
    saiu = -sum((r["amount"] for r in txs), Decimal(0))
    aplicado, proventos = await _rail_ops(conn, owner, rail, as_of)
    residual = saiu + proventos - aplicado
    covered = (
        min(b3_until, as_of)
        if rail.name in _REPORTED_BY_B3 and b3_until
        else (None if rail.name in _REPORTED_BY_B3 else as_of)
    )
    transfers = [(r["date"], -r["amount"]) for r in txs if r["amount"] < 0]
    caixa, a_caminho = calc.broker_split(residual, transfers, covered)
    return saiu, proventos, aplicado, caixa, a_caminho, covered


async def broker_cash_as_of(conn: asyncpg.Connection, owner: str, as_of: date) -> list[BrokerCash]:
    b3_until = await _b3_covered(conn)
    out: list[BrokerCash] = []
    for rail in RAILS:
        rail_rows = await _rail_transactions(conn, rail)
        saiu, proventos, aplicado, caixa, a_caminho, covered = await _rail_cash(
            conn, owner, rail, rail_rows, as_of, b3_until
        )
        check = await conn.fetchrow(
            "SELECT as_of, balance FROM broker_cash_checks WHERE rail = $1 AND as_of <= $2 "
            "ORDER BY as_of DESC LIMIT 1",
            rail.name,
            as_of,
        )
        caixa_at_check: Decimal | None = None
        if check is not None:  # o saldo visto em D se compara com o caixa calculado em D
            caixa_at_check = (
                caixa
                if check["as_of"] == as_of
                else (await _rail_cash(conn, owner, rail, rail_rows, check["as_of"], b3_until))[3]
            ).quantize(Decimal("0.01"))
        out.append(
            BrokerCash(
                rail=rail.name,
                name=BROKER_NAME.get(rail.name, rail.name),
                saiu=saiu.quantize(Decimal("0.01")),
                proventos=proventos.quantize(Decimal("0.01")),
                aplicado=aplicado.quantize(Decimal("0.01")),
                caixa=caixa.quantize(Decimal("0.01")),
                a_caminho=a_caminho.quantize(Decimal("0.01")),
                covered_until=covered,
                informed=check["balance"] if check else None,
                informed_at=check["as_of"] if check else None,
                caixa_at_check=caixa_at_check,
            )
        )
    return out


async def save_check(conn: asyncpg.Connection, rail: str, as_of: date, balance: Decimal) -> None:
    if rail not in {r.name for r in RAILS}:
        raise ValueError(rail)
    if as_of > today_brt():
        raise FutureCheckError(as_of)
    await conn.execute(
        "INSERT INTO broker_cash_checks (rail, as_of, balance) VALUES ($1, $2, $3) "
        "ON CONFLICT (rail, as_of) DO UPDATE SET balance = EXCLUDED.balance, created_at = now()",
        rail,
        as_of,
        balance,
    )


# --------------------------------------------------------------------------------------------
# Avisos (AD-10) — registrados em main.py
# --------------------------------------------------------------------------------------------


async def broker_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """ "R$ x a caminho da {corretora}. Importe o relatório B3 a partir de dd/mm/aaaa." (Importar) e
    "Caixa na {corretora}: calculado R$ a, informado R$ b." (diferença acima de R$ 1,00)."""
    out: list[Alert] = []
    for b in await broker_cash_as_of(conn, ctx.owner_id, ctx.today):
        if b.a_caminho > 0:
            since = f" a partir de {b.import_from:%d/%m/%Y}" if b.import_from else ""
            out.append(
                Alert(
                    key=f"a_caminho:{b.rail}",
                    fingerprint=fingerprint(b.a_caminho, b.covered_until),
                    severity="aviso",
                    message=f"{brl(b.a_caminho)} a caminho da {b.name}. Importe o relatório B3"
                    f"{since}.",
                    action=AlertAction(
                        label="Importar", route="/visao-geral/painel", params={"importar": "1"}
                    ),
                    as_of=ctx.today,
                )
            )
        if b.divergent and b.informed is not None:
            out.append(
                Alert(
                    key=f"caixa_divergente:{b.rail}",
                    fingerprint=fingerprint(b.caixa_at_check, b.informed, b.informed_at),
                    severity="divergencia",
                    message=f"Caixa na {b.name}: calculado {brl(b.caixa_at_check or b.caixa)}, "
                    f"informado {brl(b.informed)}.",
                    action=AlertAction(label="Ver conciliação", route="/investimentos/conciliacao"),
                    as_of=b.informed_at,
                )
            )
    return out
