---
tipo: story
epico: EPIC-02
story: STORY-02-17-18
titulo: Migração e validação de dados históricos (OPERAÇÕES)
status: pendente
estimativa: L (4-6h) — gate crítico: XIRR deve coincidir com Excel
tags: [goodies, story, portfolio, migracao, xirr, validacao]
skills: [test-driven-development, systematic-debugging]  # CSV: sem skill → conventions.md (gate crítico)
---

# STORY-02-17-18 — Migração de Dados: Portfolio

**Como** Vitor  
**Quero** importar 400+ operações históricas de investimento da planilha  
**Para** que o XIRR calculado pelo Goodies reflita o histórico real desde jul/2024

---

## Critérios de aceite

- [ ] Script `scripts/migrate_portfolio.py` que lê CSV exportado da aba "OPERAÇÕES"
- [ ] Mapeamento de colunas: data, ticker, categoria, tipo (buy/sell/income), quantidade, preço unitário, total
- [ ] Script idempotente (hash de (data, ticker, op_type, total_amount))
- [ ] Tickers da planilha mapeados para tickers do sistema (ex: "PETR4F" → "PETR4" para BRAPI, mas mantido como "PETR4F" em `asset_operations` para identificação correta)
- [ ] Renda fixa importada por valor total (sem quantidade) — campo `quantity` pode ser null para RF
- [ ] **Validação obrigatória (gate de saída da STORY):**
  - XIRR Python calculado sobre os dados importados
  - Comparar com Excel XIRR na mesma base de dados
  - Diferença deve ser < 0,1 pp
  - **Se diferença > 0,1 pp: parar, investigar, não avançar para m3**
- [ ] Relatório: X operações importadas, Y erros, XIRR resultante

## Notas de implementação
**Para calcular XIRR no Excel para comparação:**
```excel
=XIRR(valores, datas)
```
Onde valores = array dos total_amount (negativos para compra, positivos para venda) + valor atual da carteira no último dia, datas = array das datas correspondentes.

**Atenção ao sinal:** na planilha do Vitor, compras podem estar registradas como positivo — verificar e inverter no script se necessário.

**Cripto em USD:** operações de cripto na planilha estão em USD → converter para BRL usando cotação da data da operação ou usar o valor em BRL se já convertido na planilha. Definir padrão antes de rodar o script.

## Dependências
STORY-02-03 (CRUD de operações), STORY-02-05 (XIRR implementado e testado).
