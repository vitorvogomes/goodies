---
tipo: registro
projeto: Goodies
milestone: m2-portfolio
titulo: Débito Técnico m2 → m3 (Portfolio Engine)
data: 2026-06-05
status: resolvido-no-m3
tags: [goodies, debito-tecnico, code-review, portfolio, m2, m3]
---

> **✅ RESOLVIDO no m3 B0 (2026-06-06).** Os 6 pré-requisitos críticos foram tratados como a
> fundação do m3 (commit 70c456b): §3.4 chokepoint `upsert_price`+precedência is_manual; §3.2
> SSOT de categorias (`engines/portfolio/constants.py`); §3.3 categoria B3 das abas Posição;
> §2.1 XIRR com preço parcial; §3.1 data de avaliação única; §3.5 reconciliação de `docs/02`.
> Os itens **menores** que sobraram (§2.2, §2.3, §3.6–§3.10) foram revistos e migrados para
> **`docs/13_Debito_Tecnico_m3.md`**. Este doc fica como registro histórico do code-review do m2.

# Débito Técnico m2 → m3 — Portfolio Engine

Registro produzido no fechamento do m2 via `/code-review` (3 revisores paralelos:
correção backend, correção frontend+scripts, débito técnico/altitude). Lista os bugs
e dívidas a tratar **antes de iniciar o m3** (Market Engine: preços automáticos
BRAPI/CoinGecko + workers APScheduler).

Legenda: **🔴 CRÍTICO** (corrigir antes do m3) · **🟡 MÉDIO** · **⚪ MENOR (rastrear)** ·
**✅ JÁ CORRIGIDO** neste fechamento.

---

## 1. Correções aplicadas no fechamento do m2 ✅

| # | Arquivo | Correção |
|---|---|---|
| ✅ | `engines/portfolio/service.py` | IR cripto: isenção mensal passou a ser **`<= 35.000`** (era `<`, tributava indevidamente o mês com vendas == R$ 35.000). +teste de boundary. |
| ✅ | `engines/portfolio/analytics_router.py` | `PUT /portfolio/prices` agora **invalida o cache de XIRR** (antes o XIRR servia valor obsoleto por até 1h após mudar um preço). |
| ✅ | `web/.../positions/page.tsx` | Edição inline de preço: **guarda de campo vazio** (`Number("")===0` gravava preço R$ 0,00 e corrompia valoração/alocação/XIRR). |
| ✅ | `web/.../rebalancing/page.tsx` | Input de aporte: mesma guarda de campo vazio. |

---

## 2. Bugs de correção — corrigir antes do m3

### 🔴 2.1 XIRR por categoria/consolidado subestima retorno com preço parcial
`engines/portfolio/service.py` (`calculate_portfolio_xirr`). Quando uma categoria tem
ativos **com** e **sem** preço manual, `_sum_or_none` soma só os valores atuais conhecidos,
mas `build_cashflows` ainda inclui as **compras dos ativos sem preço** como saída — sem o
fluxo terminal correspondente. Resultado: o ativo sem preço é tratado como vendido por R$ 0
→ XIRR da categoria/consolidado fica fortemente negativo/errado.
**Por que importa no m3:** entre coletas do worker, ou para um ativo recém-comprado ainda
sem cotação, o XIRR (métrica-gate do m2) fica errado. Hoje não aparece só porque todos os
ativos têm preço seedado.
**Fix recomendado:** excluir do cashflow consolidado/por-categoria as operações de ativos
com posição aberta (`qty_net>0`) **sem** preço (não dá para valorá-los), OU usar o custo
como valor terminal. Decidir a semântica e cobrir com teste de preço misto.

### 🟡 2.2 `/login` retorna `refresh_token` no corpo JSON
`auth/router.py` (`TokenResponse`). ADR-006 manda o refresh **só** no cookie httpOnly, mas
o login devolve `refresh_token` no body (legível por JS → exfiltrável por XSS). O front já
ignora esse campo. **Fix:** remover de `TokenResponse` (ajustar o teste `test_login_success`
que hoje assere `data["refresh_token"]`).

### 🟡 2.3 `/refresh` e `get_current_user` não validam `type` do token
`auth/router.py` / `auth/security.py`. Seguro hoje só porque access e refresh usam segredos
distintos. Se os segredos forem unificados por engano no `.env`, um access token vira refresh
válido. **Fix:** assertar `payload["type"] == "refresh"`/`"access"` explicitamente (hardening barato).

### ⚪ 2.4 `xirr()` não captura `OverflowError`
`engines/portfolio/xirr.py`. `(1+r)**(d/365)` com `d` muito grande (datas a ~150 anos) pode
estourar `OverflowError`, não capturado (só `ValueError`) → 500 no `/portfolio/xirr`. Baixa
probabilidade. **Fix:** capturar `(ValueError, OverflowError)`.

### ⚪ 2.5 `import_operations` classifica idempotência por sufixo de string
`engines/portfolio/migration.py` (`result.endswith("1")`). Correto só para insert de 1 linha;
frágil se algum dia houver batch. **Fix:** `int(result.split()[-1])`.

---

## 3. Débito técnico estrutural (para o m3)

### 🔴 3.1 Data de avaliação inconsistente (`date.today()` vs datas hardcoded)
`service.py` usa `date.today()` no XIRR; `validate_xirr.py` e `seed_debentures_flash.py`
fixam `2026-06-05`; o preço da Flash em `asset_prices` é congelado na data do seed. Conforme
o calendário avança no m3, o XIRR consolidado deriva diariamente contra uma valoração estática
e o `validate_xirr.py` deixa de reproduzir o número ao vivo. **Fix:** um conceito único de
"data de avaliação" passado por service + seeds + validador.

### 🔴 3.2 Strings de categoria duplicadas em 4 módulos (sem fonte única)
`targets.py`, `b3_import.py` (`b3_category`), `migration.py` (`CATEGORY_MAP`),
`service.py` (`_IR_ALIQUOTAS`) — e o `09_Bridge_M1_M2.md` usa casing diferente ("Ações
nacionais"). Um typo/casing faz a posição não casar com meta/alíquota e **sumir** da alocação/IR
sem erro. O m3 adiciona um 5º produtor (worker de preços). **Fix:** módulo único de constantes
(enum) importado por engine, importadores e fetchers m3.

### 🔴 3.3 Mapa de categoria B3 é allowlist hardcoded de tickers
`b3_import.py` (`_ACOES`/`_ETF`/`_FII` + fallback `endswith("11")→FIIs`). Todo ETF/FII/ação
novo comprado depois do snapshot cai na categoria errada (ETFs também terminam em 11),
corrompendo alocação, rebalanceamento e IR (alíquota por categoria). Sem teste de
misclassificação. **Fix:** derivar categoria das abas "Posição -" do relatório (que já
separam Ações/ETF/Fundos/Tesouro) ou de um mapa versionado com teste.

### 🔴 3.4 `upsert_price` não é o ponto único de invalidação de cache / sem regra `is_manual`
`service.upsert_price` é o chokepoint que tanto o `PUT` manual quanto o worker m3 vão usar.
A invalidação de cache XIRR foi colocada no **router** (corrigido em §1), mas o worker m3
chamará `upsert_price` direto. Também não há regra de precedência: o worker m3 vai
**sobrescrever** um preço manual (`is_manual=true`) de Flash/RF que ele não tem fonte para
cotar? **Fix antes do m3:** mover a invalidação para dentro de `upsert_price` e definir a
precedência `is_manual` (worker não sobrescreve preço manual sem fonte).

### 🔴 3.5 Drift de arquitetura vs `docs/02_Arquitetura.md`
A doc especifica `service.py` + `queries.py` + `models.py` e uma **view SQL `positions`**;
o código real inlina SQL em `service.py`/`operations.py`, não tem `models.py` (respostas são
`dict[str, Any]` sem contrato), e a view `positions` não existe (calculada em Python). O schema
também diverge (`asset_symbol`/`asset_category`/`tipo`/sem `total_amount` vs `ticker`/`category`/
`op_type`/`total_amount` da doc). **Fix:** reconciliar a doc com a realidade (ou refatorar) —
ver §4. Respostas sem modelo Pydantic = sem contrato guardando o front através das mudanças do m3.

### 🟡 3.6 Frontend de import bypassa o interceptor de 401
`web/lib/ledger.ts` (`useImportStatement`) usa `fetch` cru (corpo `text/plain`) e não chama
`refreshAccessToken()`. Import com token expirado → 401 duro em vez do refresh transparente.
É o ponto de entrada da reconciliação m1→m2. **Fix:** rota no `apiFetch` ciente de corpo
raw/multipart, ou um helper de refresh+retry compartilhado.

### 🟡 3.7 "Primeiro usuário" hardcoded em 5 scripts
`import_b3.py`, `migrate_portfolio.py`, `seed_portfolio_targets.py`, `seed_debentures_flash.py`,
`validate_xirr.py` — todos `SELECT id FROM users ORDER BY created_at LIMIT 1`. O worker m3
também precisará de "para quais usuários coletar". **Fix:** helper `resolve_target_user()`
compartilhado ou arg `--user`.

### 🟡 3.8 Lógica de DCA/custo médio duplicada em 3 lugares
SQL em `operations.py` (`calculate_dca_*`), Python em `service.py` (`_dca_price`) e uma 3ª vez
no IR cripto (`calculate_crypto_ir_monthly`). Podem divergir silenciosamente (ex.: tratamento
de split no m3). **Fix:** função única de "custo médio / quantidade líquida".

### 🟡 3.9 Scripts sem testes + `b3_import.py` é o módulo de menor cobertura (76%)
Toda a cola de ingestão (XLSX, arg parsing, seed de preços) é não testada; o `b3_import` será
**reusado** pela automação do Portal do Investidor (m4). **Fix:** testes de parsing/arg + subir
cobertura dos branches de `_to_float`/`_to_date`/abas de posição.

### ⚪ 3.10 Valoração RF Flash usa dias corridos/30 (fórmula é dias úteis)
`rf_pre.py` vs `files/debentures-flash/formula.md` ("Não considerar fim de semana e feriados").
Aproximação calibrada a um snapshot (~0,44% no valor; RF deu 23,94% vs nominal "pré 24%").
Com a tolerância do gate em ±0,1pp, a deriva pode virar o gate ao longo do tempo. **Fix:**
fórmula exata por dias úteis quando a RF ganhar fonte própria.

### ⚪ 3.11 Gate validator com tabela hardcoded e data fixa
`scripts/validate_xirr.py` (`SHEET` de 21 tickers + `date(2026,6,5)`). Valida **custo** (≤1%),
não o XIRR contra uma célula `=XIRR` do Excel (a planilha não tem XIRR único). Congela ao
mudar qualquer preço no m3. **Fix:** capturar o XIRR de referência como fixture versionada e
automatizar a comparação.

### 🟢 3.12 Dados de carteira incompletos (Guanabara, Caixinha, cripto) — PARCIALMENTE RESOLVIDO (pré-m3, 2026-06-06)
O XIRR "consolidado" excluía CDB Guanabara, Caixinha/RDB e cripto. **Resolvido na faxina pré-m3**
(ver `docs/11_Coerencia_Nubank_Portfolio_pre_m3.md`): Caixinha/RDB (Snow Trip, Turbo) e CDB
Guanabara agora são ativos `Renda Fixa` (datas/valores derivados das `transactions`; valoração
`rf_cdi` com `settings.cdi_anual` provisório até o m5/BCB). Consolidado passou a **13,8%**
(baseline 15,25% não é mais comparável — esperado). **Resta:** cripto (m4) e refino do CDI real
no m5. Caveat Turbo (conta-corrente disfarçada) superestima ~+20% — usar saldo manual se preciso.

---

## 4. Reconciliação de `docs/` e `.claude/` necessária

| Documento | O que reconciliar |
|---|---|
| `docs/02_Arquitetura.md` §2.1, §3.2, §3.3 | Schema real de `asset_operations` (`asset_symbol`/`asset_category`/`tipo`, sem `total_amount`); `asset_prices` sem `user_id`; **não existe** view `positions` (cálculo em Python); não há `queries.py`/`models.py`. Endpoints estão em `/api/v1/portfolio/*` + `/api/v1/asset-operations/*` (não exatamente como na doc). |
| `docs/09_Bridge_M1_M2.md` | Casing das categorias ("Ações nacionais" → canônico "Ações Nacionais"); `asset_symbol` de exemplo "Flash-Debênture" confere. |
| `.claude/memory/decisions.md` | Registrar a **decisão de dev usar Postgres local** (`goodies@localhost`) e Supabase só no deploy; ADR-008 cumprido com cache por-usuário `xirr:consolidated:{user_id}`. |
| `.claude/memory/conventions.md` | Adicionar as **6 categorias canônicas** como fonte única (ligado a §3.2). |
| `SESSION_M2.md` | Removido (prompt de init do m2, obsoleto). |

---

## 5. Prioridade para abrir o m3

Antes de plugar o Market Engine, resolver na ordem:
1. **§3.4** chokepoint `upsert_price` (cache + precedência `is_manual`) — é o seam direto do m3.
2. **§3.2 + §3.3** fonte única de categorias + categoria B3 robusta — senão o preço automático
   corrompe alocação/IR silenciosamente.
3. **§2.1** XIRR com preço parcial — a métrica-gate precisa estar correta com cotação incompleta.
4. **§3.1** data de avaliação única — para o XIRR parar de derivar e o gate ser reprodutível.
5. **§3.5** reconciliar a arquitetura (ou a doc) antes de empilhar o m3.
