---
title: "PRD: Goodies v2"
status: final
created: 2026-10-17
updated: 2026-10-18
---

# PRD: Goodies v2

## 0. Propósito do documento

Este PRD transforma o [brief do Goodies v2](../../briefs/brief-goodies-2026-10-17/brief.md) em
requisitos testáveis para UX, arquitetura e épicos/stories.

- Detalha a **v2.0** em marcos (§6.1); a **v2.1** é só roadmap.
- Os termos do Glossário (§3) são usados de forma exata.
- Os FRs têm numeração global.
- As suposições ficam inline como `[SUPOSIÇÃO]` e indexadas em §10.
- Decisões caras dizem do que **abrem mão**.

O contexto técnico (mapa brownfield e notas para a arquitetura) fica em
[`addendum.md`](addendum.md). Este PRD descreve capacidades, não implementação.

## 1. Visão

O Goodies v2 substitui a planilha "Rotina" por um **painel de controle que se monta a partir dos
relatórios que o Vitor já baixa** (Nubank e B3). Não há preço, saldo ou operação para digitar.

Num ritual semanal (importar, revisar as transações em lote, ler o painel), o Vitor sabe como está
o mês, quanto e onde aportar e o que pede ação. Mês a mês, também consegue comparar o passado,
coisa que a planilha nunca fez.

O Goodies informa e sugere, mas **nunca executa** transações, aportes ou resgates.

### 1.1 Princípios

- **Praticidade acima de tudo.** São finanças pessoais, cuidadas com carinho, não uma corrida: o
  ritual é fácil, não cronometrado.
- **Dados úteis e fáceis de interpretar.** Todo número responde a uma pergunta do dia a dia e
  mostra a data dos dados que o geraram.
- **A planilha não é gabarito.** A v2 corrige as aproximações e os ajustes manuais da planilha, em
  vez de copiá-los.
- **Relatório é a fonte de verdade.** O que foi executado só é conhecido pelo relatório importado.

## 2. Usuário

Usuário único: o Vitor, investidor experiente. Uso em desktop.

### 2.1 Jornadas

- **UJ-1. Vitor fecha a semana em poucos cliques.**
  - **Contexto:** sábado de manhã, com o extrato do Nubank baixado (e o da B3, se houve compra).
  - **Caminho:**
    1. Vitor abre o app no **painel principal**, que mostra o resultado do mês, o patrimônio e a
       rentabilidade, com a data do último import.
    2. Abre o hub de import e escolhe os arquivos.
    3. A prévia mostra o que é novo e o que já existia.
    4. Na **revisão de transações**, ele vê todas as novas, já preenchidas por **regra** ou
       **sugestão**, corrige as erradas e confirma o lote. Ao corrigir, o app oferece criar uma
       regra.
  - **Clímax:** o **saldo da conta** bate com o do Nubank, e as posições batem com a origem
    (consolidado B3 e carteiras cripto).
  - **Tropeços:** arquivo repetido, lacuna, saldo divergente e fonte desatualizada viram **avisos**
    na **central de avisos**, cada um com a ação a tomar.
- **UJ-2. Vitor planeja e acompanha o aporte do mês.**
  - **Planejamento:** no início do mês, Vitor define o **aporte planejado**, guiado pelo seu quadro de
    estratégia rumo ao R$ 1MM (na planilha até a v2.1). O app calcula o **disponível para consumo** e sugere a **distribuição do
    aporte** (objetivos, depois classes, depois ativos).
  - **Ajuste:** Vitor muda qualquer valor e o restante é redistribuído na hora.
  - **Execução:** ele compra na corretora em qualquer data do mês.
  - **Acompanhamento:** os imports seguintes mostram o **realizado**, o que está **a caminho** e o
    **pendente**, que vale até o fim do mês.
  - `[SUPOSIÇÃO: distribuição exibida com classes primeiro e expansão para ativos; decisão de UX]`
- **UJ-3. Vitor olha para trás.** No fim do mês, compara o período com o anterior e com a média.
  Responde:
  - gastei mais ou menos, e em quê?
  - quanto do planejado aportei?
  - quanto o patrimônio cresceu, e quanto disso foi aporte e quanto foi resultado?
  - qual classe ou ativo rendeu melhor?

  Depois de conferir, ele **fecha o mês**.
- **UJ-4. Vitor ajusta o sistema.** Ele cria, renomeia e arquiva **categorias**, edita **regras**,
  **custos fixos**, **objetivos**, **debêntures**, **metas de alocação**, **bandas** e **pisos**,
  sem mexer em código.
- **UJ-5. Vitor recupera a base.** Uma única vez, importa os arquivos de jun a out/2026 já
  baixados, revisa as transações e fecha cada mês depois de conferir o saldo.

## 3. Glossário

Os termos abaixo e o FR-29 (objetivos primeiro) incorporam as regras de leitura do dinheiro do
brief. Elas foram decididas pelo Vitor e não estão em aberto.

**Dados e import**

- **Fonte** — origem de dados importada por arquivo:
  - Nubank conta CPF (OFX);
  - Nubank conta MEI (OFX);
  - B3 movimentação;
  - B3 negociação;
  - B3 consolidado mensal.

  Preços de mercado, scan de carteiras cripto e índices (CDI, IPCA) chegam automaticamente, sem
  arquivo.
- **Atualizado até** — a última data coberta pelos arquivos já importados de uma fonte.
- **Lote de import** — conjunto de registros de um ou mais arquivos importados juntos, com prévia
  e confirmação.
- **Lacuna** — intervalo de datas não coberto por nenhum arquivo importado de uma fonte, entre o
  primeiro e o último import.

**Caixa**

- **Transação** — movimento numa conta Nubank, com data, valor, descrição, **categoria**, **tipo
  de movimento** e **pagador** (quando houver).
- **Tipo de movimento** — receita, gasto, investimento ou transferência. **Gasto** é só consumo;
  **investimento** é o dinheiro direcionado a investimentos.
- **Resgate** — dinheiro que volta de caixinha, RF, corretora ou carteira/exchange cripto para a conta
  Nubank. É receita e é exibido em linha própria.
- **Receita** — tudo que entra de fora, inclusive os resgates.
- **Receita do trabalho** — receita sem os resgates e sem as devoluções (role `work_income`). É a base da
  taxa de poupança.
- **Pagador** — quem enviou uma receita (ex.: Flash, Betuel). Serve só para exibição.
- **Categoria** — classificação em dois níveis: **grupo** > **subcategoria**. Pode ser
  **arquivada**: some das sugestões e mantém o histórico.
- **Regra** — condição sobre a transação (ex.: descrição contém um texto) que atribui uma
  categoria. A regra mais específica vence.
- **Sugestão** — categoria proposta para uma transação sem regra. Nunca é aplicada sem
  confirmação.
- **Revisão de transações** — lista das transações novas de um lote, com checks, para confirmar ou
  corrigir a categoria em lote.
- **Saldo da conta** — dinheiro numa conta Nubank numa data. Tem duas leituras: **calculado**
  (pelo app, a partir das transações) e **informado** (no OFX).
- **Resultado do mês** — receitas − gastos − investimento do mês.
- **Custo fixo** — despesa recorrente cadastrada em Ajustes, com valor e dia de vencimento. Em cada
  mês está **pago** ou **pendente**. A soma dos custos fixos é a base do orçamento e da reserva de
  emergência.
- **Orçamento do mês** — receita do trabalho + resgates − custos fixos − aporte planejado − dívidas
  do mês = **disponível para consumo**.
- **Dívidas do mês** — valor do orçamento do mês, pré-preenchido com as transações em Dívidas não
  casadas a custo fixo; o Vitor pode sobrescrever. Pode ser zero.

**Investimentos**

- **Classe** — Ações Nacionais, ETFs, FIIs, Renda Fixa, Aposentadoria e Cripto. A antiga classe
  "Médio Prazo" da planilha vira o objetivo Snow Trip.
- **Ativo** — item investido dentro de uma classe (ex.: BBAS3, IPCA+ 2032, caixinha Turbo).
- **Debênture** — ativo de Renda Fixa cadastrado no app com emissor, taxa, data de início e
  vencimento (ex.: debêntures Flash, prefixado 24% a.a.).
- **Aplicado** — dinheiro líquido investido num ativo ou classe.
- **Valor atual** — posição × preço atual.
- **Resultado (do investimento)** — valor atual − aplicado.
- **Proventos** — dividendos, rendimentos de FII e juros recebidos.
- **Bloco cripto** — a classe Cripto como uma unidade: "quanto saiu × quanto vale". Nunca tem custo
  ou rentabilidade por ativo; por ativo, só o valor atual.
- **Rentabilidade** — retorno calculado por XIRR, nunca por "(resultado − aplicado)/aplicado".
- **Caixa em corretora** — dinheiro na corretora que ainda não virou ativo, confirmado por um
  relatório que cobre a data da transferência.
- **A caminho** — dinheiro que saiu do Nubank para uma corretora cujo **atualizado até** é
  anterior à data da transferência.
- **Patrimônio** — valor atual das posições + bloco cripto + caixa em corretora + saldo das contas.

**Aportes**

- **Meta de alocação** — percentual-alvo de uma classe na carteira, ou de um ativo na classe.
- **Banda** — tolerância em pontos percentuais em torno da meta de alocação.
- **Piso** — aporte mínimo que uma classe recebe todo mês.
- **Objetivo** — meta de poupança com nome, valor-alvo e prazo (ex.: Snow Trip). O progresso é o
  valor atual dos ativos vinculados a ele, com o aportado (aportes − resgates) ao lado. A **reserva de emergência** é um
  objetivo cujo valor-alvo é 6 × custos fixos (multiplicador editável).
- **Aporte planejado** — valor total que o Vitor decide aportar no mês.
- **Distribuição do aporte** — sugestão de quanto vai para cada objetivo, classe e ativo.
- **Realizado** — o que já foi aportado no mês. No **total**, conta quando o dinheiro sai do Nubank
  para investimento; **por classe e por ativo**, quando vira ativo.
- **Pendente** — planejado (ou distribuído) − realizado, até o fim do mês.

**Painel e histórico**

- **Painel principal** — a tela inicial da área Visão geral.
- **Aviso** — item da **central de avisos** que pede ação. Tem tipo, mensagem e ação sugerida.
- **Mês aberto / mês fechado** — um mês fechado tem o **resumo do mês** congelado. Pode ser
  reaberto.
- **Resumo do mês** — o conjunto de números congelado no fechamento (FR-32).

## 4. Funcionalidades

### 4.1 Hub de import

Realiza UJ-1 e UJ-5.

#### FR-1: Importar arquivos de qualquer fonte num só lugar
O Vitor importa num mesmo fluxo arquivos de qualquer **fonte**, e o app identifica a fonte de cada
um. Preços, scan de carteiras e índices chegam automaticamente, por fora do hub.
- Um arquivo de formato desconhecido é recusado com a mensagem "formato não reconhecido" e a
  lista de formatos aceitos.
- Um OFX do Nubank é associado à conta correta (CPF ou MEI) pelo próprio arquivo.
- O CSV do Nubank é aceito sem conferência de saldo, com aviso de que só o OFX permite conferir.

#### FR-2: Prévia do lote antes de gravar
Antes de confirmar, o Vitor vê, por fonte: novos, já existentes, período coberto e conta ou
corretora.
- Nada é gravado sem confirmação.
- Reimportar o mesmo arquivo resulta em zero novos e gera o aviso "arquivo já importado".

#### FR-3: Atualizado até e defasagem por fonte
O app mostra o **atualizado até** de cada fonte no painel principal e no hub, e avisa quando uma
fonte passa do limite de defasagem:
- Nubank conta PF: 7 dias.
- Nubank conta MEI: aviso só se o mês anterior não estiver coberto até o dia 15 (o OFX do MEI
  costuma cobrir vários meses).
- B3 movimentação e negociação: sem limite fixo; o aviso surge quando o FR-4 detecta transferência
  não coberta.
- B3 consolidado: aviso só se o consolidado do mês anterior não tiver sido importado até o dia 15
  do mês seguinte.

#### FR-4: Lacunas e transferências não cobertas
- Uma **lacuna** numa fonte gera o aviso "lacuna", com o intervalo a importar.
- Uma transferência **a caminho** (§3) gera o aviso "transferência não coberta": "importe o
  relatório B3 a partir de {data}".

#### FR-5: Conferência automática do saldo
Depois de cada import OFX da conta **PF (CPF)**, o app compara o saldo informado no arquivo com o
saldo calculado. A conta MEI fica sempre zerada (o dinheiro passa para a PF), então o OFX do MEI é
importado sem conferência de saldo e pode cobrir vários meses.
- O saldo deve bater ao centavo. Qualquer diferença gera o aviso "saldo divergente", com o valor e
  as transações que podem explicar a diferença.
- Quando bate, o painel principal marca o saldo como conferido na data.

#### FR-6: Desfazer o último lote
O Vitor pode desfazer o **último lote de import** feito nos últimos 7 dias.

- Depois de confirmado, o desfazer remove as transações e operações do lote, as categorizações
  dessas transações e as regras criadas na revisão desse lote.
- Se o lote tocou um mês fechado, o desfazer segue a regra de ajuste do FR-33.

#### FR-7: Recuperar a base
O Vitor importa de uma vez os arquivos de jun a out/2026 (Nubank CPF e MEI, B3), revisa as
transações e fecha cada mês.
- Os meses recuperados começam **abertos**.
- Nada anterior a jun/2026 é duplicado.
- Os meses de jul/2024 a mai/2026 são fechados em bloco na migração, depois da reclassificação de
  resgates (FR-19).

### 4.2 Categorização

Realiza UJ-1 e UJ-4.

#### FR-8: Categorias em dois níveis
O Vitor cria, renomeia e arquiva grupos e subcategorias. Cada categoria tem um **tipo de
movimento**.
- Renomear reflete em todo o histórico.
- Uma categoria com transações não pode ser apagada, só **arquivada** (§3).

#### FR-9: Revisão de transações em lote
Depois de um import, o Vitor vê **todas** as transações novas numa lista com checks, já
preenchidas por regra ou sugestão. Ele corrige qualquer uma e confirma o lote.
- Toda transação nova aparece com regra, com sugestão, ou marcada "sem sugestão" quando não há
  histórico parecido.
- Enquanto houver transações não confirmadas, a central de avisos mostra o aviso "transações a
  revisar".

#### FR-10: Criar regra a partir da correção
Ao corrigir a categoria de uma transação, o app pergunta "criar regra?" e mostra a prévia das
outras transações que a regra afetaria. O Vitor confirma, ajusta a condição ou recusa.
- A regra mais específica (condição mais longa) vence.
- O Vitor edita e desativa regras em Ajustes.
- **Abre mão de:** aprendizado totalmente automático. A pergunta evita regras ruins criadas por
  correções pontuais.

#### FR-11: Reaplicar regras ao histórico
O Vitor reaplica regras a um período passado, vendo antes a prévia das transações afetadas.
- Nunca sobrescreve uma categoria definida manualmente.
- Mudanças em mês fechado seguem o FR-33.

#### FR-12: Origem da categoria
Cada transação guarda a origem da categoria: regra, sugestão confirmada ou manual.

### 4.3 Painel principal e central de avisos

**Descrição:** a primeira tela responde às perguntas do mês antes de qualquer tabela e reúne num
lugar só o que pede ação. Realiza UJ-1 e UJ-2.

#### FR-13: Painel principal
O painel mostra:
- o resultado do mês e o disponível para consumo;
- o patrimônio, o resultado e a rentabilidade dos investimentos;
- os custos fixos pendentes, vencendo e atrasados;
- o aporte do mês: planejado, realizado, a caminho e pendente;
- as classes fora da banda;
- as transações a revisar;
- o **atualizado até** de cada fonte.

Cada número exibe a data dos dados que o geraram.

#### FR-14: Central de avisos
Uma lista única de **avisos**, cada um com tipo, mensagem e ação sugerida. Os tipos são:
- arquivo já importado;
- lacuna;
- transferência não coberta;
- fonte desatualizada;
- saldo divergente;
- CSV sem conferência;
- transações a revisar;
- custo fixo vencendo ou atrasado;
- aporte pendente, nos últimos 7 dias do mês;
- classe fora da banda;
- caixa em corretora divergente da conferência;
- posição divergente da origem;
- ajuste em mês fechado;
- mês aberto há mais de 10 dias depois do fim do mês.


Comportamento:
- Um aviso some sozinho quando a condição deixa de existir.
- Um aviso dispensado só volta se a condição mudar (ex.: o valor divergente muda).
- O painel principal mostra o número de avisos ativos.

### 4.4 Caixa e orçamento do mês

Realiza UJ-2 e UJ-3.

#### FR-15: Receitas por pagador
O app mostra as receitas do mês por **pagador** (ex.: Flash, Betuel) e, em linha própria, os
resgates.
- O pagador nunca atribui categoria.

#### FR-16: Gastos e investimentos
Os gastos aparecem por grupo e subcategoria e incluem só transações com **tipo de movimento**
gasto. O total direcionado a
investimentos aparece em linha própria.
- A fatura do cartão entra como uma única transação, com o valor pago.

#### FR-17: Orçamento do mês
O app calcula o disponível para consumo (fórmula em §3, Orçamento do mês) e mostra quanto já foi
gasto e quanto resta.
- Um resgate aumenta o disponível. Ex.: o notebook pago com o resgate da caixinha Turbo cabe no mês.
- O consumo financiado por resgates aparece em linha própria, para não parecer folga do trabalho.

#### FR-18: Custos fixos pagos × pendentes
Em cada mês, o app casa cada custo fixo com uma transação de valor ±10% numa janela de −5 a +5
dias do vencimento e o marca como pago. O Vitor confirma, corrige ou marca manualmente.

- O aviso "vencendo" surge 3 dias antes do vencimento sem pagamento casado; depois do vencimento,
  vira "atrasado".

#### FR-19: Resgates no histórico
Os resgates gravados como investimento pela regra antiga (ADR-011) são reclassificados como
resgate, ou seja, receita. Isso vale para todo o histórico, uma vez, na migração.
- A reclassificação de resgates não muda a taxa de poupança histórica, porque ela usa a receita do
  trabalho (FR-20). O gate de jun/2026 (55,48%) continua válido.
- A taxa muda só nos meses com Repasse, que passa de Trabalho para Devoluções e abate gasto; os
  deltas por mês ficam listados no teste da migração.

#### FR-20: Taxa de poupança
A taxa de poupança do mês é (receita do trabalho − (gastos − devoluções)) / receita do trabalho. Ao lado, o app
mostra o aporte em relação à receita do trabalho.

### 4.5 Investimentos

Realiza UJ-1, UJ-2 e UJ-3.

#### FR-21: Posições e alocação em dois níveis
O app mostra, por classe e por ativo, o aplicado, o valor atual, o resultado e a alocação atual ×
meta de alocação, com a banda.
- Cripto aparece como **bloco cripto** (§3); o valor atual por ativo entra na alocação.

#### FR-22: Rentabilidade
Toda rentabilidade é calculada por XIRR e pode ser lida por mês, trimestre, ano e desde o início.
- **Nominal × real por classe e consolidada.** O real desconta o IPCA efetivo do período. Se o
  IPCA do último mês ainda não saiu, o real aparece como "aguardando IPCA".
- **Mensal por ativo**, expressa em % a.m., exceto Renda Fixa e Cripto.
- O valor de início de um período vem do resumo do mês fechado anterior. Por isso, a leitura por
  período só existe a partir do primeiro mês fechado na v2 (FR-32).

#### FR-23: Renda fixa sem arquivo
Caixinhas e CDBs são derivados das transações do Nubank e valorados pelo seu percentual do CDI,
aplicado ao CDI efetivo coletado automaticamente (não a uma taxa fixa). O Tesouro (Aposentadoria) usa preço de mercado
automático.

#### FR-24: Debêntures
O Vitor cadastra cada **debênture** (§3) no app, em vez do JSON mantido à mão.
- Só saídas do Nubank com categoria de investimento em debênture viram aportes, sugeridos na
  revisão de transações. Entradas do mesmo pagador (ex.: receita da Flash) não são aportes.
- A posição é valorada pela taxa cadastrada.
- Cupons e resgate no vencimento entram como resgates no Nubank.
- **Abre mão de:** import automático, que não existe porque a Flash não fornece arquivo.

#### FR-25: Caixa em corretora e a caminho
O app calcula, por corretora, o resíduo: saídas do Nubank + proventos − aplicado.
- Se o **atualizado até** da corretora cobre a data da transferência, o resíduo é **caixa em
  corretora** e entra no patrimônio; se não cobre, fica **a caminho** (FR-4).
- O Vitor pode informar o saldo que vê na corretora como conferência opcional; uma divergência gera
  o aviso "caixa em corretora divergente da conferência".

#### FR-26: Conciliação com a origem
O app compara as posições com o consolidado mensal da B3 e com o scan das carteiras cripto. Uma
divergência acima de uma tolerância gera o aviso "posição divergente da origem". `[SUPOSIÇÃO: tolerância definida na arquitetura]`

#### FR-27: Preços sem digitação
Preços de mercado e dólar são obtidos automaticamente. Preço manual só é aceito para ativo sem
fonte de mercado (ex.: Neobankless).

### 4.6 Aportes

Realiza UJ-2.

#### FR-28: Aporte planejado do mês
O Vitor informa o aporte planejado no início do mês e pode alterá-lo durante o mês.

#### FR-29: Distribuição do aporte
O app sugere a distribuição em três passos:
1. **Objetivos:** até o valor-alvo, em proporção ao que falta e ao prazo. `[SUPOSIÇÃO: rateio
   entre objetivos; o destino do aporte para objetivo depende da Q1, §9]`
2. **Classes:** o restante vai por déficit em relação à meta de alocação. A sugestão é monotônica:
   quanto maior o déficit, maior a sugestão. Cada classe recebe ao menos o piso. Uma classe acima
   da meta, fora da banda, recebe só o piso.
3. **Ativos:** dentro da classe, por déficit em relação à meta do ativo. No bloco cripto, o
   déficit usa o valor atual por ativo.

Regras:
- Nunca sugere venda.
- Se a soma dos pisos passar do que sobra depois dos objetivos, os pisos são reduzidos em
  proporção.

#### FR-30: Ajuste da distribuição
O Vitor altera qualquer valor da distribuição. Os valores alterados ficam travados, e o restante é
redistribuído entre os não travados pela mesma regra do FR-29, respeitando o aporte planejado.

#### FR-31: Realizado, a caminho e pendente
O app acompanha até o fim do mês o **realizado** (total e por classe ou ativo, conforme §3), o que
está **a caminho** (FR-25) e o **pendente** (planejado − realizado). No mês seguinte, o pendente é
zerado.

### 4.7 Histórico e fechamento de mês

Realiza UJ-3 e UJ-5.

#### FR-32: Fechar, ajustar e reabrir mês
O Vitor fecha um mês explicitamente. O **resumo do mês** congela:
- receitas por pagador e resgates;
- gastos por categoria;
- investimento do mês;
- taxa de poupança;
- aporte planejado, realizado e pendente;
- patrimônio e valor atual por classe e ativo;
- rentabilidade do mês;
- saldo conferido.

#### FR-33: Ajuste em mês fechado
Um dado novo que caia num mês fechado (import atrasado, correção, reaplicação de regra, desfazer)
é aceito. O resumo congelado não muda, e surge o aviso "ajuste em mês fechado".
- O Vitor pode reabrir o mês, o que recalcula o resumo, e fechá-lo de novo.
- **Abre mão de:** histórico sempre recalculado. O mês fica como o Vitor o viu até que ele decida
  reabrir.

#### FR-34: Comparar períodos
O Vitor compara um mês, trimestre ou ano com o período anterior e com a média dos últimos 12
meses, em:
- receitas e gastos por categoria;
- aporte planejado × realizado;
- crescimento do patrimônio, decomposto em aporte e resultado;
- rentabilidade por classe e por ativo, com destaque para o melhor desempenho.

Disponibilidade por série:
- **Fluxo** (receitas, gastos, investimento, poupança): desde jul/2024.
- **Patrimônio e rentabilidade por período:** a partir do primeiro mês fechado na v2.

### 4.8 Ajustes

Realiza UJ-4.

#### FR-35: Configurações editáveis
O Vitor cria, edita, desativa ou arquiva, sem mexer em código:
- categorias e regras;
- custos fixos (valor, vencimento);
- contas;
- objetivos (nome, valor-alvo, prazo);
- debêntures;
- metas de alocação por classe e por ativo, bandas e pisos;
- o multiplicador da reserva de emergência (padrão 6×);
- preços manuais, só para ativos sem fonte.

### 4.9 Navegação

#### FR-36: Quatro áreas
O app se organiza em **Visão geral**, **Caixa**, **Investimentos** e **Ajustes**. Toda informação
fica a no máximo dois cliques do painel principal. O layout é desktop-first.

`[SUPOSIÇÃO: direção de UX, não requisito: sub-telas como abas e o hub de import e a revisão de
transações como painéis laterais; a etapa de UX confirma]`

## 5. Não-objetivos (inclui o que fica fora por agora)

- **Executar transações, aportes ou resgates.**
- **Reproduzir a planilha "Rotina"** (§1.1).
- **Inventar custo ou rentabilidade por ativo cripto.**
- **Reconstruir o patrimônio mês a mês antes da v2** com preços históricos.
- **Ser multiusuário, mobile ou conectado por Open Finance (Meu Pluggy)** na v2.0.
- **Detalhar a fatura do cartão.** O cartão é usado só em assinaturas; basta o valor pago.

## 6. Escopo

### 6.1 v2.0 em marcos

1. **Ritual confiável:** hub de import, categorização, painel principal, central de avisos e fechamento de
   mês (FR-1 a FR-14, FR-32, FR-33), mais a recuperação da base (FR-7) e a reclassificação de
   resgates (FR-19).
2. **Caixa e orçamento:** FR-15 a FR-18 e FR-20.
3. **Investimentos e aportes:** FR-21 a FR-31. A partir daqui começa a contar a SM-1.
4. **Histórico e ajustes completos:** FR-34 a FR-36. A navegação em quatro áreas evolui desde o
   marco 1.

### 6.2 v2.1 (roadmap)

- Análise fundamentalista (fundos e ações), que habilita a inclinação por valuation na
  distribuição do aporte.
- Estratégia 1MM: cenários, metas por trajetória, value averaging e Liberdade Financeira (300 ×
  custos fixos, multiplicador editável).
- Diário de Trade.
- Benchmarks: carteira × CDI, IBOV e IPCA.
- Deploy na nuvem, alertas no Discord e Hermes.

## 7. Métricas de sucesso

**Primárias**
- **SM-1:** 30 dias seguidos sem abrir a planilha "Rotina" para as tarefas do escopo v2.0, contados
  a partir do marco 3.
- **SM-2:** em todo mês fechado, o saldo calculado da conta Nubank PF bate ao centavo com o saldo
  informado no arquivo. Valida FR-5 e FR-32.
- **SM-3:** em todo mês fechado, o patrimônio por classe bate com a origem (consolidado B3,
  carteiras) dentro da tolerância do FR-26.

**Secundárias**
- **SM-4:** zero preço, saldo de carteira ou cotação digitados no mês, exceto ativos sem fonte.
  Valida FR-23, FR-24 e FR-27.
- **SM-5:** depois de 4 semanas de uso, ≥ 80% das transações novas chegam categorizadas por regra.
  Valida FR-9 e FR-10.
- **SM-6:** o número de correções na revisão por semana cai ao longo do primeiro mês. É uma medida
  de praticidade, sem meta de tempo. Valida FR-10.

**Contra-métricas (não otimizar)**
- **SM-C1:** % de categorias automáticas corrigidas depois de confirmadas. Deve ficar baixo:
  contrabalança a SM-5, expondo confirmação cega.
- **SM-C2:** avisos dispensados sem ação. Muito aviso dispensado é ruído. Contrabalança FR-14.

## 8. NFRs transversais

- **Correção dos dados:**
  - valores monetários exatos;
  - import idempotente;
  - na migração, os dados curados anteriores a jun/2026 só mudam pela reclassificação de resgates
    (FR-19), sem perda nem duplicação.
- **Proveniência:** toda transação e operação sabe de qual lote e fonte veio, e de onde veio a
  categoria.
- **Resiliência:** falha de API externa nunca quebra o painel nem retorna erro. O dado é marcado
  como desatualizado.
- **Ambiente e privacidade:**
  - a v2.0 roda no ambiente local do Vitor;
  - transações, saldos e posições não saem desse ambiente;
  - só saem consultas a fontes públicas (tickers, índices, endereços públicos de carteira) e às
    APIs de corretora/exchange autorizadas;
  - usuário único com autenticação própria; segredos fora do código.
- **Desempenho:** o painel principal carrega em menos de 3 s.
- **Restrições herdadas:** as decisões vigentes do projeto (ADRs, `CLAUDE.md`) continuam valendo,
  exceto o ADR-011, revertido pela regra de resgate (FR-19).

## 9. Questões em aberto

1. **Destino de um aporte para objetivo.** Como o app sabe que uma transferência foi para o
   objetivo Snow Trip e não para a carteira?
   - **Padrão provisório:** cada objetivo é vinculado a um destino (ex.: a caixinha Snow Trip), e
     o aporte para esse destino conta no objetivo.
   - **Responsável:** arquitetura, com validação da UX.
   - **Dependentes:** FR-29 (passo 1) e "Objetivo" (§3).

## 10. Índice de suposições

Delegadas às próximas etapas (as demais foram confirmadas pelo Vitor em 2026-10-17):
- UJ-2: distribuição com classes primeiro e expansão para ativos (UX).
- FR-26: tolerância da conciliação com a origem (arquitetura).
- FR-29: rateio entre objetivos; padrão provisório da Q1 (arquitetura).
- FR-36: abas e painéis laterais como direção de UX (UX).
