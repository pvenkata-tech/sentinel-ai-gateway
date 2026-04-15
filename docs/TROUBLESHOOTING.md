# Troubleshooting Guide

Common issues and solutions.

---

## Startup Issues

### Issue: "ModuleNotFoundError: No module named 'sentinel'"

**Symptom:**
```
ModuleNotFoundError: No module named 'sentinel'
```

**Causes:**
- Package not installed in development mode
- Incorrect Python path
- Virtual environment not activated

**Solutions:**

```bash
# Reinstall in development mode
pip install -e "."

# Or add to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Verify virtual environment
which python  # Should show .venv path

# If not, activate venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate      # Windows
```

---

### Issue: "ValidationError: Field required [type=missing]"

**Symptom:**
```
ValidationError: 1 validation error for Settings
openai_api_key
  Field required [type=missing]
```

**Causes:**
- `.env` file missing or not loaded
- API key environment variable not set
- `.env` path incorrect

**Solutions:**

```bash
# Create .env from template
cp .env.example .env

# Edit with your API key
nano .env

# Verify it's loaded
echo $OPENAI_API_KEY

# Or set directly
export OPENAI_API_KEY="sk-proj-..."

# For development, can use dummy key
export OPENAI_API_KEY="test-key"
```

---

### Issue: "OSError: [Errno 48] Address already in use"

**Symptom:**
```
OSError: [Errno 48] Address already in use
```

**Causes:**
- Port 8000 already in use
- Previous server instance still running
- Other service using the port

**Solutions:**

```bash
# Use different port
python -m uvicorn sentinel.main:app --port 8001

# Kill process on port 8000
# macOS/Linux:
lsof -ti :8000 | xargs kill -9

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or find what's using the port
lsof -i :8000

# Check if previous uvicorn process is running
ps aux | grep uvicorn
```

---

### Issue: "Connection refused: http://localhost:8000"

**Symptom:**
```
ConnectionError: Trying to connect to http://localhost:8000 but connection was refused
```

**Causes:**
- Server not started
- Wrong host/port
- Firewall blocking connection

**Solutions:**

```bash
# Check if server is running
curl http://localhost:8000/health

# Check if service is listening
netstat -tlnp | grep 8000

# Start server with explicit host/port
python -m uvicorn sentinel.main:app --host 127.0.0.1 --port 8000

# Try localhost instead of 127.0.0.1
curl http://127.0.0.1:8000/health
```

---

## Configuration Issues

### Issue: "Failed to initialize OpenTelemetry"

**Symptom:**
```
ERROR - Failed to initialize OpenTelemetry: name 'app' is not defined
```

**Causes:**
- Telemetry initialization happens before app creation
- OTEL configuration invalid
- Jaeger endpoint unreachable

**Solutions:**

```env
# Disable OTEL if not using it
OTEL_ENABLED=false

# Or verify endpoint is correct
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Test Jaeger connection
curl http://localhost:4317  # Should timeout (not HTTP)
```

For Docker Compose stack:
```bash
docker-compose up -d jaeger
# Then start sentinel
```

---

### Issue: "Model en_core_web_lg not installed"

**Symptom:**
```
presidio-analyzer - WARNING - Model en_core_web_lg is not installed. Downloading...
[Long wait, ~400MB download]
```

**Causes:**
- Presidio downloading large spaCy model on first run
- Network connection slow
- Disk space insufficient

**Solutions:**

```bash
# Use smaller model
export PII_DETECTION_MODEL=en_core_web_sm

# Or use regex-only mode
export REGEX_PII_PATTERNS=true

# Or pre-download model in Docker
python -m spacy download en_core_web_sm

# Check available disk space
df -h  # macOS/Linux
dir C:\  # Windows
```

---

### Issue: "Invalid API Key"

**Symptom:**
```
HTTP 401: Unauthorized - Invalid API key for OpenAI
```

**Causes:**
- API key incorrect or expired
- API key not configured
- API key quota exceeded

**Solutions:**

```bash
# Verify API key format
echo $OPENAI_API_KEY
# Should start with "sk-proj-" for OpenAI

# Get new key from
# https://platform.openai.com/api-keys

# Test with curl
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check account quota
# https://platform.openai.com/account/billing/overview
```

---

## Runtime Issues

### Issue: "Response content longer than Content-Length"

**Symptom:**
```
RuntimeError: Response content longer than Content-Length
```

**Causes:**
- Middleware modifying response body but not updating header
- Content-Length header mismatch after redaction
- Streaming response with modified chunks

**Solutions:**

```python
# In middleware, remove Content-Length before modifying body
headers = dict(response.headers)
headers.pop("content-length", None)  # Remove to let Starlette recalculate

return Response(
    body_content,
    status_code=response.status_code,
    headers=headers
)
```

---

### Issue: "Timeout waiting for response"

**Symptom:**
```
asyncio.TimeoutError: Deadline exceeded
```

**Causes:**
- Presidio NER taking too long
- Network latency to LLM provider
- Too many concurrent requests

**Solutions:**

```env
# Increase timeouts
MAX_STREAM_TIMEOUT=600  # 10 minutes

# Reduce concurrent connections
STREAM_CHUNK_SIZE=256  # Smaller chunks = faster processing

# Use regex-only mode
REGEX_PII_PATTERNS=true
```

```python
# In client code, increase timeout
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(...)
```

---

### Issue: "Memory usage growing over time"

**Symptom:**
```
Process memory usage increases, eventually crashes
```

**Causes:**
- Memory leak in Presidio NER
- spaCy model not released
- Accumulated trace spans
- Look-back buffer growing unbounded

**Solutions:**

```env
# Limit trace sampling
OTEL_TRACES_SAMPLE_RATE=0.1  # Sample 10% of traces

# Use regex-only (less memory)
REGEX_PII_PATTERNS=true

# Restart server periodically
# (In Kubernetes, just delete pods)

# Reduce buffer size (more risk of split patterns)
STREAM_BUFFER_SIZE=2048  # Default: 4096
```

```python
# Monitor memory
import psutil
import os

process = psutil.Process(os.getpid())
mem = process.memory_info().rss / 1024 / 1024  # MB
print(f"Memory: {mem:.2f} MB")
```

---

## Testing Issues

### Issue: "pytest: command not found"

**Symptom:**
```
pytest: command not found
```

**Causes:**
- pytest not installed
- Virtual environment not active
- pytest not in PATH

**Solutions:**

```bash
# Install test dependencies
pip install -e ".[dev]"

# Or install pytest directly
pip install pytest pytest-asyncio

# Verify installation
pip list | grep pytest

# Run tests
python -m pytest tests/ -v
```

---

### Issue: "Test timeout"

**Symptom:**
```
FAILED tests/test_guardrails.py::test_name - asyncio.TimeoutError
```

**Causes:**
- Test taking too long
- Presidio model loading in test
- Network request hanging

**Solutions:**

```python
# In test, increase timeout
@pytest.mark.asyncio
async def test_name():
    # Use shorter timeouts for unit tests
    pass

# Or skip slow tests in CI
@pytest.mark.slow
async def test_slow_operation():
    pass

# Run with --timeout
pytest tests/ --timeout=30
```

---

### Issue: "Test assertions failing"

**Symptom:**
```
FAILED tests/test_guardrails.py::test_email - AssertionError: ...
```

**Causes:**
- Pattern format changed
- Redaction format incorrect
- Module not initialized in test

**Solutions:**

```bash
# Run with verbose output
pytest tests/test_guardrails.py::test_email -vv

# Show print statements
pytest tests/test_guardrails.py::test_email -s

# Debug with pdb
pytest tests/test_guardrails.py::test_email --pdb

# Check current patterns
curl http://localhost:8000/guardrails/status | jq '.modules'
```

---

## Integration Issues

### Issue: "Can't connect to LLM provider"

**Symptom:**
```
HTTPError: 401 - Unauthorized for https://api.openai.com/...
```

**Causes:**
- API key invalid
- API endpoint wrong
- Network/firewall blocking

**Solutions:**

```bash
# Test API key directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Test from container
docker run --rm -e OPENAI_API_KEY=$OPENAI_API_KEY \
  sentinel-ai-gateway:latest \
  python -c "from openai import OpenAI; OpenAI().models.list()"

# Check proxy/firewall
curl -I https://api.openai.com  # Should be 400, not timeout
```

---

### Issue: "PII not being detected"

**Symptom:**
```
Email "test@example.com" not redacted
```

**Causes:**
- Regex pattern missing email format
- Presidio model not loaded
- Module disabled

**Solutions:**

```bash
# Check module status
curl http://localhost:8000/guardrails/status | jq '.modules.pii_redaction'

# Test directly
curl -X POST http://localhost:8000/guardrails/validate \
  -d '{"text":"test@example.com","mode":"prompt"}' | jq '.processed_text'

# Check logs
python -m uvicorn sentinel.main:app --log-level=DEBUG
```

```python
# Verify regex pattern
import re
pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
text = "test@example.com"
print(re.findall(pattern, text))  # Should find match
```

---

### Issue: "False positives in injection detection"

**Symptom:**
```
Safe text blocked as SQL injection
"SELECT the best option" → blocked
```

**Causes:**
- Pattern too broad
- Threshold too strict
- Multiple patterns triggering

**Solutions:**

```bash
# Increase threshold to be more lenient
export PROMPT_INJECTION_THRESHOLD=0.7

# Check which patterns matched
curl -X POST http://localhost:8000/guardrails/validate \
  -d '{"text":"SELECT the best option","mode":"prompt"}' \
  | jq '.metadata.modules.prompt_injection'

# Should show which patterns triggered
```

```python
# Tune pattern severity
module = PromptInjectionDetectionModule()
module.set_block_threshold(0.6)  # Lenient

# Or remove overly broad patterns
module.patterns.pop("SQL_INJECTION", None)
```

---

## Docker Issues

### Issue: "Docker image build fails"

**Symptom:**
```
ERROR: failed to solve with frontend dockerfile.v0
```

**Causes:**
- Python version not available
- Dependency installation fails
- Permission issues

**Solutions:**

```bash
# Build with verbose output
docker build -t sentinel:latest . --progress=plain

# Use different Python version in Dockerfile
# Change "python:3.10" to "python:3.11" or "python:3.12"

# Check internet connection
docker build --build-arg http_proxy=$http_proxy ...
```

---

### Issue: "Container exits immediately"

**Symptom:**
```
docker run sentinel:latest
docker ps  # Container not running
docker logs <container> shows error
```

**Causes:**
- App crashed on startup
- Environment variables not set
- Port already in use

**Solutions:**

```bash
# View logs
docker logs <container-id>

# Run with environment variables
docker run \
  -e OPENAI_API_KEY=sk-proj-... \
  -e LOG_LEVEL=DEBUG \
  sentinel:latest

# Run interactively
docker run -it sentinel:latest bash

# Check if port is available
docker run -p 9000:8000 sentinel:latest  # Use different external port
```

---

### Issue: "Can't access http://localhost:8000 from host"

**Symptom:**
```
curl: (7) Failed to connect to localhost port 8000
```

**Causes:**
- Container not listening on 0.0.0.0
- Port mapping incorrect
- Network isolated

**Solutions:**

```bash
# Use 0.0.0.0 not 127.0.0.1
docker run -p 8000:8000 sentinel:latest \
  python -m uvicorn sentinel.main:app --host 0.0.0.0 --port 8000

# Check port mapping
docker ps  # Should show "0.0.0.0:8000->8000/tcp"

# Try container IP directly
docker inspect <container-id> | grep IPAddress
curl http://<container-ip>:8000/health

# Use docker-compose
docker-compose up -d
# Port should be accessible immediately
```

---

## Kubernetes Issues

### Issue: "CrashLoopBackOff"

**Symptom:**
```
kubectl get pods
# sentinel-xxx   0/1     CrashLoopBackOff
```

**Causes:**
- App crash on startup
- Config/secret missing
- Resource limits too low

**Solutions:**

```bash
# Check logs
kubectl logs -f sentinel-xxx

# Check events
kubectl describe pod sentinel-xxx

# View configuration
kubectl get configmap sentinel-config -o yaml
kubectl get secret sentinel-secrets -o yaml

# Update resource limits
kubectl set resources deployment sentinel \
  --requests=cpu=100m,memory=256Mi \
  --limits=cpu=500m,memory=512Mi

# Debug in container
kubectl run -it debug --image=python:3.10 -- bash
```

---

### Issue: "Service unreachable"

**Symptom:**
```
curl http://<LoadBalancer-IP>/health  # Connection refused
```

**Causes:**
- Service not created
- Endpoint not ready
- Network policy blocking

**Solutions:**

```bash
# Check service
kubectl get svc -n sentinel
kubectl describe svc sentinel -n sentinel

# Check endpoints
kubectl get endpoints sentinel -n sentinel

# Check pods are running
kubectl get pods -n sentinel

# Check network policies
kubectl get networkpolicies -n sentinel

# Test from pod
kubectl run -it debug --image=curl -- \
  curl http://sentinel:8000/health
```

---

## Performance Issues

### Issue: "Slow response times"

**Symptom:**
```
Requests taking >1 second
```

**Causes:**
- Presidio NER processing taking time
- Tracer overhead
- Large model files being loaded

**Solutions:**

```env
# Disable features you don't need
OTEL_ENABLED=false
PROMETHEUS_ENABLED=false

# Use smaller model
PII_DETECTION_MODEL=en_core_web_sm

# Or regex-only
REGEX_PII_PATTERNS=true

# Sample traces
OTEL_TRACES_SAMPLE_RATE=0.1

# Reduce logging
LOG_LEVEL=WARNING
```

```bash
# Profile response time
time curl http://localhost:8000/guardrails/validate \
  -d '{"text":"test","mode":"prompt"}'
```

---

### Issue: "High CPU usage"

**Symptom:**
```
top shows CPU at 100%
```

**Causes:**
- Presidio NER CPU-intensive
- Concurrent requests overwhelming
- Regex pattern matching inefficient

**Solutions:**

```env
# Use smaller model
PII_DETECTION_MODEL=en_core_web_sm

# Or disable Presidio entirely
REGEX_PII_PATTERNS=true

# Limit concurrency
# (Set in Uvicorn/Kubernetes)
```

```bash
# Uvicorn workers
gunicorn sentinel.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker

# Monitor resource usage
docker stats <container-id>
```

---

## Getting Help

1. **Check logs:** `python -m uvicorn sentinel.main:app --log-level=DEBUG`
2. **Test endpoint:** `curl http://localhost:8000/health`
3. **Review docs:** See [Setup Guide](./SETUP.md) and [Architecture](./ARCHITECTURE.md)
4. **Check examples:** See [Examples](./EXAMPLES.md)
5. **Run tests:** `pytest tests/ -vv`

---

For more information, see:
- [Setup Guide](./SETUP.md) — Installation and configuration
- [Architecture](./ARCHITECTURE.md) — System design
- [API Reference](./API.md) — Endpoint documentation
- [Examples](./EXAMPLES.md) — Code samples
