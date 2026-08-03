import os

from openai import OpenAI

# Importing settings should load the project's .env.development file.
from app.core.config import settings


def main() -> None:
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = settings.OPENAI_API_KEY
    model = settings.DEFAULT_LLM_MODEL

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to .env.development."
        )

    if not base_url:
        raise RuntimeError(
            "OPENAI_BASE_URL is missing. Add it to .env.development."
        )

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        }
    ]

    print(f"Connected model: {model}")
    print("Type 'exit' to stop.\n")

    while True:
        user_text = input("You: ").strip()

        if user_text.lower() in {"exit", "quit"}:
            break

        if not user_text:
            continue

        messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
            )

            answer = response.choices[0].message.content or ""
            print(f"Assistant: {answer}\n")

            messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

        except Exception as exc:
            print(f"\nRequest failed: {type(exc).__name__}")
            print(str(exc))
            break


if __name__ == "__main__":
    main()