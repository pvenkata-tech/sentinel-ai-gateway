"""Configuration management using Pydantic Settings."""

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

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
    stream_buffer_size: int = 4096  # Look-back buffer for split patterns
    max_stream_timeout: float = 300.0

    # Cache Configuration
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
