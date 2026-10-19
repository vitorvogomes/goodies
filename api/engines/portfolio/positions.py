"""Posições em dois níveis (Story 7.1 — FR-21, FR-27): classe → ativo com o aplicado e o valor no
fim do mês e o resultado do período da leitura (`calc.period_result`; desde o início,
`calc.investment_result`). A valoração é a de `valuation_as_of` (a mesma do fechamento, AD-8).

Cripto é um bloco (memória crypto-as-bucket): quanto saiu (ledger) × quanto vale (carteiras); os
ativos aparecem só com o valor, nunca com custo ou resultado inventado.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import asyncpg
from pydantic import BaseModel, Field

from engines.common.assets import CLASS_BY_CATEGORY, CRYPTO_CATEGORIES, AssetClass
from engines.common.dates import month_end, today_brt
from engines.common.models import Valued
from engines.common.money import Money, Pct
from engines.market import service as market_service
from engines.wallet import service as wallet_service

from . import calc
from .rf import rf_cdi_assets, rf_rate_assets
from .valuation import CRYPTO_ESTIMATED, PortfolioValuation, valuation_as_of

STALE_AFTER_DAYS = 3  # preço diário + fim de semana (o mesmo do Painel)
_CRYPTO = [str(c) for c in CRYPTO_CATEGORIES]
_CENT = Decimal("0.01")
CLASS_ORDER = (
    (AssetClass.ACOES_BR, "Ações Nacionais"),
    (AssetClass.ETFS, "ETFs"),
    (AssetClass.FIIS, "FIIs"),
    (AssetClass.RENDA_FIXA, "Renda Fixa"),
    (AssetClass.APOSENTADORIA, "Aposentadoria"),
    (AssetClass.CRIPTO, "Bloco cripto: quanto saiu × quanto vale"),
)


def _pct_label(pct: Decimal) -> str:
    """117.5 → "117,5"; 100 → "100"."""
    return f"{pct.normalize():f}".replace(".", ",")


def _plain(d: Decimal) -> Decimal:
    """Sem zeros à direita e sem notação científica (10 → "10", não "1E+1")."""
    return d.quantize(Decimal(1)) if d == d.to_integral_value() else d.normalize()


def _before_first() -> Valued[Decimal]:
    return Valued[Decimal](unavailable_reason="antes_do_primeiro_fechamento")


class PositionAsset(BaseModel):
    symbol: str
    asset_id: str | None = None  # Story 8.3: a meta por ativo e o vínculo a objetivo
    aplicado: Money | None  # None no bloco cripto (custo por ativo não é conhecido)
    valor: Valued[Decimal]  # "preço de dd/mm/aaaa" = as_of + stale; sem preço → sem_preco
    resultado: Money | None
    manual: bool = False
    # o resultado desde o primeiro aporte (valor − aplicado + proventos), ao
    # lado do resultado do período; no bloco cripto, None por ativo (custo por ativo não existe)
    resultado_total: Money | None = None
    valor_usd: Money | None = None  # cripto: o valor em dólar (como nas carteiras)
    # P9: quantidade e preço unitário na data (B3, Tesouro e cripto; caixinha/CDB/debênture não)
    quantidade: Decimal | None = None
    preco: Decimal | None = None
    xirr_mensal: Decimal | None = None  # % a.m. do período (Story 7.3); o bloco cripto não tem
    nota: str | None = None  # RF pelo CDI: "{x}% do CDI · CDI até dd/mm/aaaa" (Story 7.4)
    # Story 8.3 (preenchidos por `planning`): % do ativo na classe × meta do ativo, desvio em p.p.
    alocacao: Pct | None = None
    meta: Pct | None = None
    desvio_pp: Pct | None = None


class PositionClass(BaseModel):
    key: str
    label: str
    is_bucket: bool
    aplicado: Money | None
    valor: Money
    resultado: Money | None
    assets: list[PositionAsset]
    resultado_total: Money | None = None  # desde o primeiro aporte; cripto: quanto vale − saiu
    valor_usd: Money | None = None  # bloco cripto em dólar
    xirr_mensal: Pct | None = None  # o XIRR nominal da classe ao mês (preenchido por `closing`)
    # Story 7.3: XIRR do período da classe (% a.a.), nominal e real — preenchidos por `closing`
    xirr_nominal: Valued[Decimal] = Field(default_factory=lambda: _before_first())
    xirr_real: Valued[Decimal] = Field(default_factory=lambda: _before_first())
    # Story 8.3 (preenchidos por `planning`): % da classe na base (sem os objetivos) × meta ± banda
    alocacao: Pct | None = None
    meta: Pct | None = None
    banda: Pct | None = None
    desvio_pp: Pct | None = None
    fora_banda: bool = False


def _dec(value: Any) -> Decimal:
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


async def _live_prices(conn: asyncpg.Connection, symbols: list[str]) -> dict[str, Any]:
    rows = await conn.fetch(
        "SELECT ticker, fetched_at, is_manual FROM asset_prices WHERE ticker = ANY($1::text[])",
        symbols,
    )
    return {r["ticker"]: r for r in rows}


async def _asset_ids(conn: asyncpg.Connection) -> dict[tuple[str, str], str]:
    """(classe, símbolo) → assets.id (o `price_ref` é o símbolo das operações e dos preços)."""
    rows = await conn.fetch("SELECT id::text AS id, class, price_ref FROM assets")
    return {(r["class"], r["price_ref"]): r["id"] for r in rows}


async def _crypto_assets(
    conn: asyncpg.Connection, owner: str, as_of: date, live: bool
) -> list[PositionAsset]:
    found: dict[str, Decimal] = defaultdict(Decimal)
    usd: dict[str, Decimal] = defaultdict(Decimal)
    qty: dict[str, Decimal] = defaultdict(Decimal)  # P9: quantidade somada das carteiras
    manual: dict[str, date] = {}  # Story 7.8: posição manual → a data informada
    if live:
        for w in await wallet_service.list_wallet_positions(conn, owner):
            if w["value_brl"] is not None:
                found[w["asset_symbol"]] += _dec(w["value_brl"])
                qty[w["asset_symbol"]] += _dec(w["quantity"])
                if w.get("value_usd") is not None:
                    usd[w["asset_symbol"]] += _dec(w["value_usd"])
            if w["is_manual"]:
                manual[w["asset_symbol"]] = date.fromisoformat(w["scanned_at"][:10])
        for d in await wallet_service.manual_positions(conn, owner):
            if d["kind"] == "defi" and d["is_active"] and d["as_of"] is not None:
                manual.setdefault(d["asset_symbol"], d["as_of"])
        for d in await wallet_service.list_defi_valued(conn, owner):
            if d["value_brl"] is not None:
                found[d["asset_symbol"]] += _dec(d["value_brl"])
                qty[d["asset_symbol"]] += _dec(d["balance"])
                if d.get("value_usd") is not None:
                    usd[d["asset_symbol"]] += _dec(d["value_usd"])
    else:
        wallets = await wallet_service.positions_as_of(conn, as_of)
        prices = await market_service.prices_as_of(
            conn, [w["asset_symbol"] for w in wallets], as_of
        )
        for w in wallets:
            price = prices[w["asset_symbol"]].value
            if price is not None:
                found[w["asset_symbol"]] += price * _dec(w["quantity"])
                qty[w["asset_symbol"]] += _dec(w["quantity"])
    ids = await _asset_ids(conn)
    return [
        PositionAsset(
            symbol=s,
            asset_id=ids.get((str(AssetClass.CRIPTO), s)),
            aplicado=None,
            valor=Valued[Decimal](
                value=v.quantize(_CENT),
                as_of=manual.get(s, as_of),
                source="manual" if s in manual else "carteiras",
            ),
            resultado=None,
            valor_usd=usd[s].quantize(_CENT) if usd.get(s) else None,
            quantidade=_plain(qty[s].quantize(Decimal("1e-8"))) if qty.get(s) else None,
            preco=_plain((v / qty[s]).quantize(Decimal("0.00000001"))) if qty.get(s) else None,
            manual=s in manual,
            nota=f"informado em {manual[s]:%d/%m/%Y}" if s in manual else None,
        )
        for s, v in sorted(found.items(), key=lambda i: -i[1])
    ]


async def positions_period(
    conn: asyncpg.Connection,
    owner: str,
    start: date | None,
    end: date,
    set_aside: frozenset[str] = frozenset(),
) -> list[PositionClass]:
    """`start` = 1º mês do período (None = desde o início); `end` = mês do Seletor de período.
    `set_aside` (Story 8.3): ativos que saem das classes para o bloco "Objetivos" (quem diz quais
    são é `planning`, AD-11) — seguem no patrimônio."""
    from .crypto_sleeve import sleeve_cashflows

    today = today_brt()
    as_of = min(month_end(end), today)
    live = as_of >= today
    end_val = await valuation_as_of(conn, owner, as_of)
    start_val: PortfolioValuation | None = None
    start_day = start - timedelta(days=1) if start is not None else None
    if start_day is not None:
        start_val = await valuation_as_of(conn, owner, start_day)
    ops = await conn.fetch(
        "SELECT asset_symbol, asset_category, tipo, quantidade, valor_unitario, data_operacao "
        "FROM asset_operations WHERE user_id = $1 AND data_operacao <= $2 "
        "AND asset_category <> ALL($3::text[]) ORDER BY data_operacao",
        owner,
        as_of,
        _CRYPTO,
    )
    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for op in ops:
        by_symbol[op["asset_symbol"]].append(op)
    prices = await _live_prices(conn, list(by_symbol)) if live else {}
    cdi_assets = await rf_cdi_assets(conn)
    rate_assets = await rf_rate_assets(conn)
    cdi_until = (
        await conn.fetchval(
            "SELECT max(ref_date) FROM benchmark_data WHERE series = 'CDI' AND ref_date <= $1",
            as_of,
        )
        if cdi_assets
        else None
    )

    assets_by_class: dict[str, list[PositionAsset]] = defaultdict(list)
    ids = await _asset_ids(conn)
    for symbol, sops in by_symbol.items():
        # vendida no período: entra com valor 0 e o resultado do período; antes dele, fora
        closed = calc.quantity(sops) <= 0
        if closed and (start is None or all(op["data_operacao"] < start for op in sops)):
            continue
        cls = str(CLASS_BY_CATEGORY.get(sops[0]["asset_category"], AssetClass.ACOES_BR))
        aplicado = Decimal(0) if closed else calc.net_contributed(sops).quantize(_CENT)
        value = Decimal(0) if closed else end_val.by_asset.get(symbol)
        price = prices.get(symbol)
        price_day = today_brt(price["fetched_at"]) if price is not None else None
        manual = bool(price is not None and price["is_manual"])
        if value is None:
            valor = Valued[Decimal](unavailable_reason="sem_preco", as_of=as_of)
        else:
            stale = (
                live
                and not manual
                and price_day is not None
                and (today - price_day).days > STALE_AFTER_DAYS
            )
            valor = Valued[Decimal](
                value=value, as_of=price_day if live and price_day else as_of, stale=stale
            )
        resultado: Decimal | None = None
        if value is not None:
            if start is None or start_val is None:
                resultado = calc.investment_result(
                    value, contributed=aplicado, income=calc.income_received(sops)
                )
            else:
                in_period = [op for op in sops if op["data_operacao"] >= start]
                before = [op for op in sops if op["data_operacao"] < start]
                held = calc.quantity(before) > 0
                value_start = start_val.by_asset.get(symbol)
                if not held or value_start is not None:
                    resultado = calc.period_result(
                        value,
                        value_start or Decimal(0),
                        flows=calc.net_contributed(in_period),
                        income=calc.income_received(in_period),
                    )
        resultado_total = (
            calc.investment_result(
                value, contributed=calc.net_contributed(sops), income=calc.income_received(sops)
            ).quantize(_CENT)
            if value is not None
            else None
        )
        xirr_mensal: Decimal | None = None
        if value is not None and not closed and cls != AssetClass.CRIPTO:
            in_period = [op for op in sops if start is None or op["data_operacao"] >= start]
            held_before = (
                start is not None
                and calc.quantity([op for op in sops if op["data_operacao"] < start]) > 0
            )
            value_start = start_val.by_asset.get(symbol) if start_val is not None else None
            if not held_before or value_start is not None:
                rate = calc.period_xirr(
                    value_start or Decimal(0),
                    start_day or as_of,
                    [(op["data_operacao"], calc.signed_flow(op)) for op in in_period],
                    value,
                    as_of,
                )
                if rate is not None:
                    xirr_mensal = (Decimal(repr(calc.monthly_rate(rate))) * 100).quantize(_CENT)
        qty = Decimal(0) if closed else Decimal(str(calc.quantity(sops))).quantize(Decimal("1e-8"))
        unit = (
            (value / qty).quantize(Decimal("0.00000001"))
            if value is not None
            and qty > 0
            and symbol not in cdi_assets
            and symbol not in rate_assets
            and cls != AssetClass.RENDA_FIXA
            else None
        )
        assets_by_class[cls].append(
            PositionAsset(
                symbol=symbol,
                asset_id=ids.get((cls, symbol)),
                aplicado=aplicado,
                quantidade=None if cls == AssetClass.RENDA_FIXA else _plain(qty),
                preco=_plain(unit) if unit is not None else None,
                valor=valor,
                resultado=resultado.quantize(_CENT) if resultado is not None else None,
                resultado_total=resultado_total,
                manual=manual and symbol not in cdi_assets,
                xirr_mensal=xirr_mensal,
                nota=(
                    "vendida no período"
                    if closed
                    else f"{_pct_label(cdi_assets[symbol])}% do CDI · CDI até "
                    + (f"{cdi_until:%d/%m/%Y}" if cdi_until else "—")
                    if symbol in cdi_assets
                    else "valorada pela taxa cadastrada"
                    if symbol in rate_assets
                    else None
                ),
            )
        )

    # Bloco cripto: quanto saiu (ledger, sinal do XIRR: aporte < 0) × quanto vale (carteiras).
    flows = await sleeve_cashflows(conn)
    crypto_out = -sum((_dec(a) for d, a in flows if d <= as_of), Decimal(0))
    crypto_value = end_val.crypto_value
    crypto_result: Decimal | None
    if start is None or start_val is None:
        crypto_result = calc.investment_result(
            crypto_value, contributed=crypto_out, income=Decimal(0)
        )
    elif CRYPTO_ESTIMATED in (start_val.coverage.get("cripto"), end_val.coverage.get("cripto")):
        crypto_result = (
            None  # início pelo aplicado (sem preço histórico): o resultado seria fabricado
        )
    else:
        crypto_result = calc.period_result(
            crypto_value,
            start_val.crypto_value,
            flows=-sum((_dec(a) for d, a in flows if start <= d <= as_of), Decimal(0)),
            income=Decimal(0),
        )

    aside = [a for assets in assets_by_class.values() for a in assets if a.asset_id in set_aside]
    for cls_key in list(assets_by_class):
        assets_by_class[cls_key] = [
            a for a in assets_by_class[cls_key] if a.asset_id not in set_aside
        ]
    out: list[PositionClass] = []
    crypto_assets = await _crypto_assets(conn, owner, as_of, live)
    for key, label in CLASS_ORDER:
        if key == AssetClass.CRIPTO:
            out.append(
                PositionClass(
                    key=str(key),
                    label=label,
                    is_bucket=True,
                    aplicado=crypto_out.quantize(_CENT),
                    valor=crypto_value.quantize(_CENT),
                    resultado=crypto_result.quantize(_CENT) if crypto_result is not None else None,
                    resultado_total=(crypto_value - crypto_out).quantize(_CENT),
                    assets=crypto_assets,
                    valor_usd=(
                        sum((a.valor_usd for a in crypto_assets if a.valor_usd), Decimal(0))
                        if any(a.valor_usd for a in crypto_assets)
                        else None
                    ),
                )
            )
            continue
        assets = sorted(
            assets_by_class.get(str(key), []),
            key=lambda a: -(a.valor.value if a.valor.value is not None else Decimal(-1)),
        )
        results = [a.resultado for a in assets]
        out.append(
            PositionClass(
                key=str(key),
                label=label,
                is_bucket=False,
                aplicado=sum((a.aplicado or Decimal(0) for a in assets), Decimal(0)),
                valor=sum((a.valor.value or Decimal(0) for a in assets), Decimal(0)),
                resultado=(
                    sum((r for r in results if r is not None), Decimal(0))
                    if all(r is not None for r in results)
                    else None
                ),
                resultado_total=_sum_total(assets),
                assets=assets,
            )
        )
    if aside:
        out.append(_block(GOALS_BLOCK, "Objetivos", aside))
    return out


GOALS_BLOCK = "objetivos"


def _block(key: str, label: str, assets: list[PositionAsset]) -> PositionClass:
    results = [a.resultado for a in assets]
    return PositionClass(
        key=key,
        label=label,
        is_bucket=False,
        aplicado=sum((a.aplicado or Decimal(0) for a in assets), Decimal(0)),
        valor=sum((a.valor.value or Decimal(0) for a in assets), Decimal(0)),
        resultado=(
            sum((r for r in results if r is not None), Decimal(0))
            if all(r is not None for r in results)
            else None
        ),
        resultado_total=_sum_total(assets),
        assets=assets,
    )


def _sum_total(assets: list[PositionAsset]) -> Decimal | None:
    totals = [a.resultado_total for a in assets]
    return sum((t for t in totals if t is not None), Decimal(0)) if totals else Decimal(0)


async def month_contributions(
    conn: asyncpg.Connection, owner: str, month: date
) -> tuple[dict[str, Decimal], Decimal]:
    """Story 8.7: o que virou ativo no mês — o que entrou em cada ativo (compras e aportes, por
    assets.id) e, no bloco cripto, o que saiu para as carteiras no mês. Só entradas: o realizado
    total (o investimento do ledger) não abate resgates, que são receita (ADR-015)."""
    from .crypto_sleeve import sleeve_cashflows

    end = month_end(month)
    rows = await conn.fetch(
        "SELECT asset_id::text AS asset_id, tipo, quantidade, valor_unitario FROM asset_operations "
        "WHERE user_id = $1 AND data_operacao BETWEEN $2 AND $3 AND asset_id IS NOT NULL "
        "AND asset_category <> ALL($4::text[])",
        owner,
        month,
        end,
        _CRYPTO,
    )
    by_asset: dict[str, list[Any]] = defaultdict(list)
    for r in rows:
        by_asset[r["asset_id"]].append(r)
    contributions = {
        a: calc.net_contributed([op for op in ops if op["tipo"] in calc.INFLOW])
        for a, ops in by_asset.items()
    }
    contributions = {a: v for a, v in contributions.items() if v}
    crypto = -sum(
        (
            _dec(amount)
            for d, amount in await sleeve_cashflows(conn)
            if month <= d <= end and amount < 0
        ),
        Decimal(0),
    )
    return contributions, crypto
