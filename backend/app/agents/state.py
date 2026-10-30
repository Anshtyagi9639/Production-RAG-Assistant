"""The agent's working state (BUILD.md section 7)."""

from typing import Any, Literal, TypedDict

from app.ai.retrieval import RetrievedChunk

Classification = Literal["simple", "complex"]


class AgentState(TypedDict, total=False):
    request: str
    workspace_id: str
    classification: Classification | None
    sub_questions: list[str]
    retrieved_chunks: list[RetrievedChunk]
    analysis: str
    tool_results: list[dict[str, Any]]
    retrieval_rounds: int
    validation: dict[str, Any] | None
    revisions: int
    final_answer: str | None
    sources: list[dict[str, Any]]
    is_partial: bool
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    error: str | None
    prompt_tokens: int
    completion_tokens: int
