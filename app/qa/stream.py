"""Streaming adapter for the grounded Q&A pipeline.

We validate before streaming.  This avoids the common failure mode where an
ungrounded token is sent before the application has checked citations.
"""

from collections.abc import AsyncIterator

from app.qa.graph import QAResult, answer_question


async def stream_answer(question: str, *, cohort: str) -> AsyncIterator[str]:
    """Yield a validated answer in line-sized chunks and then stop.

    A full token-by-token LLM stream cannot be safely grounded until citation
    validation completes, so this adapter streams the already-validated text.
    """
    result: QAResult = await answer_question(question, cohort=cohort)
    for line in result.answer.splitlines(keepends=True):
        if line:
            yield line


__all__ = ["stream_answer"]
