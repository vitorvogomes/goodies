---
description: Roda a suite de testes completa com relatório de cobertura
---

Execute:
```bash
cd api && pytest tests/ --cov=api --cov-report=term-missing -q
```

Depois execute o type checker:
```bash
cd api && mypy api/ --ignore-missing-imports --quiet
```

Relate:
1. Total de testes: X passando, Y falhando
2. Cobertura por engine:
   - `engines/ledger/`: X%
   - `engines/portfolio/`: X%
   - `engines/market/`: X%
   - `engines/analytics/`: X%
3. Arquivos abaixo de 80%: liste com cobertura atual
4. Erros de mypy: liste se houver

Se alguma engine crítica (portfolio ou analytics) estiver abaixo de 80%, marque como **BLOQUEADOR** para avançar de milestone.
