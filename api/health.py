"""Registro plugável de checagens de componentes do health check — STORY-00-02.

00-02 define o contrato. Stories seguintes registram seus checks aqui sem alterar
a lógica de agregação em `main.py` (conflito de merge mínimo entre stories):

    # 00-03 — api/db/connection.py
    register_component_check(check_postgres)   # -> ("postgres", "connected")
    # 00-04 — api/engines/market/cache.py
    register_component_check(check_redis)       # -> ("redis", "connected")
"""

from collections.abc import Awaitable, Callable

# Cada check devolve (nome_do_componente, status). Ex.: ("postgres", "connected").
ComponentCheck = Callable[[], Awaitable[tuple[str, str]]]

_checks: list[ComponentCheck] = []


def register_component_check(check: ComponentCheck) -> None:
    """Registra um check de componente a ser incluído no `/api/v1/health`."""
    _checks.append(check)


async def collect_component_status() -> dict[str, str]:
    """Executa todos os checks registrados e devolve `{componente: status}`."""
    status: dict[str, str] = {}
    for check in _checks:
        name, value = await check()
        status[name] = value
    return status
