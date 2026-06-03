---
tipo: story
epico: EPIC-02
story: STORY-02-09
titulo: Motor de rebalanceamento
status: pendente
estimativa: M (2-3h)
tags: [goodies, story, portfolio, rebalanceamento]
---

# STORY-02-09 — Motor de Rebalanceamento

**Como** Vitor  
**Quero** informar o valor que quero aportar e receber a sugestão de quanto vai para cada categoria  
**Para** corrigir os desvios da alocação alvo sem precisar calcular manualmente

---

## Critérios de aceite

- [ ] `GET /api/v1/portfolio/rebalancing?amount=4500` retorna:
  ```json
  {
    "contribution": 4500.00,
    "suggestions": {
      "rf": 1850.00,
      "fii": 980.00,
      "etf": 870.00,
      "acoes": 500.00,
      "aposentadoria": 300.00,
      "cripto": 0.00
    },
    "current_allocation": { ... },
    "target_allocation": { ... },
    "deviations_pp": {
      "cripto": "+8.7pp — acima do alvo, sem aporte sugerido",
      "rf": "-2.4pp",
      ...
    }
  }
  ```
- [ ] Regra: **nunca sugere venda** — só aporta em categorias abaixo do alvo
- [ ] Cripto acima do alvo em +8,7pp → aporte em cripto = R$ 0 (correto)
- [ ] Distribuição proporcional ao gap negativo de cada categoria
- [ ] Se todas as categorias estão no alvo ou acima, retornar `suggestions: {}` com mensagem
- [ ] Testes com o portfólio atual do Vitor (dados da planilha): verificar sugestão de rebalanceamento

## Notas de implementação
Implementação em `engines/portfolio/service.py → suggest_rebalancing()`. Ver pseudocódigo na Arquitetura seção 7.

Alocação atual requer preços de mercado (do Market Engine). Em m2, usar último preço manual disponível — em m3+, usar preços automáticos.

## Dependências
STORY-02-08 (cálculo de alocação atual vs. meta).
