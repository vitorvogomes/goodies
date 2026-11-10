# Segurança — Goodies

> Política de dados sensíveis. Vale para humano e para o agente.

## 1. Segredos só em `.env` (gitignored)

- **Todo dado sensível** — chaves de wallet, endereços, tokens de API, connection
  strings, segredos JWT, webhooks — vive **apenas** em `.env`.
- `.env` está no `.gitignore` e **nunca** é commitado.
- Em código/docs, referencie por **nome da variável** (`os.environ["X"]` /
  `${X}`), nunca o valor literal.

## 2. `.env` e `.env.example` SEMPRE sincronizados

- `.env.example` é **público** (commitado): mesmas chaves do `.env`, mas com
  **placeholders** (`your_token`, `0xYOUR_EVM_ADDRESS`, `${...}`) e comentários.
- Regra: ao adicionar/remover uma chave em um, faça o mesmo no outro. As duas
  listas de chaves devem ser idênticas — só os valores diferem.
- Checagem rápida de sync:
  ```bash
  diff <(grep -oE '^[A-Z0-9_]+' .env | sort) <(grep -oE '^[A-Z0-9_]+' .env.example | sort)
  ```
  Saída vazia = sincronizado.

## 3. gitleaks bloqueia segredos antes do commit

- Binário em `~/.local/bin/gitleaks`. Config em `.gitleaks.toml`.
- Hook commitado em `.githooks/pre-commit` (ativar com `bash scripts/setup-dev.sh`,
  que roda `git config core.hooksPath .githooks`).
- Scan manual do que será commitado:
  ```bash
  gitleaks git --staged --redact -c .gitleaks.toml
  ```
- Scan do histórico inteiro:
  ```bash
  gitleaks git --redact -c .gitleaks.toml
  ```

## 4. NÃO expor dados sensíveis no chat do Claude Code

- Ao manipular segredos, **não imprima os valores** no terminal/respostas.
  Use extração programática (grep/sed para arquivo) e reporte só PASS/FAIL,
  contagens ou prefixos mascarados.
- Evite `cat .env`, `echo $TOKEN`, prints de endereços completos, etc.

## 5. Nota sobre os asset IDs e config de wallet (m4)

- Desde 10/11/2026 (revisão das env vars, a pedido do Vitor) os asset ids da Liquid
  (`settings.lbtc_asset_id`/`lusdt_asset_id`) e as URLs base da Blockstream
  (`liquid_base_url`/`btc_base_url`) ficam **no código** (`api/config.py`): são constantes públicas
  da rede. Ver ADR-005.
- Os fetchers de wallet leem endereços do `.env`. Todos os endereços (`WALLET_RABBY_ADDRESS`,
  `WALLET_PHANTOM_SOL_ADDRESS`, `WALLET_SIDESWAP_ADDRESS`, `WALLET_TRUST_BTC_ADDRESS`,
  `WALLET_NEOBANKLESS_ADDRESS` — o depósito Neobankless, lido pelo scan Solana) e
  as URLs de RPC (`SOLANA_RPC_URL`, `HYPEREVM_RPC_URL` — podem embutir chave de provedor) são
  `.env`-managed — mesma tier das API keys.
- Regra do `.env`: só segredo, PII e o que muda por ambiente. Constante pública e política (TTLs,
  flags com padrão) ficam em `api/config.py`; a env var homônima continua podendo sobrescrever.
- **SideSwap** é confidencial (entrada manual): só o **endereço** é env-managed; não há
  credencial/chave de visão guardada.

## 6. Produção no Railway (ADR-018)

- Segredos de produção vivem **só** nas variáveis dos serviços do Railway, gerados novos
  (`openssl rand -hex 32`) — nunca os mesmos do `.env` local, nunca colados no chat.
- O `.env` local é só de desenvolvimento. Para levar chaves de mercado e endereços ao Railway, o
  Vitor cola pelo Raw Editor do serviço; o agente não lê nem repassa valores.
- `ADMIN_EMAIL`/`ADMIN_PASSWORD` só existem na 1ª subida da api (bootstrap) e são apagados depois.
- Postgres e Redis sem acesso público ("Add Public Access" desligado); acesso da máquina local
  só por túnel (`railway connect Postgres --tunnel-only`).
- Logs do Railway seguem a regra de sempre: nada de valor financeiro, DSN ou segredo.

## 7. Dados financeiros

- `docs/v1/Utils/posicao.json` contém posições reais (mantido por escolha do dono).
  Se o repo for tornado público, revisar antes: posições/saldos são sensíveis.
- Logs: `structlog` — **nunca** logar valores financeiros em texto plano (CLAUDE.md).

Relacionado: `.claude/memory/decisions.md`, `.claude/memory/conventions.md`.
