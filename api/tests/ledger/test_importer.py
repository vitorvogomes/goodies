"""Parsers Nubank (OFX/CSV) + classificação (STORY-01-13-14) — funções puras.

Fixtures inline (CI-safe, sem depender de files/nubank/). A validação com o
extrato real de janeiro é feita via scripts/migrate_ledger.py.
"""

import datetime
import uuid
from decimal import Decimal

from engines.ledger.calc import Rule
from engines.ledger.importer import (
    StatementEntry,
    classify,
    import_statement,
    parse_account_number,
    parse_csv,
    parse_ofx,
)


# Regras inline com direção (Story 2.4/2.5, ADR-015): padrão de investimento vira duas regras —
# saída → a subcategoria de investimento; entrada → o Resgate correspondente (receita).
def _rules(category: str, resgate: str, patterns: tuple[str, ...]) -> list[Rule]:
    out = []
    for p in patterns:
        out.append(Rule(p, "saida", f"id:{category}", category, "investment", f"r:{p}:s"))
        out.append(Rule(p, "entrada", f"id:{resgate}", resgate, "income", f"r:{p}:e"))
    return out


_RULES = _rules(
    "Caixinha/RDB Nubank",
    "Resgate Caixinha/RDB Nubank",
    ("rdb", "aplicação", "resgate rdb", "nu reserva imediata", "dinheiro guardado"),
) + _rules("Toro (B3)", "Resgate Toro (B3)", ("toro", "corretora de titulos"))

_CSV = """Data,Valor,Identificador,Descrição
01/01/2026,1000.00,aaa,Salário recebido
02/01/2026,-200.00,bbb,Pagamento de boleto efetuado - PREF
03/01/2026,-2130.00,ccc,Aplicação RDB
"""

_OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM>
<BANKID>0260</BANKID>
<ACCTID>4288917-8</ACCTID>
<ACCTTYPE>CHECKING</ACCTTYPE>
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT</TRNTYPE>
<DTPOSTED>20260101000000[-3:BRT]</DTPOSTED>
<TRNAMT>1000.00</TRNAMT>
<FITID>aaa</FITID>
<MEMO>Salario recebido
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260102000000[-3:BRT]</DTPOSTED>
<TRNAMT>-200.00</TRNAMT>
<FITID>bbb</FITID>
<MEMO>Pagamento de boleto efetuado
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260103000000[-3:BRT]</DTPOSTED>
<TRNAMT>-2130.00</TRNAMT>
<FITID>ccc</FITID>
<MEMO>Aplicacao RDB
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>0.23</BALAMT>
<DTASOF>20260131000000[-3:BRT]</DTASOF>
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


def test_parse_csv():
    entries = parse_csv(_CSV)
    assert len(entries) == 3
    assert entries[0] == StatementEntry(
        "aaa", datetime.date(2026, 1, 1), Decimal("1000.00"), "Salário recebido"
    )
    assert entries[2].amount == Decimal("-2130.00")
    assert entries[1].external_id == "bbb"


def test_parse_ofx():
    entries = parse_ofx(_OFX)
    assert len(entries) == 3
    by_id = {e.external_id: e for e in entries}
    assert by_id["aaa"].amount == Decimal("1000.00")
    assert by_id["aaa"].date == datetime.date(2026, 1, 1)
    assert by_id["ccc"].amount == Decimal("-2130.00")


def test_classify_investment_by_rule():
    e = StatementEntry("ccc", datetime.date(2026, 1, 3), Decimal("-2130.00"), "Aplicação RDB")
    assert classify(e, _RULES).kind == "investment"
    assert classify(e, _RULES).category == "Caixinha/RDB Nubank"
    # sem regras carregadas, cai no fallback por sinal (despesa)
    assert classify(e).kind == "expense"


def test_classify_brokerage_deposit_is_investment():
    # Pix p/ corretora (mesmo CNPJ Toro/Santander) é investimento, não consumo.
    e = StatementEntry(
        "t",
        datetime.date(2026, 6, 1),
        Decimal("-579.00"),
        "Transferência enviada pelo Pix - SANTANDER CORRETORA DE TITULOS E VALORES MOBILIARIOS",
    )
    assert classify(e, _RULES).kind == "investment"
    assert classify(e, _RULES).category == "Toro (B3)"


def test_classify_redemption_positive_is_resgate_income():
    # ADR-015: "Resgate RDB" (entrada) é receita na subcategoria de Resgates, não investimento.
    e = StatementEntry("r", datetime.date(2026, 1, 10), Decimal("1000.00"), "Resgate RDB")
    assert classify(e, _RULES).kind == "income"
    assert classify(e, _RULES).category == "Resgate Caixinha/RDB Nubank"


def test_classify_caixinha_app_is_investment_and_redemption_is_resgate():
    # Story 2.4: a direção separa aplicação (saída → investimento) de resgate (entrada → Resgates).
    app = StatementEntry(
        "a", datetime.date(2026, 1, 5), Decimal("-500.00"), "Aplicação RDB - Caixinha Turbo"
    )
    redemption = StatementEntry(
        "b", datetime.date(2026, 1, 20), Decimal("480.00"), "Resgate RDB - Caixinha Turbo"
    )
    assert classify(app, _RULES).kind == "investment"
    assert classify(app, _RULES).category == "Caixinha/RDB Nubank"
    assert classify(redemption, _RULES).kind == "income"
    assert classify(redemption, _RULES).category == "Resgate Caixinha/RDB Nubank"


def test_classify_nu_reserva_fundo_redemption_is_resgate():
    # Resgate de fundo (Nu Reserva Imediata) não tem 'caixinha'/'rdb' na descrição — o padrão
    # 'nu reserva imediata' (entrada) leva ao Resgate da caixinha (receita, ADR-015).
    e = StatementEntry(
        "c",
        datetime.date(2025, 7, 18),
        Decimal("2844.50"),
        "Resgate Fundo - Nu Reserva Imediata - Resp. Ltda  - Caixinha Reserva",
    )
    assert classify(e, _RULES).kind == "income"
    assert classify(e, _RULES).category == "Resgate Caixinha/RDB Nubank"


def test_classify_income_and_expense_by_sign():
    income = StatementEntry("a", datetime.date(2026, 1, 1), Decimal("1000"), "Salário recebido")
    expense = StatementEntry("b", datetime.date(2026, 1, 2), Decimal("-200"), "Pagamento de boleto")
    assert classify(income).kind == "income"
    assert classify(expense).kind == "expense"


def test_parse_account_number_from_ofx():
    assert parse_account_number(_OFX) == "4288917-8"
    assert parse_account_number(_CSV) is None  # CSV não carrega a conta


def test_classify_transfer_by_account_number():
    # transferência cujo destino é uma conta própria (número na descrição) -> interna
    entry = StatementEntry(
        "z",
        datetime.date(2026, 1, 5),
        Decimal("-4196.34"),
        "Transferência enviada pelo Pix - Fulano - NU PAGAMENTOS Agência: 1 Conta: 58022571-6",
    )
    assert classify(entry, self_identifiers=["58022571-6"]).kind == "transfer"
    assert classify(entry).kind == "expense"  # sem o identificador, é despesa


async def test_import_statement_records_transfer_with_kind(pool):
    num_b = f"TEST-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        acc_a = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, $2) RETURNING id", "A", "bank"
        )
        await conn.execute(
            "INSERT INTO accounts (name, type, account_number) VALUES ($1, $2, $3)",
            "B",
            "bank",
            num_b,
        )
        entries = [
            StatementEntry(
                uuid.uuid4().hex,
                datetime.date(2099, 1, 1),
                Decimal("-100.00"),
                f"Transferência enviada pelo Pix - Fulano - Conta: {num_b}",
            ),
            StatementEntry(
                uuid.uuid4().hex,
                datetime.date(2099, 1, 2),
                Decimal("-30.00"),
                "Pagamento de boleto efetuado",
            ),
        ]
        report = await import_statement(conn, acc_a, entries)
        kinds = {
            r["kind"]
            for r in await conn.fetch("SELECT kind FROM transactions WHERE account_id = $1", acc_a)
        }
    assert report.skipped == 0  # nada é pulado: grava-se tudo, classificado por kind
    assert report.imported == 2  # transferência interna + despesa, ambas gravadas
    assert kinds == {"transfer", "expense"}  # a transferência fica fora de receita/despesa


async def test_import_report_by_kind_breaks_down_new(pool):
    """ImportReport.by_kind conta só as NOVAS importadas, por kind (clareza no front)."""
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, $2) RETURNING id", "ByKind", "bank"
        )
        entries = [
            StatementEntry(uuid.uuid4().hex, datetime.date(2099, 2, 1), Decimal("1000"), "Salário"),
            StatementEntry(uuid.uuid4().hex, datetime.date(2099, 2, 2), Decimal("-50"), "Mercado"),
            StatementEntry(uuid.uuid4().hex, datetime.date(2099, 2, 3), Decimal("-80"), "Padaria"),
        ]
        report = await import_statement(conn, acc, entries)
        report2 = await import_statement(conn, acc, entries)  # reimport: tudo duplicado
    assert report.imported == 3
    assert report.by_kind == {"income": 1, "expense": 2}
    assert report2.imported == 0
    assert sum(report2.by_kind.values()) == 0  # duplicadas não contam


def test_classify_self_transfer_when_identifier_present():
    e = StatementEntry(
        "d",
        datetime.date(2026, 1, 3),
        Decimal("905.60"),
        "Transferência recebida pelo Pix - FULANO DE TAL - BANCO X",
    )
    assert classify(e, self_identifiers=["FULANO DE TAL"]).kind == "transfer"
    # sem o identificador, cai no default por sinal (receita)
    assert classify(e).kind == "income"


async def test_import_statement_records_batch_and_source(pool):
    """Story 2.2: o import v1 grava lote `applied` (período do arquivo) e `source`; reimport sem
    linha nova não deixa lote vazio."""
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, $2) RETURNING id", "Lote", "bank"
        )
        entries = [
            StatementEntry(uuid.uuid4().hex, datetime.date(2099, 3, 1), Decimal("-5"), "Café"),
            StatementEntry(uuid.uuid4().hex, datetime.date(2099, 3, 9), Decimal("-7"), "Pão"),
        ]
        before = await conn.fetchval("SELECT count(*) FROM import_batches")
        await import_statement(conn, acc, entries, source="nubank_csv", file_name="x.csv")
        rows = await conn.fetch(
            "SELECT t.source, f.period_start, f.period_end, b.status FROM transactions t "
            "JOIN import_batches b ON b.id = t.batch_id "
            "JOIN import_batch_files f ON f.batch_id = b.id WHERE t.account_id = $1",
            acc,
        )
        mid = await conn.fetchval("SELECT count(*) FROM import_batches")
        await import_statement(conn, acc, entries, source="nubank_csv", file_name="x.csv")
        after = await conn.fetchval("SELECT count(*) FROM import_batches")
    assert {(r["source"], r["period_start"], r["period_end"], r["status"]) for r in rows} == {
        ("nubank_csv", datetime.date(2099, 3, 1), datetime.date(2099, 3, 9), "applied")
    }
    assert mid == before + 1 and after == mid


def test_source_for_filename():
    from engines.ledger.importer import source_for

    assert source_for("NU_2026.OFX") == "nubank_ofx"
    assert source_for("extrato.csv") == "nubank_csv"


async def test_import_categorizes_through_categorize(pool):
    """Story 2.5: import grava "a classificar" e a regra vem por categorize() (cause import,
    pendente de revisão, evento com o lote)."""
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, $2) RETURNING id", "Cat", "bank"
        )
        cat = await conn.fetchval("SELECT id FROM categories WHERE key = 'gasto:lazer'")
        await conn.execute(
            "INSERT INTO category_rules (pattern, direction, category_id) "
            "VALUES ('zzcinema', 'saida', $1) ON CONFLICT DO NOTHING",
            cat,
        )
        entries = [
            StatementEntry(
                uuid.uuid4().hex, datetime.date(2099, 4, 1), Decimal("-30"), "ZZCINEMA X"
            ),
            StatementEntry(uuid.uuid4().hex, datetime.date(2099, 4, 2), Decimal("-9"), "Algo novo"),
        ]
        await import_statement(conn, acc, entries)
        rows = await conn.fetch(
            "SELECT t.category, t.category_source, t.review_status, "
            "(SELECT cause FROM categorization_events e WHERE e.transaction_id = t.id) cause "
            "FROM transactions t WHERE t.account_id = $1 ORDER BY t.date",
            acc,
        )
        await conn.execute("DELETE FROM category_rules WHERE pattern = 'zzcinema'")
    assert [tuple(r) for r in rows] == [
        ("Lazer", "rule", "pending", "import"),
        ("Saída a classificar", "suggestion", "pending", None),
    ]
