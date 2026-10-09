# AgentCore Runtime runs containers on ARM64 (Graviton).
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim

# uv installs the exact versions pinned in uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DOCKER_CONTAINER=1 \
    CREWAI_DISABLE_TELEMETRY=true \
    CREWAI_TRACING_ENABLED=false \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1. Dependencies first, so this layer is cached when only the code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2. Then the agent code.
COPY src ./src
RUN uv sync --frozen --no-dev

# Run as a non-root user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8080
CMD ["python", "-m", "subscription_auditor.agentcore_app"]
