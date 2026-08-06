"""Ingest every enabled cohort from cohorts_config.json."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.cohorts.config import cohort_config
from app.kb.ingest import ingest_sources


def main() -> None:
    cohort_ids = cohort_config.list_cohorts()
    if not cohort_ids:
        raise RuntimeError(
            "No enabled cohorts found. Check COHORTS_CONFIG_PATH."
        )

    for cohort_id in cohort_ids:
        config = cohort_config.load_cohort_config(cohort_id)
        sources = cohort_config.get_sources(cohort_id)
        root = config.get("materials_root", "")

        if not root:
            raise RuntimeError(f"{cohort_id}: materials_root is missing")
        if not sources:
            raise RuntimeError(f"{cohort_id}: no approved materials configured")

        stats = ingest_sources(sources, base_dir=root)
        print(
            f"{cohort_id}: seen={stats.sources_seen}, "
            f"ingested={stats.sources_ingested}, "
            f"skipped={stats.sources_skipped}, "
            f"chunks={stats.chunks_written}"
        )


if __name__ == "__main__":
    main()
