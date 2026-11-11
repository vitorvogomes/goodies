#!/usr/bin/env bash
# Restaura um dump de casa no Postgres de produção, mantendo o login de produção (ADR-018, runbook §5/§6).
#
#   DSN_ALVO=... scripts/restore_railway.sh arquivo.dump
#
# DSN_ALVO: DSN do Postgres alvo (túnel ou proxy TCP temporário). Lido só da env, nunca impresso.
# Antes, a api tem de estar parada (`railway down --service api --yes`; `railway scale ...=0` não para):
# o script recusa seguir se houver outra conexão no banco alvo.
#
# Etapas (qualquer falha para o script com o alvo como estava):
#   1. ensaio: restaura o dump num Postgres 15 descartável local e tira a impressão digital de cada tabela;
#   2. confere o alvo: mesma revisão do Alembic, 1 usuário e nenhuma transação (banco recém-criado);
#   3. backup do alvo em $BACKUP_DIR/railway/pre-restore_<data>.dump;
#   4. guarda e-mail + hash da senha do admin do alvo num esquema à parte (restore_keep);
#   5. pg_restore --single-transaction --clean: entra tudo ou nada;
#   6. põe o e-mail e a senha guardados no usuário restaurado, zera a sessão e apaga o restore_keep;
#   7. confere contagem e md5 de cada tabela do alvo contra o ensaio.
# Nada aqui imprime DSN, senha, hash ou conteúdo do banco: só nomes de tabela, contagens e ok/DIFERE.
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMG="postgres:15-alpine"
REF="goodies-restore-ensaio-$$"
# Mesma renderização de texto nos dois servidores (o md5 compara o texto das linhas).
export PGOPTIONS="-c TimeZone=UTC -c DateStyle=ISO,MDY -c IntervalStyle=postgres -c extra_float_digits=1"

die() { echo "FALHOU: $*" >&2; exit 1; }

dump="${1:-}"
[[ -n "$dump" && -f "$dump" ]] || die "uso: DSN_ALVO=... $0 arquivo.dump"
[[ -n "${DSN_ALVO:-}" ]] || die "defina DSN_ALVO (não cole o valor no chat)"
dump="$(cd "$(dirname "$dump")" && pwd)/$(basename "$dump")"

backup_dir="${RESTORE_BACKUP_DIR:-$(grep -E '^BACKUP_DIR=' "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)}"
[[ "$backup_dir" = /* ]] || die "BACKUP_DIR do .env precisa ser absoluto"
mkdir -p "$backup_dir/railway"

# psql no alvo: SQL pela entrada padrão, DSN só pela env do container.
alvo() { docker run --rm -i --network host -e DSN_ALVO -e PGOPTIONS "$IMG" \
  sh -c 'psql "$DSN_ALVO" -X -q -At -F "|" -v ON_ERROR_STOP=1' 2>/dev/null; }
ensaio() { docker exec -i -e PGOPTIONS "$REF" psql -h 127.0.0.1 -U postgres -d ensaio -X -q -At -F "|" -v ON_ERROR_STOP=1 2>/dev/null; }

cleanup() { docker rm -f "$REF" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# Uma linha "tabela|linhas|md5" por tabela. Em users só id e created_at: e-mail e senha são os de produção.
FINGERPRINT_SQL=$(cat <<'SQL'
SELECT string_agg(format(
  'SELECT %L, count(*), md5(coalesce(string_agg(%s::text, E''\n'' ORDER BY %s::text COLLATE "C"), '''')) FROM public.%I x',
  table_name,
  CASE WHEN table_name = 'users' THEN '(x.id, x.created_at)' ELSE 'x' END,
  CASE WHEN table_name = 'users' THEN '(x.id, x.created_at)' ELSE 'x' END,
  table_name), ' UNION ALL ' ORDER BY table_name)
FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' \gset
:string_agg
SQL
)

# ---- 1. ensaio local
echo "1/7 ensaio: restaurando $(basename "$dump") num Postgres 15 descartável..."
docker run -d --rm --name "$REF" -e POSTGRES_PASSWORD="ensaio-$$" -e POSTGRES_HOST_AUTH_METHOD=trust "$IMG" >/dev/null
# O init da imagem sobe um servidor temporário só no socket unix e reinicia: por TCP (127.0.0.1) só o
# servidor definitivo responde.
criado=false
for _ in $(seq 1 60); do
  if docker exec "$REF" createdb -h 127.0.0.1 -U postgres ensaio 2>/dev/null; then criado=true; break; fi
  sleep 1
done
$criado || die "ensaio: createdb"
docker exec -i "$REF" pg_restore -h 127.0.0.1 -U postgres -d ensaio --single-transaction --exit-on-error \
  --no-owner --no-privileges < "$dump" >/dev/null 2>&1 || die "o dump não restaura nem no ensaio local"
ref_rev="$(echo 'SELECT version_num FROM alembic_version' | ensaio)" || die "ensaio: alembic_version"
ref_users="$(echo 'SELECT count(*) FROM users' | ensaio)" || die "ensaio: users"
ref_fp="$(echo "$FINGERPRINT_SQL" | ensaio | sort)" || die "ensaio: impressão digital"
[[ "$ref_users" == 1 ]] || die "o dump tem $ref_users usuários (esperado 1)"
echo "    dump na revisão $ref_rev, $(wc -l <<< "$ref_fp") tabelas"

# ---- 2. alvo
echo "2/7 conferindo o alvo..."
estado="$(echo "SELECT (SELECT version_num FROM alembic_version), (SELECT count(*) FROM users),
  (SELECT count(*) FROM transactions), (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()
   AND pid <> pg_backend_pid() AND backend_type = 'client backend')" | alvo)" \
  || die "não conectou no alvo (proxy aberto? DSN_ALVO certo?)"
IFS='|' read -r alvo_rev alvo_users alvo_tx alvo_conns <<< "$estado"
[[ "$alvo_conns" == 0 ]] || die "há $alvo_conns outra(s) conexão(ões) no alvo: pare a api (railway down) antes"
[[ "$alvo_rev" == "$ref_rev" ]] || die "alvo na revisão $alvo_rev, dump na $ref_rev"
[[ "$alvo_users" == 1 ]] || die "alvo tem $alvo_users usuários (esperado só o admin de produção)"
[[ "$alvo_tx" == 0 ]] || die "alvo já tem $alvo_tx transações: não é o banco vazio do bootstrap"
echo "    alvo na revisão $alvo_rev, 1 usuário, 0 transações"

# ---- 3. backup do alvo
dest="$backup_dir/railway/pre-restore_$(date -u +%Y%m%d_%H%M%S).dump"
echo "3/7 backup do alvo..."
docker run --rm -i --network host -e DSN_ALVO "$IMG" sh -c 'pg_dump -Fc "$DSN_ALVO"' \
  > "$dest.tmp" 2>/dev/null || { rm -f "$dest.tmp"; die "pg_dump do alvo"; }
items="$(docker run --rm -i "$IMG" pg_restore --list < "$dest.tmp" 2>/dev/null | grep -cv '^;' || true)"
[[ "${items:-0}" -gt 0 ]] || { rm -f "$dest.tmp"; die "backup do alvo ilegível"; }
mv "$dest.tmp" "$dest"
echo "    $(basename "$dest") ($items itens)"

# ---- 4. guarda o login de produção
echo "4/7 guardando o login de produção..."
drop_keep() { echo 'DROP SCHEMA IF EXISTS restore_keep CASCADE;' | alvo >/dev/null || true; }
# Até o pg_restore confirmar, o alvo segue como estava: na falha, o restore_keep sai junto.
trap 'drop_keep; cleanup' EXIT
alvo >/dev/null <<'SQL' || die "não guardou o login"
DROP SCHEMA IF EXISTS restore_keep CASCADE;
CREATE SCHEMA restore_keep;
CREATE TABLE restore_keep.admin AS SELECT email, password_hash FROM public.users;
SQL

# ---- 5. restauração
echo "5/7 restaurando (uma transação só)..."
log="$backup_dir/railway/restore_$(date -u +%Y%m%d_%H%M%S).log"
if ! docker run --rm -i --network host -e DSN_ALVO "$IMG" sh -c \
  'pg_restore --single-transaction --exit-on-error --clean --if-exists --no-owner --no-privileges -d "$DSN_ALVO"' \
  < "$dump" > "$log" 2>&1; then
  die "pg_restore falhou ($(wc -l < "$log") linhas em $log); o alvo ficou como estava"
fi
# Daqui em diante o alvo tem os dados de casa: o restore_keep (login de produção) não pode mais sumir.
trap cleanup EXIT
rm -f "$log"

# ---- 6. login de produção no usuário restaurado
echo "6/7 aplicando o login de produção..."
ok="$(alvo <<'SQL'
BEGIN;
UPDATE public.users u SET email = k.email, password_hash = k.password_hash, refresh_token_hash = NULL
  FROM restore_keep.admin k;
DO $$ BEGIN
  IF (SELECT count(*) FROM public.users) <> 1 OR (SELECT count(*) FROM public.users u
      JOIN restore_keep.admin k USING (email, password_hash) WHERE u.refresh_token_hash IS NULL) <> 1 THEN
    RAISE EXCEPTION 'login de produção não conferiu';
  END IF;
END $$;
DROP SCHEMA restore_keep CASCADE;
COMMIT;
SELECT 1;
SQL
)" || die "não aplicou o login (o login de produção fica em restore_keep e no backup)"
[[ "$ok" == 1 ]] || die "login de produção não conferiu"

# ---- 7. conferência
echo "7/7 conferindo tabela a tabela..."
alvo_fp="$(echo "$FINGERPRINT_SQL" | alvo | sort)" || die "impressão digital do alvo"
difere="$(diff <(echo "$ref_fp") <(echo "$alvo_fp") | grep -E '^[<>]' | cut -c3- | cut -d'|' -f1 | sort -u || true)"
total="$(wc -l <<< "$ref_fp")"
if [[ -n "$difere" ]]; then
  echo "DIFERE:"; sed 's/^/    /' <<< "$difere"
  die "o alvo não ficou igual ao dump (backup em $dest)"
fi
resumo="$(echo "SELECT (SELECT version_num FROM alembic_version), (SELECT count(*) FROM transactions),
  (SELECT count(DISTINCT month) FROM month_closes)" | alvo)" || die "restaurado e conferido, mas o resumo falhou"
IFS='|' read -r rev tx meses <<< "$resumo"
echo "ok: $total/$total tabelas iguais ao dump; revisão $rev; $tx transações; $meses meses com fechamento;"
echo "    login de produção mantido, sessões zeradas; backup do alvo em $dest"
