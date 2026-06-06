"""Wallet Engine (m4 — Broker Integration).

Saldos escaneados on-chain/exchange (QUANTIDADES) em `wallet_positions` + reconciliação
contra `asset_operations`. Separado do Market Engine (preços): aqui é quantidade, lá é
preço. A valoração em BRL reusa o preço do m3 (engines.market).
"""
