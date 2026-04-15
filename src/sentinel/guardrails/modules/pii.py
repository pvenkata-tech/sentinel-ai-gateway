"""PII/PHI Redaction Guardrail Module."""

import logging
import re
from typing import Any, Dict, Optional

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from sentinel.guardrails.base import GuardrailModule, GuardrailResponse

logger = logging.getLogger(__name__)


class PIIRedactionModule(GuardrailModule):
    """PII/PHI redaction module using hybrid approach.

    Combines fast regex patterns for streaming + Presidio NER for audit.
    """

    def __init__(self, use_regex: bool = True, use_presidio: bool = True):
        """Initialize PII redaction module.

        Args:
            use_regex: Enable fast regex-based detection (stream-friendly).
            use_presidio: Enable Presidio analyzer for deeper NER (async audit).
        """
        self.use_regex = use_regex
        self.use_presidio = use_presidio

        # Fast regex patterns for streaming (low latency)
        self.regex_patterns: Dict[str, str] = {
            "EMAIL": r"[\w\.-]+@[\w\.-]+\.\w+",
            "PHONE": r"\+?1?\s*\(?(\d{3})\)?\s*[-.\s]?(\d{3})\s*[-.\s]?(\d{4})",
            "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
            "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "ZIP_CODE": r"\b\d{5}(?:-\d{4})?\b",
            "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        }

        # Presidio engines for comprehensive detection
        self.analyzer: Optional[AnalyzerEngine] = None
        self.anonymizer: Optional[AnonymizerEngine] = None

        self._initialized = False

    def setup(self) -> None:
        """Initialize Presidio engines."""
        if self._initialized:
            return

        if self.use_presidio:
            try:
                self.analyzer = AnalyzerEngine()
                self.anonymizer = AnonymizerEngine()
                logger.info("Presidio analyzer and anonymizer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Presidio: {e}. Using regex only.")
                self.use_presidio = False

        self._initialized = True

    def shutdown(self) -> None:
        """Cleanup resources."""
        # Presidio doesn't require explicit cleanup
        self._initialized = False

    async def validate(self, text: str) -> GuardrailResponse:
        """Redact PII from text using hybrid approach.

        Fast regex runs synchronously on every chunk.
        Presidio analysis can run asynchronously for retrospective audit.

        Args:
            text: Text to redact.

        Returns:
            GuardrailResponse with redacted content and detected entities.
        """
        if not text:
            return GuardrailResponse(
                is_safe=True, content=text, metadata={"redacted": False}
            )

        redacted_text = text
        found_pii: Dict[str, int] = {}

        # Phase 1: Fast regex redaction (stream-friendly)
        if self.use_regex:
            for label, pattern in self.regex_patterns.items():
                matches = list(re.finditer(pattern, redacted_text))
                if matches:
                    found_pii[label] = len(matches)
                    # Replace with token (using safe format that won't trigger injection detection)
                    redacted_text = re.sub(pattern, f"REDACTED_{label}", redacted_text)

        # Phase 2: Presidio detection (async-safe, can be logged separately)
        presidio_findings: Dict[str, int] = {}
        if self.use_presidio and self.analyzer:
            try:
                results = self.analyzer.analyze(text=text, language="en")
                for finding in results:
                    entity_type = finding.entity_type
                    presidio_findings[entity_type] = (
                        presidio_findings.get(entity_type, 0) + 1
                    )

                # Anonymize using Presidio for audit trail
                if results and self.anonymizer:
                    _anon_text = self.anonymizer.anonymize(
                        text=text, analyzer_results=results
                    )
                    logger.debug(f"Presidio found {len(results)} PII entities")

            except Exception as e:
                logger.warning(f"Presidio analysis failed: {e}")

        # Combine findings
        all_findings = {**found_pii, **presidio_findings}

        return GuardrailResponse(
            is_safe=True,  # Content is safe because it's redacted
            content=redacted_text,
            metadata={
                "redacted": redacted_text != text,
                "detection_method": "hybrid" if all_findings else "clean",
                "text_length": len(text),
                "redacted_length": len(redacted_text),
            },
            violations=all_findings,  # Track what was found for audit
        )

    async def validate_streaming_chunk(
        self, chunk: str, look_back_buffer: Optional[str] = None
    ) -> GuardrailResponse:
        """Validate a streaming chunk with look-back buffer support.

        For split patterns (e.g., "test" + "@email.com"), we use a
        sliding window buffer to catch patterns spanning chunks.

        Args:
            chunk: Current chunk to process.
            look_back_buffer: Previous chunk suffix for pattern matching.

        Returns:
            Redacted chunk and metadata.
        """
        # Combine buffer with current chunk for pattern detection
        search_text = (look_back_buffer or "") + chunk
        response = await self.validate(search_text)

        # Return only the current chunk's redaction
        if look_back_buffer:
            # Strip the redacted buffer prefix
            buffer_len = len(look_back_buffer)
            # This is simplified; in production, track byte offsets
            redacted_chunk = response.content[buffer_len:]
        else:
            redacted_chunk = response.content

        return GuardrailResponse(
            is_safe=response.is_safe,
            content=redacted_chunk,
            metadata={
                **response.metadata,
                "uses_buffer": look_back_buffer is not None,
            },
            violations=response.violations,
        )
