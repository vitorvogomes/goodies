# Convenções de Código — Goodies (v2.2)

Invariantes completos no spine: `docs/v2/planning/architecture/architecture-goodies-2026-10-17/ARCHITECTURE-SPINE.md`
(AD-1..AD-19). Em conflito, o spine vence este arquivo.

## Python (api/)

- **Dependências/execução:** uv (ADR-010) — `pyproject.toml` é a fonte; `uv sync` instala,
  `uv run ruff|mypy|pytest|uvicorn|alembic` executa (a partir de `api/`). Sem `requirements*.txt`/`pip`.
- **Linting/formatação:** `ruff check --fix` + `ruff format` (hook automático)
- **Type checking:** `mypy --strict` nos pacotes inteiros tocados — sem `Any` sem justificativa
- **Imports:** stdlib → third-party → local, separados por linha em branco
- **Testes:** `pytest` + `pytest-asyncio` em `api/tests/<engine>/test_<módulo>.py`; serviços contra Postgres real
  (`goodies_test`); testes de dado real com `@pytest.mark.dados_reais` contra `goodies_dados` (nunca pulados no gate)
- **Cobertura mínima:** ≥ 80% (pyproject); todo `calc.py`/módulo puro com teste unitário
- **Nomes:** snake_case para funções/variáveis, PascalCase para classes, UPPER_SNAKE para constantes; funções de
  cálculo com o termo do glossário em inglês snake (`consumed`, `available_for_spending`)
- **Async:** todas as rotas FastAPI e queries asyncpg são `async def`
- **Logs:** `structlog` em tudo — evento snake + campos; nunca segredo nem valor financeiro
- **Erros de API externa:** logar com structlog, retornar dado cacheado + `"stale": true`. Nunca HTTP 5xx
- **Inspecionar o banco:** `docker compose exec -T postgres psql -U goodies -d goodies -c '<SQL>'` — só leitura;
  schema só via Alembic. Ver `docs/LOCAL_DEV.md`.

### Engines e camadas (AD-1)

`common` ← `market`/`ingest`/`jobs` ← `ledger`/`wallet` ← `portfolio` ← `planning` ← `closing` ← `alerts` ←
`overview` (`jobs` é a camada dos jobs — no código, `api/workers/`, rotas em `/api/v1/jobs`). Engine só importa
engine de camada **menor**; engine baixa recebe o que precisa de cima por registro
feito em `main.py`. `api/workers/` e `main.py` são a casca; nenhuma engine os importa.
Movimentos obrigatórios da AD-1 (enums → `common`, `PriceCache` → `common.cache`...) acontecem na primeira
story que toca o módulo; **atribuição explícita de um movimento a uma story vence essa regra**.
Base comum (Story 2.1): `common.money` (`Money`/`Pct`), `common.models.Valued[T]`, `common.deps` (`Db`,
`AuthUser`), `common.owner.get_owner_id`, `common.cache` (`cache()`, `invalidate_xirr_cache`),
`common.month_status` (`MonthStatusPort`), `common.dates` (`today_brt`, `resolve_period`). "Hoje" nunca
por `date.today()`/`datetime.now()` sem fuso/`CURRENT_DATE` — um teste barra.

### Layout de engine (AD-2)

```
api/engines/<engine>/
  router.py    # só HTTP: valida entrada, chama service, declara response_model
  service.py   # orquestração, conn.transaction(), chama calc e queries
  queries.py   # todo o SQL da engine ($n params)
  models.py    # Pydantic de I/O (XCreate, XUpdate, XResponse, XList, XPreview)
  calc.py      # puro: Decimal, sem IO (cálculo grande pode ter irmão puro: xirr.py, distribution.py)
```

- Código **novo** nasce nesse layout. O legado ainda tem SQL em `service.py`/módulos soltos (não existe
  `queries.py` em todas as engines hoje); um módulo legado migra para o layout quando uma story o toca.
- `Db` e `AuthUser` vêm de `common.deps`. Dono único por tabela (AD-3): só a dona escreve; leitura cruzada só por
  funções públicas da dona.

### Dinheiro e números (AD-4)

- Dinheiro é `Decimal` em todo o Python; **proibido `float()` em dinheiro**.
- Fronteira HTTP: `common.money.Money` (JSON number, 2 casas, `ROUND_HALF_EVEN`); percentual `common.money.Pct`
  (2 casas, já em %); quantidade como string decimal. Taxas internas são frações (0,0548).
- Quantização a centavos no `calc` que produz o termo; gravado como `numeric(15,2)`.
- Rateios fecham ao centavo pelo maior resto. O frontend **nunca** faz aritmética de dinheiro.
- Termos de dinheiro (AD-7): uma função pura por termo, lida por **role**/`key` de categoria, nunca pelo nome.
- Retorno é sempre XIRR (`portfolio/xirr.py`), nunca `(resultado − aplicado)/aplicado`.

### Contrato HTTP (AD-15)

- Rotas `/api/v1/<engine>/<recurso>`; toda rota nova ou tocada declara `response_model`.
- Termos e totais = `Valued[T]` (`value` null quando não há dado + `unavailable_reason`, `as_of`, `source`, `stale`).
- Lista paginada: `{items, total, limit, offset}`.
- Recálculo interativo: `POST .../preview`, que não grava.
- Período: `periodo=YYYY-MM`, `leitura ∈ {mes, tri, ano, inicio}`, resolvido por `common.dates.resolve_period`;
  "hoje" = `common.dates.today_brt()`; mês no banco = `date` dia 1; timestamps `timestamptz` UTC.

### Estrutura de erros (backend)

```python
# Sempre um dict com código snake e mensagem pt-BR
raise HTTPException(
    status_code=422,
    detail={"error": "invalid_cashflow", "message": "Taxa de câmbio ausente para cripto em USD"},
)
```

### Padrão de router FastAPI

```python
router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])

@router.get("/transactions", response_model=TransactionList)
async def list_transactions(
    db: Db,
    user: AuthUser,
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
) -> TransactionList:
    return await service.list_transactions(db, month)
```

### Padrão de teste

```python
from decimal import Decimal

def test_taxa_poupanca_junho_2026() -> None:
    rate = savings_rate(work_income=Decimal("..."), expenses=Decimal("..."), refunds=Decimal("..."))
    assert rate.quantize(Decimal("0.0001")) == PINNED["2026-06"]  # baseline por mês (ADR-016)
```

### Banco e migrações (AD-16, AD-18)

- Alembic em `api/db/migrations/versions/NNNN_snake_name.py` (revision = nome do arquivo); modelo e backfill na
  mesma revisão, SQL idempotente; cada revisão de dado com teste de invariantes (poupança por mês = baseline fixado, contagens, zero órfãs,
  deltas esperados).
- **Backup antes de toda migração** (`pg_dump` em `BACKUP_DIR`). Nunca `docker compose down -v`.
- Tabelas novas com `user_id` NOT NULL (`common.owner.get_owner_id`). Enums persistidos = `text` + `CHECK`.

## TypeScript (web/)

- **Linting:** `pnpm lint` (ESLint); **testes:** Vitest em utilitários puros (`format`, período) e nos guardas
  estáticos (`web/tests/`: no raw color, estados vazios de Ajustes)
- **Imports:** path aliases (`@/components/...`)
- **Componentes:** PascalCase, um por arquivo; primitivos shadcn em `web/components/ui/` (`shadcn init -b radix`;
  o new-york no CLI 4 é o preset Vega → `style: "radix-vega"` no `components.json`; nunca `init -d`),
  domínio em `web/components/<area>/`
- **Páginas são client components** (`"use client"`); dados via hooks TanStack Query em `web/lib/<engine>.ts`
  com queryKey `[engine, recurso, periodo?, ...]`; mutação invalida a própria engine e as que dependem dela
- **Rotas:** `web/app/(app)/{visao-geral,caixa,investimentos,ajustes}/<aba>`, período e leitura na URL
- **Tipos:** espelham `models.py` do backend em `web/types/<engine>.ts`
- **Tipografia:** Geist na interface; **Geist Mono** com `tabular-nums` em todo número, alinhado à direita;
  `formatBRL()`/`formatPercent()` de `@/lib/format` (só formatam — nunca somam)
- **Cores:** só tokens do DESIGN.md (`app/globals.css`, `@theme inline`), claro e escuro; nunca hex em componente.
  O teste "no raw color" (`pnpm test`) barra hex/`rgb()`/`hsl()`/`oklch()` e classe de paleta fora do
  `globals.css`, sem lista de exceções (zerada na Story 10.6)
- **Theme-showcase:** toda story que cria componente o acrescenta ao `/dev/tema`
  (`web/app/dev/tema/page.tsx`), em todos os estados, claro e escuro lado a lado
- **Tipografia em classe:** `type-page-title`, `type-section-title`, `type-body(-sm)`, `type-label`,
  `type-caption`, `type-num-display|lg|body|table`, `type-tag` (escala do DESIGN.md)
- **Auth (ADR-006):** access token em memória; 401 → refresh pelo cookie → repete; falhou → `/login?next=`
- **Celular é alvo (v2.2, ADR-019):** abaixo de 1024px a navegação é a `BottomNav` (Importar na barra superior);
  abaixo de 640px (`useMedia(PHONE)` de `@/lib/use-media`) o `DataTable` vira cartão — marque as colunas com
  `mobile: "title" | "aside" | "meta" | "block" | "hide"` (o resto vira rótulo/valor); tabela crua ganha
  `className="table-stack"` + `data-label` em cada `<td>` (uma linha vira bloco); página com layout próprio decide
  por `useMedia(PHONE)` (Posições, Objetivos/Classes do aporte). Seção longa ou detalhe vai em `Section`
  (`components/data/Section`, recolhível). Alvo de toque ≥ 44px; campo de formulário em 16px no celular.
- **Conta é da API (AD-4), inclusive o que parece "só de tela":** US$ (`to_usd`), % de fatia de pizza
  (`common.shares`, soma 100,00), larguras de barra (fluxo do mês) — o web só formata e desenha.
- **Gráficos:** recharts; pizza só com `PieBreakdown` (tons `--pie-1..8`, legenda com nome, % e valor, "Ver como
  tabela"); cor de gráfico só por variável CSS (`var(--pie-N)`, `--color-chart-N`), nunca literal

## Git

- **Commits:** `tipo(escopo): descrição` com o id da story — ex.: `feat(e2): 2.3 — categorias em dois níveis`,
  `chore(e2): progress`. Migração no mesmo commit do código que a usa.
- **Branch:** `main` local. **Nunca `git push`** — o Vitor faz push manual.
