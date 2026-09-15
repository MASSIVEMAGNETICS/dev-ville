param(
    [string]$BaseUrl = "https://api.iambandobandz.com",
    [string]$Origin = "https://iambandobandz.com",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$EnvironmentFile = "$env:ProgramData\IAMBANDOBANDZ\lead-consent\lead-ledger.env"
)

$ErrorActionPreference = "Stop"

function Assert-Status([scriptblock]$Request, [int]$Expected, [string]$Label) {
    try {
        $response = & $Request
        $actual = [int]$response.StatusCode
    } catch {
        if ($_.Exception.Response) {
            $actual = [int]$_.Exception.Response.StatusCode
            $response = $_.Exception.Response
        } else {
            throw "$Label failed before HTTP response: $($_.Exception.Message)"
        }
    }
    if ($actual -ne $Expected) {
        throw "$Label expected HTTP $Expected but received $actual"
    }
    Write-Host "[PASS] $Label -> HTTP $actual"
    return $response
}

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw "Missing host environment file: $EnvironmentFile"
}

$runtime = @{}
Get-Content -LiteralPath $EnvironmentFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) {
        $runtime[$parts[0]] = $parts[1]
        [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
    }
}

$health = Invoke-RestMethod -Uri "$BaseUrl/healthz" -TimeoutSec 15
if (-not $health.ok) { throw "Public /healthz reports unhealthy." }
Write-Host "[PASS] public health"

$idempotency = "prod-verify-$([guid]::NewGuid().ToString('N'))"
$leadBody = @{
    email = "verification+iambandobandz@example.com"
    phone = ""
    sms_consent = $false
    consent_text_version = "signal-capture-v1"
    source = "production-verification"
    idempotency_key = $idempotency
} | ConvertTo-Json -Compress

$headers = @{ Origin = $Origin; "X-Idempotency-Key" = $idempotency }
$first = Invoke-WebRequest -Method Post -Uri "$BaseUrl/api/v1/leads" -Headers $headers -ContentType "application/json" -Body $leadBody -TimeoutSec 15
if ([int]$first.StatusCode -ne 201) { throw "First lead submit expected 201." }
$firstBody = $first.Content | ConvertFrom-Json
if (-not $firstBody.receipt_id) { throw "First lead submit returned no receipt_id." }
Write-Host "[PASS] durable lead receipt $($firstBody.receipt_id)"

$replay = Invoke-WebRequest -Method Post -Uri "$BaseUrl/api/v1/leads" -Headers $headers -ContentType "application/json" -Body $leadBody -TimeoutSec 15
if ([int]$replay.StatusCode -ne 200) { throw "Replay expected 200." }
$replayBody = $replay.Content | ConvertFrom-Json
if ($replayBody.receipt_id -ne $firstBody.receipt_id -or -not $replayBody.idempotent_replay) {
    throw "Idempotent replay did not preserve the original receipt."
}
Write-Host "[PASS] idempotent replay"

$changed = @{
    email = "changed+iambandobandz@example.com"
    phone = ""
    sms_consent = $false
    consent_text_version = "signal-capture-v1"
    source = "production-verification"
    idempotency_key = $idempotency
} | ConvertTo-Json -Compress
Assert-Status { Invoke-WebRequest -Method Post -Uri "$BaseUrl/api/v1/leads" -Headers $headers -ContentType "application/json" -Body $changed -TimeoutSec 15 } 409 "changed payload reusing idempotency key" | Out-Null

$hostileHeaders = @{ Origin = "https://evil.example"; "X-Idempotency-Key" = "hostile-$([guid]::NewGuid().ToString('N'))" }
Assert-Status { Invoke-WebRequest -Method Post -Uri "$BaseUrl/api/v1/leads" -Headers $hostileHeaders -ContentType "application/json" -Body $leadBody -TimeoutSec 15 } 403 "hostile browser origin" | Out-Null

Assert-Status { Invoke-WebRequest -Method Post -Uri "$BaseUrl/api/v1/leads" -ContentType "application/json" -Body $leadBody -TimeoutSec 15 } 403 "server-to-server request without ingest token" | Out-Null

Assert-Status { Invoke-WebRequest -Method Get -Uri "$BaseUrl/api/v1/admin/stats" -Headers @{Authorization="Bearer definitely-wrong"} -TimeoutSec 15 } 401 "wrong admin bearer" | Out-Null

if (-not $runtime.ContainsKey("LEAD_ADMIN_TOKEN")) { throw "LEAD_ADMIN_TOKEN missing from host environment." }
$stats = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/admin/stats" -Headers @{Authorization="Bearer $($runtime['LEAD_ADMIN_TOKEN'])"} -TimeoutSec 15
if (-not $stats.audit_chain_valid) { throw "Admin stats reports invalid audit chain." }
$statsJson = $stats | ConvertTo-Json -Depth 8
foreach ($forbidden in "email","phone","user_agent","ip_address","admin_token","session_secret") {
    if ($statsJson -match ('"' + [regex]::Escape($forbidden) + '"\s*:')) {
        throw "Admin stats unexpectedly exposes field: $forbidden"
    }
}
Write-Host "[PASS] authorized admin stats without PII fields"

if ($runtime.ContainsKey("LEAD_ADMIN_SESSION_SECRET") -and $runtime["LEAD_ADMIN_SESSION_SECRET"]) {
    $webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $loginBody = @{token=$runtime["LEAD_ADMIN_TOKEN"]} | ConvertTo-Json -Compress
    $login = Invoke-WebRequest -Method Post -Uri "$BaseUrl/api/v1/admin/login" -Headers @{Origin=$Origin} -ContentType "application/json" -Body $loginBody -WebSession $webSession -TimeoutSec 15
    if ([int]$login.StatusCode -ne 200) { throw "Browser admin login expected 200." }
    $setCookie = $login.Headers["Set-Cookie"] -join ";"
    foreach ($required in "Secure","HttpOnly","SameSite=Strict","Path=/") {
        if ($setCookie -notmatch [regex]::Escape($required)) { throw "Admin cookie missing $required" }
    }
    $session = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/admin/session" -Headers @{Origin=$Origin} -WebSession $webSession -TimeoutSec 15
    if (-not $session.authenticated) { throw "Browser admin session was not authenticated." }
    Assert-Status { Invoke-WebRequest -Method Get -Uri "$BaseUrl/api/v1/admin/session" -Headers @{Origin="https://evil.example"} -WebSession $webSession -TimeoutSec 15 } 401 "hostile-origin admin session use" | Out-Null
    $logout = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/admin/logout" -Headers @{Origin=$Origin} -ContentType "application/json" -Body "{}" -WebSession $webSession -TimeoutSec 15
    if (-not $logout.ok) { throw "Admin logout failed." }
    Write-Host "[PASS] browser admin login/session/logout"
} else {
    Write-Warning "Browser admin session secret absent; browser-session tests skipped."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python not found for local audit verification." }
Push-Location $RepoRoot
try {
    if ($python.Name -eq "py.exe") {
        & $python.Source -3 .\lead_consent_service.py --verify
    } else {
        & $python.Source .\lead_consent_service.py --verify
    }
    if ($LASTEXITCODE -ne 0) { throw "Local audit verification exited $LASTEXITCODE" }
} finally {
    Pop-Location
}
Write-Host "[PASS] local SQLite audit chain"

Write-Host ""
Write-Host "PRODUCTION VERIFICATION COMPLETE"
Write-Host "receipt_id=$($firstBody.receipt_id)"
Write-Host "idempotency_key=$idempotency"
