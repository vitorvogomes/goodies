---
description: Encerra a story atual, atualiza PROGRESS.md e commita. Uso: /done STORY-XX-YY "descrição"
---

Execute esta sequência para encerrar a story $ARGUMENTS:

1. **Rodar os testes da área implementada:**
   ```
   cd api && pytest tests/ -q --cov=api --cov-fail-under=80 --tb=short
   ```
   Se falhar: NÃO continue. Corrija os testes primeiro.

2. **Atualizar PROGRESS.md:**
   - Encontre a linha da story $ARGUMENTS
   - Mude `[ ]` para `[x]`
   - Adicione o hash do commit na coluna Commit (use o próximo commit)

3. **Adicionar linha no Registro de sessões** (tabela no final do PROGRESS.md):
   - Data: hoje
   - Milestone: milestone atual
   - Stories: a story que acabou
   - Notas: qualquer observação relevante

4. **Commitar:**
   ```
   git add -A
   git commit -m "feat(MILESTONE): STORY-XX-YY — descrição concisa"
   ```
   Use o milestone no escopo (ex: `feat(m0)`, `feat(m1)`, etc.)

5. **Mostrar próxima story pendente** do PROGRESS.md.
