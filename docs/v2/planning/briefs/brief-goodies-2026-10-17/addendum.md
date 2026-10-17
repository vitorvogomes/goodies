---
title: "Addendum — Product Brief Goodies v2"
created: 2026-10-17
updated: 2026-10-17
---

# Addendum — Goodies v2

> Referência de apoio ao [brief](brief.md). "Notas" registra decisões e pendências para PRD e
> arquitetura; as demais seções são evidência (mercado, inventário e fórmulas da planilha).

## Notas para o PRD e a arquitetura

- **Reversão do ADR-011 (decidida).** O resgate de caixinha/RF conta como receita, exibido em
  linha própria na composição. O Goodies v1 tratava resgate como `investment` líquido, e o gate m1
  (poupança jun/2026 = 55,48%) foi calibrado nessa semântica. **Em aberto para o PRD/arquitetura:**
  como a taxa de poupança trata os resgates (incluí-los ou calcular sobre a receita do trabalho),
  sem perder a leitura correta de consumo × investimento.
- **Investimento não é gasto:** o total "direcionado a investimentos" substitui a linha
  INVESTIMENTOS do controle de gastos da planilha.
- **Modelos de aporte considerados:**

  | Modelo | Papel na v2 |
  |---|---|
  | A. Preencher déficit | Base, nos níveis classe e ativo |
  | B. Bandas de tolerância | Nível classe |
  | C. Piso por classe | Nível classe; substitui overrides fixos |
  | D. Peso exponencial | Alternativa suave ao A, não escolhida |
  | E. Metas por trajetória (glide path) | v2.1, ligado à Estratégia 1MM |
  | F. Value averaging | v2.1, quanto aportar para seguir a trajetória |
  | G. Inclinação por valuation | Nível ativo; entra na v2.1, com a análise fundamentalista (na v2.0, só déficit) |
  | H. Risk parity | Rejeitado: o perfil é de metas estratégicas, não de risco, e exige histórico de volatilidade |
  | Fórmula da planilha | Rejeitada: não é monotônica e depende de overrides (ver "Lógica real da planilha") |

  Antes do modelo, vem "objetivos primeiro": reserva = 6 × custos fixos, Snow Trip e objetivos
  criados pelo Vitor.
- **Cadência por fonte:**
  - Nubank: diário/semanal; mais de 7 dias já é defasagem.
  - B3 movimentação: no dia, quando houver compra.
  - B3 consolidado: mês fechado.
  - Flash: mensal.
  - Investimentos toleram defasagem maior.
- **Recuperar a base (estado em 2026-10-17):** o banco vai até 06/06/2026; `files/` tem:
  - Nubank CPF até 16/10;
  - Nubank MEI (no banco: conta `Nubank_CNPJ`), com 44 transações de jan a 16/out/2026 (o import
    deduplica o que já existe até jun);
  - B3 movimentação até 16/10;
  - consolidado até setembro;
  - Flash `integralizacoes.json` atualizado em 17/10.

  Caso de teste real: em out/2026, o resgate da caixinha Turbo (R$ 4.994) pagou o notebook
  (categoria SETUP) e deixou a RF negativa no mês.
- **Alternativas de ingestão descartadas por agora:** Nubank automático via "Meu Pluggy" (ver
  "Panorama") e detalhamento da fatura do cartão (usado só
  em assinaturas; basta o valor pago).
- **Histórico mês a mês:** o consolidado mensal da B3 pode servir de snapshot de posição e preço
  no fim de cada mês, para comparar rentabilidade entre meses.
- **Base de custos.** Reserva (6×) e Liberdade (300×) usam os **custos fixos recorrentes**
  cadastrados em Ajustes. A planilha separa as categorias CUSTOS FIXOS e RECORRENTE; o PRD define
  a fronteira.
- **Método de rentabilidade.** As duas leituras usam XIRR (CLAUDE.md): nominal × real por classe,
  com o IPCA efetivo do BCB, e o XIRR por ativo expresso em % ao mês. Esse "ponderado mensal"
  substitui o cálculo linear da planilha.

## Panorama de mercado (pesquisa 2026-10-17)

**Padrões que valem copiar.** Inbox de revisão com contador e lote; "criar regra?" a partir da
correção, com prévia e aplicação retroativa; regras com prioridade/estágios (normalizar payee →
categorizar); sugestão só com alta confiança; grupos + subcategorias com orçado × realizado;
navegação curta.

**BR.** Mobills/Organizze usam Open Finance via agregador (Belvo) + ML; reviews: categorização
erra e exige revisão periódica; navegação clássica em 5–6 seções. Pierre (CloudWalk, 2025): chat +
agentes temáticos, poucas telas, análise rasa. Kinvo/Investidor10/Status Invest: "Conexão B3"
(licenciada a instituições) — sync manual, queixas de quantidades erradas; Status Invest (set/2025)
consolidou tudo em página única com abas.

**Internacional.** Copilot Money: fila "To Review" no dashboard (meta: zerar), ML pessoal após
~30 revisões, sugestão só com alta confiança (se errar, oferece as duas melhores opções), regras de nome com prévia das
afetadas. Monarch: flag "needs review" + regras if-then + card no dashboard. Actual Budget
(self-hosted): regras em estágios pre/default/post, criadas automaticamente ao categorizar,
"Apply actions" retroativo; sync Pluggy para bancos BR. Firefly III: regras trigger→action
reaplicáveis a períodos passados.

**Acesso programático (pessoa física).** APIs da Área do Investidor B3 e Open Finance/Open
Investment só para instituições → **xlsx manual da B3 segue sendo o caminho realista**. Pluggy é
B2B (~R$ 2,5 mil/mês, segundo relato no TabNews), mas existe o **"Meu Pluggy"** (uso pessoal gratuito com client id/secret
+ item id; conectar/alterar contas só no trial) — já usado pela integração do Actual.

Fontes: actualbudget.org/docs/budgeting/rules · actualbudget.org/docs/advanced/bank-sync/pluggyai ·
monarch.com/transaction-review · changelog.copilot.money/log/transaction-category-rules ·
docs.firefly-iii.org (rules) · b3.com.br (integrações da Área do Investidor) ·
statusinvest.com.br/noticias/status-invest-nova-area-logada · tabnews.com.br (custos Pluggy/Belvo).

## Inventário da planilha "Rotina" (prints do Vitor, 2026-10-17)

Blocos do **painel de controle** que a primeira tela da v2 deve substituir:

1. **Gestão Qualificada (resumo de ativos).** Por classe (Cripto, Ações, ETFs, FIIs, Renda Fixa,
   Aposentadoria, Médio Prazo): %carteira × %projetada, aporte do mês × aporte médio, valor
   aplicado, resultado, %variação. Topo: data inicial (16/07/2024), meses/semanas, média mensal e
   semanal de aporte, saldo, rentabilidade real e nominal, projeção RF × RV.
2. **Resumo mensal.** Caixa, receita, gasto, saldo do mês.
3. **Custos recorrentes.** Item, valor, dia de vencimento, marcação pago/pendente; total;
   **Reserva = total × 6** e **Liberdade = total × 300**.
4. **Controle de receitas.** Por fonte (Flash, Betuel, Salário, Extra) com %; total − recorrentes
   − dívidas → **projeção de investimento do mês (valor-alvo, ex.: R$ 4.500)** e sobra do mês.
5. **Modelo de aportes.** Por classe: %atual × %meta → peso → aporte sugerido (proporcional ao
   peso sobre o valor-alvo), realizado no mês, pendente.
6. **Controle de gastos.** Total por categoria e % (SETUP, CUSTOS FIXOS, INVESTIMENTOS, VESTUÁRIO,
   GASOLINA, COMIDA FORA, ESPORTES).
7. **Rendimento ponderado mensal por ativo** (exceto RF): aplicado, resultado, variação,
   %carteira, %planejado × %atual por classe, prazo ponderado em meses, %ponderado mensal.

Outras abas:
- **Desempenho carteira:** por ativo com setor/descrição, preço médio, cotas, %atual × %meta
  **dentro da classe**, peso e aporte sugerido por ativo (rebalanceamento em 2 níveis).
- **Carteira cripto:** por carteira (TrustWallet, Phantom, Rabby, Binance, KuCoin, Cartão) com
  qtd, aplicado e resultado em USD; balanço geral com preço médio, %aplicada × %atual ×
  %projetada, alvo e "previsão médio futuro"; DeFi (hyUSD, sUSDai PT com vencimento).
- **Lançamento de operações:** log manual (data, corretora, tipo, categoria, ativo, operação,
  montante, preço, taxas, par de negociação, prazo ponderado) — B3, Nu Invest (Tesouro e
  reservas), FlashCapital (debênture), Binance/Liquid/Cartão (depósitos cripto com taxa).
- **Fluxo de caixa do mês:** extrato com categoria e saldo corrente; resgate de caixinha
  lançado como EXTRA (receita).
- **Análise de fundos / ações:** fundamentos (P/VP, DY, liquidez, ROE, margens, dívida/EBIT,
  CAGR, valor intrínseco de Graham) e checklist qualitativo.
- **Estratégia 1MM:** 10 anos × 3 cenários (inicial/intermediário/arrojado) com aporte anual e
  marco estratégico por ano.
- **Extrato trader:** day trade em mini-índice/mini-dólar (WIN/WDO): resultado, corretagem,
  IRRF, saldo líquido, meta diária.

## Lógica real da planilha (fórmulas lidas do .xlsx exportado, 2026-10-17)

- **Peso de aporte (classe, ativo e cripto):** `Δ = %Atual − %Meta`;
  `Peso = MAX(0, 1 − |Δ|·(10 + 100·Δ))`; aporte = Peso/ΣPesos × valor-alvo (R$ 4.500).
  ⚠ **Não é monotônico:** abaixo da meta o peso cai até ~0,75 (Δ=−5pp), volta a 1 em −10pp e
  passa de 1 depois disso; acima da meta zera em ~+6,2pp. Há overrides manuais (RF = 2,77;
  alguns ativos zerados; Médio Prazo = 300 fixo).
- **Realizado no mês:** SUMIFS de OPERAÇÕES por classe, com regras que variam por classe (cripto
  = depósitos; ações sem vendas; RF inclui resgates negativos → o pendente infla).
  Pendente = MAX(0, aporte − realizado). Aporte por ativo = peso do ativo × pendente da classe.
- **Rentabilidade:** nominal = (resultado − aplicado)/aplicado, acumulada e simples; real =
  (1+nominal)/(1+4,4%) − 1 com IPCA fixo digitado. "%Pond. Mensal" = variação simples ÷ idade
  média ponderada **por quantidade** (meses) — linear, não XIRR.
- **Receitas:** Proj. Mês = receita − recorrentes − dívidas − valor-alvo de investimento.
  "Receita do mês" soma inclusive a linha SALDO ANTERIOR.
- **Gastos:** pivot de todos os débitos por categoria; **inclui INVESTIMENTOS**. Categorias usadas: CUSTOS FIXOS, INVESTIMENTOS,
  GASOLINA, COMIDA FORA, GANJA, RECORRENTE, ESPORTES, LAZER, EXTRA, VIVÊNCIAS, DÍVIDAS,
  EMERGÊNCIA, SETUP, CARRO, DIA A DIA, VESTUÁRIO, CAIXA, BANCOS, RESGATE (+ PITBIKE,
  CONHECIMENTO em 2025).
- **Cripto:** qtd/aplicado em USD via OPERAÇÕES por ativo+carteira; resultado e preços
  **digitados**; dólar digitado; aplicado em BRL fixo (retorno −1,4% em USD × −15,4% em BRL).
  Previsão de preço médio futuro = PM após comprar a "balança" (quantidade que falta até a
  meta) ao preço de mercado.
- **Trade (day trade WIN/WDO):** corretagem = nº ops × 0,50; IRRF 1%; meta diária; imposto
  20% por gross-up.
- **Outros achados:** preços de mercado todos digitados; proventos de FII quase não separados;
  bugs pontuais de fórmula (prazo de DeFi/USDT, Aposentadoria fora do total).
