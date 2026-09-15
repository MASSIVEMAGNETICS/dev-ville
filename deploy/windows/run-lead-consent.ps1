param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$EnvironmentFile = "$env:ProgramData\IAMBANDOBANDZ\lead-consent\lead-ledger.env",
    [string]$PythonExe = ""
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

if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $PythonExe = (& $cmd.Source -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
    }
    if (-not $PythonExe) {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) {
            $PythonExe = (& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
        }
    }
}

if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python 3.11+ executable was not resolved. PythonExe='$PythonExe'"
}

Set-Location -LiteralPath $RepoRoot
& $PythonExe .\lead_consent_service.py
exit $LASTEXITCODE
