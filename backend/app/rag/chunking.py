"""Cleaning and chunking.

Chunks are ~800 tokens with ~120 tokens of overlap (the README's "AI / RAG design" explains why).
Chunking is per page so every chunk keeps an exact page number for citations.
"""

import re
import uuid
from dataclasses import dataclass
from functools import lru_cache

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.extraction import ExtractionError, Page

CHUNK_SIZE_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 120
# The tokenizer used by text-embedding-3-small, so token counts match what the model sees.
ENCODING_NAME = "cl100k_base"

# Any whitespace except a newline (spaces, tabs, non-breaking spaces).
_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class Chunk:
    id: uuid.UUID
    index: int
    page: int | None
    text: str
    token_count: int


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [_HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in text.split("\n")]
    return _EXTRA_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def chunk_id(document_id: uuid.UUID, index: int) -> uuid.UUID:
    """Deterministic, so re-processing a document overwrites its Qdrant points."""
    return uuid.uuid5(document_id, str(index))


@lru_cache
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


@lru_cache
def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=ENCODING_NAME,
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
    )


def chunk_pages(pages: list[Page], document_id: uuid.UUID) -> list[Chunk]:
    """Clean each page, drop empty ones, and split into overlapping token-sized chunks."""
    chunks: list[Chunk] = []
    for page in pages:
        text = clean_text(page.text)
        if not text:
            continue
        for piece in _splitter().split_text(text):
            index = len(chunks)
            chunks.append(
                Chunk(
                    id=chunk_id(document_id, index),
                    index=index,
                    page=page.number,
                    text=piece,
                    token_count=len(_encoding().encode(piece)),
                )
            )
    if not chunks:
        raise ExtractionError("No extractable text was found (a PDF may be a scanned image).")
    return chunks
