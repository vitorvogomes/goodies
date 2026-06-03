---
tipo: epico
projeto: Goodies
epico: EPIC-01
milestone: m1-ledger
titulo: Ledger Engine — Controle de Caixa
status: pendente
tags: [goodies, epic, ledger, caixa, financeiro]
---

# EPIC-01 — Ledger Engine

**Milestone:** m1-ledger  
**Objetivo:** Controle completo de receitas, despesas e caixa — substituindo a aba "FLUXO DE CAIXA" e "FINANCEIRO (resumo)" da planilha.  
**Gate de saída:** Taxa de poupança calculada automaticamente bate com o valor da planilha para junho/2026 (tolerância < 0,1%).

---

## Escopo

### Inclui:
- CRUD de transações (receitas e despesas) com data, valor, categoria, conta, descrição
- CRUD de contas (`accounts`)
- Categorias configuráveis (seed inicial com categorias da planilha do Vitor)
- Custos fixos com dia de vencimento (`fixed_costs`)
- Cálculo automático de: saldo running, receita total, despesa total, taxa de poupança
- View `monthly_summary` e endpoint de resumo mensal
- Projeção de caixa para 30/60/90 dias (receitas fixas previstas − despesas fixas previstas)
- Alerta: conta fixa vencendo nos próximos 5 dias
- Alerta: categoria ultrapassou 120% da média histórica dos últimos 3 meses
- Endpoints Hermes: `POST /hermes/expenses`, `POST /hermes/income`
- Frontend: lista de transações, formulário de nova transação, dashboard de caixa (resumo mensal + taxa de poupança)
- **Migração manual:** script de importação CSV da aba FLUXO DE CAIXA (24 meses de histórico)

### Não inclui:
- Preços de mercado (Ledger usa valores brutos informados pelo usuário)
- Integração com extratos bancários (OpenFinance — futuro)

---

## Stories

- STORY-01-01: Schema de banco (accounts, transactions, fixed_costs, monthly_summary view)
- STORY-01-02: CRUD de contas e categorias
- STORY-01-03: CRUD de transações com validação
- STORY-01-04: Cálculo de saldo running e resumo mensal
- STORY-01-05: Cálculo de taxa de poupança
- STORY-01-06: Projeção de caixa 30/60/90 dias
- STORY-01-07: CRUD de custos fixos
- STORY-01-08: Alertas de vencimento e categoria acima de 120%
- STORY-01-09: Endpoints Hermes (POST /expenses, POST /income)
- STORY-01-10: Frontend — lista de transações + filtros
- STORY-01-11: Frontend — formulário de nova transação
- STORY-01-12: Frontend — dashboard de caixa (resumo mensal, taxa de poupança, projeção)
- STORY-01-13: Script de migração CSV (FLUXO DE CAIXA planilha → Postgres)
- STORY-01-14: Validação de migração (saldo final bate com planilha)

---

## Dependências
EPIC-00 concluído.

## Bloqueados por este épico
EPIC-05 (Analytics precisa de dados de caixa para taxa de poupança)
