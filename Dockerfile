# Skeleton MCP Server Dockerfile
# Multi-stage build for development and production

FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Production stage
FROM base AS production
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uv", "run", "skeleton-mcp"]

# Development stage with additional tools
FROM base AS development

# Install Node.js for Claude Code CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install dev dependencies
RUN uv sync --frozen 2>/dev/null || uv sync

# Copy test files
COPY tests/ ./tests/

ENV PYTHONUNBUFFERED=1
CMD ["bash"]
