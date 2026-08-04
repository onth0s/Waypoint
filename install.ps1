$RepoDir = "$PSScriptRoot".TrimEnd('\')

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found on PATH. Install Python 3.10+ first." -ForegroundColor Red
    exit 1
}

python -c "import rich, pyperclip, yaml" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies via pyproject.toml..." -ForegroundColor Yellow
    python -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install dependencies." -ForegroundColor Red
        exit 1
    }
}

# $RepoDir is interpolated here (baked into the profile). Function-body
# variables ($lines, $LASTEXITCODE, $args) must stay literal -> backtick-escape.
# The wrapper cds only when the CLI printed exactly one line that is an
# existing path (the navigation protocol).
$MarkerStart = "# Waypoint - path bookmark CLI (ASCII only: profiles may not be UTF-8)"
$Block = @"

$MarkerStart
function wp {
    `$env:WP_FORCE_COLOR = if ([Environment]::UserInteractive) { "1" } else { "0" }
    # add prompts for a name via rich Prompt.ask; @() capture would swallow the
    # prompt (stdout is a pipe), leaving the user typing blind. Run it live.
    # Any future prompting command must be added to this list.
    if (`$args.Count -gt 0 -and `$args[0] -eq 'add') {
        & python "$RepoDir\waypoint\__main__.py" @args
        Remove-Item Env:WP_FORCE_COLOR -ErrorAction SilentlyContinue
        return
    }
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

$ProfilePath = "$HOME\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"

if (-not (Test-Path -LiteralPath $ProfilePath)) {
    New-Item -ItemType File -Path $ProfilePath -Force | Out-Null
}

$Existing = Get-Content -LiteralPath $ProfilePath -Raw -ErrorAction SilentlyContinue

if ($Existing -and $Existing -match [regex]::Escape($MarkerStart)) {
    # Replace the old block: everything from marker to the next blank line (or EOF).
    $Lines = $Existing -split "`r?`n"
    $Start = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match [regex]::Escape($MarkerStart)) { $Start = $i; break }
    }
    if ($Start -ge 0) {
        $End = $Start
        while ($End -lt $Lines.Count -and $Lines[$End] -ne "") { $End++ }
        $Before = $Lines[0..($Start - 1)]
        $After = if ($End -lt $Lines.Count) { $Lines[$End..($Lines.Count - 1)] } else { @() }
        $NewContent = ($Before + $Block.TrimEnd() + $After) -join "`r`n"
        Set-Content -LiteralPath $ProfilePath -Value $NewContent -Encoding UTF8
        Write-Host "Waypoint updated in profile." -ForegroundColor Green
    }
} else {
    Add-Content -LiteralPath $ProfilePath -Value $Block -Encoding UTF8
    Write-Host "Waypoint installed!" -ForegroundColor Green
}
Write-Host "Run uprof, then type:  wp" -ForegroundColor Yellow
