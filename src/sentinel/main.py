"""FastAPI Application Entry Point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from sentinel.core.config import settings
from sentinel.core.telemetry import telemetry_manager
from sentinel.guardrails.engine import GuardrailEngine
from sentinel.guardrails.modules.pii import PIIRedactionModule
from sentinel.guardrails.modules.security import PromptInjectionDetectionModule
from sentinel.middleware.proxy import GuardrailProxyMiddleware

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Global guardrail engine
guardrail_engine = GuardrailEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # STARTUP
    logger.info(f"Starting {settings.app_name} (v{settings.version})")

    # Initialize telemetry
    try:
        telemetry_manager.initialize()
    except Exception as e:
        logger.error(f"Telemetry initialization failed: {e}")
        if settings.environment == "production":
            raise

    # Initialize guardrails
    try:
        # Register PII redaction module
        if settings.enable_pii_redaction:
            # Use regex-only for dev (faster), hybrid for prod
            use_presidio = settings.environment == "production"
            pii_module = PIIRedactionModule(use_regex=True, use_presidio=use_presidio)
            guardrail_engine.register_module("pii_redaction", pii_module, priority=2)

        # Register prompt injection detection module
        if settings.enable_prompt_injection_detection:
            injection_module = PromptInjectionDetectionModule()
            guardrail_engine.register_module(
                "prompt_injection", injection_module, priority=1
            )

        await guardrail_engine.setup()
        logger.info(
            f"Guardrail engine initialized with {len(guardrail_engine.list_modules())} modules"
        )
    except Exception as e:
        logger.error(f"Guardrail initialization failed: {e}")
        if settings.environment == "production":
            raise

    yield

    # SHUTDOWN
    logger.info("Shutting down application")

    try:
        await guardrail_engine.shutdown()
    except Exception as e:
        logger.error(f"Error shutting down guardrails: {e}")

    try:
        telemetry_manager.shutdown()
    except Exception as e:
        logger.error(f"Error shutting down telemetry: {e}")

    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Production-grade AI gateway with guardrails and observability",
    lifespan=lifespan,
    debug=settings.debug,
)

# Instrument FastAPI for OpenTelemetry
if settings.otel_enabled:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add guardrail proxy middleware
app.add_middleware(GuardrailProxyMiddleware, guardrail_engine=guardrail_engine)


# ==================== ROUTES ====================


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.version,
            "guardrails": guardrail_engine.get_stats(),
        }
    )


@app.get("/metrics", tags=["Metrics"])
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    try:
        from prometheus_client import REGISTRY, generate_latest

        metrics_output = generate_latest(REGISTRY).decode("utf-8")
        return Response(content=metrics_output, media_type="text/plain; charset=utf-8")
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/v1/chat/completions", tags=["Chat"])
async def chat_completion(request: Request) -> JSONResponse:
    """Chat completion endpoint compatible with OpenAI API.

    This endpoint:
    1. Validates inbound prompt through guardrails
    2. Forwards to upstream LLM provider
    3. Applies outbound redaction to completion

    The guardrail middleware handles all interception.
    """
    # This is a placeholder - actual logic is in the middleware
    body = await request.json()

    return JSONResponse(
        {
            "error": "This endpoint requires a configured LLM provider",
            "hint": "Set OPENAI_API_KEY and configure provider in settings",
        },
        status_code=501,
    )


@app.get("/guardrails/status", tags=["Guardrails"])
async def guardrails_status() -> JSONResponse:
    """Get guardrail engine status."""
    stats = guardrail_engine.get_stats()
    return JSONResponse(
        {
            "status": "operational" if stats["initialized"] else "not_initialized",
            "modules": stats["modules"],
            "count": stats["modules_count"],
        }
    )


@app.post("/guardrails/validate", tags=["Guardrails"])
async def validate_prompt(request: Request) -> JSONResponse:
    """Directly validate a prompt through guardrails.

    Used for testing/debugging guardrail configuration.

    Request body:
    {
        "text": "Prompt text to validate",
        "mode": "prompt" | "completion"
    }
    """
    try:
        body = await request.json()
        text = body.get("text", "")
        mode = body.get("mode", "prompt")

        if not text:
            return JSONResponse({"error": "text field required"}, status_code=400)

        if mode == "prompt":
            is_safe, processed, meta = await guardrail_engine.validate_prompt(text)
        elif mode == "completion":
            is_safe, processed, meta = await guardrail_engine.validate_completion(text)
        else:
            return JSONResponse(
                {"error": "mode must be 'prompt' or 'completion'"},
                status_code=400,
            )

        return JSONResponse(
            {
                "input_length": len(text),
                "output_length": len(processed),
                "is_safe": is_safe,
                "processed_text": processed,
                "metadata": meta,
            }
        )

    except Exception as e:
        logger.error(f"Validation error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ==================== ERROR HANDLERS ====================


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        {
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An error occurred",
        },
        status_code=500,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
