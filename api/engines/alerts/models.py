from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from engines.common.alerts import Alert


class AlertList(BaseModel):
    items: list[Alert]
    total: int
    data_until: date | None  # transação mais recente da base: "Dados até {dd/mm/aaaa}"


class DismissalIn(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    fingerprint: str = Field(min_length=1, max_length=64)
