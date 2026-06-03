---
tipo: epico
projeto: Goodies
epico: EPIC-04
milestone: m4-broker-integration
titulo: Broker Integration — Binance API e Wallet Scan
status: pendente
tags: [goodies, epic, broker, binance, wallets, cripto]
---

# EPIC-04 — Broker Integration

**Milestone:** m4-broker-integration  
**Objetivo:** Reconciliar posições cripto multi-wallet automaticamente. Eliminação da entrada manual de posições em 6 wallets.  
**Gate de saída:** Posições cripto em Etherscan, Solscan, Liquid e Binance escaneadas automaticamente. `wallet_positions` bate com saldo real (validação manual na UI).

---

## Escopo

### Inclui:
- Schema: `wallet_positions`
- Fetcher Etherscan: ETH, ARB, HYPE (`${WALLET_EVM_ADDRESS}`)
- Fetcher Solscan: SOL, SPL tokens (`${WALLET_SOL_ADDRESS}`)
- Fetcher Liquid Network (blockstream.info/liquid): L-BTC (`${WALLET_LIQUID_ADDRESS}`)
  - **Atenção ADR-005:** client dedicado, não reusar Bitcoin mainchain
- Fetcher Binance API: spot + earn wallets (signed requests HMAC-SHA256)
  - Cron: 3× ao dia (8h, 14h, 20h) — nunca on-demand (rate limit)
- Worker APScheduler: `wallet_scan` cron 3× ao dia
- Benchmark data worker: BCB (CDI/IPCA) daily 22h + yfinance (IBOV)
- Posições DeFi (Phantom): manual com alerta de vencimento para xSOL e hyUSD (29/09/2026)
- Frontend: tela de wallets com posição por wallet/ativo e timestamp de scan
- Reconciliação: comparar posição escaneada com posição registrada em `asset_operations` — delta visível

### Não inclui:
- KuCoin (baixa prioridade — será ativado no mesmo padrão futuro)
- Entrada automática de operações de compra/venda via API de corretora (risco de integridade dos dados)

---

## Stories

- STORY-04-01: Schema wallet_positions + worker scaffold
- STORY-04-02: Fetcher Etherscan (ETH/ARB/HYPE)
- STORY-04-03: Fetcher Solscan (SOL + SPL tokens)
- STORY-04-04: Fetcher Liquid Network (L-BTC) — client dedicado
- STORY-04-05: Fetcher Binance API (spot + earn) com HMAC assinado
- STORY-04-06: Worker wallet_scan cron 3× ao dia + fallback
- STORY-04-07: Worker benchmark_daily (BCB CDI/IPCA + yfinance IBOV)
- STORY-04-08: Entrada manual de DeFi (Phantom) com alerta de vencimento
- STORY-04-09: Alertas de vencimento DeFi (30 dias e 7 dias antes — xSOL/hyUSD 29/09/2026)
- STORY-04-10: Frontend — tela de wallets com scan recente e staleness
- STORY-04-11: Frontend — reconciliação de posição escaneada vs. registrada
- STORY-04-12: Testes de integração (mock Binance + mock chain explorers)

---

## Dependências
EPIC-03 concluído (cache Redis, padrão de fallback).

## Bloqueados por este épico
EPIC-05 (Analytics precisa de posições cripto para XIRR consolidado com cripto)
