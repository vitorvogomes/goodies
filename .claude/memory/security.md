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

## 5. Nota sobre `LBTC_ASSET_ID`

- É uma constante **pública** da Liquid Network, mas por escolha do Vitor ela
  também é **env-managed** (`${LBTC_ASSET_ID}` nos arquivos, valor real só no
  `.env`) — mesmo tratamento dos endereços. Ver ADR-005.

## 6. Dados financeiros

- `docs/Utils/posicao.json` contém posições reais (mantido por escolha do dono).
  Se o repo for tornado público, revisar antes: posições/saldos são sensíveis.
- Logs: `structlog` — **nunca** logar valores financeiros em texto plano (CLAUDE.md).

Relacionado: `.claude/memory/decisions.md`, `.claude/memory/conventions.md`.
