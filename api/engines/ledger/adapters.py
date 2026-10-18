"""Adapter do extrato Nubank (OFX e CSV) no protocolo `SourceAdapter` (AD-5 — Stories 3.3 e 3.4).

OFX: a conta vem do `ACCTID` do próprio arquivo e a dedup usa o FITID. CSV não traz conta: a prévia
pede a escolha (`needs = ["account"]`) e a nova prévia leva `overrides = {"account_id": ...}`. A
detecção de transferência interna (contas próprias + `LEDGER_SELF_IDENTIFIERS`) roda no `apply`,
antes das regras. O OFX traz ainda o saldo informado (`LEDGERBAL` → `account_balances`) e o pagador
das entradas (`transactions.payer`).
"""

from __future__ import annotations

import uuid

import asyncpg

from config import settings
from engines.ingest.protocol import Applied, FilePlan, ParsedFile, PlanError

from .importer import (
    StatementEntry,
    insert_entries,
    own_identifiers,
    parse_account_number,
    parse_csv,
    parse_ledger_balance,
    parse_ofx,
)


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
            balance = parse_ledger_balance(_text(parsed.content))
            if balance is not None:
                plan.reported_balance, plan.reported_balance_date = balance
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
        if plan.reported_balance is not None and plan.reported_balance_date is not None:
            # Saldo informado entra mesmo com 0 transações novas (Story 3.4).
            await conn.execute(
                "INSERT INTO account_balances (account_id, as_of, balance, batch_id) "
                "VALUES ($1::uuid, $2, $3, $4::uuid) ON CONFLICT (account_id, as_of) DO NOTHING",
                plan.account_id,
                plan.reported_balance_date,
                plan.reported_balance,
                batch_id,
            )
        return Applied(
            inserted=report.imported,
            months={e.date.replace(day=1) for e in plan.rows},
            detail={"by_kind": report.by_kind, "errors": report.errors},
        )

    async def undo(self, conn: asyncpg.Connection, batch_id: str) -> None:
        await conn.execute("DELETE FROM account_balances WHERE batch_id = $1::uuid", batch_id)
        await conn.execute("DELETE FROM transactions WHERE batch_id = $1::uuid", batch_id)
