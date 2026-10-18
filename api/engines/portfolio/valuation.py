"""Valoração do portfolio numa data (AD-8 — Story 5.2): o construtor por mês que `closing` chama.

- Hoje: posições a preço atual, bloco cripto das carteiras e caixa em corretora (o mesmo número do
  Painel) e o XIRR consolidado de sempre.
- Mês passado (as_of = fim do mês):
  - B3 e Tesouro: o consolidado daquele fim de mês (`broker_position_snapshots`); sem ele, o preço
    do histórico até a data × a quantidade (`market.price_as_of`);
  - caixinhas e CDB: o CDI fixo até a data (`caixinhas.compute_value`, método vigente até a 7.4);
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

from config import settings
from engines.common.assets import CLASS_BY_CATEGORY, CRYPTO_CATEGORIES, AssetCategory, AssetClass
from engines.common.dates import today_brt
from engines.market import service as market_service
from engines.wallet import service as wallet_service

from . import calc
from .caixinhas import CAIXINHAS, CDB_GUANABARA, compute_value
from .xirr import xirr

_CRYPTO = [str(c) for c in CRYPTO_CATEGORIES]
_SPECS = {s.symbol: s for s in [*CAIXINHAS, CDB_GUANABARA]}
_B3_CLASSES = {AssetClass.ACOES_BR, AssetClass.ETFS, AssetClass.FIIS, AssetClass.APOSENTADORIA}
_CENT = Decimal("0.01")


@dataclass
class PortfolioValuation:
    as_of: date
    by_asset: dict[str, Decimal] = field(default_factory=dict)  # símbolo → valor
    by_class: dict[str, Decimal] = field(default_factory=dict)  # classe (AD-11) → valor
    positions_value: Decimal = Decimal(0)  # sem cripto
    crypto_value: Decimal = Decimal(0)
    broker_cash: Decimal = Decimal(0)
    contributed: Decimal = Decimal(0)  # aportado líquido até a data (operações + bloco cripto)
    income: Decimal = Decimal(0)  # proventos até a data
    xirr: float | None = None  # consolidado, desde o início até a data
    coverage: dict[str, str] = field(default_factory=dict)  # fonte → método de valoração
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


def _dec(value: Any) -> Decimal:
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


def _cls(category: str) -> str:
    return str(CLASS_BY_CATEGORY.get(category, AssetClass.ACOES_BR))


async def valuation_as_of(
    conn: asyncpg.Connection, user_id: str, as_of: date
) -> PortfolioValuation:
    if as_of >= today_brt():
        return await _live(conn, user_id, as_of)
    return await _past(conn, user_id, as_of)


async def _live(conn: asyncpg.Connection, user_id: str, as_of: date) -> PortfolioValuation:
    from . import service, transit

    snap = await service.portfolio_snapshot(conn, user_id)
    out = PortfolioValuation(as_of=as_of, data_as_of=snap.as_of, stale=snap.stale)
    for p in await service.calculate_positions(conn, user_id):
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
    rails = (await transit.calculate_transit(conn, user_id))["rails"]
    out.broker_cash = sum(
        (_dec(r["caixa_corretora_brl"]) for r in rails if r["caixa_corretora_brl"] > 0), Decimal(0)
    )
    out.xirr = (await service.calculate_portfolio_xirr(conn, user_id)).get("consolidated")
    out.coverage = {"B3": "preço atual", "RF": "CDI fixo", "cripto": "carteiras"}
    return out


async def _past(conn: asyncpg.Connection, user_id: str, as_of: date) -> PortfolioValuation:
    from .crypto_sleeve import sleeve_cashflows

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
    estimated_rf = False
    unpriced: set[str] = set()
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
                price = await market_service.price_as_of(conn, symbol, as_of)
                value = price.value * qty if price.value is not None else None
        elif symbol in _SPECS:
            spec = _SPECS[symbol]
            spec_ops = [dict(op) for op in sops]
            value = _dec(compute_value(spec_ops, as_of, settings.cdi_anual, spec.pct_cdi))
        else:
            price = await market_service.price_as_of(conn, symbol, as_of)
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

    crypto_flows = [(d, a) for d, a in await sleeve_cashflows(conn) if d <= as_of]
    crypto_net = -sum((_dec(a) for _, a in crypto_flows), Decimal(0))
    wallets = await wallet_service.positions_as_of(conn, as_of)
    crypto_value = Decimal(0)
    priced_all = bool(wallets)
    for w in wallets:
        price = await market_service.price_as_of(conn, w["asset_symbol"], as_of)
        if price.value is None:
            priced_all = False
            break
        crypto_value += price.value * Decimal(w["quantity"])
    if priced_all:
        out.crypto_value = crypto_value.quantize(_CENT)
        crypto_method = "histórico de carteira"
    else:
        out.crypto_value = max(crypto_net, Decimal(0))
        crypto_method = "estimada (aplicado do bloco)"
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
    out.coverage = {
        "B3": b3_method,
        "RF": "CDI fixo" + (" + aplicado estimado" if estimated_rf else ""),
        "cripto": crypto_method,
    }
    return out


_FLOW_TIPOS = frozenset({"compra", "aporte", "venda", "resgate", "dividendo", "juros"})


def _signed(op: Any) -> Decimal:
    total = _dec(op["quantidade"]) * _dec(op["valor_unitario"])
    return -total if op["tipo"] in calc.INFLOW else total


__all__ = ["AssetCategory", "PortfolioValuation", "valuation_as_of"]
