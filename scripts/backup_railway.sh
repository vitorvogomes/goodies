#!/usr/bin/env bash
# Cópia do backup do Railway para fora do Railway (ADR-018). Rodar à mão, ex.: 1x/semana.
#
#   scripts/backup_railway.sh           # baixa o dump diário mais novo de /backups (serviço api)
#   scripts/backup_railway.sh --novo    # faz um dump na hora (scripts.ops.backup) e baixa esse
#
# Pré-requisitos: `railway login` + `railway link` no projeto goodies; docker (valida com pg_restore 15).
# Destino: $BACKUP_DIR/railway/ (BACKUP_DIR lido do .env pelo nome). Se existir a chave age em
# ~/.config/goodies/backup.key, o arquivo fica só cifrado (.dump.age).
# Nada aqui imprime conteúdo do banco, DSN ou segredo: só nomes de arquivo, tamanhos e contagens.
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE="${RAILWAY_API_SERVICE:-api}"
AGE_KEY="${HOME}/.config/goodies/backup.key"

backup_dir="$(grep -E '^BACKUP_DIR=' "$ROOT/.env" | head -1 | cut -d= -f2-)"
[[ "$backup_dir" = /* ]] || { echo "BACKUP_DIR do .env precisa ser absoluto" >&2; exit 1; }
dest_dir="$backup_dir/railway"
mkdir -p "$dest_dir"

remote() { railway ssh -s "$SERVICE" -- sh -c "$1" 2>/dev/null | tr -d '\r'; }

if [[ "${1:-}" == "--novo" ]]; then
  echo "dump novo no Railway..."
  remote 'cd /app && python -m scripts.ops.backup --tag externo >/dev/null 2>&1 && echo ok' | grep -q '^ok$' \
    || { echo "FALHOU: backup remoto" >&2; exit 1; }
  pattern='/backups/pre-migracao/*_externo.dump'
else
  pattern='/backups/*.dump'
fi

remote_file="$(remote "ls -1t $pattern 2>/dev/null | head -1")"
[[ -n "$remote_file" ]] || { echo "FALHOU: nenhum dump em $pattern" >&2; exit 1; }
name="$(basename "$remote_file")"
local_file="$dest_dir/$name"
echo "baixando $name"

remote_sha="$(remote "sha256sum '$remote_file' | cut -d' ' -f1")"
remote "base64 '$remote_file'" | base64 -d > "$local_file.tmp"
local_sha="$(sha256sum "$local_file.tmp" | cut -d' ' -f1)"
if [[ -z "$remote_sha" || "$remote_sha" != "$local_sha" ]]; then
  rm -f "$local_file.tmp"; echo "FALHOU: sha256 não confere" >&2; exit 1
fi
mv "$local_file.tmp" "$local_file"

items="$(docker run --rm -i postgres:15-alpine pg_restore --list < "$local_file" 2>/dev/null | grep -cv '^;' || true)"
if [[ "${items:-0}" -le 0 ]]; then
  echo "FALHOU: pg_restore --list não leu o arquivo" >&2; exit 1
fi
size="$(du -h "$local_file" | cut -f1)"

if [[ -f "$AGE_KEY" ]] && command -v age >/dev/null && command -v age-keygen >/dev/null; then
  age -r "$(age-keygen -y "$AGE_KEY")" -o "$local_file.age" "$local_file" && rm -f "$local_file"
  echo "ok: $name ($size, $items itens no índice, sha256 conferido) → cifrado em $dest_dir"
else
  echo "ok: $name ($size, $items itens no índice, sha256 conferido) → $dest_dir (sem age: não cifrado)"
fi
