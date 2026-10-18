---
title: "Addendum — PRD Goodies v2"
created: 2026-10-17
updated: 2026-10-17
---

# Addendum — PRD Goodies v2

> Apoio técnico ao PRD: mapa brownfield (o que já existe no código) e notas para a arquitetura.

## Mapa brownfield: escopo v2.0 × código atual (2026-10-17)

| Item v2.0 | Estado | O que existe / o que falta |
|---|---|---|
| Recuperar a base (FR-7) | Parcial | Import Nubank (`engines/ledger/importer.py`, dedup por FITID) e B3 (`portfolio/b3_import*`, `dry_run`) existem; debêntures Flash só por seed script; sem conferência do saldo Nubank (FR-5) |
| Hub de import (FR-1–6) | Parcial | Duas páginas separadas; Nubank sem prévia; debêntures Flash sem import; negociação B3 sem tratamento explícito; sem "atualizado até" por fonte nem aviso de 7 dias |
| Categorização (FR-8–12) | Parcial | Lista plana com `kind` + `match_patterns` (regras); sugestão só para despesas em "outros" (`suggest.py`); sem grupos, sem lote, aprovar não cria regra, sem reaplicação ao histórico |
| Painel principal e central de avisos (FR-13–14) | Parcial | Dashboard com resumo do mês, projeção e alertas de vencimento; faltam resultado/rentabilidade, aporte do mês, bandas, transações a revisar e **atualizado até** por fonte |
| Caixa e orçamento do mês (FR-15–20) | Parcial | Transações, `/cashflow/by-category`, view `monthly_summary`; faltam receita por pagador, custos fixos pagos × pendentes, fatura como valor pago |
| Investimentos (FR-21–27) | Parcial | Posições, alocação (só classe), XIRR, rendimentos, IR, bloco cripto; falta classe → ativo e conciliação com o consolidado B3 |
| Aportes (FR-28–31) | Parcial | `suggest_rebalancing` por déficit de classe, sem vender; faltam objetivos, bandas, piso e nível ativo |
| Histórico e fechamento de mês (FR-32–34) | Parcial | Só `monthly_summary` (fluxo); sem snapshots de patrimônio/rentabilidade por mês |
| Ajustes (FR-35) | Parcial | CRUD de categorias, custos fixos, contas, preço manual; metas de alocação sem API (seed em `portfolio/targets.py`); objetivos inexistentes; sem tela de ajustes |
| Navegação (FR-36) | Ausente | `AppShell.tsx` com 16 links planos |

| Regra de leitura | Estado | Nota |
|---|---|---|
| Receita inclui resgates | **Conflito** | Migration 0009 + `reclassify_caixinhas` gravam resgate como `investment` (ADR-011); view só soma `kind='income'` |
| Gasto só consumo / direcionado a investimentos | Existe | `kind` expense × investment; "investido" hoje é líquido de resgates → muda com a regra acima |
| Cripto em bloco | Existe | `portfolio/crypto_sleeve.py` |
| Objetivos primeiro | Ausente | Tabela `goals` adiada desde o m5 (migration 0011) |
| Rentabilidade por XIRR | Parcial | XIRR anual nominal por ativo/classe/consolidado; faltam real (IPCA, já coletado em `benchmark_data` e não lido), % ao mês e exclusão de Renda Fixa e Cripto na rentabilidade mensal por ativo |
| Custos fixos pagos × pendentes | Ausente | `fixed_costs` sem status; nada casa custo fixo com transação |
| Metas de alocação | Parcial | `portfolio_targets` só por classe, sem banda/piso/CRUD |

## Notas para a arquitetura

- **Modelo de aporte (do brief):**
  - nível classe = preencher déficit (monotônico) + bandas + piso;
  - nível ativo = déficit;
  - na v2.1, entram a inclinação por valuation, as metas por trajetória e o value averaging.

  Rejeitados: peso exponencial (alternativa ao déficit), risk parity e a fórmula de peso da
  planilha (não monotônica, com overrides). Detalhes em
  `../../briefs/brief-goodies-2026-10-17/addendum.md`.
- **Reclassificação de resgates (FR-19):**
  - a migration 0009 e `scripts/oneoff/reclassify_caixinhas.py` aplicaram o ADR-011;
  - a reversão precisa ser idempotente e preservar os totais de poupança (gate jun/2026 = 55,48%,
    que não muda porque a taxa usa a receita do trabalho);
  - as `asset_operations` derivadas de caixinhas seguem existindo.
- **Renda fixa sem arquivo (FR-23):** o CDI vem de `benchmark_data`, já coletado, e substitui
  `settings.cdi_anual`. Hoje os seeds manuais (`seed_caixinhas`, `seed_cdb_guanabara`) derivam as
  operações; na v2 isso precisa ser automático depois de cada import.
- **Debêntures (FR-24):** substituem `files/debentures-flash/integralizacoes.json` e
  `scripts/ops/seed_debentures_flash.py`. A fórmula de valoração está em
  `files/debentures-flash/formula.md`.
- **Resumo do mês (FR-32/FR-34):** não existem snapshots hoje (só a view `monthly_summary`). O
  resumo do mês fechado é o primeiro snapshot de patrimônio.
- **Saldo informado (FR-5):** o OFX do Nubank traz `<LEDGERBAL>`; o importer atual não o lê.
- **Party mode na arquitetura** (pedido do Vitor): resumo do mês fechado, vínculo aporte →
  objetivo (Q1) e migração das categorias para dois níveis sem perder a curadoria.
