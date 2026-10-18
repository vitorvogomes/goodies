# Goodies

Plataforma pessoal de controle financeiro. Usuário único: Vitor.
Substitui a planilha (FLUXO DE CAIXA) como fonte única de verdade para fluxo de caixa,
portfólio e análise de retorno.

## O que faz

- **Ledger** — fluxo de caixa, custos fixos, taxa de poupança, projeção 30/60/90 dias.
- **Portfolio** — operações, preço médio (DCA), alocação vs. meta, rebalanceamento e
  **XIRR** como métrica principal de retorno (não `(resultado−aplicado)/aplicado`).
- **Market** — preços (B3, cripto, Tesouro) com cache Redis e fallback que nunca derruba a API.
- **Analytics** — benchmarks (CDI/IPCA/IBOV), retorno real, drawdown, metas e alertas.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI 0.111+ / Python 3.12 — `api/` |
| Frontend | Next.js 16 (App Router) / TypeScript — `web/` |
| Database | Supabase (Postgres 15) via asyncpg direto (sem ORM) |
| Cache | Redis (Upstash) — `redis[asyncio]` |
| Scheduler | APScheduler no processo FastAPI (não Celery) |
| Auth | JWT custom (`python-jose` + `passlib[bcrypt]`) — **não** Supabase Auth |
| Deploy | Nenhum — só localhost; infra de deploy do zero na v2.1 |

> Decisões travadas (ADRs) em [`docs/07_Decisoes.md`](docs/07_Decisoes.md) — não violar sem novo ADR.

## Estrutura

```
goodies/
├── api/              # backend FastAPI (pyproject.toml aqui)
│   ├── engines/      # ledger · portfolio · market · analytics
│   ├── workers/      # jobs APScheduler (preços, alertas)
│   ├── hermes/       # endpoints service-token (opcional, ADR-007)
│   ├── auth/         # JWT custom (ADR-006)
│   └── db/           # pool asyncpg + queries SQL explícitas
├── web/              # frontend Next.js (app · components · lib)
├── docs/             # brief, PRD, arquitetura, épicos e stories
├── .github/workflows # CI/CD (STORY-00-08-09)
├── docker-compose.yml # dev local (Postgres + Redis + API)
├── CLAUDE.md         # regras do projeto p/ o Claude Code
└── PROGRESS.md       # rastreador de stories entre sessões
```

## Setup de desenvolvimento

```bash
bash scripts/setup-dev.sh                       # git hooks (.githooks) + gitleaks + .env (na raiz)
docker compose build                            # imagem da API (Postgres + Redis + API via compose)
( cd web && pnpm install )                      # deps do front (host)
# (opcional) deps do backend no host p/ pytest/ruff/mypy:  ( cd api && uv sync )
```

Backend usa **uv** (ADR-010): `pyproject.toml` é a fonte única de dependências e `uv.lock`
fixa as versões. Sem `requirements*.txt`.

**Rodar e validar localmente:** ver [`docs/LOCAL_DEV.md`](docs/LOCAL_DEV.md) — stack
(Postgres + Redis + **API**) via `docker compose` na porta **8000**; front no host (não
precisa de Supabase/Upstash).

O pre-commit (`.githooks/pre-commit`) roda **gitleaks** (segredos) + **ruff** (api/) +
**eslint** (web/) nos arquivos staged.

## Documentação

| Doc | Conteúdo |
|---|---|
| [`docs/v1/00_Brief.md`](docs/v1/00_Brief.md) | Visão e objetivo |
| [`docs/v1/01_PRD.md`](docs/v1/01_PRD.md) | Requisitos de produto |
| [`docs/v1/02_Arquitetura.md`](docs/v1/02_Arquitetura.md) | Arquitetura técnica |
| [`docs/v1/03_Stack.md`](docs/v1/03_Stack.md) | Stack detalhada |
| [`docs/v1/04_UX.md`](docs/v1/04_UX.md) | UX / design |
| [`docs/07_Decisoes.md`](docs/07_Decisoes.md) | ADRs |
| [`docs/v1/08_Contexto_Financeiro.md`](docs/v1/08_Contexto_Financeiro.md) | Contexto financeiro do Vitor |
| [`docs/v1/05_Epicos/`](docs/v1/05_Epicos/) · [`docs/v1/06_Stories/`](docs/v1/06_Stories/) | Épicos e stories |
| [`docs/15_Debito_Tecnico.md`](docs/15_Debito_Tecnico.md) | Débito técnico (registro vivo) |
| [`docs/LOCAL_DEV.md`](docs/LOCAL_DEV.md) | Como rodar localmente |

## Segurança

Segredos vivem **só** no `.env` (gitignored). `.env.example` lista as chaves sem valores e
deve ficar **sincronizado** com o `.env`. Nada de segredo no chat ou em commits — gitleaks
bloqueia no pre-commit. Detalhes em `.claude/memory/security.md`.
