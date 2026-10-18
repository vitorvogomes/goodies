"""Valoração do portfolio numa data (AD-8 — Story 5.2): o construtor por mês que `closing` chama.

- Hoje: posições a preço atual, bloco cripto das carteiras e caixa em corretora (o mesmo número do
  Painel) e o XIRR consolidado de sempre.
- Mês passado (as_of = fim do mês):
  - B3 e Tesouro: o consolidado daquele fim de mês (`broker_position_snapshots`); sem ele, o preço
    do histórico até a data × a quantidade (`market.price_as_of`);
  - caixinhas e CDB: o %CDI do ativo sobre o CDI publicado até a data (`rf.cdi_value`, Story 7.4);
  - outra renda fixa sem preço na data: o aplicado (cobertura "estimada");
  - cripto: a carteira do histórico até a data × o preço até a data; sem histórico, o aplicado do
    bloco (cobertura "estimada").
Posição aberta sem valor sai do valor e do aportado (como no XIRR). A cobertura diz o método.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg

from engines.common.assets import CLASS_BY_CATEGORY, CRYPTO_CATEGORIES, AssetCategory, AssetClass
from engines.common.dates import today_brt
from engines.market import service as market_service
from engines.wallet import service as wallet_service

from . import calc
from .rf import cdi_value, pre_value, rf_cdi_assets, rf_rate_assets
from .xirr import xirr

_CRYPTO = [str(c) for c in CRYPTO_CATEGORIES]
_B3_CLASSES = {AssetClass.ACOES_BR, AssetClass.ETFS, AssetClass.FIIS, AssetClass.APOSENTADORIA}
_CENT = Decimal("0.01")


@dataclass
class PortfolioValuation:
    as_of: date
    by_asset: dict[str, Decimal] = field(default_factory=dict)  # símbolo → valor
    by_class: dict[str, Decimal] = field(default_factory=dict)  # classe (AD-11) → valor
    positions_value: Decimal = Decimal(0)  # sem cripto
    crypto_value: Decimal = Decimal(0)
    broker_cash: Decimal = Decimal(0)  # caixa em corretora (no patrimônio) — Story 7.7
    on_the_way: Decimal = Decimal(0)  # dinheiro a caminho (fora do patrimônio)
    contributed: Decimal = Decimal(0)  # aportado líquido até a data (operações + bloco cripto)
    income: Decimal = Decimal(0)  # proventos até a data
    xirr: float | None = None  # consolidado, desde o início até a data
    coverage: dict[str, str] = field(default_factory=dict)  # fonte → método de valoração
    by_asset_id: dict[str, Decimal] = field(default_factory=dict)  # assets.id → valor (snapshot)
    # Fluxos líquidos do mês por (classe, data), sinal do XIRR (aporte < 0): XIRR de período.
    flows: dict[tuple[str, date], Decimal] = field(default_factory=dict)
    data_as_of: date | None = None
    stale: bool = False

    @property
    def invested(self) -> Decimal:
        return calc.invested_value(
            positions=self.positions_value, crypto=self.crypto_value, broker_cash=self.broker_cash
        )

    @property
    def result(self) -> Decimal:
        return calc.investment_result(
            self.invested, contributed=self.contributed, income=self.income
        )


# Sem preço histórico de algum ativo cripto na data: o bloco vale o aplicado (custo), não o mercado
CRYPTO_ESTIMATED = "estimada (aplicado do bloco)"


def _dec(value: Any) -> Decimal:
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


def _cls(category: str) -> str:
    return str(CLASS_BY_CATEGORY.get(category, AssetClass.ACOES_BR))


async def valuation_as_of(
    conn: asyncpg.Connection, user_id: str, as_of: date
) -> PortfolioValuation:
    from .crypto_sleeve import sleeve_cashflows

    crypto_flows = await sleeve_cashflows(conn)  # uma vez: o passado e os fluxos do mês leem
    if as_of >= today_brt():
        out = await _live(conn, user_id, as_of)
    else:
        out = await _past(conn, user_id, as_of, crypto_flows)
    await _asset_ids(conn, out)
    await _month_flows(conn, user_id, out, crypto_flows)
    return out


async def _asset_ids(conn: asyncpg.Connection, out: PortfolioValuation) -> None:
    rows = await conn.fetch(
        "SELECT DISTINCT ON (symbol) symbol, asset_id::text AS asset_id FROM asset_aliases "
        "WHERE symbol = ANY($1::text[]) ORDER BY symbol, chain",
        list(out.by_asset),
    )
    ids = {r["symbol"]: r["asset_id"] for r in rows}
    for symbol, value in out.by_asset.items():
        if symbol in ids:
            out.by_asset_id[ids[symbol]] = out.by_asset_id.get(ids[symbol], Decimal(0)) + value


async def _month_flows(
    conn: asyncpg.Connection,
    user_id: str,
    out: PortfolioValuation,
    crypto_flows: list[tuple[date, float]],
) -> None:
    start = out.as_of.replace(day=1)
    ops = await conn.fetch(
        "SELECT asset_category, tipo, quantidade, valor_unitario, data_operacao "
        "FROM asset_operations WHERE user_id = $1 AND data_operacao BETWEEN $2 AND $3 "
        "AND asset_category <> ALL($4::text[])",
        user_id,
        start,
        out.as_of,
        _CRYPTO,
    )
    for op in ops:
        if op["tipo"] not in _FLOW_TIPOS:
            continue
        key = (_cls(op["asset_category"]), op["data_operacao"])
        out.flows[key] = out.flows.get(key, Decimal(0)) + _signed(op)
    for day, amount in crypto_flows:
        if start <= day <= out.as_of:
            key = ("cripto", day)
            out.flows[key] = out.flows.get(key, Decimal(0)) + _dec(amount)


async def _broker_cash(
    conn: asyncpg.Connection, user_id: str, as_of: date, out: PortfolioValuation
) -> None:
    """Story 7.7: caixa em corretora (no patrimônio) e a caminho (fora), pelo resíduo."""
    from .brokers import broker_cash_as_of

    brokers = await broker_cash_as_of(conn, user_id, as_of)
    out.broker_cash = sum((b.caixa for b in brokers), Decimal(0))
    out.on_the_way = sum((b.a_caminho for b in brokers), Decimal(0))
    covered = [b.covered_until for b in brokers if b.rail == "B3 (corretoras)" and b.covered_until]
    out.coverage["caixa"] = "resíduo saiu + proventos − aplicado" + (
        f" (B3 até {covered[0]:%d/%m/%Y})" if covered else ""
    )


async def _live(conn: asyncpg.Connection, user_id: str, as_of: date) -> PortfolioValuation:
    from . import service

    snap = await service.portfolio_snapshot(conn, user_id)
    out = PortfolioValuation(as_of=as_of, data_as_of=snap.as_of, stale=snap.stale)
    for p in snap.positions:
        if p["valor_atual"] is None:
            continue
        value = _dec(p["valor_atual"])
        cls = "cripto" if p["asset_category"] in _CRYPTO else _cls(p["asset_category"])
        out.by_asset[p["asset_symbol"]] = value
        out.by_class[cls] = out.by_class.get(cls, Decimal(0)) + value
    out.positions_value = snap.positions_value
    out.crypto_value = snap.crypto_value
    out.contributed = snap.contributed
    out.income = snap.income
    await _broker_cash(conn, user_id, as_of, out)
    out.xirr = (await service.calculate_portfolio_xirr(conn, user_id)).get("consolidated")
    out.coverage.update({"B3": "preço atual", "RF": "CDI real (job rf_cdi)", "cripto": "carteiras"})
    return out


async def _past(
    conn: asyncpg.Connection,
    user_id: str,
    as_of: date,
    all_crypto_flows: list[tuple[date, float]],
) -> PortfolioValuation:
    out = PortfolioValuation(as_of=as_of, data_as_of=as_of)
    ops = await conn.fetch(
        "SELECT asset_symbol, asset_category, tipo, quantidade, valor_unitario, data_operacao "
        "FROM asset_operations WHERE user_id = $1 AND data_operacao <= $2 "
        "AND asset_category <> ALL($3::text[]) ORDER BY data_operacao",
        user_id,
        as_of,
        _CRYPTO,
    )
    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for op in ops:
        by_symbol[op["asset_symbol"]].append(op)
    snapshot = {
        r["symbol"]: r["reported_value"]
        for r in await conn.fetch(
            "SELECT DISTINCT ON (a.symbol) a.symbol, s.reported_value "
            "FROM broker_position_snapshots s JOIN asset_aliases a ON a.asset_id = s.asset_id "
            "WHERE s.ref_date = $1 "
            "AND s.reported_value IS NOT NULL ORDER BY a.symbol",
            as_of,
        )
    }
    b3_method = f"consolidado de {as_of:%d/%m/%Y}" if snapshot else "histórico de preço"
    wallets = await wallet_service.positions_as_of(conn, as_of)
    prices = await market_service.prices_as_of(
        conn, [*by_symbol, *(w["asset_symbol"] for w in wallets)], as_of
    )
    estimated_rf = False
    unpriced: set[str] = set()
    cdi_assets = await rf_cdi_assets(conn)
    rate_assets = await rf_rate_assets(conn)
    rate_valued = False
    cdi_series: list[tuple[date, Decimal]] | None = None
    cdi_until: date | None = None
    cdi_estimated = False
    for symbol, sops in by_symbol.items():
        qty = calc.quantity(sops)
        if qty <= 0:
            continue
        category = sops[0]["asset_category"]
        cls = _cls(category)
        value: Decimal | None
        if cls in _B3_CLASSES:
            if symbol in snapshot:
                value = Decimal(snapshot[symbol])
            else:
                price = prices[symbol]
                value = price.value * qty if price.value is not None else None
        elif symbol in rate_assets:  # Story 7.6: debênture pela taxa cadastrada
            value = pre_value(sops, as_of, *rate_assets[symbol])
            rate_valued = True
        elif symbol in cdi_assets:  # Story 7.4: %CDI do ativo sobre o CDI publicado
            if cdi_series is None:
                cdi_series = await market_service.cdi_daily(conn, date(2000, 1, 1), as_of)
            cdi = cdi_value(sops, as_of, cdi_assets[symbol], cdi_series)
            value = cdi.value
            if cdi.cdi_until is not None:
                cdi_until = max(cdi_until or cdi.cdi_until, cdi.cdi_until)
            cdi_estimated = cdi_estimated or cdi.estimated
        else:
            price = prices[symbol]
            if price.value is not None:
                value = price.value * qty
            else:  # RF sem preço na data (ex.: debênture): o aplicado, estimado
                value = calc.net_contributed(sops)
                estimated_rf = True
        if value is None:
            unpriced.add(symbol)
            out.stale = True
            continue
        value = value.quantize(_CENT)
        out.by_asset[symbol] = value
        out.by_class[cls] = out.by_class.get(cls, Decimal(0)) + value
        out.positions_value += value
    priced_ops = [op for op in ops if op["asset_symbol"] not in unpriced]
    out.contributed = calc.net_contributed(priced_ops)
    out.income = calc.income_received(priced_ops)

    crypto_flows = [(d, a) for d, a in all_crypto_flows if d <= as_of]
    crypto_net = -sum((_dec(a) for _, a in crypto_flows), Decimal(0))
    crypto_value = Decimal(0)
    priced_all = bool(wallets)
    for w in wallets:
        price = prices[w["asset_symbol"]]
        if price.value is None:
            priced_all = False
            break
        crypto_value += price.value * Decimal(w["quantity"])
    if priced_all:
        out.crypto_value = crypto_value.quantize(_CENT)
        crypto_method = "histórico de carteira"
    else:
        out.crypto_value = max(crypto_net, Decimal(0))
        crypto_method = CRYPTO_ESTIMATED
    if out.crypto_value:
        out.by_class["cripto"] = out.crypto_value
    out.contributed += crypto_net

    flows: list[tuple[date, float]] = [
        (op["data_operacao"], float(_signed(op))) for op in priced_ops if op["tipo"] in _FLOW_TIPOS
    ]
    flows += [(d, float(a)) for d, a in crypto_flows]
    terminal = float(out.positions_value + out.crypto_value)
    if terminal > 0:
        flows.append((as_of, terminal))
    rate = xirr(flows) if len(flows) >= 2 else float("nan")
    out.xirr = None if rate != rate else rate  # NaN → sem convergência
    out.coverage.update(
        {
            "B3": b3_method,
            "RF": (
                f"CDI real até {cdi_until:%d/%m/%Y}" if cdi_until else "CDI real sem CDI publicado"
            )
            + (" · dias sem CDI estimados" if cdi_estimated else "")
            + (" · debêntures pela taxa cadastrada" if rate_valued else "")
            + (" + aplicado estimado" if estimated_rf else ""),
            "cripto": crypto_method,
        }
    )
    await _broker_cash(conn, user_id, as_of, out)  # Story 7.7: o caixa daquela data
    return out


_FLOW_TIPOS = frozenset({"compra", "aporte", "venda", "resgate", "dividendo", "juros"})


def _signed(op: Any) -> Decimal:
    total = _dec(op["quantidade"]) * _dec(op["valor_unitario"])
    return -total if op["tipo"] in calc.INFLOW else total


__all__ = ["AssetCategory", "PortfolioValuation", "valuation_as_of"]
