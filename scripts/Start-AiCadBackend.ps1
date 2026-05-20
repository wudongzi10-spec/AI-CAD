param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$PythonPath = $env:FREECAD_PYTHON_PATH,
    [string]$EnvFile = ".env",
    [string]$StdoutLog = "logs\backend_stdout.log",
    [string]$StderrLog = "logs\backend_stderr.log",
    [switch]$NoRedirect
)

$ErrorActionPreference = "Stop"

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

Set-Location $ProjectRoot
Import-DotEnv -Path (Join-Path $ProjectRoot $EnvFile)

if (-not $PythonPath) {
    $freecadBin = if ($env:FREECAD_BIN_PATH) { $env:FREECAD_BIN_PATH } else { "E:\FreeCAD 1.0\bin" }
    $PythonPath = Join-Path $freecadBin "python.exe"
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "FreeCAD Python was not found: $PythonPath"
}

if (-not $env:APP_HOST) {
    $env:APP_HOST = "127.0.0.1"
}
if (-not $env:APP_PORT) {
    $env:APP_PORT = "5001"
}

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "logs") | Out-Null
$appPath = Join-Path $ProjectRoot "app.py"

Write-Host "Using FreeCAD Python: $PythonPath"
Write-Host "Serving AI-CAD on http://$($env:APP_HOST):$($env:APP_PORT)"

$previousPreference = $ErrorActionPreference
$global:LASTEXITCODE = 0

try {
    $ErrorActionPreference = "Continue"
    if ($NoRedirect) {
        & $PythonPath $appPath
    }
    else {
        & $PythonPath $appPath 1> (Join-Path $ProjectRoot $StdoutLog) 2> (Join-Path $ProjectRoot $StderrLog)
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Backend process exited with code: $LASTEXITCODE"
    }
}
finally {
    $ErrorActionPreference = $previousPreference
}
