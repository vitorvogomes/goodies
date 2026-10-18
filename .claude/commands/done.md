---
description: Encerra a story atual, atualiza PROGRESS.md e commita (local). Uso: /done 1.1 "descrição"
---

Encerre a story $ARGUMENTS nesta ordem. Pare no primeiro passo que falhar e corrija antes de seguir.

1. **Testes da API:**
   ```
   cd api && uv run pytest tests/ -q --cov --tb=short
   ```
   `--cov` usa o `[tool.coverage]` do pyproject (`fail_under = 80`). Testes `dados_reais` pulados contam como falha se a
   story tocou dado real (eles precisam de `goodies_dados`: `python -m scripts.ops.restore_dados_db --backup <pré-migração>`).

2. **Web, se a story tocou `web/`:** `cd web && pnpm test && pnpm lint && pnpm build`.

3. **Critérios de aceite:** releia a seção da story em `docs/v2/planning/epics.md` e confirme cada Given/When/Then com a
   evidência (teste, comando ou tela). Item sem evidência = não concluída.

4. **Code review:** `/code-review` deve ter rodado nesta story, com os achados aplicados ou registrados. Se não rodou, rode
   agora.

5. **PROGRESS.md:** na linha da story $ARGUMENTS, troque `[~]`/`[ ]` por `[x]` e preencha o Commit com o hash curto do
   commit do passo 7 (atualize depois do commit, num amend, ou registre na próxima sessão). Adicione uma linha no
   **Registro de sessões** (data, marco, story, notas relevantes).

6. **Migração no banco real:** se a story tem revisão Alembic, ela NÃO é aplicada aqui. Diga ao Vitor que o banco real
   só migra por `python -m scripts.ops.migrar` (main limpa, testes `dados_reais` verdes, backup na hora).

7. **Commit local (nunca `git push` — o Vitor faz o push manual):**
   ```
   git add -A
   git commit -m "feat(e<N>): <N.M> — descrição concisa"
   ```
   O gitleaks do pre-commit precisa passar.

8. **Mostre a próxima story pendente** do `PROGRESS.md`.
