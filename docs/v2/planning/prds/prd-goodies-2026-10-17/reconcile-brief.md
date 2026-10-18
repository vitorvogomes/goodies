---
title: "Reconciliação brief → PRD — Goodies v2"
created: 2026-10-17
inputs:
  - docs/v2/planning/briefs/brief-goodies-2026-10-17/brief.md
  - docs/v2/planning/briefs/brief-goodies-2026-10-17/addendum.md
  - docs/v2/planning/briefs/brief-goodies-2026-10-17/.memlog.md
target:
  - prd.md, addendum.md, .memlog.md (desta pasta)
---

# Reconciliação brief → PRD

Objetivo: listar o que o brief (brief + addendum + memlog) decidiu ou afirmou e que o PRD
**omite, contradiz ou enfraquece**. Decisões posteriores registradas no `.memlog.md` do PRD
prevalecem e aparecem como "alterado pelo memlog do PRD" (não são gaps, salvo quando criam
tensão nova).

Severidade: **Alta** = contradição ou regra do brief que o PRD quebra; **Média** = critério ou
regra enfraquecida/sem teste; **Baixa** = omissão de nuance, tom ou consistência de listas.

---

## 1. Gaps prioritários (resumo)

| # | Sev. | Gap | Onde no PRD |
|---|---|---|---|
| G1 | Alta | Rentabilidade "mensal por ativo, exceto RF" não exclui **Cripto**, mas o bloco cripto proíbe custo por ativo (sem custo não há XIRR por ativo). Idem FR-28 "rentabilidade por ativo, com destaque para o melhor". | FR-20, FR-28, Glossário "Rentabilidade" |
| G2 | Alta | Brief: impacto da reversão do ADR-011 no **gate m1 (poupança jun/2026 = 55,48%)** deveria ser tratado no PRD. O PRD resolve a fórmula (FR-32, receita do trabalho) mas não diz se o gate m1 continua válido, é recalibrado ou é substituído. | FR-32, §8 "Restrições herdadas" |
| G3 | Média | Critério de sucesso 2 do brief ("o **patrimônio** bate com as posições de origem — consolidado B3, carteiras") saiu das métricas: SM-2 cobre só o saldo Nubank; a conciliação ficou em FR-22 com tolerância indefinida. | §7 SM-2, FR-22 |
| G4 | Média | Critério 5 do brief ("**toda** transação nova chega categorizada por regra ou com sugestão; não há categorização linha a linha") virou SM-4 "a maioria", e FR-9 admite transação "sem regra nem sugestão". Métrica não testável e mais fraca. | §7 SM-4, FR-9 |
| G5 | Média | Flash: o PRD afirma "a Flash não fornece arquivo", mas o addendum do brief registra o arquivo `integralizacoes.json` (atualizado em 17/10) e cadência mensal da Flash. O memlog do PRD marca a decisão como "[proposta do PM, confirmar]" — ainda não confirmada. | Glossário "Fonte", FR-7, FR-33, §1 |

---

## 2. Regras de leitura do dinheiro ("Como o dinheiro é lido")

### 2.1 Resgate / receita
- **OK:** receita inclui resgates, em linha própria (Glossário, FR-15); pagador só para exibição
  (FR-15); gasto só consumo e investimento em linha própria (FR-16); ADR-011 revertido (§8).
- **Alterado pelo memlog do PRD (resolve pendência do brief):** taxa de poupança sobre a receita
  do trabalho (FR-32).
- **G2 (Alta)** — gate m1 55,48% não mencionado (ver tabela).
- **Média — escopo de "resgate" ampliado.** Brief: resgate = "caixinha ou RF". PRD: "caixinha,
  RF **ou corretora**". Venda em corretora transferida ao Nubank vira receita? Isso não foi
  decidido no brief e afeta receita, poupança e "realizado total" (que hoje é líquido). Confirmar.
- **Média — investimento bruto × líquido não explicitado.** O addendum do PRD (mapa brownfield)
  nota que o "investido" hoje é líquido de resgates e "muda com a regra". O PRD não diz que o
  "direcionado a investimentos" passa a ser **bruto** (saídas para investimento, sem abater
  resgates). Falta uma frase no Glossário/FR-16.
- **Baixa — caso de teste real omitido.** O brief indica o resgate da caixinha Turbo (R$ 4.994)
  que pagou o notebook (SETUP) e deixou a RF negativa em out/2026 como "caso de teste real". O
  PRD não o usa como critério de aceite (FR-15/FR-16/FR-32 ou FR-27: RF negativa no mês ×
  pendente da classe — a planilha inflava o pendente nesse caso).

### 2.2 Cripto em bloco
- **OK:** Glossário "Bloco cripto", FR-19, §5 "Inventar custo por ativo cripto".
- **G1 (Alta)** — FR-20/FR-28 pedem rentabilidade por ativo sem excluir cripto.

### 2.3 Objetivos primeiro
- **OK:** ordem objetivos → classes → ativos (FR-25); reserva = multiplicador × custos fixos
  (Glossário, FR-30); Snow Trip e objetivos livres (FR-30).
- **Alterado pelo memlog do PRD:** "custos fixos recorrentes" do brief = lista cadastrada em
  Ajustes (FR-17, suposição). Coerente com a nota do brief de que o PRD define a fronteira.
- **Baixa — Liberdade Financeira fora de lugar.** Brief/memlog: "Liberdade Financeira = 300×
  custos fica na área de estratégia (1MM)" → v2.1. O PRD põe o multiplicador da Liberdade em
  FR-30 (v2.0), mas nenhum FR da v2.0 exibe a Liberdade. Ou exibir (como no bloco "Custos
  recorrentes" da planilha) ou mover o multiplicador para a v2.1.

### 2.4 Modelos de aporte
| Decisão do brief | PRD | Estado |
|---|---|---|
| Classe = A (déficit) + B (bandas) + C (piso) | FR-25 passo 2, Glossário Banda/Piso | OK |
| Ativo = A (déficit) na v2.0 | FR-25 passo 3 | OK |
| G (inclinação por valuation) só na v2.1 | §6.2 (análise fundamentalista) | OK |
| E (glide path) e F (value averaging) na v2.1 | §6.2 (Estratégia 1MM) | OK |
| D não escolhido; H (risk parity) rejeitado; fórmula da planilha rejeitada | Não mencionado | Baixa — registrar como não-objetivo ou no addendum para a arquitetura não reabrir |
| Modelo **monotônico** (motivo da rejeição da fórmula da planilha) | Não exigido | Média — falta critério: "mais déficit nunca recebe menos aporte" |
| Modelo **substitui pesos e overrides manuais** da planilha (RF = 2,77, Médio Prazo = 300 fixo, ativos zerados) | Não dito; FR-26 permite ajuste manual mensal | Baixa — deixar claro que FR-26 é ajuste do mês, não override persistente |
| Objetivos antes da carteira de longo prazo | FR-25 passo 1 | OK |

Outros pontos de aportes:
- **Média — classe "Médio Prazo" sumiu.** O inventário da planilha lista Cripto, Ações, ETFs,
  FIIs, Renda Fixa, Aposentadoria e **Médio Prazo** (com override fixo de 300). O Glossário do
  PRD não tem Médio Prazo nem diz se ele vira objetivo. Também não diz em que classe ficam as
  debêntures Flash (FR-33).
- **Baixa — regra da banda incompleta.** FR-25 diz só que a classe acima da meta e fora da banda
  recebe o piso. Não cobre a classe acima da meta mas **dentro** da banda.

### 2.5 Rentabilidade
| Decisão do brief | PRD | Estado |
|---|---|---|
| Sempre XIRR, nunca (resultado − aplicado)/aplicado | FR-20 | OK |
| Nominal × real **por classe**, IPCA efetivo do período (BCB) | FR-20 (+ consolidado) | OK (fonte BCB fica para a arquitetura) |
| "Rendimento ponderado mensal" por ativo, exceto RF = **XIRR expresso em % ao mês** | FR-20 "mensal por ativo, exceto RF" | Média — "% ao mês" e o nome "ponderado mensal" (que o Vitor reconhece da planilha) não aparecem; o critério de aceite fica ambíguo (XIRR do mês × XIRR anualizado convertido para % a.m.) |
| Substitui o cálculo linear da planilha | Implícito (§5 "não reproduzir a planilha") | OK |
| Cripto sem rentabilidade por ativo | Não excluído | **G1** |

---

## 3. Critérios de sucesso

| Critério do brief | Métrica do PRD | Estado |
|---|---|---|
| 1. A planilha morre (30 dias, escopo v2.0; Fundamentos/1MM/Trade seguem na planilha até a v2.1) | SM-1 | OK; Baixa: o PRD não lista o que continua na planilha. UJ-2 cita "o quadro rumo ao R$ 1MM", que na v2.0 ainda vive na planilha — vale explicitar |
| 2. Saldo bate (Nubank CPF e MEI) **e patrimônio bate com a origem** | SM-2 (só saldo, ao centavo) | **G3** — metade patrimônio sem métrica |
| 3. Zero digitação de mercado; manual só sem fonte (ex.: Neobankless) | SM-3, FR-23 | OK; Baixa: FR-23 cita preços e dólar, mas não **saldo de carteira cripto** (só SM-3 e FR-22 citam) |
| 4. Base viva: "atualizado até" por fonte + aviso Nubank > 7 dias | FR-3 | OK, mas sem SM; ver §5 (cadência) |
| 5. Categorização assistida: **toda** nova por regra ou sugestão; nada linha a linha | SM-4 "a maioria" | **G4** |
| Gate principal: 30 dias sem a planilha **+** saldo batendo | SM-1 + SM-2 | OK |

---

## 4. Tom e qualidades (ideias qualitativas)

- **Média — "finanças cuidadas com carinho; o critério é praticidade, não minutos
  economizados".** O PRD §2 diz "cuida das finanças com atenção e quer praticidade". O "carinho"
  virou "atenção", e o princípio "praticidade > velocidade" não orienta nenhum requisito. A UJ-1
  ("fecha a semana em poucos cliques") puxa para a velocidade, e o memlog do brief decidiu "sem
  meta de tempo para o ritual". Sugestão: um princípio de produto em §2 ou §8.
- **Média — "dados úteis, práticos e fáceis de interpretar no dia a dia"** (memlog do brief:
  "Sucesso = confiável, dinâmico... dados práticos e fáceis de interpretar"). O PRD não tem
  NFR nem princípio de legibilidade (ex.: cada número com contexto e comparação, linguagem do
  Vitor, nada de tabela crua na primeira tela). Só o FR-13 ("data dos dados") e o FR-31 ("no
  máximo dois cliques") tocam nisso. A UX vai precisar desse norte.
- **OK — "planilha não é gabarito".** §5 "Reproduzir a planilha 'Rotina'" e FR-20 (IPCA
  efetivo, XIRR). Baixa: o PRD não lembra que a validação contra a planilha (ex.: gate m1, saldos
  históricos) deve tolerar as correções intencionais da v2. Isso é relevante para G2.
- **Baixa — problema = esforço e dados em dobro, não risco.** O brief diz que "nunca houve erro
  por dado desatualizado". O PRD não tem seção de problema. Sem isso, a contra-métrica SM-C2
  (volume de avisos) é a única proteção contra excesso de alarme. OK, mas vale citar.
- **Baixa — Visão.** O brief fala em "único lugar onde o Vitor olha e decide o próprio
  dinheiro", diferencial = "visão no tempo" (passado → presente → futuro), e na v2.1 "passa de
  registrar a orientar a estratégia"; "primeiro desktop, depois mobile". O PRD §1 guarda só a
  comparação com o passado.

---

## 5. Escopo v2.0

| Item do brief | PRD | Estado |
|---|---|---|
| Recuperar a base jun→out/2026: Nubank CPF/MEI, B3 **e Flash**; depois conciliar; primeiro teste do import | FR-7, §6.1 | Flash removida (memlog do PRD, ver **G5**); conciliação = fechamento com saldo (FR-5/FR-29) — OK |
| Hub: OFX Nubank CPF/MEI, xlsx B3 (3 tipos), **aportes da Flash**; prévia, dedup, "atualizado até" | FR-1..FR-3 | Flash removida (G5) |
| Categorias dinâmicas: grupo + sub, inbox, lote, regras reaplicáveis ao histórico | FR-8..FR-12 | OK. Baixa: "sugestão só com alta confiança" (padrão de mercado no addendum) não virou regra |
| Primeira tela: saldo, resultado, rentabilidade, custos fixos, **aporte feito e onde colocar o restante**, bandas, a categorizar, fontes velhas | FR-13 | Baixa: FR-13 mostra planejado/realizado/a caminho/pendente, mas não "onde colocar o restante" (a distribuição do pendente) |
| Caixa: transações, receitas por fonte, gastos por categoria, custos fixos pagos × pendentes, fatura = valor pago | FR-15..FR-18 | OK |
| Investimentos: posições e alocação classe → ativo, rentabilidade, cripto em bloco, conciliação | FR-19..FR-23 | OK (exceto G1) |
| Aportes: objetivos primeiro + rebalanceamento em 2 níveis | FR-24..FR-27 | OK (ver §2.4) |
| Histórico mês a mês: **saldo**, gastos por categoria, aportes, rentabilidade; "**qual mês foi melhor?**" | FR-28 | Baixa: "saldo do mês" não está na lista do FR-28; o destaque é para a melhor classe/ativo, não para o melhor **mês**. A ideia do brief de usar o consolidado mensal B3 como snapshot de fim de mês também não aparece (nem no addendum do PRD) |
| Ajustes: categorias, regras, custos fixos, contas, objetivos, metas, preços manuais | FR-30 | OK (+ bandas, pisos, multiplicadores) |
| 4 áreas, abas, imports em drawers, desktop-first | FR-31 | OK |

### Cadência por fonte (addendum do brief)
- Brief: Nubank > 7 dias = defasagem; B3 movimentação só quando houver compra; consolidado só
  com o mês fechado; Flash mensal; "investimentos toleram defasagem maior".
- PRD: FR-3 só define o limite do Nubank. O memlog do PRD decidiu que "imports devem cobrir o
  **mesmo período** em todas as fontes" (FR-4).
- **Média — tensão nova:** o consolidado B3 sempre fica um mês atrás e a movimentação B3 só
  existe quando há compra. Sem limites por fonte, o FR-4 pode gerar avisos permanentes. Isso
  contradiz "investimentos toleram defasagem maior" e a contra-métrica SM-C2. Falta definir a
  defasagem tolerada por fonte e quando uma B3 sem arquivo é "sem movimento" e não "lacuna".

---

## 6. v2.1 (roadmap) e "Fora"

### v2.1
| Brief | PRD §6.2 | Estado |
|---|---|---|
| Análise fundamentalista → habilita inclinação por valuation | Sim | OK |
| Estratégia 1MM: cenários, trajetória, value averaging, Liberdade Financeira | Sim | OK (ver Liberdade em §2.3) |
| Diário de Trade (day trade) | "Diário de Trade" | OK |
| Benchmarks carteira × CDI/IBOV/IPCA | Sim | OK |
| Deploy na nuvem "para o cron rodar sempre e o app ficar acessível" | "Deploy na nuvem" | OK (motivo omitido, Baixa) |
| Hermes (lançamentos pelo Discord) + alertas no Discord | Sim | OK; central de avisos in-app na v2.0 (memlog do PRD) é coerente |

- **Baixa — NFR × v2.1.** §8 "dados financeiros não saem do ambiente do Vitor" pode conflitar
  com o deploy em nuvem da v2.1 (e o banco já é Supabase em nuvem). Definir "ambiente do Vitor"
  (contas/infra dele, sem terceiros de analytics/IA?).

### Fora
| Brief | PRD | Estado |
|---|---|---|
| Por agora: Nubank automático (Meu Pluggy) | §6.3, §5 | OK |
| Por agora: detalhamento da fatura do cartão | §5 (não-objetivo), **ausente em §6.3** | Baixa — listas inconsistentes |
| Por agora: mobile, multiusuário | §6.3, §5 | OK |
| Sempre: executar transações/aportes/resgates | §1, §5 | OK |

---

## 7. Itens do brief alterados explicitamente pelo memlog do PRD (não são gaps)

- Flash deixa de ser fonte de arquivo → derivada do Nubank (FR-33) — **ainda marcada "confirmar"** (G5).
- Taxa de poupança sobre a receita do trabalho (resolve a pendência do brief).
- Custos fixos = lista cadastrada em Ajustes (suposição; brief delegou ao PRD).
- Central de avisos in-app na v2.0 (novo; Discord segue v2.1).
- Aporte planejado manual (não "o que sobrar"); orçamento = receitas − custos fixos − aporte − dívidas.
- Fechamento explícito de mês; jul/2024–mai/2026 fechados em bloco; jun–out/2026 abertos.
- Saldo bate ao centavo.

## 8. Ações sugeridas para o PRD

1. FR-20/FR-28/Glossário: "mensal por ativo, exceto RF e Cripto (bloco)"; expressar como XIRR
   em % ao mês ("rendimento ponderado mensal").
2. FR-32 ou §8: dizer o destino do gate m1 (55,48%): mantido na nova fórmula, recalibrado ou
   substituído.
3. §7: incluir uma métrica de patrimônio × origem (consolidado B3 e carteiras) ou elevar o FR-22.
4. SM-4: tornar testável e alinhado ao brief (toda transação nova chega com regra ou sugestão).
5. Confirmar com o Vitor a origem da Flash (`integralizacoes.json` × derivação do Nubank).
6. Acrescentar em §2/§8 os princípios de praticidade e de dados fáceis de interpretar.
7. FR-3/FR-4: defasagem tolerada por fonte (Nubank 7 d; B3 conforme compra; consolidado = mês
   fechado; investimentos mais tolerantes).
8. Glossário: Médio Prazo (classe ou objetivo?), classe das debêntures Flash, resgate de
   corretora, investimento bruto.
9. FR-25: exigir monotonicidade; registrar D/H/fórmula da planilha como rejeitados.
10. Usar o caso Turbo/notebook (out/2026) como critério de aceite de FR-15/FR-16/FR-27/FR-32.
