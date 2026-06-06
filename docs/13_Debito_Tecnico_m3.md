---
tipo: registro
projeto: Goodies
milestone: m3-market
titulo: Débito Técnico m3 → m4 (Market Engine)
data: 2026-06-06
status: aberto
tags: [goodies, debito-tecnico, code-review, market, m3, m4]
---

# Débito Técnico m3 → m4 — Market Engine

Registro do fechamento do m3 (`/code-review` 4 ângulos: correção engines/workers,
correção fetchers, correção frontend, cleanup/altitude) + itens menores herdados do m2.

Legenda: **🔴 CRÍTICO** · **🟡 MÉDIO** · **⚪ MENOR (rastrear)** · **✅ JÁ CORRIGIDO no m3**.

---

## ✅ Já corrigido no fechamento do m3 (commit fix pós-review)
- **Override manual mascarado por cache:** `POST /market/prices` agora chama
  `market.service.invalidate_price_cache(ticker)` (manual sempre vence também em `/market`).
- **`upsert_price` apagava `price_usd`** numa edição manual de BRL → `COALESCE(EXCLUDED, existente)`.
- **Front:** `useSetManualPrice` invalida `["market"]` além de `["portfolio"]`.
- `calculate_positions`: uma varredura de `asset_prices` (preço+is_manual) em vez de duas.
- `scheduler`: job cripto com `timezone=America/Sao_Paulo` (consistência com o B3).

## 🟡 MÉDIO — tratar no **m4 B0** (antes de escrever os fetchers de wallet)
1. **Fatorar a base dos fetchers.** Os 3 fetchers do m3 (BRAPI/CoinGecko/Tesouro) repetem o
   mesmo scaffold "client próprio-ou-injetado + `with_retry` + fail-soft". O m4 adiciona **5
   fetchers** (Etherscan, Solscan, Liquid, Binance, BCB/benchmark) — extrair um `_fetch(do_request)`
   em `fetchers/base.py` (ou base class / async-ctxmanager) ANTES, senão a duplicação multiplica.
2. **`market.service.list_user_prices` é N+1.** Faz um `get_price` por ticker (1 SELECT + 1 Redis
   GET cada). O m4 cresce a carteira (cripto/wallets). Trocar por um `SELECT ... WHERE ticker =
   ANY($1)` + Redis MGET, montando em memória (1 ida ao DB + 1 ao Redis).
3. **Worker do XIRR flusha o cache toda rodada.** `upsert_price` chama `_invalidate_xirr_for_ticker`
   mesmo quando o preço não mudou → o cache de XIRR (TTL 1h, ADR-008) raramente sobrevive (cripto
   */2h). Invalidar só quando `price_brl`/`price_usd` realmente mudou (comparar com o valor anterior).

## ⚪ MENOR — rastrear
4. **Reuso de parsers.** `treasury._br_float`/`_br_date` duplicam `migration._to_float`/`parse_date`;
   `brapi._strip_fractional` duplica `b3_import.parse_produto`. Promover a um util compartilhado
   (cuidado com o acoplamento market→portfolio; hoje já há `constants`).
5. **`import_b3` rotula preço de Tesouro como `source='b3'`** no seed do snapshot (deveria ser
   `'tesouro'`). Cosmético — o worker corrige na 1ª rodada; só afeta a janela inicial.
6. **Tesouro CSV (~14MB) é bufferizado inteiro** (`resp.content`), apesar do "baixa memória" no
   docstring (o parse é single-pass, mas o download não). Opção: range-tail (suffix `bytes=-N` não
   é honrado; usar `bytes=START-` após descobrir o tamanho) ou stream linha-a-linha.
7. **`enable_market_pricing.py`** é script one-off com categorias hardcoded — poderia ser uma
   migration Alembic (versionada) e/ou ler de `B3_CATEGORIES | TREASURY_CATEGORIES`.
8. **`failed = len(symbols) - len(quotes)`** assume `quotes ⊆ symbols` (verdade p/ os fetchers
   atuais). Se um fetcher futuro devolver chave extra/normalizada, o contador fica errado/negativo.

## ⚪ Herdados do m2 (não bloqueiam; revisar quando tocar a área)
- **§2.2** `refresh_token` no body do login — **verificar** (o fix de refresh do m2 pós-gate pode
  ter resolvido); **§2.3** assert de `type` no token.
- **§3.6** import do front bypassa o 401. **§3.7** "primeiro usuário" hardcoded em ~8 scripts
  (multi-user readiness — não crítico p/ usuário único). **§3.8** DCA duplicado (`_dca_price` x
  `calculate_dca_*`). **§3.9** scripts sem teste / `b3_import` cobertura. **§3.10** Flash dias
  corridos vs úteis.

## Pendências operacionais (não-código)
- **Gate 48h:** dispensado a pedido do Vitor (não esperar). O worker foi **validado ao vivo**
  (23/23 cotados, zero exceção em múltiplas execuções); a observação formal de 48h + alerta de
  falha de worker no Discord é **m6** (observabilidade). Ver `docs/12_Gate_M3_Market.md`.
- **Deploy (m0 STORY-00-08-09):** Fly.io/Vercel ainda pendentes — dev 100% local (docker compose).
- **CDI real:** `settings.cdi_anual` provisório → m5 troca pela série do BCB (sem mexer no `rf_cdi`).
- **Tesouro em prod:** o CSV do Tesouro Transparente não tem WAF/quota; validar só que o ambiente
  de deploy alcança `tesourotransparente.gov.br`.
