---
tipo: registro
projeto: Goodies
milestone: m4-broker
titulo: Débito Técnico m4 → m5 (Broker Integration)
data: 2026-06-06
status: aberto
tags: [goodies, debito-tecnico, code-review, broker, wallets, m4, m5]
---

# Débito Técnico m4 → m5 — Broker Integration

Registro do `/code-review` (high effort, 7 ângulos) do backend do m4 (B0..B5-backend).
Legenda: **🔴 CRÍTICO** · **🟡 MÉDIO** · **⚪ MENOR (rastrear)** · **✅ JÁ CORRIGIDO**.

---

## ✅ Corrigido no fechamento do backend m4 (pós-review)

1. **Posição fantasma (varredura):** o scan era upsert-only + filtro `qty>0` nos fetchers →
   ativo vendido/zerado ficava com a quantidade antiga para sempre, poluindo `/positions`
   e `/reconciliation`. Adicionado `wallet.service.sweep_wallet_positions` (snapshot-replace
   **por source**): após um fetcher retornar ≥1 saldo, apaga as linhas daquele source ausentes
   no scan atual. Source fora devolve `[]` → **não varre** (outage ≠ posição fechada).
2. **`ttl_wallet` < gap noturno:** era 4h, mas o scan roda 3x/dia (8/14/20h) com gap de 12h à
   noite → saldo saudável aparecia `stale` ~8h/noite. Subido p/ **14h** (`50400`s); CLAUDE.md
   atualizado.
3. **`run_price_crypto` (cron crítico do m3) dependendo de `wallet_positions` sem fail-soft:**
   `_wallet_symbols` agora tem `try/except → []` (tabela ausente / SELECT falho não derruba o
   ciclo de preço cripto).
4. **`failed` inflado:** `_run_for` contava como falha de fonte os símbolos só-de-wallet fora do
   mapa do fetcher. Agora `failed = core - quotes` (só os tickers das categorias de mercado).

---

## 🟡 MÉDIO — tratar no m5/m6

1. **Binance Simple Earn ignora paginação.** `flexible/position` e `locked/position` retornam
   `size=10` por página (default). >10 ativos em Earn → 11º+ silenciosamente não contados
   (subdimensiona o valor). Adicionar `current`/`size` e paginar. Baixo hoje (poucos ativos).
2. **PUT de DeFi não limpa campos nullable.** `defi_router.update_position` usa
   `COALESCE($n, coluna)` → enviar `maturity_date: null` é ignorado (mantém a data antiga; o
   alerta de vencimento continua disparando). Usar PATCH com `fields_set` (Pydantic
   `model_fields_set`) ou sentinela p/ distinguir "ausente" de "null". (Mesmo padrão do
   `ledger/fixed_costs`, mas lá os campos não são feitos p/ serem limpos.)
3. **`date.today()` em UTC, não BRT.** `defi_router.defi_alerts` (e `ledger/alerts.py`) usam
   `datetime.date.today()`; no deploy (Fly = UTC) entre 21–24h BRT o "hoje" vira o dia seguinte
   → `days_until` off-by-one nas bordas 7d/30d. Extrair um helper único "hoje em America/Sao_Paulo"
   e usar em todos os compute-on-read.
4. **Observabilidade dos fetchers (m6).** Todos os fetchers fazem `except Exception: return []`
   **sem log no nível do fetcher** — um bug de parse (KeyError/ValueError por mudança de schema da
   API) fica indistinguível de blip de rede; a posição some do scan sem sinal. m6 (observabilidade)
   deve logar a exceção com o nome do fetcher/endpoint antes do fail-soft.

## ⚪ MENOR — rastrear

5. **Eficiência do scan.** `run_wallet_scan` roda os 5 fetchers **em série** segurando 1 conexão
   do pool durante todo o IO de rede (até ~30s se um source faz retry 1/2/4s). Opções:
   `asyncio.gather` nos fetchers (wall-clock = máximo, não soma) + adquirir a conexão só p/ os
   upserts. Também: client `httpx` novo por `fetch()` (sem reuse de conexão entre scans);
   Binance puxa `/api/v3/time` todo scan; Solana/Etherscan fazem chamadas independentes em série.
   Cron 3x/dia → prioridade baixa.
6. **`BinanceFetcher._offset_ms` é estado de instância** (não reentrante). Irrelevante hoje
   (cron `max_instances=1`); se algum dia houver `fetch()` concorrente na mesma instância, o
   offset pode ser lido sujo → `-1021`. Passar como parâmetro local de `_signed_get`.
7. **`_wallet_symbols` é global (sem `user_id`).** Correto p/ usuário único; landmine multi-user
   (§3.7) — é o único ponto do caminho de wallet que dropa o escopo por usuário.
8. **Duplicação (passe de simplificação):** `_as_decimal` (defi_router + ledger fixed_costs +
   transactions = 3x) → util compartilhado; parser de data BR (`bcb._parse_date` vs
   `treasury._br_date`); lifecycle "client próprio-ou-injetado" hand-rolled em 4 fetchers de loop
   (etherscan/binance/solana/bcb) apesar do `with_client` — extrair um `with_client_loop`;
   staleness inline (`wallet.service` vs `market.service._is_stale`); `resolve_owner_id` vs a query
   "primeiro usuário" inline em ~8 scripts (promover a `db` helper); boilerplate CRUD owner-scoped
   (4º router quase idêntico).
9. **XIRR invalida ao mudar só `price_usd`.** `upsert_price` considera `changed` quando o USD muda,
   mas o XIRR é calculado em BRL → invalidação extra p/ ativos dual-currency (resultado correto,
   só churn de cache). Comparar só `price_brl` p/ o XIRR.

## ⚪ DeFi/valoração (2026-06-07)

10. **Aliases DeFi em `coingecko_ids` carregam o sufixo de vencimento.** `HYUSD-2609`/`SHYUSD-2609`
    são chaves específicas da posição atual — se o Vitor rolar para uma nova maturidade (ex.: `-2703`),
    o símbolo não casa e o ativo fica sem preço silenciosamente. Generalizar: normalizar o símbolo
    (tirar o sufixo `-NNNN`) antes do lookup, ou mover o mapa de preço para um campo por posição.
11. **PT/YT Pendle valorados pelo subjacente.** PT sUSDai usa o preço de `susdai` (subjacente) —
    superestima levemente (PT < subjacente até o vencimento); YT-xSOL fica sem preço (yield token).
    Aceito como aproximação; um valuator Pendle-aware (PT desconta, YT = saldo×preço-do-yield) é débito.
12. **`susdai`: id da API ≠ slug do site.** O slug CoinGecko `staked-usdai` devolve vazio; o id correto
    é `susdai` (achado via `/search`). Ao mapear novos ativos, confirmar o id pela busca, não pela URL.

## Herdados / operacionais (não-código)
- **Smoke ao vivo pendente** (ambiente do Vitor): validar Liquid confidencial (UTXO blinded),
  shapes do Binance Simple Earn, cobertura Etherscan (só ETH+ARB), mapa de mints Solana
  (só USDC/USDT). Ver checklist de env no plano. **Frontend (04-10/04-11) ainda pendente.**
- **Deploy m0 STORY-00-08-09** (Fly/Vercel) segue pendente — dev 100% local.
