"""Ingest one PDF into the production knowledge-base table."""

from app.kb.ingest import ingest_file
from app.kb.schema import SourceType


def main() -> None:
    """Ingest the test PDF and print the result."""
    stats = ingest_file(
        "materials/test_faqs.pdf", # Path
        cohort="General",
        source_type=SourceType.FAQ, # FAQ, ONBOARDING, SCHEDULE, PROGRAM_DOC
        title="FAQs",
        source="materials/test_faqs.pdf", # Source of file
    )

    print("PDF ingestion completed")
    print(stats.model_dump())


if __name__ == "__main__":
    main()