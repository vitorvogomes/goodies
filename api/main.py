"""Aplicação FastAPI do Goodies — STORY-00-02 (+ 00-03/00-04 health, 00-05 auth).

Instância base + CORS + health check com checks plugáveis de componentes
(Postgres em 00-03, Redis em 00-04). Auth JWT (00-05) no router /api/v1/auth.
O pool asyncpg é aberto no startup (lifespan) e fechado no shutdown.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from config import assert_secure, settings
from db.connection import check_postgres, close_pool, init_pool
from engines.alerts import service as alerts_service
from engines.alerts.router import router as alerts_router
from engines.closing import alerts as closing_alerts
from engines.closing import service as closing_service
from engines.closing.checks import register_close_check
from engines.closing.router import router as closing_router
from engines.common.cache import check_redis
from engines.common.month_status import register_month_status
from engines.ingest import service as ingest_service
from engines.ingest.router import router as ingest_router
from engines.ledger import service as ledger_service
from engines.ledger.adapters import NubankStatementAdapter
from engines.ledger.router import router as ledger_router
from engines.ledger.service import register_on_transactions_changed
from engines.market import service as market_service
from engines.market.router import router as market_router
from engines.overview.router import router as overview_router
from engines.planning import targets as planning_targets
from engines.planning.router import router as planning_router
from engines.portfolio import brokers as portfolio_brokers
from engines.portfolio import debentures as portfolio_debentures
from engines.portfolio import hooks as portfolio_hooks
from engines.portfolio import reconciliation as portfolio_reconciliation
from engines.portfolio import service as portfolio_service
from engines.portfolio.analytics_router import router as portfolio_analytics_router
from engines.portfolio.b3_adapter import B3Adapter
from engines.portfolio.brokers_router import router as portfolio_brokers_router
from engines.portfolio.debentures_router import router as portfolio_debentures_router
from engines.portfolio.import_b3_routes import router as portfolio_import_b3_router
from engines.portfolio.reconciliation_router import router as portfolio_reconciliation_router
from engines.portfolio.router import router as portfolio_router
from engines.portfolio.transit_routes import router as portfolio_transit_router
from engines.wallet import service as wallet_service
from engines.wallet.defi import defi_maturity_provider
from engines.wallet.defi_router import router as defi_router
from engines.wallet.router import router as wallet_router
from health import collect_component_status, register_component_check
from hermes.router import router as hermes_router
from workers.job_alerts import job_alerts
from workers.router import router as jobs_router

# Status do mês (AD-8): o real, de `closing` (fechado / aberto / ajuste).
register_month_status(closing_service.ClosingMonthStatus())
register_on_transactions_changed(portfolio_hooks.on_transactions_changed)
ledger_service.register_on_transactions_deleting(portfolio_hooks.on_transactions_deleting)
market_service.register_on_price_changed(portfolio_service.invalidate_xirr_for_ticker)
# Ingestão (AD-5): adapters vivem na engine dona; derivações de cima por hook de lote.
ingest_service.register_adapter(NubankStatementAdapter())
ingest_service.register_adapter(B3Adapter())
ingest_service.register_on_batch_applied(portfolio_hooks.on_batch_applied)
# Story 7.5: depois da derivação, o ativo das transações (resolver do portfolio no ledger).
ledger_service.register_asset_resolver(portfolio_hooks.transaction_assets)
ingest_service.register_on_batch_applied(ledger_service.on_batch_applied_assets)
# Story 7.6: aporte em debênture sugerido na Revisão e confirmado com ela.
ledger_service.register_review_suggester(portfolio_debentures.review_suggestions)
portfolio_service.register_targets_provider(planning_targets.legacy_category_targets)  # 8.2
ledger_service.register_on_review_confirmed(portfolio_debentures.on_review_confirmed)
ingest_service.register_on_batch_undo(portfolio_hooks.on_batch_undo, layer=3)
ingest_service.register_undo_counter(portfolio_hooks.count_derived_for_undo)
ingest_service.register_account_holders(ledger_service.account_holders)
ingest_service.register_source_balances(ledger_service.source_balances)
# Fechamento (AD-8): cada engine registra as precondições do mês.
for _check in (
    ledger_service.close_checks,
    portfolio_service.close_checks,
    portfolio_reconciliation.close_checks,
    wallet_service.close_checks,
):
    register_close_check(_check)
# Central de avisos (AD-10): cada engine registra seu provider; nenhuma importa `alerts`.
for _provider in (
    ledger_service.fixed_cost_alerts,
    ledger_service.overspend_alerts,
    defi_maturity_provider,
    ingest_service.already_imported_alerts,
    ingest_service.csv_unconfirmed_alerts,
    ingest_service.source_alerts,
    ledger_service.pending_review_alerts,
    ledger_service.balance_alerts,
    job_alerts,
    portfolio_brokers.broker_alerts,
    portfolio_reconciliation.reconciliation_alerts,
    closing_alerts.adjustment_alerts,
    closing_alerts.open_month_alerts,
):
    alerts_service.register_alert_provider(_provider)

# Checks incluídos no /api/v1/health (registrados no import do módulo).
register_component_check(check_postgres)
register_component_check(check_redis)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    assert_secure(settings)  # Story 1.6: nunca sobe com segredo público fora de teste
    await init_pool()
    scheduler = None
    # Workers de preço (m3): só fora de testes e quando habilitado (ADR-003).
    if settings.enable_scheduler and settings.environment != "test":
        from workers.scheduler import build_scheduler

        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await close_pool()


app = FastAPI(title="Goodies API", version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ledger_router)
app.include_router(portfolio_router)
app.include_router(portfolio_analytics_router)
app.include_router(portfolio_import_b3_router)
app.include_router(portfolio_transit_router)
app.include_router(portfolio_debentures_router)
app.include_router(portfolio_brokers_router)
app.include_router(portfolio_reconciliation_router)
app.include_router(market_router)
if settings.hermes_enabled:  # Story 1.6: Hermes desligado na v2.0 (HERMES_ENABLED=false)
    app.include_router(hermes_router)
app.include_router(defi_router)
app.include_router(wallet_router)
app.include_router(jobs_router)
app.include_router(alerts_router)
app.include_router(ingest_router)
app.include_router(overview_router)
app.include_router(closing_router)
app.include_router(planning_router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.version,
        "environment": settings.environment,
        **await collect_component_status(),
    }
