---
title: "Revisão de interface — key screens Goodies v2"
created: 2026-10-17
scope: .working/key-painel.html, key-revisao.html, key-aportes.html, key-orcamento.html (escuro + claro)
method: interface-review → better-interface (acessibilidade, layout, escrita, tipografia, cor, UI polish)
verdict: Block (4 HIGH)
---

# Revisão de interface — key screens Goodies v2

## Escopo e cobertura

**O que foi revisado:** 4 mockups HTML estáticos, cada um com variante escura e clara (o Orçamento traz também o estado alternativo "restante negativo"). Desktop, pt-BR.

**Contrato respeitado:** `DESIGN.md` e `EXPERIENCE.md` desta pasta. A paleta (darkmatter + supabase), a personalidade ("terminal de trader, porém arejado") e a dupla sans + mono tabular não são criticadas. Só entram aqui quando causam problema de uso ou de acessibilidade.

**Recon:** os quatro mocks compartilham o mesmo bloco de CSS (tokens + componentes, linhas 23–186, idêntico nos quatro arquivos). Por isso, um achado no CSS compartilhado vale para todas as telas e é tratado como sistêmico. As fontes Geist / Geist Mono não carregam offline, e o render usou fallback (sans do sistema + DejaVu Sans Mono, de avanço quase igual ao da Geist Mono).

**Ressalva de escopo:** é uma revisão de tela, não de mudança. Como não há diff, a classificação Introduced/Regression do `interface-review` não se aplica. Todo achado é tratado como pertencente ao mock.

**Sobre o limite de 15 achados do `better-interface`:** foi excedido de propósito, porque o pedido foi um detalhamento por tela. Os achados sistêmicos estão consolidados numa tabela única e ranqueada. Os achados que valem só para o mock aparecem nas seções de cada tela.

| Domínio | Evidência inspecionada | Resultado |
|---|---|---|
| Acessibilidade | Contraste medido por par renderizado, contraste não-texto (WCAG 1.4.11), cor como único sinal, alvos ≥ 24px, foco desenhado (linha focada da Revisão), semântica do HTML do mock | 2 sistêmicos HIGH (cor/não-texto), 1 LOW só no mock |
| Layout | Screenshots em 1440, 1280 (largura alvo) e 1024 (piso "funciona sem quebrar"); alinhamento de colunas; agrupamento; espaços mortos | 1 HIGH, 4 MEDIUM, 2 LOW |
| Escrita | Vocabulário fechado de selos/tags, consistência de termos entre telas, cópia × EXPERIENCE › Voice and Tone; aritmética dos números exibidos | 1 HIGH, 3 MEDIUM, 4 LOW |
| Tipografia | Escala usada × tokens, pesos, alinhamento tabular, tamanho mínimo de tag | 3 MEDIUM, 1 LOW |
| Cor | Tokens × uso por papel, pares de contraste nos dois temas, segmentos da barra | Incluído nos HIGH de acessibilidade, mais 1 LOW |
| UI polish | Superfícies (card dentro de card), botões vs. links, paridade claro/escuro | 1 LOW (o achado de botões × links da Revisão está contado em Layout) |

## Verificação

**Executado:**

- **Screenshots:** `chrome-headless-shell` (Playwright 1223) via `playwright-core`, viewport 1500px, recorte em cada `.frame`, dois temas por tela. Os 8 frames e os 2 recortes do estado alternativo foram inspecionados visualmente.
- **Largura reduzida:** os mesmos arquivos com `.sheet,.frame{width:1280px | 1024px}` injetado. Um script mediu o transbordo de cada elemento contra a borda direita do frame:
  - 1280: Aportes transborda 53px, Orçamento 23px;
  - 1024: os KPIs do Painel saem do card (`scrollWidth 183/211 > 169`), Aportes transborda 309px e Orçamento 151px. O painel da Revisão (1040px) fica mais largo que a viewport.
- **Contraste:** fórmula WCAG 2.x sobre os hex dos tokens, já com a mistura de `color-mix` (tint 10% / 14%) e a opacidade aplicadas. Os valores citados abaixo saíram desse cálculo, não de estimativa.
- **Aritmética:** todas as somas conferem:
  - KPIs do Painel;
  - Conta do orçamento (8.405,59 → 1.493,22 → −2.994,77);
  - Distribuição: 1.300 + 3.200 = 4.500, metas somando 100%, 6 × 3.412,40 = 20.474,40;
  - rodapé da Revisão: −1.358,38.

**Não verificado:**

- Fontes reais (Geist / Geist Mono): as larguras são aproximadas. A margem de transbordo em 1280 (23–53px) é maior que a diferença esperada entre as fontes.
- Navegação por teclado, ordem de Tab e leitor de tela: os mocks são estáticos e o HTML não é normativo.
- Zoom de 200% e `prefers-reduced-motion`: não há movimento nos mocks.
- `forced-colors`.

---

## Achados sistêmicos (corrigir no DESIGN.md / EXPERIENCE.md)

Ordenados por severidade e depois por alcance. "Destino" indica onde a correção mora.

| # | Sev. | Domínio | Local | Antes | Depois | Por quê | Destino |
|---|---|---|---|---|---|---|---|
| S1 | **HIGH** | Layout | `key-aportes.html:197,208` (tabela Objetivos); `key-orcamento.html:257` (Gastos por grupo); `key-painel.html:120,124` (`.grid4` + `.kpi-value` nowrap 24px); `key-revisao.html:187` (`.drawer{width:1040px}`) | Em **1280px, que é a largura alvo**, a coluna "Pendente" da tabela de objetivos e a coluna "Transações" de Gastos por grupo ficam cortadas (transbordo de 53px e 23px). Em 1024px, "R$ 68.695,66" invade o card vizinho e "+R$ 6.482,10" aparece cortado em "+R$ 6.482,". O painel largo de 1040px passa da viewport | **DESIGN › Layout:** (1) a fileira de 4 KPIs vira 2×2 abaixo de ~1280px de conteúdo, por container query no grid; nunca cortar um valor monetário. (2) `drawer-width-wide: min(1040px, 100vw − 48px)`. (3) Tabela em card: `overflow-x:auto` com sombra/fade na borda como pista. No modo Resumo, as colunas de baixa prioridade (Alvo, Prazo, % do consumido) saem primeiro. Remover `min-width:220px` de `.obj-prog`. **EXPERIENCE › Accessibility Floor:** declarar o comportamento em zoom de 200% (1440 → 720 CSS px, abaixo do piso de 1024) ou registrar a exceção da 1.4.10 para tabelas, porque hoje "WCAG 2.2 AA" e "< 1024 não suportado" se contradizem | Na largura alvo, a coluna cortada esconde dados financeiros sem nenhum sinal. Em 1024, que o spec promete "sem quebrar", um valor de patrimônio aparece truncado | DESIGN + EXPERIENCE |
| S2 | **HIGH** | Acessibilidade / Cor | `key-revisao.html:204` (`tr.focused td{background:var(--accent)}`), `:210` (`.rule-strip` em `--muted`), `:271` (`<span class="muted">Afeta 4 outras transações</span>`); DESIGN `data-table.row-hover` e `transaction-review.row-selected` = `{colors.accent}`; `rule-proposal.background` = `{colors.muted}` | Na linha em foco (justamente a "sem sugestão", que bloqueia o Confirmar): legenda "Débito" `muted-foreground`/`accent` = **3,56:1** (escuro) e **4,17:1** (claro); tag "SEM SUGESTÃO" `warning` sobre `accent` = **3,93 / 4,19:1**. Na Proposta de regra, "Afeta 4 outras transações" usa `muted-foreground`/`muted` = **4,49 / 4,39:1**, que é o par que o próprio DESIGN proíbe | Novo token `row-highlight` para hover/seleção/foco de linha: `#1e1e1e` (escuro) e `#f9fafb` (claro). Com ele, muted fica em 4,70 / 4,63:1 e a tag warning em 5,16 / 4,63:1. O anel `{colors.ring}` continua marcando o foco. Na `rule-proposal`, o texto vai em `{colors.foreground}` (ou a faixa passa a `{colors.card}` com borda esquerda `{colors.border}`). Acrescentar ao "Par proibido": `muted-foreground` e `warning` sobre `accent` | Texto de 12–13px abaixo de 4,5:1, justamente na linha que o usuário precisa ler para destravar o lote. A causa está nos tokens do componente, não no mock | DESIGN |
| S3 | **HIGH** | Escrita | `key-aportes.html:~252` (legenda "Pendente R$ 1.700,00") × `:296` (nota "pendente R$ 2.200,00, dos quais R$ 500,00 a caminho") × totais da tabela (900 + 1.300 = 2.200); `key-painel.html:292` (1.700) | "Pendente" tem dois valores na mesma tela: 1.700 na barra (sem o a caminho) e 2.200 na Distribuição (com o a caminho) | **EXPERIENCE › Números/Distribuição:** definir `pendente = planejado − realizado − a caminho` em todo lugar. Na Distribuição, mostrar "a caminho R$ 500,00 (ainda sem classe)" como linha própria antes do total, para a coluna Pendente fechar em 1.700. A nota passa a "pendente R$ 1.700,00 · a caminho R$ 500,00" | A mesma palavra com dois números induz ao erro sobre quanto falta aportar, que é a decisão central da tela (UJ-2) | EXPERIENCE |
| S4 | **HIGH** | Acessibilidade / Cor | Token `input` = `border` (`#222222` / `#e5e7eb`), CSS `.input`, `.combo`, `.lockcell`, `.inline-input` (ex.: `key-orcamento.html:196`, `key-revisao.html:200`); DESIGN `category-combobox.border`, `broker-card.input-border`, `budget-ledger.input-border`, `period-selector.border` | Borda de controle editável a **1,18:1** (escuro, sobre `#121113`) e **1,24:1** (claro): abaixo dos 3:1 da WCAG 1.4.11. Na Conta do orçamento, "Dívidas do mês" é o único valor editável e parece um número comum dentro de uma caixa fantasma. O checkbox **desmarcado** da Revisão (borda = `input`) fica quase invisível no escuro, e desmarcar é a ação principal do fluxo | Separar `input` de `border` no DESIGN: `input-dark: #666666` (3,28:1) e `input: #8b8f97` (3,24:1). `border` continua discreto para cards e divisórias. Mostrar no theme-showcase o checkbox desmarcado nos dois temas | Controle editável e estado de seleção sem contorno perceptível. A falha se repete em todos os inputs e comboboxes | DESIGN |
| S5 | MEDIUM | Tipografia | `key-aportes.html:281` (`21,40% <span class="pp">−3,60 p.p.</span>`), `:209` (`.piso`), `:200` (`.lockcell`); `key-orcamento.html:196` (`.inline-input` com padding de 10px) | Anotações dentro da célula numérica tiram o número da borda direita: "21,40% −3,60 p.p." vs. "25,40%" logo abaixo; "R$ 200,00 piso" vs. "R$ 550,00"; o cadeado em FIIs; o valor do input de Dívidas fica 11px para dentro da coluna da conta | **DESIGN › data-table:** "anotações (desvio em p.p., piso, cadeado) ficam em coluna própria ou em slot fixo à direita do número; o número sempre encosta na borda da coluna". Desvio vira coluna "Desvio" (p.p.); "piso" vira ícone ou tag em slot de largura fixa; input inline com `margin-inline-end:-10px` para alinhar o texto | Coluna numérica que não alinha na vírgula quebra a leitura vertical, que é a razão de usar mono tabular | DESIGN |
| S6 | MEDIUM | Escrita | `key-painel.html:236–238` (tags "DIVERGÊNCIA" / "AVISO"), `:317` (Fontes usa a tag de aviso "divergência"); `key-revisao.html:271` (tags "REGRA" / "SUGESTÃO"); `.tag{text-transform:uppercase}` × `.badge{text-transform:lowercase}` | Duas peças mono de 11px com regras de caixa opostas: tag em CAIXA ALTA e Selo de estado em minúscula. Em Fontes aparece a tag "DIVERGÊNCIA", mas o DESIGN (`sources-block`) manda Selo de estado "divergente" | **DESIGN › Typography/tag:** escolher uma política. Recomendo minúscula sem `text-transform` para tag e selo, porque o vocabulário fechado do EXPERIENCE já está em minúscula. No Bloco Fontes, usar `status-badge` "divergente" + valor | Dois tratamentos para o mesmo tipo de rótulo de estado e dois termos ("divergência" / "divergente") para a mesma condição | DESIGN (+ mock) |
| S7 | MEDIUM | Escrita | `key-revisao.html:271` (linha ASUN: categoria corrigida, origem ainda "sugestão") | Depois da correção manual, a tag de origem continua "sugestão", embora a categoria já não seja a sugerida | **EXPERIENCE › Revisão:** acrescentar a origem "manual" ao vocabulário ("regra", "sugestão", "sem sugestão", **"manual"**), aplicada assim que a categoria é trocada na linha | A origem mente sobre de onde veio a categoria, e a Proposta de regra depende exatamente dessa informação | EXPERIENCE |
| S8 | MEDIUM | Tipografia | `key-painel.html:287` (`style="font-size:18px"`), `key-aportes.html:188` (input 18px), `:192`/legend 16px, `key-orcamento.html:194` (linhas "=" a 16px) | Tamanhos fora da escala (16 e 18px) inventados para "número de ênfase média". O DESIGN pede `num-display` (24px) no Disponível para consumo, e o mock usa 16px | Adicionar `num-lg: 16px / 600 / 1.4` (Geist Mono, tabular) à escala. Mapear: Planejado e input de aporte → `num-lg`; linhas "=" → `num-lg`, ou `num-display` no Disponível, como o spec já diz. Decidir uma das duas e atualizar `budget-ledger.total-font` | Sem um degrau intermediário, cada mock cria o seu e a hierarquia numérica deriva entre telas | DESIGN |
| S9 | MEDIUM | Tipografia | `.dt tr.group td{font-weight:600}` (CSS compartilhado `:172`); `key-orcamento.html:257` (todas as linhas são grupo); `key-aportes.html:281–293` | No modo Resumo, toda linha é linha de grupo, então a tabela inteira sai em 600 e a linha de total ("Consumido", "Classes") perde destaque | **DESIGN › data-table:** "linha de grupo: 600 só na célula do nome; números em 400. Total: 600 + fundo `{colors.muted}`" | Quando tudo é negrito, nada é. O total deixa de ser o ponto de ancoragem da tabela | DESIGN |
| S10 | LOW | Cor / UI | `.track` (`--muted`), `.transit` (`--chart-3`), `.sw.pend` (CSS compartilhado `:160–164`) | Trilho × card = 1,18 / 1,10:1 (o fim de 100% não aparece); "a caminho" × realizado no claro = **1,74:1**; amostra "Pendente" da legenda invisível | Trilho com contorno interno de 1px em `input` (depois do S4); "a caminho" com hachura diagonal ou token próprio `progress-transit` (claro `#c4c4c4`, 3,23:1 contra o verde). Amostra "Pendente" com contorno `input` | Os números estão escritos ao lado ("a barra não é o dado"), por isso LOW. Mesmo assim, a barra não comunica a proporção que promete | DESIGN |
| S11 | LOW | Layout | `.alert` (CSS compartilhado `:145`), `key-painel.html:236–238` | Tags de largura variável ("DIVERGÊNCIA" × "AVISO") fazem as mensagens começarem em x diferentes (408 × 365px) | **DESIGN › alert-item:** slot de tag com `min-width` igual à tag mais longa do vocabulário, para alinhar a coluna da mensagem | Borda esquerda irregular numa lista que se lê em sequência | DESIGN |
| S12 | LOW | Tipografia | DESIGN `typography.tag` (11px/600), usado em "sem sugestão", "atrasado", "divergência" | Estado crítico em 11px CAIXA ALTA mono, abaixo do piso de ~12px para texto de UI | `tag.fontSize: 12px` (ou manter 11px só se cair para minúscula, conforme S6) | Legibilidade do rótulo que carrega o estado | DESIGN |
| S13 | LOW | Escrita / Cor | DESIGN › Do's ("Sinal + seta + cor em todo valor com direção") × `key-revisao.html:271` e tabela de Transações (valores só com sinal) | A regra literal mandaria pintar e pôr seta em cada valor de transação. Os mocks, com acerto, não fazem isso | Precisar a regra: "seta + cor em **variação e resultado**; valor de transação, só o sinal". Definir também o visual do toggle Resumo/Detalhado (hoje `.seg` usa `secondary`, enquanto o Seletor de leitura usa `background`) | Ambiguidade no spine que vai gerar implementações divergentes | DESIGN |

---

## Por tela

### 1. Painel principal (`key-painel.html`)

**Sistêmicos que atingem esta tela:** S1 (KPIs em 1024), S3 (pendente 1.700), S6 (tags e Fontes), S8 (Planejado 18px), S10, S11, S12.

| Sev. | Domínio | Local | Achado | Correção | Destino |
|---|---|---|---|---|---|
| MEDIUM | Escrita | `:243` × `:264` | Dois KPIs verdes com ▲ sob a mesma palavra: "Resultado do mês" (+4.673,32, fluxo de caixa) e "Resultado" (+6.482,10, investimentos). O `aria-label` diz "Resultado dos investimentos", mas o rótulo visível não diz | Rótulo visível "Resultado dos investimentos". No EXPERIENCE › IA, trocar "patrimônio, resultado e rentabilidade" por "patrimônio, resultado dos investimentos e rentabilidade" | Mock + EXPERIENCE (texto) |
| MEDIUM | Layout | `:311–322` | O Bloco Fontes está incompleto em relação ao spec: 4 fontes de 5 (falta B3 negociação) e nenhuma automática (preços, carteiras, CDI/IPCA). B3 movimentação (13/10) e consolidado (set/2026) estão atrasados em relação às demais e não têm o ponto `warning-dot`, então o estado "fonte defasada" não aparece. Está desenhado como tabela de 4 colunas em largura total, com datas à esquerda, quando o DESIGN pede lista compacta com a data mono à direita | Lista compacta (nome · Carimbo de data à direita · Selo de estado), as 5 fontes de arquivo + 3 automáticas, e pelo menos uma linha defasada com ponto de aviso. Pode ficar em meia largura ao lado de Custos fixos, como a ordem do DESIGN prevê | Mock |
| LOW | Layout | `:284–297` (`.aporte-body`) | O card Aporte do mês estica até a altura de Custos fixos e deixa ~120px de vazio antes do rodapé | `align-items:start` no grid desta fileira, ou mover o rodapé (51,11% · Carimbo) para logo abaixo da legenda | Mock |
| LOW | Escrita | `:235`, `:312` | "3 de 5" e "Ver todos (5)" repetem a contagem. O subtítulo "atualizado até e conferência de saldo por fonte" é um fragmento | Manter só "Ver todos (5)". Subtítulo: "Data de cada fonte e conferência de saldo" | Mock |

**O que funciona:** a ordem de leitura segue o DESIGN; a severidade dos avisos vem com redundância (ponto + tag + texto); o valor só fica colorido quando o sinal é o próprio dado; há Carimbo de data em todo número; a moeda aparece completa.

### 2. Revisão de transações (`key-revisao.html`)

**Sistêmicos que atingem esta tela:** S1 (painel de 1040px em 1024), **S2 (contraste da linha em foco e da Proposta de regra)**, **S4 (checkbox desmarcado)**, S6 (tags CAIXA ALTA), S7 (origem "sugestão" na linha corrigida), S12, S13.

| Sev. | Domínio | Local | Achado | Correção | Destino |
|---|---|---|---|---|---|
| MEDIUM | UI / Layout | `:212` (`.rule-strip .acts`), `:271` (`btn ghost sm` × 2) | "Ajustar condição" e "Agora não" são botões ghost com borda `input` sobre a faixa `muted`. No escuro dá 1,0:1 e eles parecem texto estático em negrito; no claro aparecem com caixa. Ou seja, um controle muda de forma conforme o tema. O DESIGN (`rule-proposal`) pede que sejam links | "Criar regra" em `button-secondary`; os outros dois como `.link` (verde, sublinhado), como o spec define | Mock |
| LOW | Acessibilidade | `:271`, `:279` | O HTML do mock modela controles com `<a>` e `<span role=…>`: Confirmar é `<a aria-disabled>`, os checkboxes e comboboxes são `span` sem `tabindex`. O Confirmar desabilitado a 50% fica com fundo a 1,47:1 (escuro) e 1,27:1 (claro), quase sumindo, embora a nota de bloqueio ao lado explique o motivo | Não é normativo. Na implementação, usar Button, Checkbox e Combobox do shadcn. Para o Confirmar bloqueado, `aria-disabled` + `aria-describedby` apontando para a nota "1 sem categoria…" | Mock (nota para implementação) |

**O que funciona:** o bloqueio vem com caminho de saída ("Escolha a categoria ou desmarque a linha."); a combobox vazia tem borda de aviso, tag e nota no rodapé (não depende só de cor); a legenda de atalhos fica visível; o total vai em `aria-live`; os checkboxes têm alvo de 24px; o resumo do lote (−1.358,38 · +1.280,00) confere.

### 3. Aportes (`key-aportes.html`)

**Sistêmicos que atingem esta tela:** **S1 (coluna Pendente cortada em 1280)**, **S3 (pendente 1.700 × 2.200)**, S4 (input do aporte, cadeado), S5 (p.p./piso/cadeado na célula), S8 (input de 18px), S9 (classes em 600), S10.

| Sev. | Domínio | Local | Achado | Correção | Destino |
|---|---|---|---|---|---|
| MEDIUM | Layout | `:~262` (Objetivos) × `:~277` (Classes) | Duas tabelas no mesmo card com grades diferentes: Sugerido, Realizado e Pendente não se alinham verticalmente (cabeçalhos em x 1131/1243/1390 × 1083/1216/1390), e por isso os subtotais "Objetivos" e "Classes" não se somam de olho | Um `colgroup` comum com larguras fixas para as três últimas colunas nas duas tabelas (ou uma tabela só, com duas seções de cabeçalho). Vale registrar em `allocation-distribution`: "objetivos e classes compartilham a grade de colunas" | Mock + DESIGN (1 linha) |
| LOW | Escrita / Tipografia | `:242` | O rótulo em `text-transform:uppercase` transforma o mês em "OUT/2026", contrariando o formato "out/2026" | Tirar o mês do rótulo ("Aporte planejado") e mostrá-lo no Seletor de período, ou envolver o mês em `<span class="num">` sem transform | Mock (regra geral no DESIGN: "datas e meses nunca em CAIXA ALTA") |

**O que funciona:** objetivos aparecem antes das classes (FR-29); a classe fora da banda tem desvio colorido e Linha de aviso com texto; a trava tem ícone e uma nota que explica a redistribuição; as somas e metas (100%) conferem; o Bloco cripto aparece como bloco.

### 4. Orçamento (`key-orcamento.html`)

**Sistêmicos que atingem esta tela:** **S1 (coluna Transações cortada em 1280)**, **S4 (input de Dívidas do mês)**, S5 (valor do input fora do alinhamento), S8 (linhas "=" em 16px × `num-display`), S9 (Gastos por grupo todo em 600).

| Sev. | Domínio | Local | Achado | Correção | Destino |
|---|---|---|---|---|---|
| MEDIUM | Layout | `:257–270` | Falta conteúdo previsto no EXPERIENCE › IA: a linha de investimento fora do total e o rodapé com **taxa de poupança** e aporte ÷ receita do trabalho. A taxa de poupança é a métrica do gate m1 | Rodapé do card Gastos por grupo: "Investimento R$ 2.800,00 (fora do consumido)" + "Taxa de poupança xx,xx% · Aporte ÷ receita do trabalho xx,xx%" em `num-body` | Mock |
| LOW | UI | `:198` (`.funded`), `:252` | "Consumo financiado por resgate" fica numa caixa com borda dentro do card, o que o DESIGN proíbe ("cards dentro de cards"). O `budget-ledger` pede separação por `section-gap` em `body-sm` | Tirar a borda e o raio; separar com 24px e uma régua `border` no topo; texto em `body-sm` | Mock |
| LOW | Escrita | `:238` (op vazio), `:343` | A primeira linha não tem o operador "+", que o EXPERIENCE prevê ("+ Receita do trabalho"). A cópia do estado negativo ("Você consumiu R$ 312,48 além do disponível…") diverge do spec ("Gasto acima do disponível em R$ 312,48."). A frase inteira em vermelho de 12px pesa mais que o próprio valor | Pôr "+" na primeira linha. Usar a cópia do EXPERIENCE em `muted-foreground`, deixando o vermelho só no valor "−R$ 312,48" (que já tem ▼ e sinal) | Mock |

**O que funciona:** a conta aberta com operador em coluna própria, mono tabular e régua sobre as linhas "=" lê como planilha de trader, e bem. A linha "Consumo financiado por resgate" explica o caso real (notebook) com o contrafactual. O estado negativo usa sinal, seta e cor.

---

## Resumo

| Severidade | Sistêmicos | Só no mock | Total |
|---|---|---|---|
| HIGH | 4 (S1–S4) | 0 | **4** |
| MEDIUM | 5 (S5–S9) | 5 | **10** |
| LOW | 4 (S10–S13) | 6 | **10** |
| **Total** | 13 | 11 | **24** |

**Leitura geral:** a base é fiel à personalidade e ao contrato. A densidade fica arejada, o verde e o laranja são usados com disciplina, os números são completos e tabulares, e a aritmética confere em todas as telas. Os quatro bloqueios não são de estética:

1. Conteúdo cortado na largura alvo de 1280px, além do piso de 1024px.
2. Dois pares de texto abaixo de AA, criados pelos tokens de linha destacada e pela faixa `muted`.
3. Um termo ("pendente") com dois valores na mesma tela.
4. Contorno de input e de checkbox abaixo de 3:1.

Os quatro se corrigem nos spines, com poucos tokens novos (`row-highlight`, `input` separado de `border`, `num-lg`) e algumas regras de layout e vocabulário. Os mocks herdam a correção pelo CSS compartilhado.

## Veredito

**Block.** Há 4 achados HIGH. Os MEDIUM e LOW ficam na tabela como trabalho a fazer.
