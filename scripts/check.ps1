$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:UV_CACHE_DIR = Join-Path $root '.uv-cache'

Push-Location (Join-Path $root 'backend')
try {
  python -m uv run ruff check .
  python -m uv run mypy app
  python -m uv run pytest
}
finally {
  Pop-Location
}

Push-Location (Join-Path $root 'frontend')
try {
  npm.cmd run lint
  npm.cmd run typecheck
  npm.cmd test
}
finally {
  Pop-Location
}
