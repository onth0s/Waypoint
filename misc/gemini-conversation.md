
## User

for history tracking, is there any tool already? or do I need to write a lean 'cd' wrapper that handles history?

## Agent

## Option 2: Write a Lean `cd` Wrapper (If you want exact `cd -` behavior)

If you just want simple **`cd -` style back-and-forth toggling** or a clean FIFO history buffer without fuzzy-matching or heavy database tracking, writing a tiny wrapper around `Set-Location` in PowerShell is super easy.

Here is a minimal, self-contained snippet you can add directly to your `$PROFILE`:

PowerShell
```
# Store up to 20 recent paths in a global list

$global:LocationHistory = [System.Collections.Generic.List[string]]::new()

$global:MaxHistorySize = 20



function Set-LocationWithHistory {

param(

[Parameter(Position=0)]

[string]$Path

)



# Handle `cd -` to jump to the previous directory

if ($Path -eq '-') {

if ($global:LocationHistory.Count -gt 1) {

# The previous directory is second-to-last in history

$target = $global:LocationHistory[$global:LocationHistory.Count - 2]

Set-Location $target

return

} else {

Write-Warning "No previous directory in history."

return

}

}



# Standard navigation

if ($Path) {

Set-Location $Path

} else {

Set-Location ~

}



# Record current directory to history if it's new

$current = (Get-Location).Path

if ($global:LocationHistory.Count -eq 0 -or $global:LocationHistory[-1] -ne $current) {

$global:LocationHistory.Add($current)

if ($global:LocationHistory.Count -gt $global:MaxHistorySize) {

$global:LocationHistory.RemoveAt(0)

}

}

}



# Alias `cd` or `chdir` to use the wrapper

Set-Alias -Name cd -Value Set-LocationWithHistory -Option Option -Scope Global -Force

```


### Quick Helper Commands You Can Add To It:


- **Show history:**

PowerShell
```
function cdh { $global:LocationHistory }

```

- **Integrate with `Waypoint`:** If you want `Waypoint` jumps to also feed into this history list, your `wp` PowerShell wrapper function can simply append `$env:TARGET_PATH` to `$global:LocationHistory` whenever a jump occurs.


## Recommendation


- **Go with `zoxide`** if you want zero-effort, automatic history tracking across session restarts with smart fuzzy searching.


- **Go with the lean wrapper** if you just want deterministic `cd -` toggling and an in-memory stack that stays 100% inside your PowerShell session.

## User

yeah, I'd like Waypoint to straight up capture 'cd' with its own wrapper and set it up with _install.ps1_. should be simple, right?

## Agent

Yes, overall it is very straightforward! However, in PowerShell, capturing `cd` has **one minor quirk** you need to handle: `cd` is already built into PowerShell as a native alias for `Set-Location`.

Because of that, you can't just define a function called `cd` and call it a day—you have to explicitly clear or overwrite the default alias first.

Here is the straightforward architecture for adding this to your project.


## 1. Update `install.ps1`

When your `install.ps1` appends logic to `$PROFILE`, overwrite the `cd` alias with a custom wrapper function.

Here is what `install.ps1` should append to `$PROFILE`:

PowerShell
```
# --- Waypoint & History Integration ---

$global:WpHistory = [System.Collections.Generic.List[string]]::new()



# Overwrite default 'cd' alias so it points to our wrapper function

Set-Alias -Name cd -Value Set-WaypointLocation -Option Option -Scope Global -Force



function Set-WaypointLocation {

param(

[Parameter(ValueFromRemainingArguments=$true)]

[string[]]$PathArgs

)



$targetPath = $PathArgs -join ' '



# Handle `cd -` for quick toggling

if ($targetPath -eq '-') {

if ($global:WpHistory.Count -gt 1) {

$targetPath = $global:WpHistory[$global:WpHistory.Count - 2]

} else {

Write-Warning "No previous location in history."

return

}

}



# Standard Set-Location execution

if ($targetPath) {

Set-Location $targetPath

} else {

Set-Location ~

}



# Log to in-memory history

$current = (Get-Location).Path

if ($global:WpHistory.Count -eq 0 -or $global:WpHistory[-1] -ne $current) {

$global:WpHistory.Add($current)

}

}

```


## 2. Connect standard `wp` jumps to the same history stack

Since `wp` ultimately prints a target directory path for PowerShell to `cd` into, make sure your `$PROFILE` `wp` function calls `Set-WaypointLocation` (or appends to `$global:WpHistory` directly) instead of calling standard `Set-Location`.

Your updated wrapper in `$PROFILE` would look like this:

PowerShell
```
function wp {

# Call the python CLI wrapper

$out = python -m waypoint $args



# If python outputted a single existing directory path, jump there

if ($LASTEXITCODE -eq 0 -and $out -and (Test-Path -Path $out -PathType Container)) {

Set-WaypointLocation $out

} else {

# Otherwise, just print the rich output/help text

$out

}

}

```


## 3. The Details to Keep in Mind


- **`cd -` support:** Standard PowerShell `Set-Location` handles `cd -` differently across versions, but by capturing it in `Set-WaypointLocation`, you get reliable `cd -` behavior out of the box.


- **Arguments with spaces:** Using `$PathArgs -join ' '` ensures that unquoted paths with spaces (e.g., `cd C:\My Projects\App`) pass through smoothly without breaking parameter parsing.


- **Session Persistence:** If you want history to persist _across different shell restarts_, you can swap the `$global:WpHistory` memory array with a append-only text file (e.g., `~/.waypoint_history`).
