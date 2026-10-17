---
tipo: bridge
projeto: Goodies
milestone: m1→m2
criado: 2026-06-04
tags: [goodies, bridge, ledger, portfolio, reconciliação]
---

# Bridge Ledger (m1) ↔ Portfolio (m2)

> Contrato de dados e semântica que conecta o Ledger Engine (caixa + receitas/despesas + histórico de aportes) ao Portfolio Engine (posições + operações + retorno).

---

## 1. Fluxo de aportes m1 → m2

### Movimentos de investimento (kind=investment)

O Ledger Engine classifica **saídas de caixa para investimento** com `kind=investment`. Cada movimento grava:

| Campo m1 | Semântica |
|---|---|
| `transactions.amount` | Negativo (saída de caixa). Ex.: `-1.000,00` = aporte de R$ 1.000 |
| `transactions.category` | Rótulo do **destino**. Ex.: "Toro (B3)", "Binance", "Flash Capital debêntures" |
| `transactions.description` | Descrição breve ou vazia. **NÃO é canal de operação** |
| `transactions.date` | Data do aporte (m2 usa como timestamp) |

### Destinos mapeados (m1 category → m2 broker/modelo)

| m1 category | m2 broker | Modelo | Fonte de dados m2 | Export externo? |
|---|---|---|---|---|
| **Caixinha/RDB Nubank** | "Caixinha/RDB" | Flow-based | Fluxos m1 + valor snapshot manual | Não |
| **Renda Fixa Nubank** | "Renda Fixa Nubank" | Flow-based | Fluxos m1 + API Tesouro Direto (m3) | Quase não |
| **Toro (B3)** | "Toro" | Holding-based | B3/CEI export + cotação BRAPI | **Sim** |
| **Santander Corretora** | "Santander" | Holding-based | CEI export + cotação BRAPI | **Sim** |
| **Binance** | "Binance" | Holding-based | Binance API (m4) | **Sim** |
| **Liquid / DeFi** | "Liquid" / "DeFi" | Holding-based | Wallet scan (m4, ADR-005) + chain explorer | **Sim** |
| **Flash Capital debêntures** | "Flash" | Flow-based | Fluxos m1 + valor prefixado (fórmula) | Não |

**Regra:** se o m1 grava `category = 'Toro (B3)'` e o ativo em m2 é `PETR4`, o link semântico é:
- `asset_operations.broker = 'Toro'`
- `asset_operations.asset_category = 'Ações Nacionais'` (categoria canônica — `engines/portfolio/constants.py`)

### Movimentos de resgate (kind=investment, amount positivo)

"Resgate RDB", "Venda B3", etc. são **resgates** — registram como `kind=investment` com `amount > 0` (entrada de caixa).

| Cenário | m1 tratamento | m2 impacto |
|---|---|---|
| Resgate de R$ 500 da Caixinha | `amount = +500`, `category = 'Caixinha/RDB'` | Reduz saldo da Caixinha |
| Venda de 10 cotas PETR4 por R$ 759 | `amount = +759`, `category = 'Toro (B3)'` | Aciona `operacao.tipo = 'venda'` |
| DeFi liquidação de posição | `amount = +1.234`, `category = 'Liquid/DeFi'` | Posição atual deve reduzir (wallet scan confirma) |

---

## 2. Métrica primária: XIRR

**m1 não calcula XIRR.** O m2 Portfolio Engine é responsável.

### Input: tabela m2 `asset_operations`

```sql
CREATE TABLE asset_operations (
    id UUID PRIMARY KEY,
    broker TEXT NOT NULL,           -- 'Toro', 'Binance', 'Caixinha/RDB', etc.
    asset_category TEXT NOT NULL,   -- canônicas: 'Ações Nacionais', 'Renda Fixa', 'Cripto', etc.
    asset_symbol TEXT NOT NULL,     -- 'PETR4', 'BTC', 'Flash-Debênture', etc.
    tipo ENUM ('compra','venda','juros','dividendo') NOT NULL,
    valor_unitario NUMERIC(15, 2) NOT NULL,
    quantidade NUMERIC(15, 8) NOT NULL,
    data_operacao DATE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id)
);
```

**XIRR sobre todas as operações do ativo** = taxa interna considerando cada compra/venda + data.

**XIRR consolidado** = taxa considerando toda a carteira (fluxo caixa de entrada/saída).

### Ponte: m1 → `asset_operations`

Existe uma **correspondência lógica** (não FK):
- `asset_operations` **referencia implicitamente** o m1 via `broker + data_operacao`
- Se m1 tem `{date: '2024-07-15', category: 'Toro (B3)', amount: -5000}`, significa "aporte de 5k em B3 em 15/jul"
- O m2 reconcilia: "em 15/jul comprei X cotas de PETR4 a Y reais, totalizando 5k" → entry em `asset_operations`

**Fluxo de entrada manual m1 → m2:**
1. Usuário importa extrato Nubank → m1 grava `kind=investment, category='Toro (B3)', amount=-5000`
2. Usuário acessa m2 Portfolio → vê "Pendente: reconciliar aporte Toro em 15/jul de R$ 5.000"
3. Usuário entra a operação real (ex.: "100 cotas PETR4 a 50") → m2 insere em `asset_operations`
4. m2 calcula XIRR usando `asset_operations`; m1 exibe o aporte no Ledger

### Validação: gate m2 = XIRR Python == Excel XIRR (±0,1 pp)

Usa dados históricos jan/2024→junho/2026 da planilha (aba OPERAÇÕES, ~400 linhas).

---

## 3. Taxa de poupança (m1) vs. taxa de investimento (m2)

Ambas são **não mutuamente excludentes**. Usuário é motivado por ambas.

| Métrica | Fórmula | Quem calcula | Uso |
|---|---|---|---|
| **Savings rate (B)** | `(receita − consumo) / receita × 100` | m1 Ledger | Taxa de poupança (economizar caixa) |
| **Investment rate (A)** | `total_investido / receita × 100` | m1 Ledger (bridge m2 futuro) | Velocidade de acumulação de patrimônio |
| **XIRR consolidada** | Taxa interna de retorno em %; anualizada | m2 Portfolio | Rentabilidade real da carteira |
| **Retorno real** | `(1 + XIRR) / (1 + inflação) − 1` | m5 Analytics | Poder de compra (XIRR − IPCA) |

---

## 4. Destinos flow-based vs. holding-based

### Flow-based (fluxos m1 = custo; valor snapshot manual)

**Caixinha/RDB**, **Renda Fixa Nubank** (Tesouro Direto + CDB), **Flash debêntures**.

- **Entrada:** m1 grava aporte (`amount < 0`)
- **Saída:** m1 grava resgate (`amount > 0`)
- **Valor atual:** usuário insere manual em m2 (ou API se publica: Tesouro → API Tesouro Direto em m3)
- **Custo médio:** `total_aportes − total_resgates`
- **Ganho:** `valor_atual − custo`
- **XIRR:** calculado sobre fluxos (aportes/resgates com data)

**Exemplo:** Caixinha Nubank
- 01/jan: aporte R$ 1.000 (m1: `-1.000`, m2: insere operação "aporte")
- 15/fev: aporte R$ 500 (m1: `-500`)
- 20/abr: resgate R$ 600 (m1: `+600`)
- Hoje: saldo manual = R$ 1.200 (é o valor com juros, acima do custo R$ 900)
- XIRR = solução de NPV(r) sobre fluxos: `-1000, -500, +600, +1200` com datas

### Holding-based (posição contínua via scanner/API)

**Toro/B3**, **Binance**, **DeFi/Liquid**.

- **Entrada:** m1 grava aporte (`amount < 0`); m2 reconcilia qual ativo/quantidade
- **Saída:** m1 grava venda (`amount > 0`); m2 reconcilia
- **Posição atual:** m2 scanner/API lê **hoje** (m4: Binance API, wallet scan)
- **Valor atual:** preço × quantidade (preço vem do m3 Market Engine)
- **Custo médio:** `SUM(compra.preço × compra.qtde) / SUM(compra.qtde)`
- **Ganho:** `valor_atual × quantidade − SUM(compra.preço × compra.qtde)`
- **XIRR:** calculado sobre histórico de compra/venda (operações m2)

**Exemplo:** Toro (B3)
- 01/jan: compra 100 PETR4 a 50 (m1: `-5.000`, m2: operação "compra")
- 15/fev: compra 50 PETR4 a 52 (m1: `-2.600`)
- 01/jun: venda 30 PETR4 a 60 (m1: `+1.800`)
- Hoje: API Toro/CEI diz "você tem 120 PETR4" (100−30 da venda + resgate de evento corporativo?)
- Posição: 120 × preço_hoje (do BRAPI)
- XIRR = sobre fluxos de compra/venda com date

---

## 5. Sincronização de dados em cascata

```
m1 Ledger (daily)
  → transações importadas de OFX Nubank
  → cashflow + savings_rate visíveis
  
m2 Portfolio (on-demand)
  ← lê m1 transações com kind=investment, destino = categoria
  → usuário reconcilia/entra operações reais
  → asset_operations são a fonte de verdade para XIRR
  
m3 Market (cron)
  ← preço_ativo atualiza via fetcher (BRAPI, CoinGecko, Tesouro API)
  → portfolio usa preço_hoje
  
m4 Broker (cron)
  ← wallet_positions atualiza via scanner (Binance API, Etherscan, etc.)
  → posição holding-based reconcilia
  
m5 Analytics (cron)
  ← lê m2 (XIRR, posições, alocação)
  ← lê m4 (alertas, vencimentos)
  ← lê m3 (preços, benchmarks)
  → dashboard integrado
```

---

## 6. Dados que FALTAM para XIRR gate

**XIRR depende de dados históricos precisos.** Atualmente (2026-06-04):

| Dados | Status | Impacto em m2 |
|---|---|---|
| Histórico OPERAÇÕES (01/2024–06/2026) | ✅ Completo na planilha | XIRR gate pode validar |
| Transações m1 jan–jun/2026 importadas | ✅ Completadas (320 tx) | Aportes/resgates via fluxos OK |
| Posições atuais B3 (Toro) | ❓ Partial (manual 06/2024) | m2 precisa de export CEI/Toro |
| Posições atuais DeFi/wallets | ❓ Manual (4 wallets) | m4 scanner vai automatizar |
| Posições atuais Binance | ❓ Manual | m4 API vai automatizar |
| Preços históricos B3 | ✅ BRAPI API (daily) | m3 fetcher cobre |
| Preços históricos Tesouro | ✅ API Tesouro Direto | m3 fetcher cobre |
| Preços históricos cripto | ✅ CoinGecko (daily) | m3 fetcher cobre |

**Ação p/ m2:**
- Seed m2 com operações jan/2024→jun/2026 da planilha (manual, via migration ou script)
- XIRR = teste com seed histórica
- Gate = validar Python XIRR vs. Excel XIRR (±0,1 pp) antes de mover para m3/m4

---

## 7. Constrastes com a planilha

| Item | Planilha | Goodies | Diferença |
|---|---|---|---|
| Receita mensal | Manual (7 fontes) | m1 Ledger importado Nubank | Requer Santander import + dedupe |
| Despesa mensal | Manual subset | m1 Ledger importado (tudo) | Planilha pode ser menor (dedupe de categoria?) |
| Taxa poupança | Manual `(receita-despesa)/receita` | m1 `savings_rate` view | Fórmula idêntica, dados podem diferir |
| Aportes investimento | Manual (aba OPERAÇÕES) | m1 `kind=investment` + m2 reconciliação | Rastreamento automático via categorias m1 |
| XIRR | Manual Excel (irr.serie) | m2 Portfolio (`scipy.optimize.brentq`) | Python vs. Excel; gate ±0,1 pp |
| Posições atuais | Manual snapshot (de quê?) | m2 + m3 + m4 automático | Dinâmico + atualizado |
| Alertas concentração Flash | Manual visual | m5 Engine | Automático + Discord webhook |

---

## 8. Checklist: o que m2 precisa herdar de m1

- [ ] Setup `asset_operations` schema + CRUD (02-01 a 02-03)
- [ ] Preço médio ponderado (DCA) — fórmula m1 já existe em docs (02-04)
- [ ] XIRR Python via `scipy.optimize.brentq` (02-05, gate crítico)
- [ ] Endpoints XIRR por ativo + consolidado (02-06)
- [ ] Posição atual = soma operações com preço manual (02-07)
- [ ] Alocação atual vs. meta (02-08)
- [ ] Motor rebalanceamento (02-09)
- [ ] Seed m2 com planilha (02-17-18, gate crítico)
- [ ] Validar XIRR vs. Excel XIRR (02-17-18, gate crítico)

---

*→ [[08_Contexto_Financeiro]] | [[CLAUDE.md]] (Stack)*
