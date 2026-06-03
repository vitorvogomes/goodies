---
tipo: epico
projeto: Goodies
epico: EPIC-07
milestone: m7-frontend
titulo: Frontend — Dashboard Completo e UI Final
status: pendente
tags: [goodies, epic, frontend, dashboard, ux]
---

# EPIC-07 — Frontend Real

**Milestone:** m7-frontend  
**Objetivo:** Interface de usuário final com dashboard completo, todas as telas funcionais, mobile-responsive acima de 1024px. Ponto de "fechar a planilha".  
**Gate de saída:** Vitor usa o Goodies como única fonte de verdade financeira por 30 dias sem precisar abrir a planilha.

---

## Escopo

Este épico consolida e polishes os frontends parciais construídos nos épicos anteriores, adiciona navegação unificada, e garante que todas as telas estão completas.

### Inclui:
- Layout global: sidebar de navegação, header com alertas, tema dark
- Dashboard principal: patrimônio total, XIRR, retorno real, alertas ativos, última atualização
- Ledger UI: lista de transações com filtros e busca, formulário de transação com autocomplete de categoria, resumo mensal, projeção de caixa (gráfico)
- Portfolio UI: tabela de posições (preço médio, valor atual, retorno %), alocação (pizza chart), histórico de operações, tela de rebalanceamento com input de valor
- Market UI: preços atuais com indicador de staleness, wallets scan recente, botão de atualização manual
- Analytics UI: XIRR vs benchmarks (gráfico de linha lado a lado), projeções 3 cenários (gráfico área), metas com progress bars e countdown, timeline de alertas
- Responsividade: tela mínima 1024px (desktop-first)
- Loading states e error states para todos os componentes
- Formulário de login
- Empty states para dados ainda não cadastrados

### Não inclui:
- Mobile app
- Importação de extrato bancário
- Dark/light toggle (dark-only no MVP)

---

## Stories

- STORY-07-01: Layout global (sidebar, header, sistema de rotas)
- STORY-07-02: Dashboard principal (patrimônio, XIRR, alertas, última atualização)
- STORY-07-03: Ledger UI — lista de transações com filtros
- STORY-07-04: Ledger UI — formulário de transação
- STORY-07-05: Ledger UI — resumo mensal e projeção de caixa
- STORY-07-06: Portfolio UI — tabela de posições polida
- STORY-07-07: Portfolio UI — alocação (pizza chart) e motor de rebalanceamento
- STORY-07-08: Portfolio UI — histórico de operações paginado
- STORY-07-09: Market UI — preços com staleness e atualização manual
- STORY-07-10: Analytics UI — XIRR vs benchmarks (gráfico linha)
- STORY-07-11: Analytics UI — projeções 3 cenários e metas
- STORY-07-12: Loading states e error states globais
- STORY-07-13: Revisão de acessibilidade (contraste, keyboard nav básico)
- STORY-07-14: Validação final: 30 dias de uso sem planilha

---

## Dependências
EPIC-00 a EPIC-06 concluídos.

## Bloqueados por este épico
Nenhum — este é o épico final do MVP.
