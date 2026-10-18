---
title: "Sprint Change Proposal — v1 → v2 (tracker e comandos)"
date: 2026-10-18
mode: batch
scope: moderate
status: aprovada e aplicada
---

# Sprint Change Proposal — v1 → v2 (tracker e comandos)

## 1. Problema

O planejamento da v2 está pronto:
- `docs/v2/planning/epics.md` está final, com 10 épicos e 78 stories;
- a checagem de prontidão deu PASS;
- a revisão adversarial foi aplicada.

Mas o fluxo de trabalho ainda aponta para a v1:
- `PROGRESS.md` acompanha as stories `XX-YY` dos milestones m0–m7.
- `/story` lê `docs/v1/06_Stories/STORY-XX-YY*.md`.
- `/gate` verifica m0–m5 da v1 (ex.: alerta de concentração Flash, wallets com scan < 4 h).
- `/done` usa `--cov=api` e não exige `/code-review` nem os testes `dados_reais`.
- `/status` lê a estrutura de milestones da v1.
- `.claude/memory/skills.md` tem a matriz B2 com épicos indicativos (A–F) que não existem no backlog final.

Sem essa troca, o primeiro `/story 1.1` não encontra a story, e o `/gate` aprova o marco com critérios errados.

## 2. Impacto

- **Épicos e stories:** nenhum muda; o backlog é a fonte.
- **PRD, arquitetura e UX:** nenhum muda.
- **Artefatos de processo:**
  - `PROGRESS.md`;
  - `.claude/commands/{story,done,gate,status,test}.md`;
  - matriz B2 de `.claude/memory/skills.md`;
  - a seção "Workflow de sessão" do `CLAUDE.md` (formato do id).
- **Código:** nenhum. A Story 1.1 continua dona da reescrita da stack e dos gates no `CLAUDE.md`, do `conventions.md`
  e do `.env.example`.

## 3. Abordagem recomendada

**Ajuste direto.** O tracker da v1 vai para `docs/v1/PROGRESS-v1.md` (`git mv`, histórico preservado). O `PROGRESS.md`
novo é gerado das 78 stories do `epics.md`, agrupadas por marco e por épico, com:
- o gate de cada marco;
- o ponto de uso no fim do Épico 3;
- a SM-1 parcial no marco 2;
- as datas-alvo **em aberto**, por decisão do Vitor: medir o ritmo real primeiro.

Esforço baixo e risco baixo, sem impacto no cronograma.

## 4. Mudanças

| Artefato | Antes | Depois |
|---|---|---|
| `PROGRESS.md` | v1: m0–m7, stories `XX-YY`, registro de sessões da v1 | v2: 4 marcos → 10 épicos → 78 stories `N.M` (`[ ]`), gate por marco, regras do backlog e registro de sessões novo |
| `docs/v1/PROGRESS-v1.md` | — | o `PROGRESS.md` da v1, movido com `git mv` |
| `/story` | glob em `docs/v1/06_Stories/`; skills pelo frontmatter ou pela matriz m0–m7 | lê `### Story N.M` em `docs/v2/planning/epics.md` + o épico + as regras gerais; skills pela matriz B2 nova; plano TDD com backup, baseline e `goodies_dev` quando a story toca dado real; marca `[~]` |
| `/done` | `pytest --cov=api`; marca `[x]`; commit `feat(mX)` | `pytest --cov` (pyproject), `pnpm test/lint/build` se tocou o web, confere cada AC com evidência, exige `/code-review`, `dados_reais` pulado = falha, lembra que o banco real só migra por `scripts.ops.migrar`; commit `feat(e<N>): <N.M>` local, sem push |
| `/gate` | m0–m5 da v1 | m1–m4 da v2: comum (suíte com `-rs`, web, health, banco em `head`, `dados_reais` pulado = FAIL) + critérios por marco (55,48%, deltas, baseline, UJ-1/UJ-5, `close_retro`, goldens do orçamento, SM-1) |
| `/status` | milestone/story da v1 | marco, progresso no marco e no total (78), em andamento, próxima story, gate |
| `/test` | cobertura por engine da v1 | todas as engines da v2, testes pulados listados, web quando tocado; `dados_reais` pulado ou engine crítica < 80% = bloqueador |
| `skills.md` B2 | épicos indicativos A–F | épicos 1–10 do backlog final → skills |
| `CLAUDE.md` › Workflow de sessão | `/story XX-YY`, `/done XX-YY`, `/gate mX` | `/story N.M`, `/done N.M`, `/gate m1..m4`, com o backlog em `docs/v2/planning/epics.md` (o resto do arquivo fica para a Story 1.1) |

Os textos completos estão prontos para aplicar.

## 5. Handoff

- **Escopo:** moderado (reorganização do backlog e do processo). Sem replanejamento.
- **Responsável:** o agente de dev aplica nesta sessão, num commit local (`chore(v2): tracker e comandos para a v2`).
- **Critérios de sucesso:**
  - `/status` aponta "Próxima: 1.1 — Arrumação dos docs vivos para a v2";
  - `/story 1.1` carrega a seção certa;
  - `/gate m1` lista os critérios da v2;
  - o `PROGRESS.md` tem as 78 linhas;
  - o tracker da v1 fica preservado no histórico do git.
