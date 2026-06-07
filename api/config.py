"""Configuração da aplicação via pydantic-settings — STORY-00-02.

Lê variáveis de ambiente (e `.env` em dev). Valores ausentes usam os defaults
abaixo. Em produção (Fly.io) as variáveis vêm de secrets, não de arquivo `.env`.
"""

from datetime import date
from pathlib import Path

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# O `.env` (e o `.env.example`) ficam no raiz do repo, não em api/. Resolvemos o
# caminho absoluto p/ que `uv run` a partir de api/ leia o arquivo certo. Em
# produção (Fly.io/Docker) o arquivo não existe → cai p/ env vars + defaults.
_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"

_DEV_DATABASE_URL = "postgresql://goodies:goodies@localhost:5432/goodies"
_DEV_SECRETS = {
    "jwt_secret_key": "dev-insecure-jwt-secret",
    "jwt_refresh_secret_key": "dev-insecure-refresh-secret",
    "hermes_service_token_secret": "dev-insecure-hermes-secret",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ROOT_ENV), extra="ignore")

    environment: str = "development"
    version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = _DEV_DATABASE_URL

    # Auth JWT (ADR-006). Secrets vazios no .env caem p/ defaults de dev.
    jwt_secret_key: str = _DEV_SECRETS["jwt_secret_key"]
    jwt_refresh_secret_key: str = _DEV_SECRETS["jwt_refresh_secret_key"]
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    hermes_service_token_secret: str = _DEV_SECRETS["hermes_service_token_secret"]
    hermes_token_ttl_days: int = 90

    # Import Nubank (STORY-01-13-14): nomes/CPF do próprio usuário (separados por
    # vírgula) p/ marcar transferências entre contas próprias como "transferência
    # interna" (fora do caixa). Vazio = sem detecção. Definir no .env (PII).
    ledger_self_identifiers: str = ""

    # Valoração pós-fixada (pré-m3): CDI anual de referência (fração) p/ caixinhas/CDB
    # do Nubank (engines.portfolio.rf_cdi). Provisório — o m5 importa a série do BCB.
    cdi_anual: float = 0.1065

    # Data de avaliação única (§3.1): "hoje" do XIRR/valoração. Vazio/ausente → data
    # corrente. Fixar via env EVALUATION_DATE=YYYY-MM-DD p/ reproduzir o gate ou gerar
    # relatórios "as-of" determinísticos (service + workers + validate_xirr + seeds).
    evaluation_date: date | None = None

    # ---- Market Engine (m3) — fetchers de preço ----
    brapi_token: str = ""  # BRAPI (B3) — https://brapi.dev
    coingecko_api_key: str = ""  # CoinGecko (cripto)
    # symbol (UPPER) -> id CoinGecko. Em config, não hardcoded (CLAUDE.md). Override
    # via env COINGECKO_IDS (JSON). Estende conforme a carteira cripto cresce (m4).
    coingecko_ids: dict[str, str] = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "ARB": "arbitrum",
        "HYPE": "hyperliquid",
        "USDT": "tether",
        "USDC": "usd-coin",
        "PENDLE": "pendle",  # PENDLE (Arbitrum) — RABBY (m4)
        # L-BTC (Liquid, ADR-005) vale 1:1 com BTC → reusa o caminho de preço do m3.
        "L-BTC": "bitcoin",
        "L-USDT": "tether",  # USDt na Liquid (SideSwap) → 1:1 USD
        # Aliases DeFi (m4): chave em UPPER (fetcher casa por símbolo.upper()). YT-xSOL
        # fica sem fonte (yield token). Sufixo de vencimento (-2609) = débito (docs/14).
        "XSOL": "hylo-leveraged-sol",  # xSOL — Hylo Leveraged SOL
        "PT SUSDAI": "susdai",  # PT sUSDai (Pendle) ~ subjacente sUSDai (id API = susdai)
        "HYUSD-2609": "hylo-usd",  # hyUSD (Hylo) — stablecoin ~US$1
        "SHYUSD-2609": "hylo-usd",  # sHYUSD = hyUSD stakeado ~US$1
    }
    # TTLs de cache de preço (segundos). Cripto=2h, XIRR=1h (CLAUDE.md).
    # B3 e Tesouro = 26h: cotação buscada 1x/dia útil (B3: limite free-tier BRAPI
    # 1.000 req/mês; Tesouro Transparente publica preço de fechamento 1x/dia útil),
    # então o preço do dia NÃO deve aparecer "desatualizado" durante o dia.
    ttl_b3: int = 93600
    ttl_crypto: int = 7200
    ttl_tesouro: int = 93600
    ttl_xirr: int = 3600

    # Workers de preço (APScheduler no processo FastAPI). Desligar via env em ambientes
    # onde o cron não deve rodar (ex.: scripts pontuais). Não inicia sob testes.
    enable_scheduler: bool = True

    # ---- Broker Integration (m4) — wallet scan + Binance + benchmark ----
    # Chaves/endereços vêm do .env (PII/segredos — gitignored; placeholders no .env.example).
    # Vazios caem em defaults; os fetchers de wallet ficam no-op sem credencial.
    etherscan_api_key: str = ""  # ETH/ARB/HYPE — https://etherscan.io (V2 multichain)
    solscan_api_key: str = ""  # SOL/SPL — https://solscan.io
    binance_api_key: str = ""  # Binance spot+earn — CRON ONLY, assinado HMAC-SHA256
    binance_api_secret: str = ""
    wallet_rabby_address: str = ""  # Rabby — ETH/ARB/PENDLE (Etherscan) + HYPE (L1 spot + HyperEVM)
    wallet_phantom_sol_address: str = ""  # Phantom — endereço SOL (JSON-RPC)
    wallet_sideswap_address: str = ""  # SideSwap — recebimento Liquid (L-BTC + USDT)
    # Liquid Network (ADR-005): client DEDICADO; base .../liquid/api (NÃO /btc/api).
    liquid_base_url: str = "https://blockstream.info/liquid/api"
    lbtc_asset_id: str = ""  # constante pública L-BTC (64 hex) — valor no .env
    lusdt_asset_id: str = ""  # asset id público do USDt na Liquid (64 hex) — valor no .env
    # Bitcoin mainchain (Trust) — ADR-005: client SEPARADO do Liquid (NÃO /liquid/api).
    wallet_trust_btc_address: str = ""  # Trust — endereço BTC mainchain (bc1q...)
    btc_base_url: str = "https://blockstream.info/api"
    # RPC Solana (JSON-RPC). Default = endpoint público (throttla); apontar p/
    # Helius/QuickNode no .env evita o rate-limit do mainnet-beta público.
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"
    # HyperEVM (chain EVM da Hyperliquid): HYPE é o gas token NATIVO (18 casas). O scan L1
    # spot (Info API) não enxerga o saldo aqui — `eth_getBalance` no RPC público.
    hyperevm_rpc_url: str = "https://rpc.hyperliquid.xyz/evm"
    # TTLs de cache (segundos). wallet = 14h: o scan roda 3x/dia (8/14/20h BRT), com
    # gap noturno de 12h (20h→8h); o TTL precisa ser > esse gap p/ não marcar saldo
    # saudável como stale durante a noite. benchmark CDI/IPCA = 24h.
    ttl_wallet: int = 50400
    ttl_benchmark: int = 86400

    @field_validator("evaluation_date", mode="before")
    @classmethod
    def _empty_evaluation_date(cls, v: object) -> object:
        # .env de dev pode trazer EVALUATION_DATE= (vazio) → data corrente (None).
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def _fallback_database_url(cls, v: object) -> object:
        # .env de dev pode trazer DATABASE_URL= (vazio) → usa o Postgres local do compose.
        if v is None or (isinstance(v, str) and not v.strip()):
            return _DEV_DATABASE_URL
        return v

    @field_validator(
        "jwt_secret_key",
        "jwt_refresh_secret_key",
        "hermes_service_token_secret",
        mode="before",
    )
    @classmethod
    def _fallback_secret(cls, v: object, info: ValidationInfo) -> object:
        # Secret vazio no .env → default de dev (inseguro; prod define via secrets).
        if info.field_name and (v is None or (isinstance(v, str) and not v.strip())):
            return _DEV_SECRETS[info.field_name]
        return v


settings = Settings()
