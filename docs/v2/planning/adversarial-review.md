---
title: "Revisão adversarial — Goodies v2.0"
date: 2026-10-18
lens: adversarial (bmad-review)
inputs: [epics.md, prd.md, ARCHITECTURE-SPINE.md, EXPERIENCE.md, implementation-readiness.md]
---

# Revisão adversarial — Goodies v2.0

Um revisor independente revisou o pacote inteiro depois da checagem de prontidão e encontrou **24 achados**. Os de
segurança e o do mockup foram conferidos no código:
- `docker-compose.yml` publica as portas 8000, 5432 e 6379 em todas as interfaces;
- dentro do container, o `.env` não é lido (`config.py:7`), e os segredos caem nos padrões `dev-insecure-*` do
  repositório;
- o `hermes_router` está montado (`main.py:68`);
- `mockups/key-orcamento.html` mostra o financiado como R$ 4.487,99.

## Precisa de decisão do Vitor

| # | Achado | Recomendação |
|---|---|---|
| R1 | Tarefas da Rotina e de telas v1 sem story, e a 10.5 apaga as rotas v1 sem substituto. Faltam: posições manuais (L-BTC/L-USDT da SideSwap, DeFi hyUSD/xSOL), aviso de vencimento DeFi, aviso de gasto acima de 120% da média, lançamento manual de transação (/ledger/new), média de aporte, projeção RF × RV e %projetada da Gestão Qualificada | Stories novas: Ajustes › Posições manuais (cripto confidencial + DeFi com vencimento), aviso de vencimento DeFi, aviso de gasto acima da média e "Nova transação" em Caixa › Transações, todas antes da 10.5. A 10.5 só apaga rota v1 que tenha substituto. Projeção RF × RV, Gestão Qualificada e a estratégia 1MM ficam na v2.1 e **não contam** para a SM-1 |
| R2 | A SM-1 só começa depois de ~58 de 70 stories, e não há instrumento para medi-la | Data-alvo por marco no PROGRESS.md; SM-1 parcial por marco (caixa sem planilha a partir do marco 2); `metricas` registra `sm1_inicio` e `planilha_aberta(data, motivo)` |
| R3 | A receita do trabalho chega pelo OFX do MEI, que é multi-mês. Até ele ser importado, o mês aparece com trabalho = 0 e pode ser fechado assim | Precondição `confirma` "MEI não cobre {mês}"; termos que dependem do trabalho com o `as_of` do MEI; o aviso "mês segue aberto" só depois do dia 15. Na prática, fechar o mês pede o OFX do MEI até o fim dele |
| R4 | A conferência cumulativa desde uma âncora só faz um erro em 2024 deixar todos os meses seguintes divergentes | Conferência **encadeada**: saldo informado anterior + Σ transações do intervalo = saldo informado atual; candidatas só do intervalo; `ancorar_saldo --relatorio` antes do Épico 5 para medir o problema; retroativo divergente vira `confirma` com o valor |
| R5 | O OFX semanal quase nunca termina no fim do mês, então quase todo mês fecharia com pendência | Aceitar como conferido do mês o primeiro saldo informado com data ≥ fim do mês que bate com o calculado |
| R6 | O container migra o banco real a partir do diretório de trabalho (qualquer branch, `--reload`) e não há banco de desenvolvimento | `AUTO_MIGRATE=false`; desenvolvimento em `goodies_dev` (restaurado do backup); o banco real só migra por `scripts.ops.migrar` (main limpa + invariantes verdes + backup); runbook de recuperação no LOCAL_DEV.md |
| R7 | Os backups ficam no mesmo disco, sem criptografia e com retenção por contagem (reinícios encurtam a janela) | Retenção por idade (30 diários + 12 mensais) separada dos pré-migração; restauração automática mensal em `goodies_dados`; recusar `BACKUP_DIR` sincronizado com a nuvem; criptografia com `age` e cópia para disco externo (opcional, escolha do Vitor) |
| R8 | Segurança local: portas abertas na rede, segredos públicos no container, Hermes montado, login sem limite de tentativas | Portas em `127.0.0.1`; `env_file: .env` e caminho do `.env` corrigido; recusar segredos `dev-insecure-*` fora de teste; senha no Postgres e no Redis; Hermes desligado por flag na v2.0 (e não migrado nas 2.2/2.5); limite de tentativas no login |
| R9 | Cada termo novo pede refechar os mesmos meses de 4 a 6 vezes, e o refechar recalcula tudo, mudando o passado em silêncio | `refechar --completar` (padrão) só preenche colunas nulas/`fora_do_resumo`; recalcular tudo exige `--recalcular` com a diferença por métrica; um refechar geral recomendado no fim do marco 3 |

## Aplicar direto (sem decisão de produto)

| # | Achado | Correção |
|---|---|---|
| A1 | O fechamento não exige o consolidado B3 do mês (SM-3 falha por construção) | Precondição `confirma` "consolidado B3 de {mês} não importado"; cobertura grava a fonte da B3 |
| A2 | `wallet_positions` só guarda o último scan | `wallet_position_history` (1 linha por dia, último scan antes do fim do mês) na 5.1; `build_month_summary` usa o último ≤ `as_of`; precondição "sem scan de cripto no fim de {mês}" |
| A3 | A regra de lacuna gera falso positivo em B3 mov/neg, no consolidado e nos lotes legado | Lacuna por intervalo só no Nubank; consolidado = mês sem arquivo; B3 mov/neg só por transferência não coberta; legado sem lacuna interna |
| A4 | Conta do CSV e período editados depois do hash da prévia | Overrides geram nova prévia (`staged` e hash novos); `confirm` só com `batch_id` + hash |
| A5 | "XIRR igual ao anterior" depende de `date.today()` e de preço vivo | `EVALUATION_DATE` fixa, preços congelados, `scripts.ops.baseline --salvar` fora do repo |
| A6 | `restore_dados_db` usa o backup mais recente, já migrado; a 2.3 cita `goodies_test`; o `/gate` passa com testes pulados | `--backup <pré-migração>` fixado por revisão; ordem restaura → mede → upgrade → mede; 2.3 em `goodies_dados`; `/gate` falha com `dados_reais` pulado |
| A7 | O mockup diz financiado R$ 4.487,99; os insumos do golden não estão em fixture | Corrigir o mockup; `tests/fixtures/mockup_out2026.json`; goldens do teto e com devolução |
| A8 | ACs não verificáveis (similaridade, "< 3 s", "dois cliques") | Similaridade = Jaccard de tokens ≥ 0,6 (empate → mais recente) com fixture; p95 de 10 cargas a frio em `goodies_dados`; tabela informação → caminho |
| A9 | 5.7 ainda cita "âncora de jun/2024" | Fim de jul/2024 |
| A10 | `categorization_events` não distingue correção de migração/reaplicação | `cause ∈ {import, review, inline_edit, rule_created, reapply, move, migration, undo}`; a 10.4 filtra por causa |
| A11 | Renome deixa o texto legado com o nome velho e quebra as telas v1 | Renome regrava a coluna de texto em `ledger.service` (exceção documentada) + fumaça v1 |
| A12 | Notebook desligado gera avisos de job e de scan antes do catch-up | Catch-up na subida antes de `/alerts`; aviso só se o catch-up falhar ou após 30 min |
| A13 | `date.today()` / `datetime.now()` / `CURRENT_DATE` legados em UTC | Lint/teste na 2.1 que proíbe fora de `common.dates` e corrige os usos atuais |
| A14 | 3.4, 3.11 e 7.2 grandes demais | Dividir: 3.4 (saldo/pagador × `transaction_id`/hook), 3.11 (`ancorar_saldo`+cálculo × aviso/UI), 7.2 (histórico BCB × XIRR real) |
| A15 | `/alerts` roda resumos pesados em toda tela | Diferença do aviso só com fluxo + cache por (mês, dirty); p95 `GET /alerts` < 500 ms |

## Achados (JSON)

A lista bruta dos 24 achados (lente `adversarial`) fica no histórico desta sessão. A tabela acima cobre todos: 1→R1, 2→R2,
3→R3, 4→A1, 5→A2, 6→R4, 7→R5, 8→A3, 9→A4, 10→R6, 11→R7, 12→R8, 13→A5, 14→A6, 15→A7, 16→A8, 17→A9, 18→R9, 19→A10,
20→A11, 21→A12, 22→A13, 23→A14, 24→A15.

## Resolução (2026-10-18)

O Vitor aprovou R1–R9 como recomendados e mandou desligar o Hermes na v2.0. Tudo foi aplicado. `epics.md` passou a ter
**78 stories**. Novas:
- 1.6 Endurecimento local;
- 2.8 Lançar transação manual;
- 6.4 Aviso de gasto acima da média;
- 7.8 Posições manuais e vencimento DeFi;
- 10.3 Ajustes › Atualização.

Divididas:
- 3.4 → 3.4 + 3.5;
- 3.11 → 3.12 + 3.13;
- 7.2 → 7.2 + 7.3.

A1–A15 entraram nos ACs. PRD, EXPERIENCE, spine (lint sem apontamentos) e o mockup `key-orcamento.html` foram emendados,
com linha no memlog de cada um.
