param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$EnvironmentFile = "$env:ProgramData\IAMBANDOBANDZ\lead-consent\lead-ledger.env"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw "Missing environment file: $EnvironmentFile"
}

Get-Content -LiteralPath $EnvironmentFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line.Split("=", 2)
    if ($parts.Count -ne 2) { throw "Invalid environment line: $line" }
    [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "Python 3.11+ is required and was not found on PATH."
}

Set-Location -LiteralPath $RepoRoot
if ($python.Name -eq "py.exe") {
    & $python.Source -3 .\lead_consent_service.py
} else {
    & $python.Source .\lead_consent_service.py
}
exit $LASTEXITCODE
