# SESSION m2-portfolio — Prompt de inicialização

**Data:** 2026-06-04  
**Branch:** `m2-portfolio` (HEAD = f527418, merged from m1-ledger)  
**Milestone:** m2 — Portfolio Engine  
**Gate crítico:** XIRR Python == Excel XIRR (±0,1 pp)

---

## Estado atual

✅ m1 Ledger Engine **100% completo** e **mergeado** para main.
✅ STORY-02-01 (schema `asset_operations` + `portfolio_targets`) commitada.
✅ Suite: 105/105 testes verdes; cobertura engines 94%.

Próximas stories: **02-02** (seed targets) e **02-05** (XIRR) podem rodar em paralelo.

---

## Sequência recomendada (batches com paralelismo)

```
B1: 02-02 (seed targets) + 02-05 (XIRR scipy)      [PARALELO ✅]
  ↓
B2: 02-03 (CRUD backend asset-operations)          [sequencial — desbloqueia B3+]
  ↓
B3: 02-04 (DCA) + 02-10 (dividendos)                [PARALELO ✅]
  ↓
B4: 02-06 (endpoint XIRR) + 02-07 (posição)         [PARALELO ✅]
  ↓
B5: 02-08 (alocação) → 02-09 (rebalanceamento)      [sequencial]
  ↓
B6: 02-11 (IR) → 02-12 (IR cripto)                  [sequencial]
  ↓
B7: 02-13 (FE posições) + 02-14 (FE histórico)      [PARALELO ✅]
  ↓
B8: 02-15 (FE alocação) → 02-16 (FE rebalanceamento) [sequencial]
  ↓
GATE: 02-17 (seed fontes reais) → 02-18 (validação XIRR) [sequencial — BLOQUEADOR]
```

### Próximo passo da sessão

**Executar B1 em paralelo:**
1. STORY-02-02: Seed `portfolio_targets` com 6 categorias (Ações 10%, ETFs 12.5%, FIIs 10%, Renda Fixa 50%, Cripto 5%, Aposentadoria 12.5%)
2. STORY-02-05: Implementar XIRR via `scipy.optimize.brentq(npv, -0.999, 100.0, xtol=1e-8)`

Ambas são **independentes**: 02-02 só cria INSERTs; 02-05 é pura matemática sem DB.

---

## Contexto técnico importante

### Bridge m1↔m2 (ADR — refere docs/09_Bridge_M1_M2.md)

- m1 grava `kind=investment` com `category='Toro (B3)'`, `amount=-5000` (aporte)
- m2 reconcilia: operação real em `asset_operations` (broker='Toro', asset_symbol='PETR4', ...)
- XIRR calcula sobre `asset_operations` usando `scipy.optimize.brentq`

### Fontes de dados para gate 02-17-18

| Destino | Fonte | Mecanismo |
|---|---|---|
| Flash Capital | Debêntures Serie 5 (12 itens, jul/2024–jun/2026) | Seed direto (JSON já disponível) |
| Toro (B3) | Portal do Investidor | Playwright (automatizado — credenciais B3 no .env) |
| Binance | Binance API | GET /api/v3/myTrades (credenciais já no .env) |
| Liquid/DeFi | Wallet scan | m4 placeholder (manual por ora) |
| Renda Fixa / Caixinha | Aportes m1 + snapshot manual | Flow-based |

### Skills obrigatórios por story

- **02-02:** TDD (testes de inserção)
- **02-05:** `test-driven-development` + `supabase-postgres-best-practices` (se query)
- **02-03+:** TDD + `supabase-postgres-best-practices` (schema, índices, validação)
- **FE (02-13+):** `frontend-design` + `next-best-practices` (quando chegar)

---

## Checklist para iniciar nova sessão

```bash
# 1. Verificar estado
git status                      # deve estar clean
git log --oneline -1           # deve ser f527418 (merge commit)
git branch                      # deve estar em m2-portfolio

# 2. Confirmar suite
cd api && uv run pytest -q      # esperado: 105/105 passando

# 3. Iniciar story
/story 02-02  # ou /story 02-05 (decidir qual batch começar)
```

---

## Referências rápidas

- **Estrutura:** `CLAUDE.md` (stack + guardrails) | `docs/09_Bridge_M1_M2.md` (semântica)
- **Memória:** `.claude/memory/` (conventions, decisions, skills, security)
- **Progresso:** `PROGRESS.md` (atualizar ao concluir story)
- **Git:** conventional commits `feat(m2): ...` | `fix(m2): ...`
- **TDD:** RED → GREEN → REFACTOR (sempre)
- **Cobertura:** ≥80% para engines críticas (portfolio, analytics)

---

## Perguntas para o usuário (fazer antes de começar)

1. **B1 em paralelo ou sequencial?** Quer rodar 02-02 + 02-05 em paralelo (mais rápido) ou um por vez?
2. **02-02 ou 02-05 primeiro?** Qual prefere começar?
3. **Comunicação ao longo?** Quer perguntas inline para confirmar decisões ou liberdade total?

---

*Prompt pronto para colar em nova sessão:*

> Read `CLAUDE.md`, `PROGRESS.md`, and `SESSION_M2.md`. Continue from **STORY-02-02** (seed portfolio_targets) or **STORY-02-05** (XIRR) — they run in parallel (B1).
>
> Implement following TDD. Ask questions along the way if unsure. Update PROGRESS.md when done.
>
> **Contexto:** m1-ledger mergeado em main. Nova branch m2-portfolio (HEAD f527418). 105/105 testes verdes. Próximo gate: XIRR Python == Excel XIRR (±0,1 pp).
>
> **Referências:** docs/09_Bridge_M1_M2.md (semântica), .claude/memory/ (stack + patterns)
