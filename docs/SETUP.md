# Setup Guide

Complete installation, configuration, and local development guide.

## Prerequisites

- **Python:** 3.10+
- **pip:** Latest version
- **Git:** For cloning the repository
- **API Keys:** OpenAI, Gemini, or Anthropic (for LLM functionality)

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/your-org/sentinel-ai-gateway.git
cd sentinel-ai-gateway
```

### 2. Create Virtual Environment

```bash
# Python 3.10+
python -m venv .venv

# Activate
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install in development mode with all extras
pip install -e ".[dev]"

# Or minimal installation
pip install -e "."
```

**What gets installed:**
- FastAPI, Uvicorn (web framework)
- Pydantic (configuration)
- OpenTelemetry (tracing & metrics)
- Presidio (NER for PII detection)
- spaCy (NLP)
- pytest (testing)

---

## Configuration

### 1. Environment File

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

Get your keys:
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

### 5. Observability (Optional)

```env
# OpenTelemetry
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=sentinel-gateway
OTEL_TRACES_SAMPLE_RATE=1.0

# Prometheus
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=8001
```

**Detailed configuration reference:**

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENVIRONMENT` | string | `development` | `development`, `staging`, `production` |
| `DEBUG` | boolean | `false` | Enable debug mode |
| `LOG_LEVEL` | string | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `API_HOST` | string | `0.0.0.0` | Server bind address |
| `API_PORT` | integer | `8000` | Server port |
| `ENABLE_PII_REDACTION` | boolean | `true` | Enable PII detection |
| `ENABLE_PROMPT_INJECTION_DETECTION` | boolean | `true` | Enable injection detection |
| `PII_DETECTION_MODEL` | string | `en_core_web_sm` | spaCy model (`en_core_web_sm` or `en_core_web_lg`) |
| `REGEX_PII_PATTERNS` | boolean | `true` | Enable regex-based PII patterns |
| `STREAM_CHUNK_SIZE` | integer | `512` | Bytes per stream chunk |
| `STREAM_BUFFER_SIZE` | integer | `4096` | Look-back buffer size for split patterns |
| `MAX_STREAM_TIMEOUT` | float | `300.0` | Stream timeout in seconds |
| `OTEL_ENABLED` | boolean | `true` | Enable OpenTelemetry |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | string | `http://localhost:4317` | OTLP gRPC endpoint |
| `OTEL_SERVICE_NAME` | string | `sentinel-gateway` | Service name in traces |
| `OTEL_TRACES_SAMPLE_RATE` | float | `1.0` | Trace sampling rate (0-1) |
| `PROMETHEUS_ENABLED` | boolean | `true` | Enable Prometheus metrics |
| `PROMETHEUS_PORT` | integer | `8001` | Prometheus metrics port |

---

## Local Development

### 1. Start Development Server

```bash
# With auto-reload
python -m uvicorn sentinel.main:app --reload --port 8000

# Or using Flask development server
python -m uvicorn sentinel.main:app --host 0.0.0.0 --port 8000 --reload
```

**Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12508]
INFO:     Started server process [4736]
INFO:     Application startup complete.
```

The server is now running at `http://localhost:8000`

### 2. Test Endpoints

**Health check:**
```bash
curl http://localhost:8000/health
```

**Validate text:**
```bash
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"My email is test@example.com","mode":"prompt"}'
```

**Get status:**
```bash
curl http://localhost:8000/guardrails/status | jq
```

### 3. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_guardrails.py -v

# Run with coverage
pytest tests/ -v --cov=sentinel --cov-report=html

# Run and watch for changes
pytest tests/ -v --watch  # requires pytest-watch
```

**View coverage report:**
```bash
# Generate HTML report
pytest tests/ --cov=sentinel --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

### 4. View Logs

By default, logs go to stdout. Customize in `src/sentinel/main.py`:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

Watch logs in real-time:
```bash
# Terminal 1: Start server
python -m uvicorn sentinel.main:app --reload

# Terminal 2: Make request
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"admin'\'''; DROP TABLE users;--","mode":"prompt"}'

# Terminal 1 shows:
# sentinel.guardrails.modules.security - INFO - SQL_INJECTION pattern detected
```

### 5. IDE Setup (VS Code)

**`.vscode/launch.json`:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Server",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["sentinel.main:app", "--reload", "--port", "8000"],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v", "--tb=short"],
      "console": "integratedTerminal"
    }
  ]
}
```

**Debugging:**
1. Set breakpoint in code
2. Run "FastAPI Server" from VS Code Run menu
3. Make request to trigger breakpoint

---

## Docker Setup

### 1. Build Image

```bash
docker build -t sentinel-ai-gateway:latest .
```

### 2. Run Container

```bash
docker run -p 8000:8000 \
  --env-file .env \
  sentinel-ai-gateway:latest
```

### 3. Docker Compose (with Observability)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f sentinel

# Stop
docker-compose down
```

**Services:**
- **sentinel:** http://localhost:8000
- **Jaeger UI:** http://localhost:16686 (distributed traces)
- **Prometheus:** http://localhost:9090 (metrics)
- **Postgres:** localhost:5432 (Jaeger backend)

---

## Troubleshooting

### Issue: Import Errors

```
ModuleNotFoundError: No module named 'sentinel'
```

**Solution:**
```bash
# Reinstall in development mode
pip install -e "."

# Or add to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

### Issue: API Key Not Found

```
ValidationError: 1 validation error for Settings
openai_api_key
  Field required [type=missing]
```

**Solution:**
```bash
# Verify .env file exists
ls -la .env

# Check API key is set
echo $OPENAI_API_KEY

# Or set directly
export OPENAI_API_KEY="sk-proj-..."
```

### Issue: Port Already in Use

```
OSError: [Errno 48] Address already in use
```

**Solution:**
```bash
# Use different port
python -m uvicorn sentinel.main:app --port 8001

# Or kill process on port 8000
lsof -ti :8000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :8000    # Windows
```

### Issue: Slow Startup (spaCy Download)

On first run, Presidio downloads spaCy model (~400MB):

```
presidio-analyzer - WARNING - Model en_core_web_lg is not installed. Downloading...
```

**Solution:**
- Wait for download to complete (2-5 minutes)
- Or use smaller model: `PII_DETECTION_MODEL=en_core_web_sm`
- Or skip Presidio: `REGEX_PII_PATTERNS=true` (regex-only mode)

### Issue: Tests Fail

```
FAILED tests/test_guardrails.py::test_email_redaction - AssertionError: ...
```

**Debug:**
```bash
# Run with verbose output
pytest tests/test_guardrails.py::test_email_redaction -vv

# Run with print statements
pytest tests/test_guardrails.py::test_email_redaction -s

# Run with pdb debugger
pytest tests/test_guardrails.py::test_email_redaction --pdb
```

---

## Environment Profiles

### Development

```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
OTEL_TRACES_SAMPLE_RATE=1.0
```

### Staging

```env
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
OTEL_TRACES_SAMPLE_RATE=0.5
```

### Production

```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
OTEL_TRACES_SAMPLE_RATE=0.1
```

---

## Performance Tuning

### High Throughput

```env
STREAM_CHUNK_SIZE=4096    # Larger chunks
STREAM_BUFFER_SIZE=2048   # Smaller buffer
LOG_LEVEL=WARNING         # Less logging
OTEL_TRACES_SAMPLE_RATE=0.1  # Sample traces
```

### Low Latency

```env
STREAM_CHUNK_SIZE=256     # Smaller chunks
STREAM_BUFFER_SIZE=4096   # Larger buffer (split pattern safety)
LOG_LEVEL=INFO
OTEL_ENABLED=false        # Skip telemetry overhead
```

### Memory Constrained

```env
PII_DETECTION_MODEL=en_core_web_sm  # Smaller model
PROMETHEUS_ENABLED=false  # Skip metrics
OTEL_ENABLED=false        # Skip tracing
```

---

## Security Checklist

- [ ] `.env` file in `.gitignore` (don't commit API keys)
- [ ] Use environment variables in production (not .env files)
- [ ] Enable HTTPS/TLS in production
- [ ] Rotate API keys regularly
- [ ] Monitor metrics and logs
- [ ] Use strong authentication on `/metrics` endpoint
- [ ] Run tests before deployment
- [ ] Keep dependencies updated: `pip list --outdated`

---

## Useful Commands

```bash
# List environment variables
env | grep SENTINEL

# Check Python version
python --version

# Verify dependencies
pip list

# Update dependencies
pip install --upgrade -r requirements-dev.txt

# Format code
black src/

# Lint code
flake8 src/

# Type checking
mypy src/

# Security audit
bandit -r src/
```

---

## Next Steps

1. **Run tests:** `pytest tests/ -v`
2. **Start server:** `python -m uvicorn sentinel.main:app --reload`
3. **Test endpoint:** `curl http://localhost:8000/health`
4. **Read API docs:** See [API Reference](./API.md)
5. **Deploy:** See [Deployment Guide](./DEPLOYMENT.md)

For more details, see [Architecture](./ARCHITECTURE.md) and [Guardrails Guide](./GUARDRAILS.md).
