# syntax=docker/dockerfile:1.7

FROM python:3.11.4-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
WORKDIR /app

FROM base AS build
RUN python -m pip install --no-cache-dir uv==0.11.21
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --project /app

FROM base AS development
RUN useradd --create-home --shell /bin/bash codepilot
RUN python -m pip install --no-cache-dir uv==0.11.21
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group dev --project /app
COPY . .
RUN chown -R codepilot:codepilot /app
USER codepilot
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
RUN useradd --create-home --shell /bin/bash codepilot
RUN python -m pip install --no-cache-dir uv==0.11.21
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --project /app
COPY . .
RUN chown -R codepilot:codepilot /app
USER codepilot
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
