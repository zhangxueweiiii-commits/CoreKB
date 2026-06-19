from app.services.chunker import Chunker
from app.services.document_parser import ParsedSection


def test_chunker_keeps_metadata_and_overlap() -> None:
    text = "一" * 1000
    chunker = Chunker(chunk_size=300, chunk_overlap=50)

    chunks = chunker.chunk([ParsedSection(text=text, page_number=3, section_title="制度")])

    assert len(chunks) == 4
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 3
    assert chunks[0].section_title == "制度"
    assert chunks[1].chunk_text.startswith("一" * 10)
    assert chunks[1].metadata == {"source_start": 250, "source_end": 550}


def test_chunker_ignores_empty_sections() -> None:
    chunks = Chunker(chunk_size=10, chunk_overlap=2).chunk([ParsedSection(text="\n\n")])

    assert chunks == []
