#!/usr/bin/env python3
"""
coleta_carteira.py - Snapshot diário da carteira do Vitor
Executado pelo Hermes Agent via cron job (dias úteis ~18h)

Fontes de dados:
  - B3 (ações, ETFs, FIIs) : BRAPI.dev (gratuito, sem token necessário para uso básico)
  - Cripto                 : CoinGecko API (gratuito, sem key)
  - Tesouro Direto         : API pública do TD (offlineFile)
  - RF privada / DeFi      : valor estático do posicao.json (atualização manual)

Saída:
  - snapshots/<YYYY-MM-DD>.json   → dados brutos
  - ../../01_Inbox/Economia/Portfolio_Snapshot_<data>.md  → relatório legível
  - stdout → resumo para o Discord (Hermes captura e posta)

Dependências: pip install requests
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, date
from pathlib import Path

# ─── Config (paths via env - código no Linux, vault no Windows) ─────────────
# VAULT (Windows/OneDrive, via mount WSL): LÊ posicao.json e ESCREVE o .md de snapshot.
# PORTFOLIO_HOME (Linux): snapshots brutos (.json) e logs - dado de máquina NÃO vai
# pro vault. Assim o OneDrive só recebe texto legível.
VAULT = Path(os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/Vitor/OneDrive/Documents/Vault_Vitor"
))
HOME_DIR      = Path(os.environ.get("PORTFOLIO_HOME", str(Path.home() / "hermes-portfolio")))
POSICAO_FILE  = VAULT / "04_Projetos" / "Goodies" / "Utils" / "posicao.json"
SNAPSHOTS_DIR = HOME_DIR / "snapshots"

# BRAPI: sem token funciona para uso pessoal básico (rate limit ~15 req/min)
# Para uso estável: cadastre em https://brapi.dev e adicione token em ~/.hermes/.env
# BRAPI_TOKEN=seu_token
BRAPI_TOKEN = os.environ.get("BRAPI_TOKEN", "")

BRAPI_URL    = "https://brapi.dev/api/quote"
CG_URL       = "https://api.coingecko.com/api/v3/simple/price"
TD_URL       = "https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/component/publicarea/BizContent/data.offlineFile"

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


# ─── Coleta B3 ────────────────────────────────────────────────────────────

def fetch_b3_prices(tickers: list) -> dict:
    """
    Retorna {ticker_original: {preco, variacao_dia}} via BRAPI.dev.
    Plano free do BRAPI aceita 1 ticker por requisicao -> consulta em loop.
    Acoes fracionarias tem sufixo F (BBAS3F) -> remove para consultar a API.
    """
    final = {}
    for t in tickers:
        clean = t[:-1] if (t.endswith("F") and len(t) >= 2 and t[-2].isdigit()) else t
        params = {}
        if BRAPI_TOKEN:
            params["token"] = BRAPI_TOKEN
        try:
            resp = requests.get(f"{BRAPI_URL}/{clean}", params=params,
                                headers=HEADERS, timeout=20)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as e:
            print(f"\u26a0\ufe0f  BRAPI {clean}: {e}", file=sys.stderr)
            time.sleep(0.4); continue
        if results:
            it = results[0]
            final[t] = {
                "preco":        it.get("regularMarketPrice"),
                "variacao_dia": it.get("regularMarketChangePercent", 0),
                "nome":         it.get("shortName", ""),
            }
        time.sleep(0.4)
    return final


# ─── Coleta Cripto ────────────────────────────────────────────────────────

def fetch_cripto_prices(ativos_cripto: list) -> dict:
    """
    Retorna {ticker: {preco_brl, variacao_24h}} via CoinGecko free tier.
    Usa o campo 'coingecko_id' de cada ativo no posicao.json.
    """
    # Monta mapeamento coingecko_id → ticker
    id_to_ticker = {}
    for a in ativos_cripto:
        cg_id = a.get("coingecko_id")
        if cg_id:
            id_to_ticker[cg_id] = a["ticker"]

    if not id_to_ticker:
        return {}

    params = {
        "ids":                ",".join(id_to_ticker.keys()),
        "vs_currencies":      "brl",
        "include_24hr_change": "true",
    }

    try:
        # CoinGecko free tier: 30 req/min - sem problema para uso pessoal
        resp = requests.get(CG_URL, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"⚠️  CoinGecko erro: {e}", file=sys.stderr)
        return {}

    result = {}
    for cg_id, info in data.items():
        ticker = id_to_ticker.get(cg_id, cg_id.upper())
        result[ticker] = {
            "preco_brl":    info.get("brl"),
            "variacao_24h": info.get("brl_24h_change"),
        }
    return result


# ─── Coleta Tesouro Direto ────────────────────────────────────────────────

def fetch_td_prices() -> dict:
    """
    {nome_titulo: {preco_venda, vencimento}} via tesourodireto.com.br com headers
    de navegador. Se falhar, apenas avisa e retorna {} -> o script usa
    valor_atual_base. Sem download pesado.
    """
    hdr = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.tesourodireto.com.br/titulos/precos-e-taxas.htm",
        "Origin": "https://www.tesourodireto.com.br",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    try:
        resp = requests.get(TD_URL, headers=hdr, timeout=25)
        resp.raise_for_status()
        out = {}
        for bond in resp.json()["response"]["TrsrBdTradgList"]:
            b = bond.get("TrsrBd", {})
            nm = b.get("nm", "")
            if nm:
                out[nm] = {"preco_venda": b.get("untrRedVal"), "vencimento": b.get("mtrtyDt", "")}
        return out
    except Exception as e:
        print(f"\u26a0\ufe0f  Tesouro nao coletado nesta varredura ({e}) - usando valor_atual_base", file=sys.stderr)
        return {}


# ─── Calcula posição ──────────────────────────────────────────────────────

def calcular_portfolio(posicao: dict, b3_prices: dict, cripto_prices: dict, td_prices: dict) -> dict:
    resultado = {
        "data":           datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_aplicado": 0.0,
        "total_atual":    0.0,
        "categorias":     {},
        "ativos":         [],
        "alertas":        [],
    }

    cat_alvo = posicao.get("categorias_alvo_pct", {})

    for a in posicao.get("ativos", []):
        ticker   = a["ticker"]
        tipo     = a["tipo"]
        cat      = a["categoria"]
        custo    = a.get("custo_total", 0.0)

        preco_atual   = None
        variacao_dia  = None
        valor_atual   = a.get("valor_atual_base", custo)  # fallback
        fonte         = "base"

        # - B3 -
        if tipo in ("acao", "etf", "fii"):
            info = b3_prices.get(ticker, {})
            preco_atual = info.get("preco")
            variacao_dia = info.get("variacao_dia")
            if preco_atual:
                valor_atual = preco_atual * a["quantidade"]
                fonte = "brapi"

        # - Cripto -
        elif tipo == "cripto":
            info = cripto_prices.get(ticker, {})
            preco_atual  = info.get("preco_brl")
            variacao_dia = info.get("variacao_24h")
            if preco_atual:
                valor_atual = preco_atual * a["quantidade"]
                fonte = "coingecko"

        # - Tesouro Direto -
        elif tipo == "tesouro":
            td_nome = a.get("td_nome_api", "")
            # Tenta match exato, depois parcial
            td_info = td_prices.get(td_nome)
            if not td_info:
                for nome_api, info in td_prices.items():
                    if td_nome.lower() in nome_api.lower() or nome_api.lower() in td_nome.lower():
                        td_info = info
                        break
            if td_info and td_info.get("preco_venda") and a.get("fracoes"):
                preco_atual  = td_info["preco_venda"]
                valor_atual  = preco_atual * a["fracoes"]
                fonte = "tesouro_direto"

        # - RF privada, DeFi, stablecoin → valor estático -
        else:
            if tipo == "stablecoin_brl":
                valor_atual = a.get("quantidade_brl", custo)
            elif tipo == "defi_manual":
                valor_atual = a.get("quantidade_brl", custo)
            fonte = "manual"

        rendimento     = valor_atual - custo
        rendimento_pct = (rendimento / custo * 100) if custo > 0 else 0.0

        resultado["total_aplicado"] += custo
        resultado["total_atual"]    += valor_atual

        resultado["ativos"].append({
            "ticker":        ticker,
            "nome":          a.get("nome", ticker),
            "categoria":     cat,
            "tipo":          tipo,
            "quantidade":    a.get("quantidade") or a.get("fracoes") or a.get("quantidade_brl"),
            "custo_total":   round(custo, 2),
            "valor_atual":   round(valor_atual, 2),
            "rendimento":    round(rendimento, 2),
            "rendimento_pct":round(rendimento_pct, 2),
            "preco_atual":   round(preco_atual, 4) if preco_atual else None,
            "variacao_dia":  round(variacao_dia, 2) if variacao_dia is not None else None,
            "fonte":         fonte,
        })

    # - Totais por categoria -
    for atv in resultado["ativos"]:
        cat = atv["categoria"]
        if cat not in resultado["categorias"]:
            resultado["categorias"][cat] = {"valor_atual": 0.0, "custo_total": 0.0}
        resultado["categorias"][cat]["valor_atual"] += atv["valor_atual"]
        resultado["categorias"][cat]["custo_total"] += atv["custo_total"]

    total = resultado["total_atual"]

    # - Alertas de desvio de alocação -
    for cat, alvo_pct in cat_alvo.items():
        vals = resultado["categorias"].get(cat, {})
        atual_pct = (vals.get("valor_atual", 0) / total * 100) if total > 0 else 0
        desvio = atual_pct - alvo_pct
        if abs(desvio) >= 2.0:  # alerta se desvio ≥ 2 pontos percentuais
            resultado["alertas"].append({
                "categoria": cat,
                "alvo_pct":  alvo_pct,
                "atual_pct": round(atual_pct, 1),
                "desvio":    round(desvio, 1),
            })

    resultado["total_aplicado"]     = round(resultado["total_aplicado"], 2)
    resultado["total_atual"]        = round(resultado["total_atual"], 2)
    resultado["total_rendimento"]   = round(resultado["total_atual"] - resultado["total_aplicado"], 2)
    resultado["total_rendimento_pct"] = round(
        (resultado["total_rendimento"] / resultado["total_aplicado"] * 100)
        if resultado["total_aplicado"] > 0 else 0, 2
    )

    return resultado


# ─── Relatório Markdown ───────────────────────────────────────────────────

def gerar_relatorio_md(r: dict) -> str:
    s   = "+" if r["total_rendimento"] >= 0 else ""
    now = r["data"]

    linhas = [
        "---",
        "tipo: snapshot_portfolio",
        f"data: {now}",
        "tags: [portfolio, snapshot, economia]",
        "---",
        "",
        f"# Portfolio Snapshot - {now}",
        "",
        f"| | |",
        f"|---|---|",
        f"| **Total aplicado** | R$ {r['total_aplicado']:,.2f} |",
        f"| **Valor atual**    | R$ {r['total_atual']:,.2f} |",
        f"| **Rendimento**     | {s}R$ {r['total_rendimento']:,.2f} ({s}{r['total_rendimento_pct']:.2f}%) |",
        "",
        "## Alocação por Categoria",
        "",
        "| Categoria | Valor Atual | % Carteira | Rend R$ | Rend % |",
        "|---|---|---|---|---|",
    ]

    total = r["total_atual"]
    for cat, vals in r["categorias"].items():
        va   = vals["valor_atual"]
        ct   = vals["custo_total"]
        rend = va - ct
        pct  = (va / total * 100) if total > 0 else 0
        rs   = "+" if rend >= 0 else ""
        linhas.append(
            f"| {cat} | R$ {va:,.2f} | {pct:.1f}% | {rs}R$ {rend:,.2f} | {rs}{(rend/ct*100):.1f}% |"
        )

    if r["alertas"]:
        linhas += ["", "## ⚠️ Alertas de Alocação", ""]
        for alerta in r["alertas"]:
            sinal = "acima" if alerta["desvio"] > 0 else "abaixo"
            linhas.append(
                f"- **{alerta['categoria']}**: {alerta['atual_pct']}% atual vs {alerta['alvo_pct']}% alvo "
                f"({abs(alerta['desvio']):.1f}pp {sinal})"
            )

    # Tabela por categoria
    for cat in r["categorias"]:
        ativos_cat = [a for a in r["ativos"] if a["categoria"] == cat]
        linhas += ["", f"## {cat}", "", "| Ativo | Qtd | Valor Atual | Rend R$ | Rend % | Var Dia |", "|---|---|---|---|---|---|"]
        for a in ativos_cat:
            rs = "+" if a["rendimento"] >= 0 else ""
            vd = f"{a['variacao_dia']:+.2f}%" if a["variacao_dia"] is not None else "-"
            qtd = f"{a['quantidade']:.4f}" if isinstance(a["quantidade"], float) and a["quantidade"] < 1 else str(a["quantidade"])
            linhas.append(
                f"| {a['ticker']} | {qtd} | R$ {a['valor_atual']:,.2f} | "
                f"{rs}R$ {a['rendimento']:,.2f} | {rs}{a['rendimento_pct']:.2f}% | {vd} |"
            )

    linhas += ["", "---", f"*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*"]
    return "\n".join(linhas)


# ─── Resumo Discord ───────────────────────────────────────────────────────

def gerar_resumo_discord(r: dict) -> str:
    s    = "+" if r["total_rendimento"] >= 0 else ""
    icon = "📈" if r["total_rendimento"] >= 0 else "📉"
    now  = r["data"]

    linhas = [
        f"**{icon} Portfolio - {now}**",
        f"Valor atual: **R$ {r['total_atual']:,.2f}** | {s}R$ {r['total_rendimento']:,.2f} ({s}{r['total_rendimento_pct']:.2f}%)",
        "",
    ]

    # Alocação
    total = r["total_atual"]
    linhas.append("**Alocação:**")
    for cat, vals in r["categorias"].items():
        pct = (vals["valor_atual"] / total * 100) if total > 0 else 0
        linhas.append(f"  `{cat:<15}` R$ {vals['valor_atual']:>9,.2f} ({pct:.1f}%)")

    # Alertas
    if r["alertas"]:
        linhas.append("")
        linhas.append("**⚠️ Rebalancear:**")
        for alerta in r["alertas"]:
            sinal = "↑" if alerta["desvio"] > 0 else "↓"
            linhas.append(
                f"  {sinal} {alerta['categoria']}: {alerta['atual_pct']}% (alvo {alerta['alvo_pct']}%)"
            )

    # Top movers (apenas ativos com variacao_dia da API)
    movers = [a for a in r["ativos"] if a["variacao_dia"] is not None]
    if movers:
        movers_sorted = sorted(movers, key=lambda x: x["variacao_dia"], reverse=True)
        linhas.append("")
        linhas.append("**Destaques do dia:**")
        for a in movers_sorted[:3]:
            e = "🟢" if a["variacao_dia"] >= 0 else "🔴"
            linhas.append(f"  {e} {a['ticker']}: {a['variacao_dia']:+.2f}%")
        if len(movers_sorted) > 3 and movers_sorted[-1]["variacao_dia"] < movers_sorted[2]["variacao_dia"]:
            worst = movers_sorted[-1]
            linhas.append(f"  🔴 {worst['ticker']}: {worst['variacao_dia']:+.2f}% ← pior")

    return "\n".join(linhas)


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    print("📂 Carregando posição...", file=sys.stderr)
    try:
        with open(POSICAO_FILE, encoding="utf-8") as f:
            posicao = json.load(f)
    except Exception as e:
        print(f"❌ coleta_carteira: não li posicao.json ({e}). Vault montado? Caminho: {POSICAO_FILE}")
        sys.exit(1)

    ativos_b3     = [a for a in posicao["ativos"] if a["tipo"] in ("acao", "etf", "fii")]
    ativos_cripto = [a for a in posicao["ativos"] if a["tipo"] == "cripto"]

    print(f"🏦 Buscando {len(ativos_b3)} ativos B3...", file=sys.stderr)
    b3_prices = fetch_b3_prices([a["ticker"] for a in ativos_b3])
    time.sleep(1)  # respeita rate limit

    print(f"🪙  Buscando {len(ativos_cripto)} cripto...", file=sys.stderr)
    cripto_prices = fetch_cripto_prices(ativos_cripto)
    time.sleep(1)

    print("📜 Buscando Tesouro Direto...", file=sys.stderr)
    td_prices = fetch_td_prices()

    print("🧮 Calculando portfolio...", file=sys.stderr)
    resultado = calcular_portfolio(posicao, b3_prices, cripto_prices, td_prices)

    # Salva snapshot JSON bruto no LINUX (não polui o vault)
    try:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snap_file = SNAPSHOTS_DIR / f"{date.today().isoformat()}.json"
        with open(snap_file, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        print(f"💾 Snapshot: {snap_file}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️  Snapshot bruto nao salvo ({e}) - segue mesmo assim.", file=sys.stderr)

    # Salva relatorio Markdown no VAULT (texto legivel)
    try:
        notas_dir = VAULT / "01_Inbox" / "Economia"
        notas_dir.mkdir(parents=True, exist_ok=True)
        md_file = notas_dir / f"Portfolio_Snapshot_{date.today().isoformat()}.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(gerar_relatorio_md(resultado))
        print(f"📝 Relatorio: {md_file}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️  Relatorio nao salvo no vault ({e}) - segue o resumo abaixo.", file=sys.stderr)

    # Resumo para o Discord (stdout - Hermes captura e posta)
    print("\n" + gerar_resumo_discord(resultado))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ coleta_carteira falhou: {e}")
        sys.exit(1)
