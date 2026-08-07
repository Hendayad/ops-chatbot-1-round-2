import re


SMALL_TALK = {
    "hi",
    "hello",
    "hey",
    "how are you",
    "good morning",
    "good evening",
    "thanks",
    "thank you",
}


def is_small_talk(message: str) -> bool:
    """Detect simple conversational messages."""
    normalized = message.strip().lower()
    normalized = re.sub(r"[?!.,]+$", "", normalized).strip()

    return normalized in SMALL_TALK