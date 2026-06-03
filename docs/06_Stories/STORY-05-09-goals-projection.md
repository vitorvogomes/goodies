---
tipo: story
epico: EPIC-05
story: STORY-05-09
titulo: Cálculo de prazo para metas (Reserva e LF)
status: pendente
estimativa: M (2-3h)
tags: [goodies, story, analytics, metas, projecao]
skills: [test-driven-development, systematic-debugging]  # scipy (anuidade): sem skill → conventions.md
---

# STORY-05-09 — Prazo para Metas

**Como** Vitor  
**Quero** saber quantos anos faltam para atingir minha Reserva de Emergência e Liberdade Financeira  
**Para** tomar decisões de aporte sabendo o impacto no prazo da minha independência financeira

---

## Critérios de aceite

- [ ] `GET /api/v1/analytics/goals` retorna para cada meta:
  ```json
  [
    {
      "id": "...",
      "name": "Reserva de Emergência",
      "target_brl": 50872.00,
      "current_brl": 28303.02,
      "progress_pct": 55.6,
      "months_to_goal_conservative": 26,
      "months_to_goal_base": 18,
      "months_to_goal_aggressive": 14,
      "monthly_contribution": 1247.39
    },
    {
      "id": "...",
      "name": "Liberdade Financeira",
      "target_brl": 1271802.00,
      "current_brl": 28303.02,
      "progress_pct": 2.22,
      ...
    }
  ]
  ```
- [ ] Fórmula: `n = solve(VF = VP × (1+r)^n + PMT × ((1+r)^n − 1)/r)`
  - VP = patrimônio atual
  - PMT = aporte médio mensal (média dos últimos 3 meses ou configurável)
  - VF = meta
  - r = taxa mensal (conservador: 0,487%/mês ≈ 6% a.a.; base: 0,797%; agressivo: 1,10%)
- [ ] Prazo calculado corretamente para os valores reais (Vitor pode validar manualmente)
- [ ] Atualizado a cada novo aporte registrado (invalidar cache)
- [ ] Seed de metas com os valores reais do Vitor (R$ 50.872 e R$ 1.271.802)

## Notas de implementação
Usar `scipy.optimize.brentq` ou `numpy` para resolver numericamente — não existe fórmula fechada simples para n nesse contexto. PMT fixo simplifica para a fórmula acima.

## Dependências
STORY-05-08 (seed de metas), STORY-05-07 (projeções).
