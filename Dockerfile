FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY README.md .
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN pip install --no-cache-dir -e .

# Download spaCy model for NER
RUN python -m spacy download en_core_web_sm

# Expose port
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "sentinel.main:app", "--host", "0.0.0.0", "--port", "8000"]
