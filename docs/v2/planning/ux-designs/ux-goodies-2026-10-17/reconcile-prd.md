---
title: "Reconciliação PRD × decisões de UX — Goodies v2"
created: 2026-10-17
source: ../../prds/prd-goodies-2026-10-17/prd.md (+ addendum.md)
target: .memlog.md (estado em 2026-10-17T22:30)
---

# Reconciliação PRD × decisões de UX

Cada necessidade do PRD que tem implicação de tela ou de comportamento foi comparada com o que o
`.memlog.md` já decide. DESIGN.md e EXPERIENCE.md ficaram fora desta comparação.

**Legenda**
- **COVERED**: o memlog decide onde aparece e como se comporta, o suficiente para desenhar.
- **PARTIAL**: o memlog decide onde aparece (área/aba/componente), mas não como (layout, estados,
  interação, texto).
- **MISSING**: não há decisão de UX sobre onde nem como.
- **N/A**: sem superfície de UX própria (registrado só para rastreabilidade, fora da contagem).

**Decisões do memlog usadas como base:** IA aprovada (sidebar com Visão geral, Caixa, Investimentos,
Ajustes e botão Importar fixo; topo com seletor de período global, sino da central de avisos e
switch de tema; abas por área); Histórico como aba da Visão geral com comparações e
fechar/reabrir; aportes em Investimentos > Aportes com resumo na Visão geral; revisão em lote
(tudo marcado, correção na linha com dropdown com busca, atalhos, Shift para intervalo); densidade
"resumo + detalhe sob demanda, com visão detalhada completa"; mais números que gráficos (3
gráficos: patrimônio no tempo, gastos por categoria, aporte planejado × realizado); paleta A2
(verde positivo, vermelho negativo, laranja só para avisos); tipografia B1 (números em mono
tabular); voz "você", direta; valores sempre completos; animação mínima com painéis laterais
deslizando.

## Contagem

| Status | Qtde |
|---|---|
| COVERED | 8 |
| PARTIAL | 61 |
| MISSING | 40 |
| N/A | 2 |
| **Total avaliado (sem N/A)** | **109** |

## 1. Requisitos funcionais (FR-1..FR-36)

| ID | Necessidade (PRD) | Implicação de UX | Status | O que o memlog já decide | Lacuna / proposta |
|---|---|---|---|---|---|
| FR-1 | Importar qualquer fonte num só lugar; identificação automática da fonte | Ponto de entrada do hub, área de soltar arquivos, identificação da fonte por arquivo, recusa "formato não reconhecido" + lista de formatos, aviso de CSV sem conferência | PARTIAL | Botão Importar fixo na sidebar; painéis laterais deslizando (animação) | Decidir se o hub é painel lateral ou página (a suposição do FR-36 sugere painel). Definir dropzone multiarquivo, chip de fonte detectada por arquivo, erro inline com formatos aceitos e aviso inline "CSV: sem conferência de saldo, prefira OFX" |
| FR-2 | Prévia do lote antes de gravar | Tabela de prévia por fonte: novos, já existentes, período coberto, conta/corretora; botão confirmar; reimport = 0 novos | MISSING | — | Prévia agrupada por fonte com contadores (novos / existentes), período, conta; CTA único "Confirmar lote". Estado "0 novos: arquivo já importado" sem bloquear |
| FR-3 | Atualizado até por fonte no painel e no hub; defasagem | Lista de fontes com data e estado (em dia / defasado) em dois lugares | MISSING | — | Faixa ou card "Fontes" no Painel (5 fontes + automáticas: preços, carteiras, CDI/IPCA) e o mesmo bloco no topo do hub. Defasagem em laranja (cor de aviso) |
| FR-4 | Lacuna e transferência não coberta | Avisos com intervalo/data e ação "importe o relatório B3 a partir de {data}" | PARTIAL | Central de avisos no sino | Definir anatomia do aviso (tipo, mensagem, ação) e se a ação abre o hub já filtrado na fonte |
| FR-5 | Conferência automática do saldo (OFX) | Resultado da conferência após import; "saldo conferido em {data}" no painel; divergência com valor e transações candidatas | PARTIAL | Exemplo de voz: "Saldo divergente em R$ 37,20. Ver transações." | Selo "conferido em dd/mm" junto ao saldo no Painel; tela/painel de divergência listando transações candidatas; estado de sucesso no fim do import (clímax da UJ-1) |
| FR-6 | Desfazer o último lote (≤ 7 dias) | Ação de desfazer, confirmação destrutiva listando o que sai (transações, operações, categorizações, regras do lote); efeito em mês fechado | MISSING | — | Onde fica (histórico de lotes no hub?), o texto da confirmação com contagens e o aviso de que o desfazer gera "ajuste em mês fechado" quando for o caso |
| FR-7 | Recuperar a base (jun–out/2026) | Fluxo único de import multi-mês, revisão longa, fechamento mês a mês | MISSING | — | Modo "recuperação": import em lote de vários arquivos, revisão paginada/por mês, checklist de meses a fechar (saldo conferido por mês). Os meses jul/2024–mai/2026 já aparecem fechados |
| FR-8 | Categorias em dois níveis; renomear; arquivar | Editor de árvore grupo > subcategoria, tipo de movimento por categoria, arquivar em vez de apagar | PARTIAL | Ajustes > Categorias | Árvore com edição inline; seletor de tipo de movimento; arquivadas ocultas por padrão com filtro "mostrar arquivadas"; bloqueio de apagar com explicação |
| FR-9 | Revisão de transações em lote | Lista com checks, pré-preenchida, correção, confirmação do lote | PARTIAL | Abre com tudo marcado; correção na linha (dropdown com busca); atalhos; Shift para intervalo; Enter confirma | Falta: onde mora (painel lateral, como sugere o FR-36?); indicação de origem por linha (regra / sugestão / "sem sugestão"); filtros (ex.: só "sem sugestão"); combinação exata de atalhos |
| FR-10 | Criar regra a partir da correção, com prévia | Pergunta "criar regra?" após corrigir, condição editável, prévia das transações afetadas, confirmar / ajustar / recusar | MISSING | — | Padrão não bloqueante (popover ou faixa na linha corrigida) para não travar o ritmo da revisão com teclado; prévia com contagem + lista; edição da condição "descrição contém" |
| FR-11 | Reaplicar regras ao histórico | Escolha de período, prévia das transações afetadas, aviso sobre categorias manuais preservadas e meses fechados | MISSING | — | Ação em Ajustes > Regras ("Reaplicar a um período"); prévia com diff de/para; nota "N categorias manuais não serão alteradas"; contagem de meses fechados afetados |
| FR-12 | Origem da categoria (regra / sugestão confirmada / manual) | Indicador por transação | MISSING | — | Ícone ou rótulo discreto na lista de transações e na revisão; tooltip com a regra aplicada |
| FR-13 | Painel principal | Composição: resultado do mês + disponível; patrimônio, resultado, rentabilidade; custos fixos pendentes/vencendo/atrasados; aporte do mês; classes fora da banda; transações a revisar; atualizado até por fonte; data de cada número | PARTIAL | Visão geral > Painel; resumo do aporte do mês; densidade resumo + detalhe; mais números que gráficos; gráfico de patrimônio no tempo | Falta a hierarquia e a ordem dos blocos, o número de avisos ativos, o bloco de fontes e o padrão de data por número (ver Princípios) |
| FR-14 | Central de avisos | Lista única; tipo, mensagem, ação; some sozinho; dispensar; contagem no painel | PARTIAL | Sino no topo; laranja só para avisos; voz direta | Falta: popover × painel lateral × página; agrupamento por tipo; botão de ação por aviso; "dispensar" e o comportamento de reaparecer; badge de contagem no sino e no Painel |
| FR-15 | Receitas por pagador + resgates em linha própria | Quebra de receitas por pagador; linha separada de resgates | MISSING | — | Bloco "Receitas" em Caixa > Orçamento (ou Transações?) com pagadores + linha "Resgates" visualmente separada; subtotal "Receita do trabalho" |
| FR-16 | Gastos por grupo/subcategoria; investimento em linha própria; fatura = valor pago | Tabela/gráfico por grupo com expansão; linha "Direcionado a investimentos" | PARTIAL | Gráfico de barras de gastos por categoria | Em qual aba fica (Orçamento?); expansão grupo → subcategoria; linha própria de investimento fora do total de gastos |
| FR-17 | Orçamento do mês: disponível para consumo, gasto, resta; consumo financiado por resgates em linha própria | Cálculo visível (receitas − custos fixos − aporte planejado − dívidas), entrada de "dívidas do mês", linha do consumo financiado por resgates | PARTIAL | Aba Caixa > Orçamento existe | MISSING no "como": mostrar a fórmula como cascata; campo editável de dívidas do mês; barra "gasto × disponível"; linha "consumo financiado por resgates" com texto que deixe claro que não é folga do trabalho; espelho do disponível no Painel |
| FR-18 | Custos fixos pagos × pendentes; casamento ±10%/±5 dias; confirmar/corrigir/marcar manualmente; vencendo/atrasado | Lista do mês com estado, transação casada, ações | PARTIAL | Aba Caixa > Custos fixos | Linha por custo fixo com estado (pago / pendente / vencendo / atrasado), transação casada sugerida com "confirmar / trocar / marcar pago manualmente"; definir cores de estado (laranja só para aviso → atrasado também é aviso?) |
| FR-19 | Reclassificação histórica de resgates | Migração; efeito visível é "Resgates" como receita nos meses antigos | N/A | — | Coberto pelos FR-15/FR-17 |
| FR-20 | Taxa de poupança + aporte / receita do trabalho | Onde e como mostrar as duas razões | MISSING | — | Provável Caixa > Orçamento e Histórico; definir se aparece no Painel |
| FR-21 | Posições e alocação em dois níveis; banda; bloco cripto | Tabela classe → ativo com aplicado, valor atual, resultado, alocação × meta com banda; cripto em bloco | PARTIAL | Investimentos > Posições; detalhe sob demanda | Linhas de classe expansíveis; visual da banda (barra meta ± banda com marcador da alocação atual); bloco cripto sem custo/rentabilidade por ativo (célula vazia com explicação) |
| FR-22 | Rentabilidade XIRR por mês/tri/ano/desde o início; nominal × real; "aguardando IPCA"; % a.m. por ativo exceto RF e Cripto; leitura por período só após o 1º mês fechado | Seletor de período; colunas nominal/real; estados especiais | PARTIAL | Seletor de período global | Como o seletor global vira "mês/tri/ano/desde o início" para rentabilidade; rótulo "XIRR"; estado "aguardando IPCA"; célula "—" para RF/Cripto mensal; estado vazio antes do 1º mês fechado |
| FR-23 | Renda fixa sem arquivo (CDI efetivo); Tesouro a mercado | Mostrar base da valoração (% do CDI) e data do CDI usado | MISSING | — | Detalhe do ativo RF com "% do CDI" e "CDI até dd/mm" |
| FR-24 | Debêntures: cadastro; aportes sugeridos na revisão; valoração pela taxa | Formulário (emissor, taxa, início, vencimento); sugestão "aporte em debênture" na revisão; cupons como resgate | PARTIAL | Ajustes > Debêntures | Campos e validação do formulário; como a revisão sugere o vínculo transação → debênture; posição na aba Posições com selo "valorada pela taxa cadastrada" |
| FR-25 | Caixa em corretora e a caminho; conferência opcional do saldo da corretora | Resíduo por corretora com estado (caixa × a caminho); campo para informar saldo visto na corretora | MISSING | (Aba Investimentos > Conciliação existe, sem conteúdo definido) | Card por corretora em Conciliação: resíduo, estado, data de cobertura; campo inline "saldo que vejo na corretora" com data; divergência → aviso |
| FR-26 | Conciliação com a origem (B3 consolidado, carteiras) | Comparação app × origem por classe/ativo com tolerância | PARTIAL | Aba Investimentos > Conciliação | Layout da comparação (app, origem, diferença, dentro/fora da tolerância), data do consolidado/scan usado |
| FR-27 | Preços automáticos; manual só sem fonte | Edição de preço manual restrita; preço defasado marcado | PARTIAL | Ajustes > Preços manuais | Lista só de ativos sem fonte; marca visual de preço manual nas posições; marca de "desatualizado" (NFR resiliência) |
| FR-28 | Aporte planejado do mês, editável no mês | Campo de entrada no início do mês; referência ao quadro 1MM (na planilha até a v2.1) | PARTIAL | Investimentos > Aportes; resumo no Painel | Estado inicial "defina o aporte do mês"; edição inline; atalho a partir do Painel |
| FR-29 | Distribuição em 3 passos (objetivos → classes → ativos); piso; nunca vende | Visual em cascata com os três níveis e o motivo da sugestão | PARTIAL | Aba Aportes | Suposição UJ-2 (classes primeiro, expansão para ativos) ainda não decidida; seção de objetivos antes das classes; explicação do "porquê" (déficit, piso, fora da banda) |
| FR-30 | Ajuste com travas e redistribuição instantânea | Edição de qualquer valor, cadeado nos valores alterados, recálculo ao vivo, soma = planejado | MISSING | — | Célula editável com cadeado; "destravar"/"restaurar sugestão"; total fixo visível; validação quando travas excedem o planejado |
| FR-31 | Realizado, a caminho e pendente | Total e por classe/ativo; a caminho; pendente até o fim do mês | PARTIAL | Resumo no Painel; gráfico de barras planejado × realizado | Como "a caminho" aparece (segmento da barra? linha própria?); realizado total × por classe com regras diferentes (§3) precisa de explicação visual |
| FR-32 | Fechar o mês; resumo congelado; reabrir | Ação de fechar, conferência prévia, indicação de mês fechado | PARTIAL | Fechar/reabrir na aba Visão geral > Histórico | Checklist antes de fechar (saldo conferido, transações revisadas, avisos abertos); confirmação; selo "fechado" no seletor de período e nas telas do mês |
| FR-33 | Ajuste em mês fechado; reabrir recalcula | Resumo congelado × dado novo; aviso; reabrir e fechar de novo | MISSING | — | Indicador "há ajustes pendentes neste mês fechado" no mês; ação do aviso leva ao Histórico com "reabrir"; mostrar diferença congelado × recalculado antes de reabrir |
| FR-34 | Comparar períodos (anterior, média 12m); decomposição aporte × resultado; melhor desempenho; disponibilidade por série | Telas de comparação | PARTIAL | Aba Histórico com mês/tri/ano × anterior × média 12m; gráficos de linha e barras | Visual da decomposição do crescimento (aporte × resultado); destaque do melhor desempenho; estado "disponível a partir de {mês}" para patrimônio/rentabilidade |
| FR-35a | Ajustes: categorias e regras | CRUD + desativar regra | PARTIAL | Abas Categorias e Regras | Editor de regra (condição, categoria, especificidade, ativo/inativo, prévia) — ver FR-10/FR-11 |
| FR-35b | Ajustes: custos fixos (valor, vencimento) | CRUD simples | COVERED | Aba Ajustes > Custos fixos | — (formulário simples) |
| FR-35c | Ajustes: contas | CRUD simples | COVERED | Aba Ajustes > Contas | — |
| FR-35d | Ajustes: objetivos (nome, valor-alvo, prazo) + vínculo ao destino (Q1) | CRUD + escolha do destino | PARTIAL | Aba Ajustes > Objetivos | Campo "destino" (ex.: caixinha Snow Trip) pendente da Q1; reserva de emergência como objetivo especial com alvo calculado |
| FR-35e | Ajustes: debêntures | — | PARTIAL | Aba Ajustes > Debêntures | Ver FR-24 |
| FR-35f | Ajustes: metas por classe e por ativo, bandas, pisos | Editor em dois níveis com soma = 100% | PARTIAL | Aba Ajustes > Metas | Tabela classe → ativo com %, banda (pp) e piso (R$); validação de soma 100% em cada nível |
| FR-35g | Ajustes: multiplicador da reserva de emergência (6×) | Campo editável | MISSING | — | Não há aba. Propor dentro de Ajustes > Objetivos, no item "Reserva de emergência" |
| FR-35h | Ajustes: preços manuais (só sem fonte) | CRUD restrito | COVERED | Aba Ajustes > Preços manuais | — |
| FR-36a | Quatro áreas; tudo a ≤ 2 cliques; desktop-first | IA | COVERED | Sidebar + abas aprovadas | — |
| FR-36b | Suposição: hub de import e revisão como painéis laterais | Contêiner dos dois fluxos | PARTIAL | "Painéis laterais deslizando" (animação) | Confirmar explicitamente que hub e revisão são painéis laterais (e a largura, já que a revisão é uma tabela larga) |

## 2. Jornadas (UJ-1..UJ-5)

| ID | Jornada | Status | O que o memlog já decide | Lacuna |
|---|---|---|---|---|
| UJ-1 | Fechar a semana em poucos cliques | PARTIAL | Botão Importar fixo; revisão em lote com atalhos | Prévia (FR-2), criar regra (FR-10), momento de sucesso "saldo bate / posições batem" (clímax) e roteamento dos tropeços para avisos |
| UJ-2 | Planejar e acompanhar o aporte | PARTIAL | Aba Aportes; resumo no Painel; gráfico planejado × realizado | Entrada do aporte, travas (FR-30), objetivos primeiro, "a caminho", "classes primeiro com expansão para ativos" (suposição) |
| UJ-3 | Olhar para trás e fechar o mês | PARTIAL | Aba Histórico com comparações e fechar/reabrir | Layout que responde às 4 perguntas; fluxo de fechamento (FR-32) |
| UJ-4 | Ajustar o sistema sem código | PARTIAL | Abas de Ajustes | Editores de regra, metas em dois níveis, objetivos, multiplicador |
| UJ-5 | Recuperar a base (jun–out/2026) | MISSING | — | Fluxo de recuperação (FR-7) |

## 3. Princípios (§1.1) e conceitos transversais

| ID | Necessidade | Status | O que o memlog já decide | Lacuna |
|---|---|---|---|---|
| P-1 | Praticidade acima de tudo (ritual fácil, não cronometrado) | COVERED | Importar fixo; revisão tudo marcado; atalhos; animação mínima | — |
| P-2 | Dados úteis e fáceis de interpretar (todo número responde a uma pergunta) | PARTIAL | Densidade resumo + detalhe; mais números que gráficos; valores completos; voz direta | Falta regra de rótulo: cada número com legenda em forma de pergunta/resposta; tooltips de definição (glossário §3) |
| P-3 | Cada número exibe a data dos dados que o geraram | MISSING | — | Padrão visual único (ex.: legenda "até dd/mm" sob o valor ou no cabeçalho do card) e regra de quando agrupar várias datas |
| P-4 | A planilha não é gabarito | COVERED | Desapegar da estética da planilha | — |
| P-5 | Relatório é a fonte de verdade; o app informa e sugere, nunca executa | PARTIAL | Voz direta | Regra de texto: "sugestão", "planejado", nunca "comprar/executar"; nenhum botão que pareça executar ordem |
| NFR-1 | Resiliência: dado de API externa marcado como desatualizado, sem erro | MISSING | — | Estado visual "desatualizado" (cor de aviso? ícone?) em preços, carteiras, índices |
| NFR-2 | Proveniência: lote e fonte de cada transação/operação | MISSING | — | Detalhe da transação com fonte, lote e origem da categoria |
| NFR-3 | Painel em < 3 s | MISSING | — | Estados de carregamento (skeleton) e carregamento parcial por bloco |
| NFR-4 | Usuário único com autenticação própria | MISSING | — | Tela de login (provavelmente herdada da v1; confirmar se muda com o novo visual) |
| NG-1 | Desktop-first, sem mobile | COVERED | Desktop-first (IA) | — |
| NG-2 | Fatura como valor pago, sem detalhamento | N/A | — | — |
| Q1 | Destino do aporte para objetivo (validação de UX) | MISSING | — | Como o vínculo objetivo → destino aparece em Ajustes > Objetivos e na revisão |
| GLB | Seletor de período global × mês fechado | PARTIAL | Seletor global, mês atual por padrão | Mostrar no seletor se o mês está aberto/fechado e se tem ajuste pendente |

## 4. Conceitos do glossário que precisam de exibição

| Conceito | Status | O que o memlog já decide | Lacuna / proposta |
|---|---|---|---|
| Fonte (5 por arquivo + 3 automáticas) | MISSING | — | Bloco "Fontes" com nome, tipo (arquivo / automática) e estado |
| Atualizado até | MISSING | — | Data por fonte no Painel e no hub (FR-3) |
| Lote de import | PARTIAL | Revisão em lote | Identificação do lote (data, arquivos) e lista de lotes para desfazer |
| Lacuna | PARTIAL | Aviso via sino | Intervalo exibido no aviso e, talvez, linha do tempo de cobertura por fonte |
| Transação (data, valor, descrição, categoria, tipo, pagador) | PARTIAL | Revisão com correção na linha; Caixa > Transações | Colunas da tabela e filtros |
| Tipo de movimento (receita/gasto/investimento/transferência) | MISSING | — | Como é codificado sem cores de categoria (rótulo? ícone?); verde/vermelho reservados a positivo/negativo |
| Resgate (linha própria) | MISSING | — | Ver FR-15/FR-17 |
| Receita do trabalho | MISSING | — | Subtotal visível (base da taxa de poupança) |
| Pagador | MISSING | — | Coluna nas transações de receita e agrupamento no Orçamento |
| Categoria arquivada | MISSING | — | Some da busca da revisão; aparece esmaecida no histórico |
| Regra / Sugestão / "sem sugestão" | MISSING | — | Indicador por linha na revisão (FR-9/FR-12) |
| Saldo da conta: calculado × informado; conferido | PARTIAL | Voz do aviso "saldo divergente" | Mostrar as duas leituras lado a lado e o selo "conferido em" |
| Resultado do mês | PARTIAL | Painel (via PRD) | Posição e destaque no Painel |
| Custo fixo pago / pendente / vencendo / atrasado | MISSING | — | Estados visuais e onde aparecem (Caixa > Custos fixos e Painel) |
| Orçamento do mês / disponível para consumo | PARTIAL | Aba Orçamento | Ver FR-17 |
| Dívidas do mês (manual) | MISSING | — | Campo editável no Orçamento, com zero como padrão |
| Classe > Ativo | PARTIAL | Posições; detalhe sob demanda | Expansão de linha |
| Debênture | PARTIAL | Ajustes > Debêntures | Ver FR-24 |
| Aplicado / Valor atual / Resultado | PARTIAL | Números em mono, completos; verde/vermelho | Ordem das colunas; resultado com sinal e cor |
| Proventos | MISSING | — | Onde aparecem (Posições? Caixa?) |
| Bloco cripto | MISSING | — | Linha única "quanto saiu × quanto vale" com ativos só com valor atual |
| Rentabilidade (XIRR; nominal × real) | MISSING | — | Rótulo "XIRR", alternância nominal/real, "aguardando IPCA" |
| Caixa em corretora | MISSING | — | Card por corretora em Conciliação e componente do patrimônio |
| A caminho | MISSING | — | Estado com data da transferência e ação "importar B3 a partir de"; aparece no aporte do mês e no patrimônio (fora dele) |
| Patrimônio (composição) | PARTIAL | Gráfico de patrimônio no tempo | Quebra posições + bloco cripto + caixa em corretora + saldo das contas |
| Meta de alocação / Banda / Piso | MISSING | — | Visual de meta ± banda; marcação "fora da banda" |
| Objetivo (progresso) | MISSING | — | Barra de progresso (aportes − resgates / valor-alvo) com prazo e ritmo necessário; onde aparece (Aportes? Painel?) |
| Reserva de emergência | MISSING | — | Objetivo especial com alvo calculado (6 × custos fixos) visível |
| Aporte planejado | PARTIAL | Aba Aportes | Ver FR-28 |
| Distribuição do aporte | PARTIAL | Aba Aportes | Ver FR-29/FR-30 |
| Realizado / Pendente | PARTIAL | Gráfico planejado × realizado | Ver FR-31 |
| Painel principal | COVERED | Visão geral > Painel, tela inicial | — |
| Mês aberto / mês fechado | PARTIAL | Fechar/reabrir no Histórico | Selo no seletor de período e nas telas |
| Resumo do mês | PARTIAL | Histórico | Exibição do snapshot congelado e diferença para o recalculado |

## 5. Tipos de aviso (FR-14)

A central de avisos está decidida (sino no topo, laranja só para avisos, voz direta), mas a
anatomia do aviso, a ação de cada tipo e o comportamento de dispensar não estão. Todos ficam
PARTIAL; a coluna "ação proposta" é sugestão para a etapa de UX.

| Tipo | Status | Ação proposta (destino) |
|---|---|---|
| Arquivo já importado | PARTIAL | Informativo no fim do import; nenhuma ação |
| Lacuna | PARTIAL | "Importar {fonte} de {data} a {data}" → hub |
| Transferência não coberta | PARTIAL | "Importar B3 a partir de {data}" → hub |
| Fonte desatualizada | PARTIAL | "Importar {fonte}" → hub |
| Saldo divergente | PARTIAL | "Ver transações" → lista de candidatas (voz já exemplificada) |
| CSV sem conferência | PARTIAL | "Importar o OFX do mesmo período" → hub |
| Transações a revisar | PARTIAL | "Revisar N transações" → revisão |
| Custo fixo vencendo / atrasado | PARTIAL | "Marcar como pago" / "Ver custo fixo" → Caixa > Custos fixos |
| Aporte pendente (últimos 7 dias do mês) | PARTIAL | "Ver aporte" → Investimentos > Aportes |
| Classe fora da banda | PARTIAL | "Ver alocação" → Posições ou Aportes |
| Caixa em corretora divergente da conferência | PARTIAL | "Ver corretora" → Conciliação |
| Posição divergente da origem | PARTIAL | "Ver conciliação" → Conciliação |
| Ajuste em mês fechado | PARTIAL | "Reabrir mês" → Histórico |
| Mês aberto há mais de 10 dias | PARTIAL | "Fechar mês" → Histórico |
| Comportamento: some sozinho, dispensar e reaparecer se a condição mudar, contagem no Painel | MISSING | Botão "dispensar" por aviso; seção "dispensados"; badge no sino e no Painel |

## 6. Itens prioritários (MISSING/PARTIAL de maior impacto)

1. **P-3 / FR-3 — data dos dados e "atualizado até" por fonte**: não há padrão visual para a data
   de cada número nem bloco de fontes no Painel e no hub.
2. **FR-17 — Orçamento do mês**: a aba existe, mas faltam a cascata do disponível para consumo, o
   campo "dívidas do mês" e a linha "consumo financiado por resgates".
3. **FR-10 / FR-11 — regras**: falta o padrão "criar regra?" com prévia na revisão sem quebrar o
   fluxo de teclado e o fluxo "reaplicar ao período" com prévia.
4. **FR-25 / glossário — caixa em corretora e a caminho**: sem exibição nem campo da conferência
   opcional do saldo da corretora (provável Investimentos > Conciliação).
5. **FR-32 / FR-33 — fechar, ajuste em mês fechado e reabrir**: o lugar está decidido (Histórico),
   mas faltam o checklist de fechamento, o selo aberto/fechado no seletor e o "congelado ×
   recalculado" antes de reabrir.
6. **FR-29 / FR-30 / objetivos — distribuição do aporte**: falta decidir "classes primeiro com
   expansão" (suposição UJ-2), travas com recálculo ao vivo e a exibição do progresso dos objetivos.
7. **FR-2 / FR-6 / FR-7 — prévia, desfazer lote e recuperação da base**: sem prévia por fonte, sem
   UI para desfazer o lote e sem fluxo de recuperação jun–out/2026.
8. **FR-18 — custos fixos**: falta a UI para confirmar, trocar ou marcar manualmente o casamento,
   e os estados pago/pendente/vencendo/atrasado.
