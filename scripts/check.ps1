# Unified quality check runner for Waypoint (ruff + mypy + pytest)
$ErrorActionPreference = "Stop"

Write-Host "==> Running ruff check..." -ForegroundColor Cyan
python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Running mypy check..." -ForegroundColor Cyan
python -m mypy waypoint
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Running pytest suite..." -ForegroundColor Cyan
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> All quality checks passed!" -ForegroundColor Green
