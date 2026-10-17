---
description: Roda a suite de testes completa com relatório de cobertura
---

Execute:
```bash
cd api && uv run pytest tests/ --cov --cov-report=term-missing -q
# --cov sem alvo usa [tool.coverage] do pyproject: engines + workers + auth + hermes,
# fail_under = 80 (a suite falha se a cobertura total cair abaixo)
```

Depois execute o type checker:
```bash
cd api && uv run mypy engines workers hermes auth db config.py main.py
```

Relate:
1. Total de testes: X passando, Y falhando
2. Cobertura por engine:
   - `engines/ledger/`: X%
   - `engines/portfolio/`: X%
   - `engines/market/`: X%
   - `engines/wallet/`: X%
   - `workers/`: X%
3. Arquivos abaixo de 80%: liste com cobertura atual
4. Erros de mypy: liste se houver

Se alguma engine crítica (portfolio, ledger ou wallet) estiver abaixo de 80%, marque como **BLOQUEADOR** para avançar de milestone.
