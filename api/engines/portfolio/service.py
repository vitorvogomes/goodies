"""Portfolio service — lógica de negócio e orquestração (m2).

Funções puras testáveis (cashflows, rebalanceamento) + orquestração sobre asyncpg.
Cálculos:
- XIRR por ativo, por categoria e consolidado (STORY-02-06) — usa `xirr.py`.
- Posições atuais valoradas com preço manual (STORY-02-07).
- Alocação vs meta (STORY-02-08), rebalanceamento (STORY-02-09),
  rendimentos (STORY-02-10), IR RV (STORY-02-11), IR cripto (STORY-02-12).

Sinais do cashflow (ADR-002 / CLAUDE.md):
- compra/aporte -> saida de caixa (negativo)
- venda/resgate/dividendo/juros -> entrada (positivo)
- posicao atual -> entrada positiva na data de hoje (qtd_net * preco manual)
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from config import settings
from engines.common.assets import CRYPTO_CATEGORIES, AssetCategory
from engines.common.cache import cache, invalidate_xirr_cache, xirr_key
from engines.common.dates import today_brt

# Re-exportados para scripts e testes: o chokepoint de preço mora em `market` (AD-1).
from engines.market.service import clear_manual_price as clear_manual_price
from engines.market.service import upsert_price as upsert_price

from .xirr import xirr

# Categorias valoradas SÓ pelo sleeve/bloco cripto (carteiras) — excluídas do fold
# per-ativo em posições/XIRR p/ não contar 2x (C6). Lista p/ o parâmetro asyncpg.
_CRYPTO_CATS = [str(c) for c in CRYPTO_CATEGORIES]

# Tipos que aumentam posição (entram no DCA e no quantidade_net positivo)
_INFLOW_TIPOS = ("compra", "aporte")
# Tipos que reduzem posição
_OUTFLOW_TIPOS = ("venda", "resgate")
_XIRR_TTL_SECONDS = settings.ttl_xirr  # 1h (ADR-008), configurável


# --------------------------------------------------------------------------- #
# Cashflows / XIRR (funções puras + orquestração)
# --------------------------------------------------------------------------- #
def signed_amount(tipo: str, quantidade: float, valor_unitario: float) -> float:
    """Valor com sinal do cashflow: compra/aporte negativo, demais positivo."""
    total = quantidade * valor_unitario
    return -total if tipo in _INFLOW_TIPOS else total


def net_quantity(ops: Sequence[Any]) -> float:
    """Quantidade liquida: soma(compra,aporte) - soma(venda,resgate)."""
    qty = 0.0
    for op in ops:
        tipo = op["tipo"]
        if tipo in _INFLOW_TIPOS:
            qty += float(op["quantidade"])
        elif tipo in _OUTFLOW_TIPOS:
            qty -= float(op["quantidade"])
    return qty


def build_cashflows(
    ops: Sequence[Any], current_value: float | None, today: date
) -> list[tuple[date, float]]:
    """Constrói a série de cashflows de um conjunto de operações.

    Adiciona a posição atual (valor de mercado) como entrada positiva em `today`
    quando `current_value` é conhecido e positivo.
    """
    flows: list[tuple[date, float]] = [
        (
            op["data_operacao"],
            signed_amount(op["tipo"], float(op["quantidade"]), float(op["valor_unitario"])),
        )
        for op in ops
    ]
    if current_value is not None and current_value > 0:
        flows.append((today, current_value))
    return flows


def _nan_to_none(value: float) -> float | None:
    """XIRR devolve nan para <2 fluxos / não-convergência → None (JSON-safe)."""
    return None if math.isnan(value) else value


def _sum_or_none(values: Sequence[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def eval_date(override: date | None = None) -> date:
    """Data única de avaliação (terminal do XIRR/valoração) — §3.1.

    Precedência: argumento explícito > `settings.evaluation_date` (env EVALUATION_DATE, p/
    reproduzir o gate / relatórios 'as-of') > hoje em BRT (`common.dates.today_brt`).
    """
    return override or settings.evaluation_date or today_brt()


async def fetch_prices(conn: asyncpg.Connection) -> dict[str, float]:
    """Carrega o último preço (BRL) por ticker de asset_prices."""
    rows = await conn.fetch("SELECT ticker, price_brl FROM asset_prices")
    return {row["ticker"]: float(row["price_brl"]) for row in rows}


# --------------------------------------------------------------------------- #
# Posições (STORY-02-07)
# --------------------------------------------------------------------------- #
def _dca_price(ops: Sequence[Any]) -> float:
    """Preço médio ponderado de compra/aporte: Σ(quantidade·valor_unitário)/Σquantidade.

    Fonte ÚNICA do custo-médio em Python (posições + IR cripto). A mesma fórmula está
    expressa em SQL em `operations.calculate_dca_*` (roda no banco, p/ o endpoint /dca).
    Guard: Σquantidade=0 → 0.0.
    """
    qty = sum(float(o["quantidade"]) for o in ops if o["tipo"] in _INFLOW_TIPOS)
    cost = sum(
        float(o["quantidade"]) * float(o["valor_unitario"])
        for o in ops
        if o["tipo"] in _INFLOW_TIPOS
    )
    return cost / qty if qty else 0.0


async def calculate_positions(conn: asyncpg.Connection, user_id: str) -> list[dict[str, Any]]:
    """Posicao atual por ativo, valorada com preco manual (asset_prices).

    Inclui apenas ativos com quantidade liquida > 0 (posicoes abertas).
    Sem preco -> valor_atual/resultado null e stale=true (ADR-004).
    """
    # Exclui categoria Cripto do fold per-ativo: cripto é valorada SÓ pelo sleeve/bloco
    # (carteiras), então uma op Cripto em asset_operations (ex.: registrada p/ o IR-cripto)
    # contaria 2x — uma vez per-ativo e outra no bloco. O IR-cripto lê asset_operations
    # direto, então a op fica preservada. Achado C6.
    ops = await conn.fetch(
        """
        SELECT asset_symbol, asset_category, tipo, quantidade, valor_unitario
        FROM asset_operations
        WHERE user_id = $1 AND asset_category <> ALL($2::text[])
        """,
        user_id,
        _CRYPTO_CATS,
    )
    # Preço + is_manual numa só varredura de asset_prices. is_manual: o front bloqueia a
    # edição quando False (capturado via Market Engine); sem linha → tratado como manual.
    price_rows = await conn.fetch("SELECT ticker, price_brl, is_manual FROM asset_prices")
    prices = {r["ticker"]: float(r["price_brl"]) for r in price_rows}
    manual_map = {r["ticker"]: r["is_manual"] for r in price_rows}

    by_asset: dict[str, list[Any]] = defaultdict(list)
    category_of: dict[str, str] = {}
    for op in ops:
        by_asset[op["asset_symbol"]].append(op)
        category_of[op["asset_symbol"]] = op["asset_category"]

    positions: list[dict[str, Any]] = []
    for sym, aops in by_asset.items():
        qty_net = net_quantity(aops)
        if qty_net <= 0:
            continue
        preco_medio = _dca_price(aops)
        custo_total = preco_medio * qty_net
        price = prices.get(sym)
        valor_atual: float | None = None
        resultado: float | None = None
        resultado_pct: float | None = None
        stale = True
        if price is not None:
            valor_atual = qty_net * price
            resultado = valor_atual - custo_total
            resultado_pct = resultado / custo_total * 100 if custo_total else 0.0
            stale = False
        positions.append(
            {
                "asset_symbol": sym,
                "asset_category": category_of[sym],
                "quantidade_net": qty_net,
                "preco_medio": preco_medio,
                "custo_total": custo_total,
                "preco_atual": price,
                "valor_atual": valor_atual,
                "resultado": resultado,
                "resultado_pct": resultado_pct,
                "stale": stale,
                # sem preço ainda → editável (manual); com preço de mercado → bloqueado
                "is_manual": manual_map.get(sym, True),
            }
        )
    # Fold do sleeve cripto (m4): cripto não vive em asset_operations — agrega wallet/defi
    # por ativo (qtd+preço+valor fiéis; custo None). Import lazy evita o ciclo
    # portfolio.service <-> wallet.service. Alocação/rebalanceamento herdam o valor.
    from .crypto_sleeve import crypto_positions

    positions.extend(await crypto_positions(conn, user_id))
    positions.sort(key=lambda p: str(p["asset_symbol"]))
    return positions


# --------------------------------------------------------------------------- #
# Alocacao atual vs meta (STORY-02-08)
# --------------------------------------------------------------------------- #
TargetsProvider = Callable[[asyncpg.Connection, str], Awaitable[dict[str, float]]]
_targets_provider: TargetsProvider | None = None


def register_targets_provider(provider: TargetsProvider) -> None:
    """Story 8.2: a meta vigente por rótulo legado de classe vem de `planning`."""
    global _targets_provider
    _targets_provider = provider


async def calculate_allocation(conn: asyncpg.Connection, user_id: str) -> dict[str, Any]:
    """Alocacao atual (valor de mercado) vs meta por categoria + desvio em pp.

    Categorias = uniao das categorias com posicao e das metas seedadas.
    `pct_meta`/`desvio_pp` ficam null para categorias sem meta definida.
    """
    positions = await calculate_positions(conn, user_id)
    # Story 8.2: as metas são de `planning` (registrado em main.py — AD-1)
    target_map = await _targets_provider(conn, user_id) if _targets_provider else {}

    value_by_cat: dict[str, float] = defaultdict(float)
    for pos in positions:
        if pos["valor_atual"] is not None:
            value_by_cat[pos["asset_category"]] += float(pos["valor_atual"])
    total = sum(value_by_cat.values())

    categories: list[dict[str, Any]] = []
    for cat in sorted(set(value_by_cat) | set(target_map)):
        valor = value_by_cat.get(cat, 0.0)
        pct_atual = valor / total * 100 if total else 0.0
        pct_meta = target_map.get(cat)
        desvio_pp = pct_atual - pct_meta if pct_meta is not None else None
        categories.append(
            {
                "category": cat,
                "valor_atual": valor,
                "pct_atual": pct_atual,
                "pct_meta": pct_meta,
                "desvio_pp": desvio_pp,
            }
        )
    return {"total": total, "categories": categories}


# --------------------------------------------------------------------------- #
# Rebalanceamento (STORY-02-09)
# --------------------------------------------------------------------------- #
def suggest_rebalancing(
    value_by_cat: dict[str, float],
    target_map: dict[str, float],
    contribution: float,
) -> dict[str, float]:
    """Distribui `contribution` para as categorias abaixo do alvo (nunca vende).

    Pseudocodigo da Arquitetura secao 7: gap = meta% * (total+aporte) - valor_atual;
    so categorias com gap positivo recebem aporte, proporcional ao gap.
    Retorna {} quando nao ha gap positivo (tudo no alvo/acima) ou aporte <= 0.
    """
    if contribution <= 0:
        return {}
    total = sum(value_by_cat.values()) + contribution
    gaps = {cat: pct / 100 * total - value_by_cat.get(cat, 0.0) for cat, pct in target_map.items()}
    positive = {cat: gap for cat, gap in gaps.items() if gap > 0}
    total_gap = sum(positive.values())
    if total_gap <= 0:
        return {}
    return {cat: contribution * gap / total_gap for cat, gap in positive.items()}




async def invalidate_xirr_for_ticker(conn: asyncpg.Connection, ticker: str) -> None:
    """Invalida o cache de XIRR de todo usuário que detém `ticker` (preço mudou).

    Inclui quem detém o ticker SÓ nas carteiras (wallet_positions/defi_positions): o sleeve
    cripto (m4) valora pelo mesmo preço, então uma cotação nova de cripto também o afeta —
    senão o XIRR consolidado/Cripto ficaria stale até o TTL (1h).
    """
    rows = await conn.fetch(
        "SELECT user_id FROM asset_operations WHERE asset_symbol = $1 "
        "UNION SELECT user_id FROM wallet_positions WHERE asset_symbol = $1 "
        "UNION SELECT user_id FROM defi_positions WHERE asset_symbol = $1",
        ticker,
    )
    for row in rows:
        await invalidate_xirr_cache(str(row["user_id"]))


async def calculate_portfolio_xirr(
    conn: asyncpg.Connection, user_id: str, today: date | None = None
) -> dict[str, Any]:
    """XIRR por ativo, por categoria e consolidado. Cacheado 1h (ADR-008)."""
    cached = await cache().get(xirr_key(user_id))
    if cached is not None:
        return dict(cached)

    today = eval_date(today)
    # Exclui Cripto do fold per-ativo: o sleeve folda Cripto no by_category/consolidado
    # mais abaixo (valor das carteiras). Sem isto, uma op Cripto em asset_operations entra
    # 2x no consolidado (per-ativo + sleeve). IR-cripto lê asset_operations à parte. C6.
    ops = await conn.fetch(
        """
        SELECT asset_symbol, asset_category, tipo, quantidade, valor_unitario,
               data_operacao
        FROM asset_operations
        WHERE user_id = $1 AND asset_category <> ALL($2::text[])
        ORDER BY data_operacao
        """,
        user_id,
        _CRYPTO_CATS,
    )
    prices = await fetch_prices(conn)

    by_asset_ops: dict[str, list[Any]] = defaultdict(list)
    by_cat_ops: dict[str, list[Any]] = defaultdict(list)
    for op in ops:
        by_asset_ops[op["asset_symbol"]].append(op)
        by_cat_ops[op["asset_category"]].append(op)

    # Por ativo + valor atual de cada ativo (qtd_net * preco manual)
    by_asset: dict[str, float | None] = {}
    asset_current: dict[str, float | None] = {}
    for sym, aops in by_asset_ops.items():
        price = prices.get(sym)
        cur = net_quantity(aops) * price if price is not None else None
        asset_current[sym] = cur
        by_asset[sym] = _nan_to_none(xirr(build_cashflows(aops, cur, today)))

    # §2.1: posição ABERTA sem preço não pode ser valorada — excluí-la inteiramente do
    # cashflow agregado (senão as compras entram como saída sem valor terminal e a taxa
    # despenca). Posição FECHADA (net<=0) permanece: seus fluxos realizados são válidos.
    unpriced_open = {
        sym
        for sym, aops in by_asset_ops.items()
        if prices.get(sym) is None and net_quantity(aops) > 0
    }

    # Por categoria (soma dos valores atuais dos ativos valoráveis da categoria)
    by_category: dict[str, float | None] = {}
    for cat, cops in by_cat_ops.items():
        cat_ops = [op for op in cops if op["asset_symbol"] not in unpriced_open]
        if not cat_ops:
            by_category[cat] = None
            continue
        syms = {op["asset_symbol"] for op in cat_ops}
        cat_cur = _sum_or_none([asset_current.get(s) for s in syms])
        by_category[cat] = _nan_to_none(xirr(build_cashflows(cat_ops, cat_cur, today)))

    # Consolidado (exclui as posições abertas sem preço)
    incl_ops = [op for op in ops if op["asset_symbol"] not in unpriced_open]
    incl_syms = set(by_asset_ops) - unpriced_open
    total_cur = _sum_or_none([asset_current.get(s) for s in incl_syms])
    incl_flows = build_cashflows(incl_ops, total_cur, today)
    consolidated = _nan_to_none(xirr(incl_flows))

    # Sleeve cripto (m4): cashflows do ledger + valor atual das carteiras (não vem de
    # asset_operations). Folda Cripto no by_category e no consolidado. Import lazy evita o
    # ciclo portfolio.service <-> wallet.service.
    from .crypto_sleeve import sleeve_cashflows, sleeve_current_value

    sleeve_flows = await sleeve_cashflows(conn)
    sleeve_cur = (await sleeve_current_value(conn, user_id)).total_brl
    sleeve_terminal = [(today, sleeve_cur)] if sleeve_cur > 0 else []
    if sleeve_flows or sleeve_terminal:
        by_category[str(AssetCategory.CRIPTO)] = _nan_to_none(xirr(sleeve_flows + sleeve_terminal))
        consolidated = _nan_to_none(xirr(incl_flows + sleeve_flows + sleeve_terminal))

    result: dict[str, Any] = {
        "consolidated": consolidated,
        "by_category": by_category,
        "by_asset": by_asset,
        "calculated_at": datetime.now(tz=UTC).isoformat(),
    }
    await cache().set(xirr_key(user_id), result, _XIRR_TTL_SECONDS)
    return result


# --------------------------------------------------------------------------- #
# Retrato do portfolio para o Painel (Story 4.1 — AD-7)
# --------------------------------------------------------------------------- #
STALE_AFTER_DAYS = 3  # preço diário (B3/Tesouro) + fim de semana


@dataclass(frozen=True)
class PortfolioSnapshot:
    positions_value: Decimal  # posições (sem cripto) a preço atual
    crypto_value: Decimal  # bloco cripto (carteiras)
    contributed: Decimal  # aportado líquido: operações + bloco cripto (ledger)
    income: Decimal  # proventos recebidos
    as_of: date | None  # o mais antigo entre preços das posições e scan das carteiras
    stale: bool  # alguma posição sem preço
    prices_as_of: date | None = None  # Bloco Fontes "Preços": a mesma data do patrimônio
    wallets_as_of: date | None = None
    # todas as posições de `calculate_positions` (com o bloco cripto): quem precisa delas não
    # recalcula (revisão do Épico 5)
    positions: list[dict[str, Any]] = field(default_factory=list)


async def portfolio_snapshot(conn: asyncpg.Connection, user_id: str) -> PortfolioSnapshot:
    from engines.wallet.service import oldest_scan

    from . import calc
    from .crypto_sleeve import sleeve_cost_basis, sleeve_current_value

    ops = await conn.fetch(
        "SELECT asset_symbol, tipo, quantidade, valor_unitario FROM asset_operations "
        "WHERE user_id = $1 AND asset_category <> ALL($2::text[])",
        user_id,
        _CRYPTO_CATS,
    )
    all_positions = await calculate_positions(conn, user_id)
    positions = [p for p in all_positions if p["asset_category"] not in _CRYPTO_CATS]
    stale = any(p["valor_atual"] is None for p in positions)
    # Posição aberta sem preço sai dos dois lados (como no XIRR): sem valor terminal, o aportado
    # dela derrubaria o resultado.
    unpriced = {p["asset_symbol"] for p in positions if p["valor_atual"] is None}
    ops = [op for op in ops if op["asset_symbol"] not in unpriced]
    positions_value = sum(
        (Decimal(repr(p["valor_atual"])) for p in positions if p["valor_atual"] is not None),
        Decimal(0),
    )
    sleeve = await sleeve_current_value(conn, user_id)
    cost = await sleeve_cost_basis(conn)
    # Preço manual não envelhece (ADR-012): a data é a do preço de mercado mais antigo das
    # posições abertas. Datas no fuso de Brasília (o run das 22h de BRT é do mesmo dia).
    prices_at = await conn.fetchval(
        "SELECT min(fetched_at) FROM asset_prices WHERE ticker = ANY($1::text[]) "
        "AND NOT is_manual",
        [p["asset_symbol"] for p in positions if p["valor_atual"] is not None],
    )
    scan_at = await oldest_scan(conn)
    prices_as_of = today_brt(prices_at) if prices_at else None
    wallets_as_of = today_brt(scan_at) if scan_at else None
    known = [d for d in (prices_as_of, wallets_as_of) if d is not None]
    oldest = min(known) if known else None
    # API externa falhando: o valor segue com o último preço, marcado defasado (nunca erro).
    lagging = oldest is not None and (today_brt() - oldest).days > STALE_AFTER_DAYS
    return PortfolioSnapshot(
        positions_value=positions_value,
        crypto_value=Decimal(repr(sleeve.total_brl)),
        contributed=calc.net_contributed(ops) + Decimal(repr(cost["net_invested_brl"])),
        income=calc.income_received(ops),
        as_of=oldest,
        stale=stale or sleeve.stale or lagging,
        prices_as_of=prices_as_of,
        wallets_as_of=wallets_as_of,
        positions=all_positions,
    )


async def close_checks(conn: asyncpg.Connection, month: date) -> list[dict[str, str]]:
    """Precondição do fechamento (Story 5.3): sem o consolidado B3 daquele fim de mês, a B3 é
    valorada pelo histórico de preço; com dinheiro a caminho (7.7), o patrimônio fecha sem ele —
    ambos pedem "fechar mesmo assim"."""
    from engines.common.alerts import brl
    from engines.common.assets import B3_CATEGORIES, TREASURY_CATEGORIES
    from engines.common.dates import month_end, month_label
    from engines.common.owner import get_owner_id

    from .brokers import broker_cash_as_of

    end = month_end(month)
    found: list[dict[str, str]] = []
    has = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM broker_position_snapshots WHERE ref_date = $1)", end
    )
    # sem posição na B3 no fim do mês, não há o que o consolidado conferir
    held = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM (SELECT asset_symbol, sum(CASE WHEN tipo IN "
        "('compra', 'aporte') THEN quantidade WHEN tipo IN ('venda', 'resgate') THEN -quantidade "
        "ELSE 0 END) AS q FROM asset_operations WHERE data_operacao <= $1 "
        "AND asset_category = ANY($2::text[]) GROUP BY asset_symbol) x WHERE x.q > 0)",
        end,
        sorted(B3_CATEGORIES | TREASURY_CATEGORIES),
    )
    if not has and held:
        found.append(
            {
                "code": "consolidado_ausente",
                "kind": "confirma",
                "message": f"Consolidado B3 de {month_label(month)} não importado: a B3 do mês "
                "vale pelo histórico de preço.",
            }
        )
    # Story 7.7: dinheiro a caminho no fim do mês (o patrimônio fecha sem ele)
    for b in await broker_cash_as_of(conn, await get_owner_id(conn), end):
        if b.a_caminho > 0:
            found.append(
                {
                    "code": "dinheiro_a_caminho",
                    "kind": "confirma",
                    "message": f"{brl(b.a_caminho)} a caminho da {b.name} no fim de "
                    f"{month_label(month)}.",
                }
            )
    return found


async def consolidado_dates(conn: asyncpg.Connection) -> set[date]:
    """Datas de referência dos consolidados B3 já importados (snapshots de posição)."""
    rows = await conn.fetch("SELECT DISTINCT ref_date FROM broker_position_snapshots")
    return {r["ref_date"] for r in rows}
