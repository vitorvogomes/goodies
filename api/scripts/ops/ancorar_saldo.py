"""Âncora do saldo da conta PF e conferência encadeada (Story 3.12 — FR-5).

Lê os OFX mensais da conta PF em `files/nubank/` em **modo só-saldo**: grava o `LEDGERBAL` de cada
um em `account_balances` (sem lote) e nunca insere transação; só entram os meses que a base já
cobre (de jul/2024 — o fluxo começa ali, o OFX de jun/2024 fica de fora — até a última transação da
conta). Ancora no saldo informado mais antigo: `opening_balance` = saldo informado na âncora − Σ
transações até essa data. Idempotente; com backup antes. Rodar de novo recalcula a âncora (útil se
chegarem transações anteriores a ela ou se o lote da âncora for desfeito).

Uso (a partir de api/):
    uv run python -m scripts.ops.ancorar_saldo --relatorio   # só calcula e lista os divergentes
    uv run python -m scripts.ops.ancorar_saldo               # backup + grava saldos e âncora
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import asyncpg

from config import settings
from engines.ledger import queries
from engines.ledger.calc import BalanceInterval, chained_check, opening_balance
from engines.ledger.importer import parse_account_number, parse_ledger_balance
from workers.backup import make_pre_migration_backup
from workers.dbops import API_DIR

FLOW_START = date(2024, 7, 1)
FILES_DIR = API_DIR.parent / "files" / "nubank"


@dataclass
class AnchorReport:
    balances: list[tuple[date, Decimal]] = field(default_factory=list)
    anchor: tuple[date, Decimal] | None = None
    opening: Decimal | None = None
    intervals: list[BalanceInterval] = field(default_factory=list)

    @property
    def divergent(self) -> list[BalanceInterval]:
        return [i for i in self.intervals if not i.ok]


def read_balances(
    files: list[Path], account_number: str, until: date
) -> list[tuple[date, Decimal]]:
    """`LEDGERBAL` dos OFX da conta, de jul/2024 até `until` (um por data)."""
    found: dict[date, Decimal] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if parse_account_number(text) != account_number:
            continue
        balance = parse_ledger_balance(text)
        if balance is None:
            continue
        amount, as_of = balance
        if FLOW_START <= as_of <= until:
            found[as_of] = amount
    return sorted(found.items())


async def anchor(conn: asyncpg.Connection, files: list[Path], *, write: bool) -> AnchorReport:
    report = AnchorReport()
    account = await conn.fetchrow(queries.PF_ACCOUNT)
    if account is None or not account["account_number"]:
        return report
    movements = [
        (r["date"], r["amount"]) for r in await conn.fetch(queries.ACCOUNT_MOVEMENTS, account["id"])
    ]
    if not movements:
        return report
    report.balances = read_balances(files, account["account_number"], movements[-1][0])
    stored = {
        r["as_of"]: r["balance"]
        for r in await conn.fetch(queries.REPORTED_BALANCES, account["id"])
        if r["as_of"] >= FLOW_START
    }
    reported = sorted({**stored, **dict(report.balances)}.items())
    if not reported:
        return report
    report.anchor = reported[0]
    report.opening = opening_balance(report.anchor[1], report.anchor[0], movements)
    report.intervals = chained_check(reported, movements)
    if write:
        async with conn.transaction():
            for as_of, amount in report.balances:
                await conn.execute(
                    "INSERT INTO account_balances (account_id, as_of, balance) VALUES ($1, $2, $3) "
                    "ON CONFLICT (account_id, as_of) DO NOTHING",
                    account["id"],
                    as_of,
                    amount,
                )
            await conn.execute(
                "UPDATE accounts SET opening_balance = $2, opening_balance_date = $3 WHERE id = $1",
                account["id"],
                report.opening,
                report.anchor[0],
            )
    return report


async def _run(write: bool) -> AnchorReport:
    if write:
        await make_pre_migration_backup(settings.database_url, "pre-ancorar-saldo")
    conn = await asyncpg.connect(settings.database_url)
    try:
        return await anchor(conn, sorted(FILES_DIR.rglob("*.ofx")), write=write)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relatorio", action="store_true", help="só calcula, não grava")
    args = parser.parse_args()
    report = asyncio.run(_run(write=not args.relatorio))
    if report.anchor is None:
        print("sem conta PF, transações ou saldo informado: nada a ancorar")
        return
    print(f"âncora: {report.anchor[0]:%d/%m/%Y} | saldos informados: {len(report.intervals) + 1}")
    print(f"intervalos: {len(report.intervals)} | divergentes: {len(report.divergent)}")
    for i in report.divergent:
        print(f"  {i.start:%d/%m/%Y} a {i.end:%d/%m/%Y}: diferença R$ {i.difference}")
    if args.relatorio:
        print("(relatório: nada gravado)")


if __name__ == "__main__":
    main()
