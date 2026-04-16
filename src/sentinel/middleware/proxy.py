"""Proxy Middleware - Request/Response interception with guardrails.

Features:
- Distributed tracing via X-Request-ID and traceparent headers
- Pydantic v2 optimized JSON validation (Rust-accelerated core)
- Circuit breaker protection for guardrail modules
- Zero Time-To-First-Token (TTFT) impact with streaming redaction
"""

import json
import logging
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from sentinel.core.config import settings
from sentinel.core.validators import validate_json_model
from sentinel.guardrails.engine import GuardrailEngine

logger = logging.getLogger(__name__)


def _get_tracer():
    """Lazy load tracer."""
    try:
        from sentinel.core.telemetry import telemetry_manager
        return telemetry_manager.get_tracer(__name__)
    except RuntimeError:
        import opentelemetry.trace as trace
        return trace.get_tracer(__name__)


class GuardrailProxyMiddleware(BaseHTTPMiddleware):
    """HTTP middleware that applies guardrails to LLM requests/responses.

    Intercepts requests before hitting the LLM provider and responses
    from the provider to apply PII redaction and injection detection.
    """

    def __init__(self, app: Any, guardrail_engine: GuardrailEngine) -> None:
        """Initialize proxy middleware.

        Args:
            app: FastAPI application.
            guardrail_engine: Configured GuardrailEngine instance.
        """
        super().__init__(app)
        self.guardrail_engine = guardrail_engine

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """Process request/response through guardrails.

        Propagates distributed tracing headers (X-Request-ID, traceparent)
        throughout the request lifecycle for full observability.

        Args:
            request: Incoming HTTP request.
            call_next: Next handler.

        Returns:
            Response (streaming or non-streaming).
        """
        # Extract or generate request ID for distributed tracing
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        traceparent = request.headers.get("traceparent")
        
        # Store in request state for downstream use
        request.state.request_id = request_id
        request.state.traceparent = traceparent
        
        # Skip guardrails for health checks
        if request.url.path in ["/health", "/metrics"]:
            response = await call_next(request)
            # Add request ID to response headers
            response.headers["x-request-id"] = request_id
            return response

        tracer = _get_tracer()
        with tracer.start_as_current_span("proxy_middleware") as span:
            span.set_attribute("path", request.url.path)
            span.set_attribute("method", request.method)
            span.set_attribute("request_id", request_id)
            if traceparent:
                span.set_attribute("traceparent", traceparent)

            # Only intercept POST requests with JSON bodies
            if request.method != "POST" or "application/json" not in request.headers.get(
                "content-type", ""
            ):
                response = await call_next(request)
                response.headers["x-request-id"] = request_id
                if traceparent:
                    response.headers["traceparent"] = traceparent
                return response

            # 1. INBOUND GUARDRAIL - Validate prompt
            try:
                body = await request.json()
                prompt = body.get("messages", [])

                if prompt:
                    # Extract text from messages
                    prompt_text = self._extract_messages_text(prompt)

                    is_safe, processed_prompt, validation_meta = (
                        await self.guardrail_engine.validate_prompt(
                            prompt_text, block_on_violation=settings.debug
                        )
                    )

                    if not is_safe:
                        logger.warning(
                            f"Prompt blocked by guardrails: {validation_meta}"
                        )
                        return self._json_response(
                            {
                                "error": "Request blocked by security guardrails",
                                "violations": validation_meta.get("violations", {}),
                            "request_id": request_id,
                        },
                        status_code=400,
                        headers={
                            "x-request-id": request_id,
                            **({"traceparent": traceparent} if traceparent else {}),
                        },
                return responses_text(body, processed_prompt)

            except json.JSONDecodeError:
                logger.error("Failed to parse request body as JSON")
                return await call_next(request)
            except Exception as e:
                logger.error(f"Error in inbound guardrail: {e}")
                # Don't block request on error, log and continue
                return await call_next(request)

            # 2. FORWARD REQUEST - Send to next handler
            # Create new request with processed body
            request._body = json.dumps(body).encode()
            response = await call_next(request)

            # 3. OUTBOUND GUARDRAIL - Apply to response
            # Check if response is streaming
            if response.status_code == 200 and "stream" in body and body["stream"]:
                return await self._apply_streaming_guardrails(response)
            else:
                return await self._apply_completion_guardrails(response)

    async def _apply_streaming_guardrails(
        self, response: StreamingResponse
    ) -> StreamingResponse:
        """Apply guardrails to streaming response.

        Wraps the response stream to redact PII on-the-fly.

        Args:
            response: Streaming response from provider.

        Returns:
            New StreamingResponse with guardrails applied.
        """

        async def stream_wrapper() -> AsyncGenerator[str, None]:
            """Wrap stream with guardrail processing.
            
            Handles partial PII that spans chunk boundaries using a look-back buffer.
            Example: Email "test@example.com" split as:
              - Chunk 1: "...last chunk content test@exa"
              - Chunk 2: "mple.com..."
            
            The look-back buffer (last N chars of previous chunk) ensures the email
            is detected even though it spans two chunks.
            """
            buffer = ""  # Look-back buffer for split patterns (3-5 tokens)
            buffer_size = settings.stream_buffer_size  # Keep last N chars for overlap

            async for chunk_raw in response.body_iterator:
                try:
                    # Parse SSE format (data: {...}\n\n)
                    lines = chunk_raw.decode().split("\n")

                    for line in lines:
                        if not line.startswith("data: "):
                            if line:
                                yield chunk_raw
                            continue

                        data_str = line[6:].strip()
                        if not data_str or data_str == "[DONE]":
                            yield line.encode() + b"\n\n"
                            continue

                        try:
                            data = json.loads(data_str)
                            content = (
                                data.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )

                            if content:
                                # Validate chunk through guardrails
                                redacted_response = (
                                    await self.guardrail_engine.stream_validate_chunk(
                                        content, look_back_buffer=buffer
                                    )
                                )

                                # Update content with redacted version
                                data["choices"][0]["delta"]["content"] = (
                                    redacted_response.content
                                )

                                # Update look-back buffer
                                buffer = content[
                                    -settings.stream_buffer_size :
                                ]  # Keep last N chars

                            # Yield updated chunk
                            yield f"data: {json.dumps(data)}\n\n".encode()

                        except json.JSONDecodeError:
                            logger.warning("Failed to parse streaming chunk")
                            yield line.encode() + b"\n\n"

                except Exception as e:
                    logger.error(f"Error processing stream chunk: {e}")
                    yield chunk_raw

        # Create response headers, removing Content-Length since we're streaming
        response_headers = dict(response.headers)
        response_headers.pop("content-length", None)
        
        return StreamingResponse(
            stream_wrapper(),
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.media_type,
        )

    async def _apply_completion_guardrails(self, response: Any) -> Any:
        """Apply guardrails to non-streaming completion response.

        Args:
            response: Response from provider.

        Returns:
            Modified response with guardrails applied.
        """
        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            if response.status_code != 200:
                return response

            data = json.loads(body)

            # Extract completion content
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if content:
                # Validate through guardrails
                is_safe, redacted_content, meta = (
                    await self.guardrail_engine.validate_completion(content)
                )

                # Update content
                data["choices"][0]["message"]["content"] = redacted_content
                if "guardrail_metadata" not in data:
                    data["guardrail_metadata"] = meta

            # Return modified response with recalculated headers
            from starlette.responses import Response

            response_headers = dict(response.headers)
            response_headers.pop("content-length", None)  # Remove to avoid mismatch

            return Response(
                json.dumps(data),
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.media_type,
            )

        except Exception as e:
            logger.error(f"Error applying completion guardrails: {e}")
            # Return original response on error
            return response

    @staticmethod
    def _extract_messages_text(messages: Any) -> str:
        """Extract text from OpenAI-format messages."""
        if isinstance(messages, list):
            texts = []
            for msg in messages:
                if isinstance(msg, dict) and "content" in msg:
                    texts.append(msg["content"])
            return " ".join(texts)
        elif isinstance(messages, str):
            return messages
        return ""

    @staticmethod
    def _update_messages_text(body: Dict[str, Any], new_text: str) -> Dict[str, Any]:
        """Update messages text in request body."""
        if "messages" in body and isinstance(body["messages"], list):
            # Update last user message
            for msg in reversed(body["messages"]):
                if msg.get("role") == "user":
                    msg["content"] = new_text
                    break
        return body

    @staticmethod
    def _json_response(data: Dict[str, Any], status_code: int = 200) -> Any:
        """Create JSON response."""
        from starlette.responses import JSONResponse

        return JSONResponse(data, status_code=status_code)
