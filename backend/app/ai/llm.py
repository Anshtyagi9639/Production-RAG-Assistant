"""Chat-completion boundary. The OpenAI implementation is the only one used by the app; tests
use tests/fakes.py:FakeLLM."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.ai.http import create_openai_http_client
from app.core.config import Settings
from app.core.errors import UserFacingError

logger = logging.getLogger(__name__)

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int


class LLMError(UserFacingError):
    """The language model failed or timed out. Worth retrying later."""

    def __init__(self) -> None:
        super().__init__("The language model failed to respond. Try again in a moment.")


class LLMRateLimitedError(UserFacingError):
    def __init__(self) -> None:
        super().__init__("The language model is busy. Try again in a moment.")


class LLMNotConfiguredError(UserFacingError):
    def __init__(self) -> None:
        super().__init__("Answers are not configured on the server (OPENAI_API_KEY is not set).")


class LLM(Protocol):
    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int, json_mode: bool = False
    ) -> LLMResult: ...


def _to_langchain(message: LLMMessage) -> BaseMessage:
    if message.role == "system":
        return SystemMessage(message.content)
    if message.role == "assistant":
        return AIMessage(message.content)
    return HumanMessage(message.content)


class OpenAIChatLLM:
    """OpenAI chat completions via langchain-openai, temperature 0, bounded retries/timeout."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.openai_key
        self._client = (
            ChatOpenAI(
                model=settings.openai_chat_model,
                api_key=SecretStr(api_key),
                temperature=0,
                timeout=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
                http_async_client=create_openai_http_client(settings.llm_timeout_seconds),
            )
            if api_key
            else None
        )

    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int, json_mode: bool = False
    ) -> LLMResult:
        if self._client is None:
            raise LLMNotConfiguredError
        kwargs: dict[str, Any] = {"max_tokens": max_tokens}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            reply = await self._client.ainvoke([_to_langchain(m) for m in messages], **kwargs)
        except openai.RateLimitError as exc:
            logger.warning("llm_rate_limited", extra={"error": type(exc).__name__})
            raise LLMRateLimitedError from exc
        except Exception as exc:
            # Only the exception type: provider messages can echo request details.
            logger.warning("llm_request_failed", extra={"error": type(exc).__name__})
            raise LLMError from exc
        usage = reply.usage_metadata or {"input_tokens": 0, "output_tokens": 0}
        text = reply.content if isinstance(reply.content, str) else str(reply.content)
        return LLMResult(
            text=text.strip(),
            prompt_tokens=usage["input_tokens"],
            completion_tokens=usage["output_tokens"],
        )


def parse_json_object(text: str) -> dict[str, Any]:
    """The model's JSON reply, or {} if it isn't a JSON object (callers fall back safely)."""
    try:
        value = json.loads(text)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}
