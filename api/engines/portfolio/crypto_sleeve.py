"""Crypto sleeve (m4) — bridge fiel entre o ledger (custo BRL) e as carteiras (valor atual).

Cripto NÃO vive em `asset_operations`: o BRL do ledger não tem ativo/quantidade por linha;
linhas sintéticas corromperiam `_dca_price`, o IR-cripto e o `reconcile()` por quantidade.
Este módulo cruza as duas fontes de verdade já existentes:
- **valor atual** (user-scoped): `wallet_positions` + `defi_positions`, valorados pelo cache
  de preço do m3 (reuso de `list_wallet_positions`/`list_defi_valued`).
- **custo/cashflows** (BRL): `transactions` nas categorias cripto do ledger
  (`settings.crypto_ledger_category_keys`).

O custo/resultado/XIRR são conhecidos só no NÍVEL DO SLEEVE (cripto como um bucket) — fiel à
reconciliação estilo "caixa parado na Toro" (caixa enviado vs posição atual). NUNCA fabricar
retorno por ativo (CLAUDE.md: usar XIRR, não `(resultado-aplicado)/aplicado`).

Import lazy a partir de `portfolio.service` (evita ciclo: `wallet.service` já importa
`portfolio.service.net_quantity`).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

import asyncpg

from config import settings
from engines.ledger import queries as ledger_queries
from engines.wallet.service import list_defi_valued, list_wallet_positions

from .constants import AssetCategory
from .service import _nan_to_none, eval_date
from .xirr import xirr


async def sleeve_cost_basis(conn: asyncpg.Connection) -> dict[str, Any]:
    """Custo do sleeve a partir do ledger (global/single-user; `transactions` não tem user_id).

    `cost_basis` = Σ|saídas| (amount<0); `returned` = Σ entradas (amount>0);
    `net_invested` = cost_basis - returned. `by_category` traz o investido líquido por rail.
    """
    rails = settings.crypto_ledger_category_keys
    rows = await ledger_queries.transactions_by_category_keys(conn, rails, with_pairs=True)
    cost_basis = 0.0
    returned = 0.0
    # Story 2.6: o resgate do trilho (`resgate:x`) soma no mesmo rail do investimento (`invest:x`),
    # rotulado pelo nome da subcategoria de investimento.
    by_rail: dict[str, float] = defaultdict(float)
    label: dict[str, str] = {}
    for r in rows:
        amt = float(r["amount"])
        if amt < 0:
            cost_basis += -amt
        else:
            returned += amt
        rail = str(r["category_key"]).split(":", 1)[-1]
        by_rail[rail] += -amt  # saída (negativa) → investido positivo
        if str(r["category_key"]).startswith("invest:") or rail not in label:
            label[rail] = r["category_name"]
    by_category = {label[k]: v for k, v in by_rail.items()}
    return {
        "cost_basis_brl": cost_basis,
        "returned_brl": returned,
        "net_invested_brl": cost_basis - returned,
        "by_category": [
            {"category": c, "net_invested_brl": v}
            for c, v in sorted(by_category.items())
        ],
    }


async def sleeve_cashflows(conn: asyncpg.Connection) -> list[tuple[date, float]]:
    """Série de cashflows do ledger cripto (sinais crus: aporte<0, retorno>0)."""
    rails = settings.crypto_ledger_category_keys
    rows = await ledger_queries.transactions_by_category_keys(conn, rails, with_pairs=True)
    return [(r["date"], float(r["amount"])) for r in rows]


@dataclass(frozen=True)
class SleeveValue:
    """Valor atual do sleeve cripto: BRL + por rail + USD (parcial) + staleness."""

    total_brl: float
    by_rail: dict[str, float]
    stale: bool
    total_usd: float
    usd_partial: bool  # algum ativo tem BRL mas não USD (cotação em dólar ausente)


async def sleeve_current_value(
    conn: asyncpg.Connection, user_id: str
) -> SleeveValue:
    """Valor atual do sleeve (BRL+USD) + por rail + `stale` (alguma posição sem preço).

    Wallets agrupadas por `chain`; DeFi sob o rail do protocolo. Sem preço BRL → contribui
    0 e marca `stale=True`. USD é fail-soft: ativo com BRL mas sem USD marca `usd_partial`
    (cripto sempre tem valor em dólar; ver ADR-005). Nunca levanta por falta de preço.
    """
    wallets = await list_wallet_positions(conn, user_id)
    defi = await list_defi_valued(conn, user_id)
    total = 0.0
    total_usd = 0.0
    usd_partial = False
    by_rail: dict[str, float] = defaultdict(float)
    stale = False

    def _accumulate(value_brl: float | None, value_usd: float | None) -> bool:
        nonlocal total, total_usd, usd_partial, stale
        if value_brl is None:
            stale = True
            return False
        total += value_brl
        if value_usd is None:
            usd_partial = True  # tem BRL mas não USD
        else:
            total_usd += value_usd
        return True

    for w in wallets:
        if _accumulate(w["value_brl"], w["value_usd"]):
            by_rail[w["chain"]] += w["value_brl"]
    for d in defi:
        if _accumulate(d["value_brl"], d["value_usd"]):
            # rail por protocolo (hylo/pendle_v2/neobankless...) em vez de um "defi"
            # genérico — assim cada custódia aparece distinta na reconciliação de valor.
            by_rail[d.get("protocol") or "defi"] += d["value_brl"]
    return SleeveValue(total, dict(by_rail), stale, total_usd, usd_partial)


async def crypto_positions(
    conn: asyncpg.Connection, user_id: str
) -> list[dict[str, Any]]:
    """Cripto como UM BLOCO (sleeve) p/ a aba Posições (m4).

    Cripto não tem a granularidade fiel de B3/RF (custo por ativo só é recuperável em parte —
    ver `docs/15`). Em vez de poluir Posições com linhas per-ativo incompletas, devolve **uma
    linha-bloco**: investido (ledger) vs valor atual (carteiras) → resultado. `is_bucket=True`;
    o detalhe por moeda/chain vive na aba Carteiras Cripto. Alocação soma este `valor_atual`
    como a categoria Cripto. Vazio (sem carteira e sem aporte) → `[]`.
    """
    sv = await sleeve_current_value(conn, user_id)
    total, stale = sv.total_brl, sv.stale
    cost = await sleeve_cost_basis(conn)
    net_invested = cost["net_invested_brl"]
    if total <= 0 and net_invested <= 0:
        return []
    custo = net_invested if net_invested > 0 else None
    resultado = total - net_invested if custo is not None else None
    resultado_pct = (
        resultado / net_invested * 100 if resultado is not None and net_invested else None
    )
    return [
        {
            "asset_symbol": "Cripto",
            "asset_category": str(AssetCategory.CRIPTO),
            "custody": None,
            "is_bucket": True,
            "quantidade_net": None,
            "preco_medio": None,
            "custo_total": custo,
            "preco_atual": None,
            "valor_atual": total,
            "resultado": resultado,
            "resultado_pct": resultado_pct,
            "stale": stale,
            "is_manual": False,
        }
    ]


async def calculate_crypto_sleeve(
    conn: asyncpg.Connection, user_id: str, today: date | None = None
) -> dict[str, Any]:
    """Resumo do sleeve cripto: custo (ledger) vs valor atual (carteiras) → resultado + XIRR.

    Também serve a reconciliação de VALOR (net_invested vs current_value → resultado, por rail).
    XIRR = `xirr(cashflows do ledger + (today, +valor_atual))`; None com <2 fluxos ou sem
    convergência (`_nan_to_none`).
    """
    today = eval_date(today)
    sv = await sleeve_current_value(conn, user_id)
    total = sv.total_brl
    cost = await sleeve_cost_basis(conn)
    flows = await sleeve_cashflows(conn)
    if total > 0:
        flows = [*flows, (today, total)]
    rate = _nan_to_none(xirr(flows)) if len(flows) >= 2 else None
    return {
        "current_value_brl": total,
        "current_value_usd": sv.total_usd,
        "usd_partial": sv.usd_partial,
        "cost_basis_brl": cost["cost_basis_brl"],
        "returned_brl": cost["returned_brl"],
        "net_invested_brl": cost["net_invested_brl"],
        "resultado": total - cost["net_invested_brl"],
        "xirr": rate,
        "by_rail": [
            {"rail": k, "current_value_brl": v} for k, v in sorted(sv.by_rail.items())
        ],
        "by_category": cost["by_category"],
        "stale_value": sv.stale,
    }
