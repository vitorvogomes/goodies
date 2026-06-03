---
tipo: brief
projeto: Goodies
mestra_responsavel: Hatchepsut
criado: 2026-06-02
status: aprovado
tags: [goodies, brief, planejamento, economia, dev]
---

# Goodies — Product Brief

> Documento de contexto financeiro e estratégico. Input primário para o trabalho da Minerva (PRD + Arquitetura + Stories).
> Produzido por Hatchepsut com base no raio-x completo da planilha financeira (sessão 2026-06-02).

---

## 1. Problema central

Vitor controla suas finanças pessoais numa planilha Google Sheets mantida manualmente desde julho/2024. A planilha está bem estruturada — cobre portfólio, fluxo de caixa, cripto multi-wallet e operações — mas tem limitações estruturais que distorcem a tomada de decisão:

- **Retorno calculado errado:** a métrica principal ("Rent. Nominal 3,14%") usa `(resultado - aplicado)/aplicado`, que ignora o timing dos aportes. Em portfólio DCA, isso é inútil. O número correto é XIRR.
- **Sem benchmark:** não há CDI, IPCA nem IBOV do mesmo período. Impossível saber se a carteira está performando bem ou mal relativamente.
- **Dados críticos manuais:** preços de ativos, posições de cripto em 6+ wallets, e saldo de renda fixa privada são atualizados na mão — ou ficam desatualizados.
- **Caixa e portfólio separados:** o fluxo de caixa e os investimentos não se conversam automaticamente. Taxa de poupança e capacidade de aporte não são calculadas em tempo real.
- **Sem rastreamento de metas:** as metas de Reserva (R$ 50.872) e Liberdade Financeira (R$ 1.271.802) existem na planilha mas não têm progresso % atualizado nem projeção de prazo.
- **Sem alertas ativos:** não existe nada que notifique sobre rebalanceamento necessário, risco de concentração, vencimentos de DeFi ou proximidade de limite de IR (R$ 35k/mês em cripto).
- **Cripto fragmentada:** posições distribuídas em TrustWallet, Phantom, Rabby, Binance, KuCoin e Liquid sem reconciliação automatizada.

---

## 2. Usuário

**Único:** Vitor — investidor individual, 22+ meses de histórico, perfil College→Enterprise em análise de investimentos. Não é iniciante: conhece DCA, rebalanceamento, ciclos de cripto, instrumentos de RF/RV. O sistema precisa respeitar esse nível — não simplificar demais.

Fluxo atual: atualiza a planilha manualmente a cada operação, consulta quando precisa tomar decisão de aporte. Não tem dashboard em tempo real. Toma decisões com dados defasados ou com o número de retorno errado.

---

## 3. Objetivo do produto

Goodies é uma **plataforma pessoal de controle financeiro** que substitui e supera a planilha atual. Não é um app genérico de finanças — é construído especificamente para o portfólio, a estrutura de renda e as metas do Vitor.

O critério de sucesso não é "bonito" ou "completo" — é **tomar decisões financeiras melhores com dados corretos em tempo real.**

---

## 4. Features core — MVP

O MVP cobre os 4 domínios mapeados no Excalidraw:

### Ledger Engine (domínio 1)
- Registro de receitas e despesas por categoria e conta
- Fluxo de caixa com saldo running
- Cálculo automático de taxa de poupança mensal
- Projeção de caixa para 30/60/90 dias
- Controle de custos fixos vs. variáveis
- Alertas de contas fixas vencendo

### Portfolio Engine (domínio 2)
- Registro de cada compra/venda com timestamp (base para XIRR)
- Cálculo de preço médio ponderado por ativo
- **XIRR por ativo e consolidado** — o cálculo mais importante
- % atual vs. % meta por categoria com desvio em pontos percentuais
- Motor de rebalanceamento: quanto aportar em cada categoria para corrigir desvio
- Rastreamento de dividendos/rendimentos separados do ganho de capital
- Estimativa de passivo de IR por categoria

### Market Engine (domínio 3)
- Preços B3: ações, ETFs, FIIs, Tesouro Direto (atualização a cada 4h em dias úteis)
- Preços cripto: BTC, ETH, SOL e altcoins (atualização a cada 2h)
- Cotação BRL/USD para conversão de cripto
- Scan de wallets on-chain: ETH/ARB (`0xB3EE...`), SOL (`BjZ8...`), HYPE, Liquid
- Integração Binance API para posições e saldo

### Analytics Engine (domínio 4)
- XIRR total e por categoria
- Benchmark: CDI, IPCA e IBOV no mesmo período de investimento
- Retorno real = nominal − inflação acumulada
- Drawdown máximo histórico
- Projeção de patrimônio em 3 cenários (conservador 6%, base 10%, agressivo 14% a.a.)
- Anos estimados para atingir meta de Reserva e meta de LF ao ritmo atual
- Detector de correlação de risco (ex: Flash como empregador + credor simultaneamente)

---

## 5. Métricas de sucesso do produto

O Goodies está funcionando quando:

1. XIRR do portfólio está visível e atualizado daily
2. Benchmark CDI/IPCA/IBOV comparável no mesmo período está na tela
3. Taxa de poupança mensal é calculada automaticamente (sem entrada manual)
4. Alertas de rebalanceamento disparam quando desvio ≥ 2pp do alvo
5. Projeção de prazo para LF é recalculada toda vez que um aporte é registrado
6. Posições cripto multi-wallet são reconciliadas sem intervenção manual

---

## 6. Restrições e constraints

| Constraint | Detalhe |
|---|---|
| **Dados manuais persistentes** | Flash debênture, CDB Guanabara e posições DeFi não têm API pública — precisam de entrada manual ou webhook manual. O sistema não pode travar sem eles. |
| **Liquid Network (Bitcoin)** | A API do Liquid é diferente do Bitcoin mainchain — o scan precisa de tratamento específico (`blockstream.info/liquid`). |
| **Binance rate limits** | API pública da Binance tem limite de requisições. Usar cache + cron, não pull on-demand. |
| **IR cripto** | O threshold de isenção é R$ 35.000/mês em vendas por tipo de ativo. O cálculo exige consolidação por mês, não por operação isolada. |
| **Usuário único** | Sem multi-tenant, sem autenticação OAuth de terceiros além do que for necessário para APIs. Auth simples (JWT) é suficiente. |
| **Vencimentos DeFi** | xSOL e hyUSD na Phantom vencem em 29/09/2026. O sistema precisa de alerta de vencimento configurável. |

---

## 7. Fora do escopo (MVP)

- Recomendações de compra/venda (o sistema informa, não recomenda)
- Análise fundamentalista de empresas (isso fica no vault com os mestres)
- Previdência privada (PGBL/VGBL) — tratamento futuro
- Múltiplos usuários
- Aplicativo mobile (web-first)
- Importação automática de extratos bancários (futuro — OpenFinance)
- Tributação completa de IR anual (escopo do GCAP, não do Goodies MVP)

---

## 8. Unit economics / pricing

Ferramenta pessoal, sem monetização planejada. Custo operacional estimado para MVP:

| Serviço | Plano | Custo/mês |
|---|---|---|
| Supabase (DB + auth + storage) | Free tier | R$ 0 |
| Fly.io (FastAPI backend) | Hobby | ~R$ 30 |
| Vercel (Next.js frontend) | Hobby | R$ 0 |
| BRAPI.dev (B3 prices) | Free | R$ 0 |
| CoinGecko API | Free | R$ 0 |
| Redis (cache) | Upstash free | R$ 0 |
| **Total estimado** | | **~R$ 30/mês** |

---

## 9. Adendo — Hermes como braço operacional

O Hermes (agente Discord) já tem um script funcional de coleta de carteira (`coleta_carteira.py`) que roda via cron job e publica snapshot no Discord. Esse é o ponto de partida de uma integração mais ampla.

**Princípio:** o Goodies funciona de forma completamente independente do Hermes. O Hermes é um **braço operacional opcional** — ele pode acionar, executar e consumir dados do Goodies, mas a ausência dele não impacta o funcionamento da plataforma.

**O que o Hermes pode fazer (em paralelo com o desenvolvimento):**

| Workflow | Trigger | O que o Hermes faz |
|---|---|---|
| `portfolio-daily` | Cron: dias úteis 18h | Roda `coleta_carteira.py`, posta snapshot no Discord |
| `portfolio-alert` | Webhook da API do Goodies | Recebe alerta de rebalanceamento e notifica no Discord |
| `market-update` | Comando manual ou cron | Puxa preços atuais via API do Goodies e resume em texto |
| `cashflow-register` | Comando de voz/texto | "Gastei R$ 150 em gasolina hoje" → Hermes POST /expenses via API |
| `analytics-briefing` | Cron: toda segunda 9h | Puxa /resumo-geral da API e posta briefing semanal no Discord |

**Contratos que a API do Goodies precisa expor para o Hermes:**

- `GET /resumo-geral` — snapshot completo da carteira (JSON)
- `GET /alertas` — lista de alertas ativos (rebalanceamento, vencimentos, IR)
- `POST /expenses` — registrar despesa via Hermes
- `POST /income` — registrar receita via Hermes
- `GET /portfolio/xirr` — retorno XIRR atual

**Evolução futura (não-MVP):** Hermes aprende a interpretar perguntas em linguagem natural sobre as finanças do Vitor, consultando a API do Goodies como fonte de verdade. Exemplo: "Hermes, quanto eu gastei em gasolina esse mês?" → Hermes GET /expenses?categoria=gasolina&mes=2026-06.

- Exemplo de interação Hermes: [[Ex_Hermes_Snapshot_Diario]]

---

## 10. Próximo passo (handoff para Minerva)

Com este brief aprovado, a Minerva deve:

1. Acionar `bmad-agent-pm` (John) para refinar e formalizar o PRD → `01_PRD.md`
2. Acionar `bmad-agent-architect` (Winston) para arquitetura técnica → `02_Arquitetura.md`
3. Acionar `bmad-create-epics-and-stories` para quebrar em épicos + stories → `05_Epicos/` + `06_Stories/`
4. Acionar `bmad-generate-project-context` para o `project-context.md` (memória do agente para Claude Code)
5. Acionar `bmad-check-implementation-readiness` para validar prontidão

---

*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
*→ [[08_Contexto_Financeiro]]*
*→ [[README]]*
