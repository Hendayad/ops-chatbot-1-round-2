"""High-level ingestion entry points for approved Operations materials.

This module loads validated source files and delegates chunking, embedding, and
update-not-duplicate persistence to :class:`app.kb.store.KBStore`. Keeping file
loading here and storage logic in ``store.py`` avoids duplicating the ingestion
rules while still providing a small public API for scripts, tests, and future
cohort configuration.
"""

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from app.kb.schema import (
    IngestionStats,
    RawMaterial,
    SourceMetadata,
    SourceType,
)
from app.kb.store import KBStore, build_default_store


@lru_cache(maxsize=1)
def get_default_store() -> KBStore:
    """Return the lazily created process-wide production knowledge-base store."""
    return build_default_store()


def _read_text_file(path: Path, *, encoding: str) -> str:
    """Read one local source file with clear path validation errors."""
    if not path.exists():
        raise FileNotFoundError(f"Knowledge source not found: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"Knowledge source is not a file: {path}")
    return path.read_text(encoding=encoding)


def load_material(
    metadata: SourceMetadata,
    *,
    base_dir: str | Path | None = None,
    encoding: str = "utf-8",
) -> RawMaterial:
    """Load one local approved material using its validated metadata.

    ``metadata.source`` is treated as a local path. Relative paths are resolved
    against ``base_dir`` when provided, otherwise against the current working
    directory. The original source value is preserved in metadata so source IDs
    remain stable across repeated ingestion runs.

    Args:
        metadata: Validated title, source path, type, and cohort information.
        base_dir: Optional directory used to resolve relative source paths.
        encoding: Text encoding used to read the source file.

    Returns:
        A validated raw material ready for chunking and persistence.

    Raises:
        FileNotFoundError: If the source file does not exist.
        IsADirectoryError: If the source points to a directory.
        UnicodeDecodeError: If the file cannot be decoded with ``encoding``.
    """
    source_path = Path(metadata.source)
    file_path = source_path if source_path.is_absolute() else Path(base_dir or ".") / source_path

    return RawMaterial(
        metadata=metadata,
        content=_read_text_file(file_path, encoding=encoding),
    )


def material_from_file(
    path: str | Path,
    *,
    cohort: str,
    source_type: SourceType | str,
    title: str | None = None,
    source: str | None = None,
    encoding: str = "utf-8",
) -> RawMaterial:
    """Create one validated material directly from a local text file.

    Args:
        path: Local file to read.
        cohort: Cohort that owns this material.
        source_type: Approved material category.
        title: Optional display title; defaults to a readable file-stem title.
        source: Optional stable source identifier/path stored in metadata.
        encoding: Text encoding used to read the file.

    Returns:
        A validated material ready for ingestion.
    """
    file_path = Path(path)
    display_title = title or file_path.stem.replace("_", " ").replace("-", " ").strip().title()
    stable_source = source or file_path.as_posix()
    metadata = SourceMetadata(
        title=display_title,
        source=stable_source,
        type=source_type,
        cohort=cohort,
    )

    # Read from the actual supplied path while preserving ``stable_source`` in
    # metadata. This supports a logical source name that differs from its local
    # filesystem location.
    return RawMaterial(
        metadata=metadata,
        content=_read_text_file(file_path, encoding=encoding),
    )


def ingest_materials(
    materials: Iterable[RawMaterial],
    *,
    store: KBStore | None = None,
) -> IngestionStats:
    """Ingest validated materials with update-not-duplicate behavior.

    Args:
        materials: Approved in-memory materials to ingest.
        store: Optional injected store for tests; production uses the shared
            pgvector/OpenAI-backed store.

    Returns:
        Counts for seen, ingested, skipped, and written chunks.
    """
    material_list = list(materials)
    if not material_list:
        return IngestionStats()

    active_store = store or get_default_store()
    return active_store.ingest(material_list)


def ingest_sources(
    sources: Iterable[SourceMetadata],
    *,
    base_dir: str | Path | None = None,
    encoding: str = "utf-8",
    store: KBStore | None = None,
) -> IngestionStats:
    """Load and ingest local source files described by validated metadata.

    This function is the intended seam for ``app.cohorts.config``: cohort
    configuration can provide a list of ``SourceMetadata`` records, while this
    module handles file loading and the store handles idempotent persistence.
    """
    materials = [
        load_material(source, base_dir=base_dir, encoding=encoding)
        for source in sources
    ]
    return ingest_materials(materials, store=store)


def ingest_file(
    path: str | Path,
    *,
    cohort: str,
    source_type: SourceType | str,
    title: str | None = None,
    source: str | None = None,
    encoding: str = "utf-8",
    store: KBStore | None = None,
) -> IngestionStats:
    """Load and ingest one approved local source file."""
    material = material_from_file(
        path,
        cohort=cohort,
        source_type=source_type,
        title=title,
        source=source,
        encoding=encoding,
    )
    return ingest_materials([material], store=store)


__all__ = [
    "get_default_store",
    "ingest_file",
    "ingest_materials",
    "ingest_sources",
    "load_material",
    "material_from_file",
]