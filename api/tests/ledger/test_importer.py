"""Parsers Nubank (OFX/CSV) + classificação (STORY-01-13-14) — funções puras.

Fixtures inline (CI-safe, sem depender de files/nubank/). A validação com o
extrato real de janeiro é feita via scripts/migrate_ledger.py.
"""

import datetime
import uuid
from decimal import Decimal

from engines.ledger.importer import (
    MatchRule,
    StatementEntry,
    classify,
    import_statement,
    parse_account_number,
    parse_csv,
    parse_ofx,
)

# Regras inline (espelham categories.match_patterns após a migration 0009: caixinha
# = investment net — aplicação E resgate caem em investment; a categoria income
# 'Resgate' foi neutralizada, então não aparece aqui).
_RULES = [
    MatchRule(
        "Caixinha/RDB Nubank",
        "investment",
        ("rdb", "aplicação", "resgate rdb", "nu reserva imediata", "dinheiro guardado"),
    ),
    MatchRule("Toro (B3)", "investment", ("toro", "corretora de titulos")),
]

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


def test_classify_redemption_positive_is_investment_not_income():
    # "Resgate RDB" é positivo (volta p/ a conta) mas é movimento de investimento.
    e = StatementEntry("r", datetime.date(2026, 1, 10), Decimal("1000.00"), "Resgate RDB")
    assert classify(e, _RULES).kind == "investment"


def test_classify_caixinha_app_and_redemption_both_investment():
    # Política caixinha=investment net: aplicação (saída) E resgate (entrada) → investment.
    app = StatementEntry(
        "a", datetime.date(2026, 1, 5), Decimal("-500.00"), "Aplicação RDB - Caixinha Turbo"
    )
    redemption = StatementEntry(
        "b", datetime.date(2026, 1, 20), Decimal("480.00"), "Resgate RDB - Caixinha Turbo"
    )
    assert classify(app, _RULES).kind == "investment"
    assert classify(app, _RULES).category == "Caixinha/RDB Nubank"
    assert classify(redemption, _RULES).kind == "investment"
    assert classify(redemption, _RULES).category == "Caixinha/RDB Nubank"


def test_classify_nu_reserva_fundo_redemption_is_investment():
    # Resgate de fundo (Nu Reserva Imediata) NÃO tem 'caixinha'/'rdb' na descrição —
    # o anchor 'nu reserva imediata' garante investment (não receita) no import futuro.
    e = StatementEntry(
        "c",
        datetime.date(2025, 7, 18),
        Decimal("2844.50"),
        "Resgate Fundo - Nu Reserva Imediata - Resp. Ltda  - Caixinha Reserva",
    )
    assert classify(e, _RULES).kind == "investment"


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
