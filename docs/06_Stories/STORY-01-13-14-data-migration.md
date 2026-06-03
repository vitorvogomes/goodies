---
tipo: story
epico: EPIC-01
story: STORY-01-13-14
titulo: Migração e validação de dados históricos (FLUXO DE CAIXA)
status: pendente
estimativa: L (4-6h)
tags: [goodies, story, ledger, migracao, dados]
---

# STORY-01-13-14 — Migração de Dados: Ledger

**Como** Vitor  
**Quero** importar 24 meses de histórico de caixa da planilha para o Goodies  
**Para** ter análise histórica real desde jul/2024 sem redigitar tudo manualmente

---

## Critérios de aceite

- [ ] Script `scripts/migrate_ledger.py` que lê CSV exportado da aba "FLUXO DE CAIXA"
- [ ] Mapeamento de colunas do CSV para `transactions` (data, valor, categoria, conta, descrição)
- [ ] Script idempotente: rodar 2× não duplica dados (idempotency via hash de (data, valor, categoria, conta))
- [ ] Categorias do CSV mapeadas para as categorias do sistema (dicionário de mapeamento configurável)
- [ ] Contas criadas automaticamente se não existirem
- [ ] **Validação (STORY-01-14):**
  - Saldo total do último mês bate com a planilha (tolerância < R$ 1)
  - Total de receita do período bate
  - Total de despesa do período bate
  - Taxa de poupança de junho/2026 bate com a planilha (55% ± 0,1%)
- [ ] Relatório de migração: X linhas importadas, Y erros (com detalhes), Z linhas duplicadas ignoradas

## Notas de implementação
- Exportar CSV da planilha: File → Download → CSV (aba FLUXO DE CAIXA)
- Colunas esperadas do CSV da planilha do Vitor: validar o formato real antes de escrever o script
- Valores negativos na planilha = despesa; positivos = receita (confirmar convenção com Vitor)
- Rodar localmente antes de aplicar em produção

## Dependências
STORY-01-01 a STORY-01-04 concluídas (schema e CRUD de transações existentes).
