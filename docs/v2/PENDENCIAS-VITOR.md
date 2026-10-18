# Pendências para o Vitor — v2.0

Coisas que precisam de você. A implementação dos épicos segue sem parar; resolvemos esta lista no final.
Cada item diz o que é, por que ficou para você e o que eu recomendo.

| # | Desde | Pendência | Por que é sua | Recomendação |
|---|---|---|---|---|
| P1 | Épico 1 (1.6) | Fazer login de novo no app | A api passou a usar os segredos JWT reais do `.env`; as sessões antigas foram assinadas com os segredos de desenvolvimento | Só entrar de novo |
| P2 | Import 2026-10-18 (ADR-016) | Revisar as 212 transações importadas de jun a 16/10/2026 | Ninguém revisou: 128 têm categoria sugerida pelo histórico, ~52 vieram por regra e 20 estão "a classificar" (2 delas em junho: uma entrada de R$ 164,12 e uma saída de R$ 60,92) | Revisar pela Revisão de transações do Épico 3; até lá elas contam com a categoria proposta (`pending`) |
| P3 | ADR-016 | Confirmar o novo gate de dados | Os 55,48% da planilha não são reproduzíveis pela base (jun/2026 = 56,87% na fórmula v2, com as 2 transações a classificar) | Aceitar o invariante "poupança de cada mês = lista fixada", já em vigor |
| P4 | Story 2.6 | Conferir os deltas da taxa de poupança v2 | A fórmula v2 abate devoluções dos gastos e não conta "entrada a classificar" como trabalho; mudam os meses com Reembolso/Repasse ou a classificar (ex.: fev/2025 65,77% → 68,61%) | Aceitar — é a regra do PRD (FR-20); a lista completa está em `BACKUP_DIR/baseline/savings_v2_*.json` |
| P5 | Story 2.6 | 5 "pagamento de fatura" em Dívidas depois de nov/2025 | O party mode decidiu só sobre as 18 de 2024–nov/2025 | Dizer se elas também vão para "Cartão de crédito" |
| P6 | Import B3 | Liquidação D+2 duplicada no import da movimentação | Descartei 7 operações de 09/06/2026 que repetiam os negócios de 05/06 já importados pela negociação | Nada a fazer se concordar. Desde a Story 3.8 o adapter B3 casa a liquidação com os negócios do dia (inclusive somados) e pula sozinho; reimportar os arquivos reais deu 0 novas |
| P7 | Infra | Desativar os projetos antigos de Fly, Supabase e Upstash | São contas suas fora do repositório | Desativar quando puder |
