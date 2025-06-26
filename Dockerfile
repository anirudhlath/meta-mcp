# Multi-stage build for Meta MCP Server
FROM python:3.11-slim as builder

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

# Install dependencies and build
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy UV and virtual environment from builder
COPY --from=builder /bin/uv /bin/uv
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Set working directory
WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash metauser
RUN chown -R metauser:metauser /app
USER metauser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Create configuration directory
RUN mkdir -p /app/config /app/logs /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports
EXPOSE 3456 8080

# Default command
CMD ["python", "-m", "meta_mcp.main", "run", "--web-ui"]