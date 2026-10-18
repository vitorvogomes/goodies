"""Refechar meses fechados (Story 5.5 — FR-33): grava a `version + 1` pelo serviço de `closing`.

`--completar` (padrão) copia o congelado e preenche só as colunas nulas ou `fora_do_resumo` — o
caminho para um termo novo chegar aos meses já fechados (recomendado: um `--completar` geral no fim
do marco 3). `--recalcular` recalcula tudo, mas antes mostra a diferença por métrica e pede
confirmação. Meses abertos ficam de fora. Sempre com backup antes.

Uso (a partir de api/):
    uv run python -m scripts.ops.refechar --meses 2026-06..2026-09
    uv run python -m scripts.ops.refechar --meses 2026-06..2026-09 --recalcular
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from datetime import date

import asyncpg

from config import settings
from engines.closing import service as closing
from engines.common.dates import month_label, parse_periodo
from workers.backup import make_pre_migration_backup


def parse_months(spec: str) -> list[date]:
    """`AAAA-MM..AAAA-MM` (ou um mês só) → os meses do intervalo, em ordem."""
    first, _, last = spec.partition("..")
    start, end = parse_periodo(first), parse_periodo(last or first)
    if end < start:
        raise ValueError("intervalo invertido")
    out: list[date] = []
    month = start
    while month <= end:
        out.append(month)
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return out


async def run(
    conn: asyncpg.Connection,
    months: list[date],
    *,
    mode: str = "completar",
    confirm: Callable[[str], bool] = lambda _: True,
    echo: Callable[[str], None] = print,
) -> list[tuple[date, int]]:
    done: list[tuple[date, int]] = []
    for month in months:
        if not await closing.ClosingMonthStatus().is_closed(conn, month):
            echo(f"{month_label(month)}: aberto, fica de fora.")
            continue
        if mode == "recalcular":
            preview = await closing.reopen_preview(conn, month)
            for row in preview.rows:
                echo(f"{month_label(month)} · {row.label}: {row.frozen} → {row.live}")
            if preview.rows and not confirm(f"Recalcular {month_label(month)}? [s/N] "):
                echo(f"{month_label(month)}: mantido.")
                continue
        out = await closing.refechar(conn, month, mode=mode)
        echo(f"{month_label(month)}: versão {out.version} ({mode}).")
        done.append((month, out.version))
    return done


async def _main(spec: str, mode: str) -> None:
    months = parse_months(spec)
    await make_pre_migration_backup(settings.database_url, "pre-refechar")
    conn = await asyncpg.connect(settings.database_url)
    try:
        await run(conn, months, mode=mode, confirm=lambda q: input(q).strip().lower() == "s")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meses", required=True, help="AAAA-MM..AAAA-MM")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--completar", action="store_true", help="padrão")
    group.add_argument("--recalcular", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.meses, "recalcular" if args.recalcular else "completar"))


if __name__ == "__main__":
    main()
