"""Parser da aba "Movimentação" do relatório B3 -> asset_operations (m2).

Fonte real (Toro/B3 + Tesouro Direto via NU). É a peça reutilizável pela futura
rotina automatizada do Portal do Investidor (exporta o mesmo formato de
"Movimentação"). Converte cada linha de movimentação em uma operação canônica,
descartando eventos que não são cashflow (atualização de posição, subscrição,
cessão de direitos, desdobro/grupamento). Bonificação e leilão de fração mudam a quantidade
e entram (Story 7.9).

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

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from engines.common.assets import AssetCategory

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
    """FALLBACK de categoria (allowlist + heurística de sufixo).

    Só deve ser usado quando o ticker NÃO está no mapa derivado das abas 'Posição'
    (`parse_b3_categories`) — ex.: ativo totalmente vendido, sem linha de posição.
    A heurística de sufixo ('11' -> FII) é ambígua (ETFs também terminam em 11), por
    isso o mapa das abas tem precedência em `parse_b3_movimentacao`.
    """
    if ticker.startswith("Tesouro"):
        return AssetCategory.APOSENTADORIA
    if ticker in _ETF:
        return AssetCategory.ETFS
    if ticker in _FII:
        return AssetCategory.FIIS
    if ticker in _ACOES:
        return AssetCategory.ACOES
    # fallback: 11 = fundo listado; demais = ação
    return AssetCategory.FIIS if ticker.endswith("11") else AssetCategory.ACOES


def map_movimentacao(entrada_saida: str, movimentacao: str) -> str | None:
    """Tipo de 'Movimentação' B3 -> tipo de asset_operations (None = ignorar)."""
    m = movimentacao.strip().lower()
    es = entrada_saida.strip().lower()
    if m.startswith("transferência - liquidação") or m.startswith("transferencia - liquidacao"):
        return "compra" if es == "credito" else "venda"
    if m == "compra":
        return "compra"
    if m == "venda":
        return "venda"
    if m == "rendimento" or m == "dividendo":
        return "dividendo"
    if "juros sobre capital" in m:
        return "juros"
    # Eventos corporativos (Story 7.9): a bonificação é compra a custo zero; o leilão de fração é a
    # venda da fração (o dinheiro cai na corretora), então "Fração em Ativos" já está coberta.
    if m.startswith("bonificação em ativos") or m.startswith("bonificacao em ativos"):
        return "compra" if es == "credito" else None
    if m.startswith("leilão de fração") or m.startswith("leilao de fracao"):
        return "venda" if es == "credito" else None
    # Atualização, Direitos de Subscrição, Cessão de Direitos, Desdobro, Grupamento, Fração...
    # não são cashflow.
    return None


def is_corporate_event(movimentacao: str) -> bool:
    m = movimentacao.strip().lower()
    return m.startswith(("bonificação", "bonificacao", "leilão de fração", "leilao de fracao"))


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


def _next_seq(
    seen: dict[tuple[date, str, str, float], int],
    data_operacao: date,
    ticker: str,
    tipo: str,
    total: float,
) -> int:
    """Nº de ocorrência (0-based) de um (data, ticker, tipo, total) idêntico já visto
    no mesmo parse. Determinístico pela ordem das linhas -> re-import é idempotente."""
    key = (data_operacao, ticker, tipo, round(total, 2))
    seq = seen.get(key, 0)
    seen[key] = seq + 1
    return seq


def _to_date(value: Any) -> date:
    # openpyxl (data_only) entrega células de data como datetime; datetime é subclasse
    # de date, então sem este ramo passava cru -> `data_op <= cut`(date) dava TypeError
    # (500) e o isoformat divergia ('T00:00:00'). Normaliza p/ date puro. Achado C1.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return parse_date(str(value))


# Abas de "Posição" do relatório consolidado -> preço unitário atual por ticker.
# (ticker_col, price_col, qty_col): se qty_col != None, preço = valor/quantidade.
_POSITION_SHEETS: dict[str, tuple[str, str, str | None]] = {
    "Posição - Ações": ("Código de Negociação", "Preço de Fechamento", None),
    "Posição - ETF": ("Código de Negociação", "Preço de Fechamento", None),
    "Posição - Fundos": ("Código de Negociação", "Preço de Fechamento", None),
    "Posição - Tesouro Direto": ("Produto", "Valor Atualizado", "Quantidade"),
}


def parse_b3_position_prices(
    sheets: Mapping[str, Sequence[Sequence[Any]]],
) -> dict[str, float]:
    """Extrai preço unitário atual por ticker das abas 'Posição' do consolidado.

    `sheets`: nome da aba -> linhas (incluindo cabeçalho). Linhas de 'Total'/vazias
    são ignoradas. Tesouro Direto: preço = Valor Atualizado / Quantidade.
    """
    prices: dict[str, float] = {}
    for sheet, (tcol, pcol, qcol) in _POSITION_SHEETS.items():
        rows = sheets.get(sheet)
        if not rows:
            continue
        header = [str(h) for h in rows[0]]
        ti = header.index(tcol) if tcol in header else None
        pi = header.index(pcol) if pcol in header else None
        qi = header.index(qcol) if qcol and qcol in header else None
        if ti is None or pi is None:
            continue
        for row in rows[1:]:
            tick = row[ti] if ti < len(row) else None
            if not tick or str(tick).strip().lower().startswith("total"):
                continue
            ticker = str(tick).strip()
            price = _to_float(row[pi]) if pi < len(row) else None
            if qi is not None:
                qty = _to_float(row[qi]) if qi < len(row) else None
                if price is not None and qty:
                    price = price / qty
            if price is not None:
                prices[ticker] = price
    return prices


# Aba 'Posição' -> categoria canônica (as abas já separam Ações/ETF/Fundos/Tesouro).
_SHEET_CATEGORY: dict[str, str] = {
    "Posição - Ações": AssetCategory.ACOES,
    "Posição - ETF": AssetCategory.ETFS,
    "Posição - Fundos": AssetCategory.FIIS,
    "Posição - Tesouro Direto": AssetCategory.APOSENTADORIA,
}


# Aba 'Posição' → (coluna do símbolo, coluna da quantidade, coluna do valor) para o snapshot.
_SNAPSHOT_SHEETS: dict[str, tuple[str, str, str]] = {
    "Posição - Ações": ("Código de Negociação", "Quantidade", "Valor Atualizado"),
    "Posição - ETF": ("Código de Negociação", "Quantidade", "Valor Atualizado"),
    "Posição - Fundos": ("Código de Negociação", "Quantidade", "Valor Atualizado"),
    "Posição - Tesouro Direto": ("Produto", "Quantidade", "Valor Atualizado"),
}


def parse_b3_positions(
    sheets: Mapping[str, Sequence[Sequence[Any]]],
) -> list[dict[str, Any]]:
    """Posições informadas pelo consolidado (Story 3.8): símbolo (como nas operações), categoria
    canônica, quantidade e valor atualizado, uma linha por símbolo (somadas se repetem)."""
    found: dict[str, dict[str, Any]] = {}
    for sheet, (tcol, qcol, vcol) in _SNAPSHOT_SHEETS.items():
        rows = sheets.get(sheet)
        if not rows:
            continue
        header = [str(h) for h in rows[0]]
        if tcol not in header or qcol not in header:
            continue
        ti, qi = header.index(tcol), header.index(qcol)
        vi = header.index(vcol) if vcol in header else None
        for row in rows[1:]:
            tick = row[ti] if ti < len(row) else None
            if not tick or str(tick).strip().lower().startswith("total"):
                continue
            qty = _to_float(row[qi]) if qi < len(row) else None
            if qty is None:
                continue
            value = _to_float(row[vi]) if vi is not None and vi < len(row) else None
            symbol = parse_produto(str(tick))
            item = found.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "category": _SHEET_CATEGORY[sheet],
                    "quantity": 0.0,
                    "value": None,
                },
            )
            item["quantity"] += qty
            if value is not None:
                item["value"] = (item["value"] or 0.0) + value
    return list(found.values())


def parse_b3_categories(
    sheets: Mapping[str, Sequence[Sequence[Any]]],
) -> dict[str, str]:
    """Mapeia ticker -> categoria canônica a partir das abas 'Posição' do consolidado.

    Fonte robusta (vs. heurística de sufixo): cada aba já separa a classe do ativo.
    Reutilizada pela rotina de import (`scripts/import_b3.py`) e pelo worker do
    Market Engine (m3) para classificar com segurança qualquer ticker novo.
    """
    cats: dict[str, str] = {}
    for sheet, category in _SHEET_CATEGORY.items():
        rows = sheets.get(sheet)
        if not rows:
            continue
        tcol = _POSITION_SHEETS[sheet][0]
        header = [str(h) for h in rows[0]]
        ti = header.index(tcol) if tcol in header else None
        if ti is None:
            continue
        for row in rows[1:]:
            tick = row[ti] if ti < len(row) else None
            if not tick or str(tick).strip().lower().startswith("total"):
                continue
            cats[parse_produto(str(tick))] = category
    return cats


def parse_b3_movimentacao(
    rows: Sequence[Sequence[Any]],
    category_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Converte linhas de dados da aba Movimentação em operações canônicas.

    `rows` NÃO deve incluir o cabeçalho. Linhas que não representam cashflow
    (ou sem quantidade/preço válidos) são descartadas. `category_map` (derivado das
    abas 'Posição' via `parse_b3_categories`) tem precedência sobre a heurística
    `b3_category` — evita que um ETF novo terminando em 11 vire FII.
    """
    ops: list[dict[str, Any]] = []
    seen: dict[tuple[date, str, str, float], int] = {}
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
        evento = is_corporate_event(str(movimentacao))
        if evento and tipo == "compra" and valor_unitario is None and valor_total is None:
            valor_unitario = 0.0  # bonificação: ações a custo zero
        if valor_unitario is None:
            if valor_total is None:
                continue
            valor_unitario = valor_total / quantidade
        ticker = parse_produto(str(produto))
        data_operacao = _to_date(data)
        total = valor_total if valor_total is not None else quantidade * valor_unitario
        category = (category_map or {}).get(ticker) or b3_category(ticker)
        seq = _next_seq(seen, data_operacao, ticker, tipo, total)
        ops.append(
            {
                "asset_symbol": ticker,
                "asset_category": category,
                "tipo": tipo,
                "quantidade": quantidade,
                "valor_unitario": valor_unitario,
                "data_operacao": data_operacao,
                "external_id": operation_hash(data_operacao, ticker, tipo, total, seq),
                "evento": evento,  # só a movimentação traz: fora da regra de cobertura
            }
        )
    return ops


def parse_b3_negociacao(
    rows: Sequence[Sequence[Any]],
    category_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Converte linhas da aba "Negociação" (extrato diário/semanal) em operações.

    Layout (cabeçalho tolerado — linhas não-compra/venda são descartadas):
        Data do Negócio | Tipo de Movimentação | Mercado | Prazo/Vencimento |
        Instituição | Código de Negociação | Quantidade | Preço | Valor

    CRÍTICO: usa a **data do negócio** (trade date), enquanto `parse_b3_movimentacao`
    usa a data de liquidação (D+2) na "Transferência - Liquidação". O mesmo trade
    gera `external_id` DIFERENTE entre as duas fontes -> o hash não deduplica entre
    elas; a regra de cobertura por período (no serviço de import) é que evita a
    dupla contagem. `category_map` (abas 'Posição' ou tickers já existentes) tem
    precedência sobre a heurística de sufixo.
    """
    ops: list[dict[str, Any]] = []
    seen: dict[tuple[date, str, str, float], int] = {}
    for row in rows:
        if len(row) < 9:
            continue
        data, tipo_raw, _mercado, _prazo, _inst, codigo, qtd, preco, valor = row[:9]
        if not codigo or not tipo_raw:
            continue
        tipo = map_movimentacao("", str(tipo_raw))
        if tipo not in ("compra", "venda"):  # ignora cabeçalho/totais/outros
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
        ticker = parse_produto(str(codigo))
        data_operacao = _to_date(data)
        total = valor_total if valor_total is not None else quantidade * valor_unitario
        category = (category_map or {}).get(ticker) or b3_category(ticker)
        # fills idênticos no mesmo dia são trades reais distintos (extrato trade-a-trade):
        # a sequência evita que o 2º colida no hash e seja descartado. Achado C3.
        seq = _next_seq(seen, data_operacao, ticker, tipo, total)
        ops.append(
            {
                "asset_symbol": ticker,
                "asset_category": category,
                "tipo": tipo,
                "quantidade": quantidade,
                "valor_unitario": valor_unitario,
                "data_operacao": data_operacao,
                "external_id": operation_hash(data_operacao, ticker, tipo, total, seq),
            }
        )
    return ops
