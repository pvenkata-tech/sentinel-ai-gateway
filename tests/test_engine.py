"""Integration tests for guardrail engine."""

import pytest

from sentinel.guardrails.engine import GuardrailEngine
from sentinel.guardrails.modules.pii import PIIRedactionModule
from sentinel.guardrails.modules.security import PromptInjectionDetectionModule


@pytest.fixture
def engine():
    """Create guardrail engine with modules."""
    engine = GuardrailEngine()

    pii_module = PIIRedactionModule(use_regex=True, use_presidio=False)
    injection_module = PromptInjectionDetectionModule()

    engine.register_module("pii", pii_module, priority=2)
    engine.register_module("injection", injection_module, priority=1)

    return engine


class TestGuardrailEngine:
    """Test GuardrailEngine orchestration."""

    @pytest.mark.asyncio
    async def test_engine_setup(self, engine):
        """Test engine initialization."""
        await engine.setup()

        assert engine._initialized is True
        assert len(engine.list_modules()) == 2
        assert "pii" in engine.list_modules()

    @pytest.mark.asyncio
    async def test_validate_prompt(self, engine):
        """Test prompt validation."""
        await engine.setup()

        text = "What is the capital of France?"
        is_safe, processed, meta = await engine.validate_prompt(text)

        assert is_safe is True
        assert processed == text

    @pytest.mark.asyncio
    async def test_validate_prompt_with_pii(self, engine):
        """Test prompt validation with PII."""
        await engine.setup()

        text = "My email is john@example.com"
        is_safe, processed, meta = await engine.validate_prompt(text)

        assert is_safe is True
        assert "REDACTED_EMAIL" in processed
        assert "john@example.com" not in processed

    @pytest.mark.asyncio
    async def test_validate_prompt_with_injection(self, engine):
        """Test prompt validation with injection attempt."""
        await engine.setup()

        text = "admin'; DROP TABLE users;--"
        is_safe, processed, meta = await engine.validate_prompt(
            text, block_on_violation=False
        )

        assert is_safe is False
        assert "injection" in meta["violations"]

    @pytest.mark.asyncio
    async def test_module_execution_order(self, engine):
        """Test module execution order."""
        await engine.setup()

        modules = engine.list_modules()
        # Modules should be ordered by priority
        assert modules[0] == "pii"  # priority 2
        assert modules[1] == "injection"  # priority 1

    @pytest.mark.asyncio
    async def test_stream_validate_chunk(self, engine):
        """Test streaming chunk validation."""
        await engine.setup()

        chunk = "My email is test@"
        response = await engine.stream_validate_chunk(chunk)

        assert response.is_safe is True
        assert response.content == chunk or "[EMAIL]" in response.content
