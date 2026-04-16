# Quick Start Guide

Complete setup and deployment guide for Sentinel AI Gateway.

## Prerequisites

- **Python:** 3.10+
- **pip:** Latest version
- **Git:** For cloning the repository
- **Docker & Docker Compose:** For containerized deployment (recommended)
- **API Keys:** OpenAI, Gemini, or Anthropic (for LLM functionality)

---

## Installation

### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/sentinel-ai-gateway.git
cd sentinel-ai-gateway

# Start all services
docker compose up -d

# Verify services
docker compose ps
```

**Services:**
- **API:** http://localhost:8000
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/admin)
- **Jaeger:** http://localhost:16686

### Option 2: Local Development

```bash
# Clone repository
git clone https://github.com/your-org/sentinel-ai-gateway.git
cd sentinel-ai-gateway

# Create virtual environment
python -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -e "."
```

---

## Configuration

### 1. Environment Setup

```bash
# Copy example config
cp .env.example .env

# Edit with your settings
code .env  # or your editor
```

### 2. Required Settings

**API Keys (choose at least one):**

```env
# OpenAI
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1

# Google Gemini
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

Get your keys from:
- **OpenAI:** https://platform.openai.com/api-keys
- **Gemini:** https://makersuite.google.com/app/apikey
- **Anthropic:** https://console.anthropic.com/

### 3. Application Settings

```env
# Environment
ENVIRONMENT=development  # or staging, production

# API Server
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
LOG_LEVEL=INFO
```

### 4. Guardrails Configuration

```env
# Enable/disable modules
ENABLE_PII_REDACTION=true
ENABLE_PROMPT_INJECTION_DETECTION=true

# PII Detection
PII_DETECTION_MODEL=en_core_web_sm
REGEX_PII_PATTERNS=true

# Streaming
STREAM_CHUNK_SIZE=512
STREAM_BUFFER_SIZE=4096
MAX_STREAM_TIMEOUT=300.0
```

### Configuration Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENVIRONMENT` | string | `development` | `development`, `staging`, `production` |
| `DEBUG` | boolean | `false` | Enable debug mode |
| `LOG_LEVEL` | string | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `API_HOST` | string | `0.0.0.0` | Server bind address |
| `API_PORT` | integer | `8000` | Server port |
| `ENABLE_PII_REDACTION` | boolean | `true` | Enable PII detection |
| `ENABLE_PROMPT_INJECTION_DETECTION` | boolean | `true` | Enable injection detection |
| `PII_DETECTION_MODEL` | string | `en_core_web_sm` | spaCy model |
| `OTEL_ENABLED` | boolean | `true` | Enable OpenTelemetry tracing |
| `PROMETHEUS_ENABLED` | boolean | `true` | Enable metrics collection |

---

## Running the Application

### Docker

```bash
# Start all services in background
docker compose up -d

# View logs
docker compose logs -f sentinel-gateway

# Stop services
docker compose down
```

### Local Development

```bash
# Start development server (auto-reload)
python -m uvicorn sentinel.main:app --reload --port 8000

# Output:
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
# INFO:     Application startup complete.
```

---

## Testing Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "app": "Sentinel AI Gateway",
  "version": "0.1.0",
  "guardrails": {
    "modules": ["pii_redaction", "prompt_injection"],
    "modules_count": 2,
    "initialized": true
  }
}
```

### Validate Text

```bash
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"My email is test@example.com","mode":"prompt"}'
```

Response:
```json
{
  "input_length": 28,
  "output_length": 26,
  "is_safe": true,
  "processed_text": "My email is REDACTED_EMAIL",
  "metadata": {
    "modules": {
      "pii_redaction": {
        "redacted": true,
        "detection_method": "hybrid"
      },
      "prompt_injection": {
        "injection_risk": 0.0
      }
    }
  }
}
```

### Check Guardrails Status

```bash
curl http://localhost:8000/guardrails/status
```

---

## Docker Deployment

### Single Container

```bash
# Build image
docker build -t sentinel-ai-gateway:latest .

# Run container
docker run -d \
  --name sentinel \
  --env-file .env \
  -p 8000:8000 \
  sentinel-ai-gateway:latest

# Check health
docker logs sentinel
curl http://localhost:8000/health
```

### Docker Compose Stack

```bash
# Start with all observability services
docker compose up -d

# View running services
docker compose ps

# Stop services
docker compose down

# Clean up volumes
docker compose down -v
```

**Includes:**
- Sentinel Gateway (API)
- Prometheus (metrics)
- Grafana (dashboards)
- Jaeger (tracing)
- OTEL Collector (trace collection)

---

## Kubernetes Deployment

### Quick Deploy

```bash
# Create namespace
kubectl create namespace sentinel

# Create secrets
kubectl create secret generic sentinel-secrets \
  --from-env-file=.env.prod \
  -n sentinel

# Deploy using manifests
kubectl apply -f k8s/

# Verify
kubectl get pods -n sentinel
kubectl logs -f -n sentinel deployment/sentinel
```

### Service Access

```bash
# Get service endpoint
kubectl get svc -n sentinel

# Port forward for local access
kubectl port-forward svc/sentinel 8000:80 -n sentinel

# Access at http://localhost:8000
```

---

## Next Steps

- **Learn Architecture:** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **API Reference:** See [API.md](API.md)
- **Troubleshooting:** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Advanced Setup:** Edit docker-compose.yml for Kubernetes, custom volumes, etc.

