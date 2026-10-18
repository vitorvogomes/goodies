---
description: Verifica se um marco da v2 passou no gate. Uso: /gate m1 (m1..m4)
---

Verifique o gate do marco $ARGUMENTS da v2. O gate está no fim da seção do marco no `PROGRESS.md`; os critérios abaixo
são o mínimo. Reporte **PASS** ou **FAIL** com a evidência de cada item.

**Comum a todos os marcos:**
```bash
cd api && uv run pytest tests/ -q --cov -rs     # -rs lista os pulados
cd web && pnpm test && pnpm lint && pnpm build
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool   # postgres e redis ok
```
- **FAIL** se algum teste `dados_reais` foi pulado (o `-rs` mostra). Antes: `python -m scripts.ops.restore_dados_db`.
- **FAIL** se o banco real não estiver no `head` do código.
- Todas as stories do marco `[x]` no `PROGRESS.md`.

**m1 — Ritual confiável:**
- Poupança de jun/2026 = 55,48% (teste `dados_reais`), contagens iguais, zero órfãs e só os deltas esperados no script
  de comparação mês × categoria.
- Invariantes contra o baseline da Story 1.3: XIRR consolidado/por ativo, caixinhas, aplicado Flash = R$ 12.000,00.
- UJ-1 executada no app: importar → revisar → conta PF "conferido". UJ-5: meses de jun/2026 até o anterior fechados.
- `jul/2024–mai/2026` fechados (`origin = retro`).

**m2 — Caixa e orçamento:**
- Golden tests do orçamento a partir de `tests/fixtures/mockup_out2026.json`.
- `python -m scripts.ops.metricas --sm1-inicio <data>` registrado (SM-1 parcial: caixa).

**m3 — Investimentos e aportes:**
- XIRR igual ao baseline (ou diferença explicada); conciliação B3/carteiras dentro da AD-13; distribuição fecha ao centavo.
- SM-1 iniciada (`metricas --sm1-inicio`).

**m4 — Histórico e ajustes completos:**
- `python -m scripts.ops.metricas` mostra SM-1 ≥ 30 dias seguidos; SM-2, SM-3 e SM-5 na meta.
- Nenhuma rota v1 sem substituto; lista de exceção do "no raw color" vazia.
