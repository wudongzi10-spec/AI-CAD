param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$PythonPath = $env:FREECAD_PYTHON_PATH,
    [string]$CloudflaredPath = ".\tools\cloudflared.exe",
    [string]$TunnelName = "AI-CAD",
    [string]$TunnelId = $env:CLOUDFLARE_TUNNEL_ID,
    [string]$Hostname = "cad.wudz.cloud",
    [string]$ServiceUrl = "http://127.0.0.1:5001",
    [switch]$RestartTunnel
)

$ErrorActionPreference = "Stop"

function Stop-MatchingProcess {
    param(
        [string]$Name,
        [string]$CommandLinePattern
    )

    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq $Name -and $_.CommandLine -like $CommandLinePattern
    } | ForEach-Object {
        Write-Host "Stopping $($_.Name) pid=$($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }
}

Set-Location $ProjectRoot

$appPath = Join-Path $ProjectRoot "app.py"
Stop-MatchingProcess -Name "python.exe" -CommandLinePattern "*$appPath*"

if ($RestartTunnel) {
    Stop-MatchingProcess -Name "cloudflared.exe" -CommandLinePattern "*tunnel*run*$TunnelName*"
}

# GitHub Actions marks child processes for cleanup. Clear the marker before
# launching the long-running local deployment processes.
[Environment]::SetEnvironmentVariable("RUNNER_TRACKING_ID", $null, "Process")

$backendScript = Join-Path $ProjectRoot "scripts\Start-AiCadBackend.ps1"
$backendArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$backendScript`"",
    "-ProjectRoot", "`"$ProjectRoot`""
)
if ($PythonPath) {
    $backendArgs += @("-PythonPath", "`"$PythonPath`"")
}

Start-Process -FilePath "powershell.exe" -ArgumentList $backendArgs -WorkingDirectory $ProjectRoot -WindowStyle Hidden
Write-Host "Backend process started."

if ($RestartTunnel) {
    $tunnelScript = Join-Path $ProjectRoot "scripts\Start-AiCadTunnel.ps1"
    $tunnelArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$tunnelScript`"",
        "-ProjectRoot", "`"$ProjectRoot`"",
        "-CloudflaredPath", "`"$CloudflaredPath`"",
        "-TunnelName", "`"$TunnelName`"",
        "-Hostname", "`"$Hostname`"",
        "-ServiceUrl", "`"$ServiceUrl`""
    )
    if ($TunnelId) {
        $tunnelArgs += @("-TunnelId", "`"$TunnelId`"")
    }
    Start-Process -FilePath "powershell.exe" -ArgumentList $tunnelArgs -WorkingDirectory $ProjectRoot -WindowStyle Hidden
    Write-Host "Cloudflare Tunnel process started."
}

$healthUrl = "http://127.0.0.1:5001/api/health"
$lastError = $null
for ($attempt = 1; $attempt -le 12; $attempt++) {
    try {
        Invoke-WebRequest -UseBasicParsing $healthUrl | Select-Object -ExpandProperty Content
        exit 0
    }
    catch {
        $lastError = $_
        Start-Sleep -Seconds 3
    }
}

throw "Backend health check failed: $lastError"
