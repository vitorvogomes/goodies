---
title: "EXPERIENCE — Goodies v2"
status: final
created: 2026-10-17
updated: 2026-10-18
name: Goodies
sources:
  - ../../prds/prd-goodies-2026-10-17/prd.md
  - ../../briefs/brief-goodies-2026-10-17/brief.md
---

# EXPERIENCE — Goodies v2

## Foundation

Web app desktop de uma superfície só (Next.js App Router + shadcn/ui + Radix + Tailwind v4), usuário único, ambiente local. `DESIGN.md` é o visual; este arquivo, a experiência; os nomes de componentes são idênticos nos dois.

- **Ritual central:** importar, revisar as transações em lote e ler o painel (PRD §1).
- **Postura:** o app informa e sugere, nunca executa. Nenhum botão move dinheiro; o texto diz "sugerido"/"planejado", nunca "comprar"/"executar".
- **Densidade:** resumo primeiro; a visão detalhada, com tudo à vista, fica a um clique.
- **Tema:** segue o sistema, com Switch de tema manual.
- **Plataforma:** alvo ≥ 1280px; 1024–1279px degrada com graça; abaixo de 1024px (ou com zoom de 200%) reflui para uma coluna, best-effort, sem cortar nada. Mobile não é objetivo da v2.0. Regras em `DESIGN.md` › Layout & Spacing.
- **Login:** a tela da v1 (JWT próprio), mesmo fluxo, com o visual novo.
- **Mockups aprovados** em `mockups/`, citados nas seções que ilustram. Em conflito, os spines prevalecem.

## Information Architecture

- **Barra lateral:** Visão geral · Caixa · Investimentos · Ajustes, mais o botão **Importar**, fixo e sempre visível.
- **Barra superior:** Seletor de período (global, mês atual por padrão), Sino de avisos e Switch de tema.
- **Contexto na URL:** área, aba, período e leitura (`/caixa/orcamento?periodo=2026-10`, `&leitura=tri`). Link, recarga e voltar do navegador mantêm o contexto.

Sub-telas são **Abas**; Hub de import, Revisão de transações, Central de avisos e Formulário em painel lateral são **painéis laterais** (FR-36). Tudo fica a no máximo dois cliques do Painel principal.

| Área | Aba | Conteúdo | FRs |
|---|---|---|---|
| Visão geral | **Painel** (Painel principal) · [`mockups/key-painel.html`](mockups/key-painel.html) | Avisos; resultado do mês + disponível para consumo; patrimônio, resultado dos investimentos, rentabilidade nominal e real; Resumo do aporte ao lado do Resumo de custos fixos; Bloco Fontes. Sem gráfico. Assistente de recuperação no topo enquanto a base estiver incompleta. Ordem e grade em `DESIGN.md` › Layout & Spacing | FR-13, FR-3, FR-5, FR-14, FR-7 |
| Visão geral | **Histórico** | Seletor de leitura; período × anterior × média 12m; receitas e gastos por categoria; aporte planejado × realizado; crescimento do patrimônio = aporte + resultado; rentabilidade por classe, com o ativo de melhor desempenho em destaque; taxa de poupança; os três gráficos; Fechamento de mês | FR-34, FR-32, FR-33, FR-22, FR-20 |
| Caixa | **Transações** | Data, descrição, valor, tipo de movimento (rótulo em texto), categoria, origem da categoria, pagador, conta. A linha expandida mostra fonte, lote e regra aplicada | FR-12, FR-16, NFR-2 |
| Caixa | **Orçamento** · [`mockups/key-orcamento.html`](mockups/key-orcamento.html) | Conta do orçamento; ao lado, **Consumido por grupo** → subcategoria (% do consumido); rodapé com custos fixos pagos, gastos do mês, investimento (fora dos gastos), taxa de poupança e aporte ÷ receita do trabalho | FR-15, FR-16, FR-17, FR-20 |
| Caixa | **Custos fixos** | Lista de custos fixos com casamento | FR-18 |
| Investimentos | **Posições** | Seletor de leitura; classe → ativo: aplicado, valor atual, resultado, alocação × meta ± banda, XIRR nominal × real (% a.m. por ativo, exceto RF e Cripto); bloco cripto; caixa em corretora e a caminho. RF: "{x}% do CDI · CDI até dd/mm/aaaa"; debênture: "valorada pela taxa cadastrada"; preço manual: Selo de estado "manual" | FR-21–FR-25, FR-27 |
| Investimentos | **Aportes** · [`mockups/key-aportes.html`](mockups/key-aportes.html) | Input do aporte planejado + linha "Disponível para consumo depois do aporte"; andamento (realizado total, pendente, Barra de progresso); Distribuição do aporte | FR-28–FR-31 |
| Investimentos | **Conciliação** | Cartões de corretora; abaixo, posições × consolidado B3 e × scan das carteiras (app, origem, diferença, Selo de estado, Carimbo de data) | FR-25, FR-26 |
| Ajustes | 8 abas (tabela abaixo) | Cadastros editáveis | FR-8, FR-10, FR-11, FR-24, FR-27, FR-35 |
| Global | **Hub de import** (painel lateral) | Upload multi-fonte, prévia, confirmação, Bloco Fontes, Histórico de imports | FR-1–FR-4, FR-6 |
| Global | **Revisão de transações** (painel lateral largo) · [`mockups/key-revisao.html`](mockups/key-revisao.html) | Transações novas do lote; Proposta de regra | FR-9, FR-10, FR-12, FR-24 |
| Global | **Central de avisos** (painel lateral) | Lista única de avisos com tipo, mensagem e ação | FR-14 |

"Custos fixos" aparece em **Caixa** (estado do mês) e em **Ajustes** (cadastro). Em Ajustes, valor único se edita inline; criar ou editar item com vários campos usa o Formulário em painel lateral.

| Aba | Conteúdo e regras | Estado vazio |
|---|---|---|
| Categorias | Árvore grupo › subcategoria com tipo de movimento. Renomear avisa "reflete em todo o histórico". Com transações, só "Arquivar". Arquivadas ocultas; "Mostrar arquivadas" as exibe esmaecidas | "Nenhuma categoria. Crie o primeiro grupo." · Nova categoria |
| Regras | Condição "descrição contém", categoria, ativa/inativa, prévia das afetadas. **Reaplicar regras**: período → prévia antes × depois, "{n} categorias manuais não serão alteradas", "{n} transações em meses fechados: o resumo congelado não muda". Grava ao confirmar | "Nenhuma regra. Regras nascem na revisão quando você corrige uma categoria." |
| Custos fixos | Nome, valor, vencimento (dia), categoria | "Nenhum custo fixo. Cadastre para acompanhar pago × pendente." · Novo custo fixo |
| Contas | Conta, CPF/MEI, fonte | "Nenhuma conta. Cadastre a conta Nubank CPF." · Nova conta |
| Objetivos | Nome, valor-alvo, prazo, destino (Q1): uma caixinha ou conta de investimento existente, escolhida numa lista (provisório até a arquitetura). Reserva de emergência é fixa: alvo = multiplicador × custos fixos; o multiplicador (6× por padrão) se edita aqui, no item Reserva de emergência | "Nenhum objetivo além da reserva de emergência." · Novo objetivo |
| Debêntures | Emissor, taxa, início, vencimento | "Nenhuma debênture. Cadastre para valorar pela taxa." · Nova debênture |
| Metas | Classe → ativo: %, banda (p.p.), piso (R$). Cada nível soma 100%; senão, "Soma em {x}%. Ajuste para 100%." e Salvar desabilitado | "Nenhuma meta. Sem metas, a distribuição do aporte não tem base." · Definir metas |
| Preços manuais | Só ativos sem fonte de mercado; valor + data | "Nenhum ativo sem fonte de mercado." |

## Voice and Tone

"Você", pt-BR, direto e técnico: o que aconteceu e o que fazer, sem exclamação, emoji ou celebração.

| Faça | Não faça |
|---|---|
| "Saldo divergente em R$ 37,20. Ver transações." | "Ops! Parece que algo não bateu 😕" |
| "41 transações confirmadas. 2 continuam a revisar." | "Sucesso! Suas transações foram salvas!" |
| "Importe o relatório B3 a partir de 14/10/2026." | "Seus dados da B3 podem estar desatualizados." |
| "R$ 68.695,66" | "R$ 68,7 mil" · "68.7k" |
| "Não foi possível carregar as posições. Tentar de novo." | "Erro 500" · "Internal Server Error" |

**Rótulos curtos em minúscula** (regra de caixa em `DESIGN.md` › Typography). A tag da Linha de aviso nomeia a **severidade** (substantivo: "aviso", "divergência"); o Selo de estado nomeia o **estado** (adjetivo ou particípio: "divergente", "conferido", "pago").

**Avisos (FR-14).** Severidade **divergência**, em vermelho: saldo divergente, caixa em corretora divergente, posição divergente da origem. Todos os demais são **aviso**, em laranja.

| Tipo | Mensagem | Ação |
|---|---|---|
| arquivo já importado | "Arquivo já importado: {nome}. 0 transações novas." | Dispensar |
| lacuna | "Lacuna em {fonte}: {dd/mm/aaaa} a {dd/mm/aaaa}." | Importar |
| transferência não coberta | "R$ {valor} a caminho da {corretora}. Importe o relatório B3 a partir de {dd/mm/aaaa}." | Importar |
| fonte desatualizada | "{Fonte} sem import desde {dd/mm/aaaa}." | Importar |
| saldo divergente | "Saldo divergente em R$ {valor} na conta PF." | Ver transações |
| CSV sem conferência | "CSV importado sem conferência de saldo. Só o OFX permite conferir." | Importar OFX |
| transações a revisar | "{n} transações a revisar." | Revisar |
| custo fixo vencendo ou atrasado | "{Custo} vence em {dd/mm/aaaa}." · "{Custo} atrasado desde {dd/mm/aaaa}." | Ver custos fixos |
| aporte pendente | "Faltam R$ {valor} do aporte de {mês}." | Ver aportes |
| classe fora da banda | "{Classe} em {x,xx}%, meta {y,yy}% ± {b} p.p." | Ver aportes |
| caixa em corretora divergente | "Caixa na {corretora}: calculado R$ {a}, informado R$ {b}." | Ver conciliação |
| posição divergente da origem | "{Ativo}: {q} no app, {q'} no consolidado B3." | Ver conciliação |
| ajuste em mês fechado | "Ajuste em {mês}, já fechado. O resumo congelado não mudou." | Reabrir mês |
| mês aberto há mais de 10 dias | "{Mês} segue aberto. Confira o saldo e feche." | Ir para Histórico |

"Importar" abre o Hub; as outras ações levam à tela já filtrada. **Vazios e erros:** uma frase com o porquê + uma ação; nunca código HTTP ou stack. Falha de fonte externa não é erro: vira dado desatualizado com Carimbo de data.

## Component Patterns

Comportamento; o visual está em `DESIGN.md` › Components.

| Componente | Uso | Regras de comportamento |
|---|---|---|
| **Barra lateral** | Global | Item ativo = área da rota. Importar abre o Hub sobre qualquer tela. Não recolhe na v2.0; abaixo de 1024px, empilha acima do conteúdo. |
| **Barra superior** | Global | Fixa no scroll. O título da área fica no conteúdo. |
| **Seletor de período** | Global | Escolhe o mês (na URL), mostrado como "out/2026" + Selo de estado. ‹ › navegam; o popover lista os meses com Selo de estado "aberto", "fechado" ou "ajuste". Trocar mantém a aba. Meses futuros e anteriores a jul/2024 desabilitados. |
| **Seletor de leitura** | Posições, Histórico | **Mês · Trimestre · Ano · Desde o início**, ancorado no mês do Seletor de período (trimestre que o contém; ano até ele; início até ele). Padrão: Mês; na URL; vale só para a aba. Em Posições, muda resultado e XIRR do período; aplicado e valor atual seguem o fim do mês. No Histórico, define o intervalo comparado; "Desde o início" mostra o acumulado, sem comparação. |
| **Sino de avisos** | Global | Contador de **todos** os avisos ativos (aria-live polite); abre a Central de avisos. |
| **Central de avisos** | Painel lateral | Divergências, depois avisos; mais recentes primeiro. A ação leva à tela filtrada e fecha o painel. "Dispensar" esconde até a condição mudar (ex.: outro valor divergente). O aviso some sozinho quando a condição acaba. |
| **Switch de tema** | Global | Sistema / Claro / Escuro (next-themes, no navegador). Troca instantânea. |
| **Cartão KPI** | Painel, Histórico | Valor completo + Carimbo de data. Clique leva ao detalhe (Patrimônio → Posições; Disponível → Orçamento; Rentabilidade → Posições). Variação só se o período anterior existe. No Painel, rentabilidade = XIRR **desde o início até o fim do período selecionado**, rotulado "XIRR · desde o início"; a real traz o carimbo do IPCA. |
| **Linha de aviso** | Central de avisos, Painel | Mensagem + uma ação. No Painel, até 3 (divergências primeiro) + "Ver todos ({n})", com {n} = total de avisos ativos, o mesmo do Sino de avisos. |
| **Resumo do aporte** | Painel | Planejado; "Realizado R$ {total} · dos quais R$ {a caminho} a caminho"; Barra de progresso com legenda realizado em ativo · a caminho · pendente; linha "a caminho" com a corretora e "importe o relatório B3 a partir de dd/mm/aaaa"; com classe fora da banda, Linha de aviso compacta "{n} classes fora da banda" → **Ver aportes** (FR-13). Clique no cabeçalho → Aportes. |
| **Resumo de custos fixos** | Painel | Cabeçalho "pago R$ {x} de R$ {y}". Só atrasados, vencendo e pendentes, nessa ordem, com data e Selo de estado; pagos recolhidos em "{n} pagos". Rodapé "{n} a pagar · R$ {valor}". Clique → Caixa › Custos fixos. |
| **Bloco Fontes** | Painel, Hub de import | Uma linha por fonte: as 5 de arquivo (Nubank CPF e MEI; B3 movimentação, negociação, consolidado) e as automáticas (preços, carteiras, CDI/IPCA), com Carimbo de data. Conta Nubank PF: "conferido" + data, ou "divergente" + valor (leva às transações candidatas); a linha do MEI mostra só o atualizado até (conta sempre zerada, sem conferência). Defasada (FR-3): ponto de aviso. Fonte de arquivo abre o Hub. |
| **Tabela de dados** | Todas as listas | Modos **Resumo** (grupos recolhidos) e **Detalhado** (tudo expandido, todas as colunas), lembrados por tabela. Ordenação por coluna; grupo expande com clique ou →/←. Filtro de texto em tabelas com mais de 20 linhas. **Nunca corta:** sem espaço, rola na horizontal com pista visível e primeira coluna fixa; a rolagem é alcançável por teclado (contêiner focável). |
| **Selo de variação** | Tabelas, KPIs | Seta + sinal + valor; zero = "0,00%" neutro, sem seta. |
| **Selo de estado** | Seletor de período, Bloco Fontes, Custos fixos, Posições, Conciliação, Histórico | Só leitura, com texto e tooltip ("o IPCA de out/2026 ainda não saiu"). Vocabulário fechado: neutro "aberto", "fechado", "conferido", "pago", "pendente", "a caminho", "aguardando IPCA", "manual"; aviso "vencendo", "atrasado", "ajuste"; divergência "divergente". |
| **Carimbo de data** | Todo número do Painel; tabelas de preço | "até dd/mm/aaaa" da fonte do número; tooltip com fonte e hora. Defasada → ponto de aviso. Várias fontes: a mais antiga. |
| **Barra de progresso** | Resumo do aporte, Aportes, objetivos | Três trechos sobre o planejado: **realizado em ativo**, **a caminho** (os dois somam o realizado total) e **pendente**. Os números ficam escritos ao lado, com os mesmos rótulos: a barra não é o dado. "% realizado" = realizado total ÷ planejado. |
| **Botão** | Global | Um primário por região. Destrutivo ou que congela dados → Diálogo de confirmação. |
| **Abas** | Áreas | Na URL; ←/→ trocam de aba (Radix). |
| **Toast** | Global | Sonner herdado: inferior direito, 4 s, só resultado de ação concluída ("41 transações confirmadas."). Sem botão. O que pede ação vira aviso; erro fica no bloco. |
| **Hub de import** | Painel lateral | Topo: Bloco Fontes. Dropzone multiarquivo; cada arquivo ganha a fonte detectada; formato desconhecido é recusado na linha, sem travar os outros. CSV Nubank: "CSV não permite conferir o saldo. Prefira o OFX." **Prévia** por fonte: novos, existentes, período, conta ou corretora. Nada grava antes de **Confirmar import**; havendo novas, abre a Revisão de transações. Rodapé: Histórico de imports. |
| **Histórico de imports** | Hub de import | Lotes, do mais recente: data, arquivos, contagens. **Desfazer** só no último lote, até 7 dias, com Diálogo de confirmação do que sai ("Remove 43 transações, 2 operações, 38 categorizações e 2 regras do lote de 17/10/2026."). Lote em mês fechado: o diálogo avisa que vira ajuste (FR-33). Demais lotes: só leitura. |
| **Revisão de transações** | Painel lateral largo | Abre com **todas as linhas marcadas**. Tag de origem: "regra", "sugestão", "sem sugestão" ou **"manual"**; a linha passa a "manual" assim que você troca a categoria nela (FR-12), e o cabeçalho reconta. Desmarcadas seguem "a revisar". Correção na linha (Combobox de categoria). Categoria de debênture traz o campo "Debênture" sugerido (FR-24). Filtro "Só sem categoria". Lote de vários meses: agrupado por mês, com subtotais. **Teclado:** ↑↓ foco; **Espaço** marca; **Shift+clique** (mouse) marca o intervalo desde a última linha tocada, sem variante de teclado; **Enter** confirma ("Confirmar {n} transações"); **C** abre o Combobox da linha. **Sem sugestão bloqueia:** linha marcada sem categoria desabilita o Confirmar até ganhar categoria ou ser desmarcada; o rodapé diz "{n} sem categoria. Escolha a categoria ou desmarque a linha." e o botão aponta para essa nota (`aria-describedby`). |
| **Combobox de categoria** | Revisão de transações, Transações | Busca ("merc" → "Alimentação › Mercado"); ↑↓ + Enter escolhem (sem confirmar o lote); Esc fecha. Sem arquivadas. |
| **Proposta de regra** | Revisão de transações, Transações | Faixa inline não bloqueante sob a linha cuja categoria de regra ou sugestão foi trocada: "Criar regra? Descrição contém '{texto}' → {categoria}. Afeta {n} outras transações." **Criar regra** · **Ajustar condição** (prévia ao vivo) · **Agora não**. Confirmar o lote sem responder = "Agora não". |
| **Formulário em painel lateral** | Ajustes (criar e editar) | Tabela visível ao fundo. Validação ao sair do campo e no Salvar, mensagem sob o campo ("Vencimento entre 1 e 31."). Esc com alterações: "Descartar alterações?". Salvo: fecha, Toast "{Item} salvo.", foco na linha. |
| **Conta do orçamento** | Caixa › Orçamento | Conta aberta, linha a linha, operador à esquerda: **+ Receita do trabalho** (expande por pagador) · **+ Resgates** · **− Custos fixos** (todos do mês, pagos ou não) · **− Aporte planejado** · **− Dívidas do mês** (input inline, R$ 0,00 por padrão) · **= Disponível para consumo** · **− Consumido** · **= Restante**. Abaixo, separada: **Consumo financiado por resgate** ("coberto por resgates, não pelo trabalho") e o restante sem os resgates. Definições em Termos de dinheiro do mês. Cada linha leva ao detalhe. Dívidas: Enter grava, Esc reverte; a conta recalcula e anuncia "Disponível: R$ {valor}". |
| **Lista de custos fixos com casamento** | Caixa › Custos fixos | Cabeçalho: pago × pendente. Linha: nome, valor, vencimento, Selo de estado (pago, pendente, vencendo, atrasado) e transação casada (±10%, −5 a +5 dias); ordem atrasado → pago. Ações: **Confirmar** · **Trocar** (transações do mês, com busca) · **Marcar pago manualmente** (Selo de estado "manual"). Confirmado: "Desfazer casamento". Duas candidatas: ver Casamento ambíguo (State Patterns). |
| **Distribuição do aporte** | Investimentos › Aportes | Ordem do FR-29: **objetivos** (progresso até o alvo, prazo), **classes recolhidas**, expansíveis para **ativos**. Colunas de classe: meta, atual, desvio (p.p.), banda, sugerido, realizado, pendente. **Por linha, realizado = só o que virou ativo.** **Rodapé de conciliação:** objetivos + classes (Σ realizado em ativo, Σ pendente) · **+ a caminho, ainda sem classe** · **= total do mês** (realizado total, pendente total); ver Conciliação do pendente em Termos de dinheiro do mês. Editar **trava** o valor (cadeado; clique destrava); o resto redistribui na hora e o total = planejado fica fixo. Travas acima do total: "Travas somam R$ {x}, acima do planejado." Anuncia "Redistribuído: {n} linhas". Pisos reduzidos geram nota. Nunca sugere venda. |
| **Cartão de corretora** | Investimentos › Conciliação | Um por corretora: **saiu** (do Nubank), **proventos**, **aplicado**, **caixa em corretora**, **a caminho** (Selo de estado + "importe o relatório B3 a partir de dd/mm/aaaa"), Carimbo de data. Input opcional **"Saldo que vejo na corretora"** (valor + data): mostra calculado × informado; divergência → Selo de estado "divergente" + aviso. Vazio = sem conferência. |
| **Checklist de fechamento** | Fechamento de mês | No Diálogo de "Fechar {mês}", antes do resumo a congelar: **saldo conferido** (conta PF), **transações revisadas**, **avisos do mês** (listados). Pendência: ponto de aviso + link para a tela. Fechar com pendências é permitido depois de vê-las: "Fechar {mês} com {n} pendências". |
| **Fechamento de mês** | Visão geral › Histórico | "Fechar {mês}" abre o Checklist de fechamento. Selo de estado "aberto"/"fechado" no Histórico e no Seletor de período. "Reabrir {mês}": diálogo com **congelado × recalculado** (só linhas que mudam). Ajuste em mês fechado: Selo de estado "ajuste" + "Reabrir para recalcular". |
| **Assistente de recuperação** | Visão geral › Painel | Cartão no topo do Painel enquanto a base não chega ao mês anterior. Trilha **jun → out/2026**, um mês por vez, 4 passos (feito / atual / a fazer): **Importar** (Hub; feito se os arquivos cobrem o mês) · **Revisar** (Revisão de transações filtrada pelo mês) · **Conferir** ("conferido"/"divergente" da conta PF) · **Fechar** (Checklist de fechamento). O Seletor de período acompanha o mês; o próximo abre quando o atual fecha. Progresso derivado dos dados: pausar não perde nada. |
| **Gráfico de patrimônio** | Histórico | Linha mensal, com a série "aplicado" como referência. Tooltip com valor e data. A partir do primeiro mês fechado na v2. |
| **Gráfico de gastos por categoria** | Histórico | Barras por grupo: período × anterior, média 12m como marcador. Clicar na barra abre as transações do grupo. |
| **Gráfico de aporte planejado × realizado** | Histórico | Barras por mês do intervalo; sem planejado, só realizado. |
| **Estado vazio** | Qualquer lista ou área | Uma frase com o porquê + no máximo uma ação. |
| **Esqueleto** | Carregamento | Mesmo layout final; `aria-busy` no contêiner. |
| **Diálogo de confirmação** | Fechar/reabrir mês, desfazer lote, descartar formulário | Efeito em números; foco em "Cancelar" se destrutivo. |

Os três gráficos moram só no Histórico, cada um com "Ver como tabela" (mesmos dados numa Tabela de dados).

## State Patterns

| Estado | Superfície | Tratamento |
|---|---|---|
| Carga inicial | Todas as telas | Esqueleto com a geometria final; blocos independentes; Painel em < 3 s. |
| Base vazia (antes da UJ-5) | Painel | Assistente de recuperação: "A base vai até {dd/mm/aaaa}. Recupere mês a mês até hoje." Ação: Começar por {mês}. |
| Período sem dados | Qualquer aba | "Nenhuma transação em {mês}. Importe o extrato do Nubank." |
| Antes de jul/2024 | Seletor de período | Meses e ‹ desabilitados; tooltip "Sem dados antes de jul/2024". URL com período anterior cai em jul/2024. |
| Fonte defasada | Bloco Fontes, Carimbo de data | Ponto de aviso + aviso "fonte desatualizada" (limites do FR-3). O número continua visível. |
| Preço desatualizado / API externa falhou | Posições, Painel | Último valor + Carimbo "preço de {dd/mm/aaaa}" + ponto de aviso. Sem valor: "—" + "sem preço". Nunca erro. |
| Erro ao carregar | Qualquer bloco | No bloco: "Não foi possível carregar {o quê}. Tentar de novo." O resto funciona. |
| Falha ao gravar | Confirmar import, Confirmar lote, Salvar, Fechar/Reabrir mês, Desfazer lote, Dívidas do mês | No próprio painel, diálogo ou linha: "Não foi possível {verbo}. Nada foi perdido. Tentar de novo." O que você preencheu continua; foco vai para "Tentar de novo". Nunca Toast. |
| Sessão expirada | Global | Login; depois volta à mesma rota e período. |
| A caminho | Painel, Posições, Aportes, Conciliação | Selo de estado "a caminho" + valor + "importe o relatório B3 a partir de {dd/mm/aaaa}". Conta no **realizado total**, fica **fora do realizado por classe** até virar ativo e não entra no patrimônio. |
| Aguardando IPCA | Posições, Histórico | Rentabilidade real = Selo de estado "aguardando IPCA"; a nominal aparece normalmente. |
| Bloco cripto | Posições, Distribuição do aporte | Linha "Bloco cripto": quanto saiu × quanto vale. Ativos só com valor atual; o resto = "—". |
| Sem aporte planejado | Aportes, Resumo do aporte | "Defina o aporte planejado de {mês} para ver a distribuição." O clique leva ao campo do valor, com foco. |
| Sem aporte planejado | Conta do orçamento | "− Aporte planejado" mostra "R$ 0,00" + legenda "não definido · Definir em Aportes"; o Disponível conta zero. |
| Sem metas | Investimentos › Aportes | No lugar da Distribuição do aporte: "Sem metas, a distribuição do aporte não tem base. Defina as metas em Ajustes › Metas." Andamento e objetivos seguem visíveis. |
| Leitura antes do primeiro mês fechado | Histórico, Posições (Seletor de leitura) | Fluxo desde jul/2024. Patrimônio e rentabilidade por período: "Disponível a partir do primeiro mês fechado na v2." A opção não some. |
| Disponível negativo | Conta do orçamento, Cartão KPI | "−R$ 420,00" em vermelho com ▼ e nota neutra "O planejado passa da receita em R$ 420,00. Reduza o aporte ou as dívidas." Restante negativo: "Gasto acima do disponível em R$ {valor}." |
| Dívidas vazio | Conta do orçamento | "R$ 0,00", conta como zero; legenda "sem dívidas informadas". |
| Custos fixos sem cadastro | Caixa › Custos fixos | "Nenhum custo fixo cadastrado. Cadastre em Ajustes › Custos fixos." A ação abre o Formulário em painel lateral. |
| Casamento ambíguo | Lista de custos fixos com casamento | Selo de estado "pendente" + "2 candidatas"; as duas transações como opções; nada fica pago até a escolha. |
| Tudo bate | Investimentos › Conciliação | "Tudo bate com o consolidado B3 de {dd/mm/aaaa} e com as carteiras de {dd/mm/aaaa}." "Conferido" em cada cartão. |
| Consolidado B3 não importado | Investimentos › Conciliação | Tabela B3: "Sem consolidado B3. Importe o consolidado (.xlsx) para conciliar." Ação: Importar. Cartões e carteiras seguem visíveis. |
| Ajustes sem itens | Cada aba de Ajustes | Mensagem e ação da tabela Ajustes (Information Architecture). |
| Mês fechado | Todas as áreas | Selo de estado "fechado"; resumo congelado. Edições viram ajuste. |
| Ajuste em mês fechado | Histórico, Central de avisos | Selo de estado "ajuste" + aviso + "Reabrir {mês} para recalcular". |
| Arquivo repetido | Hub de import (prévia) | "0 novas" na fonte + aviso "arquivo já importado". Confirmar só se outro arquivo tiver algo novo. |
| Formato não reconhecido | Hub de import | Na linha: "Formato não reconhecido. Aceitos: OFX Nubank, CSV Nubank, B3 movimentação, negociação e consolidado (.xlsx)." |
| Lendo arquivo grande | Hub de import | Na linha: "Lendo {nome}…" com Esqueleto da prévia; os outros seguem. Confirmar só depois de todas as prévias. |
| Filtro sem resultados | Revisão de transações ("Só sem categoria"), tabelas com filtro de texto | "Nenhuma transação sem categoria." / "Nada encontrado para '{texto}'." Ação: Limpar filtro. |
| Desfazer indisponível | Histórico de imports | Último lote com mais de 7 dias: sem "Desfazer"; "Último lote: {dd/mm/aaaa}. Prazo de desfazer encerrado." |
| Nada a revisar | Revisão de transações | "Nada a revisar. Todas as transações do lote vieram de regras." Ação: Fechar. |
| Sem avisos | Central de avisos, Painel | "Nenhum aviso. Dados até {dd/mm/aaaa}." |

## Interaction Primitives

| Primitivo | Regra |
|---|---|
| Painéis laterais | Deslizam da direita: entrada 200 ms ease-out, saída 150 ms. A tela de fundo segue visível sob o overlay e não perde estado. Pilha máxima: um painel lateral + um diálogo. |
| Movimento | Sem count-up de número nem animação de gráfico. Hover discreto só em linhas de tabela. Com `prefers-reduced-motion`: só opacidade, ≤ 100 ms. |
| Foco | Ao abrir, vai para o primeiro elemento útil: dropzone no Hub, primeira linha na Revisão de transações, primeiro aviso na Central de avisos, primeiro campo no Formulário, "Cancelar" em diálogo destrutivo. Ao fechar, volta ao gatilho. Preso no painel enquanto aberto (Radix). |
| Teclado | Tab segue a ordem de leitura; Esc fecha a camada do topo; tabelas com ↑↓ e →/←. Sem atalhos globais na v2.0: atalhos só na Revisão de transações. |
| Edição | Inline em tabelas (Ajustes, Distribuição do aporte, dívidas do mês): Enter grava, Esc reverte. Vários campos: Formulário em painel lateral. |
| Proibido | Drag-and-drop para reordenar, scroll infinito, hover como único caminho para uma ação, modal sobre modal. |

## Accessibility Floor

Contraste em `DESIGN.md` › Colors.

- **Conformidade:** WCAG 2.2 AA em todas as telas; `lang="pt-BR"`.
- **Reflow e zoom (1.4.10):** com zoom de 200% (ou viewport abaixo de 1024px) o layout reflui para uma coluna; só as tabelas de dados rolam na horizontal, a exceção que a 1.4.10 admite para conteúdo tabular. Nenhum valor é cortado.
- **Teclado completo:** UJ-1 a UJ-5 terminam sem mouse. A seleção de intervalo (Shift+clique) é atalho só de mouse; pelo teclado, cada linha se marca com Espaço.
- **Foco visível:** anel de 2px `{colors.ring}` com offset de 2px. Nunca `outline: none` sem substituto.
- **Contorno de controle (1.4.11):** input, Combobox, checkbox desmarcado e trilho da Barra de progresso com contorno `{colors.input}` ≥ 3:1.
- **Cor nunca é o único sinal:** sinal e seta conforme Números e formatação financeira; aviso, divergência, fora da banda e estados sempre com texto (tag ou Selo de estado); trechos da Barra de progresso por forma (sólido, hachurado, vazio) e rótulo; séries de gráfico também por estilo de linha ou contorno e legenda.
- **Números:** valores com sinal têm `aria-label` por extenso ("menos R$ 163,80"); tabelas usam `<th scope>`; a Conta do orçamento é uma tabela com operador em coluna própria.
- **Gráficos:** "Ver como tabela" em todos.
- **Anúncios (aria-live polite):** Sino de avisos, total do lote na Revisão de transações, redistribuição da Distribuição do aporte, disponível na Conta do orçamento, Toast.
- **Alvos:** ≥ 24 × 24 px, checkboxes da Revisão de transações inclusive.
- **Movimento:** `prefers-reduced-motion` respeitado.

## Números e formatação financeira

| Item | Regra | Exemplo |
|---|---|---|
| Moeda | Completa, com centavos; milhar com ponto, decimal com vírgula; espaço não separável após "R$". Nunca "mil", "k", "MM", nem em eixo de gráfico | "R$ 68.695,66"; tick "R$ 60.000,00" |
| Sinal | Menos tipográfico antes da moeda. Variação e resultado: "+" e ▲ em verde, "−" e ▼ em vermelho. Saldo, valor absoluto e valor de transação: só o sinal, sem seta nem cor | "▼ −R$ 163,80" · "▲ +R$ 682,10" · "−R$ 35,00" |
| Percentual | Duas casas; XIRR com sufixo do período; alocação em p.p.; nominal e real lado a lado, rotulados | "55,48%" · "10,90% a.a." · "0,87% a.m." |
| Desvio de alocação | Em p.p., com sinal, coluna própria; fora da banda em laranja + Linha de aviso. Não é ganho nem perda: sem seta | "−3,60 p.p." |
| Anotação em célula numérica | Cadeado, "piso" e similares no slot fixo depois do número, ou em coluna própria; o número nunca sai da borda direita | "R$ 800,00" + cadeado no slot, alinhado com "R$ 1.250,00" |
| Data | Dia "dd/mm/aaaa"; mês "out/2026", sempre em minúscula; data relativa só em tooltip | "14/10/2026" |
| Tipografia | Todo número em mono com `tabular-nums`, à direita em tabela | `{typography.num-table}` |
| Proveniência | Todo número do Painel tem Carimbo de data. Rentabilidade é sempre XIRR; o bloco cripto nunca mostra custo ou rentabilidade por ativo (PRD §3) | — |

**Termos de dinheiro do mês** (uma leitura só, em todas as telas; exemplo de out/2026 dos mockups):

| Termo | Definição | Exemplo |
|---|---|---|
| Aporte planejado | Total que você decide aportar no mês | R$ 4.500,00 |
| Realizado (total) | Dinheiro que saiu do Nubank para investimento no mês. **Inclui o que está a caminho.** É o "investimento" do Resultado do mês | "Realizado R$ 2.800,00 · dos quais R$ 500,00 a caminho" |
| A caminho | Parte do realizado total que saiu para uma corretora cujo relatório ainda não cobre a transferência. Ainda sem classe; fora do patrimônio | R$ 500,00 para a XP |
| Realizado em ativo | Realizado total − a caminho | R$ 2.300,00 |
| Pendente (total) | Planejado − realizado total | R$ 1.700,00 |
| Realizado da linha (objetivo, classe, ativo) | Só o que já virou ativo daquela linha | Ações Nacionais R$ 700,00 |
| Pendente da linha | Sugerido da linha − realizado da linha | Ações Nacionais R$ 550,00 |
| Conciliação do pendente | Σ pendente das linhas = pendente total + a caminho (ainda sem classe) | R$ 2.200,00 = R$ 1.700,00 + R$ 500,00 |
| Consumido | Gastos do mês sem os custos fixos: gastos − transações casadas a custos fixos. Investimento nunca é gasto `[ASSUMPTION: pagamento de dívida informada em Dívidas do mês também sai do consumido, porque já está descontado no disponível]` | R$ 9.494,67 − R$ 2.582,30 = R$ 6.912,37 |
| Disponível para consumo | Receita do trabalho + resgates − custos fixos (todos do mês) − aporte planejado − dívidas do mês | R$ 8.405,59 |
| Restante | Disponível para consumo − consumido | R$ 1.493,22 |
| Consumo financiado por resgate | Parte do consumido coberta por resgates = mín(resgates, consumido); ao lado, o restante sem os resgates (restante − resgates) `[ASSUMPTION: fórmula do consumo financiado por resgate]` | R$ 4.487,99; sem o resgate, −R$ 2.994,77 |
| Taxa de poupança | (Receita do trabalho − gastos) ÷ receita do trabalho (FR-20); ao lado, realizado total ÷ receita do trabalho | 23,92% · 22,44% |

## Key Flows

### UJ-1. Vitor fecha a semana em poucos cliques.

Sábado de manhã, com o OFX do Nubank CPF e MEI e o xlsx de negociação da B3.

1. No **Painel**, a Linha de aviso diz "Nubank CPF sem import desde 10/10/2026"; o Sino de avisos mostra 2.
2. **Importar**: o Hub de import desliza, foco na dropzone. Ele arrasta os três arquivos; cada um ganha a fonte detectada.
3. A **prévia** mostra novos, existentes, período e conta. **Confirmar import**.
4. A **Revisão de transações** abre larga: 43 novas, todas marcadas.
5. Numa "sugestão" errada, aperta C, digita "merc", escolhe "Alimentação › Mercado"; a tag vira "manual". A Proposta de regra surge ("Descrição contém 'ZAFFARI' … Afeta 3 outras transações."); **Criar regra**, sem perder o ritmo.
6. Desmarca duas com Espaço; **Enter**: "Confirmar 41 transações". Toast: "41 transações confirmadas. 2 continuam a revisar."
7. **Clímax:** no Bloco Fontes, a conta PF "conferido" em 17/10/2026: o saldo bate ao centavo. Conciliação: "Tudo bate com o consolidado B3 de set/2026" (o último importado).

**Tropeços** (viram aviso): saldo divergente → candidatas; arquivo repetido → "0 novas"; formato desconhecido → recusado na linha; transferência sem B3 → "R$ 1.200,00 a caminho"; caixa em corretora divergente → Cartão de corretora com "divergente" e calculado × informado.

### UJ-2. Vitor planeja e acompanha o aporte do mês.

1. No Painel, o Resumo do aporte diz "Defina o aporte planejado de nov/2026"; o clique leva a Aportes, foco no campo.
2. Informa **R$ 4.500,00**. A linha "Disponível para consumo depois do aporte" recalcula ali mesmo; a **Distribuição do aporte** mostra objetivos (Reserva de emergência, Snow Trip) e as classes, recolhidas.
3. Expande Ações Nacionais: a sugestão por ativo segue o déficit em relação à meta.
4. Muda FIIs para R$ 800,00: cadeado na célula, as demais redistribuem, o total segue R$ 4.500,00.
5. Compra fora do app; a cada import, o realizado total e o pendente avançam na Barra de progresso do Painel; o a caminho vira realizado da classe quando o relatório B3 o cobre.
6. **Clímax:** no fim do mês, pendente = R$ 0,00, nada a caminho, e a distribuição por classe mostra para onde foi cada real.

**Falhas:** pisos acima do disponível → nota de pisos reduzidos; últimos 7 dias com pendente → aviso "aporte pendente"; transferência sem relatório B3 → "a caminho" até o import que a cobre.

### UJ-3. Vitor olha para trás.

1. Período out/2026, **Visão geral › Histórico**, leitura **Mês**: × anterior × média 12m.
2. Lê receitas e gastos por categoria. Gastou mais em Lazer; clica na barra e vê as transações.
3. Vê planejado × realizado, crescimento = aporte + resultado, e rentabilidade nominal × real com o melhor desempenho destacado.
4. Em **Caixa › Custos fixos**, o Plano de saúde mostra "2 candidatas"; ele escolhe a transação certa e **Confirma** o casamento: o selo vira "pago".
5. **Fechar out/2026**: o Checklist de fechamento mostra saldo conferido na conta PF, 0 a revisar e 1 aviso (classe fora da banda). Ele lê e confirma.
6. **Clímax:** out/2026 ganha "fechado" no Histórico e no Seletor de período. O resumo fica como ele viu.

**Falhas:** import atrasado em mês fechado → aviso + Selo de estado "ajuste"; "Reabrir out/2026" mostra congelado × recalculado, ele confirma e fecha de novo. IPCA de outubro ausente → "aguardando IPCA". Antes do primeiro mês fechado na v2 → estado de leitura indisponível.

### UJ-4. Vitor ajusta o sistema.

1. **Ajustes › Categorias:** cria "Lazer › Shows" (Formulário em painel lateral), renomeia um grupo (aviso de efeito em todo o histórico) e arquiva uma categoria antiga.
2. **Ajustes › Regras:** edita uma condição com prévia; desativa uma regra; **Reaplicar regras** a set/2026, com prévia antes × depois; categorias manuais intactas.
3. **Metas:** sobe FIIs e ajusta banda e piso; a soma volta a 100%. **Objetivos:** muda o prazo do Snow Trip e o multiplicador da reserva.
4. Ajusta um custo fixo, cadastra uma debênture e informa o preço manual da Neobankless.
5. **Clímax:** em Aportes, a Distribuição do aporte já reflete as novas metas. Nenhum código tocado.

**Falhas:** categoria com transações → só "Arquivar"; reaplicação em mês fechado → "2 transações em meses fechados: o resumo congelado não muda"; preço manual em ativo com fonte → "BBAS3 tem preço de mercado automático."

### UJ-5. Vitor recupera a base.

Uma única vez, com os arquivos de jun a out/2026 já baixados. Jul/2024 a mai/2026 já entram fechados em bloco (FR-7).

1. O Painel abre com o **Assistente de recuperação**: "A base vai até 31/05/2026." Trilha jun → out/2026; passo atual: jun, Importar.
2. **Importar** abre o Hub de import. Ele arrasta tudo de uma vez (OFX CPF e MEI, B3 movimentação, negociação e consolidado). A prévia marca o que é anterior a jun/2026 como já existente. Confirma: o passo Importar fica feito em todos os meses cobertos.
3. **Revisar** abre a Revisão de transações filtrada por jun/2026. Ele confirma em partes e desmarca o que vai rever depois.
4. **Conferir** mostra a conta PF "conferido" em 30/06/2026.
5. **Fechar** abre o Checklist de fechamento; ele fecha jun/2026. O assistente avança para jul, e o Seletor de período vai junto.
6. **Clímax:** de jun a out/2026, os cinco meses fechados com saldo conferido. O assistente some, o Painel fica sem avisos de fonte e o Histórico compara meses pela primeira vez.

**Falhas:** arquivo faltando → aviso "lacuna" com o intervalo, e o passo Importar do mês fica pendente; saldo divergente → passo Conferir com "divergente" e link para as candidatas, resolvido antes de fechar; arquivo errado → **Desfazer** no Histórico de imports (último lote, até 7 dias) remove o lote, as categorizações e as regras criadas nele.

## Inspiration & Anti-patterns

- **Tirado de tweakcn / 21st.dev:** neutros do *darkmatter* e o verde do *supabase* como única cor de ação e ganho (`DESIGN.md` › Colors).
- **Tirado do shadcn:** o vocabulário de componentes. O Goodies é o que adicionamos a ele.
- **Tirado do grupo-natus:** só o rigor (tokens semânticos, teste "no raw color", theme-showcase).
- **Rejeitado:** a cara da planilha "Rotina" (roxo, categorias coloridas, células de ajuste manual); as ~16 abas soltas da v1; dashboard de gráficos, abreviação e animação de número; gamificação (confete, streak, "parabéns"). Fechar o mês é a recompensa.
