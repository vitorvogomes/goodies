"""Import de extrato Nubank -> ledger (STORY-01-13-14).

Parsers OFX (1.0.2 SGML) e CSV; classificação configurável; dedup idempotente por
external_id (FITID/Identificador). Movimentos de investimento e transferência
interna NÃO viram transações (preservam a taxa de poupança — ver cashflow.py).
"""

import csv
import datetime
import io
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import asyncpg


@dataclass(frozen=True)
class StatementEntry:
    external_id: str
    date: datetime.date
    amount: Decimal  # com sinal: positivo = crédito, negativo = débito
    description: str


@dataclass(frozen=True)
class Classification:
    kind: str  # "income" | "expense" | "investment" | "transfer"
    category: str


@dataclass(frozen=True)
class MatchRule:
    """Regra de classificação configurável (vem de categories.match_patterns)."""

    category: str
    kind: str
    patterns: tuple[str, ...]


@dataclass
class ImportReport:
    imported: int = 0
    duplicates: int = 0
    skipped: int = 0  # legado: nada é pulado agora (grava-se tudo, classificado por kind)
    errors: int = 0


_TRNTAG = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.DOTALL)


def _ofx_tag(block: str, name: str) -> str | None:
    # OFX SGML: tags podem não fechar (ex.: MEMO) — lê até newline ou próxima tag.
    match = re.search(rf"<{name}>([^\r\n<]*)", block)
    return match.group(1).strip() if match else None


def parse_ofx(content: str) -> list[StatementEntry]:
    entries: list[StatementEntry] = []
    for block in _TRNTAG.findall(content):
        posted = _ofx_tag(block, "DTPOSTED")
        amount = _ofx_tag(block, "TRNAMT")
        fitid = _ofx_tag(block, "FITID")
        memo = _ofx_tag(block, "MEMO") or _ofx_tag(block, "NAME") or ""
        if not (posted and amount and fitid):
            continue
        entries.append(
            StatementEntry(
                external_id=fitid,
                date=datetime.date(int(posted[0:4]), int(posted[4:6]), int(posted[6:8])),
                amount=Decimal(amount),
                description=memo,
            )
        )
    return entries


def parse_csv(content: str) -> list[StatementEntry]:
    entries: list[StatementEntry] = []
    reader = csv.DictReader(io.StringIO(content.lstrip("﻿")))
    for row in reader:
        raw_date = (row.get("Data") or "").strip()
        raw_amount = (row.get("Valor") or "").strip()
        fitid = (row.get("Identificador") or "").strip()
        description = (row.get("Descrição") or row.get("Descricao") or "").strip()
        if not (raw_date and raw_amount and fitid):
            continue
        day, month, year = raw_date.split("/")
        entries.append(
            StatementEntry(
                external_id=fitid,
                date=datetime.date(int(year), int(month), int(day)),
                amount=Decimal(raw_amount),
                description=description,
            )
        )
    return entries


def classify(
    entry: StatementEntry,
    rules: Sequence[MatchRule] = (),
    self_identifiers: Sequence[str] = (),
) -> Classification:
    """Classifica um lançamento: regra de destino (maior pattern vence) > transferência
    interna (conta própria na descrição) > fallback por sinal (receita/despesa)."""
    desc = entry.description.lower()
    best: MatchRule | None = None
    best_len = 0
    for rule in rules:
        for pattern in rule.patterns:
            p = pattern.lower()
            if p and p in desc and len(p) > best_len:
                best, best_len = rule, len(p)
    if best is not None:
        return Classification(best.kind, best.category)
    if "transfer" in desc and any(s.lower() in desc for s in self_identifiers):
        return Classification("transfer", "Transferência interna")
    if entry.amount > 0:
        return Classification("income", "outros")
    return Classification("expense", "outros")


async def _load_rules(conn: asyncpg.Connection) -> list[MatchRule]:
    """Carrega as regras de classificação das categorias ativas com patterns."""
    rows = await conn.fetch(
        "SELECT name, kind, match_patterns FROM categories "
        "WHERE is_active AND array_length(match_patterns, 1) IS NOT NULL"
    )
    return [MatchRule(r["name"], r["kind"], tuple(r["match_patterns"])) for r in rows]


def parse_statement(filename: str, content: str) -> list[StatementEntry]:
    """Escolhe o parser pela extensão/conteúdo do arquivo."""
    if filename.lower().endswith(".ofx") or content.lstrip().upper().startswith("OFXHEADER"):
        return parse_ofx(content)
    return parse_csv(content)


def parse_account_number(content: str) -> str | None:
    """Extrai o ACCTID (nº da conta) do OFX BANKACCTFROM. CSV não carrega conta -> None."""
    match = re.search(r"<ACCTID>([^\r\n<]*)", content)
    return match.group(1).strip() if match else None


async def import_statement(
    conn: asyncpg.Connection,
    account_id: uuid.UUID,
    entries: Sequence[StatementEntry],
    self_identifiers: Sequence[str] = (),
) -> ImportReport:
    """Grava todos os lançamentos com o `kind` classificado (dedup por external_id).

    Investimento e transferência interna TAMBÉM são gravados (consertam o saldo); o
    relatório (view monthly_summary) é que decide o que é consumo via `kind`. Os
    números das contas cadastradas entram como identificadores de transferência
    interna: um lançamento cuja origem/destino é uma conta própria (nº na descrição)
    vira `transfer` e fica fora da receita/despesa (evita dupla contagem CPF↔CNPJ).
    """
    own = await conn.fetch("SELECT account_number FROM accounts WHERE account_number IS NOT NULL")
    identifiers = [r["account_number"] for r in own] + list(self_identifiers)
    rules = await _load_rules(conn)
    report = ImportReport()
    for entry in entries:
        result = classify(entry, rules, identifiers)
        try:
            inserted = await conn.fetchval(
                "INSERT INTO transactions "
                "(account_id, date, amount, category, kind, description, external_id) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                "ON CONFLICT (external_id) WHERE external_id IS NOT NULL DO NOTHING "
                "RETURNING id",
                account_id,
                entry.date,
                entry.amount,
                result.category,
                result.kind,
                entry.description,
                entry.external_id,
            )
        except (asyncpg.PostgresError, InvalidOperation):
            report.errors += 1
            continue
        if inserted is None:
            report.duplicates += 1
        else:
            report.imported += 1
    return report
