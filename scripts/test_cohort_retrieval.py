"""Test cohort-scoped retrieval without the frontend."""

import asyncio
from app.retrieval.retriever import retrieve


async def show(cohort_id: str) -> None:
    results = await retrieve(
        "When is the final project deadline?",
        cohort=cohort_id,
        top_k=5,
    )

    print(f"\n{cohort_id}")
    for item in results:
        preview = " ".join(item.content.split())[:220]
        print(
            f"{item.similarity:.4f} | {item.source_id} | "
            f"{item.source} | {preview}"
        )


async def main() -> None:
    await show("cohort-a")
    await show("cohort-b")


if __name__ == "__main__":
    asyncio.run(main())
