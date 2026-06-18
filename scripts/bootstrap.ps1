$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:UV_CACHE_DIR = Join-Path $root '.uv-cache'

if (-not (Test-Path -LiteralPath (Join-Path $root '.env')) -and (Test-Path -LiteralPath (Join-Path $root '.env.example'))) {
  Copy-Item -LiteralPath (Join-Path $root '.env.example') -Destination (Join-Path $root '.env')
}

python -m uv sync --project (Join-Path $root 'backend') --group dev
Push-Location (Join-Path $root 'frontend')
try {
  npm.cmd install
}
finally {
  Pop-Location
}
