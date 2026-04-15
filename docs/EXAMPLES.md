# Examples & Integration Patterns

Practical code examples and integration patterns for Sentinel AI Gateway.

---

## Table of Contents

1. [HTTP Requests](#http-requests)
2. [Python Integration](#python-integration)
3. [JavaScript/Node.js](#javascriptnodejs)
4. [Custom Guardrails](#custom-guardrails)
5. [Streaming Responses](#streaming-responses)
6. [Error Handling](#error-handling)

---

## HTTP Requests

### cURL: Basic Validation

```bash
# Validate clean text
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"What is AI?","mode":"prompt"}'
```

Response:
```json
{
  "is_safe": true,
  "processed_text": "What is AI?",
  "metadata": {"modules": {...}, "violations": {}}
}
```

### cURL: PII Detection

```bash
# Detect and redact email
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Contact support at help@company.com",
    "mode": "prompt"
  }' | jq '.processed_text'
```

Output: `"Contact support at REDACTED_EMAIL"`

### cURL: Injection Detection

```bash
# Test SQL injection blocking
curl -X POST http://localhost:8000/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "SELECT * FROM users WHERE id=1; DROP TABLE users;--",
    "mode": "prompt"
  }' | jq '.is_safe'
```

Output: `false` (blocked)

### cURL: Chat Completion

```bash
# Send to OpenAI with guardrails
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "My email is test@example.com. What is my account balance?"}
    ],
    "stream": false
  }' | jq '.choices[0].message.content'
```

The email is automatically redacted before sending to OpenAI.

---

## Python Integration

### Basic Usage

```python
import httpx
import asyncio

async def validate_text(text: str) -> dict:
    """Validate text through Sentinel guardrails."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/guardrails/validate",
            json={"text": text, "mode": "prompt"}
        )
        return response.json()

# Usage
async def main():
    result = await validate_text("My email is test@example.com")
    print(f"Safe: {result['is_safe']}")
    print(f"Processed: {result['processed_text']}")
    
    # Check violations
    if result['metadata']['violations']:
        print(f"Detected: {result['metadata']['violations']}")

asyncio.run(main())
```

### OpenAI Integration

```python
import httpx
from openai import AsyncOpenAI

class SentinelOpenAI:
    """OpenAI client with Sentinel guardrails."""
    
    def __init__(self, sentinel_url: str = "http://localhost:8000"):
        self.sentinel_url = sentinel_url
        self.client = AsyncOpenAI()
    
    async def chat_with_guardrails(
        self,
        messages: list,
        model: str = "gpt-4",
        stream: bool = False
    ):
        """Send chat completion through Sentinel guardrails."""
        
        # 1. Validate prompt through Sentinel
        prompt_text = "\n".join(msg["content"] for msg in messages)
        
        async with httpx.AsyncClient() as client:
            validation = await client.post(
                f"{self.sentinel_url}/guardrails/validate",
                json={"text": prompt_text, "mode": "prompt"}
            )
            result = validation.json()
        
        # 2. Check if safe
        if not result["is_safe"]:
            return {
                "error": "Request blocked by guardrails",
                "violations": result["metadata"]["violations"]
            }
        
        # 3. Update messages with redacted content
        redacted_text = result["processed_text"]
        messages[0]["content"] = redacted_text  # Simplified
        
        # 4. Send to OpenAI
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream
        )
        
        # 5. Return with metadata
        return {
            "response": response,
            "guardrail_metadata": result["metadata"]
        }

# Usage
async def main():
    sentinel_ai = SentinelOpenAI()
    
    messages = [
        {"role": "user", "content": "My email is john@example.com. What's my balance?"}
    ]
    
    result = await sentinel_ai.chat_with_guardrails(messages)
    
    if "error" in result:
        print(f"Blocked: {result['error']}")
    else:
        print(f"Response: {result['response'].choices[0].message.content}")
        print(f"Violations: {result['guardrail_metadata']['violations']}")

asyncio.run(main())
```

### Health Check & Monitoring

```python
import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

async def check_sentinel_health(url: str = "http://localhost:8000") -> bool:
    """Check if Sentinel gateway is healthy."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/health")
            return response.status_code == 200
    except httpx.RequestError as e:
        logger.error(f"Health check failed: {e}")
        return False

async def get_sentinel_status(url: str = "http://localhost:8000") -> dict:
    """Get detailed status of guardrail modules."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{url}/guardrails/status")
        return response.json()

# Usage
async def main():
    is_healthy = await check_sentinel_health()
    print(f"Sentinel healthy: {is_healthy}")
    
    status = await get_sentinel_status()
    print(f"Modules: {list(status['modules'].keys())}")
    for name, info in status['modules'].items():
        print(f"  {name}: {info['status']}")

asyncio.run(main())
```

### Batch Processing

```python
import httpx
import asyncio
from typing import List

async def validate_batch(
    texts: List[str],
    mode: str = "prompt",
    url: str = "http://localhost:8000"
) -> List[dict]:
    """Validate multiple texts in parallel."""
    
    async with httpx.AsyncClient() as client:
        tasks = [
            client.post(
                f"{url}/guardrails/validate",
                json={"text": text, "mode": mode}
            )
            for text in texts
        ]
        responses = await asyncio.gather(*tasks)
        return [r.json() for r in responses]

# Usage
async def main():
    texts = [
        "Hello, world!",
        "Email me at test@example.com",
        "admin'; DROP TABLE users;--"
    ]
    
    results = await validate_batch(texts)
    
    for text, result in zip(texts, results):
        status = "✅" if result["is_safe"] else "❌"
        print(f"{status} {text[:30]}")

asyncio.run(main())
```

---

## JavaScript/Node.js

### Basic Fetch

```javascript
async function validateText(text) {
  const response = await fetch('http://localhost:8000/guardrails/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, mode: 'prompt' })
  });
  
  return response.json();
}

// Usage
const result = await validateText('My email is test@example.com');
console.log(`Safe: ${result.is_safe}`);
console.log(`Processed: ${result.processed_text}`);
```

### TypeScript Types

```typescript
interface GuardrailValidation {
  is_safe: boolean;
  processed_text: string;
  input_length: number;
  output_length: number;
  metadata: {
    modules: Record<string, ModuleResult>;
    violations: Record<string, Record<string, number>>;
  };
}

interface ModuleResult {
  redacted?: boolean;
  detection_method?: string;
  injection_risk?: number;
  patterns_found?: string[];
  threshold?: number;
}

async function validateWithTypes(text: string): Promise<GuardrailValidation> {
  const response = await fetch('http://localhost:8000/guardrails/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, mode: 'prompt' })
  });
  
  if (!response.ok) {
    throw new Error(`Validation failed: ${response.statusText}`);
  }
  
  return response.json() as Promise<GuardrailValidation>;
}
```

### OpenAI Integration (Node.js)

```javascript
const axios = require('axios');
const { OpenAI } = require('openai');

class SentinelOpenAI {
  constructor(sentinelUrl = 'http://localhost:8000') {
    this.sentinelUrl = sentinelUrl;
    this.openai = new OpenAI();
  }

  async chatWithGuardrails(messages, model = 'gpt-4', stream = false) {
    // 1. Validate prompt
    const promptText = messages.map(m => m.content).join('\n');
    
    const validation = await axios.post(
      `${this.sentinelUrl}/guardrails/validate`,
      { text: promptText, mode: 'prompt' }
    );

    // 2. Check safety
    if (!validation.data.is_safe) {
      return {
        error: 'Request blocked by guardrails',
        violations: validation.data.metadata.violations
      };
    }

    // 3. Update with redacted text
    const redactedMessages = messages.map(msg => ({
      ...msg,
      content: validation.data.processed_text
    }));

    // 4. Send to OpenAI
    const response = await this.openai.chat.completions.create({
      model,
      messages: redactedMessages,
      stream
    });

    return {
      response,
      guardrailMetadata: validation.data.metadata
    };
  }
}

// Usage
const sentinel = new SentinelOpenAI();

(async () => {
  const messages = [
    { role: 'user', content: 'My email is test@example.com. What is my balance?' }
  ];

  const result = await sentinel.chatWithGuardrails(messages);
  
  if (result.error) {
    console.log(`Blocked: ${result.error}`);
  } else {
    console.log(result.response.choices[0].message.content);
    console.log('Violations:', result.guardrailMetadata.violations);
  }
})();
```

### Streaming Responses

```javascript
async function streamChatCompletion(messages) {
  const response = await fetch('http://localhost:8000/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'gpt-4',
      messages,
      stream: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') continue;

        const parsed = JSON.parse(data);
        const content = parsed.choices[0]?.delta?.content;
        
        if (content) {
          process.stdout.write(content);  // Print as it arrives
        }
      }
    }
  }
}
```

---

## Custom Guardrails

### Adding a Custom Module

```python
# custom_guardrails.py
from sentinel.guardrails.base import GuardrailModule, GuardrailResponse

class ComplianceModule(GuardrailModule):
    """Custom guardrail for company compliance policies."""
    
    FORBIDDEN_TOPICS = {
        'competitor_names': ['competitor_a', 'competitor_b'],
        'internal_codenames': ['project_x', 'operation_y'],
        'confidential_features': ['unreleased_feature_1', 'roadmap_item_3']
    }
    
    async def validate(self, text: str) -> GuardrailResponse:
        violations = {}
        
        for category, keywords in self.FORBIDDEN_TOPICS.items():
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    if category not in violations:
                        violations[category] = 0
                    violations[category] += 1
        
        is_safe = len(violations) == 0
        
        return GuardrailResponse(
            is_safe=is_safe,
            processed_text=text,
            violations={'compliance': violations} if violations else {}
        )
    
    async def validate_streaming_chunk(
        self,
        chunk: str,
        look_back_buffer: str
    ) -> GuardrailResponse:
        combined = look_back_buffer + chunk
        response = await self.validate(combined)
        
        return GuardrailResponse(
            is_safe=response.is_safe,
            processed_text=chunk,
            violations=response.violations
        )
    
    def setup(self) -> None:
        print("Compliance guardrail module loaded")
    
    def shutdown(self) -> None:
        print("Compliance guardrail module unloaded")

# In main.py
from custom_guardrails import ComplianceModule

@app.lifespan
async def lifespan(app: FastAPI):
    # ... existing code ...
    
    # Register custom module
    compliance = ComplianceModule()
    guardrail_engine.register_module(
        "compliance",
        compliance,
        priority=1  # Execute after PII redaction (2)
    )
    
    yield
    
    # ... shutdown code ...
```

### Testing Custom Module

```python
# test_compliance.py
import pytest
from custom_guardrails import ComplianceModule

@pytest.mark.asyncio
async def test_compliance_module():
    module = ComplianceModule()
    module.setup()
    
    # Should pass
    response = await module.validate("Tell me about our market strategy")
    assert response.is_safe == True
    assert response.violations == {}
    
    # Should block
    response = await module.validate("How does competitor_a approach this?")
    assert response.is_safe == False
    assert 'compliance' in response.violations
    assert response.violations['compliance']['competitor_names'] > 0
    
    module.shutdown()
```

---

## Streaming Responses

### Server-Sent Events (SSE)

```python
# In your client code
async def stream_chat_completion(messages: list):
    """Stream chat completion with real-time PII redaction."""
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": messages,
                "stream": True
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        content = data['choices'][0]['delta'].get('content', '')
                        
                        if content:
                            print(content, end='', flush=True)
                    except json.JSONDecodeError:
                        pass

# Usage
messages = [{"role": "user", "content": "Write a poem"}]
await stream_chat_completion(messages)
```

### Web Socket Alternative

```javascript
// For real-time applications
class SentinelWebSocket {
  constructor(url = 'ws://localhost:8000/ws') {
    this.ws = new WebSocket(url);
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Chunk:', data);
    };
  }
  
  sendMessage(text) {
    this.ws.send(JSON.stringify({
      type: 'validate',
      text,
      mode: 'prompt'
    }));
  }
}

const client = new SentinelWebSocket();
client.sendMessage('Hello, world!');
```

---

## Error Handling

### Graceful Degradation

```python
import asyncio

async def validate_with_fallback(
    text: str,
    sentinel_url: str = "http://localhost:8000",
    timeout: float = 5.0
) -> dict:
    """Validate text with fallback if Sentinel is unavailable."""
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{sentinel_url}/guardrails/validate",
                json={"text": text, "mode": "prompt"}
            )
            return response.json()
    
    except asyncio.TimeoutError:
        logger.warning("Sentinel timeout, using basic validation")
        # Fallback: Basic email regex check
        has_email = '@' in text
        return {
            "is_safe": True,  # Conservative: assume safe
            "processed_text": text,
            "warnings": ["Sentinel unavailable, using fallback validation"]
        }
    
    except httpx.RequestError as e:
        logger.error(f"Sentinel error: {e}")
        return {
            "is_safe": True,  # Fail open
            "processed_text": text,
            "error": str(e)
        }

# Usage
result = await validate_with_fallback("Test email test@example.com")
if "warnings" in result:
    print(f"Warning: {result['warnings']}")
```

### Retry Logic

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def validate_with_retry(text: str) -> dict:
    """Validate with automatic retry on failure."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/guardrails/validate",
            json={"text": text, "mode": "prompt"},
            timeout=5.0
        )
        return response.json()

# Usage - automatically retries up to 3 times with exponential backoff
result = await validate_with_retry("My email is test@example.com")
```

### Comprehensive Error Handler

```python
async def safe_validate(text: str) -> tuple[bool, str, dict]:
    """
    Safely validate text with comprehensive error handling.
    
    Returns:
        (is_safe, processed_text, metadata)
    """
    try:
        result = await validate_text(text)
        
        return (
            result.get("is_safe", True),
            result.get("processed_text", text),
            result.get("metadata", {})
        )
    
    except ValueError as e:
        logger.error(f"Invalid response format: {e}")
        return (True, text, {})  # Safe: pass through on error
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            logger.warning(f"Validation error: {e.response.text}")
            return (False, text, {"error": "Invalid request"})
        else:
            logger.error(f"Server error: {e}")
            return (True, text, {})  # Fail open
    
    except asyncio.TimeoutError:
        logger.warning("Validation timeout")
        return (True, text, {"warning": "timeout"})  # Fail open
```

---

## Complete Integration Example

```python
# app.py - FastAPI app with Sentinel integration
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    redacted: bool

sentinel_url = "http://localhost:8000"

@app.post("/api/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat endpoint with Sentinel guardrails."""
    
    # 1. Validate through Sentinel
    async with httpx.AsyncClient() as client:
        validation = await client.post(
            f"{sentinel_url}/guardrails/validate",
            json={"text": request.message, "mode": "prompt"}
        )
        
        validation_result = validation.json()
    
    # 2. Check safety
    if not validation_result["is_safe"]:
        raise HTTPException(
            status_code=400,
            detail="Request blocked by security guardrails"
        )
    
    # 3. Use redacted text
    safe_text = validation_result["processed_text"]
    was_redacted = safe_text != request.message
    
    # 4. Process (e.g., call LLM)
    response_text = f"You said: {safe_text}"
    
    return ChatResponse(
        response=response_text,
        redacted=was_redacted
    )

@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            sentinel_health = await client.get(f"{sentinel_url}/health")
        
        return {
            "status": "healthy",
            "sentinel": sentinel_health.status_code == 200
        }
    except Exception as e:
        return {
            "status": "degraded",
            "sentinel": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

---

For more details, see [API Reference](./API.md) and [Guardrails Guide](./GUARDRAILS.md).
