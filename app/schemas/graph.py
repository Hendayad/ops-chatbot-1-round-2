"""Shared LangGraph state for the Operations support workflow."""

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class GraphState(BaseModel):
    """State fields shared by grounded answering and orchestration nodes."""

    messages: Annotated[list[Any], add_messages] = Field(
        default_factory=list,
        description="Messages in the conversation",
    )
    long_term_memory: str = Field(
        default="",
        description="Long-term memory associated with the conversation",
    )
    session_id: str | None = Field(default=None, description="Session identifier")
    user_id: str | None = Field(default=None, description="User identifier")
    cohort_id: str | None = Field(
        default=None,
        description="Mandatory learner cohort used to scope knowledge retrieval",
    )

    # The answer node writes these fields so the escalation router can consume
    # honest-refusal outcomes without parsing AIMessage metadata.
    answer_generated: bool = False
    answer_escalation_signal: bool = False
    answer_escalation_reason: str | None = None
