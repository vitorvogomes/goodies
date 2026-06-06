"""WI-1: reclassificação in-place dos resgates de caixinha (income → investment net).

O resgate de caixinha hoje volta como `income/Resgate`, inflando a receita (e a
taxa de poupança). Política caixinha=investment net: o resgate vira `investment`
com valor positivo, netando o total investido; receita fica limpa.

Testes garantem: o resgate vira investment na categoria certa; linhas de controle
(Tesouro investment positivo, receita real) ficam INTACTAS; idempotência; e o
efeito de queda da receita por conta.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from scripts.reclassify_caixinhas import reclassify_caixinhas

_MONTH = datetime.date(2099, 3, 1)


async def _seed(conn, account_id: str) -> dict[str, str]:
    """Insere o cenário e devolve os ids das linhas-chave."""
    rows = {
        "app": (
            "Caixinha/RDB Nubank",
            "investment",
            Decimal("-500.00"),
            "Aplicação RDB - Caixinha Turbo",
        ),
        "redemption": ("Resgate", "income", Decimal("480.00"), "Resgate RDB - Caixinha Turbo"),
        "tesouro": (
            "Tesouro Direto Nubank",
            "investment",
            Decimal("5.91"),
            "Resgate - Tesouro IPCA+",
        ),
        "salario": ("Salário", "income", Decimal("1000.00"), "Salário recebido"),
    }
    ids: dict[str, str] = {}
    for key, (cat, kind, amount, desc) in rows.items():
        ids[key] = str(
            await conn.fetchval(
                "INSERT INTO transactions (account_id, date, amount, category, kind, "
                "description, external_id) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id",
                account_id,
                _MONTH,
                amount,
                cat,
                kind,
                desc,
                f"recl-{uuid.uuid4().hex}",
            )
        )
    return ids


async def test_redemption_becomes_investment(pool, account):
    async with pool.acquire() as conn:
        ids = await _seed(conn, account)
        result = await reclassify_caixinhas(conn)
        row = await conn.fetchrow(
            "SELECT kind, category FROM transactions WHERE id = $1", ids["redemption"]
        )
    assert row["kind"] == "investment"
    assert row["category"] == "Caixinha/RDB Nubank"
    assert result["resgates_moved"] == 1


async def test_control_rows_untouched(pool, account):
    async with pool.acquire() as conn:
        ids = await _seed(conn, account)
        await reclassify_caixinhas(conn)
        tesouro = await conn.fetchrow(
            "SELECT kind, category FROM transactions WHERE id = $1", ids["tesouro"]
        )
        salario = await conn.fetchrow(
            "SELECT kind, category FROM transactions WHERE id = $1", ids["salario"]
        )
    # Tesouro (investment positivo, categoria diferente) NÃO é tocado.
    assert (tesouro["kind"], tesouro["category"]) == ("investment", "Tesouro Direto Nubank")
    # Receita real continua receita.
    assert (salario["kind"], salario["category"]) == ("income", "Salário")


async def test_app_stays_investment(pool, account):
    async with pool.acquire() as conn:
        ids = await _seed(conn, account)
        await reclassify_caixinhas(conn)
        app = await conn.fetchrow(
            "SELECT kind, category FROM transactions WHERE id = $1", ids["app"]
        )
    assert (app["kind"], app["category"]) == ("investment", "Caixinha/RDB Nubank")


async def test_idempotent(pool, account):
    async with pool.acquire() as conn:
        await _seed(conn, account)
        first = await reclassify_caixinhas(conn)
        second = await reclassify_caixinhas(conn)
    assert first["resgates_moved"] == 1
    assert second == {"apps_fixed": 0, "resgates_moved": 0}


async def test_income_drops_and_invested_nets(pool, account):
    """Receita da conta cai pelo valor do resgate; investido líquido também."""
    async with pool.acquire() as conn:
        await _seed(conn, account)

        async def scoped(kind: str) -> float:
            v = await conn.fetchval(
                "SELECT COALESCE(SUM(amount),0) FROM transactions "
                "WHERE account_id = $1 AND kind = $2",
                account,
                kind,
            )
            return float(v)

        income_before = await scoped("income")
        invested_before = await scoped("investment")  # -500 + 5.91 (apps negativo)
        await reclassify_caixinhas(conn)
        income_after = await scoped("income")
        invested_after = await scoped("investment")

    # Receita perde os 480 do resgate (sobra só o salário 1000).
    assert income_before == 1480.0
    assert income_after == 1000.0
    # Investido (SUM amount) ganha o +480 do resgate → neta a saída da aplicação.
    assert abs(invested_after - (invested_before + 480.0)) < 1e-6
