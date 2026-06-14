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
`10_Debito_Tecnico_m2.md`, `13_Debito_Tecnico_m3.md` e `14_Debito_Tecnico_m4.md`. Itens
**resolvidos** são removidos (ficam no git). Atualizar a cada novo review.

> **Pass de débito m4 (2026-06-07).** Após o `/code-review` do m4, um pass dedicado (8 fases,
> branch `m4-broker`, commits `dc2cf06..890b4ba`) sanou **tudo o que não depende de marco
> posterior**: auth hardening (refresh só no cookie + valida `type`); contagem dupla
> manual/escaneada; `today_brt()` nos alertas; valoração wallet/DeFi pelo cache do m3 +
> XIRR só invalida em BRL + `xirr` captura Zero/OverflowError; Binance Earn paginado +
> Tesouro CSV em stream + PUT DeFi nullable; frontend (parse pt-BR, double-fire, erro
> inline, EPS, USD parcial, dedup); dedup backend (`as_decimal`/`value_of`/
> `_distinct_symbols`/`with_owned_client`) + aliases DeFi sem sufixo + specs EVM em config;
> custo-médio com fonte única; higiene de scripts (`resolve_owner`/`--user`, source do
> Tesouro, idempotência por rowcount) + front de import sob o interceptor 401. Suite 410→427.

Legenda: **🔴 CRÍTICO** · **🟡 MÉDIO** · **⚪ MENOR (rastrear)**.

---

## 🟡 MÉDIO

> **Pass de review m4 (2026-06-10).** `/code-review` (high, 7 ângulos × verify) +
> conferências do Vitor. **Corrigidos** (não são mais débito): C1 `_to_date` datetime→date;
> C3 hash de fills idênticos; C4 import consolidado (botão confirmar + cache Redis + contador);
> C5 sweep não apaga sub-unidade que falhou (`ScanBalances.complete`); C6 dupla contagem
> cripto (exclui Cripto do fold per-ativo); C7 CRUD wallet/DeFi invalida XIRR; C8 worker
> cripto reporta apagão; frescor honesto (status `partial` + `data_age` de `scanned_at`);
> trânsito coerente (resíduo `saiu+proventos−aplicado` = caixa em corretora vira o título,
> status no backend: B3→355, RF/Flash→0); revert de preço manual; USD no sleeve/
> reconciliação; `/cashflow` running_balance ancorado; ILIKE no histórico.
> Suite 504→530. Itens **abertos** abaixo.

### Cobertura B3 cruza calendários diferentes (C2 — desenho)
- **A regra de cobertura compara datas de bases distintas.** `_ticker_cutoffs` usa
  `max(data_operacao)` de outra proveniência, mas **negociação = data do negócio** e
  **movimentação = liquidação D+2** (`b3_import_service.py:120`). Na borda de ~2 dias um
  trade pode ser importado em dobro (mov depois de neg) ou descartado como overlap (neg
  depois de mov). Hoje mitigado por importar uma proveniência só; vira problema ao misturar.
  **Fix de desenho:** normalizar para a data do negócio (subtrair D+2 da movimentação) ou
  cobrir por (ticker, qtd, valor) em vez de só data. Sem impacto enquanto não se mistura.

### Caixinhas Nubank — rendimento realizado registrado (RESOLVIDO 2026-06-10)
- **Resolvido.** O extrato Nubank lança o resgate inteiro (principal+juros) como saída de
  principal, então `net = aportes−resgates` subcontava o principal de caixinhas muito
  giradas (Turbo: net R$2.276 vs principal real R$2.400) e o rendimento ficava oculto.
  `scripts/register_caixinha_yields.py` reclassifica resgate→juros (XIRR-neutro): Turbo
  → investido R$2.400 + op `juros` R$123,91; bucket `Nubank-Encerradas` (Extra/Reserva/
  HotCash/Potencial por EXCLUSÃO de snow/turbo/guanabara — evita a ambiguidade de nomes)
  → op `juros` R$351,98, sem posição. Rendimento agora visível em /income + card em
  Posições. Idempotente/reversível.

### Trânsito — reframe do resíduo (RESOLVIDO 2026-06-10)
- **Resolvido.** O número-título do trilho era `em_transito = saiu − aplicado`, que é
  meio-número quando há proventos (um dividendo/juros aparece nos dois lados: reduz `saiu`
  no ledger, mas é excluído de `aplicado`). O resíduo correto é **`saiu + proventos −
  aplicado`** (= caixa real na corretora), universal: se o provento voltou ao Nubank já
  está netado em `saiu` (cancela); se ficou, conta como caixa. `transit.py` agora expõe
  esse resíduo sempre como `caixa_corretora_brl` com status `reconciled`/`caixa_em_corretora`/
  `rendimento_reinvestido`. Resultado: B3 → caixa R$355,31 (= Toro real); RF Nubank → R$0
  conciliado; Flash → R$0. `em_transito` vira detalhe (tooltip).
- **Tesouro — aberto (menor, ~R$31,35 irredutível).** O resíduo do Tesouro (R$145,94)
  decompõe em: **R$114,59** = a única venda real (Tesouro IPCA+ com Juros Semestrais 2055,
  2025-02-24, ganho R$0,79 — é VENDA, não cupom) cuja devolução de caixa nunca entrou no
  ledger Nubank; **R$31,35** = artefato consolidado-vs-transferência (taxas) espalhado nas
  40 compras, irredutível sem o detalhe de taxas do Nubank (imaterial, ~1%). O script
  `scripts/register_tesouro_sale_return.py` (dry-run/idempotente/reversível) insere a
  devolução de R$114,59 → resíduo cai p/ R$31,35; **não aplicado** por tocar a Saldo
  Acumulado (+R$114,59) — aguarda confirmação de que a venda devolveu caixa ao Nubank.

### Observabilidade (m6)
- **Fetchers `except Exception: return []` sem log no nível do fetcher.** Um bug de parse
  (mudança de schema da API → KeyError/ValueError) fica indistinguível de blip de rede; a
  posição some do scan sem sinal. **Depende do m6** (structlog 06-01/02): logar exceção +
  nome do fetcher/endpoint antes do fail-soft.

---

## ⚪ MENOR (rastrear)

### Cripto Tier 2 — preço médio POR ATIVO (Binance ✅; on-chain pendente)
- **Binance FEITO** (modelo pragmático "trades + gap a custo zero"): `crypto_cost_basis`
  (migration 0014) + `scripts/reconstruct_binance_cost.py --commit` (myTrades + câmbio histórico
  **par Binance `USDTBRL`** — CoinGecko free não tem historical). Posições mostram BTC/ETH/SOL
  **por custódia** com preço médio/resultado reais (ETH@binance −R$ 82). O *gap* (escaneado −
  negociado = Earn/depósitos/Convert) entra a custo zero. **IR-cripto** dos trades Binance NÃO
  é coberto (custo vive fora de `asset_operations`) — só relevante se houver venda tributável.
- **On-chain pendente** (preencheria os "—" das linhas @ethereum/@arbitrum/@solana/@bitcoin):
  **partial** no spike — quantidade+data existem (Etherscan/Solana/esplora), mas o custo BRL
  exige preço histórico + decodificar **swaps** cripto↔cripto. Mesmo padrão do Binance, mais
  trabalhoso. **Aguarda decisão.**
- **no** (sem fonte): **HyperEVM** (RPC sem txlist), **Liquid/SideSwap** + **Neobankless**
  (custodial, endereço só de depósito) e **KuCoin** (sem API, conta zerada — lacuna permanente).

### Deferido por decisão (não depende de marco — escopo/feature)
- **PT/YT Pendle valorados pelo subjacente.** PT sUSDai usa o preço de `susdai` (superestima
  até o vencimento); YT-xSOL sem preço. Um valuator Pendle-aware (por par) é débito de
  feature — deferido nesta sessão.
- **Valoração RF Flash usa dias corridos/30** (a fórmula é dias úteis; ~0,44% de deriva).
  Precisa de calendário de feriados ANBIMA (infra nova) → casa melhor com o **m5** (RF/BCB).
- **`_wallet_symbols`/`_defi_symbols` e specs globais sem `user_id`.** O cron de preço é
  global por natureza (preço não é por-usuário), então está correto; vira landmine só se o
  app deixar de ser single-user (nenhum marco prevê). Mesma classe: `BinanceFetcher._offset_ms`
  é estado de instância (ok sob cron `max_instances=1`).
- **`susdai`: id da API ≠ slug do site.** `staked-usdai` (slug) devolve vazio; o id correto é
  `susdai` (via `/search`). Nota de processo: ao mapear novo ativo, confirmar o id pela busca.

### Limpeza / altitude (review m4 2026-06-10, baixa prioridade)
- **Card do sleeve cripto duplicado em 3 telas** (`positions`, `wallets/reconciliation`,
  `transit`): mesmo layout de 4 stats (Investido/Valor/Resultado/XIRR), já com deriva (XIRR
  colorido pelo sinal do resultado numa, do próprio XIRR noutra). Extrair `CryptoSleeveCard`.
- **Sleeve computado 2× na tela Posições:** `/positions` injeta a linha-bloco (via
  `crypto_positions`) E `useCryptoSleeve()` refaz tudo (inclui XIRR) p/ o card — 2× os SELECTs
  de wallet/defi/preço por visita. Renderizar o card da linha-bloco já em `data`.
- **`transit.py` recomputa o sleeve** (XIRR via brentq) só para descartar — o front já tem
  `useCryptoSleeve()`. Retornar só `rails` e o card vir do hook.
- **RAILS/caixinhas hardcodam strings de categoria do ledger** que são CRUD-áveis em
  `categories` (renomear quebra silenciosamente o trilho). Centralizar (Settings ou tabela).
- **`EditableNumber` (wallets) × `PriceCell`/`InlineNumber` (positions)** — editores inline
  quase iguais. `InlineNumber` já unifica o parser pt-BR em Posições; falta unir com Carteiras.
- **4 cópias da assinatura HMAC Binance** nos scripts (`crypto_history_spike`,
  `reconstruct_binance_cost`, `binance_history_discovery`) vs `BinanceFetcher`. Extrair helper.
- **`crypto_cost_basis` (migration 0014) sem leitor** em produção (o per-ativo foi removido em
  `3d92b21`). Tabela + `reconstruct_binance_cost.py` preservados p/ Tier 2 futuro, não exibidos.

### Eficiência / qualidade (baixa prioridade)
- **Scan em série.** `run_wallet_scan` roda os fetchers em série segurando 1 conexão;
  `asyncio.gather` por fonte cortaria o wall-clock. Cron 3x/dia → prioridade baixa.
- **Refresh roda os jobs em série** (`refresh_stale`): o POST /jobs/refresh espera a SOMA das
  durações (B3+Tesouro+cripto+6 fetchers+BCB). `asyncio.gather` dos vencidos cortaria o
  wall-clock do "Atualizar tudo" / catch-up. Mesma classe do scan em série.
- **Scripts sem teste**; falta cobertura de `b3_import`. **`validate_xirr.py`** ainda tem a
  planilha de referência + valores hardcoded e valida o **custo**, não o `=XIRR` (já aceita
  `--user` e usa `settings.evaluation_date`).

---

## Pendências operacionais (dependem de marco/ambiente)
- **Deploy m0 (STORY-00-08-09)** Fly.io/Vercel — dev 100% local (docker compose). O off-by-one
  de timezone já foi corrigido (`today_brt`), mas só "morde" em prod.
- **CDI real:** `settings.cdi_anual` provisório → **m5** (série SGS do BCB, sem mexer no `rf_cdi`).
- **Observabilidade (m6):** gate-48h do m3 dispensado (worker validado ao vivo); a observação
  formal + alerta de falha de worker no Discord (<5min) é **m6**.
- **Tesouro em prod:** validar que o ambiente de deploy alcança `tesourotransparente.gov.br`.
