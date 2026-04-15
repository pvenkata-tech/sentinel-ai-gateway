# Sentinel AI Gateway Documentation

Welcome to the **Sentinel AI Gateway** — a production-grade security layer for large language model (LLM) interactions. This documentation covers all aspects of deploying, configuring, and using the gateway.

## Quick Links

- **[Architecture](./ARCHITECTURE.md)** — System design, components, and data flow
- **[API Reference](./API.md)** — Endpoint documentation and request/response formats
- **[Guardrails Guide](./GUARDRAILS.md)** — PII detection, injection prevention, and custom rules
- **[Setup Guide](./SETUP.md)** — Installation, configuration, and local development
- **[Deployment](./DEPLOYMENT.md)** — Docker, Kubernetes, and production deployment
- **[Examples](./EXAMPLES.md)** — Code samples and integration patterns
- **[Troubleshooting](./TROUBLESHOOTING.md)** — Common issues and solutions

## Overview

Sentinel AI Gateway is a middleware solution that sits between your application and LLM providers (OpenAI, Google Gemini, Anthropic) to:

- **🔒 Redact Sensitive Data** — Automatically detect and remove PII (emails, SSNs, credit cards, etc.) before sending to LLMs
- **🛡️ Prevent Prompt Injection** — Block malicious prompts attempting SQL injection, command execution, jailbreaks
- **📊 Monitor & Audit** — Track all requests with detailed violation metadata and OpenTelemetry traces
- **⚡ Streaming-First** — Zero-copy streaming responses with on-the-fly redaction
- **🔌 Extensible** — Plugin architecture for custom guardrails and detection modules

## Key Features

### Hybrid PII Detection
- **Fast Path:** Regex patterns for common formats (email, phone, SSN, credit cards, IP addresses)
- **Audit Path:** Presidio NER model for comprehensive entity recognition
- **Streaming Safe:** Handles PII patterns split across chunk boundaries

### Injection Detection
- **Pattern Matching:** SQL, command shell, LDAP, XML, template injection patterns
- **Risk Scoring:** Weighted severity analysis (0-1 scale)
- **Configurable Thresholds:** Per-environment block levels

### Production Ready
- **OpenTelemetry Integration:** Distributed tracing and Prometheus metrics
- **Async/Await:** Fully asynchronous for high throughput
- **Error Handling:** Graceful degradation on guardrail failures
- **Health Checks:** Built-in `/health` and `/metrics` endpoints

## Architecture at a Glance

```
Client Request
    ↓
[FastAPI Server]
    ↓
[GuardrailProxyMiddleware]
    ├─ Inbound Validation
    │  └─ [GuardrailEngine]
    │     ├─ PII Redaction Module
    │     └─ Injection Detection Module
    ↓
[LLM Provider API]
    ↓
[Response Stream/Completion]
    ↓
[Outbound Redaction]
    └─ [GuardrailEngine] (streaming validation)
    ↓
Client Response (safe to display)
```

## File Structure

```
sentinel-ai-gateway/
├── src/sentinel/
│   ├── main.py                    # FastAPI app, routes, lifespan
│   ├── core/
│   │   ├── config.py              # Pydantic settings
│   │   └── telemetry.py           # OpenTelemetry setup
│   ├── guardrails/
│   │   ├── engine.py              # Orchestration engine
│   │   ├── base.py                # Module base class
│   │   └── modules/
│   │       ├── pii.py             # PII redaction
│   │       └── security.py        # Injection detection
│   ├── middleware/
│   │   └── proxy.py               # HTTP middleware
│   ├── utils/
│   │   ├── llm_client.py          # LLM provider clients
│   │   └── streaming.py           # Stream utilities
│   └── __init__.py
├── tests/
│   ├── test_engine.py             # Engine integration tests
│   ├── test_guardrails.py         # Module unit tests
│   └── conftest.py                # Pytest fixtures
├── docs/                          # Documentation
├── docker-compose.yml             # Stack: app, Jaeger, Prometheus
├── Dockerfile                     # Container image
├── pyproject.toml                 # Dependencies and config
├── .env.example                   # Configuration template
└── README.md                      # Project overview
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run Locally

```bash
python -m uvicorn sentinel.main:app --reload --port 8000
```

### 4. Test an Endpoint

```bash
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"My email is test@example.com","mode":"prompt"}'
```

Response:
```json
{
  "is_safe": true,
  "processed_text": "My email is REDACTED_EMAIL",
  "metadata": {
    "modules": {
      "pii_redaction": {
        "redacted": true,
        "detection_method": "hybrid"
      }
    }
  }
}
```

## Configuration

All settings are managed via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `OTEL_ENABLED` | `true` | Enable OpenTelemetry tracing |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint |
| `ENABLE_PII_REDACTION` | `true` | Enable PII detection |
| `ENABLE_PROMPT_INJECTION_DETECTION` | `true` | Enable injection detection |
| `STREAM_CHUNK_SIZE` | `512` | Bytes per stream chunk |
| `STREAM_BUFFER_SIZE` | `4096` | Look-back buffer for split patterns |
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `GEMINI_API_KEY` | (optional) | Google Gemini API key |
| `ANTHROPIC_API_KEY` | (optional) | Anthropic Claude API key |

See [Setup Guide](./SETUP.md) for complete configuration options.

## Key Endpoints

### Health & Status

- `GET /health` — Health check
- `GET /metrics` — Prometheus metrics
- `GET /guardrails/status` — Guardrail module status

### Validation

- `POST /guardrails/validate` — Validate prompt or completion
  - Body: `{"text": "...", "mode": "prompt|completion"}`

### LLM Proxy

- `POST /v1/chat/completions` — OpenAI-compatible chat endpoint
  - Transparent proxy with guardrail interception
  - Supports streaming and non-streaming

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=sentinel --cov-report=html

# Run specific test
pytest tests/test_guardrails.py::test_email_redaction -v
```

Current test coverage: **36%** (core logic 66-100%)

## Deployment

### Docker

```bash
docker build -t sentinel-ai-gateway:latest .
docker run -p 8000:8000 --env-file .env sentinel-ai-gateway:latest
```

### Docker Compose (with observability stack)

```bash
docker-compose up -d
# App: http://localhost:8000
# Jaeger UI: http://localhost:16686
# Prometheus: http://localhost:9090
```

See [Deployment Guide](./DEPLOYMENT.md) for Kubernetes and production configs.

## Support & Troubleshooting

- **[Troubleshooting Guide](./TROUBLESHOOTING.md)** — Common issues and solutions
- **[API Reference](./API.md)** — Request/response formats
- **[Examples](./EXAMPLES.md)** — Code samples

## Performance Benchmarks

| Operation | Latency | Notes |
|-----------|---------|-------|
| PII Redaction (regex) | 1-2ms | Fast path, common patterns |
| PII Redaction (hybrid) | 50-200ms | With Presidio NER |
| Injection Detection | <1ms | Pattern matching |
| Streaming Chunk | <5ms | Per 512-byte chunk |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass: `pytest tests/ -v`
5. Submit a pull request

## License

MIT License — See LICENSE file

---

**Questions?** Check the [Troubleshooting Guide](./TROUBLESHOOTING.md) or review [Examples](./EXAMPLES.md).
