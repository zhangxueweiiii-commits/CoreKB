from pathlib import Path

from openpyxl import Workbook

from app.services.chunker import Chunker
from app.services.document_parser import DocumentParser


def test_csv_parser_preserves_table_metadata(tmp_path: Path) -> None:
    path = tmp_path / "products.csv"
    path.write_text("型号,额定电压,功率\nA100,220V,500W\nA200,380V,1200W\n", encoding="utf-8")

    sections = DocumentParser().parse(path)

    assert len(sections) == 1
    section = sections[0]
    assert "Sheet：CSV" in section.text
    assert "第2行：" in section.text
    assert section.metadata["source_type"] == "table"
    assert section.metadata["sheet_name"] == "CSV"
    assert section.metadata["row_start"] == 2
    assert section.metadata["row_end"] == 3
    assert section.metadata["column_names"] == ["型号", "额定电压", "功率"]


def test_table_chunks_are_not_split_and_keep_metadata(tmp_path: Path) -> None:
    path = tmp_path / "products.csv"
    path.write_text("型号,额定电压\nA100,220V\n", encoding="utf-8")
    sections = DocumentParser().parse(path)

    chunks = Chunker(chunk_size=20, chunk_overlap=5).chunk(sections)

    assert len(chunks) == 1
    assert chunks[0].metadata["source_type"] == "table"
    assert chunks[0].metadata["row_start"] == 2


def test_xlsx_parser_preserves_sheet_and_row_range(tmp_path: Path) -> None:
    path = tmp_path / "products.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "产品A"
    sheet.append(["型号", "通信协议"])
    sheet.append(["A100", "Modbus"])
    sheet.append(["A200", "EtherCAT"])
    workbook.save(path)

    sections = DocumentParser().parse(path)

    assert len(sections) == 1
    section = sections[0]
    assert "Sheet：产品A" in section.text
    assert "行范围：2-3" in section.text
    assert section.metadata["source_type"] == "table"
    assert section.metadata["sheet_name"] == "产品A"
    assert section.metadata["row_start"] == 2
    assert section.metadata["row_end"] == 3
