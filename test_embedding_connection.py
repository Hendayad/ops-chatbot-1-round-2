import os

from openai import OpenAI

from app.core.config import settings


def main() -> None:
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = settings.OPENAI_API_KEY
    model = settings.LONG_TERM_MEMORY_EMBEDDER_MODEL

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL is missing.")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    response = client.embeddings.create(
        model=model,
        input="The final project deadline is August 7.",
    )

    vector = response.data[0].embedding

    print(f"Embedding model: {model}")
    print(f"Vector created successfully.")
    print(f"Vector length: {len(vector)}")
    print(f"First five values: {vector[:5]}")


if __name__ == "__main__":
    main()