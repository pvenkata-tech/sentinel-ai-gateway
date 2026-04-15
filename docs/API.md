# API Reference

Complete endpoint documentation for Sentinel AI Gateway.

## Base URL

```
http://localhost:8000
```

For production, replace with your deployment URL.

---

## Health & Status Endpoints

### GET /health

Health check endpoint for liveness probes (Kubernetes, load balancers).

**Request:**
```http
GET /health HTTP/1.1
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-04-15T18:04:22.853Z"
}
```

**Use Cases:**
- Kubernetes liveness probe
- Load balancer health check
- Monitoring systems

---

### GET /metrics

Prometheus metrics endpoint for monitoring and alerting.

**Request:**
```http
GET /metrics HTTP/1.1
```

**Response (200 OK):**
```
# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.01",method="POST",path="/guardrails/validate"} 45.0
http_request_duration_seconds_bucket{le="0.05",method="POST",path="/guardrails/validate"} 89.0
http_request_duration_seconds_bucket{le="0.1",method="POST",path="/guardrails/validate"} 95.0
...

# HELP pii_detections_total Total PII detections
# TYPE pii_detections_total counter
pii_detections_total{pattern="EMAIL"} 234.0
pii_detections_total{pattern="SSN"} 45.0
pii_detections_total{pattern="PHONE"} 128.0
...

# HELP injection_blocks_total Total injection attempts blocked
# TYPE injection_blocks_total counter
injection_blocks_total{pattern="SQL_INJECTION"} 12.0
injection_blocks_total{pattern="JAILBREAK"} 3.0
...
```

**Scrape with Prometheus:**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'sentinel-gateway'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

---

### GET /guardrails/status

Guardrail modules status and configuration.

**Request:**
```http
GET /guardrails/status HTTP/1.1
```

**Response (200 OK):**
```json
{
  "initialized": true,
  "modules": {
    "pii_redaction": {
      "enabled": true,
      "priority": 2,
      "patterns_available": 6,
      "detection_method": "hybrid",
      "status": "ready"
    },
    "prompt_injection": {
      "enabled": true,
      "priority": 1,
      "patterns_available": 6,
      "block_threshold": 0.5,
      "status": "ready"
    }
  },
  "timestamp": "2026-04-15T18:04:22.853Z"
}
```

**Fields:**
- `modules[].priority` — Execution order (higher = first)
- `modules[].patterns_available` — Number of detection patterns
- `modules[].status` — `ready`, `initializing`, `error`

---

## Validation Endpoints

### POST /guardrails/validate

**Direct validation endpoint** — Test guardrails without routing to LLM provider.

**Request:**
```http
POST /guardrails/validate HTTP/1.1
Content-Type: application/json

{
  "text": "My email is john@example.com and SSN is 123-45-6789",
  "mode": "prompt"
}
```

**Parameters:**
- `text` (string, required) — Text to validate
- `mode` (string, required) — `"prompt"` or `"completion"`

**Response (200 OK) — PII Detected:**
```json
{
  "input_length": 51,
  "output_length": 50,
  "is_safe": true,
  "processed_text": "My email is REDACTED_EMAIL and SSN is REDACTED_SSN",
  "metadata": {
    "modules": {
      "pii_redaction": {
        "redacted": true,
        "detection_method": "hybrid",
        "text_length": 51,
        "redacted_length": 50
      },
      "prompt_injection": {
        "injection_risk": 0.0,
        "patterns_found": [],
        "pattern_count": 0,
        "threshold": 0.5
      }
    },
    "violations": {
      "pii_redaction": {
        "EMAIL": 1,
        "SSN": 1
      }
    }
  }
}
```

**Response (200 OK) — Injection Detected:**
```json
{
  "input_length": 27,
  "output_length": 27,
  "is_safe": false,
  "processed_text": "admin'; DROP TABLE users;--",
  "metadata": {
    "modules": {
      "pii_redaction": {
        "redacted": false,
        "detection_method": "clean",
        "text_length": 27,
        "redacted_length": 27
      },
      "prompt_injection": {
        "injection_risk": 0.9,
        "patterns_found": [
          "SQL_INJECTION",
          "COMMAND_INJECTION"
        ],
        "pattern_count": 2,
        "threshold": 0.5
      }
    },
    "violations": {
      "prompt_injection": {
        "SQL_INJECTION": 1,
        "COMMAND_INJECTION": 2
      }
    }
  }
}
```

**Response (200 OK) — Clean Text:**
```json
{
  "input_length": 33,
  "output_length": 33,
  "is_safe": true,
  "processed_text": "What's the weather in New York?",
  "metadata": {
    "modules": {
      "pii_redaction": {
        "redacted": false,
        "detection_method": "clean",
        "text_length": 33,
        "redacted_length": 33
      },
      "prompt_injection": {
        "injection_risk": 0.0,
        "patterns_found": [],
        "pattern_count": 0,
        "threshold": 0.5
      }
    },
    "violations": {}
  }
}
```

**Response Field Meanings:**

| Field | Type | Meaning |
|-------|------|---------|
| `is_safe` | bool | True = safe to send to LLM, False = blocked |
| `processed_text` | string | Text after redaction (sent to LLM if safe) |
| `input_length` | int | Original text length in characters |
| `output_length` | int | Redacted text length |
| `metadata.modules.*.redacted` | bool | Whether PII was found and redacted |
| `metadata.modules.*.detection_method` | string | `"hybrid"` (regex+AI), `"clean"` (no PII) |
| `metadata.modules.*.injection_risk` | float | 0-1 risk score (threshold: 0.5) |
| `metadata.violations` | object | Detailed breakdown of what was detected |

---

## LLM Proxy Endpoints

### POST /v1/chat/completions

**OpenAI-compatible chat endpoint** — Acts as transparent proxy with guardrail interception.

**Request (Non-Streaming):**
```http
POST /v1/chat/completions HTTP/1.1
Content-Type: application/json

{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "My email is test@example.com. What is my account balance?"}
  ],
  "temperature": 0.7,
  "max_tokens": 100,
  "stream": false
}
```

**Flow:**
1. Extract prompt: `"My email is test@example.com..."`
2. Validate through guardrails
3. Redact if needed: `"My email is REDACTED_EMAIL..."`
4. Forward redacted prompt to LLM provider
5. Receive response
6. Validate response for new PII
7. Return to client

**Response (200 OK):**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1713196200,
  "model": "gpt-4",
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 50,
    "total_tokens": 75
  },
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Your account balance is $1,234.56."
      },
      "finish_reason": "stop",
      "index": 0
    }
  ],
  "guardrail_metadata": {
    "prompt_violations": {},
    "completion_violations": {},
    "redactions": 1,
    "blocks": 0
  }
}
```

**Request (Streaming):**
```http
POST /v1/chat/completions HTTP/1.1
Content-Type: application/json

{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Tell me a joke"}
  ],
  "stream": true
}
```

**Response (200 OK, Server-Sent Events):**
```
data: {"id":"chatcmpl-abc123","choices":[{"delta":{"role":"assistant","content":""},"index":0}]}

data: {"id":"chatcmpl-abc123","choices":[{"delta":{"content":"Why"},"index":0}]}

data: {"id":"chatcmpl-abc123","choices":[{"delta":{"content":" did"},"index":0}]}

data: {"id":"chatcmpl-abc123","choices":[{"delta":{"content":" the"},"index":0}]}

...

data: [DONE]
```

**Each chunk is processed through guardrails for real-time redaction.**

**Error Responses:**

**400 Bad Request — Injection Detected:**
```json
{
  "error": "Request blocked by security guardrails",
  "violations": {
    "prompt_injection": {
      "SQL_INJECTION": 1,
      "COMMAND_INJECTION": 2
    }
  }
}
```

**401 Unauthorized — Invalid API Key:**
```json
{
  "error": "Invalid or missing API key for LLM provider"
}
```

**429 Too Many Requests:**
```json
{
  "error": "Rate limit exceeded"
}
```

**500 Internal Server Error:**
```json
{
  "error": "Internal server error",
  "detail": "Error message (development only)"
}
```

---

## Error Handling

### Standard Error Response

All errors follow this format:

```json
{
  "error": "Error message",
  "detail": "Additional context (may be omitted in production)",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
}
```

### Common Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Validation passed, response returned |
| 400 | Bad Request | Invalid JSON, injection detected |
| 401 | Unauthorized | Missing/invalid API key |
| 429 | Rate Limited | Too many requests |
| 500 | Server Error | Unhandled exception |
| 503 | Unavailable | Service temporarily down |

---

## Authentication

### API Key Header (For Future Use)

```http
POST /v1/chat/completions HTTP/1.1
Authorization: Bearer your-api-key-here
```

Currently not enforced; reserved for future versioning.

---

## Rate Limiting

### Limits (Per IP)

- **Requests:** 1000 per minute
- **Tokens:** 100,000 per day

### Response Headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1713196260
```

---

## Pagination & Batch Operations

Not currently supported. Process requests individually.

---

## Request/Response Examples

### Example 1: Safe Prompt with Streaming

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "What is AI?"}],
    "stream": true
  }' \
  --no-buffer
```

### Example 2: PII Redaction Test

```bash
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Contact me at john@example.com",
    "mode": "prompt"
  }' \
  | jq '.processed_text'
```

Output: `"Contact me at REDACTED_EMAIL"`

### Example 3: Injection Detection Test

```bash
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "admin'\'''; DROP TABLE users;--",
    "mode": "prompt"
  }' \
  | jq '.is_safe'
```

Output: `false`

---

## OpenTelemetry Integration

### Tracing Headers

All requests include OpenTelemetry trace context:

```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

Access distributed traces in **Jaeger UI:** `http://localhost:16686`

### Trace Spans

For each request, these spans are created:

```
proxy_middleware (parent)
├─ validate_prompt
│  ├─ pii_redaction.validate
│  └─ injection_detection.validate
├─ forward_to_provider
└─ apply_streaming_guardrails
```

---

## Pagination, Sorting, Filtering

Not supported in current version.

---

## Versioning

Current API version: **v0.1.0**

Backward compatibility not guaranteed until v1.0.

---

## Webhooks

Not currently supported.

---

## SDK/Libraries

No official SDK yet. Use HTTP client libraries:

**Python:**
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/guardrails/validate",
        json={"text": "...", "mode": "prompt"}
    )
```

**JavaScript:**
```javascript
const response = await fetch("http://localhost:8000/guardrails/validate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text: "...", mode: "prompt" })
});
```

**cURL:** See examples above.

---

For more details, see [Architecture](./ARCHITECTURE.md) and [Examples](./EXAMPLES.md).
