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
$MarkerEnd = "# End Waypoint block"
$Block = @"

$MarkerStart
# Session history shared by `cd` and `wp` jumps. `cd -` toggles to the previous
# location; `wp undo` / `wp history` use the CLI's persistent stack instead.
`$global:WpHistory = [System.Collections.Generic.List[string]]::new()
`$global:WpMaxHistory = 50

function Set-WaypointLocation {
    param(
        [switch]`$Literal,
        [Parameter(ValueFromRemainingArguments=`$true)]
        [string[]]`$PathArgs
    )
    `$target = `$PathArgs -join ' '
    if (`$target -eq '-') {
        if (`$global:WpHistory.Count -lt 2) {
            Write-Warning "No previous location in history."
            return
        }
        `$target = `$global:WpHistory[`$global:WpHistory.Count - 2]
    }
    `$before = (Get-Location).Path
    if (`$target) {
        if (`$Literal) { Set-Location -LiteralPath `$target } else { Set-Location -Path `$target }
    } else {
        Set-Location ~
    }
    `$current = (Get-Location).Path
    if (`$current -ne `$before) {
        & python "$RepoDir\waypoint\__main__.py" _record_history `$before > `$null 2>&1
        if (`$global:WpHistory.Count -eq 0 -or `$global:WpHistory[`$global:WpHistory.Count - 1] -ne `$before) {
            `$global:WpHistory.Add(`$before)
        }
        if (`$global:WpHistory.Count -eq 0 -or `$global:WpHistory[`$global:WpHistory.Count - 1] -ne `$current) {
            `$global:WpHistory.Add(`$current)
        }
        while (`$global:WpHistory.Count -gt `$global:WpMaxHistory) { `$global:WpHistory.RemoveAt(0) }
    }
}

# Override the built-in cd/chdir aliases so every directory change feeds history.
# cd's alias is AllScope; a plain -Force would try to drop that option and fail.
Set-Alias -Name cd -Value Set-WaypointLocation -Option AllScope -Scope Global -Force
Set-Alias -Name chdir -Value Set-WaypointLocation -Option AllScope -Scope Global -Force

function cdh {
    `$global:WpHistory
}

function wp {
    `$env:WP_FORCE_COLOR = if ([Environment]::UserInteractive) { "1" } else { "0" }
    # Commands that perform interactive rich prompts (Prompt.ask). Capturing stdout via @()
    # would buffer stdout on the pipe, causing invisible prompts. Run live.
    `$interactiveCmds = @('add')
    if (`$args.Count -gt 0 -and `$interactiveCmds -contains `$args[0]) {
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
            Set-WaypointLocation -Literal `$lines[0]
        } else {
            Write-Output `$lines[0]
        }
    } else {
        `$lines | ForEach-Object { Write-Output `$_ }
    }
}

$MarkerEnd

"@

$ProfilePath = if ($PROFILE.CurrentUserAllHosts) { $PROFILE.CurrentUserAllHosts } else { "$PROFILE" }
if (-not $ProfilePath) {
    $ProfilePath = "$HOME\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"
}

if (-not (Test-Path -LiteralPath $ProfilePath)) {
    New-Item -ItemType File -Path $ProfilePath -Force | Out-Null
}

$Existing = Get-Content -LiteralPath $ProfilePath -Raw -ErrorAction SilentlyContinue

if ($Existing -and $Existing -match [regex]::Escape($MarkerStart)) {
    # Replace the old block: the span from the start marker through the end
    # marker. The block contains blank lines internally, so boundary detection
    # cannot rely on "next blank line".
    $Lines = $Existing -split "`r?`n"
    $Start = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match [regex]::Escape($MarkerStart)) { $Start = $i; break }
    }
    $End = -1
    for ($i = $Start; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match [regex]::Escape($MarkerEnd)) { $End = $i; break }
    }
    if ($Start -ge 0 -and $End -ge $Start) {
        $Before = $Lines[0..($Start - 1)]
        $After = if ($End + 1 -lt $Lines.Count) { $Lines[($End + 1)..($Lines.Count - 1)] } else { @() }
        $NewContent = ($Before + $Block.TrimEnd() + $After) -join "`r`n"
        Set-Content -LiteralPath $ProfilePath -Value $NewContent -Encoding UTF8
        Write-Host "Waypoint updated in profile." -ForegroundColor Green
    } else {
        Write-Host "Waypoint block found but end marker missing; run repair." -ForegroundColor Red
        exit 1
    }
} else {
    Add-Content -LiteralPath $ProfilePath -Value $Block -Encoding UTF8
    Write-Host "Waypoint installed!" -ForegroundColor Green
}
Write-Host "Run uprof, then type:  wp" -ForegroundColor Yellow
