# Goodies — Progress Tracker (v2.0)

> Backlog: `docs/v2/planning/epics.md` (78 stories, final). Prontidão: `docs/v2/planning/implementation-readiness.md` (PASS).
> Revisão adversarial: `docs/v2/planning/adversarial-review.md`. O tracker da v1 (m0–m7) está em `docs/v1/PROGRESS-v1.md`.
> Iniciar sessão: `/status` → `/story N.M`. Encerrar: `/test` → `/code-review` → `/done N.M "descrição"`.

**Status:** `[ ]` pendente · `[~]` em andamento · `[x]` concluída e commitada · `[!]` bloqueada

**Regras de todo o backlog:** desenvolver contra `goodies_dev`; o banco real só migra por `scripts.ops.migrar`; commits locais (push é manual).

**Datas-alvo:** em aberto — preencher depois de medir o ritmo real nas primeiras stories.

| Marco | Épicos | Stories | Data-alvo |
|---|---|---|---|
| Marco 1 — Ritual confiável | 1, 2, 3, 4, 5 | 44 | — |
| Marco 2 — Caixa e orçamento | 6 | 8 | — |
| Marco 3 — Investimentos e aportes | 7, 8 | 17 | — |
| Marco 4 — Histórico e ajustes completos | 9, 10 | 9 | — |

---

## Marco 1 — Ritual confiável

### Épico 1 — App novo de pé — 4 áreas, tema e operação local

| # | Story | Status | Commit |
|---|---|---|---|
| 1.1 | Arrumação dos docs vivos para a v2 | [x] | b20b4e8 |
| 1.2 | Backup diário do banco local | [x] | 0d3b3fd |
| 1.3 | Versões da stack atualizadas | [x] | 0d3b3fd, e0eecb9 |
| 1.4 | Fundação visual — shadcn, tokens e tema | [x] | e0eecb9 |
| 1.5 | Guarda-corpos do visual — teste "no raw color" e theme-showcase | [x] | e0eecb9 |
| 1.6 | Endurecimento local — portas, segredos e Hermes | [x] | 0d3b3fd |
| 1.7 | Navegação em 4 áreas | [x] | 1897688 |
| 1.8 | Período na URL e formatação financeira | [x] | 1897688 |
| 1.9 | Login no visual novo e sessão que volta ao lugar | [x] | 1897688 |

### Épico 2 — Categorias em dois níveis, regras e histórico corrigido

| # | Story | Status | Commit |
|---|---|---|---|
| 2.1 | Base comum do backend | [x] | 44f22e1 |
| 2.2 | Proveniência do histórico em lotes legado | [x] | f9b781c |
| 2.3 | Categorias em dois níveis com o histórico migrado | [x] | 5d9d826 |
| 2.4 | Regras e origem da categoria no histórico | [x] | d1d9b47 |
| 2.5 | Categorização por um caminho só | [x] | bb1e9c6, 029b216 |
| 2.6 | Resgates como receita e reclassificações do histórico | [x] | 28eb2f1 |
| 2.7 | Caixa › Transações com origem e correção de categoria | [x] | b84a097 |
| 2.8 | Lançar transação manual | [x] | 767da8b |
| 2.9 | Ajustes › Categorias | [x] | 1446742, 029b216 |
| 2.10 | Ajustes › Regras e reaplicar regras ao histórico | [x] | 2f85ca8, 029b216 |

### Épico 3 — Hub de import, revisão em lote e central de avisos

| # | Story | Status | Commit |
|---|---|---|---|
| 3.1 | Central de avisos e Sino | [x] | — |
| 3.2 | Ativos com chave única | [x] | — |
| 3.3 | Import com prévia e lote — protocolo e OFX do Nubank | [x] | — |
| 3.4 | OFX completo — titular, pagador e saldo informado | [x] | — |
| 3.5 | Operações de caixinha ligadas à transação | [x] | — |
| 3.6 | Sugestão de categoria para toda transação nova | [x] | — |
| 3.7 | CSV do Nubank | [x] | — |
| 3.8 | Adapters da B3 — movimentação, negociação e consolidado | [x] | — |
| 3.9 | Hub de import | [x] | — |
| 3.10 | Revisão de transações | [x] | — |
| 3.11 | Proposta de regra a partir da correção | [x] | — |
| 3.12 | Saldo ancorado e conferência encadeada | [ ] | — |
| 3.13 | Conferência na tela e aviso de saldo divergente | [ ] | — |
| 3.14 | Desfazer o último lote e Histórico de imports | [ ] | — |

### Épico 4 — Painel principal

| # | Story | Status | Commit |
|---|---|---|---|
| 4.1 | Painel principal com KPIs datados | [ ] | — |
| 4.2 | Avisos, transações a revisar e Bloco Fontes no Painel | [ ] | — |
| 4.3 | Aviso de worker com falha ou atrasado | [ ] | — |

### Épico 5 — Fechamento de mês e recuperação da base

| # | Story | Status | Commit |
|---|---|---|---|
| 5.1 | Histórico de preço e preço num lugar só | [ ] | — |
| 5.2 | Resumo do mês ao vivo | [ ] | — |
| 5.3 | Fechar o mês — serviço e snapshot | [ ] | — |
| 5.4 | Checklist de fechamento na tela | [ ] | — |
| 5.5 | Ler mês fechado do snapshot, reabrir e fechar de novo | [ ] | — |
| 5.6 | Ajuste em mês fechado | [ ] | — |
| 5.7 | Fechamento retroativo em bloco | [ ] | — |
| 5.8 | Assistente de recuperação | [ ] | — |

**Ponto de uso:** fim do Épico 3 — o ritual semanal (importar, revisar, saldo PF conferido) passa a rodar na v2.

**Gate marco 1 (`/gate m1`):**
- `GET /api/v1/health` → 200 com postgres e redis; `scripts.ops.migrar` em `head`.
- Testes `dados_reais` verdes e **nenhum pulado**: poupança de cada mês = baseline (jun/2026 = 57,46%, ADR-016), contagens, zero órfãs, deltas esperados, invariantes de caixinhas/debêntures/XIRR contra o baseline da Story 1.3.
- UJ-1 de ponta a ponta (importar → revisar → saldo PF conferido) e UJ-5 (jun/2026 → mês anterior fechados pelo Assistente).
- Jul/2024–mai/2026 fechados em bloco (`close_retro`).

---

## Marco 2 — Caixa e orçamento

### Épico 6 — Orçamento do mês e custos fixos

| # | Story | Status | Commit |
|---|---|---|---|
| 6.1 | Custos fixos com vigência e casamento automático | [ ] | — |
| 6.2 | Caixa › Custos fixos com casamento | [ ] | — |
| 6.3 | Custos fixos vencendo e atrasados no Painel | [ ] | — |
| 6.4 | Aviso de gasto acima da média | [ ] | — |
| 6.5 | Termos do orçamento | [ ] | — |
| 6.6 | Caixa › Orçamento | [ ] | — |
| 6.7 | Taxa de poupança e rodapé do orçamento | [ ] | — |
| 6.8 | Completar os meses já fechados com o orçamento | [ ] | — |

**Gate marco 2 (`/gate m2`):**
- Golden tests do orçamento verdes a partir de `tests/fixtures/mockup_out2026.json` (consumido R$ 6.912,37; disponível R$ 8.405,59; financiado R$ 2.994,77).
- Poupança por mês = baseline (ADR-016) e deltas dos meses com Repasse conferidos.
- **SM-1 parcial começa:** `metricas --sm1-inicio <data>` registrado (tarefas de caixa sem a planilha).

---

## Marco 3 — Investimentos e aportes

### Épico 7 — Investimentos sem digitação — posições, rentabilidade e conciliação

| # | Story | Status | Commit |
|---|---|---|---|
| 7.1 | Investimentos › Posições em dois níveis | [ ] | — |
| 7.2 | Histórico de CDI e IPCA | [ ] | — |
| 7.3 | Rentabilidade nominal × real por período | [ ] | — |
| 7.4 | Renda fixa pelo CDI real | [ ] | — |
| 7.5 | Caixinhas e CDBs derivados das transações | [ ] | — |
| 7.6 | Debêntures cadastradas no app | [ ] | — |
| 7.7 | Caixa em corretora e dinheiro a caminho | [ ] | — |
| 7.8 | Ajustes › Posições manuais e vencimento DeFi | [ ] | — |
| 7.9 | Conciliação com o consolidado B3 e com as carteiras | [ ] | — |

### Épico 8 — Aporte do mês, objetivos e distribuição

| # | Story | Status | Commit |
|---|---|---|---|
| 8.1 | Objetivos vinculados às caixinhas | [ ] | — |
| 8.2 | Metas de alocação, bandas e pisos | [ ] | — |
| 8.3 | Alocação × meta e bloco Objetivos em Posições | [ ] | — |
| 8.4 | Aporte planejado do mês | [ ] | — |
| 8.5 | Distribuição do aporte | [ ] | — |
| 8.6 | Ajustar a distribuição com travas | [ ] | — |
| 8.7 | Realizado, a caminho e pendente na distribuição | [ ] | — |
| 8.8 | Resumo do aporte no Painel e aviso de pendente | [ ] | — |

**Gate marco 3 (`/gate m3`):**
- XIRR consolidado igual ao baseline da Story 1.3, salvo correção explicada; conciliação B3 e carteiras dentro das tolerâncias da AD-13.
- Distribuição do aporte fecha ao centavo (golden 2.200 = 1.700 + 500).
- **SM-1 começa:** `metricas --sm1-inicio <data>`; recomendado `refechar --completar` geral.

---

## Marco 4 — Histórico e ajustes completos

### Épico 9 — Histórico e comparação de períodos

| # | Story | Status | Commit |
|---|---|---|---|
| 9.1 | Histórico do fluxo — período × anterior × média 12m | [ ] | — |
| 9.2 | Crescimento do patrimônio e melhor desempenho | [ ] | — |
| 9.3 | Os três gráficos com "Ver como tabela" | [ ] | — |

### Épico 10 — Ajustes completos e fim das telas antigas

| # | Story | Status | Commit |
|---|---|---|---|
| 10.1 | Ajustes › Contas | [ ] | — |
| 10.2 | Ajustes › Preços manuais | [ ] | — |
| 10.3 | Ajustes › Atualização | [ ] | — |
| 10.4 | Revisão final das abas de Ajustes e checagem de teclado | [ ] | — |
| 10.5 | Métricas de sucesso num comando | [ ] | — |
| 10.6 | Fim das telas da v1 | [ ] | — |

**Gate marco 4 (`/gate m4`):**
- `metricas` mostra SM-1 ≥ 30 dias seguidos sem abrir a planilha; SM-2, SM-3 e SM-5 dentro da meta.
- Nenhuma rota v1 sem substituto; teste "no raw color" sem exceções.

---

## Registro de sessões

| Data | Marco | Stories | Notas |
|---|---|---|---|
| 2026-10-18 | — | planejamento | Backlog v2 final (78 stories), prontidão PASS, revisão adversarial aplicada; tracker v1 arquivado em `docs/v1/PROGRESS-v1.md`. |
| 2026-10-18 | m1 | 1.1–1.2 | Docs vivos na v2 (CLAUDE.md, conventions, .env.example sem Upstash + BACKUP_DIR, ADR-011 substituído, ADR-014/015 em docs/07). Backup pré-v2 em BACKUP_DIR/pre-migracao. 1.2: db_backup diário + restore_check mensal, guarda no Alembic, migrar/startup (AUTO_MIGRATE=false, sem --reload), goodies_dev/goodies_dados, runbook. 1.3: baseline (EVALUATION_DATE 2026-10-18, preços congelados) fixado + teste dados_reais; web Next 16.3.8/React 19.2.9/TS 5.9.3/Tailwind 4.3.0, pnpm 11, Node 24; API já no lock travado; suíte 585 verde, cov 93,76%; 16 telas v1 sem erro de console. 1.4: shadcn radix (Vega = new-york), tokens claro/escuro do DESIGN em globals.css, Geist/Geist Mono + tabular-nums, escala type-* e raios, Switch de tema (system, persiste), anel 2px+offset, Sonner; ui.tsx vira fachada; v1 migrada de gain/loss/accent. 1.5: Vitest 4 + `pnpm test` com "no raw color" (exceção v1 só a pizza da alocação), /dev/tema claro×escuro (404 em produção), hook roda eslint+vitest. 1.6: portas em 127.0.0.1, env_file .env, senha no Postgres (ALTER USER às cegas) e no Redis, api recusa dev-insecure-* fora de test, Hermes não montado (HERMES_ENABLED=false), login 5 erros/15 min → 429 com a mensagem; redis_url na config. 1.7: Barra lateral 240px (4 áreas + Importar, ativo pela área inclusive nas URLs v1), Barra superior 56px fixa, abas na URL com ←/→, telas v1 por link dentro da área, Importar em painel lateral 560px (200/150 ms, foco preso, Esc), / → Visão geral, empilha < 1024px; 35 rotas sem erro de console. 1.8: Seletor de período na Barra superior (out/2026 mono, ‹ ›, popover, futuro e < jul/2024 desabilitados com tooltip, URL < jul/2024 → jul/2024, sem período = mês atual BRT), lib/period (resolvePeriod mes/tri/ano/inicio) e lib/format (NBSP, menos tipográfico, 2 casas, p.p.) com Vitest. 1.9: login com tokens/componentes novos; 401 → refresh → repete; sem sessão (proxy, gate ou refresh falho) → /login?next=<rota+query> e volta com o período; next só relativo; token só em memória; testes de cookie (httpOnly, lax, sem secure) e CORS só localhost:3000. |
| 2026-10-18 | m1 | Épico 1 fechado | Code review do épico: 10 achados aplicados com teste (open redirect no next, segredos placeholder, BACKUP_DIR relativo + *.dump no .gitignore, dados_reais roda o upgrade, Atualizar tudo não força backup, cores v1 de investimento, DSN com senha especial, guarda do Alembic só em escrita, baseline em Decimal, zero sem sinal). Suíte 606 verde, cov 93,86%, 0 dados_reais pulados; web 35 Vitest + lint + build. |
| 2026-10-18 | m1 | Épico 2: import + 2.1 | Base importada até 16/10/2026 (ADR-016). 2.1: common.money (Money/Pct), models.Valued, deps, owner, cache único (PriceCache + invalidate_xirr_cache saem de market/portfolio; wallet deixa de importar portfolio), MonthStatusPort "todos abertos" registrado no main, resolve_period, teste que barra date.today()/now() sem fuso. 2.2: revisões 0016 (user_id no ledger, default = dono) e 0017 (import_batches/import_batch_files, 5 lotes legacy, batch_id + source com CHECK) aplicadas no banco local com backup; engine ingest; imports v1 gravam lote applied; dados_reais restaura→mede→upgrade→mede + idempotência. 2.3: revisão 0018 (category_groups com kind, categories.group_id/role/key, transactions.category_id NOT NULL + payer, fixed_costs.category_id, mapa explícito, Cripto Nubank, sistema a classificar, triggers transitórios até a 2.5) aplicada; transit/caixinhas/bloco cripto leem key via ledger.queries; script compare_categorias; dados_reais: só deltas listados, renome não muda nada, baseline igual. 2.4: revisão 0019 (category_rules com direction, 61 regras legado; padrões de investimento → saída invest + entrada Resgate; subcategorias de Resgates; categorization_events; category_source/review_status/category_rule_id: 1.160 manual, 346 rule, 160 suggestion; importado sem revisão = pending) aplicada; totais idênticos. 2.5: ledger.service.categorize() (category_id + kind do grupo + texto + origem + evento com cause + mark_dirty + hooks; manual nunca sobrescrito), ledger/calc.best_rule (direção, mais longa, empate → recente); import e rotas v1 passam por ele; revisão 0020 deixa só o fallback de INSERT (Hermes); testes: guarda de UPDATE fora do categorize e invariante de kind (dados_reais). 2.6: revisão 0021 (pair_key invest↔resgate; 69 resgates → Resgates, 18 faturas → Cartão de crédito, Repasse → Devoluções; 87 eventos migration) aplicada; termos por role em ledger/calc; transit/cripto/caixinhas leem as duas keys (iguais); telas v1 mostram a taxa v2; lista v2 de poupança fixada (jun/2026 = 56,87%). Pendências em docs/v2/PENDENCIAS-VITOR.md. 2.7: GET /api/v1/ledger/transactions (paginada, Money, fonte/lote/regra), PATCH .../category (categorize manual, inline_edit), GET /ledger/categories; Tabela de dados v9 (Resumo/Detalhado lembrado, ordenação, →/← expande, filtro > 20 linhas, 1ª coluna fixa, th scope), Combobox de categoria, Selo de estado; testado no navegador. 2.8: POST/PATCH/DELETE /api/v1/ledger/transactions (manual: source manual, sem lote, categorize manual; importada só muda categoria → 409; mark_dirty), Money recusa float (422); Formulário em painel lateral reutilizável (descartar alterações, falha com Tentar de novo), Nova transação / Editar / Apagar com confirmação; testado no navegador. 2.9: API category-tree, grupos (tipo travado com transações), subcategorias (herda tipo e role padrão; renome regrava texto legado; mover regrava kind via categorize cause move; com transações só arquiva; sistema travado) + fumaça v1 by-category igual após renome; tela Ajustes › Categorias (arquivadas esmaecidas, formulários, aviso de renome, foco volta). 2.10: GET/PATCH /api/v1/ledger/rules (condição, direção, categoria, ativa; desativar não mexe no já categorizado), POST rules/preview (só lê), rules/reapply/preview (antes × depois, manuais preservadas, mudanças em mês fechado) e rules/reapply (categorize origem rule, cause reapply, numa transação, mark_dirty pelo categorize); tela Ajustes › Regras (Tabela de dados, painel com prévia ao digitar, reaplicar por período, estado vazio) + prévia no /dev/tema; testado no navegador (61 regras, prévia 'uber' = 3). |
| 2026-10-18 | m1 | Épico 2 fechado | Base importada (460ee75). Code review: 10 achados aplicados com teste (029b216): reimport B3 todo coberto → 0 sem 500; apagar categoria com histórico → 409; papel escolhido sobrevive ao mover e papel de outro tipo é recusado; import atômico (savepoint por linha); hook do portfolio invalida o XIRR em import/categorize; regras de grupo arquivado não aplicam; ids malformados/conta inexistente → 422/404; PUT v1 não muda dinheiro de importada; CRUD v1 de categorias grava regras e não muda kind; empate total de regra = menor id (como a 0019). Suíte 667 verde, cov 93,61%, 0 dados_reais pulados (DADOS_REAIS_REQUIRED=1); mypy das engines limpo; web 37 Vitest + lint + build. |
| 2026-10-18 | m1 | Épico 3: 3.1 | BASE do épico = e542ac7. 3.1: common.alerts (Alert com key/fingerprint/severity/ação/as_of/dismissible, AlertContext congelado, fingerprint(), brl(), LegacyAlert das telas v1); engine alerts (registro de providers no main, GET /api/v1/alerts compute-on-read: divergências antes, mais recentes primeiro, data_until; POST /alerts/dismissals; dispensa volta com fingerprint novo e some quando o provider para); revisão 0022 alert_dismissals aplicada com backup; providers: custo fixo vencendo, gasto acima da média (role consumo, por subcategoria) e posição DeFi vencendo, com mensagens do catálogo; dados_reais: p95 < 500 ms com 3 meses em ajuste; Sino na Barra superior (contador sem vermelho, aria-live) + Central de avisos 560px (foco na 1ª ação, ação fecha o painel e leva à tela filtrada, Dispensar, vazio "Nenhum aviso. Dados até …"), Linha de aviso no /dev/tema; testado no navegador (3 avisos reais). |
| 2026-10-18 | m1 | Épico 3: 3.2 | Revisão 0023 aplicada com backup (pre-0023): assets (key imutável por trigger, classe do enum AD-11, price_ref, valoração, %CDI) + asset_aliases(chain, symbol); asset_operations.asset_id e wallet_positions.asset_id NOT NULL pelo mapa explícito (b3:, td:IPCA+2032/IPCA+JS2055/PRE2032/SELIC2028, caixinha:turbo/reserva/snowtrip/encerradas, debenture:flash, cdb:guanabara, crypto: — ETH em 3 cadeias e HYPE L1+EVM = um ativo); linha nova sem id resolvida por trigger; portfolio_targets.class gerada + asset_id nulo; base real: 41 ativos, 0 órfãs. Enums de portfolio/constants → common/assets (+ AssetClass, CLASS_BY_CATEGORY, canonical_category); POST/PUT v1 de operação recusa classe fora das 6 (422, antes viraria 500 no trigger). dados_reais: contagem, aplicado, XIRR e telas v1 (posições, alocação) iguais; idempotente (desce/sobe = mesmas keys e vínculos). Telas v1 de portfolio/carteiras sem erro no navegador. |
| 2026-10-18 | m1 | Épico 3: 3.3 | Protocolo SourceAdapter em ingest/protocol (detect, parse, plan, apply, undo; FilePlan com fingerprint no hash; PlanError) + registro de adapters e hooks on_batch_applied/on_batch_undo no main. POST /api/v1/ingest/preview (multiarquivo, python-multipart 0.0.32): lote staged com arquivos + plano + hash, 24 h, por arquivo fonte/conta/período/novos/existentes/pulados/já importado/escolha pendente/erro; nada gravado. POST /ingest/replan (overrides por file_hash → novo staged, novo hash). POST /ingest/confirm: re-planeja, exige o hash, todos os apply numa transação, import_batch_files com file_hash, applied, hooks do lote, mark_dirty dos meses, XIRR invalidado; segunda confirmação → 409; prévia desatualizada/expirada → 409; escolha pendente → 422. Adapter Nubank (ledger/adapters: OFX pela conta do ACCTID e dedup por FITID; CSV pede a conta; transferência interna antes das regras) sobre importer.insert_entries (categorize, pending, sem hooks por linha). Provider "Arquivo já importado: {nome}. 0 transações novas.". Página v1 /ledger/import passa pelo protocolo (prévia + confirmação). Fumaça: OFX real do MEI → 0 novas, 44 existentes. |
| 2026-10-18 | m1 | Épico 3: 3.4 | Revisão 0024 aplicada com backup (pre-0024): accounts.holder (Nubank_CPF = pf, Nubank_CNPJ = mei; idempotente) e account_balances (conta, data, saldo, batch_id; uma linha por conta e data). Adapter OFX: LEDGERBAL/DTASOF → saldo informado na prévia, em import_batch_files e em account_balances (também com 0 novas); pagador das entradas (nome do Pix recebido, senão CNPJ) em transactions.payer, sem decidir categoria; OFX do MEI com vários meses aceito; undo do adapter remove saldos do lote. |
| 2026-10-18 | m1 | Épico 3: 3.5 | Revisão 0025 aplicada com backup (pre-0025): asset_operations.transaction_id (FK RESTRICT, único) pelo external_id (FITID; fallback data:valor) e protected (caixinha-yield:*, resgate da Turbo reduzido, bucket Encerradas); base real: 113 ligadas, 3 protegidas, 0 caixinha sem vínculo. portfolio.caixinhas.derive_caixinha_ops (cria/corrige/apaga por transaction_id; protegida nunca muda) nos hooks on_transactions_changed, on_batch_applied e on_batch_undo (registrados no main). dados_reais: reimport de todos os OFX 2024–2026 pelo protocolo = 0 novas; rederivar tudo = nada a mudar; net, aplicado e XIRR das caixinhas/CDB e XIRR consolidado = baseline. |
| 2026-10-18 | m1 | Épico 3: 3.6 | ledger/suggest reescrito: tokens (minúscula, sem acento, sem números), Jaccard ≥ 0,6, best_suggestion sobre o histórico confirmado do mesmo sinal (qualquer tipo; empate → a mais recente); insert_entries: sem regra → categorize(source suggestion, pending), sem histórico parecido → "a classificar". Tela v1 de sugestões usa o mesmo Jaccard. Testes por tipo (gasto, receita, investimento, transferência), sem histórico, abaixo do limiar, sinal trocado, empate e import com histórico confirmado. |
| 2026-10-18 | m1 | Épico 3: 3.7 | CSV do Nubank: detectado e deduplicado; a linha pede a conta (needs) e avisa "CSV não permite conferir o saldo. Prefira o OFX." (FilePlan.warnings); provider "CSV importado sem conferência de saldo. Só o OFX permite conferir." (ação Importar OFX) enquanto o último extrato aplicado da conta for CSV sem OFX cobrindo o período; arquivo desconhecido recusado só na linha dele com a lista dos formatos aceitos. |
| 2026-10-18 | m1 | Épico 3: 3.8 | Revisão 0026 aplicada com backup (pre-0026): broker_position_snapshots (ref_date, asset_id, quantidade, valor informado, batch_id; único por data e ativo). B3Adapter (portfolio) no protocolo: detecta mov/neg/consolidado pelo xlsx; período pelo nome (datas; mensal = mês; anual = 31/12), editável por overrides, nome fora do padrão exige período; mov/neg com dedup por operation_hash, corte por ticker e pareamento liquidação × negócio (soma do dia, até 7 dias) — a mesma operação entra uma vez, no mesmo lote (movimentação aplicada antes, apply_rank) ou em lotes diferentes; consolidado grava snapshots e só aplica preço se for o mais recente e o preço atual não for mais novo. Página v1 /portfolio/import-b3 pelo protocolo (manda o nome do arquivo). Base real: os 16 arquivos de files/b3 importados = 0 operações novas (as 7 liquidações de 09/06 casam), 217 posições em 11 datas; dados_reais: XIRR/aplicado/net = baseline com os mesmos preços. P6 resolvida pelo adapter. |
| 2026-10-18 | m1 | Épico 3: 3.9 | Hub de import substitui o painel provisório: Bloco Fontes (5 fontes de arquivo, tipo, atualizado até de import_batch_files applied/legacy, ponto de aviso), dropzone (foco ao abrir, arrastar ou escolher), prévia multiarquivo numa Tabela de dados ("Lendo…" com esqueleto, fonte/conta/período, novos/existentes/pulados, recusado na linha, conta do CSV e período B3 editáveis → nova prévia), Confirmar só com tudo lido, sem escolha pendente e com algo novo; falha → mensagem + foco em Tentar de novo com os arquivos mantidos; transações novas → ?revisar=<lote> (abre a Revisão na 3.10); ?importar=1 abre o Hub (ação dos avisos). API: GET /ingest/sources; ingest/calc (atraso FR-3: PF 7 dias, MEI/consolidado mês anterior até o dia 15; lacunas: Nubank por intervalo, consolidado por mês); providers "{Fonte} sem import desde …" e "Lacuna em {fonte}: …"; titular por resolver registrado pelo ledger; período do OFX por DTSTART/DTEND; apiFetch não força JSON em FormData. Base real: sem avisos de fonte. Testado no navegador (prévia real, confirmação, falha simulada e Tentar de novo). |
| 2026-10-18 | m1 | Épico 3: 3.10 | API: GET /api/v1/ledger/review?lote= (pendentes com origem regra/sugestão/sem sugestão/manual, conta, regra; meses com contagem, entradas e saídas), POST /review/confirm (marcadas → confirmed via categorize cause review; trocada vira manual, mantida guarda a origem e a regra; "a classificar" → 422 sem_categoria; devolve confirmadas e restantes); provider "{n} transações a revisar." (ação Revisar → ?revisar=todas). Revisão de transações: painel largo min(1040px, 100vw − 48px) aberto por ?revisar=<lote|todas> (o Hub abre ao confirmar com transações novas), todas marcadas, agrupada por mês com subtotais, foco na 1ª linha, ↑↓/Espaço/C/Enter, Shift+clique em intervalo, troca vira "manual", cabeçalho reconta, Confirmar desabilitado com "{n} sem categoria…" (aria-describedby), "Só sem categoria" e vazios, toast "{n} transações confirmadas. {m} continuam a revisar.", falha mantém marcações e foca Tentar de novo. Testado no navegador (212 pendentes reais na cópia dev; confirmação, falha simulada). |
| 2026-10-18 | m1 | Épico 3: 3.11 | API: POST /api/v1/ledger/rules/propose (condição proposta pelo trecho do memo depois do primeiro " - ", sem partes com número; direção pelo sinal; quantas outras não manuais mudariam) e POST /rules (grava a regra — origem review com created_in_batch quando vem da Revisão, senão manual; reativa se já existir — e aplica às afetadas não manuais via categorize cause rule_created). Faixa "Criar regra? Descrição contém '…' → … Afeta {n} outras transações." sob a linha trocada (regra/sugestão) na Revisão e em Caixa › Transações (DataTable.renderBelow): Criar regra, Ajustar condição com prévia ao vivo (rules/preview, debounce comum em lib/use-debounced), Agora não; confirmar o lote sem responder fecha as faixas. Testado no navegador (proposta, ajuste, criação). |
