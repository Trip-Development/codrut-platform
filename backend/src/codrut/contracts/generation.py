from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from codrut.core.errors import DomainError


class GenerationProviderKey(StrEnum):
    local = "local"
    vertex = "vertex"


class GenerationPurpose(StrEnum):
    actor = "actor"
    evaluator = "evaluator"
    coach = "coach"
    summary = "summary"


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0


@dataclass(frozen=True)
class GenerationMessage:
    role: Literal["user", "model"]
    text: str


@dataclass(frozen=True)
class GenerationRequest:
    messages: tuple[GenerationMessage, ...]
    system_instruction: str | None = None
    purpose: GenerationPurpose = GenerationPurpose.actor
    max_output_tokens: int = 1024
    temperature: float = 0.7
    thinking_budget: int = 0


@dataclass(frozen=True)
class GenerationResult:
    text: str
    usage: TokenUsage
    provider: GenerationProviderKey
    model: str
    region: str
    finish_reason: str
    estimated_usd: Decimal


class GenerationError(DomainError):
    def __init__(
        self,
        message: str,
        code: str = "generation_error",
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)
