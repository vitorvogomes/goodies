# Convenções de Código — Goodies

## Python (api/)

- **Dependências/execução:** uv (ADR-010) — `pyproject.toml` é a fonte; `uv sync` instala,
  `uv run ruff|mypy|pytest|uvicorn|alembic` executa (a partir de `api/`). Sem `requirements*.txt`/`pip`.
- **Linting:** `ruff check api/ --fix` (configurado como hook automático)
- **Type checking:** `mypy --strict` — sem `Any` sem justificativa
- **Formatação:** ruff format (substitui black)
- **Imports:** stdlib → third-party → local, separados por linha em branco
- **Testes:** `pytest` + `pytest-asyncio` — arquivos em `api/tests/<engine>/test_<módulo>.py`
- **Cobertura mínima:** 80% nas engines Portfolio e Analytics (críticas para correção financeira)
- **Nomes:** snake_case para funções/variáveis, PascalCase para classes, UPPER_SNAKE para constantes
- **Async:** todas as rotas FastAPI e queries asyncpg são `async def`
- **DB:** asyncpg direto — sem SQLAlchemy ORM. Queries SQL explícitas em `queries.py`
- **Erros de API externa:** logar com structlog, retornar dado cacheado + `"stale": true`. Nunca HTTP 5xx

### Padrão de router FastAPI
```python
router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])

@router.get("/summary")
async def get_summary(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> MonthlySummaryResponse:
    return await ledger_service.get_monthly_summary(db, month)
```

### Padrão de teste
```python
@pytest.mark.asyncio
async def test_taxa_poupança_junho_2026(client: AsyncClient):
    resp = await client.get("/api/v1/cashflow/summary?month=2026-06")
    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["savings_rate"] - 55.48) < 0.1  # tolerância ±0.1%
```

## TypeScript (web/)

- **Linting:** `pnpm lint` (ESLint)
- **Formatação:** Prettier (via ESLint)
- **Imports:** path aliases (`@/components/...`)
- **Componentes:** PascalCase, um componente por arquivo
- **Server vs Client:** padrão App Router — Server Components por default, `"use client"` só quando necessário (event handlers, hooks, browser APIs)
- **Data fetching:** Server Components para dados iniciais, TanStack Query para atualizações
- **Tipos:** espelhar os schemas Pydantic do backend em `web/types/`
- **Números:** sempre usar `JetBrains Mono`, alinhar à direita, `formatBRL()` e `formatPercent()` de `@/lib/format`
- **Cores semânticas:** usar tokens do design system (`text-gain`, `text-loss`, `text-warning`) — nunca hardcodar #hex para valores financeiros

## Git

- **Commits:** `tipo(escopo): descrição` — conventional commits
  - `feat(m0): STORY-00-02 setup FastAPI health check`
  - `fix(m2): corrigir sinal de cashflow no XIRR`
  - `test(m1): adicionar testes de taxa de poupança`
- **Branches:** `main` para produção. Features pequenas direto no main para MVP single-developer
- **Migrations:** sempre commitar junto com o código que usa a nova coluna/tabela

## Estrutura de erros (backend)

```python
# Sempre usar este formato para erros HTTP
raise HTTPException(
    status_code=422,
    detail={"error": "invalid_cashflow", "message": "Taxa de câmbio ausente para cripto em USD"}
)
```
