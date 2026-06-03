---
tipo: epico
projeto: Goodies
epico: EPIC-03
milestone: m3-market-data
titulo: Market Engine — Preços Automáticos
status: pendente
tags: [goodies, epic, market, precos, workers]
---

# EPIC-03 — Market Engine

**Milestone:** m3-market-data  
**Objetivo:** Coleta automática de preços B3, cripto e Tesouro Direto via workers com cache Redis. Substituir atualização manual de preços na planilha.  
**Gate de saída:** Preços B3 e cripto atualizando automaticamente a cada ciclo do worker sem erro. Dashboard mostra valores de mercado atuais sem entrada manual.

---

## Escopo

### Inclui:
- Schema: `asset_prices` (upsert por ticker)
- Fetcher BRAPI.dev: ações, ETFs, FIIs — com remoção de sufixo F para fracionárias
- Fetcher CoinGecko: BTC, ETH, SOL, PENDLE, HYPE, USDT — mapa de IDs configurável
- Fetcher Tesouro Direto: matching flexível por nome de título
- Cache Redis com TTL: B3 4h, cripto 2h, Tesouro 6h
- Workers APScheduler integrados ao FastAPI:
  - `price_b3`: cron dias úteis 9h–18h a cada 4h
  - `price_crypto`: cron diário a cada 2h
- Fallback: API falha → cache Redis → Postgres (`asset_prices`) → valor manual
- Interface para atualização manual de preço (Flash Debênture, CDB, DeFi)
- Endpoint de cotação BRL/USD para conversão de cripto
- Endpoints: `GET /market/prices`, `GET /market/prices/{ticker}`, `POST /market/prices/{ticker}` (manual)
- Frontend: tela de preços atuais com timestamp e indicador de staleness

### Não inclui:
- Wallet scan (EPIC-04)
- Binance API (EPIC-04)

---

## Stories

- STORY-03-01: Schema asset_prices + interface de cache Redis (PriceCache class)
- STORY-03-02: Fetcher BRAPI.dev com retry exponential backoff
- STORY-03-03: Fetcher CoinGecko com mapa de IDs configurável
- STORY-03-04: Fetcher Tesouro Direto com matching flexível por nome
- STORY-03-05: Worker APScheduler — price_b3 (cron dias úteis 4h)
- STORY-03-06: Worker APScheduler — price_crypto (cron 2h)
- STORY-03-07: Lógica de fallback (Redis → Postgres → manual, com flag stale)
- STORY-03-08: Endpoint de update manual de preço (ativos sem API)
- STORY-03-09: Endpoints de leitura de preços
- STORY-03-10: Atualizar Portfolio Engine para usar preços do Market Engine (posições com valor de mercado real)
- STORY-03-11: Frontend — tela de preços atuais com staleness indicator
- STORY-03-12: Testes de integração dos fetchers (mock de APIs externas)

---

## Dependências
EPIC-02 concluído (tickers vêm do portfolio).

## Bloqueados por este épico
EPIC-04 (wallet scan usa mesma interface de cache), EPIC-05 (Analytics precisa de preços atuais para XIRR)
