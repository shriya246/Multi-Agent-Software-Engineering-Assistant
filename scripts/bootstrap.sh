#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export UV_CACHE_DIR="$ROOT_DIR/.uv-cache"

if [ ! -f "$ROOT_DIR/.env" ] && [ -f "$ROOT_DIR/.env.example" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

python -m uv sync --project "$ROOT_DIR/backend" --group dev
(cd "$ROOT_DIR/frontend" && npm install)
