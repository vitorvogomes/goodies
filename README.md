# Goodies

Plataforma pessoal de controle financeiro. Usuário único: Vitor.
Substitui a planilha (FLUXO DE CAIXA) como fonte única de verdade para caixa, orçamento,
investimentos e o fechamento de cada mês.

**Estado:** v2.0 implementada (78/78 stories; gates m1–m3 PASS). O gate m4 depende só das
métricas de uso — ver [`PROGRESS.md`](PROGRESS.md).

## O que faz

O app tem 4 áreas:

- **Visão geral** — Painel do mês (KPIs, fontes e saldo da conta PF, avisos, resumo do aporte,
  crescimento do patrimônio), Histórico e Fechamento do mês.
- **Caixa** — Transações (importadas pelo Hub, categorias em dois níveis com regras), Orçamento
  (consumido por grupo, custos fixos, dívidas, receitas esperadas × recebidas) e Custos fixos.
- **Investimentos** — Posições (resultado total e do período, **XIRR** nominal e real, alocação
  × meta ± banda), Aportes (distribuição do planejado em cotas inteiras e a lista do que falta
  aplicar), Conciliação (B3 consolidado e carteiras cripto) e Corretoras (caixa na corretora e
  diferença de conciliação por trilho).
- **Ajustes** — contas, categorias e regras, custos e receitas, metas e aportes fixos do mês,
  objetivos, preços manuais (inclusive cripto em US$ e saldos de renda fixa), carteiras e jobs.

Retorno é sempre **XIRR** (não `(resultado−aplicado)/aplicado`). Preços vêm de cache Redis com
fallback que nunca derruba a API.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI 0.136 / Python 3.12 — `api/` (monólito modular em engines) |
| Frontend | Next.js 16 (App Router) / React 19 / TypeScript / shadcn/ui — `web/` |
| Database | PostgreSQL 15 no `docker compose`, asyncpg direto (sem ORM), migrações Alembic |
| Cache | Redis 7 no `docker compose` — `redis[asyncio]` |
| Scheduler | APScheduler no processo FastAPI (não Celery) |
| Auth | JWT custom (`python-jose` + `passlib[bcrypt]`) |
| Ambiente | Só localhost: sem deploy, sem CI, sem nuvem (ADR-014). Infra de deploy na v2.1 |

> Invariantes da v2 em
> [`ARCHITECTURE-SPINE.md`](docs/v2/planning/architecture/architecture-goodies-2026-10-17/ARCHITECTURE-SPINE.md)
> (AD-1..AD-19) e ADRs em [`docs/07_Decisoes.md`](docs/07_Decisoes.md) — não violar sem novo ADR.

## Estrutura

```
goodies/
├── api/                # backend FastAPI (pyproject.toml aqui)
│   ├── engines/        # common · market · ingest · ledger · wallet · portfolio · planning
│   │                   # · closing · alerts · overview (camadas da AD-1)
│   ├── workers/        # jobs APScheduler (preços, carteiras, benchmarks, CDI, backup)
│   ├── auth/           # JWT custom (ADR-006)
│   ├── hermes/         # endpoints service-token (desligado: HERMES_ENABLED=false)
│   ├── db/             # pool asyncpg + migrações Alembic
│   └── scripts/ops/    # backup, migrar, refechar, metricas, baseline
├── web/                # frontend Next.js (app · components · lib · types)
├── docs/               # v2/ (planejamento, pendências), v1/ (histórico), ADRs, dev local
├── docker-compose.yml  # Postgres + Redis + API
├── CLAUDE.md           # regras do projeto para o Claude Code
└── PROGRESS.md         # rastreador de stories e gates
```

## Setup de desenvolvimento

```bash
bash scripts/setup-dev.sh                       # git hooks (.githooks) + gitleaks + .env (na raiz)
docker compose build                            # imagem da API (Postgres + Redis + API via compose)
( cd web && pnpm install )                      # deps do front (host)
( cd api && uv sync )                           # deps do backend no host (pytest/ruff/mypy)
```

Backend usa **uv** (ADR-010): `pyproject.toml` é a fonte única de dependências e `uv.lock`
fixa as versões.

**Rodar e validar localmente:** ver [`docs/LOCAL_DEV.md`](docs/LOCAL_DEV.md) — Postgres + Redis
+ API via `docker compose` na porta **8000**; front no host com `pnpm dev`. O banco local é o
banco real: backup antes de toda migração e nunca `docker compose down -v`.

O pre-commit (`.githooks/pre-commit`) roda **gitleaks** (segredos) + **ruff** (api/) +
**eslint** (web/) nos arquivos staged.

## Documentação

| Doc | Conteúdo |
|---|---|
| [`docs/v2/planning/`](docs/v2/planning/) | Brief, PRD, UX (DESIGN/EXPERIENCE), arquitetura (spine) e épicos da v2 |
| [`PROGRESS.md`](PROGRESS.md) | Stories e gates da v2 |
| [`docs/v2/PENDENCIAS-VITOR.md`](docs/v2/PENDENCIAS-VITOR.md) | Decisões e conferências do Vitor |
| [`docs/07_Decisoes.md`](docs/07_Decisoes.md) | ADRs |
| [`docs/15_Debito_Tecnico.md`](docs/15_Debito_Tecnico.md) | Débito técnico em aberto |
| [`docs/LOCAL_DEV.md`](docs/LOCAL_DEV.md) | Como rodar, testar e fazer backup localmente |
| [`docs/v1/`](docs/v1/) | Histórico da v1 (brief, PRD, arquitetura, stories, progresso) |

## Segurança

Segredos vivem **só** no `.env` (gitignored). `.env.example` lista as chaves sem valores e
deve ficar **sincronizado** com o `.env`. Nada de segredo no chat ou em commits — gitleaks
bloqueia no pre-commit. Detalhes em `.claude/memory/security.md`.
