"""Guardrail Engine - Orchestrates guardrail execution."""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from sentinel.guardrails.base import GuardrailModule, GuardrailResponse

logger = logging.getLogger(__name__)

# Lazy import telemetry to avoid initialization issues in tests
_tracer = None
_meter = None


def _get_tracer():
    """Lazy load tracer."""
    global _tracer
    if _tracer is None:
        try:
            from sentinel.core.telemetry import telemetry_manager
            _tracer = telemetry_manager.get_tracer(__name__)
        except RuntimeError:
            # Telemetry not initialized, use no-op
            import opentelemetry.trace as trace
            _tracer = trace.get_tracer(__name__)
    return _tracer


def _get_meter():
    """Lazy load meter."""
    global _meter
    if _meter is None:
        try:
            from sentinel.core.telemetry import telemetry_manager
            _meter = telemetry_manager.get_meter(__name__)
        except RuntimeError:
            # Telemetry not initialized, use no-op
            import opentelemetry.metrics as metrics
            _meter = metrics.get_meter(__name__)
    return _meter


class GuardrailEngine:
    """Orchestrates guardrail module execution.

    Manages the pipeline for processing inbound prompts and outbound
    completions through multiple guardrail modules.
    """

    def __init__(self) -> None:
        """Initialize guardrail engine."""
        self.modules: Dict[str, GuardrailModule] = {}
        self.module_priorities: Dict[str, int] = {}  # Track priorities
        self.module_order: List[str] = []
        self._initialized = False

    def register_module(
        self, name: str, module: GuardrailModule, priority: int = 0
    ) -> None:
        """Register a guardrail module.

        Args:
            name: Unique module identifier.
            module: GuardrailModule instance.
            priority: Execution priority (higher = earlier).
        """
        if name in self.modules:
            logger.warning(f"Module {name} already registered, replacing")

        self.modules[name] = module
        self.module_priorities[name] = priority
        
        # Sort by priority (descending), then by name for stability
        self.module_order = sorted(
            self.modules.keys(),
            key=lambda x: (self.module_priorities[x], -ord(x[0])),
            reverse=True,
        )
        logger.info(f"Registered guardrail module: {name}")

    async def setup(self) -> None:
        """Initialize all registered modules."""
        if self._initialized:
            return

        for name, module in self.modules.items():
            try:
                module.setup()
                logger.debug(f"Setup complete for module: {name}")
            except Exception as e:
                logger.error(f"Failed to setup module {name}: {e}")
                raise

        self._initialized = True
        logger.info(f"Guardrail engine initialized with {len(self.modules)} modules")

    async def shutdown(self) -> None:
        """Shutdown all modules."""
        for name, module in self.modules.items():
            try:
                module.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down module {name}: {e}")

        self._initialized = False

    async def validate_prompt(
        self, prompt: str, block_on_violation: bool = False
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate inbound prompt through all modules.

        Args:
            prompt: Prompt text to validate.
            block_on_violation: Stop on first violation.

        Returns:
            Tuple of (is_safe, processed_prompt, metadata).
        """
        with _get_tracer().start_as_current_span("validate_prompt") as span:
            span.set_attribute("prompt_length", len(prompt))

            current_text = prompt
            metadata: Dict[str, Any] = {}
            violations: Dict[str, Dict[str, Any]] = {}
            is_safe_overall = True  # Track safety across modules

            for module_name in self.module_order:
                module = self.modules[module_name]
                try:
                    response = await module.validate(current_text)

                    metadata[module_name] = response.metadata
                    if response.violations:
                        violations[module_name] = response.violations

                    # Update text for next module
                    current_text = response.content

                    # A module returning is_safe=False means unsafe (blocking)
                    if not response.is_safe:
                        is_safe_overall = False
                        span.set_attribute(f"{module_name}.violation", True)
                        if block_on_violation:
                            logger.warning(
                                f"Prompt blocked by {module_name}: {response.violations}"
                            )
                            return False, current_text, metadata

                except Exception as e:
                    logger.error(f"Error in {module_name}: {e}")
                    violations[module_name] = {"error": str(e)}

            return is_safe_overall, current_text, {"modules": metadata, "violations": violations}

    async def validate_completion(
        self, completion: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate outbound completion through all modules.

        Same as validate_prompt but for LLM responses.

        Args:
            completion: Completion text to validate.

        Returns:
            Tuple of (is_safe, processed_completion, metadata).
        """
        with _get_tracer().start_as_current_span("validate_completion") as span:
            span.set_attribute("completion_length", len(completion))
            return await self.validate_prompt(completion, block_on_violation=False)

    async def stream_validate_chunk(
        self,
        chunk: str,
        module_name: str = "default",
        look_back_buffer: Optional[str] = None,
    ) -> GuardrailResponse:
        """Validate a single streaming chunk through all modules.

        Low-latency path for streaming responses.

        Args:
            chunk: Chunk to validate.
            module_name: Primary module to use.
            look_back_buffer: Buffer from previous chunk for pattern detection.

        Returns:
            GuardrailResponse with redacted chunk.
        """
        if not chunk:
            return GuardrailResponse(is_safe=True, content=chunk)

        current_chunk = chunk

        for module_name in self.module_order:
            module = self.modules[module_name]
            try:
                # Use streaming-specific method if available
                if hasattr(module, "validate_streaming_chunk"):
                    response = await module.validate_streaming_chunk(
                        current_chunk, look_back_buffer
                    )
                else:
                    response = await module.validate(current_chunk)

                current_chunk = response.content

            except Exception as e:
                logger.error(f"Error in streaming validation {module_name}: {e}")
                # Don't block stream on error, log and continue
                pass

        return GuardrailResponse(is_safe=True, content=current_chunk)

    async def stream_validate(
        self,
        input_stream: AsyncGenerator[str, None],
        buffer_size: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Validate a streaming response with look-back buffering.

        Applies guardrails to streaming chunks with overlap for
        pattern detection across boundaries.

        Args:
            input_stream: Async generator of chunks.
            buffer_size: Size of look-back buffer.

        Yields:
            Redacted chunks.
        """
        look_back = ""

        async for chunk in input_stream:
            # Validate with buffer context
            response = await self.stream_validate_chunk(
                chunk, look_back_buffer=look_back
            )

            # Yield redacted chunk
            yield response.content

            # Update look-back buffer
            look_back = chunk[-buffer_size:] if len(chunk) > buffer_size else chunk

    def get_module(self, name: str) -> Optional[GuardrailModule]:
        """Get a registered module by name."""
        return self.modules.get(name)

    def list_modules(self) -> List[str]:
        """List all registered modules in execution order."""
        return self.module_order.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "initialized": self._initialized,
            "modules_count": len(self.modules),
            "modules": self.list_modules(),
        }
