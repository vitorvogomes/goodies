---
title: "Product Brief: Goodies v2"
status: final
created: 2026-10-17
updated: 2026-10-17
---

# Product Brief: Goodies v2

> Pesquisa de mercado, inventário e fórmulas da planilha e notas para PRD/arquitetura:
> [`addendum.md`](addendum.md).

## Resumo executivo

O Goodies v2 substitui a planilha "Rotina" por um **painel de controle que se monta a partir dos
relatórios que o Vitor já baixa** (Nubank, B3, Flash). A v1 provou a coleta automática, mas não
virou rotina: a base parou em jun/2026 e a planilha voltou a ser a fonte de verdade.

A v2 tem um ritual semanal: importar, aprovar categorias em lote e ler o painel. Com ele, responde
às perguntas do mês e traz o histórico mês a mês que a planilha nunca teve.

**Sucesso:** 30 dias sem abrir a planilha, com o saldo do Goodies batendo com o das contas.

## O problema

Desde jul/2024 o Vitor controla as finanças numa planilha Google Sheets ("Rotina"). Gasta ~20 min,
3–4× por semana (mais de 1 h por semana), digitando à mão preços, saldos de carteiras cripto,
dólar e operações linha a linha.

O Goodies v1 automatizou a coleta (imports Nubank e B3, preços de mercado, scan de carteiras
cripto, XIRR), mas falhou em dois pontos:

1. **Não mostra o que o Vitor precisa.** Faltam o painel do mês, aportes planejado × realizado,
   custos fixos pagos × pendentes e a rentabilidade por classe. O que existe se espalha em ~16
   abas de tabelas soltas.
2. **Não virou rotina.** Importar os relatórios não é fácil o bastante para substituir a
   digitação. Os dados estavam coerentes até jun/2026, quando a base parou, embora os arquivos até
   out/2026 já estejam baixados. A planilha, mais familiar e completa, voltou a ser a fonte de
   verdade.

O custo hoje é **esforço e dados em dobro**, não decisões erradas: nunca houve erro por dado
desatualizado.

## A solução

Nenhum preço, saldo ou operação é digitado: tudo vem dos relatórios.

**Ritual semanal.** O Vitor arrasta para o **hub de import** o extrato do Nubank e, se houver
arquivos novos, os da B3 e da Flash. O app mostra o que entrou, sugere categoria para o que é
novo, e o Vitor aprova as sugestões em lote. Cada aprovação vira regra para os próximos imports.

**Primeira tela.** Logo após o ritual, ela responde às perguntas do mês antes de qualquer tabela:

- saldo do mês, resultado e rentabilidade dos investimentos;
- custos fixos vencendo ou atrasados;
- aporte do mês já feito e onde colocar o restante;
- classes fora da banda de alocação;
- transações a categorizar;
- fontes de dados desatualizadas (ex.: "B3 sem import há 15 dias").

**Organização.** Quatro áreas: **Visão geral**, **Caixa**, **Investimentos** e **Ajustes**. As
sub-telas viram abas, e os imports viram painéis laterais (drawers). A v2 é desktop-first.

## Como o dinheiro é lido

Estas são as regras para o PRD e a arquitetura. A planilha **não é gabarito**: a v2 corrige as
aproximações e os ajustes manuais dela, em vez de copiá-los.

- **Receita** é tudo que entra de fora, inclusive os **resgates** de caixinha ou RF. O painel
  mostra a composição: as fontes (Flash, Betuel, salário, extra) e, em linha própria, os
  resgates. A fonte é identificada pelo pagador só para exibição, nunca como regra de categoria.
  Esta regra reverte o ADR-011; o impacto no gate m1 (poupança = 55,48%) está no addendum.
- **Gasto** é só consumo. O valor **direcionado a investimentos** aparece em linha própria, nunca
  dentro de gastos.
- **Cripto** é um **bloco**: "quanto saiu × quanto vale". Nenhum custo por ativo cripto é
  inventado; por ativo, aparece só o valor atual, usado na alocação.
- **Objetivos primeiro.** A reserva de emergência (6 × custos fixos recorrentes), o Snow Trip e
  outros objetivos que o Vitor criar recebem o aporte antes da carteira de longo prazo.
- **Aportes.** Depois dos objetivos, a carteira é rebalanceada por déficit, sem vender, com bandas
  de tolerância e piso por classe. Dentro da classe, o critério também é o déficit; a inclinação
  por valuation entra quando chegar a análise fundamentalista (v2.1). Esse modelo substitui os
  pesos e os overrides manuais da planilha.
- **Rentabilidade** tem duas leituras, ambas por XIRR (nunca "(resultado − aplicado)/aplicado"):
  - **nominal × real por classe**, descontando o IPCA efetivo do período;
  - **rendimento ponderado mensal por ativo**, exceto RF, com o XIRR expresso em % ao mês.

## Critérios de sucesso

São finanças pessoais, cuidadas com carinho: o critério é **praticidade**, não minutos
economizados.

1. **A planilha morre.** 30 dias seguidos sem abrir a planilha "Rotina" para as tarefas do escopo
   v2.0. Fundamentos, Estratégia 1MM e Trade seguem nela até a v2.1.
2. **O saldo bate.** O saldo do Goodies é igual ao das contas Nubank (CPF e MEI), e o patrimônio
   bate com as posições de origem (consolidado B3, carteiras).
3. **Zero digitação de mercado.** Nenhum preço, saldo de carteira ou dólar é digitado. Lançamento
   manual só onde não há fonte (ex.: Neobankless).
4. **Base viva.** O painel mostra até quando cada fonte está atualizada e avisa quando o Nubank
   passa de 7 dias sem import.
5. **Categorização assistida.** Toda transação nova chega categorizada por regra ou com sugestão
   aprovável em lote; não há categorização linha a linha.

## Escopo

### v2.0: a planilha do dia a dia

- **Recuperar a base.** Importar os arquivos já baixados, do último dado no banco (jun/2026) até
  out/2026: Nubank CPF e MEI, B3 e Flash. Depois, conciliar. É o primeiro teste real do novo
  import.
- **Hub de import.** Recebe o OFX do Nubank (CPF e MEI), os xlsx da B3 (movimentação, negociação,
  consolidado) e os aportes da Flash. Tem prévia, deduplicação e "atualizado até" por fonte.
- **Categorias dinâmicas.** Grupos e subcategorias editáveis no painel. Uma inbox de sugestões
  com aprovação em lote; cada aprovação cria regras reaplicáveis ao histórico.
- **Visão geral.** O painel do mês, com os destaques de "Primeira tela".
- **Caixa.** Transações, receitas por fonte, gastos por categoria, custos fixos pagos × pendentes.
  A fatura do cartão entra só como valor pago.
- **Investimentos.** Posições e alocação (classe → ativo), rentabilidade, cripto em bloco e
  conciliação com as posições de origem, conforme "Como o dinheiro é lido".
- **Aportes.** Objetivos primeiro e rebalanceamento em dois níveis.
- **Histórico mês a mês.** Saldo, gastos por categoria, aportes e rentabilidade comparáveis entre
  meses ("qual mês foi melhor?").
- **Ajustes.** Categorias e regras, custos fixos, contas, objetivos, metas de alocação e preços
  manuais (só onde não há fonte).

### v2.1: estratégia e nuvem

- Análise fundamentalista (fundos e ações), que habilita a inclinação por valuation nos aportes.
- Estratégia 1MM: cenários, metas por trajetória, value averaging e Liberdade Financeira.
- Diário de Trade (day trade).
- Benchmarks: carteira × CDI, IBOV e IPCA.
- Deploy na nuvem, para o cron rodar sempre e o app ficar acessível.
- Hermes (lançamentos pelo Discord) e alertas no Discord.

### Fora

- **Por agora:** Nubank automático (Open Finance / Meu Pluggy), detalhamento da fatura do cartão,
  mobile, multiusuário.
- **Sempre:** executar transações, aportes ou resgates. O Goodies informa e sugere; a execução nas
  instituições é do Vitor.

## Visão

O Goodies vira o **único lugar onde o Vitor olha e decide o próprio dinheiro**. O diferencial é a
**visão no tempo**: analisar o passado (meses comparáveis, tendências) para executar certo no
presente e colher no futuro. Com a v2.1, o app passa de registrar a **orientar a estratégia**:
trajetória para o R$ 1MM e a Liberdade Financeira, benchmarks, análise de ativos e operação
contínua na nuvem. Primeiro desktop, depois mobile.
