"""Tests for B3 Movimentação parser (STORY-02-17-18, fonte real Toro/B3)."""
from __future__ import annotations

from datetime import date

from engines.portfolio.b3_import import (
    b3_category,
    map_movimentacao,
    parse_b3_categories,
    parse_b3_movimentacao,
    parse_b3_position_prices,
    parse_produto,
)

# Linhas de dados (sem cabeçalho), no layout real da aba "Movimentação".
# Entrada/Saída | Data | Movimentação | Produto | Instituição | Qtd | Preço | Valor
_ROWS = [
    ("Credito", "20/05/2026", "Transferência - Liquidação",
     "BBAS3 - BANCO DO BRASIL S/A", "SANTANDER", 3, 20.34, 61.02),
    ("Debito", "21/05/2026", "Transferência - Liquidação",
     "PETR4 - PETROLEO BRASILEIRO S/A PETROBRAS", "SANTANDER", 2, 30.0, 60.0),
    ("Credito", "08/05/2026", "Compra",
     "Tesouro IPCA+ 2040", "NU INVESTIMENTOS S.A. - CTVM", 0.1, 1771.82, 177.18),
    ("Credito", "20/05/2026", "Rendimento",
     "MXRF11 - MAXI RENDA FDO INV IMOB - FII", "SANTANDER", 44, 0.10, 4.40),
    ("Credito", "20/05/2026", "Juros Sobre Capital Próprio",
     "PETR4 - PETROLEO BRASILEIRO S/A PETROBRAS", "SANTANDER", 18, 0.31, 4.65),
    ("Credito", "28/05/2026", "Atualização",
     "PETR4 - PETROLEO BRASILEIRO S/A PETROBRAS", "SANTANDER", 18, "-", "-"),
    ("Debito", "14/05/2026", "Direitos de Subscrição - Não Exercido",
     "BTLG12 - BTG PACTUAL", "SANTANDER", 0, "-", "-"),
]


class TestProdutoTicker:
    def test_extracts_ticker_before_dash(self) -> None:
        assert parse_produto("BBAS3 - BANCO DO BRASIL S/A") == "BBAS3"

    def test_strips_fractional_suffix(self) -> None:
        assert parse_produto("PETR4F - PETROLEO") == "PETR4"

    def test_tesouro_keeps_full_name(self) -> None:
        assert parse_produto("Tesouro IPCA+ 2040") == "Tesouro IPCA+ 2040"


class TestCategory:
    def test_known_categories(self) -> None:
        assert b3_category("BBAS3") == "Ações Nacionais"
        assert b3_category("MXRF11") == "FIIs"
        assert b3_category("ACWI11") == "ETFs"
        assert b3_category("Tesouro IPCA+ 2040") == "Aposentadoria"


# Abas 'Posição' de exemplo (cabeçalho + 1 linha), para a derivação de categoria.
_POS_SHEETS = {
    "Posição - Ações": [
        ("Código de Negociação", "Preço de Fechamento"),
        ("PETR4", 30.0),
    ],
    "Posição - ETF": [
        ("Código de Negociação", "Preço de Fechamento"),
        ("XPTO11", 99.0),  # ETF NOVO, fora do allowlist e terminando em 11
    ],
    "Posição - Fundos": [
        ("Código de Negociação", "Preço de Fechamento"),
        ("MXRF11", 10.0),
    ],
    "Posição - Tesouro Direto": [
        ("Produto", "Quantidade", "Valor Atualizado"),
        ("Tesouro IPCA+ 2040", 0.1, 177.0),
    ],
}


class TestSheetCategories:
    """§3.3: categoria derivada das abas 'Posição' (robusta vs heurística de sufixo)."""

    def test_derives_from_position_sheets(self) -> None:
        cats = parse_b3_categories(_POS_SHEETS)
        assert cats["PETR4"] == "Ações Nacionais"
        assert cats["XPTO11"] == "ETFs"  # a heurística erraria (FIIs)
        assert cats["MXRF11"] == "FIIs"
        assert cats["Tesouro IPCA+ 2040"] == "Aposentadoria"

    def test_heuristic_misclassifies_new_etf_in_11(self) -> None:
        # documenta o risco: sem o mapa, um ETF novo em 11 cai no fallback -> FIIs
        assert b3_category("XPTO11") == "FIIs"

    def test_movimentacao_map_wins_over_heuristic(self) -> None:
        rows = [
            ("Credito", "20/05/2026", "Transferência - Liquidação",
             "XPTO11 - NOVO ETF", "TORO", 1, 100.0, 100.0),
        ]
        ops = parse_b3_movimentacao(rows, category_map={"XPTO11": "ETFs"})
        assert ops[0]["asset_category"] == "ETFs"

    def test_movimentacao_without_map_uses_heuristic(self) -> None:
        rows = [
            ("Credito", "20/05/2026", "Transferência - Liquidação",
             "XPTO11 - NOVO ETF", "TORO", 1, 100.0, 100.0),
        ]
        ops = parse_b3_movimentacao(rows)
        assert ops[0]["asset_category"] == "FIIs"  # fallback


class TestMapMovimentacao:
    def test_liquidacao_credito_is_compra(self) -> None:
        assert map_movimentacao("Credito", "Transferência - Liquidação") == "compra"

    def test_liquidacao_debito_is_venda(self) -> None:
        assert map_movimentacao("Debito", "Transferência - Liquidação") == "venda"

    def test_compra_venda_direct(self) -> None:
        assert map_movimentacao("Credito", "Compra") == "compra"
        assert map_movimentacao("Debito", "Venda") == "venda"

    def test_income_types(self) -> None:
        assert map_movimentacao("Credito", "Rendimento") == "dividendo"
        assert map_movimentacao("Credito", "Juros Sobre Capital Próprio") == "juros"

    def test_non_cashflow_returns_none(self) -> None:
        assert map_movimentacao("Credito", "Atualização") is None
        assert map_movimentacao("Debito", "Direitos de Subscrição - Não Exercido") is None
        assert map_movimentacao("Credito", "Cessão de Direitos") is None


class TestParseMovimentacao:
    def test_filters_and_maps(self) -> None:
        ops = parse_b3_movimentacao(_ROWS)
        # 5 cashflows (2 linhas non-cashflow descartadas)
        assert len(ops) == 5
        tipos = sorted(o["tipo"] for o in ops)
        assert tipos == ["compra", "compra", "dividendo", "juros", "venda"]

    def test_compra_row(self) -> None:
        ops = parse_b3_movimentacao(_ROWS)
        bbas = next(o for o in ops if o["asset_symbol"] == "BBAS3")
        assert bbas["tipo"] == "compra"
        assert bbas["asset_category"] == "Ações Nacionais"
        assert bbas["quantidade"] == 3
        assert abs(bbas["valor_unitario"] - 20.34) < 0.001
        assert bbas["data_operacao"] == date(2026, 5, 20)
        assert bbas["external_id"]

    def test_venda_row(self) -> None:
        ops = parse_b3_movimentacao(_ROWS)
        petr_venda = next(
            o for o in ops if o["asset_symbol"] == "PETR4" and o["tipo"] == "venda"
        )
        assert petr_venda["quantidade"] == 2

    def test_tesouro_compra(self) -> None:
        ops = parse_b3_movimentacao(_ROWS)
        td = next(o for o in ops if o["asset_symbol"].startswith("Tesouro"))
        assert td["tipo"] == "compra"
        assert td["asset_category"] == "Aposentadoria"
        assert abs(td["quantidade"] - 0.1) < 1e-9

    def test_income_rows(self) -> None:
        ops = parse_b3_movimentacao(_ROWS)
        div = next(o for o in ops if o["tipo"] == "dividendo")
        jcp = next(o for o in ops if o["tipo"] == "juros")
        assert div["asset_symbol"] == "MXRF11"
        assert jcp["asset_symbol"] == "PETR4"


class TestPositionPrices:
    def test_stock_uses_preco_fechamento(self) -> None:
        sheets = {
            "Posição - Ações": [
                ("Produto", "Código de Negociação", "Quantidade",
                 "Preço de Fechamento", "Valor Atualizado"),
                ("BBAS3 - BCO BRASIL", "BBAS3", 37, 20.3, 751.1),
                ("", "", "", "", "Total"),  # linha de total ignorada
            ],
        }
        prices = parse_b3_position_prices(sheets)
        assert abs(prices["BBAS3"] - 20.3) < 0.001
        assert "Total" not in prices

    def test_tesouro_price_is_value_over_qty(self) -> None:
        sheets = {
            "Posição - Tesouro Direto": [
                ("Produto", "Quantidade", "Valor Atualizado"),
                ("Tesouro IPCA+ 2029", 0.15, 564.02),
            ],
        }
        prices = parse_b3_position_prices(sheets)
        # 564.02 / 0.15 = 3760.13
        assert abs(prices["Tesouro IPCA+ 2029"] - 564.02 / 0.15) < 0.01
