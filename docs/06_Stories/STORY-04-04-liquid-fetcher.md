---
tipo: story
epico: EPIC-04
story: STORY-04-04
titulo: Fetcher Liquid Network (L-BTC) — client dedicado
status: pendente
estimativa: M (2-4h) — atenção ao ADR-005
tags: [goodies, story, market, liquid, cripto, wallet]
skills: [test-driven-development, systematic-debugging]  # ADR-005: client dedicado, não reutilizar fetcher BTC
---

# STORY-04-04 — Fetcher Liquid Network

**Como** Vitor  
**Quero** que minha posição de L-BTC na Liquid seja escaneada automaticamente  
**Para** ter o saldo atualizado sem precisar verificar manualmente

---

## Critérios de aceite

- [ ] `api/engines/market/fetchers/wallets/liquid.py` implementado como client **completamente separado** do fetcher de Bitcoin mainchain
- [ ] Endpoint base: `https://blockstream.info/liquid/api/`
- [ ] Address: `${WALLET_LIQUID_ADDRESS}`
- [ ] Fetcher retorna saldo em L-BTC
- [ ] Conversão para BRL via `CoinGecko BTC/BRL` (L-BTC pareia 1:1 com BTC)
- [ ] Salva em `wallet_positions` com `wallet="liquid"`, `ticker="L-BTC"`
- [ ] Teste: mockar resposta da Blockstream Liquid API e verificar parsing correto
- [ ] **Validação obrigatória:** testar que o endpoint `/liquid/api/` é diferente de `/btc/api/` — usar URL errada deve falhar nos testes de integração

## Notas de implementação
**ADR-005:** Não reutilizar nenhuma lógica do fetcher de Bitcoin mainchain. Liquid usa um formato de resposta diferente para UTXOs (asset_id identifica o ativo — L-BTC tem asset_id específico).

```python
# Estrutura mínima
LIQUID_BASE_URL = "https://blockstream.info/liquid/api"
LBTC_ASSET_ID = ""  # L-BTC asset ID

async def fetch_liquid_balance(address: str) -> float:
    """Retorna saldo em L-BTC para o endereço."""
    url = f"{LIQUID_BASE_URL}/address/{address}/utxo"
    # filtrar UTXOs onde asset == LBTC_ASSET_ID
    # somar valores (em satoshis) e dividir por 1e8
```

## Dependências
STORY-04-01 (schema wallet_positions, worker scaffold).
