"""Ingest one PDF into the production knowledge-base table."""

from app.kb.ingest import ingest_file
from app.kb.schema import SourceType


def main() -> None:
    """Ingest the test PDF and print the result."""
    stats = ingest_file(
        "materials/test_faqs.pdf",
        cohort="General",
        source_type=SourceType.FAQ,
        title="FAQs",
        source="materials/test_faqs.pdf",
    )

    print("PDF ingestion completed")
    print(stats.model_dump())


if __name__ == "__main__":
    main()