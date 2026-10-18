"""Baseline de regressão (Story 1.3): XIRR, aplicado e net com data e preços congelados.

Grava, **antes** de qualquer atualização/migração, o retrato do portfólio e do caixa calculado sobre
`goodies_dados` (restaurado do backup pré-migração fixado), com:
- `EVALUATION_DATE` fixa (padrão 2026-10-18), nunca a data do dia;
- preços só do Postgres (`asset_prices` do backup): o cache Redis é trocado por um cache nulo, então
  nenhum preço vivo entra; nenhum worker roda.

O teste `tests/dados_reais/test_baseline.py` recalcula o mesmo retrato e compara com o arquivo
fixado em `tests/dados_reais/pinned_baseline.txt` — o mesmo das stories de dado seguintes.

Uso (a partir de api/):
    uv run python -m scripts.ops.baseline --salvar <dir fora do repo> [--data 2026-10-18]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

import asyncpg

from config import settings
from engines.common.assets import CRYPTO_CATEGORIES
from engines.common.cache import use_cache
from engines.portfolio import service as portfolio_service
from engines.portfolio.service import _INFLOW_TIPOS
from scripts._common import resolve_owner
from workers.backup import DbTarget, pinned_dados_backup, restore, validate_backup_dir

BASELINE_EVALUATION_DATE = date(2026, 10, 18)
CENT = Decimal("0.01")
PINNED_BASELINE_FILE = (
    Path(__file__).resolve().parents[2] / "tests" / "dados_reais" / "pinned_baseline.txt"
)


class _NullCache:
    """Cache que nunca acerta: força o preço do Postgres (congelado no backup)."""

    async def get(self, key: str) -> None:
        return None

    async def mget(self, keys: list[str]) -> list[None]:
        return [None] * len(keys)

    async def set(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def delete(self, *args: Any, **kwargs: Any) -> None:
        return None


@contextmanager
def frozen_prices() -> Any:
    saved = use_cache(_NullCache())  # type: ignore[arg-type]
    try:
        yield
    finally:
        use_cache(saved)


def _r(value: float | None) -> float | None:
    """Taxa de XIRR (fração, não dinheiro): arredondada para o arquivo não carregar ruído."""
    return None if value is None else round(value, 10)


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_EVEN))


async def compute_baseline(conn: asyncpg.Connection, evaluation_date: date) -> dict[str, Any]:
    owner = await resolve_owner(conn)
    if owner is None:
        raise RuntimeError("banco sem usuário")
    uid = str(owner["id"])
    with frozen_prices():
        xirr = await portfolio_service.calculate_portfolio_xirr(conn, uid, today=evaluation_date)
        positions = await portfolio_service.calculate_positions(conn, uid)
    ops = await conn.fetch(
        "SELECT asset_symbol, tipo, quantidade, valor_unitario FROM asset_operations "
        "WHERE user_id = $1 AND asset_category <> ALL($2::text[])",
        uid,
        [str(c) for c in CRYPTO_CATEGORIES],
    )
    # Dinheiro em Decimal (AD-4): net = aportes - retornos, direto dos numeric do banco.
    net: dict[str, Decimal] = defaultdict(Decimal)
    for op in ops:
        total = Decimal(op["quantidade"]) * Decimal(op["valor_unitario"])
        net[op["asset_symbol"]] += total if op["tipo"] in _INFLOW_TIPOS else -total
    # `custo_total` vem do cálculo legado (float) de calculate_positions; vira Decimal pelo repr e é
    # quantizado a centavos, para o arquivo comparar dinheiro ao centavo e não ruído de float.
    applied = {
        str(p["asset_symbol"]): _money(Decimal(repr(p["custo_total"])))
        for p in positions
        if p.get("custo_total") is not None
    }
    savings = await conn.fetch(
        "SELECT to_char(month, 'YYYY-MM') AS m, savings_rate FROM monthly_summary ORDER BY 1"
    )
    revision = await conn.fetchval("SELECT version_num FROM alembic_version")
    return {
        "evaluation_date": evaluation_date.isoformat(),
        "revision": revision,
        "xirr": {
            "consolidated": _r(xirr["consolidated"]),
            "by_category": {k: _r(v) for k, v in sorted(xirr["by_category"].items())},
            "by_asset": {k: _r(v) for k, v in sorted(xirr["by_asset"].items())},
        },
        "aplicado": dict(sorted(applied.items())),
        "net": {k: _money(v) for k, v in sorted(net.items())},
        "counts": {
            "transactions": await conn.fetchval("SELECT count(*) FROM transactions"),
            "asset_operations": await conn.fetchval("SELECT count(*) FROM asset_operations"),
        },
        "savings_rate": {
            r["m"]: None if r["savings_rate"] is None else str(round(r["savings_rate"], 6))
            for r in savings
        },
    }


def dados_dsn() -> str:
    return DbTarget.from_dsn(settings.database_url).with_database("goodies_dados").dsn()


PINNED_SAVINGS_V2_FILE = PINNED_BASELINE_FILE.with_name("pinned_savings_v2.txt")


def pinned_savings_v2() -> dict[str, str | None] | None:
    """Taxa de poupança v2 (`ledger/calc`, em %) por mês fixada depois da Story 2.6 (ADR-016)."""
    if not PINNED_SAVINGS_V2_FILE.is_file():
        return None
    name = PINNED_SAVINGS_V2_FILE.read_text().strip()
    path = validate_backup_dir(settings.backup_dir) / "baseline" / name if name else None
    if path is None or not path.is_file():
        return None
    data: dict[str, str | None] = json.loads(path.read_text())
    return data


def pinned_baseline() -> Path | None:
    if not PINNED_BASELINE_FILE.is_file():
        return None
    name = PINNED_BASELINE_FILE.read_text().strip()
    return validate_backup_dir(settings.backup_dir) / "baseline" / name if name else None


def load_pinned_baseline() -> dict[str, Any] | None:
    """Conteúdo do baseline fixado (leitura síncrona, para os testes)."""
    path = pinned_baseline()
    if path is None or not path.is_file():
        return None
    data: dict[str, Any] = json.loads(path.read_text())
    return data


async def _build(evaluation_date: date) -> dict[str, Any]:
    source = pinned_dados_backup()
    if source is None or not source.is_file():
        raise RuntimeError("backup pré-migração fixado não encontrado")
    await restore(source, dados_dsn())
    conn = await asyncpg.connect(dados_dsn())
    try:
        return await compute_baseline(conn, evaluation_date)
    finally:
        await conn.close()


async def _savings_v2() -> tuple[str, dict[str, str | None]]:
    """Poupança v2 (`ledger/calc`, %) por mês da base fixada migrada até o head (Story 2.6)."""
    from engines.ledger.service import monthly_savings
    from workers.dbops import alembic_upgrade

    source = pinned_dados_backup()
    if source is None or not source.is_file():
        raise RuntimeError("backup pré-migração fixado não encontrado")
    await restore(source, dados_dsn())
    await asyncio.to_thread(alembic_upgrade, dados_dsn(), "head")
    conn = await asyncpg.connect(dados_dsn())
    try:
        rev = str(await conn.fetchval("SELECT version_num FROM alembic_version"))
        rates = await monthly_savings(conn)
    finally:
        await conn.close()
    return rev, {
        m.isoformat()[:7]: None if r is None else str(round(r * 100, 6)) for m, r in rates.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salvar", type=Path, required=True)
    parser.add_argument("--data", type=date.fromisoformat, default=BASELINE_EVALUATION_DATE)
    parser.add_argument("--poupanca-v2", action="store_true", help="grava só a poupança v2")
    args = parser.parse_args()
    out_dir = validate_backup_dir(str(args.salvar))
    if args.poupanca_v2:
        rev, rates = asyncio.run(_savings_v2())
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"savings_v2_{rev}.json"
        dest.write_text(json.dumps(rates, indent=1, sort_keys=True))
        print(f"poupança v2 gravada: {dest} (fixe o nome em {PINNED_SAVINGS_V2_FILE.name})")
        sys.exit(0)
    data = asyncio.run(_build(args.data))
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"baseline_{data['revision']}_{args.data.isoformat()}.json"
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"baseline gravado: {dest} (fixe o nome em {PINNED_BASELINE_FILE.name})")
    sys.exit(0)


if __name__ == "__main__":
    main()
