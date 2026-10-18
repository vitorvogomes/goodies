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
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import asyncpg

from engines.ingest import service as ingest_service
from engines.ingest.models import BatchFileIn
from engines.ledger import queries as ledger_queries
from engines.ledger import service as ledger_service
from engines.ledger.calc import Rule, best_rule
from engines.ledger.suggest import HistoryItem, best_suggestion, tokens


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
    # Story 2.5: a subcategoria vem da regra (`category_id` + `rule_id`) ou de uma key de sistema
    # (transferência interna detectada pelo adapter; "a classificar" pelo sinal).
    category_id: str | None = None
    rule_id: str | None = None
    category_key: str | None = None


@dataclass
class ImportReport:
    imported: int = 0
    duplicates: int = 0
    skipped: int = 0  # legado: nada é pulado agora (grava-se tudo, classificado por kind)
    errors: int = 0
    # breakdown das NOVAS importadas por kind (income/expense/investment/transfer)
    by_kind: dict[str, int] = field(default_factory=dict)
    new_ids: list[str] = field(default_factory=list)


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
    rules: Sequence[Rule] = (),
    self_identifiers: Sequence[str] = (),
) -> Classification:
    """Classifica um lançamento: transferência interna (conta própria na descrição — detecção do
    adapter Nubank, antes das regras, AD-6) > regra (direção pelo sinal; maior padrão vence;
    empate → mais recente) > "a classificar" pelo sinal."""
    desc = entry.description.lower()
    if "transfer" in desc and any(s.lower() in desc for s in self_identifiers):
        return Classification("transfer", "Transferência interna", category_key="transfer:interna")
    rule = best_rule(entry.description, entry.amount, rules)
    if rule is not None:
        return Classification(rule.kind, rule.category_name, rule.category_id, rule.rule_id)
    if entry.amount > 0:
        return Classification(
            "income", "Entrada a classificar", category_key="sistema:entrada_a_classificar"
        )
    return Classification(
        "expense", "Saída a classificar", category_key="sistema:saida_a_classificar"
    )


_history_cache: dict[str, Any] = {}


async def suggestion_history(conn: asyncpg.Connection) -> list[HistoryItem]:
    """Confirmadas, da mais recente para a mais antiga, sem repetir (tokens, categoria, sinal).
    Guardado enquanto a versão (confirmadas + último evento de categorização) não muda: um lote com
    vários arquivos não relê e retokeniza o histórico a cada arquivo."""
    version = tuple(await conn.fetchrow(ledger_queries.HISTORY_VERSION))
    if _history_cache.get("version") == version:
        cached: list[HistoryItem] = _history_cache["items"]
        return cached
    seen: set[tuple[frozenset[str], str, bool]] = set()
    items: list[HistoryItem] = []
    for r in await conn.fetch(ledger_queries.CONFIRMED_HISTORY):
        item = HistoryItem(tokens(r["description"]), str(r["category_id"]), r["positive"])
        key = (item.tokens, item.category_id, item.positive)
        if item.tokens and key not in seen:
            seen.add(key)
            items.append(item)
    _history_cache.update(version=version, items=items)
    return items


async def _load_rules(conn: asyncpg.Connection) -> list[Rule]:
    """Regras ativas de `category_rules` (Story 2.5; `match_patterns` deixa de ser lido)."""
    return await ledger_service.load_rules(conn)


def parse_statement(filename: str, content: str) -> list[StatementEntry]:
    """Escolhe o parser pela extensão/conteúdo do arquivo."""
    if filename.lower().endswith(".ofx") or content.lstrip().upper().startswith("OFXHEADER"):
        return parse_ofx(content)
    return parse_csv(content)


_PIX_RECEIVED = re.compile(
    r"^(?:Transfer[eê]ncia|Reembolso|Devolu[cç][aã]o)\s+recebid[ao]\s+(?:pelo\s+Pix\s+)?-\s+"
    r"(?P<name>[^-]+?)\s+-\s",
    re.IGNORECASE,
)
_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")


def extract_payer(description: str, amount: Decimal) -> str | None:
    """Pagador de uma entrada (Story 3.4): nome no Pix recebido, senão o CNPJ do memo. Saída não tem
    pagador. Nunca decide categoria."""
    if amount <= 0:
        return None
    match = _PIX_RECEIVED.match(description.strip())
    if match:
        return match.group("name").strip()
    cnpj = _CNPJ.search(description)
    return cnpj.group(0) if cnpj else None


def parse_ledger_balance(content: str) -> tuple[Decimal, datetime.date] | None:
    """Saldo informado do OFX: `<LEDGERBAL><BALAMT>` com a data de `<DTASOF>`."""
    block = re.search(r"<LEDGERBAL>(.*?)</LEDGERBAL>", content, re.DOTALL)
    if block is None:
        return None
    amount = _ofx_tag(block.group(1), "BALAMT")
    asof = _ofx_tag(block.group(1), "DTASOF")
    if not (amount and asof):
        return None
    try:
        return Decimal(amount), datetime.date(int(asof[0:4]), int(asof[4:6]), int(asof[6:8]))
    except (InvalidOperation, ValueError):
        return None


def parse_statement_period(content: str) -> tuple[datetime.date, datetime.date] | None:
    """Período do extrato OFX (`<BANKTRANLIST>` `DTSTART`/`DTEND`): mais fiel que as datas das
    transações para a cobertura e as lacunas (Story 3.9)."""
    start = _ofx_tag(content, "DTSTART")
    end = _ofx_tag(content, "DTEND")
    if not (start and end):
        return None
    try:
        return (
            datetime.date(int(start[0:4]), int(start[4:6]), int(start[6:8])),
            datetime.date(int(end[0:4]), int(end[4:6]), int(end[6:8])),
        )
    except ValueError:
        return None


def parse_account_number(content: str) -> str | None:
    """Extrai o ACCTID (nº da conta) do OFX BANKACCTFROM. CSV não carrega conta -> None."""
    match = re.search(r"<ACCTID>([^\r\n<]*)", content)
    return match.group(1).strip() if match else None


def source_for(filename: str) -> str:
    """Fonte do arquivo para a proveniência (Story 2.2): CSV ou OFX do Nubank."""
    return "nubank_csv" if filename.lower().endswith(".csv") else "nubank_ofx"


async def own_identifiers(
    conn: asyncpg.Connection, self_identifiers: Sequence[str] = ()
) -> list[str]:
    """Números das contas cadastradas + `LEDGER_SELF_IDENTIFIERS`: transferência interna."""
    own = await conn.fetch("SELECT account_number FROM accounts WHERE account_number IS NOT NULL")
    return [r["account_number"] for r in own] + list(self_identifiers)


async def insert_entries(
    conn: asyncpg.Connection,
    account_id: uuid.UUID,
    entries: Sequence[StatementEntry],
    identifiers: Sequence[str],
    *,
    source: str,
    batch_id: str | None,
) -> ImportReport:
    """Grava os lançamentos do lote (dedup por external_id), cada um "a classificar" e `pending`, e
    passa a categoria proposta por `categorize()` (cause `import`, sem hooks: a derivação roda pelo
    lote). Investimento e transferência interna também são gravados (consertam o saldo); o `kind`
    vem da categoria. Quem chama abre a transação."""
    rules = await _load_rules(conn)
    history = await suggestion_history(conn)
    report = ImportReport()
    pending_by_sign = {
        True: await ledger_queries.category_id_by_key(conn, "sistema:entrada_a_classificar"),
        False: await ledger_queries.category_id_by_key(conn, "sistema:saida_a_classificar"),
    }
    key_ids: dict[str, str] = {}
    changes: list[ledger_service.CategoryChange] = []
    for entry in entries:
        result = classify(entry, rules, identifiers)
        positive = entry.amount > 0
        try:
            # Savepoint por linha: linha ruim conta como erro sem abortar o lote.
            async with conn.transaction():
                inserted = await conn.fetchval(
                    "INSERT INTO transactions "
                    "(account_id, date, amount, category, category_id, kind, description, "
                    "external_id, batch_id, source, payer, category_source, review_status) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'suggestion', "
                    "'pending') "
                    "ON CONFLICT (external_id) WHERE external_id IS NOT NULL DO NOTHING "
                    "RETURNING id",
                    account_id,
                    entry.date,
                    entry.amount,
                    "Entrada a classificar" if positive else "Saída a classificar",
                    pending_by_sign[positive],
                    "income" if positive else "expense",
                    entry.description,
                    entry.external_id,
                    batch_id,
                    source,
                    extract_payer(entry.description, entry.amount),
                )
        except (asyncpg.PostgresError, InvalidOperation):
            report.errors += 1
            continue
        if inserted is None:
            report.duplicates += 1
            continue
        report.imported += 1
        report.new_ids.append(str(inserted))
        report.by_kind[result.kind] = report.by_kind.get(result.kind, 0) + 1
        target = result.category_id
        if target is None and result.category_key is not None:
            if result.category_key not in key_ids:
                key_ids[result.category_key] = await ledger_queries.category_id_by_key(
                    conn, result.category_key
                )
            target = key_ids[result.category_key]
        if target is not None and target != pending_by_sign[positive]:
            changes.append(
                ledger_service.CategoryChange(
                    transaction_id=str(inserted),
                    category_id=target,
                    source="rule",
                    rule_id=result.rule_id,
                )
            )
        elif (hint := best_suggestion(entry.description, entry.amount, history)) is not None:
            # Sem regra: a confirmada mais parecida (Story 3.6), pendente até a revisão.
            changes.append(
                ledger_service.CategoryChange(str(inserted), hint.category_id, "suggestion")
            )
    await ledger_service.categorize(
        conn, changes, cause="import", batch_id=batch_id, fire_hooks=False
    )
    return report


async def import_statement(
    conn: asyncpg.Connection,
    account_id: uuid.UUID,
    entries: Sequence[StatementEntry],
    self_identifiers: Sequence[str] = (),
    *,
    source: str = "nubank_ofx",
    file_name: str | None = None,
) -> ImportReport:
    """Import direto, sem prévia (scripts e testes): lote `applied` + `insert_entries` numa
    transação só; sem linha nova, o lote é apagado. O app importa pelo protocolo da engine
    `ingest` (Story 3.3)."""
    identifiers = await own_identifiers(conn, self_identifiers)
    # Tudo ou nada: lote, linhas e categorização numa transação só (falha no meio não deixa linha
    # presa "a classificar" que o reimport, deduplicado por external_id, nunca consertaria).
    async with conn.transaction():
        batch_id = None
        if entries:
            batch_id = await ingest_service.record_applied_batch(
                conn,
                [
                    BatchFileIn(
                        source=source,
                        account_id=str(account_id),
                        file_name=file_name,
                        period_start=min(e.date for e in entries),
                        period_end=max(e.date for e in entries),
                    )
                ],
            )
        report = await insert_entries(
            conn, account_id, entries, identifiers, source=source, batch_id=batch_id
        )
        if report.new_ids:
            await ledger_service.run_transaction_hooks(conn, report.new_ids)
        if batch_id is not None and report.imported == 0:
            await conn.execute(
                "DELETE FROM import_batches WHERE id = $1 AND NOT EXISTS "
                "(SELECT 1 FROM transactions WHERE batch_id = $1)",
                batch_id,
            )
    return report
