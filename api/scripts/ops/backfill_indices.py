"""Backfill de CDI e IPCA desde jun/2024 (Story 7.2): o mesmo worker do catch-up, a partir de uma
data. Idempotente; com backup antes.

Uso (a partir de api/):
    uv run python -m scripts.ops.backfill_indices              # desde jun/2024
    uv run python -m scripts.ops.backfill_indices --desde 2025-01
"""

from __future__ import annotations

import argparse
import asyncio

import asyncpg

from config import settings
from engines.common.dates import parse_periodo
from engines.market.service import BENCHMARK_START
from workers.backup import make_pre_migration_backup
from workers.benchmark_workers import run_benchmark_daily


async def _main(desde: str | None) -> None:
    start = parse_periodo(desde) if desde else BENCHMARK_START
    await make_pre_migration_backup(settings.database_url, "pre-backfill-indices")
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    try:
        stats = await run_benchmark_daily(pool, start=start)
    finally:
        await pool.close()
    print(f"CDI/IPCA desde {start:%m/%Y}: {stats['fetched']} pontos gravados.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", help="AAAA-MM (padrão: 2024-06)")
    asyncio.run(_main(parser.parse_args().desde))


if __name__ == "__main__":
    main()
