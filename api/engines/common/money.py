"""Dinheiro e percentual na fronteira HTTP (AD-4 — Story 2.1).

- `Money` / `Pct`: `Decimal` no Python, quantizados a 2 casas com `ROUND_HALF_EVEN` na validação;
  no JSON saem como number. Aceitam `Decimal`, `int` e `str`; `float` é recusado (AD-4).
- Percentual já vem em % (55,48), nunca fração; taxas internas (0,5548) só viram `Pct` na fronteira.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema

CENT = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def to_usd(value: Decimal | None, fx: Decimal | None) -> Decimal | None:
    """R$ → US$ pela cotação do dólar (R$ por US$), a 2 casas; sem valor ou sem cotação → None.
    Cripto mostra R$ e US$ em todo lugar (v2.2): a conta fica na API (AD-4)."""
    if value is None or fx is None or fx <= 0:
        return None
    return quantize_money(value / fx)


def _to_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("dinheiro/percentual não aceita float: use Decimal, int ou str")
    if isinstance(value, Decimal):
        return quantize_money(value)
    if isinstance(value, int | str):
        try:
            return quantize_money(Decimal(str(value).strip()))
        except InvalidOperation as exc:
            raise ValueError(f"número inválido: {value!r}") from exc
    raise ValueError(f"tipo não suportado para dinheiro: {type(value).__name__}")


# Serializa como number JSON: o valor já está quantizado a 2 casas, então o float de saída é a
# representação exata desse decimal (nenhuma conta acontece depois disto).
_as_number = PlainSerializer(float, return_type=float, when_used="json")
_schema = WithJsonSchema({"type": "number", "multipleOf": 0.01})

Money = Annotated[Decimal, BeforeValidator(_to_decimal), _as_number, _schema]
Pct = Annotated[Decimal, BeforeValidator(_to_decimal), _as_number, _schema]
