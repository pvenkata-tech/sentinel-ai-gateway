"""Abstract base class for guardrail modules."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict


class GuardrailResponse(BaseModel):
    """Standardized response from guardrail validation."""

    model_config = ConfigDict(extra="allow")

    is_safe: bool
    content: str
    metadata: Dict[str, Any] = {}
    violations: Dict[str, Any] = {}

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"GuardrailResponse(is_safe={self.is_safe}, "
            f"content_len={len(self.content)}, "
            f"violations={len(self.violations)})"
        )


class GuardrailModule(ABC):
    """Abstract base class for guardrail modules.

    All guardrail modules must implement the validate method to process
    inbound prompts or outbound completions.
    """

    @abstractmethod
    async def validate(self, text: str) -> GuardrailResponse:
        """Validate text and return guardrail response.

        Args:
            text: Text to validate (prompt or completion).

        Returns:
            GuardrailResponse with validation results and redacted content.
        """
        pass

    @abstractmethod
    def setup(self) -> None:
        """Setup/initialize the guardrail module.

        Called once during application startup.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup resources.

        Called during application shutdown.
        """
        pass
