"""Week 3 prompt contract for grounded answers.

The canonical implementation remains in :mod:`app.prompts.grounding`; this
module gives the Week 3 capability a stable, discoverable import path.
"""

from app.prompts.grounding import (
    GROUNDING_SYSTEM_PROMPT,
    GROUNDING_USER_PROMPT,
    HONEST_REFUSAL_MESSAGE,
    GroundedAnswer,
    GroundingChunk,
    build_grounding_messages,
    format_grounding_context,
)

__all__ = [
    "GROUNDING_SYSTEM_PROMPT",
    "GROUNDING_USER_PROMPT",
    "HONEST_REFUSAL_MESSAGE",
    "GroundedAnswer",
    "GroundingChunk",
    "build_grounding_messages",
    "format_grounding_context",
]
