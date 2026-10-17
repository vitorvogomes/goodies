---
tipo: story
epico: EPIC-05
story: STORY-05-10
titulo: Engine de alertas — avaliação e persistência
status: pendente
estimativa: L (4-6h)
tags: [goodies, story, analytics, alertas]
skills: [test-driven-development, api-design-principles, systematic-debugging]
---

# STORY-05-10 — Engine de Alertas

**Como** Vitor  
**Quero** receber alertas proativos sobre riscos financeiros  
**Para** não descobrir problemas reativamente (rebalanceamento atrasado, risco de IR, vencimentos)

---

## Critérios de aceite

- [ ] Schema `active_alerts` criado (ver Arquitetura seção 3.2)
- [ ] Worker `alert_eval` (APScheduler, cron diário 8h) que avalia todas as condições e persiste alertas
- [ ] **6 tipos de alerta implementados:**

  **REBALANCING** (severity: warning)
  - Condição: qualquer categoria com desvio > 2pp do alvo
  - Mensagem: "CRIPTO está 8,7pp acima do alvo (13,7% atual vs. 5,0% meta)"

  **CONCENTRATION** (severity: critical)
  - Condição: Flash_debênture > 35% da Renda Fixa E receita Flash > 60% do total
  - Mensagem: "Concentração Flash: maior empregador e maior ativo de RF são o mesmo player"

  **IR_CRYPTO** (severity: warning)
  - Condição: vendas de cripto no mês > R$ 28.000 (80% do limite de R$ 35.000)
  - Mensagem: "Vendas de cripto em [mês]: R$ XX.XXX — você está a R$ YYY do limite de isenção"

  **DEFI_EXPIRY** (severity: warning → critical 7 dias antes)
  - Condição: posição DeFi com vencimento em < 30 dias
  - Mensagem: "xSOL vence em 29/09/2026 — [N] dias restantes"

  **FIXED_COST** (severity: info)
  - Condição: custo fixo vence nos próximos 5 dias
  - Mensagem: "Aluguel vence em [data] — R$ [valor]"

  **OVERSPENDING** (severity: warning)
  - Condição: categoria de gasto > 120% da média histórica dos últimos 3 meses
  - Mensagem: "Lazer: R$ 800 este mês vs. média histórica de R$ 500 (160%)"

- [ ] `GET /api/v1/alerts` retorna alertas ativos não dispensados
- [ ] `PUT /api/v1/alerts/{id}/read` marca como lido
- [ ] `DELETE /api/v1/alerts/{id}` dispensa alerta (não reativa até próxima avaliação)
- [ ] Idempotência: avaliar 2× não duplica alertas — upsert por tipo + contexto
- [ ] Alerta de concentração Flash deve estar ATIVO na primeira execução (condição já é verdadeira)

## Notas de implementação
- Idempotência: usar combinação `(type, context_hash)` como chave única — context_hash é hash MD5 dos campos que identificam o alerta específico
- O alerta de concentração Flash é **imediato** — na primeira vez que o worker rodar, já deve aparecer

## Dependências
STORY-05-01 (schema), STORY-02-08 (alocação), STORY-01-04 (dados de receita por categoria), STORY-04-08 (posições DeFi com vencimento).
