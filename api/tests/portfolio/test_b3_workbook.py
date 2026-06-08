"""Loader + detecção de tipo do workbook B3 (A2). xlsx construído em memória."""
from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from engines.portfolio.b3_workbook import detect_file_type, load_workbook_sheets


def _xlsx(sheets: dict[str, list[tuple]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)  # tira a "Sheet" default
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestLoadWorkbookSheets:
    def test_round_trip_bytes_to_sheets(self) -> None:
        data = _xlsx(
            {
                "Movimentação": [
                    ("Entrada/Saída", "Data"),
                    ("Credito", "20/05/2026"),
                ]
            }
        )
        sheets = load_workbook_sheets(data)
        assert "Movimentação" in sheets
        assert sheets["Movimentação"][0] == ("Entrada/Saída", "Data")
        assert sheets["Movimentação"][1][0] == "Credito"

    def test_invalid_bytes_raise_valueerror(self) -> None:
        with pytest.raises(ValueError):
            load_workbook_sheets(b"definitely not an xlsx file")

    def test_empty_bytes_raise_valueerror(self) -> None:
        with pytest.raises(ValueError):
            load_workbook_sheets(b"")


class TestDetectFileType:
    def test_movimentacao(self) -> None:
        assert detect_file_type({"Movimentação": []}) == "movimentacao"

    def test_negociacao(self) -> None:
        assert detect_file_type({"Negociação": []}) == "negociacao"

    def test_consolidado_by_posicao_tabs(self) -> None:
        sheets = {
            "Posição - Ações": [],
            "Posição - Tesouro Direto": [],
            "Negociações": [],
            "Proventos Recebidos": [],
        }
        assert detect_file_type(sheets) == "consolidado"

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            detect_file_type({"Planilha1": []})
