import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from charset_normalizer import from_path

from app.services.document_parser import ParsedSection


@dataclass(frozen=True)
class TableRow:
    row_number: int
    values: dict[str, str]
    raw_text: str


@dataclass(frozen=True)
class TableParseResult:
    sheet_name: str
    table_index: int
    headers: list[str]
    rows: list[TableRow]
    row_count: int
    column_count: int
    source_range: str
    metadata: dict


class TableParser:
    target_chunk_size = 1000

    def parse(self, path: Path) -> list[ParsedSection]:
        results = self._parse_tables(path)
        sections: list[ParsedSection] = []
        for table in results:
            sections.extend(self._table_to_sections(path.name, table))
        return sections

    def _parse_tables(self, path: Path) -> list[TableParseResult]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return [self._parse_csv(path)]
        if suffix in {".xlsx", ".xls"}:
            return self._parse_excel(path)
        raise ValueError(f"Unsupported table file type: {suffix}")

    def _parse_csv(self, path: Path) -> TableParseResult:
        encoding = self._detect_encoding(path)
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=encoding)
        return self._frame_to_table(frame, sheet_name="CSV", table_index=0, start_row=2)

    def _parse_excel(self, path: Path) -> list[TableParseResult]:
        try:
            sheets = pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False)
        except ImportError as exc:
            raise RuntimeError("Excel parsing requires openpyxl for .xlsx and xlrd for .xls") from exc
        tables: list[TableParseResult] = []
        for index, (sheet_name, frame) in enumerate(sheets.items()):
            if frame.empty:
                continue
            table = self._frame_to_table(frame, sheet_name=str(sheet_name), table_index=index, start_row=2)
            if table.rows:
                tables.append(table)
        return tables

    def _frame_to_table(
        self,
        frame: pd.DataFrame,
        sheet_name: str,
        table_index: int,
        start_row: int,
    ) -> TableParseResult:
        frame = frame.fillna("")
        headers = self._normalize_headers(frame.columns)
        rows: list[TableRow] = []
        for offset, row in enumerate(frame.itertuples(index=False, name=None), start=start_row):
            values = {
                header: self._clean_value(value)
                for header, value in zip(headers, row, strict=False)
            }
            raw_text = "; ".join(f"{key}: {value}" for key, value in values.items() if value)
            if raw_text:
                rows.append(TableRow(row_number=offset, values=values, raw_text=raw_text))
        row_numbers = [row.row_number for row in rows]
        source_range = f"{min(row_numbers)}-{max(row_numbers)}" if row_numbers else "0-0"
        return TableParseResult(
            sheet_name=sheet_name,
            table_index=table_index,
            headers=headers,
            rows=rows,
            row_count=len(rows),
            column_count=len(headers),
            source_range=source_range,
            metadata={"source_type": "table"},
        )

    def _table_to_sections(self, filename: str, table: TableParseResult) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        current_rows: list[TableRow] = []
        current_size = 0
        for row in table.rows:
            row_size = len(row.raw_text)
            if current_rows and current_size + row_size > self.target_chunk_size:
                sections.append(self._build_section(filename, table, current_rows))
                current_rows = []
                current_size = 0
            current_rows.append(row)
            current_size += row_size
        if current_rows:
            sections.append(self._build_section(filename, table, current_rows))
        return sections

    def _build_section(self, filename: str, table: TableParseResult, rows: list[TableRow]) -> ParsedSection:
        row_start = rows[0].row_number
        row_end = rows[-1].row_number
        lines = [
            f"File: {filename}",
            f"Sheet: {table.sheet_name}",
            f"Rows: {row_start}-{row_end}",
            "Columns: " + ", ".join(table.headers),
            "",
        ]
        for row in rows:
            lines.append(f"Row {row.row_number}:")
            for header in table.headers:
                value = row.values.get(header, "")
                if value:
                    lines.append(f"{header}: {value}")
            lines.append("")
        metadata = {
            "source_type": "table",
            "sheet_name": table.sheet_name,
            "row_start": row_start,
            "row_end": row_end,
            "column_names": table.headers,
            "table_index": table.table_index,
            "source_range": f"{row_start}-{row_end}",
        }
        return ParsedSection(
            text="\n".join(lines).strip(),
            section_title=table.sheet_name,
            metadata=metadata,
        )

    @staticmethod
    def _detect_encoding(path: Path) -> str:
        match = from_path(path).best()
        return match.encoding if match and match.encoding else "utf-8"

    @classmethod
    def _normalize_headers(cls, columns: Any) -> list[str]:
        headers: list[str] = []
        seen: dict[str, int] = {}
        for index, column in enumerate(columns, start=1):
            base = cls._clean_header(column, index)
            pandas_duplicate = re.match(r"^(.+)\.\d+$", base)
            if pandas_duplicate and pandas_duplicate.group(1) in seen:
                base = pandas_duplicate.group(1)
            count = seen.get(base, 0)
            seen[base] = count + 1
            headers.append(base if count == 0 else f"{base}_{count + 1}")
        return headers

    @staticmethod
    def _clean_header(value: Any, index: int) -> str:
        text = str(value).strip()
        if not text or text.startswith("Unnamed:"):
            return f"Column {index}"
        return text

    @staticmethod
    def _clean_value(value: Any) -> str:
        return str(value).strip()
