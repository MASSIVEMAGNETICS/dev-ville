param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$RegenerateSecrets
)

$ErrorActionPreference = "Stop"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this PowerShell window as Administrator."
    }
}

function New-Secret([int]$Bytes = 48) {
    $buffer = New-Object byte[] $Bytes
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($buffer).TrimEnd("=").Replace("+","-").Replace("/","_")
}

function Resolve-PythonExecutable {
    $resolved = ""

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        try {
            $resolved = (& $python.Source -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
        } catch {}
    }

    if (-not $resolved) {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) {
            try {
                $resolved = (& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
            } catch {}
        }
    }

    if (-not $resolved -or -not (Test-Path -LiteralPath $resolved)) {
        throw "Python 3.11+ was not resolved to a real python.exe path."
    }

    $versionText = (& $resolved -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null | Select-Object -Last 1).Trim()
    $version = [version]$versionText
    if ($version -lt [version]"3.11.0") {
        throw "Python 3.11+ is required; resolved $resolved reports $versionText"
    }

    Write-Host "Resolved Python: $resolved ($versionText)"
    return $resolved
}
function Ensure-Caddy {
    $existing = Get-Command caddy -ErrorAction SilentlyContinue
    if ($existing) { return $existing }

    $arch = switch ($env:PROCESSOR_ARCHITECTURE) {
        "AMD64" { "amd64" }
        "ARM64" { "arm64" }
        default { throw "Unsupported Windows architecture for automatic Caddy install: $env:PROCESSOR_ARCHITECTURE" }
    }

    Write-Host "Caddy not found. Downloading latest official Caddy release for windows/$arch..."
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/caddyserver/caddy/releases/latest" -Headers @{ "User-Agent" = "IAMBANDOBANDZ-Lead-Host-Installer" } -TimeoutSec 30
    $pattern = "_windows_" + [regex]::Escape($arch) + "\\.zip$"
    $asset = $release.assets | Where-Object { $_.name -match $pattern } | Select-Object -First 1

    if (-not $asset) {
        throw "Could not locate official Caddy Windows $arch ZIP in latest GitHub release."
    }

    $tempRoot = Join-Path $env:TEMP ("caddy-install-" + [guid]::NewGuid().ToString("N"))
    $zipPath = Join-Path $tempRoot $asset.name
    $extractPath = Join-Path $tempRoot "extract"
    New-Item -ItemType Directory -Force -Path $extractPath | Out-Null

    try {
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing -TimeoutSec 120

        if ($asset.digest -and $asset.digest.StartsWith("sha256:")) {
            $expected = $asset.digest.Substring(7).ToLowerInvariant()
            $actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actual -ne $expected) {
                throw "Caddy SHA-256 mismatch. Expected $expected, got $actual"
            }
            Write-Host "Caddy SHA-256 verified."
        } else {
            throw "Official Caddy release did not expose a SHA-256 digest; refusing unverified install."
        }

        Expand-Archive -LiteralPath $zipPath -DestinationPath $extractPath -Force
        $sourceExe = Get-ChildItem -LiteralPath $extractPath -Filter "caddy.exe" -Recurse | Select-Object -First 1
        if (-not $sourceExe) { throw "caddy.exe not found inside downloaded archive." }

        $installDir = Join-Path $env:ProgramFiles "Caddy"
        New-Item -ItemType Directory -Force -Path $installDir | Out-Null
        $targetExe = Join-Path $installDir "caddy.exe"
        Copy-Item -LiteralPath $sourceExe.FullName -Destination $targetExe -Force

        $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        if (($machinePath -split ";") -notcontains $installDir) {
            [Environment]::SetEnvironmentVariable("Path", ($machinePath.TrimEnd(";") + ";" + $installDir), "Machine")
        }
        if (($env:Path -split ";") -notcontains $installDir) {
            $env:Path = $env:Path.TrimEnd(";") + ";" + $installDir
        }

        & $targetExe version
        return (Get-Command $targetExe -ErrorAction Stop)
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Assert-Administrator

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "lead_consent_service.py"))) {
    throw "RepoRoot does not look like dev-ville: $RepoRoot"
}

$pythonExe = Resolve-PythonExecutable
$caddy = Ensure-Caddy

$stateRoot = Join-Path $env:ProgramData "IAMBANDOBANDZ\lead-consent"
$envFile = Join-Path $stateRoot "lead-ledger.env"
$dbPath = Join-Path $stateRoot "lead_consent.sqlite3"
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null

if ((Test-Path -LiteralPath $envFile) -and -not $RegenerateSecrets) {
    Write-Host "Preserving existing secrets in $envFile"
} else {
    $privacy = New-Secret 48
    $admin = New-Secret 48
    $session = New-Secret 64
    $ingest = New-Secret 48
    @(
        "LEAD_REQUIRE_SECRETS=1"
        "LEAD_DB_PATH=$dbPath"
        "LEAD_BIND_HOST=127.0.0.1"
        "LEAD_BIND_PORT=8787"
        "LEAD_ALLOWED_ORIGINS=https://iambandobandz.com,https://www.iambandobandz.com"
        "LEAD_TRUST_PROXY=1"
        "LEAD_PRIVACY_HASH_KEY=$privacy"
        "LEAD_ADMIN_TOKEN=$admin"
        "LEAD_ADMIN_SESSION_SECRET=$session"
        "LEAD_ADMIN_SESSION_TTL_SECONDS=28800"
        "LEAD_INGEST_TOKEN=$ingest"
    ) | Set-Content -LiteralPath $envFile -Encoding ASCII

    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetAccessRuleProtection($true, $false)
    $identities = @(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name,
        "NT AUTHORITY\SYSTEM",
        "BUILTIN\Administrators"
    )
    foreach ($name in $identities) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $name, "FullControl", "Allow"
        )
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $envFile -AclObject $acl
    Write-Host "Generated private runtime secrets: $envFile"
}

foreach ($port in 80,443) {
    $ruleName = "IAMBANDOBANDZ Lead API TCP $port"
    if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port | Out-Null
    }
}

$runner = Join-Path $RepoRoot "deploy\windows\run-lead-consent.ps1"
$caddyConfig = Join-Path $RepoRoot "deploy\windows\Caddyfile"

$leadAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -RepoRoot `"$RepoRoot`" -PythonExe `"$pythonExe`""
$caddyAction = New-ScheduledTaskAction -Execute $caddy.Source -Argument "run --config `"$caddyConfig`""
$startup = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable

foreach ($taskName in "IAMBANDOBANDZ Lead API","IAMBANDOBANDZ Caddy") {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
}

Register-ScheduledTask -TaskName "IAMBANDOBANDZ Lead API" -Action $leadAction -Trigger $startup -Principal $principal -Settings $settings | Out-Null
Register-ScheduledTask -TaskName "IAMBANDOBANDZ Caddy" -Action $caddyAction -Trigger $startup -Principal $principal -Settings $settings | Out-Null

# Hosting on a laptop only works if Windows does not suspend the machine while plugged in.
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null

Start-ScheduledTask -TaskName "IAMBANDOBANDZ Lead API"

$healthy = $false
for ($attempt = 1; $attempt -le 10; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8787/healthz" -TimeoutSec 3
        if ($health.ok) {
            $healthy = $true
            break
        }
    } catch {}
}

if (-not $healthy) {
    $taskInfo = Get-ScheduledTaskInfo -TaskName "IAMBANDOBANDZ Lead API" -ErrorAction SilentlyContinue
    $lastResult = if ($taskInfo) { $taskInfo.LastTaskResult } else { "unknown" }
    throw "Lead API failed local health verification after 10 attempts. Scheduled task LastTaskResult=$lastResult; PythonExe=$pythonExe"
}
Write-Host "Local lead API: HEALTHY"

Start-ScheduledTask -TaskName "IAMBANDOBANDZ Caddy"

Write-Host ""
Write-Host "Laptop host installed."
Write-Host "State directory: $stateRoot"
Write-Host "API bind: 127.0.0.1:8787"
Write-Host "Public TLS ports expected: 80 and 443"
Write-Host ""

$lan = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -ExpandProperty IPAddress -Unique
if ($lan) {
    Write-Host "Candidate LAN addresses: $($lan -join ', ')"
}

try {
    $public = (Invoke-RestMethod -Uri "https://api.ipify.org?format=json" -TimeoutSec 10).ip
    Write-Host "Observed public IPv4: $public"
} catch {
    Write-Warning "Could not determine public IPv4 automatically."
}

Write-Host ""
Write-Host "NEXT NETWORK GATE:"
Write-Host "1. Reserve this laptop's LAN address in your router."
Write-Host "2. Forward TCP 80 and 443 to this laptop."
Write-Host "3. Point api.iambandobandz.com A/AAAA records to the public address."
Write-Host "4. Then run verify-production.ps1."
Write-Host "If the router has no usable public WAN address (CGNAT), use a tunnel for the edge instead of port forwarding."
