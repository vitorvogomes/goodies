"""Carrega um workbook B3 (.xlsx) de bytes e detecta o tipo de arquivo.

Eleva o loader que vivia em `scripts/import_b3.py` a um serviço reutilizável pelo
endpoint de import. Usa `data_only=True` **sem** `read_only`: o modo read-only confia
na tag de dimensão do .xlsx, que a B3 emite quebrada (some linhas — visto ao vivo); o
modo normal lê a planilha inteira corretamente. Arquivos da B3 são pequenos, então
carregar tudo em memória é barato.
"""
from __future__ import annotations

import io
import zipfile
from collections.abc import Mapping
from typing import Any, Literal

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

B3FileType = Literal["consolidado", "movimentacao", "negociacao"]


def load_workbook_sheets(data: bytes) -> dict[str, list[tuple[Any, ...]]]:
    """Bytes de um .xlsx -> {nome da aba: linhas (tuplas, incluindo cabeçalho)}.

    Levanta ValueError se os bytes não forem um .xlsx válido — o endpoint mapeia
    isso para HTTP 422 (nunca 5xx, fail-soft).
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"arquivo B3 inválido: {exc}") from exc
    return {name: list(wb[name].iter_rows(values_only=True)) for name in wb.sheetnames}


def detect_file_type(sheets: Mapping[str, Any]) -> B3FileType:
    """Detecta o tipo do relatório B3 pela presença de abas-marcadoras.

    - consolidado: tem abas 'Posição - *' (mensal/anual; trades em 'Negociações',
      proventos em 'Proventos Recebidos').
    - movimentacao: aba 'Movimentação' (extrato mensal/anual).
    - negociacao: aba 'Negociação' (extrato diário/semanal, trade a trade).
    """
    names = set(sheets)
    if any(n.startswith("Posição") for n in names):
        return "consolidado"
    if "Movimentação" in names:
        return "movimentacao"
    if "Negociação" in names:
        return "negociacao"
    raise ValueError(f"tipo de arquivo B3 não reconhecido (abas={sorted(names)})")
