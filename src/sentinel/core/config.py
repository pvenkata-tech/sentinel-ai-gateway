"""Configuration management using Pydantic Settings v2."""

from typing import Literal

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support.
    
    Uses Pydantic v2 with compiled schema for optimal validation performance.
    Supports environment variable override for all settings.
    """

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Use Pydantic v2 compiled Core for 2-5x faster validation
        validate_assignment=True,
    )

    # Application metadata
    app_name: str = "Sentinel AI Gateway"
    version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"

    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    debug: bool = False

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # OpenTelemetry / Observability
    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "sentinel-gateway"
    otel_traces_sample_rate: float = 1.0
    prometheus_enabled: bool = True
    prometheus_port: int = 8001

    # LLM Provider Configuration
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    # Guardrails Configuration
    enable_pii_redaction: bool = True
    enable_prompt_injection_detection: bool = True
    pii_detection_model: str = "en_core_web_sm"  # spaCy model
    regex_pii_patterns: bool = True

    # Streaming Configuration
    stream_chunk_size: int = 512
    stream_buffer_size: int = 4096  # Look-back buffer (chars) for split pattern detection
    max_stream_timeout: float = 300.0

    # Circuit Breaker Configuration (Fault Tolerance)
    # Controls behavior when guardrails hang or fail
    circuit_breaker_enabled: bool = True
    circuit_breaker_fail_mode: Literal["fail_open", "fail_closed"] = "fail_open"
    # "fail_open": Allow request through on error (availability-first)
    # "fail_closed": Block request on error (security-first)
    
    # Circuit breaker timeout (seconds) before considering operation hung
    circuit_breaker_timeout: float = 5.0
    
    # Failures before opening circuit
    circuit_breaker_failure_threshold: int = 5
    
    # Seconds before attempting recovery
    circuit_breaker_recovery_timeout: float = 60.0
    
    # Successes to close circuit from half-open
    circuit_breaker_success_threshold: int = 2

    # Cache Configuration
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600


# Singleton instance (lazy-loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Default export for backward compatibility
settings = get_settings()
