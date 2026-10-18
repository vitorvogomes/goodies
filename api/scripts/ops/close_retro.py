"""Fechamento retroativo em bloco (Story 5.7 — FR-7): jul/2024–mai/2026 entram fechados.

Cada mês é fechado por `closing.close_retro` (o mesmo `build_month_summary`, origin `retro`), nunca
por SQL de migração. Antes: aborta se o Alembic não estiver em `head` (precisa das reclassificações,
de `assets` e dos snapshots), aborta se houver consolidado B3 em `files/b3/relatorio-consolidado/`
ainda não importado para um mês do intervalo (salvo `--sem-consolidado`) e faz backup. Idempotente:
mês já fechado (ou reaberto) fica como está. No fim, lista os meses com saldo PF divergente.

Uso (a partir de api/):
    uv run python -m scripts.ops.close_retro --from 2024-07 --to 2026-05
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import asyncpg

from config import settings
from engines.closing import service as closing
from engines.common.dates import month_label, parse_periodo
from engines.portfolio import service as portfolio_service
from engines.portfolio.b3_adapter import period_from_name
from workers.backup import make_pre_migration_backup
from workers.dbops import API_DIR, current_revision, head_revision

CONSOLIDADOS_DIR = API_DIR.parent / "files" / "b3" / "relatorio-consolidado"


class RetroAborted(RuntimeError):
    """Uma pré-condição do fechamento retroativo falhou; nada foi fechado."""


@dataclass
class RetroReport:
    closed: list[date] = field(default_factory=list)
    skipped: list[date] = field(default_factory=list)  # já tinham versão
    blocked: list[tuple[date, str]] = field(default_factory=list)
    divergent: list[date] = field(default_factory=list)


def _months(start: date, end: date) -> list[date]:
    out, month = [], start
    while month <= end:
        out.append(month)
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return out


def ensure_head(current: str | None, head: str) -> None:
    if current != head:
        raise RetroAborted(f"Banco em {current or 'nenhuma revisão'}, não em head ({head}).")


def unimported_consolidados(
    files_dir: Path, imported: set[date], start: date, end: date
) -> list[date]:
    """Meses do intervalo cujo consolidado está na pasta mas não foi importado (pela data do nome:
    mensal = aquele mês; anual = dezembro)."""
    found: set[date] = set()
    for path in sorted(files_dir.rglob("*.xlsx")) if files_dir.exists() else []:
        period = period_from_name(path.name, "consolidado")
        if period is None:
            continue
        ref = period[1]
        month = ref.replace(day=1)
        if start <= month <= end and ref not in imported:
            found.add(month)
    return sorted(found)


async def run(
    conn: asyncpg.Connection,
    start: date,
    end: date,
    *,
    files_dir: Path = CONSOLIDADOS_DIR,
    sem_consolidado: bool = False,
    echo: Callable[[str], None] = print,
) -> RetroReport:
    if not sem_consolidado:
        missing = unimported_consolidados(
            files_dir, await portfolio_service.consolidado_dates(conn), start, end
        )
        if missing:
            names = ", ".join(month_label(m) for m in missing)
            raise RetroAborted(
                f"Consolidado B3 não importado: {names}. Importe pelo Hub ou use --sem-consolidado."
            )
    report = RetroReport()
    for month in _months(start, end):
        try:
            out = await closing.close_retro(conn, month)
        except closing.CloseError as exc:
            report.blocked.append((month, exc.message))
            echo(f"{month_label(month)}: não fechado — {exc.message}")
            continue
        if out is None:
            report.skipped.append(month)
            echo(f"{month_label(month)}: já tem versão, fica como está.")
            continue
        report.closed.append(month)
        divergent = [c for c in out.confirmations if c.code == "saldo_pf_divergente"]
        if divergent:
            report.divergent.append(month)
        note = "; saldo PF divergente" if divergent else ""
        n = len(out.confirmations)
        word = "confirmação" if n == 1 else "confirmações"
        echo(f"{month_label(month)}: fechado (retro, {n} {word}{note}).")
    if report.divergent:
        echo("Saldo PF divergente (fechados com 'retroativo divergente'):")
        for month in report.divergent:
            echo(f"  {month_label(month)}")
    return report


def register_engines() -> None:
    """Fora da API, os registros (precondições do fechamento, status do mês, resolvers do ingest)
    só existem depois de importar `main`: sem isso o mês fecharia sem as verificações."""
    import main  # noqa: F401


async def _main(start: date, end: date, sem_consolidado: bool) -> None:
    register_engines()
    ensure_head(await current_revision(settings.database_url), head_revision())
    if end.replace(day=calendar.monthrange(end.year, end.month)[1]) >= date.today():
        raise RetroAborted(f"{month_label(end)} ainda não terminou.")
    conn = await asyncpg.connect(settings.database_url)
    try:
        if not sem_consolidado:  # aborta antes do backup se faltar consolidado
            missing = unimported_consolidados(
                CONSOLIDADOS_DIR, await portfolio_service.consolidado_dates(conn), start, end
            )
            if missing:
                names = ", ".join(month_label(m) for m in missing)
                raise RetroAborted(f"Consolidado B3 não importado: {names}.")
        await make_pre_migration_backup(settings.database_url, "pre-close-retro")
        await run(conn, start, end, sem_consolidado=sem_consolidado)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", required=True, help="AAAA-MM")
    parser.add_argument("--to", dest="end", required=True, help="AAAA-MM")
    parser.add_argument("--sem-consolidado", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(_main(parse_periodo(args.start), parse_periodo(args.end), args.sem_consolidado))
    except RetroAborted as exc:
        raise SystemExit(f"Abortado: {exc}") from None


if __name__ == "__main__":
    main()
