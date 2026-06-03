---
description: Verifica se o milestone atual passou no gate de qualidade. Uso: /gate m0
---

Verifique o gate do milestone $ARGUMENTS:

**m0 — Foundation:**
```bash
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
# Esperado: {"status": "ok", "postgres": "connected", "redis": "connected"}
```

**m1 — Ledger:**
```bash
# Verificar taxa de poupança de junho/2026
curl -s "http://localhost:8000/api/v1/cashflow/summary?month=2026-06" | python3 -m json.tool
# savings_rate deve ser ~55.5% (±0.1% vs planilha)
```

**m2 — Portfolio (CRÍTICO):**
```bash
python3 scripts/validate_xirr.py
# XIRR Python deve coincidir com Excel XIRR (diferença < 0.1 pp)
```

**m3 — Market:**
```bash
# Verificar que workers rodaram sem erro nas últimas 48h
tail -50 .claude/session.log
grep -c "ERROR" api/logs/app.log 2>/dev/null || echo "0 erros"
```

**m4 — Broker:**
```bash
curl -s http://localhost:8000/api/v1/market/wallets | python3 -m json.tool
# Todas as wallets devem ter scanned_at com menos de 4h
```

**m5 — Analytics:**
```bash
curl -s http://localhost:8000/api/v1/alerts | python3 -m json.tool
# Deve ter pelo menos 1 alerta ativo (concentração Flash)
curl -s http://localhost:8000/api/v1/analytics/benchmarks | python3 -m json.tool
# CDI, IPCA, IBOV devem estar presentes
```

Reporte: **PASS** ou **FAIL** com evidência.
