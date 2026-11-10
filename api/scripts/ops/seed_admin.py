"""Seed do usuário admin (Vitor) — STORY-00-03.

Lê ADMIN_EMAIL e ADMIN_PASSWORD do ambiente — NÃO embute senha no repo (security.md / ADR-006);
vazios (referência do Railway que não resolveu) recusam. Upsert idempotente com hash bcrypt
(`auth.admin.upsert_admin`, o mesmo do bootstrap da subida — ADR-018); trocar a senha encerra as
sessões.

Uso (a partir de api/):
    ADMIN_EMAIL=... ADMIN_PASSWORD=... .venv/bin/python -m scripts.ops.seed_admin
"""

import asyncio
import sys

from auth.admin import upsert_admin
from config import settings
from workers.dbops import admin_from_env


async def seed_admin() -> None:
    admin = admin_from_env()
    if admin is None:
        print("seed_admin: defina ADMIN_EMAIL e ADMIN_PASSWORD (não vazios)", file=sys.stderr)
        sys.exit(1)
    await upsert_admin(settings.database_url, admin.email, admin.password)
    print(f"admin seeded: {admin.email}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
