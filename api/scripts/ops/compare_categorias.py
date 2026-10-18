"""Comparação mês x categoria antes e depois de uma revisão de dado (Stories 2.3 e 2.6 — AD-16).

`snapshot(conn, label_sql)` soma contagem e valor por (mês, rótulo); `label_sql` é a expressão SQL
do
rótulo de cada transação (alias `t`). Antes da revisão, o rótulo ESPERADO aplica os deltas listados
(renome, fusão, reclassificação); depois, o rótulo é a subcategoria real. `diff` devolve só o que
diverge — qualquer diferença fora da lista reprova.

Uso (a partir de api/), grava o retrato para comparar depois:
    uv run python -m scripts.ops.compare_categorias --salvar antes.json
    uv run python -m scripts.ops.compare_categorias --comparar antes.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

import asyncpg

from config import settings

Snapshot = dict[str, tuple[int, str]]

LABEL_BY_ID = "(SELECT c.name FROM categories c WHERE c.id = t.category_id)"


async def snapshot(conn: asyncpg.Connection, label_sql: str) -> Snapshot:
    rows = await conn.fetch(
        f"SELECT to_char(t.date, 'YYYY-MM') AS m, {label_sql} AS label, count(*) AS n, "
        f"sum(t.amount) AS s FROM transactions t GROUP BY 1, 2 ORDER BY 1, 2"
    )
    return {f"{r['m']}|{r['label']}": (int(r["n"]), str(r["s"])) for r in rows}


def diff(before: Snapshot, after: Snapshot) -> dict[str, tuple[object, object]]:
    keys = sorted(set(before) | set(after))
    return {k: (before.get(k), after.get(k)) for k in keys if before.get(k) != after.get(k)}


def total(s: Snapshot) -> tuple[int, Decimal]:
    return sum(n for n, _ in s.values()), sum((Decimal(v) for _, v in s.values()), Decimal(0))


async def _current() -> Snapshot:
    conn = await asyncpg.connect(settings.database_url)
    try:
        has_id = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'transactions' AND column_name = 'category_id')"
        )
        return await snapshot(conn, LABEL_BY_ID if has_id else "t.category")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--salvar")
    group.add_argument("--comparar")
    args = parser.parse_args()
    snap = asyncio.run(_current())
    if args.salvar:
        Path(args.salvar).write_text(json.dumps(snap, ensure_ascii=False, indent=1))
        print(f"retrato gravado: {len(snap)} pares mes x categoria")
        sys.exit(0)
    before: Snapshot = {k: tuple(v) for k, v in json.loads(Path(args.comparar).read_text()).items()}
    delta = diff(before, snap)
    for k, (b, a) in delta.items():
        print(f"{k}: antes={b} depois={a}")
    print(f"contagem antes/depois: {total(before)[0]} / {total(snap)[0]}; com delta: {len(delta)}")


if __name__ == "__main__":
    main()
