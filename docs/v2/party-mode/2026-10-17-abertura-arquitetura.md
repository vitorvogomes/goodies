---
title: "Party mode — abertura da arquitetura do Goodies v2"
date: 2026-10-17
participants: John (PM), Winston (arquiteto), Sally (UX), Amelia (dev), Mary (analista)
status: decisões aprovadas pelo Vitor
---

# Abertura da arquitetura — decisões

Insumo para o `bmad-architecture`. Todas as decisões abaixo foram aprovadas pelo Vitor em
2026-10-17. Elas fecham as suposições pendentes do PRD (Q1, FR-26, FR-29) e da UX (consumido,
consumo financiado por resgate, séries dos gráficos).

## 1. Mês fechado (FR-32, FR-33, FR-34)

- **Uma função só:** `build_month_summary(mês)` calcula tanto a leitura ao vivo quanto a
  congelada. Fechar = gravar o resultado. Teste-gabarito: jun/2026 = 55,48%.
- **Armazenamento:**
  - `month_closes` guarda mês, status, versão e `fechado_em`.
  - Os totais (receita, consumido, aporte, patrimônio, poupança) ficam em colunas tipadas.
  - O que tem dimensão (categoria, classe, ativo) fica em linhas longas
    `(mês, versão, métrica, dimensão, valor)`, que servem às séries do FR-34.
- **Versões:**
  - Reabrir e fechar de novo cria uma nova versão; as anteriores ficam guardadas para auditoria.
  - Só a última versão aparece na tela.
  - O seletor de período navega por qualquer mês: fechado = congelado, aberto = ao vivo.
- **Ajuste em mês fechado:** o aviso mostra a diferença ao vivo − congelado ("se reabrir, Lazer
  passa de R$ 812 para R$ 870").
- **Fechamento retroativo:**
  - O assistente de recuperação (FR-7) fecha os meses recuperados (jun–set/2026, e antes se houver
    consolidado).
  - O patrimônio vem do **consolidado mensal da B3**. A cripto é marcada "estimada".
  - O fechamento grava a cobertura por fonte, no mesmo padrão de proveniência do import.
  - Isso amplia o histórico de patrimônio e rentabilidade do FR-34, que antes começava no
    primeiro fechamento ao vivo.

## 2. Objetivos e aporte (Q1, FR-29)

- **O objetivo é dono de um ou mais ativos** (caixinhas). O OFX do Nubank traz o nome da caixinha
  na descrição ("Caixinha SnowTrip", "Caixinha Reserva"), então o vínculo sai do import.
- **Progresso = saldo atual dos ativos** (com o rendimento do CDI real), com o **aportado** ao lado.
  Todo aporte para o ativo do objetivo conta como aporte do objetivo naquele mês.
- **Um ativo vinculado a objetivo sai da base da alocação.** Ele continua no patrimônio e aparece
  num bloco "Objetivos" em Posições, separado das classes. A alocação filtra `goal_id IS NULL`.
  Sem isso, o dinheiro da viagem infla a classe RF e distorce o déficit.
- **Caixinha Turbo e Caixinha Extra** fazem parte da carteira de longo prazo (classe RF).
- **Rateio (passo 1 do FR-29):**
  - Cada objetivo tem uma **necessidade do mês** = o que falta ÷ meses até o prazo.
  - O passo 1 entrega só a necessidade do mês, não tudo o que falta.
  - Se o aporte não cobrir todas as necessidades, divide em proporção a elas.
- **Reserva de emergência:**
  - Horizonte editável, padrão de **12 meses**.
  - **Prioridade sempre até encher:** a necessidade dela é atendida antes da dos outros objetivos.
- Exibição: "Snow Trip · R$ 350/mês para chegar em jul/2027".

## 3. Categorias em dois níveis (FR-8 a FR-12)

**Estado atual:** `transactions.category` e `fixed_costs.category` são texto, sem FK. São 1.454
transações em 33 categorias, sem nenhuma órfã. Os padrões ficam em `categories.match_patterns`.

**Migração:**
1. Criar `category_groups`, com o **tipo de movimento no grupo**. A subcategoria herda o tipo.
2. Adicionar `categories.group_id`.
3. Adicionar `transactions.category_id` e `fixed_costs.category_id`, preenchidos por join pelo
   nome. A coluna de texto fica por uma versão e depois é removida.
4. Mover `match_patterns` para `category_rules`, com origem "legado". A regra mais específica vence.
5. Preencher `transactions.category_source`: "regra" se um padrão atual bate com a descrição;
   senão, **"manual"**. O que é manual nunca é sobrescrito (FR-11), o que protege a curadoria.
6. Corrigir o nome "Cripto Nubnak" para "Cripto Nubank".

**Grupos iniciais aprovados** (editáveis no app):

| Tipo | Grupo | Subcategorias |
|---|---|---|
| Gasto | Casa | Moradia, Assinaturas, Setup |
| Gasto | Alimentação | Comida Fora, Alimentação |
| Gasto | Transporte | Transporte, Carro, PitBike |
| Gasto | Lazer | Viagem, Lazer, Esportes, Ganja |
| Gasto | Saúde e educação | Saúde, Educação |
| Gasto | Obrigações | Impostos, Dívidas |
| Gasto | Outros | Emergência, outros, **Cartão de crédito** *(nova)* |
| Receita | Trabalho | **Recorrente**, **Extra** |
| Receita | Resgates *(novo)* | por destino (FR-19) |
| Receita | **Devoluções** | Repasse, Reembolso |
| Investimento | Investimentos | Caixinha/RDB, Toro (B3), Tesouro, Renda Fixa Nubank, Cripto Nubank, Cripto Diversos, Binance, Debêntures Flash, Liquid/DeFi |
| Transferência | Transferências | Transferência interna |

**Detalhes do grupo Trabalho:**
- O **pagador é um campo** da transação, não uma categoria. Ele é extraído do nome no Pix ou do
  CNPJ.
- O preenchimento inicial usa as subcategorias atuais como semente: Flash Capital e Betuel viram
  Recorrente, com o pagador preenchido.

**Reclassificações na migração** (junto com a reclassificação dos resgates do FR-19, antes dos
fechamentos retroativos):
- As 18 transações "Pagamento de fatura" em Dívidas (2024–nov/2025, ~R$ 9,5 mil) eram **fatura
  normal** e vão para **Cartão de crédito**. O tipo continua gasto, então a poupança não muda.
- As 4 faturas em Assinaturas (abr–mai/2026) ficam onde estão, porque foram curadoria manual.
- Repasse sai do grupo Trabalho e vai para **Devoluções**. Repasse é racha de conta: Pix de amigos
  devolvendo a parte deles. O gate de jun/2026 não muda, porque não houve repasse naquele mês.

## 4. Termos de dinheiro (fecha as suposições da UX)

- **Consumido** = gastos − custos fixos casados − **devoluções** − transações em **Dívidas**.
  - Os gastos por categoria seguem **brutos**, com uma linha "− Devoluções" no rodapé de
    Consumido por grupo.
  - Investimento nunca é gasto.
- **Dívidas do mês:**
  - É um campo manual, padrão R$ 0,00.
  - Nos meses fechados retroativamente, vem pré-preenchido com a soma das transações em Dívidas
    daquele mês.
  - A transação em Dívidas não entra no consumido, porque já foi descontada no orçamento.
- **Consumo financiado por resgate:**
  - Disponível sem resgates = trabalho − fixos − aporte − dívidas.
  - Financiado = mín(resgates, máx(0, consumido − disponível sem resgates)).
  - No mock: R$ 2.994,77, e não o resgate inteiro de R$ 4.487,99. Os testes cobrem o caso zero e o
    caso em que o resgate cobre tudo.
  - Duas linhas:
    - **"financiado por objetivo"** (ex.: resgate da caixinha Snow Trip), em tom neutro: é o plano
      funcionando;
    - **"financiado por resgate da carteira"**, em laranja.

## 5. Conciliação (FR-5, FR-25, FR-26)

| O que se confere | Contra o quê | Tolerância |
|---|---|---|
| Saldo Nubank CPF e MEI | saldo do OFX | R$ 0,00 (exato) |
| Posições B3 (ações, FII, ETF, BDR) | consolidado mensal | quantidade exata; valor só informativo |
| Tesouro | consolidado mensal | 0,01 título |
| Caixa em corretora | conferência do relatório | R$ 1,00 |
| Cripto | o próprio scan | sem divergência; aviso de idade do scan acima de 14 h |
| Caixinhas e debêntures | não há origem mensal | não conciliam; marcadas "valor calculado (CDI real)" |

A conferência é por quantidade, não por valor, porque o preço do consolidado é de outra data. Isso
evita avisos falsos (SM-C2).

## 6. Gráficos (fecha `[ASSUMPTION]` do DESIGN › Colors)

| Gráfico | chart-1 (verde) | chart-2 (neutro médio) | chart-3 (neutro claro) |
|---|---|---|---|
| Patrimônio | patrimônio | — | aplicado |
| Gastos por categoria *(ver nota)* | — | período | anterior; média 12m como marcador |
| Aporte | realizado | planejado | média 12m |

> **Nota (arquitetura, 2026-10-18):** o EXPERIENCE define o segundo gráfico como "gastos por categoria",
> não "receitas × consumido"; o mapeamento acima segue o EXPERIENCE.

## 7. Fica para depois

Os pontos da v2.1 serão discutidos de novo depois da arquitetura: deploy na nuvem, estratégia 1MM,
benchmarks e Hermes.
