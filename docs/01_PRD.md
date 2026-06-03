---
tipo: prd
projeto: Goodies
versao: "1.0"
autor: BMAD/John (PM) via Minerva
data: 2026-06-02
status: aprovado
tags: [goodies, prd, requisitos, planejamento]
---

# Goodies — Product Requirements Document

> Produzido por John (PM/BMAD) com base no brief da Hatchepsut (`00_Brief.md`) e no raio-X financeiro (`08_Contexto_Financeiro.md`).
> Input primário para Winston (Arquiteto) e para `bmad-create-epics-and-stories`.

---

## 1. Problema

Vitor gerencia ~R$ 28.300 de portfólio e ~R$ 10.000/mês de renda em uma planilha Google Sheets mantida manualmente desde julho/2024. A planilha tem **5 falhas estruturais** que distorcem decisões reais de investimento:

1. **Retorno errado:** usa `(resultado−aplicado)/aplicado` — metodologicamente inválido para DCA. O número correto é XIRR.
2. **Sem benchmark:** nenhuma referência a CDI, IPCA ou IBOV no mesmo período. Impossível saber se a carteira bate o mercado.
3. **Dados manuais e defasados:** preços de ativos B3, posições cripto em 6 wallets e saldo de RF privada são atualizados na mão.
4. **Caixa e portfólio desconexos:** taxa de poupança e capacidade de aporte não são calculadas automaticamente.
5. **Sem alertas:** rebalanceamento necessário, vencimentos DeFi, risco de IR cripto e concentração de risco só são descobertos reativamente.

**Impacto:** Vitor toma decisões de aporte com dado defasado e retorno calculado errado. Isso é material — R$ 860 de resultado nominal pode ser muito diferente em XIRR dado o timing dos aportes.

---

## 2. Usuário

**Usuário único:** Vitor — engenheiro mecatrônico, investidor individual com 22 meses de histórico ativo.

**Perfil de uso:**
- Frequência: consulta semanal para decisões de aporte, registro pós-operação
- Nível: College→Enterprise em análise de investimentos — conhece DCA, rebalanceamento, ciclos de cripto, instrumentos de RF/RV
- Expectativa: sistema que respeita o nível dele — sem simplificações desnecessárias
- Fluxo atual: planilha manual → atualização por operação → consulta quando precisa decidir

**Não há planos de múltiplos usuários no MVP.**

---

## 3. Objetivos do produto

| Objetivo | Métrica de sucesso | Baseline atual |
|---|---|---|
| Mostrar retorno correto | XIRR visível e atualizado diariamente | "3,14%" calculado errado |
| Habilitar comparação de mercado | CDI/IPCA/IBOV no mesmo período na tela | Zero benchmark hoje |
| Automatizar taxa de poupança | Calculada sem entrada manual | Manual hoje |
| Alertar rebalanceamento | Disparo quando desvio ≥ 2pp do alvo | Não existe |
| Rastrear metas | Prazo para LF recalculado a cada aporte | Metas existem, sem tracking |
| Reconciliar cripto multi-wallet | Posições sem intervenção manual | 6 wallets manuais |

**Critério de done do produto:** quando Vitor puder tomar uma decisão de aporte sem abrir a planilha.

---

## 4. Personas e jornadas

### Persona única: Vitor investidor

**Job to be done principal:** "Quero saber, em 30 segundos, se devo aportar agora, quanto e em quê — com dados corretos."

**Jornadas críticas:**

| Jornada | Frequência | Estado atual | Estado desejado |
|---|---|---|---|
| Revisar performance | Semanal | Abre planilha, calcula manualmente | Dashboard com XIRR + benchmark |
| Decidir aporte mensal | Mensal | Olha desvio na planilha, calcula peso | Motor de rebalanceamento automatizado |
| Registrar operação | Por transação | Digita na planilha | POST via UI ou Hermes |
| Monitorar cripto | Ad hoc | Soma wallets manualmente | Wallet scan automático |
| Verificar vencimentos | Ad hoc | Não existe | Alerta proativo |

---

## 5. Requisitos funcionais

### 5.1 Ledger Engine (domínio 1 — caixa)

**RF-L01** — Registro de transações com: data, valor, categoria, conta, descrição, tipo (receita/despesa).

**RF-L02** — Categorias de transação configuráveis (ex: moradia, alimentação, Flash Capital, Betuel, saúde).

**RF-L03** — Cálculo automático de:
- Saldo running por conta
- Receita total do período
- Despesa total do período
- Taxa de poupança = `(receita − despesa) / receita × 100`

**RF-L04** — Projeção de caixa para 30/60/90 dias com base em receitas e despesas fixas cadastradas.

**RF-L05** — Custos fixos com data de vencimento mensal.

**RF-L06 (alerta)** — Notificação quando conta fixa vence nos próximos 5 dias.

**RF-L07 (alerta)** — Notificação quando categoria de gasto ultrapassa 120% da média histórica dos últimos 3 meses.

**RF-L08** — Resumo mensal consolidado (view derivada) com comparação mês anterior.

**RF-L09** — Endpoint `POST /expenses` e `POST /income` para integração com Hermes.

### 5.2 Portfolio Engine (domínio 2 — investimentos)

**RF-P01** — Registro de operações de compra/venda com: data, ativo, quantidade, preço unitário, corretora, tipo (compra/venda/rendimento).

**RF-P02** — Cálculo de preço médio ponderado por ativo (DCA correto): `Σ(qtd_i × preço_i) / Σ(qtd_i)`.

**RF-P03** — **XIRR por ativo e consolidado** — requisito crítico. Usar biblioteca scipy/numpy para cálculo de XIRR sobre a tabela de operações com timestamps.

**RF-P04** — Posição atual por ativo: quantidade, preço médio, valor atual (via Market Engine), retorno absoluto e percentual.

**RF-P05** — Alocação por categoria: % atual vs. % meta, desvio em pontos percentuais.

**RF-P06** — Motor de rebalanceamento: dado um valor de aporte, distribui proporcionalmente aos desvios negativos para minimizar distância da alocação alvo.

**RF-P07** — Registro de rendimentos (dividendos, JCP, rendimentos de FII) como tipo separado — não misturado com ganho de capital.

**RF-P08** — Estimativa de IR: `(valor_atual − custo_médio_total) × 0.15` para ativos com ganho em RV.

**RF-P09** — IR cripto por mês: consolidação de vendas por tipo, alerta quando acumulado > R$ 28.000/mês (80% do limite de isenção de R$ 35.000).

**RF-P10** — Endpoint `GET /portfolio/xirr` para Hermes.

### 5.3 Market Engine (domínio 3 — preços)

**RF-M01** — Preços B3 via BRAPI.dev:
- Ações e ETFs (remoção de sufixo F para fracionárias)
- FIIs
- Atualização a cada 4h em dias úteis

**RF-M02** — Preços cripto via CoinGecko (free tier):
- BTC, ETH, SOL, PENDLE, HYPE, USDT e outros conforme `posicao.json`
- Cotação BRL/USD para conversão
- Atualização a cada 2h

**RF-M03** — Preços Tesouro Direto via API pública com matching flexível por nome (a API muda nomes de títulos sem aviso — implementar tolerância a variações).

**RF-M04** — Scan de wallets on-chain:
- ETH/ARB/HYPE: Etherscan API (`${WALLET_EVM_ADDRESS}`)
- SOL: Solscan API (`${WALLET_SOL_ADDRESS}`)
- Liquid (L-BTC): `blockstream.info/liquid` — API diferente do mainchain Bitcoin
- HYPE: Hyperliquid explorer

**RF-M05** — Integração Binance API: spot + earn wallets com cache + cron (não pull on-demand — respeitar rate limits).

**RF-M06** — Cache de preços em Redis com TTL:
- B3: 4h em dias úteis, sem atualização em fim de semana
- Cripto: 2h

**RF-M07** — Fallback manual para ativos sem API: Flash Debênture, CDB Guanabara, posições DeFi. Sistema não trava sem esses dados — exibe último valor manual com timestamp de atualização.

**RF-M08** — Endpoint `GET /resumo-geral` retornando snapshot completo (JSON) para Hermes.

### 5.4 Analytics Engine (domínio 4 — análise)

**RF-A01** — XIRR consolidado sobre todas as operações da tabela `asset_operations`.

**RF-A02** — Benchmarks no mesmo período de investimento:
- CDI: BCB API série 11 (CDI over diário acumulado)
- IPCA: BCB API série 433
- IBOV: retorno do índice via Yahoo Finance / yfinance

**RF-A03** — Retorno real = `(1 + retorno_nominal) / (1 + inflação_período) − 1`.

**RF-A04** — Drawdown máximo histórico do portfólio consolidado.

**RF-A05** — Projeção de patrimônio em 3 cenários:
- Conservador: 6% a.a.
- Base: 10% a.a.
- Agressivo: 14% a.a.
- Fórmula: `VF = VP × (1+r)^n + PMT × ((1+r)^n − 1) / r`

**RF-A06** — Anos estimados para atingir Reserva (R$ 50.872) e LF (R$ 1.271.802) ao ritmo atual.

**RF-A07 (alerta)** — Concentração Flash: quando `Flash_debênture > 35% da RF` E `receita Flash > 60% do total` → alerta de risco de concentração.

**RF-A08 (alerta)** — Rebalanceamento: quando qualquer categoria desviar > 2pp do alvo → alerta ativo.

**RF-A09 (alerta)** — Vencimento DeFi: alerta 30 dias e 7 dias antes de qualquer posição com data de vencimento.

**RF-A10** — Endpoint `GET /alertas` retornando lista de alertas ativos para Hermes.

---

## 6. Requisitos não funcionais

| Requisito | Critério | Justificativa |
|---|---|---|
| **Disponibilidade** | 99% uptime (exceto manutenção planejada) | Consulta antes de decisões de aporte |
| **Latência** | Dashboard carrega em < 3s com cache quente | Experiência fluida |
| **Segurança** | Auth JWT, sem dados sensíveis em logs, secrets em env | Dados financeiros pessoais |
| **Custo** | ≤ R$ 50/mês total | Ferramenta pessoal |
| **Manutenibilidade** | Cobertura de testes ≥ 80% nas engines críticas | Solo developer — sem time pra debugar |
| **Observabilidade** | Logs estruturados, alertas de erro no Discord via Hermes | Falha silenciosa é inaceitável em dados financeiros |
| **Resiliência a falhas de API** | Fallback para cache quando API externa falhar | Binance, CoinGecko, BRAPI podem ficar fora |
| **Escalabilidade** | Suportar 10× o volume atual sem mudança de arquitetura | ~400 operações hoje → ~4.000 em 5 anos |

---

## 7. Fora do escopo (MVP)

- Recomendações de compra/venda (o sistema informa, não recomenda)
- Análise fundamentalista de empresas
- Previdência privada (PGBL/VGBL)
- Múltiplos usuários / multi-tenant
- Aplicativo mobile (web-first)
- Importação automática de extratos bancários (OpenFinance — futuro)
- IR anual completo / GCAP (escopo específico do Receita Federal)
- Integração KuCoin (baixa prioridade vs. Binance)
- Hermes como interface de linguagem natural (fase futura)

---

## 8. Contratos de API expostos para Hermes

| Endpoint | Método | Descrição |
|---|---|---|
| `/resumo-geral` | GET | Snapshot completo da carteira (JSON) |
| `/alertas` | GET | Lista de alertas ativos |
| `/portfolio/xirr` | GET | XIRR atual consolidado e por categoria |
| `/expenses` | POST | Registrar despesa |
| `/income` | POST | Registrar receita |

Todos os endpoints Hermes requerem autenticação JWT. O Hermes usa um token dedicado de serviço, não o JWT do usuário.

---

## 9. Dependências externas e riscos

| Dependência | Risco | Mitigação |
|---|---|---|
| BRAPI.dev (B3) | Tier free tem limite; API pode mudar | Cache Redis 4h; fallback para último valor |
| CoinGecko (cripto) | Rate limit agressivo no free tier | Cache Redis 2h; retry exponential backoff |
| BCB API (CDI/IPCA) | Estável, mas sem SLA | Cache diário; dados históricos importados na inicialização |
| Binance API | Rate limits documentados | Cron schedule + cache; nunca pull on-demand |
| Etherscan/Solscan | Dependente de API key gratuita | Fallback para valor manual se falhar |
| blockstream.info/liquid | API específica do Liquid — diferente do mainchain | Implementar client dedicado, não reusar o de Bitcoin |
| Tesouro Direto API | Nomes de títulos mudam sem aviso | Matching flexível por substring + fallback manual |

---

## 10. Premissas

1. O usuário (Vitor) é o único administrador — sem onboarding para outros usuários.
2. `posicao.json` continua sendo a fonte de verdade das posições cripto até o Market Engine estar completo.
3. O script `coleta_carteira.py` do Hermes continua rodando de forma independente durante o desenvolvimento.
4. Histórico de 22 meses da planilha será migrado manualmente para o banco no m1 (ledger) e m2 (portfolio). Não há script automático de migração de planilha no MVP.
5. A interface web é responsiva mas não é mobile-first — tela mínima: 1024px.
6. Secrets (Binance API key, Etherscan key, etc.) ficam em variáveis de ambiente — nunca commitados.

---

## 11. Restrições técnicas

| Restrição | Detalhe |
|---|---|
| Stack | FastAPI + Next.js + Supabase + Redis (Upstash) + Fly.io + Vercel — não mudar sem ADR |
| Custo operacional | Máximo R$ 50/mês em produção |
| Auth | JWT simples — sem OAuth de terceiros além do que for necessário para APIs externas |
| IR cripto | Threshold de isenção: R$ 35.000/mês em vendas por **tipo** de ativo. Cálculo deve consolidar por mês, não por operação |
| Dados manuais | Flash Debênture, CDB Guanabara, DeFi: entrada manual obrigatória. Sistema não pode travar sem eles |
| Liquid Network | `blockstream.info/liquid` — API diferente do Bitcoin mainchain |

---

## 12. Riscos do produto

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| APIs externas mudam formato | Média | Alto | Adapters com testes de contrato |
| Dados de cripto desatualizados | Média | Médio | TTL conservador + timestamp visível na UI |
| Cálculo XIRR incorreto | Baixa | Crítico | Testes unitários contra valores calculados no Excel |
| Migração do histórico com erro | Média | Alto | Migração manual com validação por amostra |
| Rate limit Binance | Baixa | Alto | Cache agressivo; nunca pull síncrono |

---

## 13. Métricas de sucesso (revisão em 3 meses)

1. XIRR visível no dashboard — atualizado diariamente
2. Benchmark CDI/IPCA/IBOV disponível no mesmo período
3. Taxa de poupança calculada automaticamente (zero entrada manual para este campo)
4. Alertas de rebalanceamento disparando com < 1h de delay
5. Posições cripto multi-wallet reconciliadas automaticamente (sem abrir as wallets manualmente)
6. Projeção de prazo para LF disponível e atualizada após cada aporte

---

*→ [[00_Brief]]*
*→ [[08_Contexto_Financeiro]]*
*→ [[02_Arquitetura]]*
*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
