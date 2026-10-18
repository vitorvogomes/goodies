---
status: final
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - docs/v2/planning/prds/prd-goodies-2026-10-17/prd.md
  - docs/v2/planning/prds/prd-goodies-2026-10-17/addendum.md
  - docs/v2/planning/prds/prd-goodies-2026-10-17/.memlog.md
  - docs/v2/planning/architecture/architecture-goodies-2026-10-17/ARCHITECTURE-SPINE.md
  - docs/v2/planning/ux-designs/ux-goodies-2026-10-17/DESIGN.md
  - docs/v2/planning/ux-designs/ux-goodies-2026-10-17/EXPERIENCE.md
  - docs/v2/party-mode/2026-10-17-abertura-arquitetura.md
  - .claude/memory/decisions.md
  - .claude/memory/conventions.md
  - .claude/memory/skills.md
  - CLAUDE.md
---

# goodies - Epic Breakdown

## Overview

Este documento quebra em épicos e stories implementáveis os requisitos do PRD, da UX (DESIGN + EXPERIENCE) e da
arquitetura (AD-1..AD-19) do Goodies v2.0. Escopo: os 4 marcos do PRD §6.1. A v2.1 fica fora.

**Regras para todos os épicos:**
- **Telas da v1 seguem funcionando até o Épico 10.** Story que mexe numa rota ou módulo legado mantém a tela v1
  funcionando ou a migra na mesma story; o fechamento da story inclui fumaça das telas v1 (`/run`).
- **Regras transversais em toda story:** AR3 (layout de engine), AR4 (dono único), AR5 (dinheiro), AR16 (contrato HTTP),
  AR19 (`user_id` em tabela nova), AR22 (`structlog`), NFR1 (dinheiro exato) e NFR13 (TDD, cobertura, `/code-review`).
- **Conferência de saldo só na conta Nubank PF (CPF).** A conta MEI fica sempre zerada (o dinheiro passa para a PF):
  importa sem conferência, e o OFX dela pode cobrir vários meses.

## Requirements Inventory

### Functional Requirements

FR1: Importar num mesmo fluxo arquivos de qualquer fonte (Nubank CPF/MEI OFX e CSV; B3 movimentação, negociação e consolidado), com a fonte detectada por arquivo; formato desconhecido é recusado com "formato não reconhecido" + lista de aceitos; OFX associado à conta (CPF/MEI) pelo próprio arquivo; CSV Nubank aceito sem conferência de saldo, com aviso.
FR2: Prévia do lote por fonte (novos, existentes, período, conta/corretora) antes de gravar; nada é gravado sem confirmação; reimportar o mesmo arquivo dá zero novos e o aviso "arquivo já importado".
FR3: "Atualizado até" por fonte no painel e no hub, com aviso de defasagem: Nubank 7 dias; B3 movimentação/negociação só via transferência não coberta (FR4); B3 consolidado se o do mês anterior não chegou até o dia 15.
FR4: Aviso "lacuna" com o intervalo a importar; aviso "transferência não coberta" para dinheiro a caminho ("importe o relatório B3 a partir de {data}").
FR5: Após cada OFX da conta PF (CPF), comparar saldo informado × calculado ao centavo (a conta MEI fica sempre zerada e não confere; o OFX dela pode cobrir vários meses); diferença gera "saldo divergente" com valor e transações candidatas; quando bate, o painel marca "conferido" na data.
FR6: Desfazer o último lote de import feito nos últimos 7 dias, removendo transações, operações, categorizações e regras criadas na revisão desse lote; lote em mês fechado segue FR33.
FR7: Recuperar a base: importar de uma vez jun–out/2026 (CPF, MEI, B3), revisar e fechar mês a mês; meses recuperados nascem abertos; nada anterior a jun/2026 é duplicado; jul/2024–mai/2026 fechados em bloco na migração, depois da reclassificação de resgates (fechamento retroativo com patrimônio do consolidado B3, cripto "estimada", cobertura por fonte).
FR8: Criar, renomear e arquivar grupos e subcategorias; cada categoria tem tipo de movimento (no grupo, herdado pela subcategoria); renomear reflete em todo o histórico; categoria com transações só se arquiva.
FR9: Revisão de transações em lote: todas as novas, com checks, pré-preenchidas por regra, sugestão ou "sem sugestão"; correção individual e confirmação do lote; aviso "transações a revisar" enquanto houver não confirmadas.
FR10: Ao corrigir uma categoria, propor "criar regra?" com prévia das transações afetadas; confirmar, ajustar condição ou recusar; regra mais específica (condição mais longa) vence; editar/desativar regras em Ajustes.
FR11: Reaplicar regras a um período passado com prévia; nunca sobrescreve categoria manual; mudanças em mês fechado seguem FR33.
FR12: Cada transação guarda a origem da categoria: regra, sugestão confirmada ou manual.
FR13: Painel principal com resultado do mês, disponível para consumo, patrimônio, resultado e rentabilidade dos investimentos, custos fixos pendentes/vencendo/atrasados, aporte do mês (planejado, realizado, a caminho, pendente), classes fora da banda, transações a revisar e atualizado até de cada fonte; cada número com a data dos dados.
FR14: Central de avisos única (14 tipos: arquivo já importado, lacuna, transferência não coberta, fonte desatualizada, saldo divergente, CSV sem conferência, transações a revisar, custo fixo vencendo/atrasado, aporte pendente nos últimos 7 dias, classe fora da banda, caixa em corretora divergente, posição divergente da origem, ajuste em mês fechado, mês aberto há mais de 10 dias); some sozinho quando a condição acaba; dispensado só volta se a condição mudar; painel mostra o número de avisos ativos.
FR15: Receitas do mês por pagador e, em linha própria, os resgates; pagador nunca atribui categoria.
FR16: Gastos por grupo e subcategoria (só tipo gasto); total direcionado a investimentos em linha própria; fatura do cartão como uma transação com o valor pago.
FR17: Orçamento do mês: disponível para consumo (trabalho + resgates − custos fixos − aporte planejado − dívidas do mês), quanto já foi gasto (consumido) e quanto resta; consumo financiado por resgate em linha própria (por objetivo × por carteira).
FR18: Casar cada custo fixo com uma transação (±10%, −5/+5 dias do vencimento) e marcar pago; Vitor confirma, corrige ou marca manualmente; aviso "vencendo" 3 dias antes, "atrasado" depois do vencimento.
FR19: Reclassificar uma vez, em todo o histórico, os resgates gravados como investimento (ADR-011) para resgate = receita; taxa de poupança histórica e gate jun/2026 = 55,48% inalterados.
FR20: Taxa de poupança = (receita do trabalho − (gastos − devoluções)) / receita do trabalho; ao lado, aporte (realizado total) ÷ receita do trabalho.
FR21: Posições e alocação em dois níveis (classe → ativo): aplicado, valor atual, resultado, alocação × meta ± banda; cripto como bloco cripto (valor atual por ativo entra na alocação); ativos vinculados a objetivos ficam num bloco "Objetivos", fora da base da alocação.
FR22: Rentabilidade só por XIRR, por mês, trimestre, ano e desde o início; nominal × real (IPCA efetivo; "aguardando IPCA" se faltar) por classe e consolidada; mensal por ativo em % a.m. exceto RF e Cripto; leitura por período a partir do primeiro mês fechado.
FR23: Caixinhas e CDBs derivados das transações Nubank e valorados pelo %CDI sobre o CDI efetivo coletado (não taxa fixa); Tesouro com preço de mercado automático.
FR24: Cadastrar debêntures no app (emissor, taxa, início, vencimento), substituindo o JSON/seed; só saídas Nubank com categoria de investimento em debênture viram aportes sugeridos na revisão; valoração pela taxa cadastrada; cupons e vencimento entram como resgates.
FR25: Por corretora, resíduo = saídas Nubank + proventos − aplicado; coberto pelo atualizado até → caixa em corretora (patrimônio); não coberto → a caminho (FR4); conferência opcional do saldo informado gera "caixa em corretora divergente".
FR26: Conciliar posições com o consolidado B3 e com o scan das carteiras pelas tolerâncias de AD-13 (quantidade exata em B3; Tesouro 0,01 título; caixa R$ 1,00; cripto sem divergência e aviso se o scan > 14 h; caixinhas/debêntures não conciliam, "valor calculado"); divergência gera "posição divergente da origem".
FR27: Preços de mercado e dólar automáticos; preço manual só para ativo sem fonte (ex.: Neobankless).
FR28: Informar e alterar durante o mês o aporte planejado.
FR29: Distribuição do aporte em ordem fixa: reserva de emergência (falta ÷ meses restantes, horizonte 12, prioridade até encher) → demais objetivos (falta ÷ meses até o prazo; proporcional se faltar) → classes (déficit monotônico, piso, acima da banda só piso, pisos reduzidos em proporção) → ativos (déficit; cripto pelo valor atual); nunca sugere venda; fecha ao centavo.
FR30: Alterar qualquer valor da distribuição trava o valor; o restante redistribui pela mesma regra, respeitando o planejado.
FR31: Acompanhar até o fim do mês o realizado (total inclui a caminho; por classe/ativo só quando vira ativo), o a caminho e o pendente; no mês seguinte o pendente zera.
FR32: Fechar o mês explicitamente, congelando o resumo do mês (receitas por pagador e resgates, gastos por categoria, investimento, poupança, aporte planejado/realizado/pendente, patrimônio e valor por classe e ativo, rentabilidade, saldo conferido), com versões; reabrir e refechar cria nova versão.
FR33: Dado novo em mês fechado é aceito sem mudar o resumo congelado e gera "ajuste em mês fechado"; reabrir mostra congelado × recalculado e permite refechar.
FR34: Comparar mês, trimestre ou ano com o anterior e a média 12m em receitas e gastos por categoria, aporte planejado × realizado, crescimento do patrimônio (aporte + resultado) e rentabilidade por classe/ativo com destaque do melhor; fluxo desde jul/2024, patrimônio/rentabilidade a partir do primeiro mês fechado.
FR35: Ajustes editáveis sem código: categorias e regras, custos fixos (valor, vencimento), contas, objetivos (nome, valor-alvo, prazo, ativos vinculados), debêntures, metas de alocação por classe e ativo com bandas e pisos, multiplicador e horizonte da reserva, preços manuais só para ativos sem fonte.
FR36: Quatro áreas (Visão geral, Caixa, Investimentos, Ajustes); tudo a no máximo dois cliques do painel; desktop-first; sub-telas como abas, hub/revisão/avisos/formulários como painéis laterais.

### NonFunctional Requirements

NFR1: Correção monetária — valores exatos (Decimal no Python, `numeric(15,2)` no banco, nenhuma aritmética de dinheiro no navegador).
NFR2: Import idempotente — reimportar não duplica (dedup por FITID/`operation_hash`, hash de arquivo).
NFR3: Migração sem perda — os dados curados anteriores a jun/2026 só mudam pelas reclassificações aprovadas (FR19, faturas → Cartão de crédito, Repasse → Devoluções), sem perda nem duplicação; gate jun/2026 = 55,48%.
NFR4: Proveniência — toda transação e operação sabe de qual lote e fonte veio e de onde veio a categoria.
NFR5: Resiliência — falha de API externa nunca quebra o painel nem retorna 5xx; o dado é marcado `stale` com a última data.
NFR6: Ambiente e privacidade — v2.0 roda só em localhost; transações, saldos e posições não saem da máquina; só saem consultas a fontes públicas e APIs autorizadas; sem deploy nem CI (ADR-014).
NFR7: Segurança — usuário único com JWT próprio (ADR-006), access token em memória, refresh em cookie httpOnly; segredos só no `.env` sincronizado com `.env.example`; gitleaks no pre-commit; nada de segredo no chat.
NFR8: Desempenho — painel principal carrega em menos de 3 s.
NFR9: Restrições herdadas — ADRs vigentes e CLAUDE.md continuam valendo, exceto ADR-011 (revertido por ADR-015) e o deploy (ADR-014).
NFR10: Acessibilidade — WCAG 2.2 AA como alvo de design (tokens, contrastes e componentes do DESIGN.md), `lang="pt-BR"`; a verificação final é UJ-1..UJ-5 completas só com teclado (sem auditoria WCAG formal, decisão do Vitor em 2026-10-18).
NFR11: Plataforma — desktop-first (alvo ≥ 1280px, degradação 1024–1279px, reflow em coluna abaixo de 1024px/zoom 200%); mobile fora.
NFR12: Métricas observáveis — `categorization_events` (append-only) sustenta SM-5, SM-6 e SM-C1; `alert_dismissals` sustenta SM-C2; fechamentos sustentam SM-2 e SM-3.
NFR13: Qualidade — TDD por story, cobertura ≥ 80%, `mypy --strict` nos pacotes tocados, testes de serviço contra Postgres real (`goodies_test`), golden tests de dinheiro, `/code-review` ao fim de cada story; tudo local.

### Additional Requirements

Da arquitetura (AD-1..AD-19) e das decisões do party mode. **Não há starter template**: é brownfield; a Story 1.1 é arrumação e a 1.3 atualiza as versões.

- AR1 (Stack): atualizar para as versões travadas — Next.js 16.3.8 + `eslint-config-next` 16.3.8, React 19.2.9, TypeScript 5.9.3, @tanstack/react-query 5.100.14, @tanstack/react-table 9.2.4 (v9), Tailwind 4.3.0, Recharts 3.8.1, next-themes 0.4.6, Node 24, pnpm 11 (`packageManager`); FastAPI 0.136.3, asyncpg 0.31.0, Alembic 1.18.4, APScheduler 3.11.2, redis-py 8.0.0, Pydantic 2.13.4, SciPy 1.17.1, structlog 25.5.0, uv 0.11.12; Postgres 15 e Redis 7 no compose.
- AR2 (AD-1): camadas common ← market/ingest/jobs ← ledger/wallet ← portfolio ← planning ← closing ← alerts ← overview; casca `api/workers/` + `main.py` faz os registros. Movimentos obrigatórios na primeira story que tocar o módulo: enums de `portfolio/constants.py` → `common`; `Alert` do ledger → `common`; `upsert_price`/`clear_manual_price` → `market.service` (precedência `is_manual` e invalidação preservadas); `PriceCache` → `common.cache`; conciliação wallet × `net_quantity` → `portfolio`; SQL de `benchmark_workers.py` → `market.service`; `engines/jobs/router.py` → `api/workers/`; apagar `engines/analytics/`.
- AR3 (AD-2): layout `router.py` / `service.py` / `queries.py` / `models.py` / `calc.py` por engine; módulos puros irmãos (`xirr.py`, `distribution.py`); `Db`/`AuthUser` de `common.deps`; legado migra quando tocado.
- AR4 (AD-3): dono único por tabela (mapa no Structural Seed); leitura cruzada só por funções públicas da dona.
- AR5 (AD-4): `common.money.Money`/`Pct` na fronteira HTTP (2 casas, ROUND_HALF_EVEN), quantidade como string decimal; rateios fecham ao centavo pelo maior resto.
- AR6 (AD-5): engine `ingest` com protocolo `SourceAdapter` (detect/parse/plan/apply/undo), `import_batches` (staged → applied → undone; staged expira em 24 h; hash do plano), `import_batch_files`, hooks `on_batch_applied`/`on_batch_undo`, `account_balances` com `batch_id`, FK `asset_operations.transaction_id ON DELETE RESTRICT`, invalidação do cache de XIRR.
- AR7 (AD-6): `ledger.service.categorize()` como chokepoint; subcategorias de sistema "Entrada a classificar"/"Saída a classificar"; `category_groups.kind`; `categories.role` (CHECK: `work_income`, `resgate`, `devolucao`, `divida`, `consumo`, `investimento`, `transferencia`, `a_classificar`); `category_source` ∈ {rule, suggestion, manual}; `review_status` ∈ {pending, confirmed}; `categorization_events` append-only; `category_rules` com `created_in_batch`; `transactions.payer`; resolver de `asset_id` registrado por `portfolio`; hook `on_transactions_changed`; derivação idempotente por `transaction_id`.
- AR8 (AD-7): uma função pura por termo de dinheiro (tabela de AD-7), chamada por toda leitura.
- AR9 (AD-8): `closing.build_month_summary(conn, month, as_of)` única; `build_period_summary`; `month_closes`, `month_summary_totals`, `month_summary_lines`; `MonthStatusPort`; precondições de fechamento; versões; `close_retro` como comando `python -m scripts.ops.close_retro`; `market.asset_price_history` e `broker_position_snapshots` como fontes do `as_of`.
- AR10 (AD-9): derivar na leitura; persistir só decisões (`fixed_cost_payments`, travas em `month_plans`, `goal_assets`).
- AR11 (AD-10): providers de aviso registrados em `main.py`, `AlertContext` em `common`, `Alert` com key/fingerprint/severity/ação/as_of, `alert_dismissals`; `jobs` emite aviso de worker com falha/atrasado (substitui Discord até a v2.1).
- AR12 (AD-11): tabela `assets` (uuid, `key` imutável, classe, `price_ref`, valoração, %CDI) com backfill de `asset_operations`, `portfolio_targets`, `wallet_positions` (+ `asset_aliases`); `debentures`; `goals`/`goal_assets`; `portfolio_targets` com `asset_id` nulo = meta da classe.
- AR13 (AD-12): `planning/distribution.py: distribute(...)` pura, ordem fixa reserva → objetivos → classes → ativos, travas.
- AR14 (AD-13): tolerâncias de conciliação como constantes em `portfolio/calc` e `ledger/calc`; tabelas de fato `broker_position_snapshots`, `broker_cash_checks`.
- AR15 (AD-14): `periodo=YYYY-MM`, `leitura ∈ {mes, tri, ano, inicio}`, `common.dates.resolve_period`, `today_brt()`, mês = date dia 1, timestamps UTC, vigência (`valid_from`/`valid_to`) em `fixed_costs` e metas.
- AR16 (AD-15): rotas `/api/v1/<engine>/<recurso>`, `response_model` obrigatório, erro `{"error","message"}`, paginação `{items,total,limit,offset}`, `Valued[T]` com `unavailable_reason`/`as_of`/`source`/`stale`, rotas `POST .../preview` para recálculos.
- AR17 (AD-16): ordem das revisões Alembic — 1) `user_id` no ledger; 2) `import_batches` + lotes `legacy`; 3) grupos, roles, `category_id`, `category_rules` legado, `category_source`; 4) reclassificações (resgates FR19, faturas em Dívidas → Cartão de crédito, Repasse → Devoluções); 5) `assets`. Depois, `close_retro`. Cada revisão de dado com teste de invariantes (55,48%, contagem, zero órfãs, deltas esperados). Nome `NNNN_snake_name.py` (próxima = 0016).
- AR18 (AD-17): rotas `web/app/(app)/{visao-geral,caixa,investimentos,ajustes}/<aba>`, período/leitura na URL; navegação só 4 áreas + Importar desde o marco 1; rotas antigas apagadas no marco 4; shadcn `init -b radix` new-york (nunca `-d`), `components.json` commitado, `web/components/ui/` substitui `ui.tsx`; hooks em `web/lib/<engine>.ts` com queryKey `[engine, recurso, periodo?, ...]` e invalidação cruzada; tipos em `web/types/<engine>.ts`; auth 401 → refresh → repete → `/login?next=`.
- AR19 (AD-18): `docker compose` (postgres 15, redis 7, api) + `pnpm dev`; container da api: backup → `alembic upgrade head` → uvicorn; job diário `db_backup` + backup antes de toda migração, `pg_dump` fora do repo (diretório no `.env`), guarda 30, restauração em `docs/LOCAL_DEV.md`; CORS só `http://localhost:3000`; cookie `samesite=lax` sem `secure`; `common.owner.get_owner_id`; tabelas novas com `user_id` NOT NULL.
- AR20 (AD-19): golden tests — poupança jun/2026 = 55,48%; números dos mockups (consumido R$ 6.912,37; disponível R$ 8.405,59; financiado R$ 2.994,77; aportes 2.200 = 1.700 + 500); distribuição fecha ao centavo; snapshot = ao vivo no instante do fechamento; Vitest só em utilitários puros.
- AR21 (Docs vivos): a primeira story atualiza `conventions.md` (sem `queries.py` fantasma nem Server Components por padrão; fontes do DESIGN; erro em dict), reescreve o CLAUDE.md (stack local, sem Supabase/Upstash/Fly/Vercel, gates v2, ADR-014/015) e o `.env.example` (às cegas), e marca o ADR-011 como substituído em `docs/07_Decisoes.md`.
- AR22 (Logs): `structlog` em tudo (scheduler sai do `logging`); nunca segredo nem valor financeiro.
- AR23 (Party mode — categorias): grupos iniciais aprovados (Casa, Alimentação, Transporte, Lazer, Saúde e educação, Obrigações, Outros + "Cartão de crédito"; Trabalho = Recorrente/Extra; Resgates por destino; Devoluções = Repasse/Reembolso; Investimentos; Transferências); renomear "Cripto Nubnak" → "Cripto Nubank"; pagador semeado das subcategorias atuais (Flash Capital, Betuel → Recorrente); `category_source` = rule se padrão atual bate, senão manual; as 4 faturas em Assinaturas ficam.
- AR24 (Party mode — termos): consumido = gastos − custos fixos casados − devoluções − transações em Dívidas (cada transação em um balde); dívidas do mês manual (padrão 0; pré-preenchido nos retroativos); Caixinha Turbo e Extra são carteira (RF); vínculo objetivo × caixinha pelo nome no OFX.
- AR25 (Party mode — gráficos): patrimônio = chart-1 com aplicado em chart-3; gastos por categoria = período chart-2, anterior chart-3, média 12m marcador; aporte = realizado chart-1, planejado chart-2.

### UX Design Requirements

UX-DR1: Tokens de cor do DESIGN.md em `web/app/globals.css` (claro e escuro, `@theme inline`, `color-scheme` por modo), migrando `--gain`→`--positive`, `--loss`→`--negative`, novo `--warning`/`--warning-dot`, tints, `row-highlight`, `input` separado de `border`, `chart-1..3`; remover `--accent` índigo.
UX-DR2: Tipografia B1 — Geist (UI) e Geist Mono (números) com `tabular-nums`; escala `page-title`, `section-title`, `body`, `body-sm`, `label` (caixa alta via CSS), `caption`, `num-display`, `num-lg`, `num-body`, `num-table`, `tag` (minúscula); raios xs..full (base 0,75rem).
UX-DR3: Teste "no raw color" que falha o build com hex/`rgb()`/`hsl()`/`oklch()` fora de `globals.css` ou classe de paleta Tailwind em componente.
UX-DR4: Página theme-showcase `/dev/tema` (só local) com todos os tokens e componentes em todos os estados, claro e escuro lado a lado.
UX-DR5: shadcn inicializado com `init -b radix` (new-york), primitivos em `web/components/ui/` substituindo `ui.tsx`; Dialog, Sheet, Popover, Command, Tooltip, Checkbox, DropdownMenu, Skeleton, Sonner sem customização.
UX-DR6: Barra lateral (240px) com Visão geral · Caixa · Investimentos · Ajustes + botão Importar fixo (`button-primary`); item ativo com fundo `sidebar-accent` e marcador `positive`; empilha acima do conteúdo abaixo de 1024px.
UX-DR7: Barra superior fixa (56px) com Seletor de período à esquerda e Sino de avisos + Switch de tema à direita.
UX-DR8: Seletor de período — mês na URL ("out/2026", mono, minúsculo), ‹ ›, popover com Selo de estado aberto/fechado/ajuste por mês; futuros e anteriores a jul/2024 desabilitados (URL anterior cai em jul/2024); trocar mantém a aba.
UX-DR9: Seletor de leitura (ToggleGroup) Mês · Trimestre · Ano · Desde o início, na URL, por aba, ancorado no período; ativa em `background` 600, nunca verde.
UX-DR10: Switch de tema (DropdownMenu) Sistema / Claro / Escuro com next-themes `defaultTheme="system"`.
UX-DR11: Sino de avisos (contador de todos os ativos, aria-live, sem vermelho, sem contador quando zero) + Central de avisos (Sheet 560px, divergências depois avisos, mais recentes primeiro, ação leva à tela filtrada e fecha, Dispensar).
UX-DR12: Cartão KPI — rótulo label, valor `num-display`, linha de apoio + Carimbo de data; clique leva ao detalhe; cor só quando o sinal é o dado; variação só se o anterior existe; rentabilidade "XIRR · desde o início".
UX-DR13: Linha de aviso — ponto com halo + tag de severidade (slot de largura fixa) + mensagem + ação em link; divergência em `negative` sobre tint, aviso em `warning` sobre tint; variante compacta; no Painel até 3 + "Ver todos ({n})".
UX-DR14: Tabela de dados (TanStack v9) — modos Resumo/Detalhado lembrados por tabela; ordenação; grupos expansíveis por clique ou →/←; filtro de texto acima de 20 linhas; nunca corta (rolagem horizontal com pista, primeira coluna fixa, contêiner focável); números à direita em mono; linha de grupo e total; slot de anotação de 40px; `<th scope>`.
UX-DR15: Selo de variação — seta + sinal + valor sobre tint; zero = "0,00%" neutro sem seta; largura mínima igual na coluna.
UX-DR16: Selo de estado — pílula minúscula, vocabulário fechado (neutro: aberto, fechado, conferido, pago, pendente, a caminho, aguardando IPCA, manual; aviso: vencendo, atrasado, ajuste; divergência: divergente), tooltip, nunca verde.
UX-DR17: Carimbo de data — "até dd/mm/aaaa" em caption, tooltip com fonte e hora, ponto de aviso quando defasado; várias fontes = a mais antiga (vem da API, `as_of`).
UX-DR18: Barra de progresso — três trechos (realizado em ativo sólido, a caminho hachurado, pendente vazio), trilho com contorno `input`, legenda com os mesmos rótulos e números escritos.
UX-DR19: Toast (Sonner) inferior direito, 4 s, só resultado de ação concluída, sem botão; falha ao gravar nunca vira Toast.
UX-DR20: Formulário em painel lateral — título com verbo, uma coluna, validação ao sair do campo e no Salvar com mensagem sob o campo, Esc com alterações pede "Descartar alterações?", salvo fecha + Toast + foco na linha.
UX-DR21: Diálogo de confirmação (AlertDialog) — título com verbo, efeito em números, foco em "Cancelar" se destrutivo.
UX-DR22: Estados — Esqueleto com a geometria final (`aria-busy`); Estado vazio (frase + no máximo uma ação, sem ilustração); erro no bloco "Não foi possível carregar {o quê}. Tentar de novo." sem derrubar o resto; falha ao gravar no próprio painel/linha ("Nada foi perdido. Tentar de novo.") preservando o preenchido.
UX-DR23: Painéis laterais — deslizam da direita (200 ms in / 150 ms out), fundo visível sem perder estado, pilha máxima painel + diálogo, foco no primeiro elemento útil e volta ao gatilho, preso enquanto aberto, Esc fecha a camada do topo.
UX-DR24: Formatação financeira em `web/lib/format` (só formata): moeda completa com centavos e NBSP após "R$" (nunca mil/k/MM, inclusive em eixo), menos tipográfico, "+"/▲ e "−"/▼ em variação, percentuais com 2 casas e sufixo (a.a./a.m.), desvio em p.p. com sinal sem seta, datas dd/mm/aaaa, mês "out/2026" minúsculo; testes Vitest.
UX-DR25: Acessibilidade — anel de foco 2px `ring` offset 2px; contorno de controle ≥ 3:1 (`input`); cor nunca é o único sinal; `aria-label` por extenso em valores com sinal; aria-live em Sino, total da revisão, redistribuição, disponível e Toast; alvos ≥ 24×24 px; `prefers-reduced-motion` (só opacidade ≤ 100 ms); sem count-up nem animação de gráfico.
UX-DR26: Layout — conteúdo com gutter 32px e máx. 1440px; faixas ≥1280 / 1024–1279 (KPIs 2×2 por container query, pares empilham) / <1024 coluna única; painéis 560px e revisão `min(1040px, 100vw − 48px)`.
UX-DR27: Grade do Painel principal na ordem: Assistente de recuperação (quando houver) → Linhas de aviso → KPIs Resultado do mês | Disponível → KPIs Patrimônio | Resultado dos investimentos | Rentabilidade nominal | Rentabilidade real → Resumo do aporte | Resumo de custos fixos → Bloco Fontes; sem gráfico.
UX-DR28: Hub de import (Sheet 560px) — Bloco Fontes no topo, dropzone multiarquivo com fonte detectada por linha, recusa de formato na linha sem travar os outros, "Lendo {nome}…" com esqueleto, prévia por fonte em Tabela de dados, Confirmar import só após todas as prévias, abre a Revisão havendo novas.
UX-DR29: Histórico de imports — lotes do mais recente; "Desfazer" (destrutivo) só no último lote até 7 dias, com diálogo que lista o que sai em números e avisa ajuste em mês fechado; prazo vencido mostra a mensagem de prazo encerrado.
UX-DR30: Revisão de transações (Sheet larga) — todas marcadas ao abrir; tag de origem (regra, sugestão, sem sugestão, manual) que vira "manual" ao trocar e reconta o cabeçalho; filtro "Só sem categoria"; agrupada por mês com subtotais em lote multimês; teclado ↑↓, Espaço, Enter ("Confirmar {n} transações"), C abre o Combobox; Shift+clique marca intervalo (só mouse); sem categoria bloqueia o Confirmar com nota `aria-describedby`; campo "Debênture" sugerido em categoria de debênture.
UX-DR31: Combobox de categoria — Command em Popover, busca "Grupo › Subcategoria", ↑↓ + Enter escolhem sem confirmar o lote, Esc fecha, sem arquivadas, borda `warning` quando vazio.
UX-DR32: Proposta de regra — faixa inline não bloqueante sob a linha corrigida: "Criar regra? Descrição contém '{texto}' → {categoria}. Afeta {n} outras transações." com Criar regra · Ajustar condição (prévia ao vivo) · Agora não; confirmar o lote sem responder = Agora não.
UX-DR33: Bloco Fontes — uma linha por fonte (5 de arquivo + preços, carteiras, CDI/IPCA) com tipo, atualizado até e saldo; conta Nubank PF com "conferido · data" ou "divergente · R$ x" (leva às candidatas), MEI só com atualizado até; ponto de aviso quando defasada; fonte de arquivo abre o Hub.
UX-DR34: Resumo do aporte — planejado (`num-lg`), "Realizado R$ {total} · dos quais R$ {a caminho} a caminho", Barra de progresso, linha a caminho com corretora e data, Linha de aviso compacta de classes fora da banda, rodapé "% realizado"; estado "Defina o aporte planejado de {mês}" com foco no campo.
UX-DR35: Resumo de custos fixos — "pago R$ x de R$ y", só atrasados → vencendo → pendentes com data e Selo de estado, pagos recolhidos em "{n} pagos", rodapé "{n} a pagar · R$ {valor}".
UX-DR36: Conta do orçamento — tabela com operador em coluna própria: + Receita do trabalho (expande por pagador) · + Resgates · − Custos fixos · − Aporte planejado · − Dívidas do mês (input inline, Enter grava, Esc reverte, anuncia "Disponível: R$ {valor}") · = Disponível · − Consumido · = Restante; abaixo, Consumo financiado por resgate (por objetivo neutro, por carteira em laranja) e restante sem resgates; estados negativo, sem aporte, dívidas vazio; ao lado, Consumido por grupo → subcategoria com "− Devoluções" no rodapé.
UX-DR37: Lista de custos fixos com casamento — colunas custo, valor, vencimento, Selo de estado, transação casada, ações (Confirmar · Trocar com busca · Marcar pago manualmente · Desfazer casamento); ordem atrasado → pago; "2 candidatas" em RadioGroup com borda `warning`, nada pago até escolher.
UX-DR38: Distribuição do aporte — input do planejado com "Disponível para consumo depois do aporte"; objetivos (Barra de progresso até o alvo, "Snow Trip · R$ 350/mês para chegar em jul/2027") e classes recolhidas expansíveis para ativos; colunas meta, atual, desvio (p.p.), banda, sugerido, realizado, pendente; editar trava (cadeado; clique destrava), redistribui via prévia da API e anuncia "Redistribuído: {n} linhas"; travas acima do total avisam; nota de pisos reduzidos; rodapé de conciliação do pendente (Σ linhas + a caminho = total); estados sem planejado e sem metas.
UX-DR39: Cartão de corretora — saiu, proventos, aplicado, caixa em corretora, a caminho (Selo + data a importar), Carimbo; input opcional "Saldo que vejo na corretora" (valor + data) com calculado × informado e Selo "divergente".
UX-DR40: Fechamento de mês — "Fechar {mês}" abre o Checklist (saldo conferido da conta PF, transações revisadas, avisos do mês listados; pendência com ponto + link; "Fechar {mês} com {n} pendências"); Selo aberto/fechado/ajuste no Histórico e no Seletor; "Reabrir {mês}" com congelado × recalculado (só linhas que mudam, Selo de variação).
UX-DR41: Assistente de recuperação — cartão no topo do Painel enquanto a base não chega ao mês anterior; trilha jun → out/2026 com Selo por mês; 4 passos Importar · Revisar · Conferir (conta PF) · Fechar (feito/atual/a fazer) com um único botão primário; Seletor de período acompanha; progresso derivado dos dados.
UX-DR42: Gráficos (Recharts, só no Histórico) — patrimônio (linha 2px chart-1 + aplicado tracejado chart-3, grade horizontal), gastos por categoria (barras horizontais por grupo: período chart-2 preenchido, anterior contorno chart-3, média 12m marcador, rótulo direto, clique abre transações do grupo), aporte planejado × realizado (barras agrupadas chart-2 × chart-1); todos com "Ver como tabela"; moeda completa nos eixos.
UX-DR43: Ajustes em 8 abas (Categorias, Regras, Custos fixos, Contas, Objetivos, Debêntures, Metas, Preços manuais) com as regras e estados vazios da tabela do EXPERIENCE (ex.: árvore grupo › subcategoria, "Mostrar arquivadas", Reaplicar regras com prévia antes × depois e contagens de manuais/meses fechados, Metas somando 100% por nível com Salvar desabilitado, preço manual recusado em ativo com fonte).
UX-DR44: Voz e tom — "você", pt-BR, direto, sem exclamação/emoji/celebração; catálogo de mensagens e ações dos 14 tipos de aviso do EXPERIENCE; postura "sugerido/planejado", nunca "comprar/executar"; nenhum botão move dinheiro.
UX-DR45: Login com o visual novo (mesmo fluxo JWT da v1); sessão expirada volta à mesma rota e período após login.

### FR Coverage Map

| FR | Épico | Resumo |
|---|---|---|
| FR1 | 3 | importar qualquer fonte num fluxo só |
| FR2 | 3 | prévia do lote antes de gravar |
| FR3 | 3 (hub), 4 (Painel) | atualizado até e defasagem |
| FR4 | 3 (lacuna), 7 (a caminho) | lacunas e transferências não cobertas |
| FR5 | 3 | conferência do saldo do OFX |
| FR6 | 3 (desfazer), 5 (lote em mês fechado vira ajuste) | desfazer o último lote |
| FR7 | 5 | recuperação da base e fechamento retroativo |
| FR8 | 2 | categorias em dois níveis |
| FR9 | 3 | revisão de transações em lote |
| FR10 | 3 (proposta na revisão), 2 (edição em Ajustes) | regra a partir da correção |
| FR11 | 2 | reaplicar regras ao histórico |
| FR12 | 2 | origem da categoria |
| FR13 | 4 (base), 6, 7, 8 (cartões) | painel principal |
| FR14 | 3 (central + avisos de import), 4, 5, 6, 7, 8 (providers) | central de avisos |
| FR15 | 6 | receitas por pagador |
| FR16 | 6 | gastos e investimentos |
| FR17 | 6 | orçamento do mês |
| FR18 | 6 | custos fixos pagos × pendentes |
| FR19 | 2 | resgates como receita no histórico |
| FR20 | 6 | taxa de poupança |
| FR21 | 7 (posições), 8 (alocação × meta, bloco Objetivos) | posições e alocação |
| FR22 | 7 | rentabilidade XIRR nominal × real |
| FR23 | 7 | renda fixa pelo CDI real |
| FR24 | 7 (cadastro, valoração e o campo "Debênture" na Revisão de transações) | debêntures |
| FR25 | 7 | caixa em corretora e a caminho |
| FR26 | 7 | conciliação com a origem |
| FR27 | 7 (automático), 10 (aba Preços manuais) | preços sem digitação |
| FR28 | 8 | aporte planejado |
| FR29 | 8 | distribuição do aporte |
| FR30 | 8 | ajuste com travas |
| FR31 | 8 | realizado, a caminho e pendente |
| FR32 | 5 | fechar e reabrir mês |
| FR33 | 5 | ajuste em mês fechado |
| FR34 | 9 | comparar períodos |
| FR35 | 2, 6, 7, 8, 10 (cada aba no épico do seu domínio) | ajustes editáveis |
| FR36 | 1 (navegação), 10 (fim das rotas v1) | quatro áreas |

### UX-DR Coverage Map

| UX-DR | Story | | UX-DR | Story |
|---|---|---|---|---|
| UX-DR1, 2 | 1.4 | | UX-DR24 | 1.7 |
| UX-DR3, 4 | 1.5 | | UX-DR25 | 1.4 (base), 10.3 (teclado) |
| UX-DR5 | 1.4 | | UX-DR26 | 1.6 |
| UX-DR6, 7 | 1.6 | | UX-DR27 | 4.1, 4.2 (+ 6.3, 6.5, 7.2, 8.8) |
| UX-DR8 | 1.7 (+ Selo em 5.3, 5.5) | | UX-DR28 | 3.8 |
| UX-DR9 | 7.1 (+ 9.1) | | UX-DR29 | 3.12 |
| UX-DR10 | 1.4 | | UX-DR30 | 3.9 |
| UX-DR11 | 3.1 | | UX-DR31 | 2.6 |
| UX-DR12 | 4.1 | | UX-DR32 | 3.10 |
| UX-DR13 | 3.1, 4.2 | | UX-DR33 | 3.8, 3.11, 4.2 |
| UX-DR14 | 2.6 | | UX-DR34 | 8.8 |
| UX-DR15 | 4.1, 9.1 | | UX-DR35 | 6.3 |
| UX-DR16 | 3.11 | | UX-DR36 | 6.5, 6.6, 8.1 |
| UX-DR17 | 3.8, 4.1 | | UX-DR37 | 6.2 |
| UX-DR18 | 8.7 | | UX-DR38 | 8.5, 8.6, 8.7 |
| UX-DR19 | 1.4 (Sonner), 3.9 (primeiro uso) | | UX-DR39 | 7.5 |
| UX-DR20 | 2.7 | | UX-DR40 | 5.3, 5.4 |
| UX-DR21 | 3.12 | | UX-DR41 | 5.7 |
| UX-DR22 | 1.6, 3.8, 4.1 | | UX-DR42 | 9.3 |
| UX-DR23 | 1.6 | | UX-DR43 | 2.7, 2.8, 6.1, 7.4, 8.1, 8.2, 10.1, 10.2, 10.3 |
| | | | UX-DR44 | 3.1 (catálogo) + cada story que emite aviso |
| | | | UX-DR45 | 1.8 |

## Epic List

### Marco 1 — Ritual confiável

**Ponto de uso:** ao fim do Épico 3, o ritual semanal (importar, revisar, saldo PF conferido) passa a rodar na v2. O
Vitor começa a usá-lo antes do Painel e do fechamento, e o retorno dele alimenta os épicos 4 e 5.

### Epic 1: App novo de pé — 4 áreas, tema e operação local
O Vitor abre o app com o login no visual novo, a navegação só com Visão geral · Caixa · Investimentos · Ajustes + Importar,
o Seletor de período na URL e o tema claro/escuro; as telas atuais seguem acessíveis dentro das áreas. O banco local tem
backup diário antes de qualquer migração.
**FRs covered:** FR36 (navegação). **Também:** AR1, AR18, AR19, AR21, AR22, UX-DR1–UX-DR10, UX-DR19, UX-DR23–UX-DR26, UX-DR45.
**Notas:** Story 1.1 = arrumação (CLAUDE.md, conventions.md, `.env.example` às cegas, ADR-011 em `docs/07`). Componente
nasce onde é usado pela primeira vez; o épico não acumula componente sem tela.

### Epic 2: Categorias em dois níveis, regras e histórico corrigido
O Vitor passa a ver o histórico nos grupos aprovados, com a origem de cada categoria e o lote de cada transação, edita
categorias e regras em Ajustes e reaplica regras com prévia. Os resgates contam como receita em todo o histórico.
**FRs covered:** FR8, FR10 (edição em Ajustes), FR11, FR12, FR19, FR35 (Categorias, Regras).
**Notas:** começa pelas migrações 1–2 da AD-16 (`user_id` + `import_batches` com lotes `legacy`), depois 3–4 (grupos,
roles, `category_id`, `category_rules`, `category_source`; reclassificações). `categorize()` vira chokepoint e o Hermes é
ajustado na mesma story. `categories.key` imutável: código nunca lê nome de categoria. Testes de invariantes: 55,48%, contagem, zero órfãs, deltas esperados, mais um script de comparação **mês × categoria
antes e depois** com a lista dos deltas esperados (faturas → Cartão de crédito, Repasse → Devoluções, resgates);
qualquer delta fora da lista reprova. A Tabela de dados nasce aqui.

### Epic 3: Hub de import, revisão em lote e central de avisos
O ritual da UJ-1 de ponta a ponta: arrastar os arquivos, ver a prévia, confirmar, revisar pelo teclado, criar regra a
partir da correção, ver o saldo "conferido", desfazer o último lote — e os tropeços aparecendo no Sino e na Central de avisos.
**FRs covered:** FR1, FR2, FR3 (hub), FR4 (lacuna), FR5, FR6, FR9, FR10, FR14 (base + avisos de import, saldo, CSV,
revisão, fonte desatualizada).
**Notas:** `SourceAdapter` + adapters Nubank e B3 (AD-5); a tabela `assets` (migração 5 da AD-16) nasce aqui, antes dos
adapters B3, porque os snapshots do consolidado referenciam o ativo; base de avisos (AD-10: `Alert`/`AlertContext` em `common`,
engine `alerts`, `alert_dismissals`, Sino, Central). `MonthStatusPort` nasce em `common` com implementação padrão
"todos os meses abertos"; `ingest`, `categorize` e o desfazer já chamam `mark_dirty`, que o Épico 5 liga ao fechamento.

### Epic 4: Painel principal
A primeira tela responde como está o mês antes de qualquer tabela: KPIs com Carimbo de data, Linhas de aviso e Bloco Fontes.
Worker com falha ou atrasado vira aviso.
**FRs covered:** FR13 (base), FR3 (Painel), FR14 (aviso de worker).
**Notas:** engine `overview`; os épicos 6–8 acrescentam os próprios cartões. Painel < 3 s.

### Epic 5: Fechamento de mês e recuperação da base
O Vitor fecha o mês com checklist, reabre vendo congelado × recalculado e recebe o aviso de ajuste em mês fechado.
Jul/2024–mai/2026 entram fechados em bloco, e o Assistente de recuperação conduz jun → out/2026.
**FRs covered:** FR7, FR32, FR33, FR14 (ajuste em mês fechado, mês aberto há mais de 10 dias).
**Notas:** `month_summary_totals` nasce com **todas** as colunas da AD-7 (nulas); termo cuja engine ainda não existe =
`Valued` null com `unavailable_reason = fora_do_resumo` (tooltip "este número não existia quando o mês foi fechado · reabra
para incluir"); completar = reabrir + fechar pelo serviço, nunca SQL. `close_retro` depois das revisões de dado.
Registra o `MonthStatusPort` real (lote, reaplicação e desfazer em mês fechado viram ajuste). A trilha do Assistente de
recuperação é derivada dos dados: do mês seguinte ao bloco fechado (jun/2026) até o mês anterior a hoje. Patrimônio
retroativo: consolidado mensal só em jan–set/2026; 2024 e 2025 só o anual (= dezembro); demais meses "patrimônio não
coberto". Conferir = saldo da conta PF; sem saldo informado no fim do mês = pendência com "fechar mesmo assim".

### Marco 2 — Caixa e orçamento

### Epic 6: Orçamento do mês e custos fixos
O Vitor vê receitas por pagador, a Conta do orçamento (disponível, consumido, restante, consumo financiado por resgate),
informa as dívidas do mês e acompanha os custos fixos pagos × pendentes com casamento automático.
**FRs covered:** FR15, FR16, FR17, FR18, FR20, FR13 (Resumo de custos fixos), FR14 (vencendo/atrasado), FR35 (Custos fixos).
**Notas:** golden tests dos mockups; sem aporte planejado a linha mostra "não definido · Definir em Aportes"; mês sem
receita do trabalho = taxa de poupança `Valued` null (`sem_receita`), nunca 0%.

### Marco 3 — Investimentos e aportes (a SM-1 começa a contar)

### Epic 7: Investimentos sem digitação — posições, rentabilidade e conciliação
Posições classe → ativo, rentabilidade XIRR nominal × real por período, caixinhas/CDB pelo CDI real, debêntures
cadastradas no app, caixa em corretora e a caminho, e a aba Conciliação com as tolerâncias da AD-13.
**FRs covered:** FR21 (posições), FR22, FR23, FR24, FR25, FR26, FR27 (automático), FR4 (a caminho), FR13 (patrimônio,
rentabilidade), FR14 (divergências, a caminho), FR35 (Debêntures).
**Notas:** usa a tabela `assets` criada no Épico 3; movimentos restantes da AD-1 (benchmark → market, conciliação
wallet → portfolio).

### Epic 8: Aporte do mês, objetivos e distribuição
Objetivos vinculados às caixinhas (fora da alocação), metas com bandas e pisos, aporte planejado, Distribuição do aporte
com travas e realizado / a caminho / pendente; Resumo do aporte no Painel.
**FRs covered:** FR21 (alocação × meta, bloco Objetivos), FR28, FR29, FR30, FR31, FR13 (Resumo do aporte, classes fora da
banda), FR14 (aporte pendente, fora da banda), FR35 (Objetivos, Metas, reserva).
**Notas:** `planning/distribution.py` pura (AD-12), soma ao centavo.

### Marco 4 — Histórico e ajustes completos

### Epic 9: Histórico e comparação de períodos
O Vitor compara mês, trimestre, ano e desde o início com o anterior e a média 12m e lê os três gráficos com "Ver como tabela".
**FRs covered:** FR34.
**Notas:** o Gráfico de patrimônio mostra lacuna (sem interpolar) nos meses "patrimônio não coberto" (jan–nov/2025, jul–nov/2024).

### Epic 10: Ajustes completos e fim das telas antigas
As abas que faltam (Contas, Preços manuais), a revisão final das 8 abas com a checagem de teclado, as métricas de
sucesso num comando e a remoção das rotas da v1.
**FRs covered:** FR35 (Contas, Preços manuais), FR27 (preço manual), FR36 (fim das rotas v1).

## Epic 1: App novo de pé — 4 áreas, tema e operação local

O Vitor abre o app com o login no visual novo, a navegação só com Visão geral · Caixa · Investimentos · Ajustes +
Importar, o Seletor de período na URL e o tema claro/escuro; as telas atuais seguem acessíveis dentro das áreas. O banco
local tem backup diário antes de qualquer migração.

### Story 1.1: Arrumação dos docs vivos para a v2

As a Vitor (e os agentes que implementam o Goodies),
I want que CLAUDE.md, `conventions.md`, `.env.example` e `docs/07_Decisoes.md` descrevam a v2.0 local,
So that toda story seguinte parta das regras certas, sem Supabase/Upstash/Fly/Vercel nem padrões que não existem.

**Requisitos:** AR21, NFR7, NFR9.

**Acceptance Criteria:**

**Given** o CLAUDE.md atual
**When** a story termina
**Then** a stack descreve só o ambiente local (`docker compose` com postgres 15, redis 7 e api + `pnpm dev`), sem Supabase, Upstash, Fly ou Vercel
**And** a tabela de gates traz os gates da v2 (gate de dados jun/2026 = 55,48% e os critérios de fechamento de cada marco do PRD §6.1), citando ADR-014 e ADR-015

**Given** o `.claude/memory/conventions.md`
**When** a story termina
**Then** ele traz o layout de engine da AD-2 (`router`/`service`/`queries`/`models`/`calc`), o contrato de erro `{"error","message"}`, páginas como client components, as fontes Geist/Geist Mono e as regras de dinheiro da AD-4
**And** não cita `queries.py` que não existe nem Server Components como padrão

**Given** o `.env.example`
**When** as variáveis novas da v2.0 (ex.: diretório de backup) são adicionadas
**Then** o `.env.example` recebe só placeholders, o `.env` real é editado às cegas (nenhum valor aparece no chat) e os dois ficam com as mesmas chaves
**And** o gitleaks do pre-commit passa

**Given** o `docs/07_Decisoes.md`
**When** a story termina
**Then** o ADR-011 aparece como substituído pelo ADR-015 (resgate = receita), igual ao `.claude/memory/decisions.md`

### Story 1.2: Backup diário do banco local

As a Vitor,
I want que o banco local tenha backup automático todo dia e antes de toda migração,
So that a única cópia dos meus dados nunca se perca numa migração ou num erro.

**Requisitos:** AR19, AR22, NFR6, NFR13.

**Acceptance Criteria:**

**Given** o `docker compose up`
**When** o container da api sobe
**Then** ele roda, nesta ordem, backup → `alembic upgrade head` → uvicorn
**And** se o backup falhar e houver migração pendente, a migração não roda e a api não sobe, com o erro no log
**And** se o backup falhar sem migração pendente, a api sobe e a falha fica registrada em `job_runs` (vira aviso no Épico 4)

**Given** o scheduler da API
**When** chega o horário diário do job `db_backup`
**Then** um `pg_dump` é gravado no diretório configurado no `.env` (fora do repositório, via volume) com data no nome
**And** só os 30 backups mais recentes são mantidos
**And** a execução fica em `job_runs` como os demais jobs (catch-up incluído)

**Given** um arquivo de backup
**When** o Vitor segue o passo a passo de restauração do `docs/LOCAL_DEV.md` num banco vazio
**Then** o banco volta com as mesmas contagens de `transactions` e `asset_operations` (verificado num teste de restauração em `goodies_test`)

**Given** `python -m scripts.ops.restore_test_db`
**When** roda
**Then** restaura o backup mais recente em `goodies_test`, que vira a base dos testes de dado real (gate 55,48%, contagens, deltas)
**And** esses testes levam o marcador `@pytest.mark.dados_reais` e são pulados com aviso explícito quando a base não existe, nunca dando falso verde
**And** a base de teste fica só na máquina local, como a base real

**Given** o scheduler e os workers tocados nesta story
**When** registram eventos
**Then** usam `structlog` (o scheduler sai do `logging`), com evento snake e campos, nunca segredo nem valor financeiro

### Story 1.3: Versões da stack atualizadas

As a Vitor,
I want a stack nas versões travadas pela arquitetura,
So that as próximas stories partam de dependências atuais e sem vulnerabilidades conhecidas.

**Requisitos:** AR1, NFR13.

**Acceptance Criteria:**

**Given** o `web/package.json`
**When** a story termina
**Then** Next.js e `eslint-config-next` estão em 16.3.8, React e React DOM em 19.2.9, TypeScript 5.9.3, Tailwind 4.3.0, Recharts 3.8.1, next-themes 0.4.6, Node 24 e `packageManager` com pnpm 11
**And** `pnpm build` e `pnpm lint` passam e as telas atuais abrem sem erro no console

**Given** o `api/pyproject.toml`
**When** a story termina
**Then** FastAPI 0.136.3, asyncpg 0.31.0, Alembic 1.18.4, APScheduler 3.11.2, redis-py 8.0.0, Pydantic 2.13.4, SciPy 1.17.1 e structlog 25.5.0 estão travados no `uv.lock`
**And** a suíte `pytest` passa com cobertura ≥ 80% e `GET /api/v1/health` responde 200 com postgres e redis

**Given** o XIRR consolidado antes da atualização
**When** a suíte roda depois dela
**Then** o XIRR consolidado é igual ao anterior (teste de regressão)

### Story 1.4: Fundação visual — shadcn, tokens e tema

As a Vitor,
I want o app com a paleta e a tipografia do DESIGN.md, nos modos claro e escuro,
So that toda tela nova nasça com o mesmo visual e eu possa escolher o tema.

**Requisitos:** AR18, UX-DR1, UX-DR2, UX-DR5, UX-DR10, UX-DR19, UX-DR25.

**Acceptance Criteria:**

**Given** o `web/`
**When** o shadcn é inicializado
**Then** foi com `shadcn init -b radix`, estilo new-york, e o `components.json` está commitado
**And** os primitivos ficam em `web/components/ui/`, e `web/components/ui.tsx` vira uma fachada sobre eles para as telas v1 continuarem funcionando

**Given** o `web/app/globals.css`
**When** a story termina
**Then** ele traz todos os tokens de cor do DESIGN.md (claro e escuro, `@theme inline`, `color-scheme` por modo), com `--gain`→`--positive`, `--loss`→`--negative`, `--warning`/`--warning-dot`, tints, `row-highlight`, `input` separado de `border` e `chart-1..3`; o `--accent` índigo sai
**And** Geist e Geist Mono são carregadas, todo número usa `tabular-nums` e a escala tipográfica e os raios do DESIGN.md existem como tokens

**Given** o Switch de tema na Barra superior
**When** o Vitor escolhe Sistema, Claro ou Escuro
**Then** o tema troca na hora (next-themes, `defaultTheme="system"`) e a escolha persiste no navegador

**Given** qualquer elemento focável
**When** recebe foco pelo teclado
**Then** mostra o anel de 2px `ring` com offset de 2px, e contornos de controle usam `input` (≥ 3:1)

**Given** o Sonner (Toast)
**When** a story termina
**Then** está instalado sem customização (inferior direito, 4 s, sem botão), pronto para o primeiro uso

### Story 1.5: Guarda-corpos do visual — teste "no raw color" e theme-showcase

As a Vitor,
I want um teste que barra cor crua e uma página com todos os tokens e componentes,
So that o visual não se degrade a cada story nova.

**Requisitos:** UX-DR3, UX-DR4.

**Acceptance Criteria:**

**Given** o teste "no raw color"
**When** algum arquivo fora de `globals.css` usa hex, `rgb()`, `hsl()`, `oklch()` ou classe de paleta do Tailwind
**Then** `pnpm test` falha apontando o arquivo e a linha
**And** arquivos v1 ainda não migrados ficam numa lista de exceção explícita no teste, que só pode diminuir

**Given** `pnpm dev` em ambiente local
**When** o Vitor abre `/dev/tema`
**Then** vê todos os tokens e os componentes já existentes em todos os estados, claro e escuro lado a lado
**And** a rota não existe fora do ambiente local

**Given** uma story futura que cria componente
**When** termina
**Then** o componente aparece no `/dev/tema` (regra registrada em `conventions.md`)
### Story 1.6: Navegação em 4 áreas

As a Vitor,
I want a Barra lateral só com Visão geral, Caixa, Investimentos, Ajustes e o botão Importar,
So that eu ache tudo em no máximo dois cliques, em vez de 16 links soltos.

**Requisitos:** FR36, NFR11, AR18, UX-DR6, UX-DR7, UX-DR22, UX-DR23, UX-DR26.

**Acceptance Criteria:**

**Given** o app logado
**When** qualquer tela abre
**Then** a Barra lateral (240px) mostra as 4 áreas e o botão Importar fixo, com o item ativo marcado pela área da rota
**And** a Barra superior (56px) fica fixa no scroll, com espaço para o Seletor de período, o Sino de avisos e o Switch de tema

**Given** as rotas `web/app/(app)/{visao-geral,caixa,investimentos,ajustes}/<aba>`
**When** o Vitor entra numa área
**Then** as sub-telas aparecem como Abas na URL (←/→ trocam de aba), e as telas v1 ficam acessíveis como abas ou links dentro da área correspondente (ex.: Investimentos › Posições abre a tela atual de posições)
**And** as URLs antigas continuam abrindo as telas v1

**Given** o botão Importar
**When** é clicado em qualquer tela
**Then** abre um painel lateral (560px, entrada 200 ms / saída 150 ms, foco preso, Esc fecha, foco volta ao botão) com os imports atuais (Nubank e B3) até o Hub chegar no Épico 3

**Given** viewport entre 1024 e 1279px ou abaixo de 1024px (ou zoom de 200%)
**When** a tela renderiza
**Then** o conteúdo degrada ou reflui para uma coluna conforme o DESIGN.md, a Barra lateral empilha acima do conteúdo abaixo de 1024px e nada é cortado

**Given** a raiz `/` e o login concluído
**When** o Vitor entra no app
**Then** cai em Visão geral

### Story 1.7: Período na URL e formatação financeira

As a Vitor,
I want escolher o mês no Seletor de período e ver todo número no formato completo,
So that link, recarga e voltar mantenham o contexto e nenhum valor apareça abreviado.

**Requisitos:** AR15, UX-DR8, UX-DR24.

**Acceptance Criteria:**

**Given** a Barra superior
**When** o Vitor usa o Seletor de período
**Then** o mês aparece como "out/2026" (mono, minúsculo), ‹ › navegam e o popover lista os meses
**And** trocar o mês mantém a área e a aba, e o período fica na URL (`?periodo=2026-10`)

**Given** a URL sem período
**When** a tela abre
**Then** o período é o mês atual (BRT)

**Given** um mês futuro ou anterior a jul/2024
**When** o Vitor tenta escolhê-lo
**Then** está desabilitado com o tooltip "Sem dados antes de jul/2024" (ou futuro), e uma URL com período anterior cai em jul/2024

**Given** o `web/lib/format`
**When** formata valores
**Then** moeda sai completa com centavos e espaço não separável após "R$" (nunca mil, k ou MM), o sinal é o menos tipográfico, percentual tem 2 casas e sufixo de período (a.a., a.m.), desvio sai em p.p. com sinal e sem seta, data em dd/mm/aaaa e mês como "out/2026"
**And** o módulo só formata (não faz conta de dinheiro) e tem testes Vitest, incluindo zero, negativo e valores grandes

**Given** o utilitário de período do web
**When** resolve `periodo` + `leitura` (mes, tri, ano, inicio)
**Then** devolve os meses certos (trimestre civil até o período; ano de jan até o período; início de jul/2024 até o período), com testes Vitest

### Story 1.8: Login no visual novo e sessão que volta ao lugar

As a Vitor,
I want entrar pelo login novo e, se a sessão expirar, voltar à mesma tela e período,
So that eu não perca o contexto no meio do ritual.

**Requisitos:** AR18, AR19, NFR7, UX-DR45.

**Acceptance Criteria:**

**Given** a tela `/login`
**When** o Vitor abre
**Then** ela usa os tokens e componentes novos, com o mesmo fluxo JWT da v1 (ADR-006)

**Given** uma chamada à API que volta 401
**When** o cliente tenta o refresh pelo cookie httpOnly
**Then** se o refresh funcionar, a chamada original é repetida sem o Vitor perceber
**And** se falhar, o app vai para `/login?next=<rota+query>` e, depois do login, volta para essa rota com o período

**Given** o access token
**When** o app está aberto
**Then** ele vive só em memória (nunca em `localStorage`)

**Given** o backend local
**When** responde ao navegador
**Then** o CORS só aceita `http://localhost:3000` e o cookie de refresh é `httpOnly`, `samesite=lax` e sem `secure` em localhost

## Epic 2: Categorias em dois níveis, regras e histórico corrigido

O Vitor passa a ver o histórico nos grupos aprovados, com a origem de cada categoria e o lote de cada transação, edita
categorias e regras em Ajustes e reaplica regras com prévia. Os resgates contam como receita em todo o histórico.

### Story 2.1: Proveniência do histórico em lotes legado

As a Vitor,
I want que cada transação e operação já gravada saiba de qual lote e fonte veio,
So that o histórico tenha a mesma proveniência dos imports novos e nada fique sem origem.

**Requisitos:** NFR4, AR6, AR17, AR19.

**Acceptance Criteria:**

**Given** a base atual
**When** a revisão Alembic `0016` roda
**Then** as tabelas do ledger ganham `user_id` NOT NULL preenchido pelo owner único (`common.owner.get_owner_id`)
**And** a revisão é idempotente e roda depois do backup da Story 1.2

**Given** a revisão `0017`
**When** roda
**Then** existem `import_batches` (status `staged`, `applied`, `undone`, `legacy`) e `import_batch_files` (fonte, conta/corretora, `period_start`, `period_end`, hash do arquivo, saldo informado), donas da engine `ingest`
**And** é criado um lote `legacy` por fonte e conta, com `period_start`/`period_end` tirados das linhas existentes, e toda linha de `transactions` e `asset_operations` recebe `batch_id` e `source`

**Given** o teste de invariantes da revisão
**When** roda em `goodies_test` com a cópia dos dados
**Then** a contagem de `transactions` e `asset_operations` é a mesma de antes, nenhuma linha fica sem `batch_id` e a taxa de poupança de jun/2026 continua 55,48%

**Given** a engine `ingest`
**When** a story termina
**Then** ela segue o layout da AD-2 e expõe por `service`/`queries` a leitura dos lotes e arquivos, sem SQL de outra engine sobre essas tabelas

### Story 2.2: Categorias em dois níveis com o histórico migrado

As a Vitor,
I want que minhas 33 categorias virem subcategorias dos grupos aprovados, sem perder nenhuma transação,
So that eu leia gastos e receitas por grupo e subcategoria em todo o histórico.

**Requisitos:** FR8, AR7, AR17, AR23, NFR3.

**Acceptance Criteria:**

**Given** a revisão `0018`
**When** roda
**Then** existe `category_groups` com `kind` (receita, gasto, investimento, transferência) e `categories` ganha `group_id` e `role` (CHECK: `work_income`, `resgate`, `devolucao`, `divida`, `consumo`, `investimento`, `transferencia`, `a_classificar`)
**And** os grupos e subcategorias iniciais aprovados no party mode existem (incluindo a nova "Cartão de crédito", Trabalho = Recorrente/Extra, Resgates por destino, Devoluções = Repasse/Reembolso), com os roles certos

**Given** as transações e custos fixos com categoria em texto
**When** a revisão preenche `transactions.category_id` e `fixed_costs.category_id` por nome
**Then** zero linhas ficam órfãs e a coluna de texto continua existindo (sai numa versão posterior)
**And** "Cripto Nubnak" passa a se chamar "Cripto Nubank"

**Given** a coluna `categories.key` (imutável, única, ex.: `invest:toro_b3`, `invest:cripto_nubank`, `invest:caixinha_rdb`)
**When** a revisão preenche a `key` de cada categoria
**Then** `transit.RAILS`, `CaixinhaSpec.source_categories` e `settings.crypto_ledger_categories` passam a referenciar `key`, na mesma story do renome; nenhum código lê nome de categoria
**And** um teste renomeia cada categoria referenciada e prova que XIRR, trânsito e bloco cripto não mudam

**Given** os grupos de sistema
**When** a revisão termina
**Then** existem as subcategorias "Entrada a classificar" e "Saída a classificar" (role `a_classificar`), uma por tipo pelo sinal

**Given** o script de comparação mês × categoria
**When** roda antes e depois da revisão
**Then** os totais por mês e categoria são idênticos (esta revisão não reclassifica nada) e a contagem de transações não muda

### Story 2.3: Regras e origem da categoria no histórico

As a Vitor,
I want que as regras atuais virem regras editáveis e que cada transação saiba de onde veio a categoria,
So that minha curadoria manual fique protegida e eu saiba por que cada transação tem a categoria que tem.

**Requisitos:** FR10, FR12, AR7, AR17, AR23.

**Acceptance Criteria:**

**Given** a revisão `0019`
**When** roda
**Then** existem `category_rules` ("descrição contém", categoria, ativa, `created_in_batch`), migradas de `categories.match_patterns` com origem legado, e `categorization_events` (antes, depois, origem, lote; append-only)
**And** `transactions` ganha `category_source` ∈ {rule, suggestion, manual}, `review_status` ∈ {pending, confirmed}, `category_rule_id` (FK `ON DELETE SET NULL`) e `payer`

**Given** o histórico existente
**When** a revisão preenche a origem
**Then** a transação cuja descrição bate com um padrão atual fica `rule` com a regra correspondente; as demais ficam `manual`; todas ficam `confirmed`
**And** o `payer` é preenchido a partir das subcategorias atuais (Flash Capital e Betuel viram Recorrente com o pagador preenchido)

**Given** o script de comparação mês × categoria
**When** roda antes e depois da revisão
**Then** os totais são idênticos e a contagem de transações não muda

### Story 2.4: Categorização por um caminho só

As a Vitor,
I want que toda mudança de categoria passe por uma única função,
So that regra, sugestão e correção manual sigam as mesmas regras e nada sobrescreva o que categorizei à mão.

**Requisitos:** FR12, AR7, NFR12.

**Acceptance Criteria:**

**Given** `ledger.service.categorize()`
**When** qualquer código muda a categoria de uma transação
**Then** passa por essa função, que grava `category_id`, a cópia de `kind` do grupo, `category_source`, uma linha em `categorization_events` e chama os hooks `on_transactions_changed` registrados (registro vazio por enquanto)
**And** uma transação `manual` nunca é sobrescrita por regra ou sugestão
**And** vence a regra de condição mais longa; empate → a mais recente

**Given** o teste de invariante de `kind`
**When** roda na suíte e no `/gate`
**Then** falha se alguma transação tiver `kind` diferente do `kind` do grupo da sua categoria

**Given** os caminhos de escrita existentes (import Nubank atual, `ledger/transactions.py`, `suggest.py`)
**When** a story termina
**Then** todos chamam `categorize()`; nenhum `UPDATE` de categoria fica fora dela

**Given** o Hermes (`api/hermes/`)
**When** grava uma transação
**Then** usa `ledger.service` e `categorize()`, e os testes dele continuam passando
### Story 2.5: Resgates como receita e reclassificações do histórico

As a Vitor,
I want que os resgates antigos contem como receita e que as faturas e o Repasse fiquem nos grupos certos,
So that o histórico siga as regras de leitura do dinheiro da v2 sem mudar a minha taxa de poupança.

**Requisitos:** FR19, FR20, AR8, AR17, AR23, NFR3.

**Acceptance Criteria:**

**Given** a revisão `0020`
**When** roda
**Then** os resgates gravados como investimento pela regra do ADR-011 passam para subcategorias de Resgates (role `resgate`, tipo receita), as 18 "Pagamento de fatura" em Dívidas (2024–nov/2025) vão para "Cartão de crédito", e o Repasse sai de Trabalho para Devoluções
**And** as 4 faturas em Assinaturas (abr–mai/2026) não mudam
**And** cada mudança gera linha em `categorization_events` e a revisão é idempotente (rodar duas vezes não muda nada)

**Given** as funções puras de `ledger/calc`
**When** calculam receita do trabalho, resgates, devoluções, gastos e taxa de poupança por `role`
**Then** a taxa de poupança de jun/2026 é 55,48% (golden test) e nenhuma função lê nome de categoria

**Given** o script de comparação mês × categoria
**When** compara antes e depois da revisão
**Then** só aparecem os deltas da lista esperada (resgates, faturas → Cartão de crédito, Repasse → Devoluções) e qualquer outro delta reprova o teste

**Given** as `asset_operations` derivadas de caixinhas
**When** a revisão roda
**Then** continuam iguais

**Given** as telas v1 (dashboard e análise)
**When** abrem depois da revisão
**Then** a taxa de poupança exibida continua a mesma, usando as funções de `ledger/calc` em vez de somar `kind = income`

### Story 2.6: Caixa › Transações com origem e correção de categoria

As a Vitor,
I want ver as transações do mês com categoria, origem e lote, e corrigir uma categoria na linha,
So that eu saiba de onde veio cada número e conserte o que estiver errado.

**Requisitos:** FR12, FR16, AR16, UX-DR14, UX-DR31.

**Acceptance Criteria:**

**Given** a aba Caixa › Transações com um período
**When** abre
**Then** mostra data, descrição, valor, tipo de movimento (rótulo em texto), "Grupo › Subcategoria", origem da categoria, pagador e conta, via `GET /api/v1/ledger/transactions` paginada (`{items,total,limit,offset}`, `Money`)
**And** a linha expandida mostra fonte, lote e regra aplicada

**Given** a Tabela de dados (TanStack Table v9)
**When** usada aqui pela primeira vez
**Then** tem os modos Resumo e Detalhado lembrados por tabela, ordenação por coluna, grupos expansíveis por clique ou →/←, filtro de texto acima de 20 linhas e rolagem horizontal com primeira coluna fixa, num contêiner focável, sem cortar valor
**And** números ficam à direita em mono tabular e os cabeçalhos usam `<th scope>`

**Given** o Combobox de categoria na linha
**When** o Vitor busca ("merc" → "Alimentação › Mercado") e escolhe com ↑↓ + Enter
**Then** a categoria muda via `categorize()` com origem `manual` e a tag da linha passa a "manual"
**And** arquivadas não aparecem e Esc fecha sem mudar nada

**Given** um período sem transações
**When** a aba abre
**Then** mostra "Nenhuma transação em {mês}. Importe o extrato do Nubank."

### Story 2.7: Ajustes › Categorias

As a Vitor,
I want criar, renomear e arquivar grupos e subcategorias no app,
So that eu ajuste a classificação sem mexer em código.

**Requisitos:** FR8, FR35, UX-DR20, UX-DR43.

**Acceptance Criteria:**

**Given** Ajustes › Categorias
**When** abre
**Then** mostra a árvore grupo › subcategoria com tipo de movimento e role; arquivadas ficam ocultas e "Mostrar arquivadas" as exibe esmaecidas

**Given** o Formulário em painel lateral
**When** o Vitor cria uma subcategoria
**Then** ela herda o tipo do grupo e o role padrão dele (`consumo` em gasto, `work_income` em receita, `investimento`, `transferencia`), que pode ser trocado
**And** a validação acontece ao sair do campo e no Salvar, com a mensagem sob o campo; salvo, o painel fecha com o Toast "{Item} salvo." e o foco volta à linha
**And** Esc com alterações pergunta "Descartar alterações?"; sem alterações, fecha direto

**Given** uma categoria com transações
**When** o Vitor tenta apagá-la
**Then** só "Arquivar" está disponível, e o histórico continua com ela

**Given** um renome
**When** o Vitor renomeia
**Then** o aviso "reflete em todo o histórico" aparece antes de salvar e o novo nome aparece em todas as telas

**Given** um grupo com transações
**When** o Vitor tenta mudar o tipo dele
**Then** é recusado; mover uma subcategoria para outro grupo regrava o `kind` das transações dela via `categorize()`

**Given** a aba sem categorias
**When** abre
**Then** mostra "Nenhuma categoria. Crie o primeiro grupo." com a ação Nova categoria

### Story 2.8: Ajustes › Regras e reaplicar regras ao histórico

As a Vitor,
I want editar e desativar regras e reaplicá-las a um período com prévia,
So that o histórico fique coerente com as regras sem tocar no que categorizei à mão.

**Requisitos:** FR10, FR11, FR35, AR16, UX-DR43.

**Acceptance Criteria:**

**Given** Ajustes › Regras
**When** abre
**Then** lista condição ("descrição contém"), categoria e estado ativa/inativa
**And** sem regras, mostra "Nenhuma regra. Regras nascem na revisão quando você corrige uma categoria."

**Given** a edição de uma condição
**When** o Vitor digita
**Then** a prévia das transações afetadas vem de `POST /api/v1/ledger/rules/preview` (não grava)

**Given** Reaplicar regras com um período
**When** o Vitor pede a prévia
**Then** vê antes × depois por transação e "{n} categorias manuais não serão alteradas"
**And** ao confirmar, as mudanças passam por `categorize()` com origem `rule`, numa transação, e nenhuma categoria `manual` muda

**Given** uma regra desativada
**When** novas transações chegam
**Then** ela não é aplicada, mas as transações que já categorizou mantêm a categoria

## Epic 3: Hub de import, revisão em lote e central de avisos

O ritual da UJ-1 de ponta a ponta: arrastar os arquivos, ver a prévia, confirmar, revisar pelo teclado, criar regra a
partir da correção, ver o saldo da conta PF "conferido", desfazer o último lote — e os tropeços aparecendo no Sino e na
Central de avisos. Ao fim deste épico, o ritual semanal passa a rodar na v2 (ponto de uso).

### Story 3.1: Central de avisos e Sino

As a Vitor,
I want um lugar único com tudo que pede ação, e um contador sempre à vista,
So that nenhum tropeço passe despercebido.

**Requisitos:** FR14, AR11, UX-DR11, UX-DR13, UX-DR44.

**Acceptance Criteria:**

**Given** `common`
**When** a story termina
**Then** existem `Alert` (key `<tipo>:<sujeito>`, fingerprint, severity ∈ {divergencia, aviso}, mensagem pt-BR, ação com rota e parâmetros, `as_of`, `dismissible`), `AlertContext` (hoje BRT, período, status dos meses, owner) e `MonthStatusPort` com a implementação padrão "todos os meses abertos"
**And** o `Alert` do ledger passa para `common` (AD-1) e os avisos de vencimento atuais viram um provider, para a tela v1 continuar funcionando

**Given** a engine `alerts`
**When** `GET /api/v1/alerts` é chamado
**Then** junta os providers registrados em `main.py` na leitura (compute-on-read) e devolve divergências antes de avisos, mais recentes primeiro

**Given** um aviso dispensado
**When** a condição continua igual
**Then** ele não volta; volta só se o fingerprint mudar, e some quando o provider para de emiti-lo (`alert_dismissals` guarda só a dispensa)

**Given** a Barra superior
**When** existem avisos ativos
**Then** o Sino mostra o total (sem vermelho, sem contador quando zero, `aria-live` polite) e abre a Central de avisos (painel lateral de 560px, foco no primeiro aviso)
**And** cada Linha de aviso tem ponto, tag de severidade em slot de largura fixa, mensagem do catálogo do EXPERIENCE e uma ação em link, que leva à tela filtrada e fecha o painel
**And** sem avisos, mostra "Nenhum aviso. Dados até {dd/mm/aaaa}."

### Story 3.2: Ativos com chave única

As a Vitor,
I want que cada ativo tenha uma identidade só, usada por B3, carteiras e caixinhas,
So that posições, operações e metas falem do mesmo ativo sem rótulos divergentes.

**Requisitos:** AR2, AR12, AR17.

**Acceptance Criteria:**

**Given** a revisão `0021` (migração 5 da AD-16, depois das reclassificações)
**When** roda
**Then** existe `assets` (dono `portfolio`: `id` uuid, `key` imutável como `b3:BBAS3`, `td:IPCA+2032`, `caixinha:turbo`, `crypto:BTC`, classe, `price_ref`, valoração, %CDI) e `asset_aliases(asset_id, chain, symbol)`
**And** `asset_operations`, `portfolio_targets` e `wallet_positions` ganham `asset_id` preenchido por um mapa explícito dos rótulos legados, com zero órfãos

**Given** os enums de `portfolio/constants.py`
**When** a story toca o módulo
**Then** eles passam para `common` (AD-1)

**Given** o teste de invariantes
**When** roda
**Then** a contagem de operações, o aplicado por classe e o XIRR consolidado são iguais aos de antes

**Given** as telas v1 de posições, alocação e carteiras
**When** abrem depois da revisão
**Then** mostram os mesmos números

### Story 3.3: Import com prévia e lote — protocolo e OFX do Nubank

As a Vitor,
I want importar o OFX do Nubank vendo antes o que é novo e o que já existe,
So that nada seja gravado sem eu confirmar e reimportar nunca duplique.

**Requisitos:** FR1, FR2, AR6, NFR2, NFR4.

**Acceptance Criteria:**

**Given** a engine `ingest`
**When** a story termina
**Then** existe o protocolo `SourceAdapter` (`detect`, `parse`, `plan`, `apply`, `undo`), com adapters registrados em `main.py` e vivendo na engine dona, e os registros de hooks `on_batch_applied`/`on_batch_undo`

**Given** um ou mais arquivos enviados para `POST /api/v1/ingest/preview`
**When** a prévia é calculada
**Then** cria um lote `staged` com o plano e um hash (expira em 24 h) e devolve, por arquivo, fonte, conta, período, novos, existentes e pulados; nada de fato é gravado

**Given** um OFX do Nubank
**When** é detectado
**Then** é associado à conta pelo número da conta no próprio arquivo e a dedup usa o FITID

**Given** `POST /api/v1/ingest/confirm` com o lote e o hash
**When** confirma
**Then** re-planeja, exige o mesmo hash e roda todos os `apply` numa única transação; o lote vira `applied`, grava `import_batch_files` e o cache de XIRR é invalidado
**And** cada transação nova entra via `categorize()` por regra, por sugestão ou em "Entrada/Saída a classificar", sempre `pending`, com `batch_id` e `source`
**And** `ingest` chama `MonthStatusPort.mark_dirty(month)` para os meses tocados (sem efeito até o Épico 5)

**Given** o mesmo arquivo de novo
**When** a prévia roda
**Then** dá 0 novas e o provider emite "Arquivo já importado: {nome}. 0 transações novas."

**Given** o import Nubank atual (`ledger/importer.py`, página v1)
**When** a story termina
**Then** passa pelo protocolo, e a página v1 continua funcionando (ou redireciona para o Painel provisório de Importar)

### Story 3.4: OFX completo — titular, pagador, saldo informado e caixinhas

As a Vitor,
I want que o OFX traga o pagador, o saldo informado e as operações das caixinhas,
So that receitas, conferência e posições fiquem certas desde o import.

**Requisitos:** FR1, FR5, FR15, AR6, AR7.

**Acceptance Criteria:**

**Given** a revisão da story
**When** roda
**Then** `accounts` ganha `holder` ∈ {pf, mei} (Nubank_CPF → pf, Nubank_CNPJ → mei) e existe `account_balances` (conta, data, saldo informado, `batch_id`), dona de `ledger`
**And** `asset_operations` ganha `transaction_id` com FK `ON DELETE RESTRICT`

**Given** um OFX aplicado
**When** as transações são gravadas
**Then** o pagador é extraído (nome no Pix ou CNPJ) para `transactions.payer`, nunca atribui categoria, e o `LEDGERBAL` vai para `account_balances`
**And** um OFX do MEI que cobre vários meses é aceito normalmente

**Given** o hook `on_batch_applied`
**When** um lote Nubank é aplicado
**Then** o `portfolio` deriva as operações de caixinhas/CDB com a lógica atual (`caixinhas.py`), idempotente por `transaction_id`, na mesma transação, para a tela v1 de posições não ficar defasada
**And** reimportar ou reaplicar o hook não duplica operações
### Story 3.5: Sugestão de categoria para toda transação nova

As a Vitor,
I want que toda transação nova sem regra venha com uma sugestão, de qualquer tipo,
So that a revisão seja confirmar em vez de categorizar do zero.

**Requisitos:** FR9, NFR12 (SM-5).

**Acceptance Criteria:**

**Given** uma transação nova sem regra que bata
**When** o adapter chama `categorize()`
**Then** recebe a sugestão da transação confirmada mais parecida pela descrição (receita, gasto, investimento ou transferência; não só despesa em "outros"), com origem `suggestion` e `pending`
**And** sem histórico parecido, fica em "Entrada/Saída a classificar" e aparece como "sem sugestão"

**Given** uma sugestão
**When** nunca foi confirmada
**Then** não conta como categoria definitiva: entra nas leituras com a categoria proposta e em "transações a revisar"

**Given** o `suggest.py` atual
**When** a story termina
**Then** foi estendido (ou substituído) em `ledger`, com testes para cada tipo de movimento e para o caso sem histórico

### Story 3.6: CSV do Nubank

As a Vitor,
I want importar também o CSV do Nubank,
So that eu não fique travado quando só tiver o CSV.

**Requisitos:** FR1, FR14.

**Acceptance Criteria:**

**Given** um CSV do Nubank
**When** entra na prévia
**Then** é detectado, associado à conta e deduplicado contra o que já existe
**And** a prévia avisa "CSV não permite conferir o saldo. Prefira o OFX."

**Given** um lote aplicado com CSV
**When** os avisos são lidos
**Then** aparece "CSV importado sem conferência de saldo. Só o OFX permite conferir." com a ação Importar OFX

**Given** um arquivo de formato desconhecido
**When** entra na prévia junto com outros
**Then** só ele é recusado, com "Formato não reconhecido. Aceitos: OFX Nubank, CSV Nubank, B3 movimentação, negociação e consolidado (.xlsx).", e os outros seguem

### Story 3.7: Adapters da B3 — movimentação, negociação e consolidado

As a Vitor,
I want importar os três relatórios da B3 pelo mesmo fluxo,
So that operações e posições entrem sem duplicar e o consolidado fique guardado para conferência e fechamento.

**Requisitos:** FR1, FR2, AR6.

**Acceptance Criteria:**

**Given** um xlsx de movimentação ou negociação
**When** entra na prévia
**Then** é detectado, a dedup usa o `operation_hash` e o `plan` mantém a regra de cobertura por ticker (`_ticker_cutoffs`), reportando os pulados
**And** a mesma operação vinda de movimentação e de negociação entra uma vez só

**Given** um consolidado (mensal ou anual)
**When** é aplicado
**Then** grava `broker_position_snapshots` (criada nesta story, dona `portfolio`: data de referência, `asset_id`, quantidade, valor informado, `batch_id`); o anual vale para 31/12

**Given** os imports B3 atuais (`b3_import*`, páginas v1)
**When** a story termina
**Then** passam pelo protocolo `SourceAdapter`, e as telas v1 de import continuam funcionando (ou redirecionam para o Hub)

**Given** os arquivos reais de `files/b3/`
**When** são importados num banco de teste com a base atual
**Then** dão 0 operações novas onde a base já cobre e o XIRR B3+TD não muda

### Story 3.8: Hub de import

As a Vitor,
I want arrastar todos os arquivos num painel só e confirmar depois de ver a prévia,
So that o import da semana seja um passo só.

**Requisitos:** FR1, FR2, FR3, FR4, UX-DR17, UX-DR22, UX-DR28, UX-DR33.

**Acceptance Criteria:**

**Given** o botão Importar
**When** é clicado em qualquer tela
**Then** abre o Hub de import (560px, foco na dropzone), substituindo o painel provisório do Épico 1

**Given** vários arquivos soltos na dropzone
**When** cada um é lido
**Then** a linha mostra "Lendo {nome}…" com o Esqueleto da prévia, depois a fonte detectada; o formato desconhecido é recusado na linha sem travar os outros
**And** a prévia por fonte (novos, existentes, período, conta ou corretora) aparece numa Tabela de dados
**And** Confirmar import só habilita depois de todas as prévias; havendo transações novas, ao confirmar abre a Revisão de transações

**Given** o Bloco Fontes no topo do Hub
**When** abre
**Then** mostra uma linha por fonte de arquivo (Nubank PF e MEI; B3 movimentação, negociação e consolidado) com tipo e o atualizado até derivado só de `import_batch_files` dos lotes `applied` e `legacy`

**Given** os limites do FR-3
**When** uma fonte passa do limite (Nubank 7 dias; consolidado do mês anterior não importado até o dia 15)
**Then** o provider emite "{Fonte} sem import desde {dd/mm/aaaa}." e o Bloco Fontes mostra o ponto de aviso

**Given** um intervalo sem arquivo entre o primeiro e o último import de uma fonte
**When** os avisos são lidos
**Then** aparece "Lacuna em {fonte}: {dd/mm/aaaa} a {dd/mm/aaaa}." com a ação Importar

**Given** uma falha ao confirmar
**When** a API recusa ou cai
**Then** o Hub mostra "Não foi possível confirmar o import. Nada foi perdido. Tentar de novo.", os arquivos continuam carregados e o foco vai para "Tentar de novo"

### Story 3.9: Revisão de transações

As a Vitor,
I want revisar todas as transações novas numa lista com checks e confirmar em lote pelo teclado,
So that eu categorize a semana em poucos minutos.

**Requisitos:** FR9, FR14, UX-DR19, UX-DR30.

**Acceptance Criteria:**

**Given** um lote aplicado com transações `pending`
**When** a Revisão de transações abre (painel largo, `min(1040px, 100vw − 48px)`)
**Then** todas as linhas vêm marcadas, cada uma com a tag de origem ("regra", "sugestão", "sem sugestão" ou "manual") e o foco na primeira linha
**And** um lote com vários meses aparece agrupado por mês, com subtotais vindos da API

**Given** o teclado
**When** o Vitor usa ↑↓, Espaço, C e Enter
**Then** ↑↓ movem o foco, Espaço marca/desmarca, C abre o Combobox da linha e Enter confirma ("Confirmar {n} transações")
**And** Shift+clique marca o intervalo desde a última linha tocada (só mouse)

**Given** a troca de categoria numa linha
**When** o Vitor escolhe outra
**Then** a tag vira "manual" e o cabeçalho reconta

**Given** uma linha marcada sem categoria
**When** existe
**Then** o Confirmar fica desabilitado e o rodapé diz "{n} sem categoria. Escolha a categoria ou desmarque a linha." (`aria-describedby` no botão)

**Given** a confirmação
**When** o Vitor confirma
**Then** as marcadas ficam `confirmed` via `categorize()`, as desmarcadas seguem `pending`, e o Toast diz "{n} transações confirmadas. {m} continuam a revisar."
**And** enquanto houver `pending`, o provider emite "{n} transações a revisar." com a ação Revisar

**Given** o filtro "Só sem categoria" ou um lote todo por regra
**When** não há linhas a mostrar
**Then** aparece "Nenhuma transação sem categoria." (com Limpar filtro) ou "Nada a revisar. Todas as transações do lote vieram de regras."

### Story 3.10: Proposta de regra a partir da correção

As a Vitor,
I want que o app me ofereça criar uma regra quando corrijo uma categoria,
So that a mesma correção não precise ser feita toda semana.

**Requisitos:** FR10, UX-DR32.

**Acceptance Criteria:**

**Given** uma linha cuja categoria veio de regra ou sugestão e foi trocada (na Revisão ou em Caixa › Transações)
**When** a troca acontece
**Then** aparece sob a linha a faixa "Criar regra? Descrição contém '{texto}' → {categoria}. Afeta {n} outras transações.", sem bloquear o resto

**Given** a faixa
**When** o Vitor escolhe Criar regra
**Then** a regra é gravada (com `created_in_batch` quando vier da Revisão) e aplicada às outras transações afetadas que não são `manual`
**And** Ajustar condição mostra a prévia ao vivo via `POST .../preview`, e Agora não fecha a faixa

**Given** o lote confirmado sem responder à faixa
**When** confirma
**Then** vale como Agora não

### Story 3.11: Conferência do saldo da conta PF

As a Vitor,
I want que o app confira o saldo da conta PF com o do OFX ao centavo,
So that eu tenha certeza de que não falta nem sobra nenhuma transação.

**Requisitos:** FR5, FR14, AR14, UX-DR16, UX-DR33.

**Acceptance Criteria:**

**Given** a revisão da story
**When** roda
**Then** `accounts` ganha `opening_balance` e `opening_balance_date`, e a conta PF é ancorada no saldo informado mais antigo (o OFX de jun/2026): `opening_balance` = saldo informado na âncora − Σ transações até essa data, com a âncora registrada
**And** datas anteriores à âncora não são conferidas

**Given** um OFX da conta PF aplicado depois da âncora
**When** o saldo calculado (`opening_balance` + Σ transações até a data, em `ledger/calc`) é comparado ao saldo informado
**Then** com diferença de R$ 0,00 o Bloco Fontes mostra o Selo de estado "conferido" com a data
**And** com qualquer diferença mostra "divergente · R$ {valor}", e o provider emite "Saldo divergente em R$ {valor} na conta PF." (severidade divergência) com a ação Ver transações, que leva às transações candidatas

**Given** um OFX da conta MEI (`holder = mei`)
**When** é aplicado
**Then** não há conferência de saldo; o Bloco Fontes mostra só o atualizado até do MEI

**Given** o Selo de estado
**When** usado aqui pela primeira vez
**Then** é uma pílula minúscula com o vocabulário fechado do EXPERIENCE (neutro, aviso, divergência), com tooltip, nunca verde
### Story 3.12: Desfazer o último lote e Histórico de imports

As a Vitor,
I want desfazer o último import se errei o arquivo,
So that um engano não suje a base.

**Requisitos:** FR6, UX-DR21, UX-DR29.

**Acceptance Criteria:**

**Given** o Histórico de imports no rodapé do Hub
**When** abre
**Then** lista os lotes do mais recente para o mais antigo, com data, arquivos e contagens; só o último lote `applied` com até 7 dias tem "Desfazer"
**And** se o último lote tem mais de 7 dias ou é `legacy`, mostra "Último lote: {dd/mm/aaaa}. Prazo de desfazer encerrado." (ou que lotes legado não se desfazem)

**Given** Desfazer
**When** o Vitor clica
**Then** o Diálogo de confirmação (foco em Cancelar) mostra o efeito em números, vindo de `POST /api/v1/ingest/batches/{id}/undo/preview` ("Remove 43 transações, 2 operações, 38 categorizações e 2 regras do lote de 17/10/2026.")

**Given** a confirmação
**When** o desfazer roda
**Then** numa transação: os hooks `on_batch_undo` rodam em ordem decrescente de camada (`portfolio` remove as operações derivadas), depois o `undo` de cada adapter; saem as transações, as `categorization_events` delas e as regras com `created_in_batch` do lote
**And** transações de fora do lote categorizadas por uma regra removida voltam por `categorize()` sem ela (`suggestion`, `pending`)
**And** o lote vira `undone`, os meses tocados chamam `mark_dirty` e o cache de XIRR é invalidado

## Epic 4: Painel principal

A primeira tela responde como está o mês antes de qualquer tabela: KPIs com Carimbo de data, Linhas de aviso e Bloco
Fontes. Worker com falha ou atrasado vira aviso.

### Story 4.1: Painel principal com KPIs datados

As a Vitor,
I want abrir o app e ver o resultado do mês, o patrimônio e a rentabilidade, cada um com a data dos dados,
So that eu saiba como estou antes de abrir qualquer tabela.

**Requisitos:** FR13, AR2, NFR5, NFR8, UX-DR12, UX-DR15, UX-DR17, UX-DR22, UX-DR27.

**Acceptance Criteria:**

**Given** a engine `overview` (camada 7)
**When** `GET /api/v1/overview/painel?periodo=YYYY-MM` é chamado
**Then** devolve `Valued` (value, `unavailable_reason`, `as_of` = a data mais antiga das fontes, `source`, `stale`) para Resultado do mês, Patrimônio, Resultado dos investimentos e Rentabilidade nominal (XIRR desde o início até o fim do período)
**And** os termos vêm das funções de `ledger/calc` e `portfolio/calc` (AD-7), nunca de SQL próprio
**And** a pasta vazia `engines/analytics/` é apagada (AD-1)

**Given** Visão geral › Painel
**When** abre
**Then** mostra os Cartões KPI na grade do DESIGN.md (Resultado do mês; Patrimônio | Resultado dos investimentos | Rentabilidade nominal), cada um com valor completo e Carimbo de data; os cartões dos épicos seguintes ainda não aparecem
**And** o clique leva ao detalhe (Patrimônio e Rentabilidade → Posições) e a variação só aparece se o período anterior existe

**Given** uma API externa de preço falhando
**When** o Painel abre
**Then** mostra o último valor com o Carimbo "preço de {dd/mm/aaaa}" e o ponto de aviso, sem erro e sem 5xx

**Given** um bloco que falha ao carregar
**When** a tela abre
**Then** só ele mostra "Não foi possível carregar {o quê}. Tentar de novo." e o resto funciona; durante a carga, cada bloco mostra o Esqueleto com a geometria final

**Given** a base real
**When** o Painel abre
**Then** carrega em menos de 3 s

### Story 4.2: Avisos, transações a revisar e Bloco Fontes no Painel

As a Vitor,
I want ver no Painel os avisos mais importantes e o estado de cada fonte,
So that eu saiba o que pede ação e de quando são os dados.

**Requisitos:** FR3, FR13, FR14, UX-DR13, UX-DR33.

**Acceptance Criteria:**

**Given** avisos ativos
**When** o Painel abre
**Then** a primeira faixa mostra até 3 Linhas de aviso (divergências primeiro) e "Ver todos ({n})", com {n} igual ao Sino

**Given** o Bloco Fontes no Painel
**When** abre
**Then** mostra as 5 fontes de arquivo e as automáticas (preços, carteiras, CDI/IPCA) com tipo, Carimbo de data e, na conta PF, o Selo "conferido" ou "divergente · R$ {valor}"
**And** fonte defasada mostra o ponto de aviso, e fonte de arquivo abre o Hub

**Given** transações `pending`
**When** o Painel abre
**Then** o número de transações a revisar aparece com a ação Revisar

### Story 4.3: Aviso de worker com falha ou atrasado

As a Vitor,
I want saber quando uma atualização automática falhou ou parou,
So that eu não confie em preço ou carteira velhos sem perceber.

**Requisitos:** FR14, AR2, AR11.

**Acceptance Criteria:**

**Given** a rota de jobs em `engines/jobs/router.py`
**When** a story toca o módulo
**Then** ela passa para `api/workers/` (AD-1), e a tela v1 de Atualização continua funcionando

**Given** `job_runs`
**When** um job falhou na última execução ou passou do seu intervalo esperado
**Then** o provider de `jobs` emite um aviso com o nome do job, a última execução bem-sucedida e a ação de ir para a atualização (inclui o `db_backup`: "backup falhou")
**And** o aviso some quando o job volta a rodar

## Epic 5: Fechamento de mês e recuperação da base

O Vitor fecha o mês com checklist, reabre vendo congelado × recalculado e recebe o aviso de ajuste em mês fechado.
Jul/2024–mai/2026 entram fechados em bloco, e o Assistente de recuperação conduz do mês seguinte ao bloco até o mês anterior.

### Story 5.1: Resumo do mês ao vivo

As a Vitor,
I want que todo número de um mês aberto saia de um cálculo único,
So that Painel, Caixa e fechamento nunca mostrem números diferentes para o mesmo mês.

**Requisitos:** FR32, AR2, AR8, AR9, AR15.

**Acceptance Criteria:**

**Given** a engine `closing`
**When** `build_month_summary(conn, month, as_of)` roda
**Then** calcula com as funções da AD-7 os termos já existentes (receitas por pagador, resgates, gastos por categoria, investimento, taxa de poupança, resultado do mês, patrimônio e valor por classe e ativo, saldo conferido da PF), com `as_of` = fim do mês ou hoje no mês corrente
**And** o Painel passa a ler o mês por `closing`

**Given** um mês passado
**When** o resumo usa preços
**Then** o preço vem de `market.asset_price_history` até `as_of`; B3 de meses passados vem do consolidado (`broker_position_snapshots`); RF, do CDI até `as_of`
**And** `asset_price_history` é dona de `market`, gravada pelos workers de preço a cada coleta; `upsert_price`/`clear_manual_price` passam para `market.service` e o `PriceCache` para `common.cache` (AD-1, com a precedência `is_manual` e a invalidação preservadas)

**Given** `common.dates`
**When** a story termina
**Then** existe `resolve_period(periodo, leitura) -> list[month]`, com testes, e "hoje" usa `today_brt()`

### Story 5.2: Fechar o mês — serviço e snapshot

As a Vitor,
I want que fechar um mês congele o resumo exatamente como o calculado,
So that o passado fique como eu o conferi.

**Requisitos:** FR32, AR9, AR20.

**Acceptance Criteria:**

**Given** a revisão que cria `month_closes` (mês, versão, status, `closed_at`, cobertura por fonte, método de valoração, confirmações "fechar mesmo assim", `origin` ∈ {live, retro}), `month_summary_totals` e `month_summary_lines`
**When** roda
**Then** `month_summary_totals` já tem **todas** as colunas dos termos da AD-7 (mais valor investido, aplicado, resultado e saldo conferido), aceitando nulo
**And** `month_summary_lines` guarda as quebras (`metric`, `dimension_kind`, `dimension_id` text com tipo fixo por `dimension_kind`, `flow_date`, `value`)
**And** a cobertura grava o método de valoração vigente (ex.: "RF: CDI fixo", "cripto: estimada")

**Given** `POST /api/v1/closing/months/{mes}/close`
**When** há transações `pending` ou saldo PF divergente
**Then** recusa com o motivo
**And** posição divergente, dinheiro a caminho ou mês sem saldo PF informado no fim do mês exigem a confirmação "fechar mesmo assim", que fica gravada

**Given** um fechamento aceito
**When** grava
**Then** salva a versão 1 com o resumo de `build_month_summary`; termos cuja engine ainda não existe ficam nulos com `unavailable_reason = fora_do_resumo`
**And** o golden test "snapshot = ao vivo no instante do fechamento" passa

### Story 5.3: Checklist de fechamento na tela

As a Vitor,
I want fechar o mês por um checklist que mostra o que está pendente,
So that eu decida fechar sabendo o que fica para trás.

**Requisitos:** FR32, UX-DR8, UX-DR21, UX-DR40.

**Acceptance Criteria:**

**Given** "Fechar {mês}" em Visão geral › Histórico
**When** o Vitor clica
**Then** o Checklist de fechamento (Diálogo de confirmação) mostra saldo conferido da conta PF, transações revisadas e os avisos do mês, com check neutro quando ok e ponto de aviso + link na pendência, antes do resumo a congelar

**Given** pendências que não bloqueiam
**When** o Vitor as vê
**Then** o botão diz "Fechar {mês} com {n} pendências"; pendências que bloqueiam deixam o botão desabilitado com o motivo

**Given** o Seletor de período e Visão geral › Histórico
**When** o mês está fechado
**Then** mostram o Selo de estado "fechado" (e "aberto" nos demais)

**Given** uma falha ao fechar
**When** a API recusa ou cai
**Then** o diálogo mostra "Não foi possível fechar {mês}. Nada foi perdido. Tentar de novo." com o foco em "Tentar de novo"
### Story 5.4: Ler mês fechado do snapshot, reabrir e fechar de novo

As a Vitor,
I want que mês fechado mostre sempre o que congelei, e poder reabrir quando quiser recalcular,
So that o passado não mude sozinho, mas eu possa corrigir quando decidir.

**Requisitos:** FR33, AR9, UX-DR40.

**Acceptance Criteria:**

**Given** um mês fechado
**When** qualquer tela lê esse mês
**Then** recebe a versão vigente do snapshot, nunca recalculada, só com os campos do snapshot
**And** campo `fora_do_resumo` aparece como "—" com o tooltip "este número não existia quando o mês foi fechado · reabra para incluir"

**Given** "Reabrir {mês}"
**When** o Vitor clica
**Then** o diálogo mostra congelado × recalculado só nas linhas de fluxo que mudam, com o mesmo arredondamento, vindo de uma rota de prévia

**Given** a confirmação de reabrir
**When** o mês volta a abrir e é fechado de novo
**Then** nasce a `version + 1`; as versões anteriores nunca são apagadas nem exibidas

**Given** `python -m scripts.ops.refechar --meses 2026-06..2026-09`
**When** roda
**Then** reabre e fecha cada mês pelo serviço (nunca por SQL), com o mesmo `origin`, e lista os meses que mudaram
**And** é o caminho para atualizar meses fechados quando um termo novo ou um método de valoração novo chega
### Story 5.5: Ajuste em mês fechado

As a Vitor,
I want ser avisado quando um dado novo cai num mês já fechado,
So that eu decida se reabro, sem o resumo mudar por baixo.

**Requisitos:** FR6, FR11, FR14, FR33, AR9.

**Acceptance Criteria:**

**Given** o `MonthStatusPort` real registrado por `closing` em `main.py`
**When** `ingest`, `categorize`, a reaplicação de regras ou o desfazer tocam um mês fechado
**Then** o dado é aceito, o mês fica `dirty` e o resumo congelado não muda
**And** o provider emite "Ajuste em {mês}, já fechado. O resumo congelado não mudou." com a ação Reabrir mês, e o Seletor de período mostra "ajuste"; o `dirty` zera ao fechar de novo

**Given** o teste de contrato
**When** roda
**Then** prova que os quatro caminhos de escrita (aplicar lote, desfazer lote, `categorize`, reaplicar regras) chamam `mark_dirty` para os meses que tocam

**Given** a prévia de reaplicar regras ou de desfazer lote
**When** atinge meses fechados
**Then** diz "{n} transações em meses fechados: o resumo congelado não muda" (ou que o desfazer vira ajuste)

**Given** um mês que terminou há mais de 10 dias e segue aberto
**When** os avisos são lidos
**Then** aparece "{Mês} segue aberto. Confira o saldo e feche." com a ação Ir para Histórico

### Story 5.6: Fechamento retroativo em bloco

As a Vitor,
I want que jul/2024–mai/2026 já entrem fechados,
So that eu compare o fluxo desde jul/2024 sem refazer 23 meses.

**Requisitos:** FR7, AR9, AR17.

**Acceptance Criteria:**

**Given** `python -m scripts.ops.close_retro --from 2024-07 --to 2026-05`
**When** roda
**Then** aborta se o Alembic estiver antes da revisão de reclassificação (`0020`)
**And** fecha cada mês por `build_month_summary` com `origin = retro`, nunca por SQL de migração

**Given** consolidados em `files/b3/relatorio-consolidado/` que ainda não foram importados
**When** o comando roda
**Then** lista os meses afetados e aborta, a menos que receba `--sem-consolidado`

**Given** o patrimônio retroativo
**When** o mês tem consolidado B3 (mensal em 2026; anual = dezembro em 2024 e 2025)
**Then** usa as posições do consolidado; cripto = aplicado do bloco, com cobertura "estimada"
**And** mês sem consolidado fica "patrimônio não coberto", gravado na cobertura por fonte

**Given** os meses retroativos
**When** fechados
**Then** aporte planejado e pendente ficam nulos `nao_definido`, e os termos ainda sem engine ficam `fora_do_resumo`

**Given** o comando rodado duas vezes
**When** os meses já estão fechados
**Then** não cria versões novas
### Story 5.7: Assistente de recuperação

As a Vitor,
I want um passo a passo para recuperar os meses que faltam, um mês por vez,
So that eu chegue até hoje com cada mês importado, revisado, conferido e fechado.

**Requisitos:** FR7, UX-DR41.

**Acceptance Criteria:**

**Given** a base sem fechamento até o mês anterior a hoje
**When** o Painel abre
**Then** o Assistente de recuperação aparece no topo com "A base vai até {dd/mm/aaaa}. Recupere mês a mês até hoje." e a trilha do mês seguinte ao bloco fechado (jun/2026) até o mês anterior a hoje, derivada dos dados

**Given** o mês atual da trilha
**When** o Vitor avança
**Then** os 4 passos são Importar (feito se os arquivos cobrem o mês), Revisar (Revisão filtrada pelo mês), Conferir (Selo "conferido"/"divergente" da conta PF) e Fechar (Checklist), com um único botão primário no passo atual
**And** o Seletor de período acompanha o mês, e o próximo abre quando o atual fecha

**Given** o Vitor pausa no meio
**When** volta outro dia
**Then** o progresso é o mesmo, porque vem dos dados

**Given** todos os meses da trilha fechados
**When** o Painel abre
**Then** o assistente some

## Epic 6: Orçamento do mês e custos fixos

O Vitor vê receitas por pagador, a Conta do orçamento (disponível, consumido, restante, consumo financiado por resgate),
informa as dívidas do mês e acompanha os custos fixos pagos × pendentes com casamento automático.

### Story 6.1: Custos fixos com vigência e casamento automático

As a Vitor,
I want cadastrar custos fixos e que o app os case com as transações do mês,
So that eu saiba o que já paguei sem marcar à mão.

**Requisitos:** FR18, FR35, AR10, AR15, UX-DR43.

**Acceptance Criteria:**

**Given** a revisão da story
**When** roda
**Then** `fixed_costs` ganha vigência (`valid_from`, `valid_to`) e `fixed_cost_payments` guarda só as decisões (confirmação, correção, manual)

**Given** `ledger/calc`
**When** o casamento do mês roda
**Then** aplica primeiro as decisões de `fixed_cost_payments` e depois o guloso global 1:1 (±10% do valor, −5/+5 dias do vencimento), ordenado por (|Δvalor|, |Δdata|, `fixed_cost_id`, `transaction_id`), cada lado casando uma vez, com testes de empate e de duas candidatas

**Given** Ajustes › Custos fixos
**When** o Vitor cria ou edita (nome, valor, vencimento, categoria)
**Then** usa o Formulário em painel lateral, valida "Vencimento entre 1 e 31." e a edição de valor único é inline (Enter grava, Esc reverte)
**And** sem itens, mostra "Nenhum custo fixo. Cadastre para acompanhar pago × pendente."

### Story 6.2: Caixa › Custos fixos com casamento

As a Vitor,
I want ver cada custo fixo do mês com a transação casada e poder confirmar, trocar ou marcar pago,
So that a lista de pagos × pendentes seja confiável.

**Requisitos:** FR18, AR10, UX-DR37.

**Acceptance Criteria:**

**Given** a aba Caixa › Custos fixos
**When** abre
**Then** a Lista de custos fixos com casamento mostra nome, valor, vencimento, Selo de estado (pago, pendente, vencendo, atrasado) e a transação casada, na ordem atrasado → pago, com cabeçalho pago × pendente

**Given** uma linha
**When** o Vitor usa Confirmar, Trocar (transações do mês, com busca), Marcar pago manualmente ou Desfazer casamento
**Then** a decisão é gravada em `fixed_cost_payments` e a lista recalcula (manual mostra o Selo "manual")

**Given** duas candidatas
**When** a linha aparece
**Then** mostra "pendente" + "2 candidatas" com as duas como opções (borda de aviso); nada fica pago até a escolha

**Given** um mês fechado
**When** o Vitor tenta mudar um casamento
**Then** a lista é só leitura até reabrir

**Given** nenhum custo fixo cadastrado
**When** a aba abre
**Then** mostra "Nenhum custo fixo cadastrado. Cadastre em Ajustes › Custos fixos." e a ação abre o formulário

### Story 6.3: Custos fixos vencendo e atrasados no Painel

As a Vitor,
I want ver no Painel o que vence e o que atrasou,
So that eu não esqueça um pagamento.

**Requisitos:** FR13, FR14, FR18, UX-DR35.

**Acceptance Criteria:**

**Given** um custo fixo sem pagamento casado
**When** faltam 3 dias ou menos para o vencimento
**Then** o provider emite "{Custo} vence em {dd/mm/aaaa}."; depois do vencimento, "{Custo} atrasado desde {dd/mm/aaaa}.", com a ação Ver custos fixos
**And** o provider provisório de vencimentos do Épico 3 é removido

**Given** o Painel
**When** abre
**Then** o Resumo de custos fixos mostra "pago R$ {x} de R$ {y}", só atrasados, vencendo e pendentes (nessa ordem) com data e Selo, os pagos recolhidos em "{n} pagos" e o rodapé "{n} a pagar · R$ {valor}"; o clique leva a Caixa › Custos fixos

### Story 6.4: Termos do orçamento

As a Vitor,
I want que disponível, consumido, restante e consumo financiado por resgate tenham um cálculo único e testado,
So that o orçamento bata com os números que conferi nos mockups.

**Requisitos:** FR17, AR8, AR20, AR24.

**Acceptance Criteria:**

**Given** a engine `planning` e a revisão de `month_plans` (mês, dívidas do mês, aporte planejado nulo, travas; dona `planning`)
**When** a story termina
**Then** `planning/calc` tem disponível para consumo (trabalho + resgates − custos fixos [pago: valor pago; pendente: valor cadastrado] − aporte planejado − dívidas do mês), restante e consumo financiado por resgate (mín(resgates, máx(0, consumido − disponível sem resgates)))
**And** `ledger/calc` tem consumido: gastos − deduções, cada transação num balde só (custo fixo casado > dívida > devolução)

**Given** os números dos mockups
**When** os golden tests rodam
**Then** consumido = R$ 6.912,37, disponível = R$ 8.405,59 e financiado = R$ 2.994,77, e os casos "zero" e "resgate cobre tudo" passam

**Given** a rota do orçamento do mês por `closing` e a escrita das dívidas do mês por `planning`
**When** chamadas
**Then** devolvem `Valued`/`Money` (AD-15); a escrita das dívidas é recusada em mês fechado

### Story 6.5: Caixa › Orçamento

As a Vitor,
I want ver o disponível para consumo, quanto já consumi e quanto resta,
So that eu saiba se o mês cabe no que ganho.

**Requisitos:** FR15, FR16, FR17, UX-DR36.

**Acceptance Criteria:**

**Given** Caixa › Orçamento
**When** abre
**Then** a Conta do orçamento (tabela com operador em coluna própria) mostra + Receita do trabalho (expande por pagador) · + Resgates · − Custos fixos · − Aporte planejado · − Dívidas do mês · = Disponível para consumo · − Consumido · = Restante, todos vindos da API
**And** abaixo vem "Consumo financiado por resgate" ("coberto por resgates, não pelo trabalho") e o restante sem os resgates
**And** ao lado, Consumido por grupo → subcategoria (% do consumido), com gastos brutos e a linha "− Devoluções" no rodapé

**Given** Dívidas do mês
**When** o Vitor digita e aperta Enter
**Then** grava, a conta recalcula pela API e anuncia "Disponível: R$ {valor}"; Esc reverte; vazio conta zero com "sem dívidas informadas"
**And** num mês fechado o campo é só leitura

**Given** aporte planejado não definido
**When** a conta aparece
**Then** "− Aporte planejado" mostra R$ 0,00 + "não definido · Definir em Aportes"

**Given** disponível ou restante negativo
**When** a conta aparece
**Then** o valor sai em vermelho com "−" e ▼ e a nota "O planejado passa da receita em R$ {valor}. Reduza o aporte ou as dívidas." (ou "Gasto acima do disponível em R$ {valor}.")

**Given** o Painel
**When** abre
**Then** o Cartão KPI Disponível para consumo aparece ao lado de Resultado do mês e leva a Caixa › Orçamento
### Story 6.6: Taxa de poupança e rodapé do orçamento

As a Vitor,
I want ver a taxa de poupança e o aporte sobre a receita do trabalho,
So that eu acompanhe o quanto guardo do que ganho.

**Requisitos:** FR20, UX-DR36.

**Acceptance Criteria:**

**Given** Caixa › Orçamento
**When** abre
**Then** o rodapé mostra custos fixos pagos, gastos do mês, investimento (fora dos gastos), taxa de poupança ((trabalho − (gastos − devoluções)) / trabalho) e investimento do mês ÷ receita do trabalho (o mesmo número que vira o "realizado total" no Épico 8), todos da API

**Given** um mês sem receita do trabalho
**When** a taxa é calculada
**Then** volta `Valued` nulo com `unavailable_reason = sem_receita`, nunca 0%

**Given** jun/2026
**When** a taxa é lida
**Then** é 55,48%

### Story 6.7: Completar os meses já fechados com o orçamento

As a Vitor,
I want poder incluir os números do orçamento nos meses fechados antes deste épico,
So that jun–set/2026 fiquem completos se eu quiser.

**Requisitos:** FR7, FR32, AR9.

**Acceptance Criteria:**

**Given** `planning.ensure_month_plan(month, mode='retro')`
**When** roda para um mês retroativo
**Then** as dívidas do mês = Σ das transações de role `divida` não casadas a custo fixo, e o aporte planejado fica nulo `nao_definido`

**Given** o comando `refechar` do Épico 5 (ou a ação Reabrir + Fechar na tela) com os meses escolhidos
**When** roda depois desta story
**Then** cada mês nasce `version + 1` com os termos do orçamento preenchidos, usando `ensure_month_plan(mode='retro')` nos meses retroativos; nunca por SQL
**And** meses que o Vitor não escolher continuam como estão, com `fora_do_resumo`

## Epic 7: Investimentos sem digitação — posições, rentabilidade e conciliação

Posições classe → ativo, rentabilidade XIRR nominal × real por período, caixinhas/CDB pelo CDI real, debêntures
cadastradas no app, caixa em corretora e a caminho, e a aba Conciliação com as tolerâncias da AD-13.

### Story 7.1: Investimentos › Posições em dois níveis

As a Vitor,
I want ver minhas posições por classe e por ativo, com aplicado, valor atual e resultado,
So that eu saiba onde está meu dinheiro sem abrir a corretora.

**Requisitos:** FR21, FR27, UX-DR9, UX-DR14.

**Acceptance Criteria:**

**Given** Investimentos › Posições
**When** abre
**Then** uma Tabela de dados mostra as classes recolhidas (Ações Nacionais, ETFs, FIIs, Renda Fixa, Aposentadoria, Cripto), expansíveis para ativos, com aplicado, valor atual e resultado vindos de `portfolio/calc` via `closing`
**And** a classe Cripto aparece como "Bloco cripto: quanto saiu × quanto vale", com os ativos só com valor atual e "—" no resto

**Given** o Seletor de leitura (Mês · Trimestre · Ano · Desde o início, na URL, só desta aba)
**When** o Vitor troca a leitura
**Then** muda o resultado do período; aplicado e valor atual seguem o fim do mês

**Given** um preço desatualizado ou ausente
**When** a linha aparece
**Then** mostra o último valor com "preço de {dd/mm/aaaa}" e o ponto de aviso, ou "—" + "sem preço"; ativo com preço manual mostra o Selo "manual"

### Story 7.2: Rentabilidade nominal × real por período

As a Vitor,
I want ver a rentabilidade por XIRR, nominal e real, em qualquer leitura,
So that eu saiba quanto a carteira rendeu acima da inflação.

**Requisitos:** FR22, AR2, AR9.

**Acceptance Criteria:**

**Given** `closing.build_period_summary`
**When** calcula a rentabilidade de um período
**Then** usa XIRR (`portfolio/xirr.py`) sobre o valor investido no início e no fim e os fluxos líquidos datados; o valor inicial vem do mês anterior (snapshot se fechado; senão `build_month_summary`), e sem nenhum volta `antes_do_primeiro_fechamento`

**Given** o IPCA de `benchmark_data`
**When** o real é calculado
**Then** desconta o IPCA efetivo do período; se o IPCA do último mês não saiu, o real é o Selo "aguardando IPCA" e a nominal aparece normalmente
**And** o SQL de `benchmark_workers.py` passa para `market.service` (AD-1)

**Given** Posições
**When** abre
**Then** mostra XIRR nominal × real por classe e consolidada, e o mensal por ativo em % a.m., exceto Renda Fixa e Cripto

**Given** o Painel
**When** abre
**Then** o Cartão KPI Rentabilidade real aparece ao lado da nominal, com o carimbo do IPCA

### Story 7.3: Renda fixa pelo CDI real

As a Vitor,
I want que caixinhas e CDBs sejam valorados pelo CDI que de fato saiu,
So that o valor atual da renda fixa não dependa de uma taxa fixa nem de seed manual.

**Requisitos:** FR23, AR7, AR12.

**Acceptance Criteria:**

**Given** uma caixinha ou CDB com %CDI cadastrado no ativo
**When** o valor atual é calculado
**Then** usa o %CDI aplicado ao CDI efetivo de `benchmark_data` até a data, e `settings.cdi_anual` deixa de ser usado

**Given** os hooks `on_batch_applied` e `on_transactions_changed`
**When** um import ou uma recategorização mexe em transações de caixinha/CDB
**Then** as operações derivadas são refeitas idempotentes por `transaction_id`, na mesma transação, e os seeds `seed_caixinhas`/`seed_cdb_guanabara` deixam de ser necessários
**And** a revisão da story cria `transactions.asset_id`, preenchido pelo resolver que `portfolio` registra em `ledger` ("Caixinha SnowTrip" → `caixinha:snowtrip`), com backfill do histórico

**Given** Posições
**When** mostra um ativo de RF
**Then** traz "{x}% do CDI · CDI até dd/mm/aaaa"; o Tesouro segue o preço de mercado automático

**Given** meses fechados antes desta story
**When** são lidos
**Then** mantêm a valoração antiga ("RF: CDI fixo" na cobertura) até o Vitor rodar o `refechar` neles

### Story 7.4: Debêntures cadastradas no app

As a Vitor,
I want cadastrar minhas debêntures e que os aportes nelas sejam sugeridos na revisão,
So that eu largue o JSON mantido à mão.

**Requisitos:** FR24, FR35, AR12, UX-DR43.

**Acceptance Criteria:**

**Given** a revisão da story
**When** roda
**Then** existe `debentures` (dona `portfolio`, ligada a `assets`: emissor, taxa, início, vencimento) e as integralizações de `files/debentures-flash/integralizacoes.json` são migradas com os mesmos valores

**Given** Ajustes › Debêntures
**When** o Vitor cadastra ou edita
**Then** usa o Formulário em painel lateral; sem itens, "Nenhuma debênture. Cadastre para valorar pela taxa."

**Given** uma saída do Nubank com categoria de investimento em debênture
**When** aparece na Revisão de transações
**Then** traz o campo "Debênture" sugerido; o aporte derivado tem status `suggested`, `confirmed` ou `dismissed`, e entradas do mesmo pagador (ex.: receita da Flash) nunca viram aporte

**Given** uma debênture
**When** é valorada
**Then** segue a fórmula de `files/debentures-flash/formula.md` pela taxa cadastrada, mostra "valorada pela taxa cadastrada" em Posições e não concilia ("valor calculado")
**And** cupons e o resgate no vencimento entram como resgates no Nubank
**And** meses fechados antes desta story mantêm a valoração do JSON até serem fechados de novo pelo `refechar`

### Story 7.5: Caixa em corretora e dinheiro a caminho

As a Vitor,
I want saber quanto dinheiro está parado na corretora e quanto ainda está a caminho,
So that o patrimônio e o aporte não fiquem errados entre a transferência e o relatório.

**Requisitos:** FR4, FR14, FR25, AR14, UX-DR39.

**Acceptance Criteria:**

**Given** `portfolio/calc`
**When** calcula por corretora o resíduo (saídas do Nubank + proventos − aplicado)
**Then** se o atualizado até da corretora cobre a data da transferência, o resíduo é caixa em corretora e entra no patrimônio (valor investido); se não cobre, fica a caminho, fora do patrimônio
**And** a cobertura dos fechamentos novos registra o método; meses fechados antes ficam sem caixa em corretora até o `refechar`

**Given** dinheiro a caminho
**When** os avisos são lidos
**Then** aparece "R$ {valor} a caminho da {corretora}. Importe o relatório B3 a partir de {dd/mm/aaaa}." com a ação Importar

**Given** Investimentos › Conciliação
**When** abre
**Then** um Cartão de corretora por corretora mostra saiu, proventos, aplicado, caixa em corretora, a caminho (Selo + data a importar) e o Carimbo de data

**Given** o input "Saldo que vejo na corretora" (valor + data)
**When** o Vitor informa
**Then** fica gravado em `broker_cash_checks` e o cartão mostra calculado × informado; diferença acima de R$ 1,00 mostra o Selo "divergente" e o aviso "Caixa na {corretora}: calculado R$ {a}, informado R$ {b}."

### Story 7.6: Conciliação com o consolidado B3 e com as carteiras

As a Vitor,
I want comparar minhas posições com o consolidado B3 e com o scan das carteiras,
So that eu saiba que o app bate com a origem.

**Requisitos:** FR14, FR26, AR2, AR14.

**Acceptance Criteria:**

**Given** as tolerâncias da AD-13 como constantes de `portfolio/calc`
**When** a conciliação compara por quantidade
**Then** ações, FII, ETF e BDR exigem quantidade exata; Tesouro tolera 0,01 título; cripto não tolera divergência; caixinhas e debêntures não conciliam ("valor calculado")
**And** a conciliação wallet × `net_quantity` passa para `portfolio` (AD-1)

**Given** Investimentos › Conciliação
**When** abre
**Then** abaixo dos cartões, mostra posições × consolidado B3 e × scan das carteiras (app, origem, diferença, Selo de estado, Carimbo de data)
**And** divergência gera "{Ativo}: {q} no app, {q'} no consolidado B3." (severidade divergência), e scan com mais de 14 h gera aviso de idade

**Given** tudo dentro da tolerância
**When** a aba abre
**Then** mostra "Tudo bate com o consolidado B3 de {dd/mm/aaaa} e com as carteiras de {dd/mm/aaaa}." e "conferido" em cada cartão

**Given** nenhum consolidado importado
**When** a aba abre
**Then** a tabela B3 mostra "Sem consolidado B3. Importe o consolidado (.xlsx) para conciliar." com a ação Importar, e cartões e carteiras seguem visíveis

## Epic 8: Aporte do mês, objetivos e distribuição

Objetivos vinculados às caixinhas (fora da alocação), metas com bandas e pisos, aporte planejado, Distribuição do aporte
com travas e realizado / a caminho / pendente; Resumo do aporte no Painel.

### Story 8.1: Objetivos vinculados às caixinhas

As a Vitor,
I want cadastrar objetivos e ligá-los às caixinhas que já uso,
So that eu acompanhe o progresso de cada meta pelo saldo real.

**Requisitos:** FR17, FR35, AR12, UX-DR43.

**Acceptance Criteria:**

**Given** a revisão da story
**When** roda
**Then** existem `goals` (nome, valor-alvo, prazo) e `goal_assets` (donas de `planning`), e a reserva de emergência é um objetivo fixo com alvo = multiplicador × custos fixos (padrão 6) e horizonte editável (padrão 12 meses)

**Given** uma caixinha nomeada no OFX ("Caixinha SnowTrip")
**When** ainda não está ligada a um objetivo
**Then** o app sugere o vínculo, e ele só vale depois de confirmado (decisão gravada em `goal_assets`)

**Given** Ajustes › Objetivos
**When** o Vitor cria ou edita
**Then** escolhe nome, valor-alvo, prazo e os ativos vinculados; edita o multiplicador e o horizonte no item Reserva de emergência
**And** sem objetivos, "Nenhum objetivo além da reserva de emergência."

**Given** um objetivo
**When** o progresso é calculado
**Then** progresso = valor atual dos ativos vinculados (CDI real), com o "aportado" (aportes líquidos a eles) ao lado

**Given** a Conta do orçamento
**When** há resgate de ativo vinculado a objetivo
**Then** o consumo financiado por resgate se divide em "financiado por objetivo" (tom neutro) e "financiado por resgate da carteira" (laranja)

### Story 8.2: Metas de alocação, bandas e pisos

As a Vitor,
I want definir metas por classe e por ativo, com banda e piso,
So that a distribuição do aporte tenha uma base que eu controlo.

**Requisitos:** FR35, AR12, AR15, UX-DR43.

**Acceptance Criteria:**

**Given** a revisão da story
**When** roda
**Then** `portfolio_targets` passa a ser dona de `planning`, com `class`, `asset_id` nulo (= meta da classe), %, banda (p.p.), piso (R$) e vigência, migrando os valores de `portfolio/targets.py` / `seed_portfolio_targets`

**Given** Ajustes › Metas
**When** o Vitor edita classe → ativo
**Then** cada nível precisa somar 100%; senão aparece "Soma em {x}%. Ajuste para 100%." e Salvar fica desabilitado
**And** sem metas, "Nenhuma meta. Sem metas, a distribuição do aporte não tem base." com a ação Definir metas

### Story 8.3: Alocação × meta e bloco Objetivos em Posições

As a Vitor,
I want ver a alocação atual contra a meta e a banda, sem o dinheiro dos objetivos,
So that a viagem não pareça renda fixa sobrando.

**Requisitos:** FR14, FR21, AR12.

**Acceptance Criteria:**

**Given** `planning`
**When** calcula a alocação
**Then** a base exclui os ativos em `goal_assets`; o bloco cripto entra pelo valor atual por ativo

**Given** Investimentos › Posições
**When** abre
**Then** as linhas de classe e ativo mostram alocação atual, meta, banda e desvio em p.p. (coluna própria, sem seta), e os ativos de objetivos aparecem num bloco "Objetivos" separado das classes, ainda no patrimônio

**Given** uma classe fora da banda
**When** os avisos são lidos
**Then** aparece "{Classe} em {x,xx}%, meta {y,yy}% ± {b} p.p." com a ação Ver aportes, e o desvio sai em laranja

### Story 8.4: Aporte planejado do mês

As a Vitor,
I want informar quanto vou aportar no mês e ver o efeito no disponível,
So that eu decida o aporte já sabendo quanto sobra para consumo.

**Requisitos:** FR28, AR16.

**Acceptance Criteria:**

**Given** Investimentos › Aportes
**When** o Vitor digita o aporte planejado e aperta Enter
**Then** grava em `month_plans` do período, e a linha "Disponível para consumo depois do aporte" recalcula ali mesmo pela API
**And** a Conta do orçamento passa a usar o valor e deixa de mostrar "não definido"

**Given** o aporte planejado não definido
**When** a aba ou o Painel abre
**Then** aparece "Defina o aporte planejado de {mês} para ver a distribuição.", e o clique leva ao campo com foco

**Given** um mês fechado
**When** o Vitor tenta mudar o planejado
**Then** o campo é só leitura até reabrir

### Story 8.5: Distribuição do aporte

As a Vitor,
I want que o app sugira quanto vai para cada objetivo, classe e ativo,
So that eu aporte onde a carteira mais precisa, sem planilha.

**Requisitos:** FR29, AR5, AR13, UX-DR38.

**Acceptance Criteria:**

**Given** `planning/distribution.py: distribute(planned, goals, targets, positions, locks)` pura
**When** roda
**Then** segue a ordem fixa: reserva de emergência (falta ÷ meses restantes, até encher) → demais objetivos (falta ÷ meses até o prazo; proporcional às necessidades se faltar) → classes (déficit monotônico, piso, acima da banda só o piso, pisos reduzidos em proporção se não couberem) → ativos (déficit; cripto pelo valor atual)
**And** nunca sugere venda e a soma fecha ao centavo pelo maior resto (golden tests, incluindo o caso de pisos acima do disponível)

**Given** Investimentos › Aportes com planejado e metas
**When** abre
**Then** a Distribuição do aporte mostra os objetivos (Barra de progresso até o alvo, "Snow Trip · R$ 350/mês para chegar em jul/2027") e as classes recolhidas, expansíveis para ativos, com meta, atual, desvio (p.p.), banda e sugerido vindos de `POST /api/v1/planning/distribution/preview`
**And** quando os pisos são reduzidos, aparece a nota

**Given** nenhuma meta
**When** a aba abre
**Then** no lugar da distribuição aparece "Sem metas, a distribuição do aporte não tem base. Defina as metas em Ajustes › Metas.", e andamento e objetivos seguem visíveis

### Story 8.6: Ajustar a distribuição com travas

As a Vitor,
I want mudar qualquer valor sugerido e ver o resto se redistribuir,
So that eu siga meu julgamento sem desmontar a conta.

**Requisitos:** FR30, AR13, UX-DR38.

**Acceptance Criteria:**

**Given** uma célula de sugerido
**When** o Vitor edita e aperta Enter
**Then** o valor trava (cadeado no slot de anotação), a trava é gravada em `month_plans` e o resto redistribui pela mesma regra via prévia da API, com o total = planejado fixo
**And** a tela anuncia "Redistribuído: {n} linhas" (`aria-live`)

**Given** um cadeado
**When** o Vitor clica nele
**Then** a trava sai e o valor volta a ser sugerido

**Given** travas que somam mais que o planejado
**When** a prévia roda
**Then** aparece "Travas somam R$ {x}, acima do planejado."

### Story 8.7: Realizado, a caminho e pendente na distribuição

As a Vitor,
I want acompanhar o que já aportei, o que está a caminho e o que falta,
So that eu feche o mês com o plano cumprido.

**Requisitos:** FR31, AR20, UX-DR18, UX-DR38.

**Acceptance Criteria:**

**Given** `planning/calc`
**When** calcula o andamento
**Then** realizado total = investimento do mês (`ledger/calc`, o mesmo número da Story 6.6), incluindo o a caminho; realizado por linha = só o que virou ativo; pendente = planejado − realizado total; no mês seguinte o pendente zera
**And** o golden test dos mockups passa (Σ pendente das linhas R$ 2.200,00 = pendente total R$ 1.700,00 + a caminho R$ 500,00)

**Given** a Distribuição do aporte
**When** aparece
**Then** cada linha mostra realizado e pendente, e o rodapé de conciliação mostra objetivos + classes · + a caminho, ainda sem classe · = total do mês

**Given** a Barra de progresso
**When** aparece (Aportes e objetivos)
**Then** tem três trechos (realizado em ativo sólido, a caminho hachurado, pendente vazio), trilho com contorno `input`, legenda com os mesmos rótulos e os números escritos ao lado

### Story 8.8: Resumo do aporte no Painel e aviso de pendente

As a Vitor,
I want ver o aporte do mês no Painel e ser lembrado no fim do mês,
So that eu não esqueça de completar o aporte.

**Requisitos:** FR13, FR14, FR31, UX-DR34.

**Acceptance Criteria:**

**Given** o Painel
**When** abre
**Then** o Resumo do aporte mostra planejado, "Realizado R$ {total} · dos quais R$ {a caminho} a caminho", a Barra de progresso, a linha a caminho com corretora e "importe o relatório B3 a partir de dd/mm/aaaa", "{n} classes fora da banda" → Ver aportes e "% realizado" com Carimbo; o clique no cabeçalho leva a Aportes

**Given** os últimos 7 dias do mês com pendente
**When** os avisos são lidos
**Then** aparece "Faltam R$ {valor} do aporte de {mês}." com a ação Ver aportes
## Epic 9: Histórico e comparação de períodos

O Vitor compara mês, trimestre, ano e desde o início com o anterior e a média 12m e lê os três gráficos com "Ver como tabela".

### Story 9.1: Histórico do fluxo — período × anterior × média 12m

As a Vitor,
I want comparar receitas, gastos, poupança e aporte de um período com o anterior e com a média,
So that eu saiba se gastei mais ou menos, e em quê.

**Requisitos:** FR34, UX-DR9, UX-DR15.

**Acceptance Criteria:**

**Given** `closing.build_period_summary`
**When** soma um período (mes, tri, ano, inicio)
**Then** soma os meses (fechados do snapshot, aberto ao vivo), devolve `source` ∈ {snapshot, live} por mês, `as_of` = o mais antigo e `stale` = OU dos meses, recalcula razões dos componentes somados (nunca média de razões) e nunca inclui mês posterior

**Given** Visão geral › Histórico com o Seletor de leitura
**When** abre
**Then** mostra período × anterior × média 12m em receitas e gastos por categoria, taxa de poupança e aporte planejado × realizado, com o Selo de variação (seta + sinal + valor; zero = "0,00%" neutro)
**And** "Desde o início" mostra o acumulado, sem comparação

**Given** o card de Fechamento de mês (Épico 5)
**When** o Histórico abre
**Then** continua no lugar, com o Selo do mês

### Story 9.2: Crescimento do patrimônio e melhor desempenho

As a Vitor,
I want ver quanto o patrimônio cresceu e quanto disso foi aporte e quanto foi resultado,
So that eu entenda de onde veio o crescimento.

**Requisitos:** FR22, FR34.

**Acceptance Criteria:**

**Given** um período com início coberto
**When** o Histórico abre
**Then** mostra crescimento do patrimônio = aporte + resultado e a rentabilidade por classe e por ativo, com o ativo de melhor desempenho em destaque

**Given** um período antes do primeiro mês fechado ou sem patrimônio coberto
**When** o Histórico abre
**Then** patrimônio e rentabilidade mostram "Disponível a partir do primeiro mês fechado na v2." (ou "patrimônio não coberto"), e a opção de leitura não some

### Story 9.3: Os três gráficos com "Ver como tabela"

As a Vitor,
I want ver a evolução em gráficos simples, com a tabela ao lado quando eu quiser,
So that eu perceba tendências sem perder os números exatos.

**Requisitos:** FR34, AR25, UX-DR42.

**Acceptance Criteria:**

**Given** o Gráfico de patrimônio
**When** aparece
**Then** é uma linha mensal de 2px em `chart-1` com a série "aplicado" tracejada em `chart-3`, grade só horizontal, sem área preenchida, a partir do primeiro mês fechado
**And** meses "patrimônio não coberto" aparecem como lacuna, sem interpolação

**Given** o Gráfico de gastos por categoria
**When** aparece
**Then** barras horizontais por grupo: período preenchido em `chart-2`, anterior só com contorno `chart-3`, média 12m como marcador vertical, rótulo direto; clicar numa barra abre as transações do grupo

**Given** o Gráfico de aporte planejado × realizado
**When** aparece
**Then** barras agrupadas por mês (planejado `chart-2`, realizado `chart-1`); sem planejado, só realizado

**Given** qualquer dos três
**When** o Vitor usa "Ver como tabela"
**Then** os mesmos dados aparecem numa Tabela de dados
**And** os eixos usam moeda completa, sem animação, e as séries se distinguem também por estilo e legenda

## Epic 10: Ajustes completos e fim das telas antigas

As abas que faltam (Contas, Preços manuais), a revisão final das 8 abas e a remoção das rotas da v1.

### Story 10.1: Ajustes › Contas

As a Vitor,
I want cadastrar e editar minhas contas no app,
So that uma conta nova não precise de código.

**Requisitos:** FR35, UX-DR43.

**Acceptance Criteria:**

**Given** Ajustes › Contas
**When** abre
**Then** lista conta, tipo (PF/MEI) e fonte, com criar e editar pelo Formulário em painel lateral
**And** sem contas, "Nenhuma conta. Cadastre a conta Nubank PF." com a ação Nova conta

**Given** uma conta MEI
**When** é cadastrada
**Then** fica marcada como sem conferência de saldo

### Story 10.2: Ajustes › Preços manuais

As a Vitor,
I want informar preço só para ativo sem fonte de mercado,
So that a Neobankless entre no patrimônio sem eu digitar preço de ativo que já tem cotação.

**Requisitos:** FR27, FR35, UX-DR43.

**Acceptance Criteria:**

**Given** Ajustes › Preços manuais
**When** abre
**Then** lista só ativos sem fonte de mercado, com valor + data editáveis inline (Enter grava, Esc reverte), gravados por `market.service` com `is_manual = true` (nunca expira, worker não sobrescreve)
**And** sem itens, "Nenhum ativo sem fonte de mercado."

**Given** um ativo com fonte de mercado
**When** alguém tenta gravar preço manual para ele (tela ou API)
**Then** é recusado com "{Ativo} tem preço de mercado automático." (erro `{"error","message"}`)

### Story 10.3: Revisão final das 8 abas e checagem de teclado

As a Vitor,
I want Ajustes completo e as jornadas inteiras usáveis só pelo teclado,
So that eu ajuste tudo sem código e faça o ritual sem depender do mouse.

**Requisitos:** FR35, FR36, NFR10, UX-DR25, UX-DR43.

**Acceptance Criteria:**

**Given** as 8 abas de Ajustes (Categorias, Regras, Custos fixos, Contas, Objetivos, Debêntures, Metas, Preços manuais)
**When** são revisadas
**Then** todas seguem as regras e os estados vazios do EXPERIENCE, o mesmo Formulário em painel lateral e a mesma edição inline

**Given** as jornadas UJ-1 a UJ-5
**When** são percorridas só com o teclado
**Then** terminam sem mouse, com foco visível em todo passo, foco preso nos painéis e devolvido ao gatilho ao fechar
**And** a Shift+clique continua sendo o único atalho só de mouse, com Espaço como alternativa por linha

**Given** qualquer informação do app
**When** o Vitor parte do Painel
**Then** chega a ela em no máximo dois cliques
### Story 10.4: Métricas de sucesso num comando

As a Vitor,
I want medir as métricas de sucesso da v2 sem escrever SQL,
So that eu saiba se a v2 está cumprindo o que prometeu.

**Requisitos:** NFR12.

**Acceptance Criteria:**

**Given** `python -m scripts.ops.metricas --de 2026-11 --ate 2026-12`
**When** roda
**Then** imprime SM-2 (meses fechados com saldo PF conferido), SM-3 (meses com patrimônio por classe dentro da tolerância), SM-4 (preços/saldos digitados no período, fora dos ativos sem fonte), SM-5 (% de transações novas por regra, por semana), SM-6 (correções por semana), SM-C1 (% de automáticas corrigidas depois de confirmadas) e SM-C2 (avisos dispensados sem ação)
**And** lê só `categorization_events`, `alert_dismissals`, `month_closes` e as tabelas de fato, sem gravar nada
**And** a SM-1 (30 dias sem a planilha) fica fora, porque é contada pelo Vitor

### Story 10.5: Fim das telas da v1

As a Vitor,
I want que só reste o app novo,
So that não existam dois caminhos para a mesma informação.

**Requisitos:** FR36, AR18, UX-DR3.

**Acceptance Criteria:**

**Given** as rotas v1 (`/dashboard`, `/ledger*`, `/portfolio*`, `/market`, `/wallets*`, `/refresh`, `/analise-ledger`)
**When** a story termina
**Then** foram apagadas (ou redirecionam para a aba equivalente da v2), junto com a fachada `ui.tsx` e o `AppShell` antigo

**Given** o teste "no raw color"
**When** roda
**Then** a lista de exceção está vazia

**Given** endpoints legados sem uso no web nem no Hermes
**When** a story termina
**Then** foram removidos ou migrados para `/api/v1/<engine>/<recurso>` com `response_model`, e a coluna de texto de categoria (`transactions.category`, `fixed_costs.category`) sai numa revisão Alembic
