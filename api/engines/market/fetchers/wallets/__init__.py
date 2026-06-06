"""Fetchers de saldo de wallet/exchange (m4 — Broker Integration).

Cada fetcher (Etherscan/Solscan/Liquid/Binance) implementa `BalanceFetcher` e devolve
saldos (QUANTIDADES) por ativo — o preço vem do Market Engine (m3). Fail-soft: chain/
exchange fora → lista vazia, nunca levanta. Liquid usa client DEDICADO (ADR-005).
"""
