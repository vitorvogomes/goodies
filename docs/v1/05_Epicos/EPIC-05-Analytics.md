---
tipo: epico
projeto: Goodies
epico: EPIC-05
milestone: m5-analytics
titulo: Analytics Engine — Benchmarks, Metas e Alertas
status: pendente
tags: [goodies, epic, analytics, xirr, benchmarks, metas, alertas]
---

# EPIC-05 — Analytics Engine

**Milestone:** m5-analytics  
**Objetivo:** Dashboard analítico completo: XIRR vs benchmarks, retorno real, projeções de patrimônio, rastreamento de metas e sistema de alertas ativos.  
**Gate de saída:** CDI, IPCA e IBOV no mesmo período de investimento visíveis. Projeção de prazo para LF calculada. Alertas de rebalanceamento e concentração Flash ativos.

---

## Escopo

### Inclui:
- Schema: `benchmark_data`, `goals`, `active_alerts`
- Importação histórica de dados BCB (CDI/IPCA jul/2024 → hoje) e yfinance (IBOV)
- Cálculo de benchmarks no período de investimento (acumulado desde jul/2024)
- Retorno real = `(1 + nominal) / (1 + inflação) − 1`
- Drawdown máximo histórico do portfólio
- Projeção em 3 cenários (6%, 10%, 14% a.a.) via fórmula de anuidade
- Rastreamento de metas: Reserva (R$ 50.872) e LF (R$ 1.271.802) com progresso % e prazo estimado
- Sistema de alertas (`active_alerts`):
  - Rebalanceamento: desvio ≥ 2pp do alvo
  - Concentração Flash: Flash_debênture > 35% RF E receita Flash > 60% total
  - IR cripto: vendas mensais > R$ 28.000/mês
  - Vencimentos DeFi: 30 dias e 7 dias antes
  - Conta fixa vencendo nos próximos 5 dias
  - Categoria de gasto acima de 120% da média
- Endpoints: `GET /analytics/summary`, `/benchmarks`, `/projection`, `/goals`, `/alerts`
- Endpoint Hermes: `GET /hermes/alertas`, `GET /hermes/resumo-geral` (snapshot completo)
- Frontend: página de analytics com XIRR + benchmarks (gráfico de linha), projeções (3 cenários), metas (progress bars), alertas ativos (card no dashboard)

### Não inclui:
- Recomendações de compra/venda
- Análise fundamentalista
- IR anual completo (GCAP)

---

## Stories

- STORY-05-01: Schema benchmark_data + goals + active_alerts
- STORY-05-02: Importação histórica BCB (CDI/IPCA jul/2024 → hoje)
- STORY-05-03: Importação histórica IBOV (yfinance jul/2024 → hoje)
- STORY-05-04: Cálculo de benchmarks acumulados no período de investimento
- STORY-05-05: Cálculo de retorno real (nominal − inflação)
- STORY-05-06: Cálculo de drawdown máximo histórico
- STORY-05-07: Projeção de patrimônio em 3 cenários (fórmula de anuidade)
- STORY-05-08: Seed de metas (Reserva R$50.872, LF R$1.271.802) com fórmulas
- STORY-05-09: Cálculo de prazo estimado para cada meta (resolve n na fórmula de LF)
- STORY-05-10: Engine de alertas — avaliação e persistência em active_alerts
- STORY-05-11: Alerta de rebalanceamento (≥ 2pp desvio)
- STORY-05-12: Alerta de concentração Flash (dupla condição)
- STORY-05-13: Worker alert_eval (cron diário 8h)
- STORY-05-14: Endpoints de analytics (summary, benchmarks, projection, goals)
- STORY-05-15: Endpoints Hermes (resumo-geral, alertas)
- STORY-05-16: Endpoint GET /alertas + PUT /alertas/{id}/read
- STORY-05-17: Frontend — página analytics: XIRR vs CDI/IPCA/IBOV (gráfico linha)
- STORY-05-18: Frontend — projeções 3 cenários (gráfico área)
- STORY-05-19: Frontend — metas com progress bar e prazo estimado
- STORY-05-20: Frontend — card de alertas ativos no dashboard

---

## Dependências
EPIC-01 (dados de caixa), EPIC-02 (XIRR e operações), EPIC-03 (preços), EPIC-04 (posições cripto e dados de benchmark).

## Bloqueados por este épico
EPIC-07 (Frontend final usa dados de analytics para o dashboard principal)
