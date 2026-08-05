"""Tests for knowledge base ingestion.

These tests exercise the ingestion *logic* — hashing, chunking, update-not-
duplicate replacement, and metadata preservation — without a live database or a
real embedding API. Persistence and embedding are replaced by in-memory fakes
injected through the same protocols the production wiring uses, so the suite is
fast and deterministic and runs anywhere ``make check`` runs.
"""

import gc
import json
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from app.cohorts.config import CohortConfigLoader
from app.cohorts.scope import scope_by_cohort
from app.kb.ingest import (
    ingest_file,
    ingest_materials,
    ingest_sources,
    material_from_file,
)
from app.ingestion.loader import load_materials
from app.kb.store import (
    KBStore,
    chunk_document,
)
from app.kb.schema import (
    IngestionStats,
    KnowledgeChunk,
    RawMaterial,
    SourceMetadata,
    SourceType,
    compute_content_hash,
)


class FakeEmbedder:
    """Deterministic embedder that records how many texts it embedded."""

    def __init__(self) -> None:
        """Initialize the call counter."""
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a fixed-width deterministic vector per text and count them."""
        self.calls += len(texts)
        return [[float(len(text)), 1.0, 0.0] for text in texts]


class InMemoryChunkRepository:
    """In-memory stand-in for the pgvector repository.

    Stores, per source id, the content hash and the chunk rows that were last
    written. ``replace_source`` mirrors the atomic delete-then-insert contract
    of the real repository.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self.by_source: dict[str, tuple[str, list[KnowledgeChunk]]] = {}

    def get_source_hash(self, source_id: str) -> str | None:
        """Return the stored hash for a source, or ``None``."""
        entry = self.by_source.get(source_id)
        return entry[0] if entry is not None else None

    def replace_source(
        self,
        source_id: str,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Replace all stored chunks for a source."""
        assert len(chunks) == len(embeddings)
        content_hash = chunks[0].content_hash if chunks else ""
        self.by_source[source_id] = (content_hash, chunks)

    def list_sources(self) -> list[dict[str, Any]]:
        """Return one row per stored source, mirroring the real repository's shape."""
        return [
            {
                "source_id": source_id,
                "content_hash": content_hash,
                "last_ingested_at": None,
                "chunk_count": len(chunks),
            }
            for source_id, (content_hash, chunks) in self.by_source.items()
        ]

    def retire_source(self, source_id: str) -> bool:
        """Delete a source's stored chunks; return whether it existed."""
        return self.by_source.pop(source_id, None) is not None

    def all_chunks(self) -> list[KnowledgeChunk]:
        """Return every stored chunk across all sources."""
        result: list[KnowledgeChunk] = []
        for _, chunks in self.by_source.values():
            result.extend(chunks)
        return result


def _material(
    content: str,
    *,
    cohort: str = "2026-summer",
    source: str = "faqs/general.md",
    source_type: SourceType = SourceType.FAQ,
) -> RawMaterial:
    """Build a :class:`RawMaterial` for tests."""
    metadata = SourceMetadata(
        title="General FAQ",
        source=source,
        type=source_type,
        cohort=cohort,
    )
    return RawMaterial(metadata=metadata, content=content)


def _make_store() -> tuple[KBStore, InMemoryChunkRepository, FakeEmbedder]:
    """Build a store wired with in-memory fakes."""
    repository = InMemoryChunkRepository()
    embedder = FakeEmbedder()
    return KBStore(repository=repository, embedder=embedder), repository, embedder


def test_ingest_writes_chunks_with_required_metadata() -> None:
    """Every stored chunk carries title, source, type, and cohort."""
    store, repository, _ = _make_store()

    stats = store.ingest([_material("What are the office hours?\n\nMon-Fri, 9-5.")])

    assert stats.sources_ingested == 1
    assert stats.chunks_written >= 1
    chunks = repository.all_chunks()
    assert chunks
    for chunk in chunks:
        assert chunk.metadata.title == "General FAQ"
        assert chunk.metadata.source == "faqs/general.md"
        assert chunk.metadata.type is SourceType.FAQ
        assert chunk.metadata.cohort == "2026-summer"


def test_reingest_identical_is_idempotent() -> None:
    """Re-ingesting unchanged content writes nothing and skips embedding."""
    store, repository, embedder = _make_store()
    material = _material("Deadlines are posted every Monday.\n\nCheck the portal.")

    first = store.ingest([material])
    chunks_after_first = len(repository.all_chunks())
    embed_calls_after_first = embedder.calls

    second = store.ingest([material])

    assert first.sources_ingested == 1
    assert second.sources_skipped == 1
    assert second.sources_ingested == 0
    # No duplication: chunk count is unchanged on the second run.
    assert len(repository.all_chunks()) == chunks_after_first
    # No wasted embedding work on an unchanged source.
    assert embedder.calls == embed_calls_after_first


def test_reingest_changed_content_replaces_not_duplicates() -> None:
    """Changed content replaces the old chunks rather than adding to them."""
    store, repository, _ = _make_store()
    source = "faqs/general.md"

    store.ingest([_material("Version one of the answer.", source=source)])
    first_chunks = repository.all_chunks()
    assert all("Version one" in chunk.content for chunk in first_chunks)

    stats = store.ingest([_material("Version two is completely different.", source=source)])

    assert stats.sources_ingested == 1
    stored = repository.all_chunks()
    # Old content is gone; only the new version remains for this source.
    assert all("Version two" in chunk.content for chunk in stored)
    assert not any("Version one" in chunk.content for chunk in stored)


def test_cohorts_do_not_leak() -> None:
    """The same source in two cohorts is stored independently."""
    store, repository, _ = _make_store()
    source = "faqs/general.md"

    store.ingest([_material("Cohort A schedule.", cohort="cohort-a", source=source)])
    store.ingest([_material("Cohort B schedule.", cohort="cohort-b", source=source)])

    cohorts = {chunk.metadata.cohort for chunk in repository.all_chunks()}
    assert cohorts == {"cohort-a", "cohort-b"}
    assert len(repository.by_source) == 2


def test_content_hash_is_stable_under_cosmetic_whitespace() -> None:
    """Trailing whitespace and CRLF do not change the idempotency key."""
    assert compute_content_hash("hello\r\nworld  ") == compute_content_hash("hello\nworld")


def test_chunk_indices_are_sequential() -> None:
    """Chunk indices start at zero and increase without gaps."""
    long_body = "\n\n".join(f"Paragraph number {i} with some filler text." for i in range(50))
    chunks = chunk_document(_material(long_body), max_chars=120, overlap=20)

    assert len(chunks) > 1
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_empty_material_is_rejected() -> None:
    """Whitespace-only content is rejected during schema validation."""
    with pytest.raises(ValidationError):
        _material("   \n\n   ")


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Yield a private temporary directory and remove it afterwards.

    Uses tempfile rather than pytest's tmp_path fixture because this Windows
    environment denies access to pytest's own temporary root.
    """
    path = Path(tempfile.mkdtemp())
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_loader_reads_directory_tree(temp_dir: Path) -> None:
    """The loader tags materials by directory and stamps the cohort."""
    (temp_dir / "faqs").mkdir()
    (temp_dir / "onboarding").mkdir()
    (temp_dir / "faqs" / "general.md").write_text("# General\n\nWelcome to the program.", encoding="utf-8")
    (temp_dir / "onboarding" / "day1.md").write_text("# Day One\n\nSet up your laptop.", encoding="utf-8")

    materials: list[RawMaterial] = []
    try:
        materials = load_materials(temp_dir, cohort="cohort-x")

        assert len(materials) == 2
        types = {material.metadata.type for material in materials}
        assert types == {SourceType.FAQ, SourceType.ONBOARDING}
        assert all(material.metadata.cohort == "cohort-x" for material in materials)
    finally:
        if materials:
            del materials
        gc.collect()


def test_loader_renders_faq_json(temp_dir: Path) -> None:
    """FAQ JSON is rendered into readable question/answer text."""
    (temp_dir / "faqs").mkdir()
    (temp_dir / "faqs" / "faq.json").write_text(
        '[{"question": "When do sessions start?", "answer": "At 10 AM."}]',
        encoding="utf-8",
    )

    materials: list[RawMaterial] = []
    try:
        materials = load_materials(temp_dir, cohort="cohort-x")

        assert len(materials) == 1
        assert "When do sessions start?" in materials[0].content
        assert "At 10 AM." in materials[0].content
    finally:
        if materials:
            del materials
        gc.collect()


def test_empty_batch_returns_zero_stats_without_using_store() -> None:
    assert ingest_materials([]) == IngestionStats()


def test_missing_source_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Knowledge source not found"):
        material_from_file(
            tmp_path / "missing.md",
            cohort="cohort-x",
            source_type=SourceType.FAQ,
        )


def test_store_can_list_and_retire_materials() -> None:
    store, repository, _ = _make_store()
    material = _material("A stored FAQ.")
    ingest_materials([material], store=store)

    listed = store.list_materials()
    retired = store.retire_material(material.source_id)

    assert listed[0]["source_id"] == material.source_id
    assert retired is True
    assert repository.all_chunks() == []
    assert store.retire_material(material.source_id) is False


def _write_cohort_config(
    tmp_path: Path,
    *,
    include_invalid_entry: bool = False,
) -> Path:
    """Create a small two-cohort configuration used by isolation tests."""
    config: dict[str, Any] = {
        " COHORT-A ": {
            "name": "Cohort A",
            "materials_root": str(tmp_path / "materials" / "cohort-a"),
        },
        "cohort-b": {
            "name": "Cohort B",
            "materials_root": str(tmp_path / "materials" / "cohort-b"),
        },
    }
    if include_invalid_entry:
        config["broken-cohort"] = {
            "name": "",
            "materials_root": "",
        }

    config_path = tmp_path / "cohorts_config.json"
    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )
    return config_path


def test_cohort_config_normalizes_ids_and_loads_material_roots(
    tmp_path: Path,
) -> None:
    """Configured cohort IDs are canonical and expose their material roots."""
    config_path = _write_cohort_config(tmp_path)
    loader = CohortConfigLoader(str(config_path))

    assert loader.list_cohorts() == ["cohort-a", "cohort-b"]
    assert loader.is_known_cohort("  COHORT-A  ") is True
    assert loader.is_known_cohort("cohort-x") is False

    cohort_a = loader.load_cohort_config("COHORT-A")

    assert cohort_a["cohort_id"] == "cohort-a"
    assert cohort_a["name"] == "Cohort A"
    assert Path(cohort_a["materials_root"]) == (
        tmp_path / "materials" / "cohort-a"
    )
    assert cohort_a["enabled"] is True
    assert cohort_a["materials"] == []


def test_invalid_and_unknown_cohort_config_fails_closed(tmp_path: Path) -> None:
    """Invalid entries are ignored and unknown cohorts return no material root."""
    config_path = _write_cohort_config(
        tmp_path,
        include_invalid_entry=True,
    )
    loader = CohortConfigLoader(str(config_path))

    assert "broken-cohort" not in loader.list_cohorts()
    assert loader.is_known_cohort(None) is False
    assert loader.is_known_cohort("") is False
    unknown = loader.load_cohort_config("cohort-x")

    assert unknown["cohort_id"] == "cohort-x"
    assert unknown["name"] == ""
    assert unknown["materials_root"] == ""
    assert unknown["enabled"] is False
    assert unknown["materials"] == []


def test_configured_material_roots_drive_isolated_ingestion(
    tmp_path: Path,
) -> None:
    """Each configured root ingests the same filename under its own cohort."""
    materials_root = tmp_path / "materials"
    cohort_a_root = materials_root / "cohort-a"
    cohort_b_root = materials_root / "cohort-b"
    cohort_a_root.mkdir(parents=True)
    cohort_b_root.mkdir(parents=True)

    (cohort_a_root / "schedule.md").write_text(
        "Cohort A deadline is August 15.",
        encoding="utf-8",
    )
    (cohort_b_root / "schedule.md").write_text(
        "Cohort B deadline is August 22.",
        encoding="utf-8",
    )

    loader = CohortConfigLoader(str(_write_cohort_config(tmp_path)))
    store, repository, _ = _make_store()

    for cohort_id in loader.list_cohorts():
        cohort = loader.load_cohort_config(cohort_id)
        source = SourceMetadata(
            title=f"{cohort['name']} Schedule",
            source="schedule.md",
            type=SourceType.SCHEDULE,
            cohort=cohort_id,
        )
        stats = ingest_sources(
            [source],
            base_dir=Path(cohort["materials_root"]),
            store=store,
        )
        assert stats.sources_ingested == 1

    assert set(repository.by_source) == {
        "cohort-a::schedule.md",
        "cohort-b::schedule.md",
    }

    content_by_cohort = {
        chunk.metadata.cohort: chunk.content
        for chunk in repository.all_chunks()
    }
    assert "August 15" in content_by_cohort["cohort-a"]
    assert "August 22" in content_by_cohort["cohort-b"]


def test_ingested_records_can_be_scoped_without_cross_cohort_leakage() -> None:
    """The shared scoping hook returns records from only one cohort."""
    store, repository, _ = _make_store()
    ingest_materials(
        [
            _material(
                "Cohort A deadline is August 15.",
                cohort="cohort-a",
                source="schedule.md",
                source_type=SourceType.SCHEDULE,
            ),
            _material(
                "Cohort B deadline is August 22.",
                cohort="cohort-b",
                source="schedule.md",
                source_type=SourceType.SCHEDULE,
            ),
        ],
        store=store,
    )

    records = [
        {
            "source_id": chunk.source_id,
            "cohort": chunk.metadata.cohort,
            "content": chunk.content,
        }
        for chunk in repository.all_chunks()
    ]

    cohort_a_records = scope_by_cohort(records, "  COHORT-A  ")
    cohort_b_records = scope_by_cohort(records, "cohort-b")

    assert len(cohort_a_records) == 1
    assert cohort_a_records[0]["cohort"] == "cohort-a"
    assert "August 15" in cohort_a_records[0]["content"]

    assert len(cohort_b_records) == 1
    assert cohort_b_records[0]["cohort"] == "cohort-b"
    assert "August 22" in cohort_b_records[0]["content"]


@pytest.mark.parametrize("missing_cohort", [None, "", "   "])
def test_scoping_hook_fails_closed_without_cohort(
    missing_cohort: str | None,
) -> None:
    """A missing cohort never exposes unscoped ingestion records."""
    records = [
        {"cohort": "cohort-a", "content": "A"},
        {"cohort": "cohort-b", "content": "B"},
    ]

    assert scope_by_cohort(records, missing_cohort) == []