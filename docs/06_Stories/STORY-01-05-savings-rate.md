---
tipo: story
epico: EPIC-01
story: STORY-01-05
titulo: Cálculo de taxa de poupança
status: pendente
estimativa: S (1-2h)
tags: [goodies, story, ledger, taxa-poupanca]
skills: [test-driven-development, api-design-principles, systematic-debugging]
---

# STORY-01-05 — Taxa de Poupança

**Como** Vitor  
**Quero** ver minha taxa de poupança calculada automaticamente por mês  
**Para** saber, sem abrir planilha, quanto do que ganho estou guardando

---

## Critérios de aceite

- [ ] `GET /api/v1/cashflow/summary` retorna por mês:
  ```json
  {
    "month": "2026-06",
    "total_income": 10042.08,
    "total_expense": 4470.98,
    "net_cashflow": 5571.10,
    "savings_rate": 55.48
  }
  ```
- [ ] Fórmula: `savings_rate = (receita − despesa) / receita × 100`
- [ ] Retorna erro descritivo se receita do período for zero (evita divisão por zero)
- [ ] Valor de junho/2026 bate com a planilha (tolerância < 0,1%)
- [ ] Testes unitários com dados conhecidos (receita=10000, despesa=4500 → taxa=55%)

## Notas de implementação
Usar view `monthly_summary` (criada em STORY-01-04). A taxa de poupança já está na view — apenas expor via endpoint.

## Dependências
STORY-01-04 (view monthly_summary).
