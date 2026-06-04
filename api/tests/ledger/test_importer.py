"""Parsers Nubank (OFX/CSV) + classificação (STORY-01-13-14) — funções puras.

Fixtures inline (CI-safe, sem depender de files/nubank/). A validação com o
extrato real de janeiro é feita via scripts/migrate_ledger.py.
"""

import datetime
from decimal import Decimal

from engines.ledger.importer import StatementEntry, classify, parse_csv, parse_ofx

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


def test_classify_investment_excluded_from_cash():
    e = StatementEntry("ccc", datetime.date(2026, 1, 3), Decimal("-2130.00"), "Aplicação RDB")
    assert classify(e).kind == "investment"


def test_classify_income_and_expense_by_sign():
    income = StatementEntry("a", datetime.date(2026, 1, 1), Decimal("1000"), "Salário recebido")
    expense = StatementEntry("b", datetime.date(2026, 1, 2), Decimal("-200"), "Pagamento de boleto")
    assert classify(income).kind == "income"
    assert classify(expense).kind == "expense"


def test_classify_self_transfer_when_identifier_present():
    e = StatementEntry(
        "d", datetime.date(2026, 1, 3), Decimal("905.60"),
        "Transferência recebida pelo Pix - FULANO DE TAL - BANCO X",
    )
    assert classify(e, self_identifiers=["FULANO DE TAL"]).kind == "transfer"
    # sem o identificador, cai no default por sinal (receita)
    assert classify(e).kind == "income"
