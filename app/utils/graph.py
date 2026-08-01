"""This file contains the graph utilities for the application."""

import tiktoken
from typing import Any, Union
from langchain_core.messages import BaseMessage
from langchain_core.messages import trim_messages as _trim_messages

from app.core.config import settings
from app.core.logging import logger
from app.schemas import Message

# Cache tiktoken encoding at module level — thread-safe and reusable
try:
    _TIKTOKEN_ENCODING = tiktoken.encoding_for_model(settings.DEFAULT_LLM_MODEL)
except KeyError:
    _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens_tiktoken(messages: list[Any]) -> int:
    """Count tokens locally using tiktoken — no API call needed."""
    num_tokens = 0
    for message in messages:
        # Every message has overhead tokens for role/name
        num_tokens += 4
        if isinstance(message, dict):
            for _, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(_TIKTOKEN_ENCODING.encode(value))
        elif isinstance(message, BaseMessage):
            content = message.content
            if isinstance(content, str):
                num_tokens += len(_TIKTOKEN_ENCODING.encode(content))
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, str):
                        num_tokens += len(_TIKTOKEN_ENCODING.encode(block))
                    elif isinstance(block, dict) and "text" in block:
                        val = block["text"]
                        if isinstance(val, str):
                            num_tokens += len(_TIKTOKEN_ENCODING.encode(val))
    num_tokens += 2  # every reply is primed with assistant
    return num_tokens


def dump_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Dump the messages to a list of dictionaries.

    Messages coming straight from the request body are Message pydantic
    objects, but messages read back out of LangGraph state have already
    been dumped to plain dicts on a previous pass (see get_response /
    get_stream_response, which store dump_messages(...) output directly
    into graph state). Handle both shapes so this is safe to call at
    either point in the pipeline.

    Args:
        messages (list[Message]): The messages to dump.

    Returns:
        list[dict]: The dumped messages.
    """
    return [message.model_dump() if hasattr(message, "model_dump") else message for message in messages]


def extract_text_content(content: Union[str, list[Any]]) -> str:
    """Extract plain text from an LLM content value.

    Handles both the simple string format and the structured block list returned
    by GPT-5 / Responses API models:
        [{'type': 'reasoning', ...}, {'type': 'text', 'text': '...'}]

    Args:
        content: Raw content from a LangChain BaseMessage.

    Returns:
        Plain text string (empty string when nothing extractable is present).
    """
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif block.get("type") == "reasoning":
                logger.debug(
                    "reasoning_block_received",
                    reasoning_id=block.get("id"),
                    has_summary=bool(block.get("summary")),
                )
    return "".join(parts)


def process_llm_response(response: BaseMessage) -> BaseMessage:
    """Normalise a raw LLM response so that ``response.content`` is always a plain string.

    Args:
        response: The raw response from the LLM.

    Returns:
        The same BaseMessage instance with ``content`` set to a plain string.
    """
    if isinstance(response.content, list):
        extracted_text = extract_text_content(response.content)
        response.content = extracted_text
        logger.debug(
            "processed_structured_content",
            content_block_count=len(extracted_text),
            extracted_length=len(extracted_text),
        )
    return response


_BASE_MESSAGE_TYPE_TO_ROLE = {"human": "user", "ai": "assistant", "system": "system"}


def _message_to_mapping(msg: Union[dict, BaseMessage]) -> dict[str, Any]:
    """Normalize a trimmed message (dict or BaseMessage) to a role/content mapping.

    langchain_core's trim_messages() returns BaseMessage instances regardless
    of the input shape, so downstream code that builds our own Message schema
    needs a mapping either way.
    """
    if isinstance(msg, dict):
        return msg
    return {"role": _BASE_MESSAGE_TYPE_TO_ROLE.get(msg.type, "user"), "content": msg.content}


def prepare_messages(messages: list[Message], system_prompt: str) -> list[Message]:
    """Prepare the messages for the LLM.

    Args:
        messages (list[Message]): The messages to prepare.
        system_prompt (str): The system prompt to use.

    Returns:
        list[Message]: The prepared messages.
    """
    try:
        # LangChain's trim_messages internally converts its input to BaseMessage
        # objects (HumanMessage/AIMessage/SystemMessage) and returns that same
        # BaseMessage representation -- NOT dicts matching whatever shape we
        # passed in, despite what the old comment here claimed. So we can't
        # just cast-and-unpack the result; each item has to be normalized to
        # a {"role", "content"} mapping before it can build a Message.
        raw_trimmed = _trim_messages(
            dump_messages(messages),
            strategy="last",
            token_counter=_count_tokens_tiktoken,
            max_tokens=settings.MAX_TOKENS,
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
        trimmed_messages = [Message(**_message_to_mapping(msg)) for msg in raw_trimmed]
    except ValueError as e:
        # Handle unrecognized content blocks (e.g., reasoning blocks from GPT-5)
        if "Unrecognized content block type" in str(e):
            logger.warning(
                "token_counting_failed_skipping_trim",
                error=str(e),
                message_count=len(messages),
            )
            # Skip trimming and return all messages
            trimmed_messages = messages
        else:
            raise

    return [Message(role="system", content=system_prompt)] + trimmed_messages
