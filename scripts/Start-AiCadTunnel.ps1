param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$CloudflaredPath = ".\tools\cloudflared.exe",
    [string]$TunnelName = "AI-CAD",
    [string]$TunnelId = $env:CLOUDFLARE_TUNNEL_ID,
    [string]$Hostname = "cad.wudz.cloud",
    [string]$ServiceUrl = "http://127.0.0.1:5001",
    [string]$EnvFile = ".env",
    [string]$ConfigPath = ".\cloudflared\config.yml",
    [switch]$NoRedirect
)

$ErrorActionPreference = "Stop"

Set-Location $ProjectRoot

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (($value.StartsWith([char]34) -and $value.EndsWith([char]34)) -or ($value.StartsWith([char]39) -and $value.EndsWith([char]39))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Import-DotEnv -Path (Join-Path $ProjectRoot $EnvFile)
if (-not $TunnelId -and $env:CLOUDFLARE_TUNNEL_ID) {
    $TunnelId = $env:CLOUDFLARE_TUNNEL_ID
}

$resolvedCloudflaredPath = $CloudflaredPath
if (-not [System.IO.Path]::IsPathRooted($resolvedCloudflaredPath)) {
    $resolvedCloudflaredPath = Join-Path $ProjectRoot $resolvedCloudflaredPath
}
if (-not (Test-Path -LiteralPath $resolvedCloudflaredPath)) {
    throw "cloudflared was not found: $resolvedCloudflaredPath"
}

$resolvedConfigPath = $ConfigPath
if (-not [System.IO.Path]::IsPathRooted($resolvedConfigPath)) {
    $resolvedConfigPath = Join-Path $ProjectRoot $resolvedConfigPath
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedConfigPath) | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "logs") | Out-Null

if (-not (Test-Path -LiteralPath $resolvedConfigPath)) {
    if (-not $TunnelId) {
        throw "Tunnel UUID is required for first-time config generation. Pass -TunnelId or set CLOUDFLARE_TUNNEL_ID."
    }

    $credentialsFile = Join-Path $env:USERPROFILE ".cloudflared\$TunnelId.json"
    @(
        "tunnel: $TunnelId",
        "credentials-file: $credentialsFile",
        "",
        "ingress:",
        "  - hostname: $Hostname",
        "    service: $ServiceUrl",
        "  - service: http_status:404"
    ) | Set-Content -LiteralPath $resolvedConfigPath -Encoding UTF8
}

Write-Host "Starting Cloudflare Tunnel '$TunnelName'"
Write-Host "Hostname: https://$Hostname"
Write-Host "Service:  $ServiceUrl"
Write-Host "Config:   $resolvedConfigPath"

if ($NoRedirect) {
    & $resolvedCloudflaredPath tunnel --config $resolvedConfigPath run $TunnelName
}
else {
    & $resolvedCloudflaredPath tunnel --config $resolvedConfigPath run $TunnelName 1> (Join-Path $ProjectRoot "logs\tunnel_stdout.log") 2> (Join-Path $ProjectRoot "logs\tunnel_stderr.log")
}
