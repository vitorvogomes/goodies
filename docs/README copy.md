---
tipo: hub_projeto
projeto: Goodies
criado: 2026-06-02
tags: [goodies, dev, financeiro, hub]
---

# Goodies — Plataforma Pessoal de Controle Financeiro

> Hub central do projeto. Atualizar a cada sessão com o estado real.

---

## Estado atual

**Status:** `Pronto para implementação`  
**Fase atual:** `m0-foundation — criar repo, bootstrap FastAPI + Next.js + Supabase`  
**Última sessão:** `2026-06-02 — Minerva — BMAD Fases 1–3 completas (PRD + Arquitetura + Épicos + Stories)`  
**Próxima ação:** `Vitor: criar repo GitHub → WSL: gsd init → implementar STORY-00-01`

---

## O que é

Goodies é uma plataforma pessoal de controle financeiro que substitui a planilha Google Sheets atual. Cobre 4 domínios: Ledger (caixa), Portfolio (investimentos + XIRR), Market (preços automáticos) e Analytics (benchmarks, metas, projeções). Construído especificamente para o portfólio, estrutura de renda e metas do Vitor.

O critério de sucesso não é "bonito" — é **tomar decisões financeiras melhores com dados corretos em tempo real.**

---

## Progresso por fase

| Fase | Milestone | Status |
|---|---|---|
| — | Planejamento (Brief + Contexto) | ✅ Concluído |
| — | PRD (BMAD/John) | ✅ Concluído |
| — | Arquitetura (BMAD/Winston + Minerva) | ✅ Concluído |
| — | Épicos + Stories (BMAD) | ✅ Concluído |
| 0 | Foundation (bootstrap) | ⬜ Pendente |
| 1 | Ledger Engine | ⬜ Pendente |
| 2 | Portfolio Engine | ⬜ Pendente |
| 3 | Market Data (preços) | ⬜ Pendente |
| 4 | Integração corretoras (Binance, B3, wallets) | ⬜ Pendente |
| 5 | Analytics Engine | ⬜ Pendente |
| 6 | Observabilidade | ⬜ Pendente |
| 7 | Frontend real | ⬜ Pendente |

---

## Documentos do projeto

| Arquivo | Conteúdo | Status |
|---|---|---|
| `00_Brief.md` | Contexto financeiro, problema, features MVP, adendo Hermes | ✅ Pronto |
| `08_Contexto_Financeiro.md` | Raio-X completo da planilha: snapshot, gaps, riscos, contratos | ✅ Pronto |
| `01_PRD.md` | Product Requirements Document (BMAD/John) | ✅ Pronto |
| `02_Arquitetura.md` | Design técnico completo (BMAD/Winston + Minerva) | ✅ Pronto |
| `03_Stack.md` | Stack detalhado com versões e configs | ✅ Pronto |
| `04_UX.md` | Design system, layouts de tela, copy financeiro | ✅ Pronto |
| `05_Epicos/` | 8 épicos (EPIC-00 a EPIC-07) | ✅ Pronto |
| `06_Stories/` | User stories com critérios de aceite | ✅ Pronto (stories críticas) |
| `07_Decisoes.md` | 8 ADRs (Minerva) | ✅ Pronto |
| `project-context.md` | Contexto para GSD-Pi (Claude Code) | ✅ Pronto |

**Referências externas:**
- `coleta_carteira.py` — script de coleta diária (Hermes/cron) — funcional
- `posicao.json` — fonte de verdade das posições (atualização manual por enquanto)

---

## Sessões do projeto

```dataview
TABLE WITHOUT ID
  file.link AS "Sessão",
  data AS "Data"
FROM "03_Sessoes"
WHERE contains(file.name, "Goodies") OR contains(tags, "goodies")
SORT data DESC
```

| Sessão | Data | Mestra | O que foi feito |
|---|---|---|---|
| [[2026-06-02_Hatchepsut_Goodies_Raio_X_Financeiro]] | 2026-06-02 | Hatchepsut | Raio-X da planilha, Brief, Contexto Financeiro, metodologia BMAD+GSD-Pi |
| [[2026-06-02_Minerva_Goodies_PRD_Arquitetura]] | 2026-06-02 | Minerva | BMAD Fases 1–3: PRD + Arquitetura + Stack + ADRs + 8 Épicos + Stories + project-context.md |

---

## Decisões ativas

> Ver `07_Decisoes.md` para ADRs completos quando disponível.

- **Hermes é braço operacional, não bloqueante:** Goodies funciona 100% sem o Hermes. Hermes consome API do Goodies opcionalmente.
- **Stack definido no Excalidraw:** FastAPI + Next.js + Supabase + Redis + Fly.io + Vercel (referência: `Excalidraw/Goodies.excalidraw`)
- **XIRR é a métrica principal de retorno:** rentabilidade simples (3,14%) é irrelevante para portfólio DCA.
- **Dados manuais não bloqueiam:** Flash debênture, DeFi e Liquid têm fallback manual — sistema não pode travar por falta deles.

---

## Riscos ativos (para o sistema monitorar futuramente)

1. 🔴 **Concentração Flash** — empregador (71% renda) + credor (43% RF) simultaneamente
2. ⚠️ **Cripto acima do alvo** — 13,7% atual vs. 5% meta
3. ⚠️ **Retorno real negativo** — -1,31% em 22 meses
4. ⚠️ **Reserva de emergência subfinanciada** — Snow Trip ≠ reserva
5. ⚠️ **IR cripto 2025** — verificar meses março e julho/2025
6. 📅 **Vencimentos DeFi** — xSOL + hyUSD vencem 29/09/2026

---

## Repositório (quando criado)

- **WSL:** `/projects/goodies`
- **GitHub:** [https://github.com/vitorvogomes/goodies.git]
- **Branch principal:** `main`
- **GSD-Pi:** instalar no WSL — `npm install -g @opengsd/gsd-pi@latest`

---

## Referências

- [[00_Brief]] — Brief do projeto
- [[08_Contexto_Financeiro]] — Raio-X financeiro completo
- [[00_Sistema/Ferramentas/Agentes/BMAD_Referencia]] — como acionar BMAD
- [[00_Sistema/Ferramentas/Agentes/GSD_Pi_Referencia]] — como usar GSD-Pi
- [[00_Sistema/Templates/Projeto_Dev/_README]] — metodologia de projetos Dev

---

*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
