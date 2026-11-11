# Débito Técnico — Goodies v2 (registro vivo)

Só o que está **em aberto**. Item resolvido sai daqui (fica no git). O registro da v1 (m0–m4 e a
retomada de 17/10/2026) está em [`docs/v1/15_Debito_Tecnico-v1.md`](v1/15_Debito_Tecnico-v1.md).
Atualizar a cada review.

Legenda: **🟡 MÉDIO** · **⚪ MENOR (rastrear)**.

---

## 🟡 MÉDIO

### Leituras repetidas do histórico inteiro no fechamento
`pf_balance_check` (todas as transações da PF) roda em `pf_month_checked` e de novo em
`run_checks`/`close_checks`; `ingest.sources()` refaz a cobertura; `accounts_balance` faz uma query
de movimentos por conta ancorada. `checklist()`, `close_month()` e `recovery()` leem a PF 2–3× por
chamada, e o custo cresce com o histórico (27+ meses). **Fix:** calcular a conferência da PF uma
vez por requisição (contexto/memo, como `balance_alerts` já faz) e somar os saldos em SQL.
(Review final de 18/10/2026.)

### Fetchers fail-soft sem log
`CoinGeckoFetcher` e `BrapiFetcher` engolem a exceção (`except Exception: return {}`) sem logar:
um erro de parse (a API mudou o schema) fica igual a uma queda de rede, e o preço só fica velho.
O `job_runs` mostra o job `partial`, mas não o porquê. **Fix:** `logger.warning` com fetcher,
endpoint e tipo da exceção antes do fail-soft.

---

## ⚪ MENOR (rastrear)

- **Produção (Railway, ADR-018):**
  - não há tela para trocar a senha do admin: é `seed_admin` dentro do container (`railway ssh`, runbook §3);
  - o bloqueio de login é por e-mail e em memória: quem souber o e-mail trava o login por 15 min, e um redeploy
    zera a contagem. 2FA e limite por IP seguem no backlog;
  - `passlib` 1.7.4 está parado: com o bcrypt 4.3 só gera o aviso `(trapped) error reading bcrypt version` na
    subida, mas o bcrypt 5 o quebra. Trocar por `bcrypt` direto antes de atualizar o bcrypt;
  - banco com tabelas mas sem `alembic_version` (dump restaurado sem ela) conta como vazio: a subida tenta o
    bootstrap e cai com `relation "users" already exists` — falha alta, sem perda de dado, mas a mensagem engana;
  - a cópia fora do Railway (`scripts/backup_railway.sh`) depende do `railway ssh` com a chave do Vitor; até a
    1ª cópia, os backups ficam só no volume `/backups`.

- **v2.2 (ADR-019):**
  - a oportunidade muda o peso dentro da classe, mas com aporte pequeno e cotas inteiras (B3) o
    arredondamento costuma levar tudo ao mesmo ativo, e o ajuste não aparece; o efeito é maior em classe de
    valor livre (cripto) e com aporte maior;
  - o histórico depende do COTAHIST no site da B3 (sem contrato); se o endereço mudar, `price_history` fica
    `partial` e a máxima de 52 semanas some dos sinais (o resto segue);
  - a máxima de 52 semanas só vale com 6 meses de histórico do ativo; ativo novo fica só com 3 meses e preço
    médio;
  - as telas de celular não têm teste automatizado (só o vitest de utilitários): a conferência é por captura em
    390px.

- **Parser de fatura do cartão Nubank:** não existe; o Hub importa só o extrato da conta (OFX/CSV),
  a B3 (movimentação e consolidado) e o Tesouro.
- **Trilhos amarram nomes de categoria:** `portfolio/transit.RAILS` e as caixinhas casam por chave
  ou nome de categoria do ledger, que se edita em Ajustes › Categorias. Renomear quebra o trilho
  em silêncio. Centralizar (setting ou coluna na categoria). Mesma classe: o 2º destino do troco
  das cotas é a `caixinha:turbo` com teto de R$ 5 mil fixos no código
  (`planning/distribution_service.TURBO_KEY/TURBO_CAP`).
- **Jobs em série:** `run_wallet_scan` roda os fetchers um por um numa conexão e `refresh_stale`
  espera a soma dos jobs vencidos. `asyncio.gather` por fonte/job cortaria o tempo do "Atualizar
  tudo". Cron 3×/dia → baixa prioridade.
- **Crescimento lê o ledger cripto 2×:** `closing/growth._crypto_block` chama `sleeve_cashflows`
  de novo depois de `closing.service.positions` (o bloco cripto). Passar os fluxos ou o XIRR pela
  `PositionClass` evita a segunda leitura.
- **Teto da Turbo × aporte mensal da reserva:** o 2º destino do troco conta só o saldo da Turbo no
  início do mês; o aporte mensal da reserva não diz em qual caixinha cai, então o teto de R$ 5 mil
  pode ser passado se ele for todo para a Turbo.
- **Duplicações pequenas:** `_to_float` em `portfolio/b3_import.py` e `portfolio/migration.py`;
  a assinatura HMAC da Binance copiada em 3 spikes (`scripts/spikes/`) além do `BinanceFetcher`.
- **`crypto_cost_basis` (migração 0014) sem leitor:** a tabela e `scripts/spikes/
  reconstruct_binance_cost.py` ficam para um preço médio por ativo cripto no futuro (hoje a cripto
  é bloco: quanto saiu × quanto vale).
- **Valoração da debênture Flash por dias corridos/30:** a fórmula da plataforma é por dias úteis
  (deriva ~0,44%). Precisa do calendário de feriados ANBIMA.
- **Preço único por ticker:** `asset_prices` guarda um preço por ticker; os specs de preço são
  globais (sem `user_id`). Correto enquanto o app é de um usuário só.
- **Formatação:** `ruff format --check` acusa 67 arquivos (o pre-commit só roda `ruff check`).
  Formatar de uma vez num commit só de formatação, ou ligar o `format` no pre-commit.
