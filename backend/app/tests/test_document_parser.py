from pathlib import Path

from app.services.document_parser import DocumentParser


def test_parse_markdown_preserves_headings(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("# 总则\n第一条\n## 细则\n第二条", encoding="utf-8")

    sections = DocumentParser().parse(path)

    assert len(sections) == 2
    assert sections[0].section_title == "总则"
    assert "# 总则" in sections[0].text
    assert sections[1].section_title == "细则"


def test_parse_text_reads_plain_text(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("内部知识库", encoding="utf-8")

    sections = DocumentParser().parse(path)

    assert len(sections) == 1
    assert sections[0].text == "内部知识库"
