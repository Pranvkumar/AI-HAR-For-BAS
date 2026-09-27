param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$engine = "$PSScriptRoot\.agents\skills\impeccable\scripts\impeccable.cmd"

if (-not $CommandArgs -or $CommandArgs.Count -eq 0) {
    & $engine help
    exit $LASTEXITCODE
}

$sub = $CommandArgs[0].ToLowerInvariant()

if ($sub -eq "audit") {
    Write-Host "[IMPECCABLE] Auditing frontend/src for design anti-patterns..." -ForegroundColor Cyan
    $target = if ($CommandArgs.Count -gt 1) { $CommandArgs[1..($CommandArgs.Count - 1)] } else { @("frontend/src") }
    & $engine detect $target
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] 0 anti-patterns found. Frontend design is clean." -ForegroundColor Green
    }
    exit $LASTEXITCODE
}

if ($sub -eq "detect") {
    $target = if ($CommandArgs.Count -gt 1) { $CommandArgs[1..($CommandArgs.Count - 1)] } else { @("frontend/src") }
    & $engine detect $target
    exit $LASTEXITCODE
}

if ($sub -eq "doctor") {
    & $engine doctor
    exit $LASTEXITCODE
}

if ($sub -eq "context") {
    & $engine context --target frontend/src/App.tsx
    exit $LASTEXITCODE
}

& $engine $CommandArgs
exit $LASTEXITCODE
