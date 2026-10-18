"""Story 3.4 — pagador extraído do memo do OFX (nome no Pix ou CNPJ); nunca dá categoria."""

from decimal import Decimal

from engines.ledger.importer import extract_payer


def test_pix_received_gives_the_name() -> None:
    memo = (
        "Transferência recebida pelo Pix - ACME SECURITIZADORA S.A - 12.345.678/0001-90 - "
        "Banco XP S.A. (0348) Agência: 1 Conta: 1-1"
    )
    assert extract_payer(memo, Decimal("100")) == "ACME SECURITIZADORA S.A"


def test_cnpj_without_name_gives_the_cnpj() -> None:
    assert extract_payer("TED recebida 12.345.678/0001-90", Decimal("5")) == "12.345.678/0001-90"


def test_outgoing_and_unknown_have_no_payer() -> None:
    assert extract_payer("Transferência enviada pelo Pix - Fulano - x", Decimal("-5")) is None
    assert extract_payer("Pagamento de boleto efetuado", Decimal("-5")) is None
    assert extract_payer("Rendimento", Decimal("1")) is None


def test_statement_period_from_ofx() -> None:
    import datetime

    from engines.ledger.importer import parse_statement_period

    content = "<BANKTRANLIST>\n<DTSTART>20260401000000[-3:BRT]\n<DTEND>20260430000000[-3:BRT]\n"
    assert parse_statement_period(content) == (
        datetime.date(2026, 4, 1),
        datetime.date(2026, 4, 30),
    )
    assert parse_statement_period("<OFX></OFX>") is None
