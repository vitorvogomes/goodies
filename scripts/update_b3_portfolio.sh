#!/usr/bin/env bash
# Atualiza a carteira B3 + Tesouro + Flash no banco LOCAL de dev (idempotente).
#
# Fluxo manual (até o m4 automatizar o Portal do Investidor):
#   1. Baixe do Portal B3:
#        - Extrato -> Movimentação (período novo OU histórico completo) -> XLSX
#          salve em  files/b3/extrato/
#        - Relatório Consolidado (mensal) -> XLSX   (p/ preços de fechamento atuais)
#          salve em  files/b3/<ano>/
#   2. Se houver novos aportes de debênture Flash, edite
#        files/debentures-flash/integralizacoes.json
#   3. Rode este script:  bash scripts/update_b3_portfolio.sh
#
# O import é idempotente: reexportar o histórico inteiro não duplica nada
# (external_id = hash(data, ticker, tipo, total)). Alvo = primeiro usuário do banco.

set -euo pipefail
cd "$(dirname "$0")/../api"

export DATABASE_URL="${DATABASE_URL:-postgresql://goodies:goodies@localhost:5432/goodies}"
ROOT="$(cd .. && pwd)"
EXTRATO_DIR="$ROOT/files/b3/extrato"

# Relatório consolidado MENSAL p/ preços. Default = o mês cronologicamente mais
# recente (parseia o nome do mês — nomes não ordenam alfabeticamente). Pode ser
# passado como 1º argumento:  bash scripts/update_b3_portfolio.sh /caminho/rel.xlsx
_month_num() {
  case "$1" in
    janeiro) echo 01;; fevereiro) echo 02;; marco|março) echo 03;; abril) echo 04;;
    maio) echo 05;; junho) echo 06;; julho) echo 07;; agosto) echo 08;;
    setembro) echo 09;; outubro) echo 10;; novembro) echo 11;; dezembro) echo 12;;
    *) echo 00;;
  esac
}
_latest_snapshot() {
  local f base yr mo
  for f in "$ROOT"/files/b3/*/relatorio-consolidado-mensal-*.xlsx; do
    [ -e "$f" ] || continue
    base="$(basename "$f" .xlsx)"; yr="${base%-*}"; yr="${yr##*-}"; mo="${base##*-}"
    printf '%s%s\t%s\n' "$yr" "$(_month_num "$mo")" "$f"
  done | sort | tail -1 | cut -f2
}
SNAPSHOT="${1:-$(_latest_snapshot)}"

echo "==> Banco: $DATABASE_URL"
echo "==> Movimentações em: $EXTRATO_DIR"
echo "==> Snapshot de preços: ${SNAPSHOT:-<nenhum>}"
echo

# 1) Metas (idempotente)
uv run python ../scripts/seed_portfolio_targets.py

# 2) Operações B3 + preços do snapshot
SNAP_ARG=()
[ -n "${SNAPSHOT:-}" ] && SNAP_ARG=(--snapshot "$SNAPSHOT")
uv run python ../scripts/import_b3.py "$EXTRATO_DIR"/*.xlsx "${SNAP_ARG[@]}" --commit

# 3) Debêntures Flash (revaloriza a hoje)
uv run python ../scripts/seed_debentures_flash.py --commit

echo
echo "==> Pronto. Carteira atualizada no banco local."
