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
| Frontend | Next.js 14 (App Router) / TypeScript — `web/` |
| Database | Supabase (Postgres 15) via asyncpg direto (sem ORM) |
| Cache | Redis (Upstash) — `redis[asyncio]` |
| Scheduler | APScheduler no processo FastAPI (não Celery) |
| Auth | JWT custom (`python-jose` + `passlib[bcrypt]`) — **não** Supabase Auth |
| Deploy | Fly.io (API) + Vercel (web) |

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
├── fly.toml          # placeholder de deploy da API
├── CLAUDE.md         # regras do projeto p/ o Claude Code
└── PROGRESS.md       # rastreador de stories entre sessões
```

## Setup de desenvolvimento

```bash
bash scripts/setup-dev.sh        # git hooks (.githooks) + gitleaks + .env
cp .env.example .env             # preencha com valores reais (fica no .gitignore)
pip install -e "api[dev]"        # FastAPI + ferramentas (ruff, mypy, pytest)
# front (a partir da STORY-00-06): pnpm --dir web install
```

O pre-commit (`.githooks/pre-commit`) roda **gitleaks** (segredos) + **ruff** (api/) +
**eslint** (web/) nos arquivos staged.

## Documentação

| Doc | Conteúdo |
|---|---|
| [`docs/00_Brief.md`](docs/00_Brief.md) | Visão e objetivo |
| [`docs/01_PRD.md`](docs/01_PRD.md) | Requisitos de produto |
| [`docs/02_Arquitetura.md`](docs/02_Arquitetura.md) | Arquitetura técnica |
| [`docs/03_Stack.md`](docs/03_Stack.md) | Stack detalhada |
| [`docs/04_UX.md`](docs/04_UX.md) | UX / design |
| [`docs/07_Decisoes.md`](docs/07_Decisoes.md) | ADRs |
| [`docs/08_Contexto_Financeiro.md`](docs/08_Contexto_Financeiro.md) | Contexto financeiro do Vitor |
| [`docs/05_Epicos/`](docs/05_Epicos/) · [`docs/06_Stories/`](docs/06_Stories/) | Épicos e stories |

## Segurança

Segredos vivem **só** no `.env` (gitignored). `.env.example` lista as chaves sem valores e
deve ficar **sincronizado** com o `.env`. Nada de segredo no chat ou em commits — gitleaks
bloqueia no pre-commit. Detalhes em `.claude/memory/security.md`.
