---
tipo: epico
projeto: Goodies
epico: EPIC-06
milestone: m6-observability
titulo: Observabilidade — Logs, Erros e Alertas de Sistema
status: pendente
tags: [goodies, epic, observability, sentry, logs]
---

# EPIC-06 — Observabilidade

**Milestone:** m6-observability  
**Objetivo:** Sistema confiável com logs estruturados, error tracking e notificações de falha de workers. Falha silenciosa é inaceitável em dados financeiros.  
**Gate de saída:** Falha de worker notifica no Discord (via Hermes) em < 5min. Exceptions não tratadas capturadas no Sentry.

---

## Escopo

### Inclui:
- Logs estruturados com `structlog`: cada fetch de API externa, cada cálculo XIRR, cada alerta disparado
- Campos obrigatórios nos logs: `timestamp`, `level`, `event`, `worker`, `ticker` (quando aplicável), `duration_ms`
- Sentry SDK integrado ao FastAPI: exceptions não tratadas + performance monitoring
- Instrumentação de workers: log de início, fim e duração de cada ciclo
- Alertas de sistema para o Discord:
  - Worker falhou > 2 ciclos consecutivos
  - API externa inacessível > 2h
  - XIRR calculation error
- Rate limiting: slowapi middleware (100 req/min geral, 10 req/min para writes)
- Health check endpoint expandido: `GET /api/v1/health/detailed` → status de cada integração (Redis, Postgres, últimas chamadas de API externas)
- Dashboard de saúde da API (simples, texto)

### Não inclui:
- Métricas customizadas em Prometheus/Grafana (overkill para single-user)
- APM completo (Datadog) — fora do orçamento

---

## Stories

- STORY-06-01: Configurar structlog (formato JSON em produção, colorido em dev)
- STORY-06-02: Instrumentar todos os fetchers de API externa com logs de duração
- STORY-06-03: Instrumentar workers (início, fim, duração, resultado)
- STORY-06-04: Integrar Sentry SDK (exceptions + performance)
- STORY-06-05: Alertas de sistema para Discord via webhook (worker falhou, API down)
- STORY-06-06: Rate limiting com slowapi
- STORY-06-07: Health check detalhado (Redis, Postgres, APIs externas)
- STORY-06-08: Testes: simular falha de Redis, falha de API — verificar comportamento de fallback e log correto

---

## Dependências
EPIC-01 a EPIC-05 concluídos (há o que instrumentar).

## Bloqueados por este épico
EPIC-07 (frontend final pressupõe sistema estável)
