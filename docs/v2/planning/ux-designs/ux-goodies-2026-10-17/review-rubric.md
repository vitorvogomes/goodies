# Revisão do par de spines: Goodies v2

- **DESIGN.md:** `docs/v2/planning/ux-designs/ux-goodies-2026-10-17/DESIGN.md`
- **EXPERIENCE.md:** `docs/v2/planning/ux-designs/ux-goodies-2026-10-17/EXPERIENCE.md`
- **Fontes conferidas:** `.memlog.md`, `prds/prd-goodies-2026-10-17/prd.md` (UJ-1..5, §3 Glossário, FR-1..36), `briefs/brief-goodies-2026-10-17/brief.md` (só a resolução do caminho), mocks `.working/key-painel.html`, `key-revisao.html`, `key-aportes.html` e `key-orcamento.html`, e `.working/color-themes-2.html`.
- **Rodado em:** 2026-10-17

## Veredito geral

O par é enxuto e quase todo extraível. Todas as 37 componentes estão nos dois spines com o mesmo nome. Toda referência `{token}` resolve, e cada cor tem par claro/escuro com hex. As 5 jornadas têm passos numerados, clímax e tropeços. O que impede usar o par como contrato são dois termos de dinheiro sem definição única: **realizado/a caminho/pendente** e **consumido**. Os mocks e o próprio spine dão números diferentes para eles. Somam-se três problemas: as key-screens não estão ligadas aos spines, a ordem do Painel diverge do mock, e o Selo de estado "divergente" fica abaixo de AA no escuro. A triagem anotada no memlog (linha 38) ainda não chegou aos spines. Feito isso numa rodada de Update, o par está pronto para arquitetura e stories.

**Contagem:** crítico 0 · alto 5 · médio 12 · baixo 15.

---

## 1. Cobertura de fluxos: adequado

Conferido: UJ-1 a UJ-5 do PRD §2.1, todas com protagonista (Vitor), passos numerados, **Clímax** e Falhas/Tropeços. Também conferi que cada FR do PRD aparece em pelo menos um passo ou falha de jornada.

### Achados
- **[médio]** O FR-18 (casar custo fixo: Confirmar/Trocar/"2 candidatas") e o FR-25 (input "Saldo que vejo na corretora") não aparecem em nenhum passo de Key Flow. O PRD liga o FR-18 a UJ-2/UJ-3, mas a lógica de casamento e a ambiguidade de candidatas só existem na tabela de componentes (EXPERIENCE › Key Flows; Component Patterns › Lista de custos fixos com casamento, Cartão de corretora). *Correção:* na UJ-3, antes do passo 4, incluir um passo que resolve "2 candidatas" e confirma o casamento. Na UJ-1, incluir uma falha "caixa em corretora divergente".
- **[médio]** Na UJ-5, o passo 1 diz "A base vai até 30/06/2026" e mesmo assim manda importar e fechar **jun**/2026. O passo 2 diz que só o que é "anterior a jun/2026" vira existente. Se a base cobre junho, junho é duplicado ou não precisa de recuperação. O FR-7 fecha jul/2024–mai/2026 em bloco e recupera jun–out (EXPERIENCE › UJ-5, passos 1–2; State Patterns › Base vazia). *Correção:* trocar por "A base vai até 31/05/2026" ou dizer explicitamente que junho é reaberto e reimportado.
- **[baixo]** O clímax da UJ-1 ("Conciliação: Tudo bate") depende do consolidado B3, mas o fluxo só importa negociação (UJ-1, passo 7). *Correção:* deixar claro que compara com o último consolidado importado (set/2026). A mensagem de estado já é parametrizada.
- **[baixo]** No passo 2 da UJ-2, "A Conta do orçamento recalcula" acontece fora da tela onde Vitor está (Aportes). O mock mostra a linha "Disponível para consumo depois do aporte" em Aportes, mas a tabela de IA › Aportes não a lista. *Correção:* incluir essa linha no conteúdo da aba Aportes.

## 2. Completude de tokens: adequado

Conferido: todos os tokens do frontmatter do DESIGN.md e todas as referências `{…}` dos dois arquivos. Tudo resolve; o único "não resolvido" é o marcador de convenção `{colors.x}`. As 39 cores têm par `-dark` e hex. Recalculei a tabela de contraste: bate com o declarado (±0,02), exceto as pílulas, que dependem da base do tint.

### Achados
- **[alto]** O **Selo de estado**, nas variantes aviso e divergência, usa texto `{colors.warning}`/`{colors.negative}` sobre a pílula `{colors.secondary}`. No escuro, divergência dá **4,17:1** (#fb605c sobre #333333), abaixo de AA para texto de 11px. Aviso dá 4,78 (claro) e 4,91 (escuro), no limite. Nenhum desses pares está na tabela de contraste. O mock (`key-painel.html`, `.badge.warn`) usa fundo tingido, não `secondary` (DESIGN › Components › Selo de estado; frontmatter `status-badge`). *Correção:* adotar o fundo tingido do Selo de variação (10%/14%) nas variantes aviso e divergência e acrescentar os pares à tabela.
- **[médio]** `transaction-review.row-selected: {colors.accent}` combinado com "abre com **todas as linhas marcadas**" deixa todas as linhas em `accent`. O texto secundário das linhas (tipo de movimento "Débito", em `muted-foreground`) dá 4,17:1 no claro e 3,56:1 no escuro sobre `accent`. O mock não pinta a linha marcada (DESIGN frontmatter `transaction-review`; EXPERIENCE › Revisão de transações). *Correção:* remover o fundo de linha marcada (o checkbox já carrega o estado) ou proibir `muted-foreground` em linha marcada. Registrar o par na tabela.
- **[médio]** O trecho "a caminho" da Barra de progresso (`{colors.chart-3}`) sobre o trilho `{colors.muted}` dá 2,94:1 no claro e 2,65:1 no escuro, abaixo de 3:1 para não-texto. Os quatro números escritos ao lado atenuam, mas os segmentos continuam indistintos (DESIGN › Components › Barra de progresso). *Correção:* trocar o trilho, hachurar o trecho ou separá-lo com 1px de `{colors.card}`.
- **[médio]** Faltam tokens do Sidebar do shadcn: `sidebar-primary`, `sidebar-primary-foreground`, `sidebar-accent-foreground` e `sidebar-ring`. O DESIGN substitui `globals.css` inteiro, então esses tokens ficam sem valor ou com o neutro do shadcn, fora da paleta darkmatter (frontmatter `colors`). *Correção:* definir os quatro com par `-dark`, ou declarar o mapeamento (ex.: `sidebar-ring` = `ring`).
- **[baixo]** Há valores crus no frontmatter: `progress-bar.height: 8px`, `change-pill.tint-light/-dark`, e `fixed-costs-list.base: data-table`, que não é token nem referência. Na prosa há medidas em pixel sem token: ponto de 7px com halo de 22%, ícone de 28px, largura mínima de 66px. *Correção:* usar `{spacing.2}` onde couber e transformar `base` em nota. As demais medidas podem ficar na página theme-showcase.
- **[baixo]** `chart-2` × `chart-3` dá 1,49:1 no claro e 1,69:1 no escuro entre si. Nas barras agrupadas (gastos: período × anterior), a promessa do Accessibility Floor ("séries também por estilo de linha e legenda") não se aplica, porque barra não tem estilo de linha. *Correção:* contorno ou hachura na barra de referência, ou rótulo direto.

## 3. Cobertura de componentes: adequado

Conferido: as 37 componentes de DESIGN › Components e de EXPERIENCE › Component Patterns pareiam 1:1, com regras reais nos dois lados. Também procurei nomes usados na IA, nos estados, nos fluxos e nos mocks que não têm linha própria.

### Achados
- **[médio]** Dois blocos compostos do Painel não têm especificação: o **Aporte do mês** (planejado, barra, quatro números, linha "a caminho", "% realizado", link "Ver aportes") e o **Custos fixos** resumido (só pendente/vencendo/atrasado mais a linha recolhida "N pagos", com o total "pago X de Y"). A Lista de custos fixos com casamento é outra peça, a de Caixa (EXPERIENCE › IA › Painel; DESIGN › Layout, itens 4–5; `key-painel.html`). *Correção:* criar as linhas "Resumo do aporte" e "Resumo de custos fixos" nos dois spines, com quais itens entram, a ordem e o destino do clique.
- **[baixo]** O mock mostra elementos sem visual especificado: o alternador **Resumo/Detalhado** no cabeçalho da Tabela de dados (o comportamento está no EXPERIENCE, o visual não está no DESIGN), o input grande de **aporte planejado** em Aportes e a tela de **login**. *Correção:* uma frase em Tabela de dados ("alternador no padrão do Seletor de leitura") e uma linha para o input do aporte.
- **[baixo]** O Checklist de fechamento e o Assistente de recuperação marcam "ok/feito" com check `{colors.positive}`. Isso contradiz a regra do Selo de estado "Nunca verde: estado bom não é ganho". *Correção:* escolher uma regra (check neutro em `foreground`, ou exceção explícita para check de tarefa).

## 4. Cobertura de estados: adequado

Conferido em cada superfície da IA: carga inicial, vazio, erro de leitura, fonte defasada, preço sem fonte, sessão expirada, mês fechado/ajuste, IPCA ausente, antes de jul/2024 e vazios de Ajustes. Foco e teclado estão em Interaction Primitives. Offline e permissão negada não se aplicam (local, usuário único).

### Achados
- **[médio]** Não há estado para **falha ao gravar**: Confirmar import, Confirmar lote, Salvar formulário, Fechar/Reabrir mês, Desfazer lote, gravar dívidas do mês. "Erro ao carregar" cobre só leitura, e o Toast é só para sucesso (EXPERIENCE › State Patterns; Voice, linha "erro fica no bloco"). *Correção:* uma linha "Falha ao gravar": mensagem no próprio painel ou diálogo, nada perdido, "Tentar de novo", foco no botão.
- **[médio]** Faltam dois estados nas telas que consomem os dados: **Conta do orçamento sem aporte planejado** (a linha "− Aporte planejado" mostra R$ 0,00 ou "não definido"? O Disponível conta como?) e **Aportes sem metas** (a Distribuição sem base; hoje só existe o vazio da aba Ajustes › Metas). *Correção:* duas linhas em State Patterns.
- **[baixo]** Na Revisão, a tag de origem de uma linha corrigida não está definida. Pelo FR-12 vira "manual", mas o mock mantém "sugestão" na linha ASUN corrigida. Isso importa para "Reaplicar regras" ("categorias manuais não serão alteradas"). *Correção:* acrescentar "manual" ao vocabulário da tag de origem e dizer quando ela troca.
- **[baixo]** Também faltam: progresso de leitura de xlsx grande no Hub e o filtro sem resultados ("Só sem categoria" com 0 linhas e o filtro de texto). *Correção:* duas linhas curtas.

## 5. Cobertura de referências visuais: fraco

Conferido: `imports/` está vazio, e `mockups/` e `wireframes/` não existem. Em `.working/` há 6 HTMLs. O DESIGN só cita `.working/color-themes-2.html` (Colors), onde declara "spines vencem" uma vez. O EXPERIENCE não cita nenhum.

### Achados
- **[alto]** As quatro key-screens (`.working/key-painel.html`, `key-revisao.html`, `key-aportes.html`, `key-orcamento.html`) não estão ligadas a nenhum spine. Quem consome o par não vai saber que existem, e `.working/` é diretório de trabalho (EXPERIENCE › IA e Component Patterns; DESIGN › Layout). *Correção:* promover para `mockups/` e citar cada uma na linha da IA ou do componente que ilustra (Painel; Revisão de transações + Proposta de regra; Distribuição do aporte; Conta do orçamento), mantendo o "spines vencem" já declarado.
- **[alto]** O layout do Painel diverge entre spine e mock, e a triagem ainda não foi feita. O **DESIGN › Layout** diz: linha 3 em **3 colunas**; Aporte do mês em **largura total**; **Custos fixos | Bloco Fontes** lado a lado. O **mock** mostra: linha 3 com **4 cartões** (Rentabilidade nominal e real separadas); **Aporte | Custos fixos** lado a lado; Fontes como **tabela em largura total**. A ordem de leitura bate com o memlog (proposta 1), mas a grade não. *Correção:* decidir e atualizar DESIGN › Layout (e a linha Painel da IA). A versão do mock parece melhor (o Bloco Fontes como tabela precisa de largura); se for a escolhida, rentabilidade nominal × real em cartões separados entra no spine.
- **[médio]** O Bloco Fontes do mock lista só 4 fontes: falta B3 negociação e faltam as automáticas (preços, carteiras, CDI/IPCA), que o EXPERIENCE exige. O mock também escreve "divergência em R$ 37,20" onde o vocabulário fechado do Selo de estado diz "divergente" (EXPERIENCE › Bloco Fontes; DESIGN › Selo de estado). *Correção:* corrigir o mock ou registrar a exceção (valor ao lado do selo).
- **[baixo]** A `[ASSUMPTION]` em Shapes ("confirmar nas key-screens") já pode ser resolvida: os mocks usam 12px nos cards e 10px nos controles, ou seja, a base 0,75rem. `color-themes-1.html` fica órfão, o que é aceitável para exploração descartada. *Correção:* remover a suposição e citar o mock como confirmação.

---

## 6. Excesso e superespecificação: adequado

O par não reescreve persona nem escopo. A coluna de FRs na IA é rastreabilidade útil. A tabela de avisos acrescenta mensagem e ação ao FR-14. A voz editorial ficou no DESIGN; o EXPERIENCE é seco. O excesso que existe é **duplicação entre os dois arquivos**, e é justamente onde a divergência apareceu.

### Achados
- **[baixo]** Três regras estão escritas duas vezes: a ordem do Painel (DESIGN › Layout e EXPERIENCE › IA), o vocabulário do Selo de estado (DESIGN › Components e EXPERIENCE › Component Patterns, lista literal) e as regras de moeda e mono (DESIGN › Typography e EXPERIENCE › Números). *Correção:* um lugar de verdade para cada uma (ordem e vocabulário no EXPERIENCE, tom do selo no DESIGN), com o outro arquivo apontando.
- **[baixo]** Brand & Style traz instruções de migração de código (`--gain` → `--positive`, mapa `@theme inline`). É útil para a story, mas não é postura de marca. *Correção:* mover para uma nota curta em Colors ou para a arquitetura.

## 7. Disciplina de herança: fraco

Conferido: o `sources` do EXPERIENCE resolve (PRD e brief); o DESIGN não tem `sources`, o que o spec permite. Os nomes de componente são idênticos entre os arquivos. As referências a token resolvem. Os termos do glossário foram comparados com o PRD §3. Os números dos mocks foram recalculados.

### Achados
- **[alto]** **Realizado / a caminho / pendente** não têm leitura única.
  - O PRD §3 diz que o realizado **total** conta quando o dinheiro sai do Nubank, então "a caminho" está dentro dele. O State Patterns concorda ("Entra no aporte realizado total").
  - Mas a Barra de progresso põe "a caminho" **depois** do realizado como trecho separado e manda escrever "os quatro números" (DESIGN e EXPERIENCE › Barra de progresso), o que trata os dois como disjuntos.
  - Os mocks seguem a leitura disjunta: o Painel mostra Realizado R$ 2.300,00 + A caminho R$ 500,00 + Pendente R$ 1.700,00 e "51,11% realizado". O Resultado do mês, na mesma tela, mostra investimento R$ 2.800,00.
  - Em Aportes, o mesmo mock tem pendente **R$ 1.700,00** no cabeçalho e **R$ 2.200,00** no rodapé, que é a soma por classe.

  *Correção:* fixar no spine:
  - Total: "Realizado R$ 2.800,00, dos quais R$ 500,00 a caminho". A barra mostra o realizado em ativo mais o trecho a caminho, os dois dentro do realizado. Pendente = R$ 1.700,00.
  - Por classe e ativo, o realizado exclui o a caminho. O rodapé da Distribuição concilia: soma por classe R$ 2.300,00 + a caminho R$ 500,00 = R$ 2.800,00.
- **[alto]** **Consumido** não está definido nos spines nem no glossário do PRD (o FR-17 diz só "quanto já foi gasto"). Como o Disponível já desconta os custos fixos inteiros, Restante = Disponível − Consumido conta os custos fixos duas vezes se o consumido incluí-los. O mock define consumido como "gastos do mês sem os custos fixos" (9.494,67 − 2.582,30 = 6.912,37). Não está dito o que acontece com dívidas pagas no mês, nem a fórmula de "Consumo financiado por resgate" (EXPERIENCE › Conta do orçamento; memlog linha 38). *Correção:* definir na linha da Conta do orçamento: consumido = gastos do mês − transações casadas a custos fixos (e a dívidas, se for o caso); consumo financiado por resgate = min(resgates, consumido − ...). Levar a definição ao PRD §3.
- **[médio]** **Gastos por grupo** no Orçamento: a IA diz "gastos por grupo → subcategoria, com investimento em linha própria fora do total", ou seja, todos os gastos do FR-16. O mock mostra "% do consumido": tira os custos fixos (Casa = R$ 120,00, sem aluguel nem condomínio) e não tem a linha de investimento (EXPERIENCE › IA › Orçamento; `key-orcamento.html`). *Correção:* escolher uma das duas e registrar.
- **[médio]** O período da **rentabilidade no Painel** não está especificado. O mock mostra "XIRR · desde o início" com o seletor em out/2026. O FR-22 só permite leitura por período depois do primeiro mês fechado na v2 (EXPERIENCE › IA › Painel; Cartão KPI). *Correção:* "No Painel, rentabilidade = desde o início até o fim do período selecionado", com rótulo explícito.
- **[baixo]** O título da UJ-3 não é literal: o spine usa "Vitor olha para trás e fecha o mês." e o PRD, "Vitor olha para trás." *Correção:* usar o nome do PRD; o fechamento já é um passo.
- **[baixo]** Há abreviações de nomes de componente: "Distribuição" (State Patterns › Bloco cripto; Accessibility › Anúncios; UJ-2), "Central" (State › Ajuste em mês fechado), "Sino", "Hub", "Revisão" (fluxos). "Valor em `negative`" (State › Disponível negativo) não usa `{colors.negative}`. *Correção:* nome completo na primeira menção de cada seção e referência de token no formato `{…}`.
- **[baixo]** **Shift+Espaço** ficou decidido sem sinalização. O memlog (linha 25) pede "confirmar combinação exata na implementação" porque o Vitor citou Shift+Enter. *Correção:* marcar `[ASSUMPTION]`, como já foi feito com a tecla C.

## 8. Adequação de forma: adequado

O DESIGN tem as 8 seções na ordem canônica. O EXPERIENCE tem todas as seções padrão obrigatórias, Inspiration & Anti-patterns (que se justifica: shadcn/tweakcn/natus e a planilha rejeitada) e uma seção inventada, "Números e formatação financeira", que se justifica por ser regra de carga num app financeiro.

### Achados
- **[médio]** Falta **Responsive & Platform** apesar de haver breakpoints: alvo ≥ 1280px e "entre 1024 e 1279px funciona sem quebrar". Nenhuma regra diz o que se adapta. Com `drawer-width-wide` = 1040px, a Revisão **passa da viewport** em 1024px. A grade de 4 colunas do Painel fica com cerca de 170px por cartão em 1024px, para "R$ 68.695,66" em 24px mono (DESIGN › Layout; EXPERIENCE › Foundation). *Correção:* criar a seção com a faixa 1024–1279: Revisão em `min(1040px, 100vw − 48px)` e KPIs em 2 colunas.
- **[baixo]** "Números e formatação financeira" repete parte de DESIGN › Typography (ver o achado da seção 6). Inspiration aparece depois de Key Flows, o que é aceitável. *Correção:* manter a seção, mas tirar a repetição.

---

## Notas mecânicas

- **Frontmatter:** os dois arquivos estão com `status: draft`. O EXPERIENCE não tem `name` (o exemplo traz). O DESIGN não tem `sources`, o que é opcional, mas ajudaria na rastreabilidade com o memlog.
- **Referências cruzadas:** todas resolvem. `{colors.x}` é só o marcador de convenção. `fixed-costs-list.base: data-table` não é referência válida. `accent-foreground` está definido e não é usado (inofensivo, herança do shadcn).
- **Contraste:** a tabela do DESIGN confere com o recálculo (±0,02). Nas pílulas, o declarado difere um pouco do recalculado (negativo claro: 5,07 declarado, 4,95 calculado; aviso escuro: 6,10 declarado, 5,90 calculado), conforme o tint seja aplicado sobre `card` ou `background`. Vale dizer a base. Faltam na tabela: positivo na pílula (4,87 claro), aviso/negativo sobre `secondary`, `muted-foreground` sobre `accent`, e o trecho a caminho sobre o trilho.
- **Aritmética dos mocks:** está coerente. Painel: receitas − gastos − investimento = R$ 4.673,32. Orçamento: R$ 8.405,59 e R$ 1.493,22; grupos somam R$ 6.912,37 e 100,00%. Aportes: 1.300 + 3.200 = 4.500; FIIs travado e "R$ 2.400,00 restantes" conferem; reserva 6 × 3.412,40 = 20.474,40 e 92,31%. Revisão: 12 linhas, 8/3/1, −R$ 1.358,38. A única incoerência real é a do realizado/pendente (seção 7).
- **Desvios do memlog (linha 38) ainda não triados nos spines:** "a caminho por classe" e "consumido sem custos fixos" estão nos dois achados altos da seção 7. "B3 até 13/10" e "divergência na MEI" são coerentes entre os mocks. O "sino 5" do mock e o "Sino mostra 2" da UJ-1 são cenários diferentes, não conflito.
- **Mermaid:** nenhum diagrama. Nada a validar.
