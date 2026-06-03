---
tipo: epico
projeto: Goodies
epico: EPIC-02
milestone: m2-portfolio
titulo: Portfolio Engine — Posições e XIRR
status: pendente
tags: [goodies, epic, portfolio, xirr, investimentos]
---

# EPIC-02 — Portfolio Engine

**Milestone:** m2-portfolio  
**Objetivo:** Registro completo de operações de investimento, cálculo de XIRR, posições atuais, motor de rebalanceamento. Substitui as abas "OPERAÇÕES" e "CARTEIRA" da planilha.  
**Gate de saída:** XIRR calculado pelo Goodies coincide com Excel nos dados históricos (tolerância < 0,1 pp).

---

## Escopo

### Inclui:
- Schema: `asset_operations`, `portfolio_targets`, view `positions`
- CRUD de operações de compra/venda/rendimento com validação
- Cálculo de preço médio ponderado (DCA correto)
- **Cálculo XIRR** por ativo e consolidado (`engines/portfolio/xirr.py`)
- Posição atual por ativo: quantidade, preço médio, valor atual (sem preço de mercado ainda — usa último preço manual em m2)
- Alocação atual vs. meta por categoria (tabela `portfolio_targets` com seed dos alvos do Vitor)
- Desvio em pontos percentuais por categoria
- Motor de rebalanceamento: dado aporte, distribui proporcionalmente aos desvios negativos
- Rastreamento de rendimentos (FII, JCP) como tipo separado — não mistura com ganho de capital
- Estimativa de IR: `(valor_atual − custo_total) × 0.15` por categoria de RV
- IR cripto: consolidação mensal por tipo, alerta quando > R$ 28.000/mês (80% do limite)
- Endpoint `GET /portfolio/xirr` (e endpoint Hermes)
- Frontend: tabela de posições, histórico de operações, visualização de alocação (pizza chart), tela de rebalanceamento
- **Migração manual:** importação CSV da aba OPERAÇÕES (400+ registros históricos)

### Não inclui:
- Preços automáticos de mercado (vêm no EPIC-03) — m2 usa preço manual/última cotação
- Integração com corretoras (EPIC-04)

---

## Stories

- STORY-02-01: Schema de banco (asset_operations, portfolio_targets, positions view)
- STORY-02-02: Seed de portfolio_targets (alvos do Vitor: cripto 5%, RF 50%, etc.)
- STORY-02-03: CRUD de operações com validação de tipos
- STORY-02-04: Cálculo de preço médio ponderado (DCA)
- STORY-02-05: Implementação e testes de XIRR (xirr.py + pytest comparação com Excel)
- STORY-02-06: Endpoint XIRR por ativo e consolidado
- STORY-02-07: Posição atual por ativo (valor com preço manual)
- STORY-02-08: Cálculo de alocação atual vs. meta + desvio
- STORY-02-09: Motor de rebalanceamento (dado aporte, sugere distribuição)
- STORY-02-10: Rastreamento de rendimentos separado (FII, JCP)
- STORY-02-11: Estimativa de IR por categoria
- STORY-02-12: IR cripto: consolidação mensal + alerta 80% do limite
- STORY-02-13: Frontend — tabela de posições com valor atual
- STORY-02-14: Frontend — histórico de operações paginado
- STORY-02-15: Frontend — alocação atual vs. meta (pizza chart + desvio)
- STORY-02-16: Frontend — tela de rebalanceamento (input de aporte → sugestão)
- STORY-02-17: Script de migração CSV (OPERAÇÕES planilha → asset_operations)
- STORY-02-18: Validação de migração (XIRR Python == Excel XIRR nos dados históricos)

---

## Dependências
EPIC-00 concluído. EPIC-01 não é bloqueante (schemas independentes), mas XIRR precisa do histórico de operações importado.

## Bloqueados por este épico
EPIC-03 (Market usa tickers do portfolio), EPIC-05 (Analytics depende de XIRR e operações)
