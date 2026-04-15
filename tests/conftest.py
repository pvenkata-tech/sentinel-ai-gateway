"""Pytest configuration and fixtures."""

import os

import pytest

# Set test environment
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "true"
os.environ["OTEL_ENABLED"] = "false"


@pytest.fixture
def test_settings():
    """Provide test settings."""
    from sentinel.core.config import Settings

    return Settings(
        environment="development",
        debug=True,
        otel_enabled=False,
        prometheus_enabled=False,
    )
