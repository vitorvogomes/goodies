# Goodies no Railway — runbook (ADR-018)

Produção do Goodies desde a v2.1. O `docker compose` local continua sendo o ambiente de desenvolvimento
(`docs/LOCAL_DEV.md`). Decisão e consequências: ADR-018 em `docs/07_Decisoes.md`.

```
internet ──HTTPS──▶ web (Next.js, único domínio público *.up.railway.app)
                      │  rewrite /api/v1/* → API_INTERNAL_URL (rede privada; gravado no BUILD)
                      ▼
                    api (FastAPI + APScheduler, 1 réplica, sem domínio público, volume /backups)
                      ├──▶ Postgres 15  (postgres-ssl:15, sem TCP proxy)
                      └──▶ Redis 8      (template; sem domínio público)
```

Por que um domínio só: o cookie `refresh_token` (httpOnly) é criado pela api e o `web/proxy.ts` precisa enxergá-lo.
Com web e api em subdomínios diferentes de `up.railway.app` o navegador trata como sites distintos e o login volta para
`/login`. Com o rewrite, tudo é mesma origem e o ADR-006 fica como está.

> Config as Code (`railway.toml`) foi depreciado pelo Railway; serviços novos são configurados no painel, conforme
> abaixo. Nada de configuração do Railway vive no repo.

---

## 1. Criar o projeto (uma vez)

Projeto **goodies**, ambiente `production`. Crie os serviços nesta ordem.

### 1.1 Postgres

1. **+ New → Database → PostgreSQL**. O template já sobe e inicializa o volume com a versão dele (18 em nov/2026).
2. Settings → Source → Image = `ghcr.io/railwayapp-templates/postgres-ssl:15`. A imagem da api tem `pg_dump` **15**,
   que não faz backup de servidor 16+, e o Postgres não volta de versão.
3. **Zerar o volume** (só enquanto não houver dado): clicar no volume do Postgres → Settings → **Wipe Volume**. O
   Railway não deixa apagar o volume de um banco ("Delete Volume" fica bloqueado), mas o wipe apaga os dados da 18 e
   dispara um deploy que inicializa tudo de novo com a 15. O log deve mostrar `starting PostgreSQL 15.x` e
   `database system is ready to accept connections`. As variáveis do serviço ficam como estão.
4. Settings → Networking: **não** clicar em "Add Public Access". Basta o `postgres.railway.internal`.
5. Os backups nativos (aba Backups) são do plano Pro. Sem eles, valem os backups da §4 (volume da api + cópia local).

### 1.2 Redis

**+ New → Database → Redis**. Sem domínio público. É só cache (o app cai para o Postgres). O template vem com o
Redis 8 (8.2 em nov/2026), compatível com os comandos que o app usa e com o 7 do compose local; não trocar a imagem
(o template já configura a senha). Na api, usar `${{Redis.REDIS_URL}}` (privada), nunca a `REDIS_PUBLIC_URL`.

### 1.3 api

**+ New → GitHub Repo → este repo**, renomear o serviço para `api`.

| Settings | Valor |
|---|---|
| Source → Root Directory | `api` |
| Build → Builder | Dockerfile (`api/Dockerfile`, detectado) |
| Source → Watch Paths | `/api/**` |
| Deploy → Healthcheck Path | `/api/v1/health` |
| Deploy → Healthcheck Timeout | `300` (a 1ª subida roda o bootstrap) |
| Deploy → Restart Policy | On Failure |
| Scale → Replicas | **1** (APScheduler no processo; 2 réplicas = crons em dobro) |
| Deploy → Serverless (App Sleeping) | **desligado** (dormindo, os crons não rodam) |
| Networking | **sem** domínio público |
| Volume | no **canvas**: clique direito na api → **Attach Volume**, Mount Path `/backups` (sem volume os backups somem a cada deploy; com volume o Railway trava a api em 1 réplica, que é o que se quer) |

Variáveis na aba **Variables da api** (não em Shared Variables; não clicar em SHARE). As referências `${{…}}` são
digitadas literalmente, com o nome **exato** do serviço no canvas, e o Railway resolve para as URLs privadas. O mais
seguro é digitar `${{` e escolher na lista. Uma referência que não casa resolve **vazia**; em produção a api então
recusa subir (`DATABASE_URL`/`REDIS_URL vazia(s) ou em localhost`) em vez de cair no `localhost` do dev:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (URL privada) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `ENVIRONMENT` | `production` (cookie `secure`, `/docs` desligado) |
| `AUTO_MIGRATE` | `true` |
| `BACKUP_DIR` | `/backups` |
| `PORT` | `8000` |
| `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, `HERMES_SERVICE_TOKEN_SECRET` | **novos**, `openssl rand -hex 32` cada; nunca os do `.env` local |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | só para a 1ª subida (bootstrap); **apagar depois** |
| `LEDGER_SELF_IDENTIFIERS` | do `.env` local |
| Mercado: `BRAPI_TOKEN`, `COINGECKO_API_KEY`, `ETHERSCAN_API_KEY`, `BINANCE_API_KEY`, `BINANCE_API_SECRET` | do `.env` local (Raw Editor) |
| Carteiras: `WALLET_RABBY_ADDRESS`, `WALLET_PHANTOM_SOL_ADDRESS`, `WALLET_NEOBANKLESS_ADDRESS`, `WALLET_SIDESWAP_ADDRESS`, `WALLET_TRUST_BTC_ADDRESS` | do `.env` local |
| `SOLANA_RPC_URL`, `HYPEREVM_RPC_URL` | só se usar RPC próprio (sem eles, o público) |

Sem essas chaves os workers de preço e de carteira não fazem nada (sem erro). Ficam no código e **não** vão para o
Railway: asset ids da Liquid e URLs da Blockstream (constantes públicas), TTLs do JWT/Hermes, `PG_TOOLS` (o Dockerfile já
define `local`), `API_HOST` (só num ambiente legado só-IPv6). Também não: `BACKUP_DIR_HOST` (só do compose) e
`EVALUATION_DATE` (só para gate). Não reaproveitar do `.env` local: `DATABASE_URL`, `REDIS_URL`, `POSTGRES_PASSWORD`,
`REDIS_PASSWORD`, `BACKUP_DIR` e os JWT. Segredos nunca passam pelo chat.

### 1.4 web

**+ New → GitHub Repo → este repo**, renomear para `web`.

| Settings | Valor |
|---|---|
| Source → Root Directory | `web` |
| Build → Builder | Railpack (Node de `engines.node` ≥ 24 e `pnpm@11.2.2` de `packageManager`, no `package.json`) |
| Source → Watch Paths | `/web/**` |
| Deploy → Start Command | **vazio**: o Railpack detecta pnpm (`packageManager` + `pnpm-lock.yaml`) e roda o script `start` (`next start`, que lê `PORT`) |
| Deploy → Healthcheck Path | `/login` |
| Networking | **Generate Domain** (este é o endereço do app) |

| Variável | Valor |
|---|---|
| `API_INTERNAL_URL` | `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000` |

É a **única** variável do web, e é lida **no build**. Se mudar, faça **redeploy com rebuild**: só reiniciar não troca o
destino do rewrite. Sem ela o build aponta para `127.0.0.1:8000` (o padrão de dev) e `/api/v1` dá 500. Não existe URL
de api no browser (o `web/lib/api.ts` usa sempre a mesma origem), então também não há CORS a configurar.

---

## 2. Primeira subida (bootstrap)

1. O Vitor faz o push do `main` (deploy = push manual) ou clica Deploy nos serviços.
2. Log da api. A subida (`scripts.ops.startup`) faz, num banco vazio:
   backup em `/backups/pre-migracao` → `alembic upgrade 0002_refresh_token_hash` → admin de `ADMIN_EMAIL`/`ADMIN_PASSWORD`
   → `alembic upgrade head` → uvicorn. Sem `ADMIN_*`, ela recusa subir com
   `banco vazio: defina ADMIN_EMAIL e ADMIN_PASSWORD`.
   - Por que essa ordem: a 0016 exige um usuário, e as sementes por usuário (grupos, categorias, regras, metas de
     classe) caem nele. Se a 1ª subida cair antes do admin (banco parado na 0001/0002), a próxima retoma o bootstrap.
   - A linha `AttributeError: module 'bcrypt' has no attribute '__about__'` é um aviso conhecido do passlib e não
     é erro.
3. Apagar `ADMIN_EMAIL` e `ADMIN_PASSWORD` das variáveis da api (o redeploy sobe direto: banco no head). A api só as
   lê com o banco vazio: apagar não muda a senha, só a tira do painel.
4. Conferir:
   - `https://<web>/visao-geral/painel` sem sessão → vai para `/login`;
   - login entra e continua logado depois de recarregar a página;
   - `https://<web>/api/v1/health` → `postgres: connected`, `redis: connected`;
   - `https://<web>/docs` não chega à api (o rewrite só cobre `/api/v1`; sem sessão vai para `/login`) e a api não
     tem domínio próprio. Na própria api, `/docs` dá 404 em produção.
5. Antes do primeiro OFX: cadastrar as contas PF e MEI (o import recusa conta não cadastrada). Depois, Ajustes ›
   Atualização → "Atualizar tudo": `db_backup` e `restore_check` devem sair ok.

## 3. Deploy do dia a dia

- Deploy = **push manual do `main`**; cada serviço só reconstrói quando o seu diretório muda (Watch Paths).
- Antes do push, rode a suíte local (`/test`). Com migração nova, a subida da api faz backup e migra
  (`AUTO_MIGRATE=true`); se a migração falhar, o deploy não fica saudável e o anterior continua no ar.
- O gate `dados_reais` / `scripts.ops.migrar` depende do backup fixado em `api/tests/dados_reais/pinned_backup.txt`,
  que ainda não está nesta máquina: até o dump de casa chegar (§6), esses testes aparecem pulados.

- Variável nova ou alterada só vale no **próximo deploy**: depois de mexer em Variables, clicar Deploy (o container
  em execução continua com os valores antigos).
- Trocar a senha do admin (não há tela para isso): na api, `ADMIN_EMAIL` e `ADMIN_PASSWORD` (a nova, até 72
  caracteres por causa do bcrypt) → Deploy → `railway ssh -s api -- python -m scripts.ops.seed_admin` (imprime
  `admin seeded: <email>`; recusa variável vazia) → apagar as duas variáveis. A troca encerra as sessões abertas
  (o refresh token gravado deixa de valer): é preciso entrar de novo.

## 4. Backups

| O quê | Onde | Quando |
|---|---|---|
| `db_backup` | volume `/backups` (30 diários + 12 mensais) | 13:00 BRT e no catch-up |
| pré-migração | `/backups/pre-migracao` (nunca apagado) | toda subida que migra |
| `restore_check` | banco descartável `goodies_restore_check` | dia 1, 13:30 BRT |
| nativo do Railway | painel do Postgres | só no plano Pro |
| **cópia fora do Railway** | `$BACKUP_DIR/railway/` nesta máquina | à mão, ~1×/semana |

Cópia fora do Railway (precisa de `railway login`, `railway link` no projeto goodies, docker e uma chave SSH
registrada no Railway — uma vez por máquina: `railway ssh keys github` ou `railway ssh keys add`; sem ela o
`railway ssh` responde `No registered SSH keys found`):

```bash
scripts/backup_railway.sh          # baixa o dump diário mais novo do volume
scripts/backup_railway.sh --novo   # faz um dump na hora, baixa e o apaga do volume
```

O script baixa por `railway ssh` (em base64), confere o sha256 dos dois lados e valida com `pg_restore --list`
(postgres:15). Com `~/.config/goodies/backup.key` e o `age` instalado, guarda só o `.dump.age`.

## 5. Restaurar o banco de produção

1. api: Settings → Replicas = 0 (ou remover o deploy ativo), para nada escrever no banco.
2. Abrir um túnel sem expor o banco: `railway connect Postgres --tunnel-only` (num terminal à parte). Ele mostra a
   porta local; usuário, senha e banco estão nas variáveis do serviço Postgres (`PGUSER`, `PGPASSWORD`,
   `PGDATABASE`). Exporte o DSN no seu terminal como `DSN_TUNEL` — nunca colar no chat.
3. Restaurar com o cliente 15, sem `psql` no host (a rede `host` deixa o container alcançar o túnel local):
   ```bash
   docker run --rm -i --network host -e DSN="$DSN_TUNEL" postgres:15-alpine \
     sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges -d "$DSN"' < arquivo.dump
   ```
4. Fechar o túnel, voltar a api para 1 réplica e conferir health, login e contagens na tela.

## 6. Próxima etapa: dump curado da máquina de casa

1. Em casa: `cd api && uv run python -m scripts.ops.backup --tag para-railway`.
2. Trazer o arquivo e restaurar como na §5 (o banco de produção é substituído).
3. Conferir `alembic_version` = head (se o dump for de revisão anterior, a subida migra com backup), contagens de
   transações e operações, poupança por mês = baseline e XIRR consolidado = baseline.
4. Copiar `BACKUP_DIR/pre-migracao/<pinned_backup>` e `BACKUP_DIR/baseline/` de casa para o `BACKUP_DIR` desta
   máquina. Assim o gate `dados_reais` volta a rodar (`restore_dados_db`).

## 7. Instalação nova: o que não vem pronto

Só importa enquanto o banco for o "do zero":
- 10 categorias antigas da 0004 viram `custom:` duplicadas (a 0018 casa por nome com caixa diferente);
- a valoração CDI das caixinhas (0038) e o registro da debênture Flash (0040) não se aplicam, porque os ativos
  ainda não existem;
- os aportes fixos (Flash R$ 1.000, Ana Maria R$ 4.000) entram pela tela;
- as contas PF/MEI precisam ser cadastradas antes do 1º OFX.

O dump de casa (§6) resolve tudo isso.

## 8. Problemas conhecidos

| Sintoma | Causa | Ação |
|---|---|---|
| `/api/v1/*` no web dá 500 com `ENOTFOUND` | rewrite gravado no build com outro destino, ou `API_INTERNAL_URL` ausente no build | conferir a variável no web e **rebuild** |
| `/api/v1/*` no web dá 500 com `ECONNREFUSED 127.0.0.1:8000` | build do web sem `API_INTERNAL_URL` | definir a variável e **rebuild** |
| api não conecta pela rede privada (ambiente antigo, só IPv6) | uvicorn escutando em `0.0.0.0` | `API_HOST=::` na api |
| `db_backup` falha com erro de versão do `pg_dump` | Postgres do Railway não é 15 | §1.1 passo 2 |
| Postgres em loop: `This image runs PostgreSQL 15 but the data directory holds major version 18` | volume inicializado pelo template antes da troca de imagem | §1.1 passo 3, Wipe Volume (só sem dado; com dado, voltar para a 18) |
| api não sobe: `banco vazio: defina ADMIN_EMAIL…` | 1ª subida sem credenciais do admin | §2 |
| api não sobe: `em produção DATABASE_URL… vazia(s) ou em localhost` | referência `${{…}}` com nome de serviço errado | refazer pela lista do `${{` (§1.3) e Deploy |
| health com `redis: disconnected` logo após corrigir a variável | o container em execução é de antes da correção | Deploy da api (§3) |
| `railway ssh`: `No registered SSH keys found` | CLI ≥ 5 exige chave registrada | `railway ssh keys github` (§4) |
| "Atualizar tudo" dá 500 depois de ~30 s | rewrite com o timeout padrão do Next | `experimental.proxyTimeout` (5 min) no `next.config.ts` já cobre; se os jobs passarem disso, rebuild com valor maior |
| build do web com Node < 24 | Railpack não pegou `engines.node` | `RAILPACK_NODE_VERSION=24` no web |
