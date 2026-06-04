#!/usr/bin/env python3
"""
contexto_mercado.py — Briefing diário de CONTEXTO de mercado para o Vitor
Executado pelo Hermes Agent via cron (dias úteis ~07h)

Complementa coleta_carteira.py:
  - coleta_carteira.py (18h) = camada de POSIÇÃO  → "quanto vale o que tenho?"
  - contexto_mercado.py (07h) = camada de CONTEXTO → "o que move e o que vem aí?"

Fontes (todas no plano FREE / testadas em 2026-06-04):
  - FMP   : índices US (^GSPC ^IXIC ^VIX), commodities (ouro, brent), treasury 10Y
            ⚠️ FOREX é PAGO no plano free do Vitor → USD/BRL NÃO vem do FMP
  - BCB   : SELIC meta, IPCA 12m, USD/BRL PTAX  (API SGS, grátis, sem chave)
  - CoinDesk: NEWS por categoria + nome exato dos ativos. SEM preço de cripto.

Saída:
  - ../../../01_Inbox/Economia/Contexto_Mercado_<YYYY-MM-DD>.md  (registro completo)
  - stdout → resumo de 6-8 linhas para o Discord (Hermes posta)

Chaves (em ~/.hermes/.env):
  FMP_API_KEY=...
  COINDESK_API_KEY=...

Dependências: pip install requests
"""

import os
import re
import sys
import json
import requests
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

# ─── Config (paths via env — código no Linux, vault no Windows) ───────────
# VAULT (Windows/OneDrive, via mount WSL): só LÊ posicao.json e ESCREVE a nota .md
# PORTFOLIO_HOME (Linux): logs. Nenhum dado de máquina vai pro vault.
VAULT = Path(os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/Vitor/OneDrive/Documents/Vault_Vitor"
))
HOME_DIR = Path(os.environ.get("PORTFOLIO_HOME", str(Path.home() / "hermes-portfolio")))
POSICAO_FILE = VAULT / "04_Projetos" / "Goodies" / "Utils" / "posicao.json"
OUT_DIR      = VAULT / "01_Inbox" / "Economia"

FMP_KEY      = os.environ.get("FMP_API_KEY", "")
COINDESK_KEY = os.environ.get("COINDESK_API_KEY", "")

FMP_BASE     = "https://financialmodelingprep.com/stable"
FMP_V4       = "https://financialmodelingprep.com/stable"
COINDESK_URL = "https://data-api.coindesk.com/news/v1/article/list"
BCB          = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{sid}/dados/ultimos/1?formato=json"

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
TIMEOUT = 20

# Drivers globais via FMP (símbolo → rótulo + ativo do Vitor que ele move)
FMP_DRIVERS = [
    ("^GSPC", "S&P 500",  "risco global / ACWI11"),
    ("^IXIC", "Nasdaq",   "NASD11"),
    ("^VIX",  "VIX",      "regime de medo"),
    ("GCUSD", "Ouro",     "GOLD11"),
    ("BZUSD", "Brent",    "PETR4"),
]

# BCB SGS — confirmar séries se algum valor vier estranho
BCB_SERIES = {
    "SELIC_meta": 432,    # Selic meta definida pelo Copom (% a.a.)
    "IPCA_12m":   13522,  # IPCA acumulado 12 meses (%)
    "USDBRL":     1,      # Dólar (venda) PTAX
}


# ─── Coleta FMP ──────────────────────────────────────────────────────────
def fmp_quote(symbol: str) -> dict | None:
    try:
        r = requests.get(f"{FMP_BASE}/quote",
                         params={"symbol": symbol, "apikey": FMP_KEY}, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data[0] if data else None
    except Exception as e:
        print(f"⚠️  FMP {symbol}: {e}", file=sys.stderr)
        return None


def fmp_treasury_10y() -> float | None:
    try:
        r = requests.get(f"{FMP_BASE}/treasury-rates", params={"apikey": FMP_KEY},
                         headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        latest = max(data, key=lambda d: d.get("date", ""))
        v = latest.get("year10")
        return float(v) if v is not None else None
    except Exception as e:
        print(f"⚠️  FMP treasury: {e}", file=sys.stderr)
        return None


# ─── Coleta BCB (grátis, fecha o buraco do forex/juro BR) ────────────────
def bcb(sid: int) -> float | None:
    try:
        r = requests.get(BCB.format(sid=sid), headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return float(r.json()[-1]["valor"].replace(",", "."))
    except Exception as e:
        print(f"⚠️  BCB {sid}: {e}", file=sys.stderr)
        return None


# ─── Coleta CoinDesk (NEWS, sem preço) ───────────────────────────────────
def coindesk_news(limit: int = 60) -> list:
    try:
        r = requests.get(COINDESK_URL,
                         params={"lang": "EN", "limit": limit, "api_key": COINDESK_KEY},
                         headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("Data", [])
    except Exception as e:
        print(f"⚠️  CoinDesk news: {e}", file=sys.stderr)
        return []


def _cats(a: dict) -> list:
    return [c.get("NAME", "").upper() for c in (a.get("CATEGORY_DATA") or [])]


def filtra_narrativas(arts: list, ativos_cripto: list) -> dict:
    """
    Filtro em 2 trilhos (lição do teste 2026-06-04):
      1) NARRATIVA  → pelas CATEGORIAS nativas do CoinDesk (confiável)
      2) MEUS ATIVOS → match por NOME EXATO com word-boundary (evita falso positivo)
    """
    # Validado no teste 2026-06-04. Dois sinais por ativo:
    #   NOME completo → case-INSENSITIVE (bitcoin, hyperliquid...)
    #   TICKER curto  → case-SENSITIVE maiúsculo (HYPE, SOL, ETH) p/ não casar
    #                   a palavra comum "hype"/"sol" de marketing.
    # Genéricos ('perp','yield','defi') ficam FORA — deram falso positivo.
    NOMES_CI = {
        "BTC":    ["bitcoin"],
        "ETH":    ["ethereum", "ether"],
        "SOL":    ["solana"],
        "PENDLE": ["pendle"],
        "HYPE":   ["hyperliquid"],
    }
    TICKERS_CS = {
        "BTC":    r"\bBTC\b",
        "ETH":    r"\bETH\b",
        "SOL":    r"\bSOL\b",
        "PENDLE": r"\bPENDLE\b",
        "HYPE":   r"\bHYPE\b",
    }
    NARRATIVAS = {
        "Regulação": {"REGULATION"},
        "Macro":     {"MACROECONOMICS"},
        "DeFi":      {"DEFI"},
        "L2/Infra":  {"BLOCKCHAIN"},
    }

    def hit_nome(title, kws, tk):
        if tk == "HYPE":
            # especifico: so no TITULO, exige hyperliquid ou o ticker HYPE/$HYPE
            return ("hyperliquid" in title.lower()) or bool(re.search(r"(?<![A-Za-z])\$?HYPE\b", title))
        raw = f"{title} {kws}"
        if any(n in raw.lower() for n in NOMES_CI.get(tk, [])):
            return True
        return bool(re.search(TICKERS_CS[tk], raw))

    por_ativo, por_narrativa = {}, {}
    for a in arts:
        title = a.get("TITLE", "") or ""
        kws   = a.get("KEYWORDS", "") or ""
        cats  = set(_cats(a))
        item  = {
            "title": title,
            "sent":  a.get("SENTIMENT", "NEUTRAL"),
            "ts":    a.get("PUBLISHED_ON", 0),
            "src":   a.get("SOURCE_ID", ""),
            "url":   a.get("URL", ""),
        }
        # 1) meus ativos (nome exato)
        for tk in ativos_cripto:
            if tk in TICKERS_CS and hit_nome(title, kws, tk):
                por_ativo.setdefault(tk, []).append(item)
        # 2) narrativas (categoria nativa)
        for nome, catset in NARRATIVAS.items():
            if cats & catset:
                por_narrativa.setdefault(nome, []).append(item)
    return {"ativos": por_ativo, "narrativas": por_narrativa}


# ─── Leitura de regime ───────────────────────────────────────────────────
def regime(drivers: dict, vix: float | None) -> str:
    """Heurística simples risk-on/off a partir de índices + VIX."""
    sp  = drivers.get("^GSPC", {}).get("changePercentage")
    nas = drivers.get("^IXIC", {}).get("changePercentage")
    if sp is None or nas is None or vix is None:
        return "indeterminado (dados parciais)"
    avg = (sp + nas) / 2
    if vix >= 25:
        return "RISK-OFF (VIX alto, medo)"
    if avg <= -1.0:
        return "RISK-OFF moderado (índices em queda)"
    if avg >= 1.0 and vix < 18:
        return "RISK-ON (índices sobem, VIX baixo)"
    return "NEUTRO (mercado lateral)"


# ─── Montagem do relatório ───────────────────────────────────────────────
def fmt_pct(q):
    if not q or q.get("changePercentage") is None:
        return "s/dado"
    p = q["changePercentage"]
    return f"{q.get('price', 0):,.0f} ({p:+.2f}%)"


def main():
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        pos = json.loads(POSICAO_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ contexto_mercado: não li posicao.json ({e}). Vault montado? Caminho: {POSICAO_FILE}")
        sys.exit(1)
    ativos_cripto = [a["ticker"] for a in pos["ativos"] if a.get("tipo") == "cripto"]

    # --- coleta ---
    drivers = {}
    for sym, _, _ in FMP_DRIVERS:
        q = fmp_quote(sym)
        if q:
            drivers[sym] = q
    us10y  = fmp_treasury_10y()
    selic  = bcb(BCB_SERIES["SELIC_meta"])
    ipca   = bcb(BCB_SERIES["IPCA_12m"])
    usdbrl = bcb(BCB_SERIES["USDBRL"])

    news   = coindesk_news(60)
    filt   = filtra_narrativas(news, ativos_cripto)

    vix    = drivers.get("^VIX", {}).get("price")
    reg    = regime(drivers, vix)

    # --- nota completa no vault ---
    L = []
    L.append("---")
    L.append("tipo: nota")
    L.append("area: Economia")
    L.append(f"data: {hoje}")
    L.append("fonte: contexto_mercado.py (Hermes)")
    L.append("tags: [contexto-mercado, hermes, automacao]")
    L.append("---\n")
    L.append(f"# Contexto de Mercado — {hoje}\n")
    L.append(f"**Regime:** {reg}\n")

    L.append("## Drivers globais (FMP)\n")
    L.append("| Driver | Nível | Move |")
    L.append("|---|---|---|")
    for sym, nome, move in FMP_DRIVERS:
        L.append(f"| {nome} | {fmt_pct(drivers.get(sym))} | {move} |")
    L.append(f"| US 10Y | {us10y if us10y is not None else 's/dado'}% | regime de juro global |\n")

    L.append("## Juro e câmbio Brasil (BCB) — *fecha o buraco do FMP free*\n")
    L.append(f"- **SELIC meta:** {selic if selic is not None else 's/dado'}% a.a. → custo de oportunidade dos seus 50% em RF")
    L.append(f"- **IPCA 12m:** {ipca if ipca is not None else 's/dado'}% → seu retorno real")
    L.append(f"- **USD/BRL (PTAX):** {usdbrl if usdbrl is not None else 's/dado'} → USDB11 e cripto em BRL\n")

    L.append("## Narrativas cripto (CoinDesk) — ligadas aos seus ativos\n")
    if filt["ativos"]:
        for tk, items in filt["ativos"].items():
            sent = Counter(i["sent"] for i in items)
            tom = "+" if sent.get("POSITIVE",0) > sent.get("NEGATIVE",0) else ("-" if sent.get("NEGATIVE",0) > sent.get("POSITIVE",0) else "=")
            L.append(f"### {tk}  (tom {tom} | {len(items)} notícias)")
            for i in sorted(items, key=lambda x: -x["ts"])[:4]:
                ts = datetime.fromtimestamp(i["ts"], tz=timezone.utc).strftime("%m-%d %H:%M")
                L.append(f"- [{ts}] ({i['sent']}) {i['title']}  \n  {i['url']}")
            L.append("")
    else:
        L.append("_Nenhuma notícia tocou diretamente seus ativos nas últimas horas._\n")

    L.append("## Narrativa macro/regulatória (categorias CoinDesk)\n")
    for nome, items in filt["narrativas"].items():
        if items:
            L.append(f"- **{nome}:** {len(items)} artigos. Topo: {sorted(items, key=lambda x:-x['ts'])[0]['title']}")
    L.append("")

    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"Contexto_Mercado_{hoje}.md").write_text("\n".join(L), encoding="utf-8")
    except Exception as e:
        # Vault pode estar offline; ainda assim entregamos o resumo no Discord.
        print(f"⚠️  Nota não salva no vault ({e}) — segue o resumo abaixo.", file=sys.stderr)

    # --- resumo Discord (stdout) ---
    print(f"☀️ Contexto {hoje} — 07h")
    print(f"Regime: {reg}.")
    sp = drivers.get("^GSPC", {}); nas = drivers.get("^IXIC", {})
    print(f"S&P {fmt_pct(sp)} · Nasdaq {fmt_pct(nas)} · VIX {vix if vix else 's/d'}")
    print(f"Ouro {fmt_pct(drivers.get('GCUSD'))} · Brent {fmt_pct(drivers.get('BZUSD'))} · US10Y {us10y}%")
    print(f"BR: SELIC {selic}% · IPCA12m {ipca}% · USD/BRL {usdbrl}")
    # cripto: só o que tocou seus ativos
    if filt["ativos"]:
        destaques = []
        for tk, items in filt["ativos"].items():
            sent = Counter(i["sent"] for i in items)
            tom = "↑" if sent.get("POSITIVE",0) > sent.get("NEGATIVE",0) else ("↓" if sent.get("NEGATIVE",0) > sent.get("POSITIVE",0) else "→")
            destaques.append(f"{tk}{tom}({len(items)})")
        print("Cripto (seus ativos): " + " ".join(destaques))
    else:
        print("Cripto: nada material nos seus ativos.")
    reg_n = len(filt["narrativas"].get("Regulação", []))
    if reg_n:
        print(f"⚠️ Regulação ativa hoje ({reg_n} artigos) — ver nota.")
    print(f"📄 Nota: 01_Inbox/Economia/Contexto_Mercado_{hoje}.md")


if __name__ == "__main__":
    if not FMP_KEY or not COINDESK_KEY:
        print("❌ contexto_mercado: faltam chaves FMP_API_KEY e/ou COINDESK_API_KEY no .env")
        sys.exit(1)
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # Nunca trava sem dizer nada — o 9B precisa de UMA linha clara pra postar.
        print(f"❌ contexto_mercado falhou: {e}")
        sys.exit(1)
