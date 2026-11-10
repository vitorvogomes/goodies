"""Seed do usuário admin (Vitor) — STORY-00-03.

Lê ADMIN_EMAIL e ADMIN_PASSWORD do ambiente — NÃO embute senha no repo
(security.md / ADR-006). Upsert idempotente com hash bcrypt (`auth.admin.upsert_admin`, o mesmo
do bootstrap da subida — ADR-018).

Uso (a partir de api/):
    ADMIN_EMAIL=... ADMIN_PASSWORD=... .venv/bin/python -m scripts.ops.seed_admin
"""

import asyncio
import os

from auth.admin import upsert_admin
from config import settings


async def seed_admin() -> None:
    email = os.environ["ADMIN_EMAIL"]
    await upsert_admin(settings.database_url, email, os.environ["ADMIN_PASSWORD"])
    print(f"admin seeded: {email}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
