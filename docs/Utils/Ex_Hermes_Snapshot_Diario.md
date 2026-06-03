# Goodies — Hermes Integration

Coleta automática de preços e snapshot diário da carteira via Hermes Agent.

---

## Arquivos

```
04_Projetos/Goodies/
├── posicao.json          ← FONTE DE VERDADE: posições, quantidades, custo
├── coleta_carteira.py    ← Script de coleta (Python 3, só precisa de requests)
├── snapshots/            ← JSONs brutos por data (gerado automaticamente)
└── README.md             ← este arquivo
```

Output gerado pelo script:
- `snapshots/YYYY-MM-DD.json` — dados brutos do dia
- `02_Notas/Economia/Portfolio_Snapshot_YYYY-MM-DD.md` — relatório legível no Obsidian

---

## Dependências

```bash
pip install requests
```

Opcional (recomendado para estabilidade):
```bash
# Cadastre em https://brapi.dev e adicione ao ~/.hermes/.env:
echo 'BRAPI_TOKEN=seu_token_aqui' >> ~/.hermes/.env
```

---

## Setup do cron job no Hermes

Envie via Discord para o Hermes:

```
Create a cron job called "portfolio-daily" that runs every weekday at 18:00 (Monday to Friday).
The job should: execute the Python script at /mnt/c/Users/Vitor/OneDrive/Documents/Vault_Vitor/04_Projetos/Goodies/Utils/coleta_carteira.py using the terminal tool, then send the script's stdout output to the Discord home channel.
```

Ou, se preferir em PT-BR:
```
Crie um cron job chamado "goodies-diario" para rodar todo dia útil às 18h.
O job deve: executar o script Python em /mnt/c/Users/Vitor/OneDrive/Documents/Vault_Vitor/04_Projetos/Goodies/Utils/coleta_carteira.py via terminal, e enviar o output (stdout) para o canal do Discord.
```

Para rodar manualmente:
```
Execute o script de portfolio agora e me manda o resultado no Discord.
```

---

## Fontes de dados

| Tipo | Ativos | Fonte | Automático |
|---|---|---|---|
| Ações | BBAS3, CMIG4, PETR4, SOJA3, ITSA4 | BRAPI.dev | ✅ |
| ETFs | NASD11, ACWI11, GOLD11, ALUG11, USDB11 | BRAPI.dev | ✅ |
| FIIs | KNCR11, MXRF11, HFOF11, BTLG11 | BRAPI.dev | ✅ |
| Cripto | BTC, ETH, SOL, PENDLE, HYPE | CoinGecko | ✅ |
| Tesouro Direto | Selic/IPCA+/Pré | API pública TD | ✅ (via frações) |
| CDB privado | Flash, Guanabara | — | ❌ manual |
| DeFi / USDT | posição DeFi, USDT | — | ❌ manual |

---

## Manutenção do posicao.json

**Ao comprar/vender:** atualizar `quantidade` e `custo_total` do ativo.

**Para RF privada e DeFi:** atualizar `valor_atual_base` e `data_base` mensalmente (ver saldo na plataforma).

**Para Tesouro Direto:** o campo `fracoes` é a fração de título comprada. A API retorna o preço unitário do título inteiro; o script multiplica `preco × fracoes` para calcular o valor da posição. Confira na corretora se os valores baterem.

---

## Alertas de alocação

O script gera alerta quando qualquer categoria desviar ≥ 2pp do target definido em `categorias_alvo_pct` no posicao.json. Targets atuais:

| Categoria | Alvo |
|---|---|
| ACOES | 10% |
| ETF | 12,5% |
| FII | 10% |
| RENDA_FIXA | 50% |
| APOSENTADORIA | 5% |
| CRIPTO | 12,5% |

---

*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
