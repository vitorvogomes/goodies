---
tipo: story
epico: EPIC-02
story: STORY-02-05
titulo: Implementação e testes de XIRR
status: pendente
estimativa: L (4-6h) — crítico, não apressar
tags: [goodies, story, portfolio, xirr, calculo]
skills: [test-driven-development, systematic-debugging]  # scipy/XIRR: sem skill → CLAUDE.md/decisions.md (gate crítico)
---

# STORY-02-05 — XIRR (Extended Internal Rate of Return)

**Como** Vitor  
**Quero** ver o retorno XIRR real do meu portfólio  
**Para** tomar decisões de aporte com o número correto — não com "3,14%" metodologicamente errado

---

## Critérios de aceite

- [ ] `api/engines/portfolio/xirr.py` com função `xirr(cashflows: list[tuple[date, float]]) -> float`
- [ ] Regra de sinais:
  - Compra → cashflow **negativo** (saída de caixa do Vitor)
  - Venda → cashflow **positivo** (entrada)
  - Rendimento → cashflow **positivo**
  - Posição atual → cashflow **positivo** com data de hoje (valor de mercado)
- [ ] Implementação via `scipy.optimize.brentq` na função NPV (ver Arquitetura seção 7)
- [ ] Retorna taxa anualizada como decimal (ex: `0.0853` para 8,53% a.a.)
- [ ] `GET /api/v1/portfolio/xirr` retorna:
  ```json
  {
    "consolidated": 0.0853,
    "by_category": {
      "acoes": 0.12,
      "fii": 0.08,
      "etf": 0.18,
      "rf": 0.11,
      "cripto": -0.22,
      "aposentadoria": 0.10
    },
    "calculated_at": "2026-06-02T15:30:00Z"
  }
  ```
- [ ] **Teste de validação obrigatório:** rodar XIRR Python nos dados reais da planilha exportados como CSV → comparar com Excel XIRR → diferença < 0,1 pp. **Gate de saída da STORY.**
- [ ] Testes unitários com casos conhecidos:
  - Investimento simples: -1000 em jan, +1100 em jan do ano seguinte → ~10% a.a.
  - DCA: 3 aportes iguais + posição final → calcular manualmente e comparar
- [ ] XIRR cacheado no Redis com TTL 1h, invalidado ao inserir nova operação

## Notas de implementação

```python
# engines/portfolio/xirr.py
from scipy.optimize import brentq
from datetime import date
from typing import List, Tuple

def xirr(cashflows: List[Tuple[date, float]]) -> float:
    """
    Calcula XIRR via Newton-Raphson (brentq).
    cashflows: lista de (data, valor) — compras negativas, vendas/posição atual positivas
    Retorna: taxa anualizada (ex: 0.1253 para 12,53% a.a.)
    """
    if len(cashflows) < 2:
        raise ValueError("Precisa de pelo menos 2 cashflows para calcular XIRR")
    
    dates, amounts = zip(*sorted(cashflows, key=lambda x: x[0]))
    days = [(d - dates[0]).days for d in dates]
    
    def npv(rate: float) -> float:
        return sum(amt / (1 + rate) ** (d / 365.0) for amt, d in zip(amounts, days))
    
    try:
        return brentq(npv, -0.999, 100.0, xtol=1e-8, maxiter=1000)
    except ValueError:
        # Se não convergir (ex: todos os cashflows positivos), retornar NaN
        return float('nan')
```

**Atenção:** Edge cases a testar:
- Portfólio com retorno negativo (cripto atualmente -18,8%)
- Ativo com apenas uma compra e posição atual (sem vendas)
- Renda fixa (entrada por valor total, não quantidade)

## Dependências
STORY-02-03 (operações no banco), STORY-02-07 (posição atual = último cashflow).
