# sentinel-ai-gateway

Production-grade security middleware for LLM applications. Automatically redacts PII, blocks prompt injections, and monitors all requests with zero code changes.

![Sentinel Architecture](./docs/architecture-diagram.svg)

## ⚡ Quick Features

✅ **PII Redaction** - Hybrid regex + AI (Presidio) for emails, SSNs, phone, credit cards  
✅ **Injection Prevention** - Blocks SQL injection, command execution, jailbreaks  
✅ **Streaming-Safe** - Real-time redaction for SSE/streaming responses  
✅ **Observable** - OpenTelemetry traces + Prometheus metrics built-in  
✅ **Production-Ready** - v0.1.0 includes Docker, async/await, error handling  

## 🚀 Quick Start

### Installation

See [SETUP.md](./docs/SETUP.md) for detailed environment setup, Python versions, and API key configuration.

```bash
git clone https://github.com/your-org/sentinel-ai-gateway.git
cd sentinel-ai-gateway
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
python -m uvicorn sentinel.main:app --reload
```

Server runs at `http://localhost:8000`

## 📊 How It Works

```
Client Prompt ──┐
                ├──> Guardrail Engine ──┐
                │                       ├──> LLM Provider ──> Response Redaction ──> Safe User Response
                │   [PII Detection]    │
                │   [Injection Block]  │
                └───────────────────────┘
```

**Phase 1 (Inbound):** Validate prompt for PII and injection attempts  
**Phase 2 (Processing):** Route to LLM provider with redacted prompt  
**Phase 3 (Outbound):** Stream response with real-time redaction + violation logging  

Performance: ~1-2ms (regex), ~50-200ms (Presidio NER), <1ms (injection detection)

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **[SETUP.md](./docs/SETUP.md)** | Installation, environment config, LLM providers |
| **[API.md](./docs/API.md)** | Complete endpoint reference with examples |
| **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** | System design, streaming details, module deep-dive |
| **[GUARDRAILS.md](./docs/GUARDRAILS.md)** | PII patterns, injection detection, custom modules |
| **[DEPLOYMENT.md](./docs/DEPLOYMENT.md)** | Docker, Kubernetes, AWS ECS, monitoring |
| **[EXAMPLES.md](./docs/EXAMPLES.md)** | Code samples: Python, JavaScript, cURL |
| **[TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)** | Common issues & solutions |

## 🔌 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Liveness check |
| `GET` | `/guardrails/status` | Module status |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/guardrails/validate` | Direct text validation |
| `POST` | `/v1/chat/completions` | OpenAI-compatible proxy |

**Example:**

```bash
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"Email: john@example.com, SSN: 123-45-6789","mode":"prompt"}'

# Response:
{
  "is_safe": true,
  "processed_text": "Email: REDACTED_EMAIL, SSN: REDACTED_SSN",
  "metadata": {"violations": {"EMAIL": 1, "SSN": 1}}
}
```

## 🔧 Configuration

**Required environment variables** (see `.env.example`):

```env
# LLM Provider (choose at least one)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...

# Guardrails
ENABLE_PII_REDACTION=true
ENABLE_PROMPT_INJECTION_DETECTION=true

# Streaming
STREAM_CHUNK_SIZE=512
STREAM_BUFFER_SIZE=4096
```

**Optional:**

```env
LOG_LEVEL=INFO
ENVIRONMENT=production
OTEL_ENABLED=true
```

See [SETUP.md](./docs/SETUP.md) for all ~20 configuration options.

## 🎯 Key Principles

1. **Zero Code Changes** - Works as transparent middleware without modifying client/LLM code
2. **Streaming-First** - Generator-wrapper pattern for low-latency on-the-fly redaction
3. **Hybrid Detection** - Fast regex for streaming + Presidio for audit trails (no blocking)
4. **Graceful Degradation** - Failures in one module don't stop other guardrails
5. **Observable by Default** - Every request traced, every violation logged

## 📈 v0.1.0 Features

• **PII Detection** - 6 regex patterns + Presidio NER (email, SSN, phone, CC, IP, ZIP)  
• **Injection Prevention** - 6 attack patterns with configurable severity thresholds  
• **Split-Pattern Detection** - Look-back buffer handles patterns split across chunks  
• **Streaming Handler** - Async generator for zero-copy response redaction  
• **Middleware Interception** - Request/response processing via FastAPI middleware  
• **Observability** - OpenTelemetry + Prometheus integration  
• **Test Suite** - 16/16 tests passing, 36% coverage, production-ready  

## 📦 Project Structure

```
src/sentinel/
├── core/
│   ├── config.py           # Pydantic BaseSettings
│   └── telemetry.py        # OpenTelemetry setup
├── guardrails/
│   ├── engine.py           # Module orchestration
│   ├── base.py             # Abstract guardrail module
│   └── modules/
│       ├── pii.py          # PII redaction
│       └── security.py     # Injection detection
├── middleware/
│   └── proxy.py            # HTTP interception layer
├── services/
│   └── llm_client.py       # Async LLM providers
└── main.py                 # FastAPI entry point

tests/
├── test_guardrails.py      # Module tests
└── test_engine.py          # Integration tests

docs/
├── architecture-diagram.svg # Animated diagram
├── SETUP.md, API.md, ...   # Full documentation
```

## 🧪 Testing & Development

```bash
pytest                              # Run all tests
pytest --cov=sentinel              # With coverage
pytest -v --tb=short              # Verbose output

black src tests && ruff check       # Format & lint
docker-compose up -d               # Full stack (with Jaeger + Prometheus)
```

See [SETUP.md](./docs/SETUP.md) for local development and debugging.

## 🔐 Guardrail Modules

**PII Redaction Module** (`src/sentinel/guardrails/modules/pii.py`)
- Regex patterns: email, phone, SSN, credit card, IP, ZIP  
- Presidio NER for comprehensive detection  
- Streaming-safe with look-back buffer  

**Prompt Injection Detection** (`src/sentinel/guardrails/modules/security.py`)
- SQL injection, command injection, jailbreak, LDAP, XML, template injection  
- Risk scoring (0-1 scale) with configurable threshold  
- Custom pattern support  

## 📊 Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| PII (regex) | 1-2ms | Streaming path (default) |
| Injection detect | <1ms | Pattern matching |
| Presidio NER | 50-200ms | Audit path (async, non-blocking) |
| End-to-end | 5-50ms | Full validation pipeline |

## 🤝 Contributing

1. Fork the repo
2. Create feature branch: `git checkout -b feature/awesome`
3. Make changes, add tests to `tests/`
4. Format: `black src tests`
5. Lint: `ruff check src tests`
6. Ensure tests pass: `pytest`
7. Push and submit PR

## 📄 License

MIT License - See [LICENSE](./LICENSE) file

## 💬 Support

- **Questions?** → [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)
- **Issues:** [GitHub Issues](https://github.com/your-org/sentinel-ai-gateway/issues)
- **Docs:** [Full Documentation](./docs/README.md)
- **Examples:** [EXAMPLES.md](./docs/EXAMPLES.md)

---

**Built for production with streaming-first architecture and zero-copy redaction patterns.**