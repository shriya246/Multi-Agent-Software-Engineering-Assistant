#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export UV_CACHE_DIR="$ROOT_DIR/.uv-cache"

(
  cd "$ROOT_DIR/backend"
  python -m uv run ruff check .
  python -m uv run mypy app
  python -m uv run pytest
)
(
  cd "$ROOT_DIR/frontend"
  npm run lint
  npm run typecheck
  npm test
)
