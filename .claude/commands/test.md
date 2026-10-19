---
description: Roda as suítes de teste (api e web) com cobertura e type check
---

Execute:
```bash
cd api && uv run pytest tests/ --cov --cov-report=term-missing -q -rs
# --cov usa o [tool.coverage] do pyproject (fail_under = 80); -rs lista os testes pulados
cd api && uv run mypy engines workers hermes auth db config.py main.py
```
Se a story tocou `web/`:
```bash
cd web && pnpm test && pnpm lint
```

Relate:
1. Total de testes: passando, falhando e **pulados** (diga quais `dados_reais` foram pulados e por quê)
2. Cobertura por engine (`common`, `ingest`, `ledger`, `wallet`, `portfolio`, `planning`, `closing`, `alerts`,
   `overview`, `market`) e `workers/` (os jobs)
3. Arquivos abaixo de 80%
4. Erros de mypy (`--strict` nos pacotes tocados pela story)

Engine crítica (ledger, portfolio, planning, closing) abaixo de 80% ou teste `dados_reais` pulado numa story que toca
dado real = **BLOQUEADOR** para `/done`.
