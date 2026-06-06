# 11 — Coerência Nubank ↔ Portfólio (pré-m3)

> Faxina de dados feita antes do m3 (Market Data) para que os indicadores (taxa de
> poupança, total investido, XIRR, alocação) reflitam a realidade. Data: 2026-06-06.

## Diagnóstico (reconciliação extrato × portfólio)

- **R$73.595** saíram do Nubank como `investment`, mas o portfólio só rastreava **R$22.627**.
- A diferença era renda fixa "invisível" (caixinhas/CDB), cripto (m4) e ~R$490 de caixa
  ocioso na corretora.
- **Receita fantasma:** resgates de caixinha voltavam como `income/Resgate` (~R$32.664),
  inflando a taxa de poupança (39,2% acumulada reportada vs ~26,3% real).

## O que foi feito

### WI-1 — Resgates de caixinha = `investment` net (não receita)
- `api/scripts/reclassify_caixinhas.py` (in-place, idempotente): move `income/Resgate` →
  `investment/Caixinha-RDB`. Aplicado: **50 resgates movidos**. Saldo acumulado invariante
  (R$3.427,97). Taxa de poupança caiu p/ o número real (ex.: jan 51,8%→28,8%; abr 32,8%→17,9%).
- `0009_caixinha_classify_patterns` (Alembic): garante os anchors de caixinha (aplicação +
  resgate) na categoria de investimento e **neutraliza** a categoria income `Resgate` p/ imports
  futuros. **NÃO rodar `reset_ledger`** depois — apagaria a curadoria manual + este conserto.

### WI-2 — Caixinhas + CDB Guanabara como ativos de Renda Fixa
- `api/engines/portfolio/rf_cdi.py`: valoração pós-fixada `principal*(1+(pct/100)*cdi_anual)^(dias/365)`.
- `api/engines/portfolio/caixinhas.py`: registro **config-driven** (`CAIXINHAS`). Snow Trip
  (100% CDI) e Turbo (115% CDI, cap R$5k) ativos; **Reserva** (100% CDI) já listada — basta
  `enabled=True` quando criada; HotCash/Extra encerradas.
- `scripts/seed_caixinhas.py` + `scripts/seed_cdb_guanabara.py`: derivam as operações datadas
  das `transactions` curadas; valoram via rf_cdi; gravam preço `is_manual` (workers m3 não
  sobrescrevem). Resultado: patrimônio **R$24.212 → R$37.187**; Renda Fixa **+20,6pp** sobre a
  meta de 50% (sinal correto de carteira RF-pesada); XIRR consolidado **16,5% → 13,8%**.
- **CDI provisório:** `settings.cdi_anual` (env `CDI_ANUAL`, default 10,65% a.a.). O m5
  substitui pela série do BCB. Re-rodar os seeds quando o CDI mudar ou `--today` avançar.
- **Caveat Turbo:** por ser conta-corrente disfarçada (R$24,8k de ida/volta, net R$776), a
  valoração por fluxo líquido superestima (~+20%). Imaterial em valor absoluto; se quiser o
  número exato, basta gravar o saldo do app como preço manual (`upsert_price`).

### WI-3 — (parcial) só os anchors de caixinha
- Os `match_patterns` conservadores (ana maria, drogaria, posto…) foram **descartados** por
  decisão do usuário ("seguir apenas com os anchors de caixinha"). Categorias mantidas como
  estavam (Transporte preserva `uber`).

### WI-4 — Caixa ocioso na Toro (~R$459) — sem ação
- Nubank `investment→Toro` = R$7.948,83 vs custo B3 no portfólio = R$7.489,52. O delta ~R$459 é
  caixa enviado à corretora ainda **não alocado** em ativos. Gap esperado; o usuário aloca nas
  próximas semanas. Não é bug.

## Decisão em aberto — "Extra" (auto-Pix do Santander)

- **91 lançamentos** em `income/Extra` (**R$32.290,01**, jun/2024→mai/2026) são Pix de
  **"VITOR COUTINHO"** vindos do **Santander** (conta própria, externa/não rastreada).
- Pela decisão vigente (Santander = externo), dinheiro que ENTRA no Nubank vindo do Santander
  conta como receita. Isso, porém, infla a taxa de poupança (não é renda "ganha", é poupança
  própria sendo movida p/ dentro do sistema rastreado).
- **Atenção à assimetria:** o casamento por "santander" no lado da DESPESA pega terceiros cujo
  banco é Santander (gastos reais, ex.: Alimentação), não a perna inversa. Logo, não há uma
  contrapartida limpa Nubank→Santander a compensar.
- **Status:** não alterado (decisão do usuário = investigar). Opções: (a) manter como receita
  externa; (b) reclassificar os 91 como `transfer` (deflaciona a poupança p/ o número
  operacional). Pendente de decisão.

## Verificação

```bash
cd api/
uv run pytest tests/ -q                 # 241 passed
uv run ruff check .                      # ok
uv run mypy main.py config.py health.py db/connection.py engines/portfolio/rf_cdi.py engines/portfolio/caixinhas.py
```
