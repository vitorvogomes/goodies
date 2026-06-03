---
tipo: contexto_financeiro
projeto: Goodies
mestra_responsavel: Hatchepsut
criado: 2026-06-02
tags: [goodies, raio-x, financeiro, planilha, contexto]
---

# Goodies — Contexto Financeiro Completo

> Raio-X produzido pela Hatchepsut em 02/06/2026 com base na planilha financeira completa.
> Este documento é a fonte de verdade financeira para o design do Goodies.
> A Minerva lê este arquivo antes de qualquer decisão de dados ou schema.

---

## 1. Snapshot patrimonial (junho 2026)

| Indicador | Valor |
|---|---|
| Total investido | R$ 27.442,59 |
| Valor atual da carteira | R$ 28.303,02 |
| Resultado nominal total | R$ 860,43 |
| Rentabilidade nominal (simples) | 3,14% |
| Rentabilidade real (deflacionada) | **-1,31%** |
| Período de investimento | 22 meses (jul/2024 → jun/2026) |
| Aporte médio mensal realizado | R$ 1.247,39 |
| Aporte mensal meta | R$ 4.500,00 |
| Caixa disponível | R$ 4.743,51 |
| **Patrimônio líquido total** | **~R$ 33.046** |

**Atenção:** O "Rent. Nominal 3,14%" é calculado como `(resultado - aplicado)/aplicado`. Em portfólio DCA isso é metodologicamente errado — ignora o timing dos aportes. O Goodies deve calcular e exibir XIRR como métrica primária de retorno.

---

## 2. Estrutura de renda (referência: junho 2026)

| Fonte | Valor/mês | % do total |
|---|---|---|
| Flash Capital (sócio/salário) | R$ 7.121,08 | 70,9% |
| Betuel | R$ 1.621,00 | 16,1% |
| Salário | R$ 1.000,00 | 10,0% |
| Extra | R$ 300,00 | 3,0% |
| **Total** | **R$ 10.042,08** | 100% |

**Custos fixos mensais:** R$ 4.239,34  
**Gasto total junho/2026:** R$ 4.470,98  
**Taxa de poupança (junho/2026):** ~51% — excelente, mas precisa ser sistemático.

**Fórmulas de meta (usadas na planilha, válidas):**
- Reserva de Emergência = Custos Fixos × 12 = R$ 4.239 × 12 = **R$ 50.872**
- Liberdade Financeira = Custos Fixos × 300 = R$ 4.239 × 300 = **R$ 1.271.802** (equivalente à regra dos 4% adaptada)

---

## 3. Alocação atual vs. meta

| Categoria | % Atual | % Meta | Desvio | Status |
|---|---|---|---|---|
| CRIPTO | 13,7% | 5,0% | **+8,7pp** | ⚠️ Muito acima |
| AÇÕES NACIONAIS | 8,9% | 10,0% | -1,1pp | Leve déficit |
| ETFs | 10,6% | 12,5% | -1,9pp | Leve déficit |
| FII's | 7,9% | 10,0% | -2,1pp | Abaixo |
| RENDA FIXA | 47,6% | 50,0% | -2,4pp | Abaixo |
| APOSENTADORIA | 11,4% | 12,5% | -1,1pp | Leve déficit |

O motor de rebalanceamento do Goodies já existe como conceito na planilha (campo "Peso" e "Aporte" na aba CARTEIRA). Precisa ser replicado como lógica no Portfolio Engine.

---

## 4. Performance por ativo

### Ações nacionais

| Ativo | Aplicado | Atual | Retorno |
|---|---|---|---|
| PETR4F (18 cotas) | R$ 577,98 | R$ 759,06 | **+31,33%** ✅ |
| CMIG4F (39 cotas) | R$ 425,57 | R$ 430,95 | +1,26% |
| ITSA4F (19 cotas) | R$ 248,07 | R$ 246,24 | -0,74% |
| BBAS3F (37 cotas) | R$ 850,68 | R$ 753,69 | **-11,40%** ⚠️ |
| SOJA3F (50 cotas) | R$ 432,74 | R$ 319,77 | **-26,11%** 🔴 |

**Nota SOJA3:** payout >100% (175%) identificado em análise fundamentalista — red flag. Ativo em deterioração. Ver nota `Payout_Sustentabilidade` no vault.

### ETFs

| Ativo | Aplicado | Atual | Retorno |
|---|---|---|---|
| NASD11 (29 cotas) | R$ 437,74 | R$ 617,70 | **+41,11%** ✅ |
| GOLD11 (22 cotas) | R$ 449,28 | R$ 523,16 | **+16,44%** ✅ |
| ACWI11 (35 cotas) | R$ 515,83 | R$ 587,65 | +13,92% ✅ |
| ALUG11 (14 cotas) | R$ 567,91 | R$ 574,42 | +1,15% |
| USDB11 (7 cotas) | R$ 712,11 | R$ 685,58 | -3,73% |

### FIIs

| Ativo | Aplicado | Atual | Retorno |
|---|---|---|---|
| HFOF11 (71 cotas) | R$ 446,87 | R$ 477,12 | +6,77% |
| MXRF11 (49 cotas) | R$ 469,87 | R$ 489,02 | +4,08% |
| KNCR11 (7 cotas) | R$ 734,68 | R$ 749,00 | +1,95% |
| BTLG11 (5 cotas) | R$ 517,15 | R$ 518,00 | +0,16% |

**Nota:** nenhum FII aqui captura os rendimentos mensais pagos. O Goodies precisa rastrear DY recebido separado do ganho de capital. Esse é um gap crítico.

### Renda Fixa

| Ativo | Aplicado | Atual | Retorno |
|---|---|---|---|
| Flash Debênture | R$ 12.000,00 | R$ 13.207,62 | **+10,06%** |
| CDB Banco Guanabara | R$ 200,00 | R$ 258,45 | +29,23% |

### Aposentadoria (Tesouro Direto)

| Ativo | Aplicado | Atual | Retorno |
|---|---|---|---|
| Selic 2028 | R$ 166,29 | R$ 191,10 | +14,92% |
| Selic 2029 | R$ 165,94 | R$ 190,90 | +15,04% |
| IPCA+ 2029 | R$ 511,19 | R$ 564,02 | +10,33% |
| Pré 2032 | R$ 698,46 | R$ 724,18 | +3,68% |
| IPCA+ 2040 | R$ 762,38 | R$ 773,02 | +1,40% |
| IPCA+ 2050 | R$ 760,47 | R$ 771,89 | +1,50% |

### Cripto (consolidado em BRL)

| Ativo | Aplicado (USD) | Atual (USD) | Retorno |
|---|---|---|---|
| BTC (0,003816) | $321 | $282 | -12,13% |
| ETH (0,0588) | $183 | $120 | -34,69% |
| SOL (0,879) | $165 | $73 | **-56,01%** 🔴 |
| PENDLE (9,97) | $14 | $7 | **-52,61%** 🔴 |
| HYPE (0,301) | $5 | $21 | **+337,13%** ✅ |
| DeFi (posição) | $91 | $93 | +2,42% |
| USDT | $959 | $964 | +0,46% |
| **Total cripto** | **$974,71** | **$791,44** | **-18,80%** |

**Wallets ativas:**
- TrustWallet, Phantom, Rabby, Binance, KuCoin, Liquid (L-BTC via GenesisP2P)
- ETH/ARB/HYPE: `${WALLET_EVM_ADDRESS}`
- SOL: `${WALLET_SOL_ADDRESS}`
- Liquid: `${WALLET_LIQUID_ADDRESS}`

**Vencimentos DeFi a monitorar:**
- xSOL (Phantom/Hylo): 29/09/2026
- hyUSD (Phantom/Hylo): 29/09/2026

---

## 5. Gaps da planilha atual que o Goodies resolve

| Gap | Impacto | Solução no Goodies |
|---|---|---|
| Retorno sem XIRR | Decisão baseada em número errado | XIRR por ativo e consolidado |
| Sem benchmark | Não sabe se está ganhando ou perdendo do mercado | CDI, IPCA, IBOV no mesmo período |
| Cripto multi-wallet manual | Dados desatualizados frequentemente | Wallet scanner + Binance API |
| Caixa e portfólio separados | Taxa de poupança não é calculada | Ledger + Portfolio integrados |
| Sem rastreamento de metas | Não sabe quando vai chegar na LF | Goal tracker com projeção de prazo |
| Sem alertas | Rebalanceamento e IR são descobertos tarde | Sistema de alertas ativos |
| Dividendos não rastreados | Retorno total dos FIIs está subestimado | Registro de rendimentos separado |
| Sem IR estimado | Passivo tributário invisível | Estimador de IR por categoria |
| Tesouro com API frágil | Nome dos títulos na API muda sem aviso | Matching flexível + fallback manual |
| DeFi totalmente manual | Valor depende de atualização manual | Parcial: alertas de vencimento + entrada manual facilitada |

---

## 6. Riscos financeiros identificados (para o sistema monitorar)

### Risco #1 — Concentração Flash (CRÍTICO)
- Flash é 70,9% da renda mensal
- Flash Debênture é 43% da categoria Renda Fixa (R$ 13.207 de R$ ~13.466)
- **Se Flash tiver problema:** renda cai + maior ativo de RF perde valor simultaneamente
- **Alerta necessário:** quando Flash_debênture > 35% da Renda Fixa E receita Flash > 60% do total

### Risco #2 — Cripto acima do alvo
- 13,7% atual vs. 5% meta → 174% acima do target
- Retorno no período: -18,80%
- **Alerta necessário:** quando categoria CRIPTO desviar > 5pp do alvo

### Risco #3 — Retorno real negativo
- -1,31% real em 22 meses
- Portfólio perdendo para inflação
- **Métrica necessária:** retorno real vs. CDI vs. IPCA visível no dashboard

### Risco #4 — Reserva de emergência subfinanciada
- Meta: R$ 50.872 (12 meses de custos fixos)
- Snow Trip account (R$ 12.107) não é reserva — é objetivo de viagem
- A reserva real foi usada integralmente em julho/2025 para cirurgia (R$ 6.732)
- **Alerta necessário:** quando saldo de reserva < 3 meses de custos fixos

### Risco #5 — IR cripto
- Isenção: R$ 35.000/mês em vendas por tipo de ativo
- Operações de março e julho/2025 precisam ser revisadas
- **Alerta necessário:** quando vendas mensais de cripto acumularem > R$ 28.000 (80% do limite)

### Risco #6 — Vencimentos DeFi
- xSOL e hyUSD vencem 29/09/2026 → ~4 meses a partir da criação deste documento
- **Alerta necessário:** 30 e 7 dias antes do vencimento

---

## 7. Contratos financeiros por domínio

O que cada engine do Goodies DEVE calcular:

### Ledger Engine
- Receita total por categoria no período
- Despesa total por categoria no período
- Taxa de poupança = `(receita - despesa) / receita × 100`
- Projeção de caixa = saldo atual + receitas fixas previstas − despesas fixas previstas
- Alerta: conta fixa vencendo nos próximos 5 dias
- Alerta: categoria de gasto > 120% da média histórica dos últimos 3 meses

### Portfolio Engine
- Preço médio = `Σ(quantidade_i × preço_i) / Σ(quantidade_i)` (DCA correto)
- XIRR = taxa interna de retorno considerando data e valor de cada compra/venda
- % atual por categoria = `valor_atual_categoria / valor_total_carteira × 100`
- Desvio = `% atual − % meta`
- Peso de rebalanceamento = proporcional ao desvio (quanto mais longe da meta, maior o aporte sugerido)
- Estimativa de IR = `(valor_atual − custo_total) × 0.15` para ativos com ganho em RV
- Rendimentos de FII = registros separados de provento por cota × número de cotas

### Market Engine
- Preço de ativo B3 = BRAPI.dev (remover sufixo F para ações fracionárias)
- Preço de cripto em BRL = CoinGecko (ids mapeados no posicao.json)
- Preço do Tesouro Direto = API pública TD com matching flexível por nome
- Posição Binance = Binance API (spot + earn wallets)
- Posição DeFi on-chain = Etherscan (ETH/ARB), Solscan (SOL), Blockstream (Liquid), Hyperliquid explorer (HYPE)
- Cache de preços: Redis com TTL de 4h (B3) e 2h (cripto)

### Analytics Engine
- XIRR consolidado = XIRR calculado sobre todas as operações da tabela OPERAÇÕES
- Benchmark CDI = taxa Selic Over diária acumulada no período (BCB API série 11/CDI)
- Benchmark IPCA = IPCA acumulado no período (BCB API série 433)
- Benchmark IBOV = retorno do índice no período (via Yahoo Finance / yfinance)
- Retorno real = `(1 + retorno_nominal) / (1 + inflacao_periodo) − 1`
- Projeção de patrimônio = `VF = VP × (1+r)^n + PMT × ((1+r)^n − 1)/r` (anuidade de aportes crescentes)
- Anos para LF = resolver n em `meta_LF = patrimonio_atual × (1+r)^n + aporte_medio × ((1+r)^n − 1)/r`

---

## 8. Estrutura de dados atual (planilha) → modelo de dados futuro (Goodies)

| Aba da planilha | Domínio Goodies | Tabelas principais |
|---|---|---|
| FLUXO DE CAIXA | Ledger | `accounts`, `categories`, `transactions` |
| FINANCEIRO (resumo mensal) | Ledger | `monthly_summary` (view derivada) |
| OPERAÇÕES | Portfolio | `asset_operations` |
| CARTEIRA | Portfolio | `positions` (view derivada de operations) |
| FINANCEIRO (aportes/metas) | Portfolio + Analytics | `portfolio_targets`, `goals` |
| CRYPTO | Market + Portfolio | `wallet_positions`, `asset_prices` |
| ANÁLISE | Analytics | (cálculos, não persistência) |
| FINANCEIRO (custos fixos) | Ledger | `fixed_costs` (tipo de category) |

**Volume de dados atual (referência para sizing):**
- OPERAÇÕES: ~400 linhas (22 meses)
- FLUXO DE CAIXA: ~500 linhas por ano
- Crescimento esperado: ~20 transações de investimento + ~80 de caixa por mês

Supabase free tier (500MB storage, 50k req/mês) é mais que suficiente para o MVP com um único usuário.

---

*→ [[00_Brief]]*
*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
