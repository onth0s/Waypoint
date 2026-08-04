$RepoDir = "$PSScriptRoot".TrimEnd('\')

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found on PATH. Install Python 3.10+ first." -ForegroundColor Red
    exit 1
}

# Ensure the Python dependencies the CLI needs are importable.
python -c "import rich, pyperclip, yaml" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies: rich, pyperclip, pyyaml" -ForegroundColor Yellow
    python -m pip install rich pyperclip pyyaml
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install dependencies." -ForegroundColor Red
        exit 1
    }
}

# $RepoDir is interpolated here (baked into the profile). Function-body
# variables ($lines, $LASTEXITCODE, $args) must stay literal -> backtick-escape.
# The wrapper cds only when the CLI printed exactly one line that is an
# existing path (the navigation protocol).
$Line = @"

# Waypoint - path bookmark CLI (ASCII only: profiles may not be UTF-8)
function wp {
    `$env:WP_FORCE_COLOR = if ([Environment]::UserInteractive) { "1" } else { "0" }
    `$lines = @(& python "$RepoDir\waypoint\__main__.py" @args)
    Remove-Item Env:WP_FORCE_COLOR -ErrorAction SilentlyContinue
    if (`$LASTEXITCODE -eq 0 -and `$lines.Count -eq 1 -and `$lines[0]) {
        try {
            `$ok = Test-Path -LiteralPath `$lines[0] -ErrorAction Stop
        } catch {
            # Non-path single-line output (e.g. "Saved demo -> C:\...") must
            # never surface as a red error; it is just echoed below.
            `$ok = `$false
        }
        if (`$ok) {
            Set-Location -LiteralPath `$lines[0]
        } else {
            Write-Output `$lines[0]
        }
    } else {
        `$lines | ForEach-Object { Write-Output `$_ }
    }
}

"@

$ProfilePath = $PROFILE.CurrentUserAllHosts

if (-not (Test-Path -LiteralPath $ProfilePath)) {
    New-Item -ItemType File -Path $ProfilePath -Force | Out-Null
}

Add-Content -LiteralPath $ProfilePath -Value $Line -Encoding UTF8

Write-Host "Waypoint installed!" -ForegroundColor Green
Write-Host "Restart PowerShell, then type:  wp" -ForegroundColor Yellow
