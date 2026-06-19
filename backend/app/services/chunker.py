from dataclasses import dataclass

from app.services.document_parser import ParsedSection


@dataclass(frozen=True)
class ChunkCandidate:
    chunk_text: str
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    metadata: dict | None = None


class Chunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, sections: list[ParsedSection]) -> list[ChunkCandidate]:
        chunks: list[ChunkCandidate] = []
        index = 0
        for section in sections:
            if section.metadata and section.metadata.get("source_type") == "table":
                text = self._normalize(section.text)
                if text:
                    chunks.append(
                        ChunkCandidate(
                            chunk_text=text,
                            chunk_index=index,
                            page_number=section.page_number,
                            section_title=section.section_title,
                            metadata=section.metadata,
                        )
                    )
                    index += 1
                continue
            normalized = self._normalize(section.text)
            if not normalized:
                continue
            start = 0
            while start < len(normalized):
                end = min(start + self.chunk_size, len(normalized))
                text = normalized[start:end].strip()
                if text:
                    chunks.append(
                        ChunkCandidate(
                            chunk_text=text,
                            chunk_index=index,
                            page_number=section.page_number,
                            section_title=section.section_title,
                            metadata={
                                "source_start": start,
                                "source_end": end,
                            },
                        )
                    )
                    index += 1
                if end >= len(normalized):
                    break
                start = max(end - self.chunk_overlap, start + 1)
        return chunks

    @staticmethod
    def _normalize(text: str) -> str:
        lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
        return "\n".join(line for line in lines if line)
