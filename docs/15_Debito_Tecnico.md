---
tipo: registro
projeto: Goodies
titulo: Débito Técnico (consolidado, vivo)
data: 2026-06-07
status: aberto
tags: [goodies, debito-tecnico, code-review]
---

# Débito Técnico — Goodies (registro único e vivo)

Registro **consolidado** de tudo que está pendente. Substitui os antigos
`10_Debito_Tecnico_m2.md`, `13_Debito_Tecnico_m3.md` e `14_Debito_Tecnico_m4.md` (os itens
já **resolvidos** foram removidos — ficam no histórico do git; os code-reviews por milestone
estão nos commits `fix(mX): code-review`). Atualizar este arquivo a cada novo review.

Legenda: **🔴 CRÍTICO** · **🟡 MÉDIO** · **⚪ MENOR (rastrear)**.

---

## 🟡 MÉDIO

### Wallets / scan (m4)
- **Posição manual + escaneada do mesmo ativo = contagem dupla.** Uma posição manual
  (`wallet_address='manual'`) coexiste com uma linha escaneada real para o mesmo
  `(chain, asset_symbol)` — chaves únicas diferem por `wallet_address`, e o sweep nunca apaga
  `is_manual`. `reconcile` (`SUM … GROUP BY asset_symbol`) e o total de `/wallets` somam as duas.
  **Latente hoje** (manual só é usado p/ Liquid confidencial, que não é escaneado). Guard:
  rejeitar upsert manual quando já existe linha não-manual de `(user,chain,asset)`, ou preferir
  uma das duas em `list_wallet_positions`/`reconcile`.
- **`prices_by_ticker` ignora a camada de cache do m3 e duplica SQL.** A valoração de wallet/DeFi
  lê `asset_prices` direto do Postgres (`engines/wallet/service.py`), divergindo do caminho
  cache-aside (Redis→PG) que a tela de Ativos B3 usa (`market.service`). O mesmo
  `SELECT ticker, price_brl, price_usd FROM asset_prices WHERE ticker = ANY($1)` vive em 2 engines.
  Rotear a valoração de wallet/DeFi por `market.service` (ou um helper compartilhado).
- **Binance Simple Earn ignora paginação.** `flexible/position` e `locked/position` retornam
  `size=10` (default) → 11º+ ativo em Earn não contado. Paginar (`current`/`size`).
- **PUT de DeFi não limpa campos nullable.** `defi_router.update_position` usa `COALESCE($n, col)`
  → enviar `maturity_date: null` é ignorado (data antiga fica; alerta segue disparando). Usar
  `model_fields_set`/sentinela p/ distinguir "ausente" de "null".

### Auth (m2, herdado)
- **`refresh_token` no corpo do `/login`.** `TokenResponse.refresh_token` ainda vai no body (ADR-006
  manda só no cookie httpOnly; legível por JS → exfiltrável por XSS). O front já ignora. Remover do
  `TokenResponse` (ajustar `test_login_success`).
- **`/refresh` e `get_current_user` não asseguram `payload["type"]`.** Seguro só porque access e
  refresh usam segredos distintos; assertar o `type` é hardening barato.

### Datas / timezone (m4)
- **`date.today()` em UTC, não BRT.** `defi_router.defi_alerts` e `ledger/alerts.py` → no deploy
  (Fly=UTC) entre 21–24h BRT o "hoje" vira o dia seguinte → off-by-one nas bordas 7d/30d dos
  alertas. Helper único "hoje em America/Sao_Paulo" em todos os compute-on-read.

### Observabilidade (m6)
- **Fetchers `except Exception: return []` sem log no nível do fetcher.** Um bug de parse
  (mudança de schema da API → KeyError/ValueError) fica indistinguível de blip de rede; a posição
  some do scan sem sinal. m6 deve logar exceção + nome do fetcher/endpoint antes do fail-soft.

---

## ⚪ MENOR (rastrear)

### Frontend wallets (review m4, 2026-06-07)
- **EditableNumber dispara 2× no Enter.** `commit()` em `onKeyDown` desmonta o input → `onBlur`
  pode disparar `commit()` de novo. Benigno (upsert/PUT idempotentes), mas guardável com um flag.
- **Sem feedback de erro na edição inline.** Mutation que falha fecha o editor sem mensagem; só o
  refetch do React Query revela o valor antigo. Adicionar `onError`.
- **Separador de milhar pt-BR quebra o parse.** `"1.234,56".replace(",", ".")` → `"1.234.56"` →
  `NaN` (forms manuais + edição inline). Só `1234,56`/`1234.56` é aceito. Normalizar (tirar `.` de
  milhar) — afeta `ManualForm`, `DefiSection` e `EditableNumber`.
- **Reconciliação: delta-poeira marcado como divergência mostra "+0".** `|Δ|≥1e-9` conta como
  divergência mas `fmtQty` (8 casas) renderiza `+0`. Alinhar EPS de cor/contagem ao de exibição.
- **USD do subtotal/total ignora posição sem USD.** `value_usd ?? 0` no `reduce` → se um preço tiver
  BRL sem USD, o "R$X · $Y" subestima o $Y. Raro (CoinGecko devolve brl+usd juntos).
- **POST/PUT de DeFi devolvem `price/value=null`.** Só o GET valora (`_to_response(row)` sem `prices`
  no create/update). Benigno (front invalida `["defi"]` e refetcha).

### Backend (review m4 + herdados)
- **Eficiência do scan (série).** `run_wallet_scan` roda os 6 fetchers em série segurando 1 conexão;
  `HyperliquidFetcher` faz 2 awaits sequenciais (spot + HyperEVM); `EtherscanFetcher` 4 specs em
  série. `asyncio.gather` por fonte cortaria o wall-clock. Cron 3x/dia → prioridade baixa.
- **`reconcile` filtra o registrado por `asset_category='Cripto'` exato.** Op cripto com casing
  divergente de categoria é dropada → delta falso (= saldo escaneado inteiro). Qualidade de dado
  (o import usa o enum canônico), mas o filtro é frágil.
- **Lado escaneado de `reconcile` não é filtrado + endpoint manual sem validação de cripto.** Um
  símbolo manual "lixo" aparece como divergência cripto não-reconciliada.
- **Duplicação (passe de simplificação):** `_defi_symbols` clona `_wallet_symbols` (mesmo
  try/except fail-soft → helper `_distinct_symbols(conn, sql, label)`); `value = qty*price` com
  guarda de None duplicado em `wallet.service` e `defi_router` → `value_of(qty, price)`; `_as_decimal`
  (3×); parser de data BR (`bcb` vs `treasury`); lifecycle "client próprio-ou-injetado" hand-rolled
  em 4 fetchers de loop apesar do `with_client` → `with_client_loop`; `fmtWhen`/`StatusBadge`/`fmtQty`
  copiados entre as páginas market/wallets/reconciliação → módulo de formato compartilhado.
- **`BinanceFetcher._offset_ms` é estado de instância** (não reentrante; ok sob cron `max_instances=1`).
- **`_wallet_symbols` global (sem `user_id`)** — landmine multi-user.
- **XIRR invalida ao mudar só `price_usd`** (XIRR é em BRL) — churn de cache extra.
- **`xirr()` não captura `OverflowError`** (datas a ~150 anos → 500). Baixa prob.
- **`import_operations` idempotência por sufixo de string** (`result.endswith("1")`) — frágil p/ batch.
- **Valoração RF Flash usa dias corridos/30** (fórmula é dias úteis; ~0,44% de deriva).
- **`import_b3` rotula preço de Tesouro como `source='b3'`** no seed (worker corrige na 1ª rodada).
- **Tesouro CSV (~14MB) bufferizado inteiro** (`resp.content`).
- **`enable_market_pricing.py`** one-off com categorias hardcoded → migration / ler de constants.

### Altitude / config-as-code (review m4)
- **Aliases DeFi com sufixo de vencimento.** `coingecko_ids["HYUSD-2609"]`/`["SHYUSD-2609"]` são
  específicos da posição — rolar p/ nova maturidade (`-2703`) deixa o ativo sem preço silenciosamente.
  Normalizar o símbolo (tirar `-NNNN`) antes do lookup, ou mapa de preço por posição.
- **PT/YT Pendle valorados pelo subjacente.** PT sUSDai usa o preço de `susdai` (superestima até o
  vencimento); YT-xSOL sem preço. Um valuator Pendle-aware é débito.
- **`susdai`: id da API ≠ slug do site.** `staked-usdai` (slug) devolve vazio; o id correto é `susdai`
  (via `/search`). Ao mapear novos ativos, confirmar o id pela busca, não pela URL.
- **`etherscan._DEFAULT_SPECS` hardcoda contrato+decimais por token** (PENDLE/ARB) como constantes de
  código — novo token = edição de código. Mover p/ config junto dos endereços de wallet.
- **DCA/custo médio duplicado** (`operations.py` SQL, `service._dca_price`, IR cripto) → função única.

### Multi-user / scripts (herdado)
- **"Primeiro usuário" hardcoded em ~8 scripts** (`SELECT id FROM users … LIMIT 1`). `resolve_owner_id`
  já existe p/ o wallet scan; promover a helper `db` compartilhado + arg `--user`.
- **Scripts sem teste**; cobertura de `b3_import`; **front de import bypassa o interceptor 401**
  (`fetch` cru, sem refresh+retry).
- **Gate validator** (`validate_xirr.py`) com planilha + data hardcoded; valida custo, não o `=XIRR`.

---

## Pendências operacionais (não-código)
- **Deploy m0 (STORY-00-08-09)** Fly.io/Vercel — dev 100% local (docker compose).
- **CDI real:** `settings.cdi_anual` provisório → m5 (série SGS do BCB, sem mexer no `rf_cdi`).
- **Observabilidade (m6):** gate-48h do m3 foi dispensado (worker validado ao vivo); a observação
  formal + alerta de falha de worker no Discord (<5min) é m6.
- **Tesouro em prod:** validar que o ambiente de deploy alcança `tesourotransparente.gov.br`.
