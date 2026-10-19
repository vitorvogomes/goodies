"""Adapter do extrato Nubank (OFX e CSV) no protocolo `SourceAdapter` (AD-5 — Stories 3.3 e 3.4).

OFX: a conta vem do `ACCTID` do próprio arquivo e a dedup usa o FITID. CSV não traz conta: a prévia
pede a escolha (`needs = ["account"]`) e a nova prévia leva `overrides = {"account_id": ...}`. A
detecção de transferência interna (contas próprias + `LEDGER_SELF_IDENTIFIERS`) roda no `apply`,
antes das regras. O OFX traz ainda o saldo informado (`LEDGERBAL` → `account_balances`) e o pagador
das entradas (`transactions.payer`).
"""

from __future__ import annotations

import re
import uuid
from datetime import date

import asyncpg

from config import settings
from engines.ingest.protocol import Applied, FilePlan, ParsedFile, PlanError, Undone
from engines.ledger import queries as ledger_queries
from engines.ledger import service as ledger_service

from .importer import (
    StatementEntry,
    insert_entries,
    own_identifiers,
    parse_account_number,
    parse_csv,
    parse_ledger_balance,
    parse_ofx,
    parse_statement_period,
)

_PT_MONTHS = {
    "JAN": 1,
    "FEV": 2,
    "MAR": 3,
    "ABR": 4,
    "MAI": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SET": 9,
    "OUT": 10,
    "NOV": 11,
    "DEZ": 12,
}
_NU_NAME = re.compile(r"(\d{2})([A-Z]{3})(\d{4})_(\d{2})([A-Z]{3})(\d{4})")
_ISO_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})")


def period_from_nubank_name(file_name: str) -> tuple[date, date] | None:
    """`NU_<conta>_01MAR2026_31MAR2026.ofx` ou `..._2026-01-01_2026-10-16.ofx` → período."""
    upper = file_name.upper()
    if m := _NU_NAME.search(upper):
        d1, m1, y1, d2, m2, y2 = m.groups()
        if m1 in _PT_MONTHS and m2 in _PT_MONTHS:
            try:
                return (
                    date(int(y1), _PT_MONTHS[m1], int(d1)),
                    date(int(y2), _PT_MONTHS[m2], int(d2)),
                )
            except ValueError:
                return None
    if m := _ISO_NAME.search(file_name):
        return date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))
    return None


def _text(content: bytes) -> str:
    return content.decode("utf-8", errors="replace").lstrip("﻿")


def self_identifiers() -> list[str]:
    return [s.strip() for s in settings.ledger_self_identifiers.split(",") if s.strip()]


class NubankStatementAdapter:
    sources: tuple[str, ...] = ("nubank_ofx", "nubank_csv")

    def detect(self, file_name: str, content: bytes) -> str | None:
        text = _text(content[:4096])
        if (
            file_name.lower().endswith(".ofx")
            or "<OFX>" in text.upper()
            or (text.lstrip().upper().startswith("OFXHEADER"))
        ):
            return "nubank_ofx"
        header = text.splitlines()[0] if text else ""
        if "Identificador" in header and "Valor" in header and "Data" in header:
            return "nubank_csv"
        return None

    def apply_rank(self, source: str) -> int:
        return 0

    def parse(self, source: str, file_name: str, content: bytes) -> list[StatementEntry]:
        text = _text(content)
        return parse_ofx(text) if source == "nubank_ofx" else parse_csv(text)

    async def plan(
        self, conn: asyncpg.Connection, parsed: ParsedFile, overrides: dict[str, str]
    ) -> FilePlan:
        entries: list[StatementEntry] = parsed.data
        if not entries:
            raise PlanError("Nenhuma transação reconhecida no arquivo.")
        plan = FilePlan(parsed.source, parsed.file_name, parsed.file_hash, parsed=parsed)
        plan.period_start = min(e.date for e in entries)
        plan.period_end = max(e.date for e in entries)
        named = period_from_nubank_name(parsed.file_name)
        if named is not None:  # o nome diz o período do extrato (dia sem transação nas bordas)
            plan.period_start = min(named[0], plan.period_start)
            plan.period_end = max(named[1], plan.period_end)
        account = await self._account(conn, parsed, overrides, plan)
        if account is not None:
            plan.account_id, plan.account_name = str(account["id"]), account["name"]
        ids = [e.external_id for e in entries]
        existing = {
            r["external_id"]
            for r in await conn.fetch(
                "SELECT external_id FROM transactions WHERE external_id = ANY($1::text[])", ids
            )
        }
        seen: set[str] = set()
        for e in entries:
            if e.external_id in existing or e.external_id in seen:
                continue
            seen.add(e.external_id)
            plan.rows.append(e)
        plan.new = len(plan.rows)
        plan.existing = len(entries) - plan.new
        if parsed.source == "nubank_ofx":
            period = parse_statement_period(_text(parsed.content))
            if period is not None:
                plan.period_start = min(period[0], plan.period_start)
                plan.period_end = max(period[1], plan.period_end)
            balance = parse_ledger_balance(_text(parsed.content))
            if balance is not None:
                plan.reported_balance, plan.reported_balance_date = balance
        else:
            plan.warnings.append("CSV não permite conferir o saldo. Prefira o OFX.")
        plan.fingerprint = {"new_ids": sorted(seen)}
        return plan

    async def _account(
        self,
        conn: asyncpg.Connection,
        parsed: ParsedFile,
        overrides: dict[str, str],
        plan: FilePlan,
    ) -> asyncpg.Record | None:
        if parsed.source == "nubank_ofx":
            number = parse_account_number(_text(parsed.content))
            if number is None:
                raise PlanError("OFX sem número de conta.")
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT id, name FROM accounts WHERE account_number = $1", number
            )
            if row is None:
                raise PlanError(f"Conta {number} não cadastrada. Cadastre-a antes de importar.")
            return row
        chosen = overrides.get("account_id")
        if not chosen:
            plan.needs.append("account")
            return None
        try:
            account_id = uuid.UUID(chosen)
        except ValueError:
            raise PlanError("Conta escolhida inválida.") from None
        row = await conn.fetchrow("SELECT id, name FROM accounts WHERE id = $1", account_id)
        if row is None:
            raise PlanError("Conta escolhida não existe.")
        return row

    async def apply(self, conn: asyncpg.Connection, plan: FilePlan, batch_id: str) -> Applied:
        assert plan.account_id is not None and plan.source is not None
        report = await insert_entries(
            conn,
            uuid.UUID(plan.account_id),
            plan.rows,
            await own_identifiers(conn, self_identifiers()),
            source=plan.source,
            batch_id=batch_id,
        )
        balance_written = False
        if plan.reported_balance is not None and plan.reported_balance_date is not None:
            # Saldo informado entra mesmo com 0 transações novas (Story 3.4).
            status = await conn.execute(
                "INSERT INTO account_balances (account_id, as_of, balance, batch_id) "
                "VALUES ($1::uuid, $2, $3, $4::uuid) ON CONFLICT (account_id, as_of) DO NOTHING",
                plan.account_id,
                plan.reported_balance_date,
                plan.reported_balance,
                batch_id,
            )
            balance_written = status.endswith(" 1")
        return Applied(
            inserted=report.imported,
            wrote_other=balance_written,
            months={e.date.replace(day=1) for e in plan.rows},
            detail={"by_kind": report.by_kind, "errors": report.errors},
        )

    async def undo_preview(self, conn: asyncpg.Connection, batch_id: str) -> dict[str, int]:
        row = await conn.fetchrow(ledger_queries.UNDO_COUNTS, batch_id)
        return {k: int(row[k]) for k in ("transactions", "categorizations", "rules", "balances")}

    async def undo(self, conn: asyncpg.Connection, batch_id: str) -> Undone:
        """Sai do lote: as regras criadas nele (as transações de fora que elas categorizaram voltam
        por categorize() sem elas, pendentes), os saldos informados (a âncora da PF é recalculada se
        estava entre eles) e as transações (com as categorizações, FK cascade)."""
        months = {
            r["m"]
            for r in await conn.fetch(
                "SELECT DISTINCT date_trunc('month', date)::date AS m FROM transactions "
                "WHERE batch_id = $1::uuid",
                batch_id,
            )
        }
        outside = await conn.fetch(ledger_queries.RULED_OUTSIDE_BATCH, batch_id)
        await conn.execute("DELETE FROM category_rules WHERE created_in_batch = $1::uuid", batch_id)
        await ledger_service.recategorize_without_rules(conn, outside, batch_id)
        anchored = await conn.fetch(ledger_queries.ANCHORS_IN_BATCH, batch_id)
        await conn.execute("DELETE FROM account_balances WHERE batch_id = $1::uuid", batch_id)
        await conn.execute("DELETE FROM transactions WHERE batch_id = $1::uuid", batch_id)
        # Depois de tirar as transações do lote: a âncora nova não pode contar com elas.
        for r in anchored:
            await ledger_service.recompute_anchor(conn, r["account_id"])
        return Undone(months=months)
