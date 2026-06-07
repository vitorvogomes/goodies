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

### Observabilidade (m6)
- **Fetchers `except Exception: return []` sem log no nível do fetcher.** Um bug de parse
  (mudança de schema da API → KeyError/ValueError) fica indistinguível de blip de rede; a
  posição some do scan sem sinal. **Depende do m6** (structlog 06-01/02): logar exceção +
  nome do fetcher/endpoint antes do fail-soft.

---

## ⚪ MENOR (rastrear)

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

### Eficiência / qualidade (baixa prioridade)
- **Scan em série.** `run_wallet_scan` roda os fetchers em série segurando 1 conexão;
  `asyncio.gather` por fonte cortaria o wall-clock. Cron 3x/dia → prioridade baixa.
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
