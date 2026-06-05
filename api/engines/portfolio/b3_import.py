"""Parser da aba "Movimentação" do relatório B3 -> asset_operations (m2).

Fonte real (Toro/B3 + Tesouro Direto via NU). É a peça reutilizável pela futura
rotina automatizada do Portal do Investidor (exporta o mesmo formato de
"Movimentação"). Converte cada linha de movimentação em uma operação canônica,
descartando eventos que não são cashflow (atualização de posição, subscrição,
cessão de direitos, bonificação, desdobro/grupamento).

Layout da aba (sem cabeçalho, ao chamar parse_b3_movimentacao):
    Entrada/Saída | Data | Movimentação | Produto | Instituição |
    Quantidade | Preço unitário | Valor da Operação

Mapeamento de "Movimentação":
- "Transferência - Liquidação": Credito -> compra; Debito -> venda
- "Compra"/"Venda" (Tesouro Direto): direto
- "Rendimento" -> dividendo ; "Juros Sobre Capital Próprio" -> juros
- demais (Atualização, Direitos de Subscrição, Cessão de Direitos, ...) -> None
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from .migration import operation_hash, parse_date

# Universo conhecido do portfólio (desambigua ETF x FII, ambos terminam em 11).
_ACOES = {"PETR4", "BBAS3", "CMIG4", "ITSA4", "SOJA3", "ALLD3"}
_ETF = {"ACWI11", "GOLD11", "ALUG11", "USDB11", "NASD11"}
_FII = {"MXRF11", "HFOF11", "KNCR11", "BTLG11", "BTLG12"}


def parse_produto(produto: str) -> str:
    """'BBAS3 - BANCO...' -> 'BBAS3'; 'PETR4F - ...' -> 'PETR4'; Tesouro -> nome."""
    head = produto.split(" - ", 1)[0].strip() if " - " in produto else produto.strip()
    # remove sufixo de fracionário (PETR4F -> PETR4), preservando tickers normais
    if len(head) > 1 and head.endswith("F") and head[-2].isdigit():
        head = head[:-1]
    return head


def b3_category(ticker: str) -> str:
    """Categoria canônica do ticker (casa com portfolio_targets/asset_category)."""
    if ticker.startswith("Tesouro"):
        return "Aposentadoria"
    if ticker in _ETF:
        return "ETFs"
    if ticker in _FII:
        return "FIIs"
    if ticker in _ACOES:
        return "Ações Nacionais"
    # fallback: 11 = fundo listado; demais = ação
    return "FIIs" if ticker.endswith("11") else "Ações Nacionais"


def map_movimentacao(entrada_saida: str, movimentacao: str) -> str | None:
    """Tipo de 'Movimentação' B3 -> tipo de asset_operations (None = ignorar)."""
    m = movimentacao.strip().lower()
    es = entrada_saida.strip().lower()
    if m.startswith("transferência - liquidação") or m.startswith(
        "transferencia - liquidacao"
    ):
        return "compra" if es == "credito" else "venda"
    if m == "compra":
        return "compra"
    if m == "venda":
        return "venda"
    if m == "rendimento" or m == "dividendo":
        return "dividendo"
    if "juros sobre capital" in m:
        return "juros"
    # Atualização, Direitos de Subscrição, Cessão de Direitos, Bonificação,
    # Desdobro, Grupamento, Fração... não são cashflow.
    return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "-" or value == "":
        return None
    if isinstance(value, int | float):
        return float(value)
    txt = str(value).strip().replace(" ", "")
    if not txt or txt == "-":
        return None
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return parse_date(str(value))


def parse_b3_movimentacao(rows: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    """Converte linhas de dados da aba Movimentação em operações canônicas.

    `rows` NÃO deve incluir o cabeçalho. Linhas que não representam cashflow
    (ou sem quantidade/preço válidos) são descartadas.
    """
    ops: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 8:
            continue
        entrada, data, movimentacao, produto, _inst, qtd, preco, valor = row[:8]
        if not produto or not movimentacao:
            continue
        tipo = map_movimentacao(str(entrada), str(movimentacao))
        if tipo is None:
            continue
        quantidade = _to_float(qtd)
        valor_unitario = _to_float(preco)
        valor_total = _to_float(valor)
        if quantidade is None or quantidade == 0:
            continue
        if valor_unitario is None:
            if valor_total is None:
                continue
            valor_unitario = valor_total / quantidade
        ticker = parse_produto(str(produto))
        data_operacao = _to_date(data)
        total = valor_total if valor_total is not None else quantidade * valor_unitario
        ops.append(
            {
                "asset_symbol": ticker,
                "asset_category": b3_category(ticker),
                "tipo": tipo,
                "quantidade": quantidade,
                "valor_unitario": valor_unitario,
                "data_operacao": data_operacao,
                "external_id": operation_hash(data_operacao, ticker, tipo, total),
            }
        )
    return ops
