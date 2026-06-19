from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedSection:
    text: str
    page_number: int | None = None
    section_title: str | None = None
    metadata: dict | None = None


class DocumentParser:
    supported_extensions = {".pdf", ".docx", ".md", ".markdown", ".txt", ".xlsx", ".xls", ".csv"}

    def parse(self, file_path: str | Path) -> list[ParsedSection]:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._parse_pdf(path)
        if suffix == ".docx":
            return self._parse_docx(path)
        if suffix in {".md", ".markdown"}:
            return self._parse_markdown(path)
        if suffix == ".txt":
            return self._parse_text(path)
        if suffix in {".xlsx", ".xls", ".csv"}:
            from app.services.table_parser import TableParser

            return TableParser().parse(path)
        raise ValueError(f"Unsupported file type: {suffix}")

    def _parse_pdf(self, path: Path) -> list[ParsedSection]:
        import fitz

        sections: list[ParsedSection] = []
        with fitz.open(path) as doc:
            for index, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    sections.append(ParsedSection(text=text, page_number=index))
        return sections

    def _parse_docx(self, path: Path) -> list[ParsedSection]:
        from docx import Document

        doc = Document(path)
        sections: list[ParsedSection] = []
        current_title: str | None = None
        buffer: list[str] = []
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style_name = paragraph.style.name.lower() if paragraph.style else ""
            if style_name.startswith("heading"):
                if buffer:
                    sections.append(
                        ParsedSection(text="\n".join(buffer), section_title=current_title)
                    )
                    buffer = []
                current_title = text
            else:
                buffer.append(text)
        if buffer:
            sections.append(ParsedSection(text="\n".join(buffer), section_title=current_title))
        return sections

    def _parse_markdown(self, path: Path) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        current_title: str | None = None
        buffer: list[str] = []
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.rstrip()
            if line.startswith("#"):
                if buffer:
                    sections.append(
                        ParsedSection(text="\n".join(buffer).strip(), section_title=current_title)
                    )
                    buffer = []
                current_title = line.lstrip("#").strip() or None
                buffer.append(line)
            else:
                buffer.append(line)
        text = "\n".join(buffer).strip()
        if text:
            sections.append(ParsedSection(text=text, section_title=current_title))
        return sections

    def _parse_text(self, path: Path) -> list[ParsedSection]:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        return [ParsedSection(text=text)] if text else []
