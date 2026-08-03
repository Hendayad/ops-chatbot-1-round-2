"""Validated schemas for cohort-scoped knowledge-base ingestion.

The models in this module describe approved Operations materials before and
after chunking. Persistence remains the responsibility of ``app.kb.ingest``;
these schemas deliberately contain no database connection or SQL logic.
"""

from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    """Supported categories of approved Operations material."""

    FAQ = "faq"
    ONBOARDING = "onboarding"
    SCHEDULE = "schedule"
    PROGRAM_DOC = "program_doc"


def normalize_content(text: str) -> str:
    """Normalize line endings and trailing whitespace for stable ingestion."""
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in unified.split("\n")).strip()


def compute_content_hash(text: str) -> str:
    """Return a stable SHA-256 hash for normalized document content."""
    normalized = normalize_content(text)
    return sha256(normalized.encode("utf-8")).hexdigest()


class SchemaModel(BaseModel):
    """Common strict validation settings for knowledge-base schemas."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class SourceMetadata(SchemaModel):
    """Provenance attached to every document and generated chunk."""

    title: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=1000)
    type: SourceType
    cohort: str = Field(min_length=1, max_length=100)


class KnowledgeDocument(SchemaModel):
    """One approved source document before chunking and embedding."""

    metadata: SourceMetadata
    content: str = Field(min_length=1)

    @property
    def source_id(self) -> str:
        """Return a stable identity scoped to the owning cohort."""
        return f"{self.metadata.cohort}::{self.metadata.source}"

    @property
    def content_hash(self) -> str:
        """Return the idempotency hash used during re-ingestion."""
        return compute_content_hash(self.content)


class KnowledgeChunk(SchemaModel):
    """A document chunk ready for embedding and database persistence."""

    metadata: SourceMetadata
    source_id: str = Field(min_length=1, max_length=1200)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1)

    @property
    def chunk_id(self) -> str:
        """Return a deterministic identifier for this exact source chunk."""
        return f"{self.source_id}#chunk-{self.chunk_index}"


class IngestionStats(SchemaModel):
    """Counters returned after one knowledge-base ingestion run."""

    sources_seen: int = Field(default=0, ge=0)
    sources_ingested: int = Field(default=0, ge=0)
    sources_skipped: int = Field(default=0, ge=0)
    chunks_written: int = Field(default=0, ge=0)


# Compatibility name for loaders or existing code that calls source documents
# "raw materials" before they are chunked.
RawMaterial = KnowledgeDocument


__all__ = [
    "IngestionStats",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "RawMaterial",
    "SourceMetadata",
    "SourceType",
    "compute_content_hash",
    "normalize_content",
]