# sentinel-ai-gateway

Production-grade security middleware for LLM applications. Automatically redacts PII, blocks prompt injections, and monitors all requests with zero code changes.

![Sentinel Architecture](./docs/architecture-diagram.svg)

## ⚡ Quick Features

✅ **PII Redaction** - Hybrid regex + AI (Presidio) detection  
✅ **Injection Prevention** - SQL injection, command execution, jailbreaks  
✅ **Streaming-Safe** - Real-time redaction for SSE/streaming responses  
✅ **Observable** - OpenTelemetry traces + Prometheus metrics  
✅ **Docker-Ready** - v0.1.0, async/await, production-grade  

## 🚀 Quick Start

**Docker (Recommended):**
```bash
git clone https://github.com/your-org/sentinel-ai-gateway.git
cd sentinel-ai-gateway
docker-compose up -d
```

Server runs at `http://localhost:8000`

See [QUICKSTART.md](./docs/QUICKSTART.md) for detailed setup and configuration.

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [QUICKSTART.md](./docs/QUICKSTART.md) | Installation, configuration, deployment |
| [API.md](./docs/API.md) | Endpoint reference with examples |
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | System design, guardrails, custom modules |
| [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) | Common issues, Grafana monitoring |

## 🔌 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Liveness check |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/guardrails/validate` | Direct text validation |
| `POST` | `/v1/chat/completions` | OpenAI-compatible proxy |

**Example:**
```bash
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"Email: john@example.com, SSN: 123-45-6789","mode":"prompt"}'
```

## 📊 Monitoring with Grafana

**Pre-configured dashboards and visualization stack:**

- **Grafana** (http://localhost:3000) - Interactive dashboards (user: `admin`, pass: `admin`)
  - Memory usage (resident & virtual)
  - CPU usage rate  
  - Garbage collection activity
  - Open file descriptors
  - Request metrics
  
- **Prometheus** (http://localhost:9090) - Metrics collection & PromQL queries
- **Jaeger** (http://localhost:16686) - Distributed tracing

See [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) for detailed monitoring guides and PromQL queries.

## 🔐 Guardrail Modules

**PII Redaction** - Email, phone, SSN, credit card, IP, ZIP with Presidio NER  
**Injection Detection** - SQL, command, jailbreak, LDAP, XML, template injection patterns

## 📊 Performance

| Operation | Latency |
|-----------|---------|
| PII (regex) | 1-2ms |
| Injection detect | <1ms |
| Presidio NER | 50-200ms |

## 🎯 Key Principles

1. **Zero Code Changes** - Transparent middleware layer
2. **Streaming-First** - Generator-wrapper for on-the-fly redaction
3. **Hybrid Detection** - Fast regex + Presidio audit trail
4. **Graceful Degradation** - Failures don't block requests
5. **Observable by Default** - Full tracing & metrics

## 🧪 Testing

```bash
pytest                              # Run tests
pytest --cov=sentinel              # With coverage
docker-compose up -d               # Full stack with Jaeger + Prometheus
```

## 🤝 Contributing

1. Fork repo
2. Create feature branch: `git checkout -b feature/name`
3. Make changes, add tests
4. Format: `black src tests`
5. Ensure tests pass: `pytest`
6. Submit PR

## 📄 License

MIT License - See [LICENSE](./LICENSE)

## 💬 Support

- **Questions?** → [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)
- **API Details?** → [API.md](./docs/API.md)
- **Architecture?** → [ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- **Issues:** [GitHub Issues](https://github.com/your-org/sentinel-ai-gateway/issues)

---

**Built for production with streaming-first architecture and zero-code integration.**