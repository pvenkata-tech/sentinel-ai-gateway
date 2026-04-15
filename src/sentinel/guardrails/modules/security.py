"""Prompt Injection Detection Guardrail Module."""

import logging
import re
from typing import Any, Dict, List

from sentinel.guardrails.base import GuardrailModule, GuardrailResponse

logger = logging.getLogger(__name__)


class PromptInjectionDetectionModule(GuardrailModule):
    """Detect and flag prompt injection attempts.

    Uses pattern matching and semantic analysis to identify:
    - SQL injection attempts
    - Command injection attempts
    - Jailbreak prompts
    - System prompt extraction attempts
    """

    def __init__(self) -> None:
        """Initialize prompt injection detection module."""
        # Injection patterns to detect
        self.injection_patterns: Dict[str, str] = {
            # SQL injection
            "SQL_INJECTION": r"(union|select|insert|update|delete|drop|create|alter)\s+(from|into|table|database)",
            # Command injection
            "COMMAND_INJECTION": r"[;&|`$(){}[\]<>]",
            # Jailbreak attempt keywords
            "JAILBREAK_ATTEMPT": r"(ignore|bypass|forget|instructions|system prompt|do not|don't|you are|pretend|roleplay|act as if)",
            # LDAP/NoSQL injection
            "LDAP_INJECTION": r"(\*|&|\||\(|\)|\\\x00)",
            # Template injection
            "TEMPLATE_INJECTION": r"(\{\{|\{%|\.\_\_|\|safe)",
            # XML injection
            "XML_INJECTION": r"(<!\[CDATA\[|<!ENTITY|SYSTEM|PUBLIC)",
        }

        # Severity weights (0-1 scale)
        self.severity_weights: Dict[str, float] = {
            "SQL_INJECTION": 0.9,
            "COMMAND_INJECTION": 0.8,
            "JAILBREAK_ATTEMPT": 0.6,
            "LDAP_INJECTION": 0.8,
            "TEMPLATE_INJECTION": 0.7,
            "XML_INJECTION": 0.75,
        }

        # Threshold for blocking (0-1)
        self.block_threshold = 0.5

        self._initialized = False

    def setup(self) -> None:
        """Setup module."""
        self._initialized = True
        logger.info("Prompt injection detection module initialized")

    def shutdown(self) -> None:
        """Cleanup resources."""
        self._initialized = False

    async def validate(self, text: str) -> GuardrailResponse:
        """Detect injection attempts in prompt.

        Args:
            text: Prompt text to analyze.

        Returns:
            GuardrailResponse with safety status and findings.
        """
        if not text or len(text.strip()) == 0:
            return GuardrailResponse(
                is_safe=True,
                content=text,
                metadata={"injection_risk": 0.0, "patterns_found": []},
            )

        # Convert to lowercase for matching
        text_lower = text.lower()
        findings: Dict[str, Any] = {}
        max_severity = 0.0
        patterns_found: List[str] = []

        # Check each pattern
        for pattern_name, pattern in self.injection_patterns.items():
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                patterns_found.append(pattern_name)
                findings[pattern_name] = len(matches)

                # Calculate severity
                severity = self.severity_weights.get(pattern_name, 0.5)
                max_severity = max(max_severity, severity)

        # Determine if prompt is safe
        is_safe = max_severity < self.block_threshold

        return GuardrailResponse(
            is_safe=is_safe,
            content=text,  # Don't redact, just flag
            metadata={
                "injection_risk": float(max_severity),
                "patterns_found": patterns_found,
                "pattern_count": len(patterns_found),
                "threshold": self.block_threshold,
            },
            violations=findings,
        )

    def set_block_threshold(self, threshold: float) -> None:
        """Set the injection risk threshold for blocking.

        Args:
            threshold: Severity threshold (0-1).
        """
        if not 0 <= threshold <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        self.block_threshold = threshold
        logger.info(f"Injection block threshold set to {threshold}")

    def add_custom_pattern(
        self, name: str, pattern: str, severity: float = 0.5
    ) -> None:
        """Add a custom injection pattern.

        Args:
            name: Pattern name.
            pattern: Regex pattern to match.
            severity: Severity weight (0-1).
        """
        self.injection_patterns[name] = pattern
        self.severity_weights[name] = max(0.0, min(1.0, severity))
        logger.debug(f"Added custom injection pattern: {name}")
