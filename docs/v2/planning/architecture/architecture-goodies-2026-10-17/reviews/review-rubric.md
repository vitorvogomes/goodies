---
review_of: ../ARCHITECTURE-SPINE.md
lens: rubric (good-spine checklist)
reviewer: rubric walker
date: 2026-10-17
verdict: needs-revision (sound core, not yet build-ready)
---

# Rubric review — Architecture Spine Goodies v2.0

## Verdict

The paradigm, layering, and money and closing decisions are sound. Most of the spine ratifies the
real codebase. It is **not yet build-ready**. The ingest inversion has a hole for derivations that
cross adapters. Two layer edges in the diagram contradict AD-1 or the code. Three tables or
contracts are missing that stories will need on day one: per-file batch coverage, B3 consolidado
positions, and multi-month reads. The operational envelope has no backup or restore decision for a
local-only database that holds all of Vitor's financial data.

## Scorecard

| Criterion | Result | Notes |
| --- | --- | --- |
| Fixes the real divergence points for epics/stories | Partial | Strong on money terms, closing, alerts, categories, migrations. Misses: cross-adapter derivations, batch granularity, consolidado storage, multi-month composition, Money JSON type, preview→confirm statefulness. |
| Every AD Rule is enforceable and prevents its divergence | Mostly | AD-1 is contradicted by its own diagram (overview→alerts). AD-4's "number with 2 decimals" can't be enforced without a named type. AD-17's invalidation rule leaves stale planning and alerts queries. |
| Nothing in Deferred lets two units diverge | Mostly | "Pagination deferred" conflicts with AD-15's paginated envelope, because nothing says which lists use it. The other items are safe. |
| Ratifies (not contradicts) the brownfield code | Mostly | Versions match `uv.lock`/`pnpm-lock`. Client pages, `@theme inline`, `today_brt`, migration naming, B3 `dry_run`, Hermes raw SQL and the cycles were all confirmed. The AD-1 list of moves is incomplete (see F-8). `engines/jobs` and `engines/analytics` are unassigned. |
| Altitude dimensions decided / deferred / open | Partial | Environments, deploy, CI, secrets and logging are decided. **Backups, restore, the migration run procedure, worker-failure visibility in v2.0, and the fate of the existing Fly/Supabase setup** are missing. Auth/session is covered only by reference to ADR-006. |
| Terse (decisions, not rationale) | Pass | Mostly decisions. "Prevents" lines are format-required. A few parentheticals are rationale ("ratifica o código atual"), which is fine. |
| Mermaid diagrams valid | Pass with caveat | All 3 parse in mermaid 11.12.0. The erDiagram **fails in mermaid 11.4.1** because of unquoted accented labels (`contém`, `versão`). |
| Ingest SourceAdapter inversion sound with layering | Partial | The direction is correct (ingest@1 defines the protocol, ledger@2 and portfolio@3 implement it and register in `main.py`). It breaks for derivations from one source that land in another engine's tables (caixinha ops from the Nubank OFX). |
| Layer assignments consistent | No | `overview(6) → alerts(6)` violates "same layer doesn't import". `workers → closing` matches no real or planned call. `alerts → closing` contradicts AD-10's registration model. |

## Findings

Severity scale: critical (blocks the first stories or forces a rule violation), high (two units will
diverge), medium (probable rework), low (polish).

### F-1 — critical — Cross-adapter derivations have no legal home (AD-5 × AD-1 × AD-3)

AD-5 says "Derivações pós-import (operações de caixinha, RF, aporte de debênture sugerido) rodam no
`apply` do adapter dono". The caixinha `asset_operations` are derived from **Nubank OFX**
transactions. The code confirms this: `api/engines/portfolio/caixinhas.py:61` `build_caixinha_ops`
reads `transactions` and writes portfolio operations. The Nubank adapter lives in `ledger` (layer
2). The derived rows belong to `portfolio` (layer 3).

- If the ledger adapter writes them, it violates AD-1 (an upward import) and AD-3 (a foreign write).
- If the portfolio B3 adapter does it, the derivation doesn't run when only an OFX is imported.

Two stories will resolve this differently.

**Fix:** add an `ingest` registry of batch hooks, for example
`on_batch_applied(conn, batch_id, sources) -> None`. Higher engines register a hook at startup. The
hook runs inside the same lot transaction, after every `apply`, in layer order. Derived rows carry
the **triggering** `batch_id`, so `undo` removes them. State that portfolio's caixinha/goal
derivation is a hook, not part of the Nubank adapter.

### F-2 — high — `import_batches` granularity can't hold what FR-2–FR-5 and AD-5 need

A lot may contain several files from several sources. FR-7 imports Nubank CPF, MEI and B3 at once.
Coverage, though, is per **source and account** (`period_start`/`period_end`). The preview is per
source. FR-5 needs the reported `LEDGERBAL` persisted per account and date ("saldo conferido na
data"). FR-2's "arquivo já importado" needs a file fingerprint. A single `import_batches` row can't
hold any of this. The ER diagram shows only `import_batches`.

Legacy rows (jul/2024–out/2026 already in the DB) also have no `batch_id`. Because "Nenhuma outra
tabela guarda cobertura", FR-3 and FR-4 will report the whole history as a gap. AD-16's backfill
list doesn't include `import_batches`.

**Fix:**
- Add `import_batch_files(batch_id, source, account_id|broker, period_start, period_end, reported_balance, file_sha256)`, owned by `ingest`, to the seed and the ER diagram.
- Make coverage derive from that table.
- Add an AD-16 backfill that creates synthetic `legacy` batches per source and account from existing rows.
- State whether "último lote" in the undo rule is global or per source. The PRD implies global.

### F-3 — high — Layer diagram contradicts AD-1 and the code

1. `overview["6 · overview"] --> alerts` puts two layer-6 engines in an import, which AD-1 forbids.
2. `workers --> closing`: no worker calls closing. The real workers import `market.service`,
   `market.fetchers.*`, `wallet.service`, `portfolio.service.invalidate_xirr_cache` and
   `portfolio.constants` (`api/workers/*.py`).
3. `api/engines/jobs/router.py:19` imports `workers.refresh`, so an engine imports the shell.
   `engines/jobs` (the `/api/v1/jobs/refresh` catch-up named in AD-18) has no layer.
   `engines/analytics` (empty) has none either.
4. `alerts --> closing` contradicts AD-10, where providers register into `alerts` and `alerts`
   needs only `common`.

**Fix:**
- Move `overview` to layer 7, or let the overview router compose the alerts count itself.
- Declare `workers` and the jobs router as top-level shell, like `main.py`. The shell may call any engine's `service.py` and is never imported by an engine. Move `engines/jobs/router.py` to `api/workers/router.py`.
- Delete `engines/analytics`.
- Draw `workers` with a "→ services (any)" note.
- Remove the `alerts --> closing` edge, or annotate it as runtime registration.

### F-4 — high — B3 consolidado positions have no table, but AD-8 and AD-13 depend on them

AD-13 reconciles quantities against the "consolidado B3". AD-8 takes retro patrimônio from the
monthly consolidado. Today the consolidado import only writes **prices**
(`api/engines/portfolio/b3_import_service.py:91-117`). No table holds the consolidado's
per-month, per-asset quantity and value, and the Structural Seed lists none.

**Fix:** add `broker_position_snapshots(user_id, month, broker, asset_id, quantity, value, batch_id)`,
owned by `portfolio`, written by the consolidado adapter. Name it in AD-13 and AD-8.

### F-5 — high — Multi-month reads (`leitura ∈ {tri, ano, inicio}`) over closed and open months are undecided

AD-8 governs a single month. AD-14 exposes quarter, year and "since start" reads. A quarter can mix
two closed months (snapshot) with one open month (live). Some metrics aren't additive:

- savings rate must be re-derived from summed components;
- XIRR for a period needs cash flows, and the snapshot stores totals.

Stories will each invent an aggregation.

**Fix:** add a rule.

- `closing.service.build_period_summary(periodo, leitura)` is the only composer.
- It sums additive totals from the per-month summaries (snapshot or live).
- It recomputes ratios from the summed components.
- Period XIRR = start patrimônio (previous month's snapshot) as an outflow, plus the period's aportes and resgates (facts), plus the end value. State whether a closed month's frozen flows or the live flows are used.

### F-6 — high — Operational envelope gaps (local-only)

AD-18 makes the local Docker volume `pgdata` the **only** copy of all financial data. The only
backup in the spine is "`pg_dump` antes de rodar no banco local" (AD-16). These are not decided:

- a routine backup cadence;
- a destination that respects NFR-privacidade (local or encrypted, never cloud plaintext);
- a restore drill;
- who runs `alembic upgrade head` locally, and when. The Fly `release` command used to do this;
- how a failed worker becomes visible in v2.0 now that Discord is deferred. `job_runs` exists but no alert provider reads it;
- what happens to the existing Fly app and Supabase DB (freeze, decommission, or leave). `api/fly.toml` and the deploy jobs exist;
- local auth/session specifics (refresh cookie `secure`/`SameSite` on `http://localhost`, CORS origin), plus the Hermes token path while the API is local-only.

**Fix:** extend AD-18 with these bullets:

- daily `pg_dump -Fc` to a local or encrypted path, keeping N copies, plus a restore test;
- `alembic upgrade head` runs at API container start, or as a documented `make migrate`;
- a `workers` alert provider for "job failed / job overdue" from `job_runs`;
- Fly and Supabase frozen and read-only until v2.1, no writes;
- cookie and CORS settings for local.

Or mark any of these as open questions.

### F-7 — medium — AD-4 and AD-15 lack the shared types that make them enforceable

Pydantic v2 serializes `Decimal` as a JSON **string** by default. The current models are `float`
(`api/engines/market/models.py:11`, `api/engines/portfolio/router.py:33`). "Dinheiro sai como number
com 2 casas" will therefore come out as strings in some routes and floats in others.

AD-15's `as_of`/`stale` has no shape, and it clashes with ADR-004's existing `last_updated` key.

**Fix:**
- Define `common.money.Money = Annotated[Decimal, PlainSerializer(..., return_type=float, when_used="json")]` and `Percent` likewise.
- Define one `common.models.Valued[T] = {value, as_of, stale}`.
- State that `last_updated` maps to `as_of`, or the reverse.
- Require these in every `models.py`.

### F-8 — medium — AD-1's list of moves misses cycles that exist in the code

AD-1 moves `constants`, `Alert` and cache helpers. Three more upward edges stay:

- `market.service` and `market.router` call `portfolio.service.upsert_price` and `clear_manual_price`, but `asset_prices` belongs to `market` (`api/engines/market/service.py:260`, `router.py:57,81`);
- `wallet.service` calls `portfolio.service.net_quantity` for crypto reconciliation and reads `asset_operations` (`api/engines/wallet/service.py:24,281`);
- `PriceCache` lives in `market/cache.py` and is imported by `portfolio.service` and `main.py`.

There is also a foreign write: `workers/benchmark_workers.py` writes `benchmark_data` with its own SQL.

**Fix:** add to AD-1 or AD-3:

- move the `upsert_price` and `clear_manual_price` price chokepoint into `market.service`;
- move scan-vs-operations reconciliation into `portfolio` (layer 3 may read wallet);
- move `PriceCache` and `check_redis` to `common.cache` in the first story that touches market;
- workers write only through services.

### F-9 — medium — FR-7 "fechados em bloco na migração" vs AD-16 "SQL idempotente"

Closing jul/2024–mai/2026 needs `closing.service.build_month_summary` (Python). An Alembic revision
in pure SQL can't produce it. AD-16 also forbids using `scripts/oneoff` to change the model. The
mechanism is therefore undefined.

**Fix:** state that bulk retro-close is a closing service command, exposed as
`POST /api/v1/closing/retro` and a CLI wrapper. It runs once after the AD-16 data revisions, is
idempotent per (month, version), and has a golden test.

### F-10 — medium — Preview→confirm statefulness is unspecified

`plan` never writes, and `apply(conn, plan, batch_id)` takes a plan. Nothing says whether the web
re-uploads the files on confirm (re-detect, re-parse, re-plan) or confirms a server-held preview
token. A stale plan, with rows imported in between, must be re-planned.

**Fix:** "Confirm re-sends the files. `ingest` re-runs detect, parse and plan inside the
transaction, and aborts with `409 plan_changed` if the counts differ from the preview the client
echoes."

### F-11 — medium — AD-17 cache invalidation leaves derived screens stale

The rule invalidates "the engine prefix plus `closing`/`overview`". A ledger mutation (categorize)
also changes `planning` (restante, financiado) and `alerts`. The existing keys use `"wallets"`, not
`"wallet"` (`web/lib/jobs.ts:48`), and per-feature files exist (`lib/importB3.ts`,
`lib/transit.ts`).

**Fix:** every period-scoped query key includes `["period", periodo]` after the engine segment, and
any money mutation invalidates the predicate "all keys whose engine is downstream of the mutated
engine". Simplest: invalidate everything except `market` and `jobs`. Rename the `wallets` key in the
first web story.

### F-12 — medium — `alert_provider(conn, ctx)` has an undefined `ctx`

Each provider will choose its own context: period, today, user, or thresholds.

**Fix:** define `common.alerts.AlertContext(user_id, today, periodo)` next to `Alert`.

### F-13 — medium — AD-8 snapshot completeness

"Mês fechado nunca recalcula" holds only if every field a period screen shows exists in
`MonthSummary`. Examples are positions per asset, saldo conferido, coverage, `as_of`/`stale`, and
retro "estimada" flags. `dimension_id` has no type: categories are uuid, the payer is text, assets
are uuid.

**Fix:** "A period screen may show only `MonthSummary` fields. A new field means a new `MonthSummary`
field and a re-close." Declare `dimension_id text` together with `dimension_kind`.

### F-14 — low — `assets` ↔ `asset_operations` link is unspecified

The ER diagram has `assets ||--o{ asset_operations`, but the code joins by `asset_symbol` text.

**Fix:** state that `asset_operations.asset_id uuid FK NOT NULL` is backfilled from `asset_symbol`
in the `assets` revision, and that `asset_symbol` stays as a denormalized label until marco 4.

### F-15 — low — Ownership table omissions

These tables have no listed owner:

- `users` and refresh-token storage, owned by `api/auth`;
- `asset_prices`, which `portfolio.service` writes today;
- `job_runs`, whose owner `workers` is not an engine.

`alert_dismissals` has no `user_id`, against AD-18's "tabelas novas têm user_id NOT NULL".

**Fix:** add `auth` to the ownership table, and add `user_id` to `alert_dismissals`, or exempt it
explicitly like the global market tables.

### F-16 — low — Wording inconsistencies

- AD-3: "Exceção única: closing lê via funções das donas" isn't an exception, since everyone reads that way. Reword it or drop it.
- AD-13: "comparadas por quantidade, nunca por valor" conflicts with R$ tolerances for the balance and broker cash. Scope it to "posições".
- AD-10: the severities and keys are Portuguese (`divergencia`, `saldo_divergente`), while the conventions require English snake case for enums. Exempt UI-facing alert keys, or translate them.
- AD-19: "Cobertura ≥ 80%" doesn't name its scope. CI measures `--cov=engines`, the whole package.

### F-17 — low — erDiagram portability

`contém` and `versão` are unquoted labels. They parse in mermaid 11.12.0 but fail in 11.4.1
("got 'é'"). **Fix:** quote every ER relationship label.

### F-18 — low — Deferred "pagination" vs AD-15's paginated envelope

AD-15 defines `{items, total, limit, offset}`, but Deferred says no pagination. **Fix:** name the
lists that use the envelope (transactions, operations), or say "no route paginates in v2.0".

## Ingest SourceAdapter inversion — assessment

- **Direction: sound.** `ingest` (layer 1) owns the `SourceAdapter` protocol, its registry, and
  `import_batches`. The adapters in `ledger` (2) and `portfolio` (3) import `ingest` (edges
  `ledger→ingest` and `portfolio→ingest` are in the diagram) and register in `main.py`. `ingest`
  never imports upward. This matches AD-1's registration bullet.
- **Transaction: sound.** Confirm runs as one `conn.transaction()` across every file's `apply`.
- **Gaps:**
  - derivations that cross engines (F-1);
  - per-file and per-source coverage and balance (F-2);
  - legacy coverage backfill (F-2);
  - the preview→confirm contract (F-10);
  - which adapter wins when two `detect` the same file. Add "detect must be exclusive; ambiguity = `formato_ambiguo` error".
- **Undo ordering:** run hooks' undo, then adapters' undo, in reverse layer order, inside one
  transaction. Rows carry the batch id, so a single `DELETE ... WHERE batch_id` per owner suffices
  once F-1's "derived rows carry the triggering batch_id" holds.

## Layer assignment — assessment

| Claim | Consistent? | Note |
| --- | --- | --- |
| overview @6 reads closing @5 | Yes | Matches AD-8: period reads go through `build_month_summary` or the snapshot. |
| overview @6 → alerts @6 | **No** | Same-layer import (F-3). |
| alerts @6 → closing @5 | Redundant or contradictory | AD-10 has providers register into alerts. closing's "ajuste em mês fechado" provider registers like the others. |
| workers → closing | **No** | No such call. Workers call market, wallet and portfolio services and are the shell (F-3). |
| hermes → ledger | Yes, as a target | Today `hermes/router.py:76` inserts into `transactions` directly. AD-3 covers the move. |
| wallet @2 → market @1 | Yes, as a target | Today wallet also imports portfolio and ledger. Fixes are partly listed (F-8). |
| market @1 → common only | Target only | Today market imports `portfolio.service` (F-8). |
| planning @4 → portfolio, ledger | Yes | Needed for distribution and available-for-spending. |
| closing @5 → planning | Yes | Needs AD-7's planning terms. It also reads ingest coverage, transitively allowed. |

## Brownfield spot-checks (confirmed)

- Locked versions match the Stack table: FastAPI 0.136.3, asyncpg 0.31.0, Alembic 1.18.4, APScheduler 3.11.2, redis 8.0.0, Pydantic 2.13.4, SciPy 1.17.1, structlog 25.5.0, Next 16.2.7, React 19.2.4, TS 5.9.3, Tailwind 4.3.0, react-query 5.100.14, next-themes 0.4.6. TanStack Table, shadcn, radix-ui, lucide-react and Vitest are not installed yet; they are new additions.
- Every page under `web/app/(app)` starts with `"use client"`. `globals.css` has `@theme inline`.
- Migrations are `NNNN_snake.py` with `revision` equal to the file name (0001–0015).
- `common.dates.today_brt` exists. `common` has no `cache`, `deps`, `owner` or `money` yet; `resolve_owner_id` lives in `workers/wallet_workers.py`.
- B3 uses `dry_run` and Nubank has no preview. The B3 dedup key is `asset_operations.external_id` holding `operation_hash(...)`, so the spine's "`operation_hash` da B3" is correct in substance; name the column `external_id`.
- The scheduler uses stdlib `logging` (`workers/scheduler.py:20`), consistent with the logging convention's "sai do logging stdlib".
- The CI workflow has `deploy-api` (Fly) and `deploy-web` (Vercel) on push to main. AD-18's "keep only tests" is an actionable edit. `pytest --cov=engines --cov-fail-under=80` already exists.
- `user_id` exists only on portfolio and wallet tables. Ledger tables have none, as AD-18 states.
- The cycles named in AD-1's Prevents line are real (market↔portfolio, portfolio↔wallet, wallet→ledger `Alert`). There are also `portfolio/transit.py:134`'s lazy import and `engines/jobs → workers`.
