# PROMPT — Inicialização m2 Portfolio Engine (2026-06-04)

**Sessão:** m2-portfolio | **Que começa:** STORY-02-01  
**Duração estimada:** 8–10 sessões | **Gate crítico:** XIRR Python == Excel XIRR (±0,1 pp)

---

## Estado inicial (herança do m1)

✅ m1 Ledger Engine **consolidado** em 2026-06-04.  
✅ Dados validados jan–jun/2026 (320 tx), saldo R$ 3.386,75.  
✅ kind-aware finalizado (investimento fora do saldo fantasma, fora da taxa de poupança).  
✅ Bridge m1↔m2 documentado em `docs/09_Bridge_M1_M2.md`.

---

## O que o m2 faz

**Portfolio Engine** é responsável por:
1. **XIRR** — taxa interna de retorno consolidada (métrica primária) + por ativo
2. **Posições** — quantidade + valor atual de cada ativo em holding
3. **Alocação** — % atual vs. % meta + desvio + rebalanceamento
4. **Operações** — histórico de compra/venda com data/preço/quantidade
5. **Ponte com m1** — investimentos do Ledger (kind=investment) = aportes que o Portfolio reconcilia

---

## Dados que você TEM (input do m2)

### Do m1 Ledger (importado, validado, coerente)

```sql
-- Aportes/resgates m1 → m2
SELECT date, category, amount FROM transactions 
  WHERE kind = 'investment' 
  ORDER BY date;

-- jan/2024: Flash Capital (débito), CDB, Caixinha
-- fev/2024–jun/2026: 320 tx incluindo Toro (B3), Binance, Tesouro Direto, DeFi
-- Resgate RDB, venda PETR4, etc. como amount > 0 (entrada)
```

### Da planilha (arquivo > docs/, conversão manual p/ seed m2)

```
aba OPERAÇÕES (jan/2024–jun/2026, ~400 linhas):
  - Cada linha = operação (compra/venda/dividendo/juros)
  - Coluna: data, ativo, tipo, qtde, preço unitário, total, corretor

Usado para:
  1. Seed `asset_operations` (migration 02-01)
  2. XIRR validation (gate: Python XIRR == Excel XIRR ±0,1 pp)
  3. Posições histórias (reconciliação com m1)
```

### Do Goodies já pronto (m3/m4 vêm depois)

- Preço manual (você insere via UI ou via endpoint)
- Contas: Toro (CNPJ), Binance (API via m4), Caixinha/RDB (manual), Flash (manual), Tesouro (API m3)

---

## Roadmap m2 (16 stories, 4 fases)

### Fase 1: Schema + CRUD (stories 02-01 a 02-03)

```
STORY-02-01: Schema `asset_operations` + `portfolio_targets`
  - asset_operations: operações históricas (compra/venda/dividendo/juros)
  - portfolio_targets: alvos de alocação (ex.: Ações 10%, Renda Fixa 50%, Cripto 5%)
  - RLS + índices

STORY-02-02: Seed portfolio_targets
  - 6 categorias (Ações Nacionais, ETFs, FIIs, Renda Fixa, Cripto, Aposentadoria)
  - Metas do Vitor da planilha
  - Migration com INSERT ... ON CONFLICT

STORY-02-03: CRUD de operações
  - POST/PUT/DELETE em /api/v1/asset-operations
  - Validação: tipo (compra/venda/dividendo/juros), quantidade > 0, preço > 0
  - Frontend: formulário com auto-complete de ativos
```

### Fase 2: Cálculos DCA + XIRR (stories 02-04 a 02-06) **← GATE CRÍTICO**

```
STORY-02-04: Preço médio ponderado (DCA)
  - Fórmula: Σ(qtde_i × preço_i) / Σ(qtde_i)
  - Incluindo aportes do m1 como if "compra" implícita

STORY-02-05: XIRR — implementação e testes (GATE CRÍTICO)
  - scipy.optimize.brentq(npv, -0.999, 100.0)
  - Teste: XIRR Python vs. Excel XIRR na planilha ±0,1 pp
  - Cobertura ≥ 95% (roteador matemático crítico)

STORY-02-06: Endpoints XIRR
  - GET /api/v1/portfolio/xirr → consolidado (anualizado)
  - GET /api/v1/assets/{symbol}/xirr → por ativo
  - GET /api/v1/portfolio/xirr?from=YYYY-MM-DD&to=YYYY-MM-DD (período)
```

### Fase 3: Posições + Alocação (stories 02-07 a 02-09)

```
STORY-02-07: Posição atual por ativo
  - Saldo = compras - vendas (de asset_operations)
  - Valor = saldo × preço_atual (preço manual por enquanto)
  - View `positions` (persistida ou calculada)

STORY-02-08: Alocação atual vs. meta
  - % atual = valor_ativo / valor_total_carteira
  - Desvio = % atual - % meta
  - Ranking por desvio (ajuda rebalanceamento)

STORY-02-09: Motor de rebalanceamento
  - Sugestão de aporte para cada categoria
  - Baseado em desvio (maior desvio → aporte maior)
  - Frontend: slider interativo
```

### Fase 4: Data migration + validação (stories 02-17 a 02-18) **← GATE CRÍTICO**

```
STORY-02-17: Seed asset_operations com histórico planilha
  - Migration p/ inserir ~400 operações jan/2024–jun/2026
  - Mapeamento ativo: Excel PETR4 → Postgres 'PETR4'
  - Broker: Excel 'Toro' → Postgres 'Toro'

STORY-02-18: Validação XIRR
  - Rodar XIRR Python sobre histórico seed
  - Comparar vs. Excel XIRR (goal: ±0,1 pp)
  - Report: ativo com maior desvio, ação
  - Gate: passar antes de mover para m3/m4
```

### Fases 5–6: Renderização + Dividendos (stories 02-10 a 02-16)

```
STORY-02-10: Rastreamento de rendimentos
  - Dividendo de FII (JCP) registrado separado
  - Não mistura ganho de capital em `asset_operations`
  - Fórmula: Σ(dividendos) por ativo/período

STORY-02-11: Estimativa de IR
  - Ganho de capital = valor_atual - custo_total
  - IR estimado = 15% (padrão) ou 20% (operações day-trade)
  - Flag: vendas do mês alertam se > R$ 35k (isenção cripto)

STORY-02-12: IR cripto — consolidação mensal + alerta 80%
  - Vendas cripto acumuladas no mês vs. R$ 35k
  - Alerta em 80% (R$ 28k)
  - Consolidar por asset (BTC, ETH, etc.)

STORY-02-13/14: Frontend — tabela de posições + histórico
  - Tabela: ativo, qtde, preço_médio, preço_atual, ganho%, alocação%
  - Histórico de operações: filtros por ativo/período/tipo
  - Exportar CSV

STORY-02-15/16: Frontend — alocação vs. meta + rebalanceamento
  - Pizza chart: atual vs. meta (lado a lado)
  - Rebalanceamento: sliders, sugestão de aporte
  - Simulador: "se investir R$ X em Y, alocação fica..."
```

---

## Gate m2 (antes de mover para m3)

**XIRR Python == Excel XIRR (±0,1 pp)** na planilha histórica.

**Checklist:**
- [ ] asset_operations seed com 400 operações
- [ ] XIRR calculado sobre seed
- [ ] Relatório: ativo com maior desvio vs. Excel
- [ ] Ação corretiva (se desvio > 0,1 pp)
- [ ] Validação refeita (goal: sem achados)

---

## Dados brutos p/ você começar

### Histórico de operações (da planilha)

Tabela mínima para seed (coloque em `docs/m2_operacoes_historicas.csv` p/ fácil import):

```
data,ativo,tipo,quantidade,preco_unitario,broker,categoria
2024-07-15,PETR4,compra,100,50.00,Toro,Ações Nacionais
2024-08-10,BTC,compra,0.003816,8419.48,Binance,Cripto
2024-09-05,Flash-Debênture,aporte,12000.00,1.00,Flash,Renda Fixa
...
```

### Metas de alocação (do Vitor, em docs/08_Contexto_Financeiro.md §3)

```
Ações Nacionais: 10%
ETFs: 12.5%
FIIs: 10%
Renda Fixa: 50%
Cripto: 5%
Aposentadoria: 12.5%
```

### Destinos m1 → m2 (bridge, em docs/09_Bridge_M1_M2.md §1)

| m1 category | m2 broker | Modelo |
|---|---|---|
| Toro (B3) | Toro | holding-based |
| Binance | Binance | holding-based |
| Caixinha/RDB | Caixinha/RDB | flow-based |
| Renda Fixa Nubank | Renda Fixa Nubank | flow-based |
| Liquid/DeFi | Liquid | holding-based |
| Flash Capital debêntures | Flash | flow-based |

---

## Como começar (SESSION m2)

```
1. Read CLAUDE.md + PROGRESS.md (get context)
   → note que m1 está CONSOLIDADO
   
2. Read docs/{08_Contexto_Financeiro,09_Bridge_M1_M2}.md
   → entender semântica de aportes, destinos, gate XIRR
   
3. /story 02-01
   → carregar story + rodar TDD (RED → GREEN → REFACTOR)
   
4. Loop: STORY-02-02 → 02-03 → 02-04 → 02-05 (gate crítico)
   → antes de 02-06, validar XIRR vs. Excel
   
5. /gate m2
   → antes de mover para m3
```

---

## Dicas

- **XIRR é a métrica primária** — mande bien, todo o resto segue. Testes, não intuição.
- **Flow vs. Holding** — não misture lógica (fluxo=aportes, holding=scanner de posição).
- **Bridge m1↔m2** — cada `kind=investment` do m1 é um ativo pendente no m2. Reconciliação = insira a operação real (ativo, qtde, preço).
- **Seed é crítico** — dados históricos devem bater com a planilha. Senão, gate fica em risco.
- **RLS** — não esqueça de filtrar por `user_id` em `asset_operations` e `portfolio_targets`.

---

## Próximos milestones (depois de m2)

- **m3 Market Engine** — preços do BRAPI (B3), CoinGecko (cripto), Tesouro API
- **m4 Broker Integration** — scanner Binance API, wallet scan Etherscan/Solscan/Liquid
- **m5 Analytics** — benchmarks (CDI, IPCA, IBOV), alertas, projeção de patrimônio

---

**Pronto?** Use este prompt em uma nova sessão com:
```
/story 02-01
```

Sucesso! 🚀
