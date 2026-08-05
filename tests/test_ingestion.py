"""Tests for cohort-scoped knowledge-base ingestion.

The suite uses in-memory fakes, so it verifies chunking, hashing, file loading,
and update-not-duplicate behavior without a live database or embedding API.
"""

import json
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
from app.kb.schema import (
    IngestionStats,
    KnowledgeChunk,
    RawMaterial,
    SourceMetadata,
    SourceType,
    compute_content_hash,
)
from app.kb.store import KBStore, chunk_document


class FakeEmbedder:
    """Return deterministic vectors and record embedded texts."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return [[float(len(text)), 1.0, 0.0] for text in texts]


class InMemoryChunkRepository:
    """Minimal in-memory replacement for the pgvector repository."""

    def __init__(self) -> None:
        self.by_source: dict[str, list[KnowledgeChunk]] = {}

    def get_source_hash(self, source_id: str) -> str | None:
        chunks = self.by_source.get(source_id, [])
        return chunks[0].content_hash if chunks else None

    def replace_source(
        self,
        source_id: str,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
    ) -> None:
        assert len(chunks) == len(embeddings)
        self.by_source[source_id] = list(chunks)

    def list_sources(self) -> list[dict[str, Any]]:
        return [
            {
                "source_id": source_id,
                "cohort": chunks[0].metadata.cohort,
                "title": chunks[0].metadata.title,
                "chunk_count": len(chunks),
            }
            for source_id, chunks in self.by_source.items()
            if chunks
        ]

    def retire_source(self, source_id: str) -> bool:
        return self.by_source.pop(source_id, None) is not None

    def all_chunks(self) -> list[KnowledgeChunk]:
        return [chunk for chunks in self.by_source.values() for chunk in chunks]


def _material(
    content: str,
    *,
    cohort: str = "2026-summer",
    source: str = "faqs/general.md",
    source_type: SourceType = SourceType.FAQ,
) -> RawMaterial:
    metadata = SourceMetadata(
        title="General FAQ",
        source=source,
        type=source_type,
        cohort=cohort,
    )
    return RawMaterial(metadata=metadata, content=content)


def _make_store() -> tuple[KBStore, InMemoryChunkRepository, FakeEmbedder]:
    repository = InMemoryChunkRepository()
    embedder = FakeEmbedder()
    store = KBStore(repository=repository, embedder=embedder)
    return store, repository, embedder


def test_ingest_writes_chunks_with_required_metadata() -> None:
    store, repository, _ = _make_store()

    stats = ingest_materials(
        [_material("What are the office hours?\n\nMonday to Friday, 9 to 5.")],
        store=store,
    )

    assert stats == IngestionStats(
        sources_seen=1,
        sources_ingested=1,
        sources_skipped=0,
        chunks_written=1,
    )
    chunk = repository.all_chunks()[0]
    assert chunk.source_id == "2026-summer::faqs/general.md"
    assert chunk.metadata.title == "General FAQ"
    assert chunk.metadata.source == "faqs/general.md"
    assert chunk.metadata.type is SourceType.FAQ
    assert chunk.metadata.cohort == "2026-summer"


def test_reingest_identical_content_is_idempotent() -> None:
    store, repository, embedder = _make_store()
    material = _material("Deadlines are posted every Monday.")

    first = ingest_materials([material], store=store)
    first_chunks = list(repository.all_chunks())
    first_embed_count = len(embedder.texts)
    second = ingest_materials([material], store=store)

    assert first.sources_ingested == 1
    assert second.sources_skipped == 1
    assert second.sources_ingested == 0
    assert second.chunks_written == 0
    assert repository.all_chunks() == first_chunks
    assert len(embedder.texts) == first_embed_count


def test_changed_content_replaces_old_chunks() -> None:
    store, repository, _ = _make_store()

    ingest_materials([_material("Version one.")], store=store)
    stats = ingest_materials([_material("Version two is the updated answer.")], store=store)

    stored_text = " ".join(chunk.content for chunk in repository.all_chunks())
    assert stats.sources_ingested == 1
    assert "Version two" in stored_text
    assert "Version one" not in stored_text
    assert len(repository.by_source) == 1


def test_same_source_path_is_isolated_by_cohort() -> None:
    store, repository, _ = _make_store()
    source = "schedules/current.md"

    ingest_materials(
        [
            _material("Cohort A session is Monday.", cohort="cohort-a", source=source),
            _material("Cohort B session is Tuesday.", cohort="cohort-b", source=source),
        ],
        store=store,
    )

    assert set(repository.by_source) == {
        "cohort-a::schedules/current.md",
        "cohort-b::schedules/current.md",
    }
    assert {chunk.metadata.cohort for chunk in repository.all_chunks()} == {"cohort-a", "cohort-b"}


def test_chunking_is_deterministic_and_sequential() -> None:
    material = _material("A" * 220)

    first = chunk_document(material, max_chars=100, overlap=20)
    second = chunk_document(material, max_chars=100, overlap=20)

    assert first == second
    assert [chunk.chunk_index for chunk in first] == [0, 1, 2]
    assert all(chunk.content_hash == material.content_hash for chunk in first)
    assert first[0].content[-20:] == first[1].content[:20]


@pytest.mark.parametrize(
    ("max_chars", "overlap"),
    [(0, 0), (100, -1), (100, 100), (100, 101)],
)
def test_chunking_rejects_invalid_limits(max_chars: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_document(_material("Valid content"), max_chars=max_chars, overlap=overlap)


def test_content_hash_ignores_cosmetic_whitespace() -> None:
    assert compute_content_hash("hello\r\nworld  ") == compute_content_hash("hello\nworld")


def test_blank_document_content_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _material("   \n\n   ")


def test_ingest_file_loads_and_persists_local_material(tmp_path: Path) -> None:
    store, repository, _ = _make_store()
    file_path = tmp_path / "onboarding-guide.md"
    file_path.write_text("Install Python and clone the repository.", encoding="utf-8")

    stats = ingest_file(
        file_path,
        cohort="cohort-x",
        source_type=SourceType.ONBOARDING,
        source="onboarding/guide.md",
        store=store,
    )

    chunk = repository.all_chunks()[0]
    assert stats.sources_ingested == 1
    assert chunk.metadata.title == "Onboarding Guide"
    assert chunk.metadata.source == "onboarding/guide.md"
    assert chunk.metadata.type is SourceType.ONBOARDING
    assert chunk.metadata.cohort == "cohort-x"


def test_ingest_sources_resolves_paths_from_base_directory(tmp_path: Path) -> None:
    store, repository, _ = _make_store()
    (tmp_path / "faq.md").write_text("The support channel is listed in the portal.", encoding="utf-8")
    (tmp_path / "schedule.md").write_text("The next session is Thursday.", encoding="utf-8")
    sources = [
        SourceMetadata(title="FAQ", source="faq.md", type=SourceType.FAQ, cohort="cohort-x"),
        SourceMetadata(title="Schedule", source="schedule.md", type=SourceType.SCHEDULE, cohort="cohort-x"),
    ]

    stats = ingest_sources(sources, base_dir=tmp_path, store=store)

    assert stats.sources_seen == 2
    assert stats.sources_ingested == 2
    assert len(repository.by_source) == 2


def test_material_from_file_preserves_custom_source_id(tmp_path: Path) -> None:
    file_path = tmp_path / "program.md"
    file_path.write_text("Approved program rules.", encoding="utf-8")

    material = material_from_file(
        file_path,
        cohort="cohort-y",
        source_type="program_doc",
        title="Program Rules",
        source="program/rules.md",
    )

    assert material.source_id == "cohort-y::program/rules.md"
    assert material.metadata.type is SourceType.PROGRAM_DOC
    assert material.content == "Approved program rules."


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