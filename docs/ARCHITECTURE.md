# Architecture Guide

## System Overview

Sentinel AI Gateway is architected as a **streaming-first, middleware security layer** for LLM interactions. The design prioritizes low-latency request processing, minimal memory footprint for streaming, and extensibility via a plugin-based guardrail system.

## Core Components

### 1. FastAPI Application (`src/sentinel/main.py`)

**Responsibility:** HTTP server, route handling, application lifecycle

**Key Features:**
- Async ASGI application using FastAPI
- Lifespan context manager for startup/shutdown
- OpenTelemetry instrumentation for distributed tracing
- Middleware registration and ordering

**Lifespan Flow:**
```python
@app.lifespan
async def lifespan(app: FastAPI):
    # STARTUP
    - Initialize telemetry manager
    - Create GuardrailEngine instance
    - Register guardrail modules
    - Instrument app with FastAPI OpenTelemetry
    yield  # App is now running
    # SHUTDOWN
    - Close guardrail modules
    - Shutdown telemetry (graceful trace export)
```

**Endpoints:**
- `GET /health` — Liveness probe
- `GET /metrics` — Prometheus metrics
- `GET /guardrails/status` — Module status report
- `POST /guardrails/validate` — Direct validation endpoint
- `POST /v1/chat/completions` — OpenAI-compatible proxy

### 2. Guardrail Engine (`src/sentinel/guardrails/engine.py`)

**Responsibility:** Orchestrate and execute guardrail modules in priority order

**Design Pattern:** **Strategy Pattern** + **Pipeline Pattern**

```python
class GuardrailEngine:
    - modules: Dict[str, GuardrailModule]      # Registered modules
    - module_priorities: Dict[str, int]        # Priority ordering
    - module_order: List[str]                  # Sorted execution order
    
    Methods:
    - register_module(name, module, priority)  # Add module
    - validate_prompt(text) -> (is_safe, processed, metadata)
    - validate_completion(text) -> (is_safe, processed, metadata)
    - stream_validate_chunk(chunk, buffer) -> GuardrailResponse
```

**Execution Flow:**

```
Input: "My email is test@example.com; DROP TABLE users;--"
    ↓
[Module Priority 2] PII Redaction
    ├─ Regex: Match email → "REDACTED_EMAIL"
    ├─ Output: "My email is REDACTED_EMAIL; DROP TABLE users;--"
    └─ Metadata: {redacted: true, violations: {EMAIL: 1}}
    ↓
[Module Priority 1] Prompt Injection Detection
    ├─ Pattern Match: SQL_INJECTION detected
    ├─ Risk Score: 0.8 (> threshold 0.5)
    └─ Metadata: {injection_risk: 0.8, patterns: [SQL_INJECTION]}
    ↓
Output: is_safe=False, violations={pii_redaction: {...}, injection: {...}}
```

**Module Priority System:**
- Higher priority = executes first
- Typical: PII Redaction (2) → Injection Detection (1)
- Custom modules can insert at any priority level
- Modules don't block each other (all run, all report violations)

### 3. Guardrail Modules (Base + Implementations)

#### Base Class (`src/sentinel/guardrails/base.py`)

```python
class GuardrailModule(ABC):
    """Abstract base for all guardrail modules."""
    
    @abstractmethod
    async def validate(text: str) -> GuardrailResponse:
        """Validate text synchronously."""
        pass
    
    @abstractmethod
    async def validate_streaming_chunk(
        chunk: str, 
        look_back_buffer: str
    ) -> GuardrailResponse:
        """Handle streaming chunks (may span boundaries)."""
        pass
    
    def setup(self) -> None:
        """Initialize resources (models, patterns)."""
        pass
    
    def shutdown(self) -> None:
        """Cleanup resources."""
        pass
```

#### PII Redaction Module (`src/sentinel/guardrails/modules/pii.py`)

**Strategy:** Hybrid fast-path + audit-path

```python
class PIIRedactionModule(GuardrailModule):
    
    REGEX_PATTERNS = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "PHONE": r"(\+1|1)?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}",
        "SSN": r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "ZIP_CODE": r"\b\d{5}(-\d{4})?\b",
        "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    }
    
    Execution:
    1. Fast Path: Run regex patterns (~1-2ms)
    2. Audit Path (async): Run Presidio NER (~50-200ms, non-blocking)
    3. Output: Redacted text + violations metadata
```

**Redaction Format:**
- Pattern: `REDACTED_{PATTERN_NAME}`
- Example: `john@example.com` → `REDACTED_EMAIL`
- Chosen because: Avoids brackets `[EMAIL]` which trigger SQL injection patterns

**Streaming Safety:**
- Problem: Pattern `123-45-6789` (SSN) split across chunk boundary as `123-45` + `-6789`
- Solution: Keep 4096-char look-back buffer from previous chunk
- Example:
  ```python
  chunk1 = "Credit card: 1234-5678"  # Incomplete SSN
  buffer = chunk1[-4096:]
  chunk2 = "-90 expires"
  combined = buffer + chunk2  # "1234-5678-90" now matches
  ```

#### Injection Detection Module (`src/sentinel/guardrails/modules/security.py`)

**Strategy:** Pattern matching with risk scoring

```python
class PromptInjectionDetectionModule(GuardrailModule):
    
    PATTERNS = {
        "SQL_INJECTION": r"(DROP|DELETE|INSERT|UPDATE|SELECT|ALTER).*?(TABLE|DATABASE)",
        "COMMAND_INJECTION": r"(;|&&|\|\|).*?(rm|cat|bash|sh|cmd|powershell)",
        "JAILBREAK": r"(ignore.*?previous|system.*?prompt|ignore.*?instructions)",
        "LDAP_INJECTION": r"(\*)([\w]*)(\))",
        "XML_INJECTION": r"(<!\[CDATA\[|<\?xml|<!DOCTYPE)",
        "TEMPLATE_INJECTION": r"(\{\{.*?\}\}|\${.*?})"
    }
    
    Risk Scoring:
    - Each pattern has a severity_weight (0-1)
    - Pattern count × weight = risk_score
    - If risk_score > threshold (default 0.5) → is_safe = False
    
    Example:
    Text: "admin'; DROP TABLE users;--"
    - SQL_INJECTION: 1 match × 1.0 = 1.0
    - COMMAND_INJECTION: 2 matches × 0.5 = 1.0
    - Combined risk: 1.0 (> 0.5) → BLOCKED
```

### 4. HTTP Middleware (`src/sentinel/middleware/proxy.py`)

**Responsibility:** Intercept requests/responses, apply guardrails transparently

**Design Pattern:** ASGI Middleware (Starlette's `BaseHTTPMiddleware`)

**Request Flow:**

```
1. Client Request
   ↓
2. Parse JSON body
   ↓
3. INBOUND GUARDRAILS
   ├─ Extract text from request.messages
   ├─ Call engine.validate_prompt()
   ├─ If is_safe=False: Return 400 error
   └─ If is_safe=True: Update body with redacted text
   ↓
4. Forward to next handler (FastAPI route/LLM provider)
   ↓
5. Receive response
   ↓
6. OUTBOUND GUARDRAILS
   ├─ If streaming=True:
   │  └─ Wrap response stream, apply redaction per chunk
   └─ If streaming=False:
      └─ Parse JSON, apply redaction, update Content-Length
   ↓
7. Return to client
```

**Key Implementation Details:**

```python
class GuardrailProxyMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(request, call_next):
        # Skip non-JSON POST requests
        if not is_json_post(request):
            return await call_next(request)
        
        # 1. INBOUND: Validate prompt
        body = await request.json()
        is_safe, processed, meta = await validate_prompt(body)
        if not is_safe:
            return error_response(meta)
        
        # 2. Forward with updated body
        request._body = json.dumps(processed).encode()
        response = await call_next(request)
        
        # 3. OUTBOUND: Apply to response
        if is_streaming(body):
            return apply_streaming_guardrails(response)
        else:
            return apply_completion_guardrails(response)
    
    async def apply_streaming_guardrails(response):
        """Wrap stream iterator with guardrail processing."""
        async def stream_wrapper():
            buffer = ""
            async for chunk in response.body_iterator:
                # Parse SSE format (data: {...}\n\n)
                # Apply guardrails per chunk
                # Update buffer for split-pattern detection
                # Yield modified chunk
        
        # Remove Content-Length (streaming has no predefined length)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return StreamingResponse(stream_wrapper(), headers=headers)
    
    async def apply_completion_guardrails(response):
        """Process non-streaming completion response."""
        body = await response.body_iterator.read()
        data = json.loads(body)
        
        # Redact completion content
        content = data["choices"][0]["message"]["content"]
        redacted = await validate_completion(content)
        data["choices"][0]["message"]["content"] = redacted
        
        # Return with recalculated Content-Length
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(json.dumps(data), headers=headers)
```

### 5. Configuration (`src/sentinel/core/config.py`)

**Pattern:** Pydantic BaseSettings (environment-based)

```python
class Settings(BaseSettings):
    # Application
    environment: Literal["development", "staging", "production"]
    debug: bool = False
    log_level: str = "INFO"
    
    # OpenTelemetry
    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    
    # Guardrails
    enable_pii_redaction: bool = True
    enable_prompt_injection_detection: bool = True
    
    # Streaming
    stream_chunk_size: int = 512
    stream_buffer_size: int = 4096
    
    # LLM Provider Keys
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

### 6. Telemetry (`src/sentinel/core/telemetry.py`)

**Pattern:** Singleton TelemetryManager with lazy loading

**Features:**
- **Tracing:** OpenTelemetry gRPC (OTLP) exporter to Jaeger
- **Metrics:** Prometheus exporter with custom counters/histograms
- **Lazy Loading:** Tracer/meter only initialized when accessed (avoids conflicts)

**Integration Points:**
```
Validation Request
    ↓
[Span] proxy_middleware
    ├─ [Span] validate_prompt
    │  ├─ [Span] pii_redaction.validate
    │  └─ [Span] injection_detection.validate
    ├─ [Span] forward_to_provider
    └─ [Span] apply_streaming_guardrails
    ↓
[Export to Jaeger]
    ├─ Distributed trace ID
    ├─ Span timing
    ├─ Attributes (module, violations, etc.)
    └─ Status (OK/ERROR)
```

## Data Flow: Request → Response

### Scenario: Chat Completion with PII

```
1. Client sends:
   POST /v1/chat/completions
   {
     "messages": [{"role": "user", "content": "Email: john@example.com"}],
     "stream": false
   }

2. GuardrailProxyMiddleware.dispatch()
   - Skip check: Not in [/health, /metrics] ✓
   - Extract: content = "Email: john@example.com"

3. GuardrailEngine.validate_prompt()
   - PII Module: Detects EMAIL
     → Output: "Email: REDACTED_EMAIL"
     → is_safe: true
   - Injection Module: No patterns
     → is_safe: true
   - Combined: is_safe=true, processed_text="Email: REDACTED_EMAIL"

4. Forward to LLM provider with redacted text
   POST https://api.openai.com/v1/chat/completions
   {
     "messages": [{"role": "user", "content": "Email: REDACTED_EMAIL"}],
     ...
   }

5. Receive response:
   {
     "choices": [{"message": {"content": "The email REDACTED_EMAIL is invalid."}}]
   }

6. Outbound guardrails:
   - Validate completion: "The email REDACTED_EMAIL is invalid."
   - No new PII, no injection → safe
   - Pass through unchanged

7. Return to client:
   {
     "choices": [{"message": {"content": "The email REDACTED_EMAIL is invalid."}}],
     "guardrail_metadata": {...}
   }
```

### Scenario: Streaming with Split Pattern

```
1. Client: stream=true
2. Redact prompt: "admin; DROP TABLE" → Block (injection detected)
   OR
3. If prompt passes, forward with stream=true
4. Response arrives as SSE stream:
   
   Chunk 1: "data: {"choices":[{"delta":{"content":"Credit"}}]}\n\n"
   Chunk 2: "data: {"choices":[{"delta":{"content":" card: 1234-56"}}]}\n\n"
   Chunk 3: "data: {"choices":[{"delta":{"content":"78-9012"}}]}\n\n"
   
   Buffer tracks: "Credit card: 1234-56"
   
5. Chunk 2: Combined with buffer: "Credit card: 1234-5678"
   - No SSN match yet (incomplete)
6. Chunk 3: Combined buffer: "1234-5678-9012"
   - SSN match! Redact to "REDACTED_SSN"
   - Output: "Credit card: REDACTED_SSN"

7. Yield to client:
   "data: {"choices":[{"delta":{"content":"data: {"choices":[{"delta":{"content":" card: REDACTED_SSN"}}]}\n\n"
```

## Module Extension Points

To add custom guardrails:

1. **Implement `GuardrailModule`:**
   ```python
   class MyCustomModule(GuardrailModule):
       async def validate(self, text: str) -> GuardrailResponse:
           # Your logic here
           return GuardrailResponse(
               is_safe=False,
               processed_text=text,
               violations={"custom_pattern": 1}
           )
   ```

2. **Register in main.py lifespan:**
   ```python
   custom_module = MyCustomModule()
   guardrail_engine.register_module("my_custom", custom_module, priority=3)
   ```

3. **Module is now part of pipeline** with automatic trace reporting

## Performance Characteristics

| Operation | Time | Memory | Notes |
|-----------|------|--------|-------|
| PII (regex) | 1-2ms | <1MB | Per request, cached patterns |
| PII (presidio) | 50-200ms | 10-50MB | Async, non-blocking |
| Injection detection | <1ms | <100KB | Pattern matching |
| Stream chunk (512B) | <5ms | <1MB | Per chunk, buffered |
| Full request (avg) | 20-50ms | 5-20MB | Including network |

## Error Handling & Degradation

```
Success Path:
  Request → Validate → Forward → Response → Safe

Error Path (Guardrail Failure):
  Validate → ERROR → Log + Continue → Forward anyway
  (Non-blocking: guardrails fail-safe, don't block requests)

Example:
  Presidio model crash:
  - Regex path continues (fast path working)
  - Audit path skipped
  - Log error, continue with partial coverage
  - Client still gets response
```

## Security Considerations

1. **No Secret Leakage:** Redaction happens server-side, client never sees raw PII
2. **Pattern Completeness:** Regex patterns tested against common formats
3. **Injection Patterns:** Based on OWASP Top 10 and real-world exploits
4. **Audit Trail:** All violations logged with timestamps and trace IDs
5. **Thread Safety:** Fully async, no shared mutable state
6. **Input Validation:** Pydantic models enforce schema

## Scaling & High Availability

- **Horizontal Scaling:** Stateless design allows multiple instances
- **Load Balancing:** Round-robin across instances
- **Telemetry:** Traces aggregated in Jaeger/Prometheus
- **Health Checks:** `/health` endpoint for orchestrators
- **Graceful Shutdown:** Drains requests before stopping

---

For implementation details, see [API Reference](./API.md) and [Examples](./EXAMPLES.md).
