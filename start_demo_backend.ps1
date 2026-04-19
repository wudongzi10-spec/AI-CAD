param(
    [string]$PythonPath = $env:FREECAD_PYTHON_PATH,
    [switch]$NoRedirect
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not $PythonPath) {
    $freecadBin = if ($env:FREECAD_BIN_PATH) { $env:FREECAD_BIN_PATH } else { "E:\FreeCAD 1.0\bin" }
    $PythonPath = Join-Path $freecadBin "python.exe"
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "未找到 FreeCAD Python: $PythonPath"
}

Write-Host "Using FreeCAD Python:" $PythonPath
& $PythonPath --version

function Invoke-BackendProcess {
    param(
        [string]$ResolvedPythonPath,
        [switch]$DisableRedirect
    )

    $previousPreference = $ErrorActionPreference
    $global:LASTEXITCODE = 0

    try {
        # Flask dev server writes its warning banner to stderr. In Windows PowerShell 5.1
        # that should not be treated as a terminating script error.
        $ErrorActionPreference = "Continue"

        if ($DisableRedirect) {
            & $ResolvedPythonPath app.py
        }
        else {
            & $ResolvedPythonPath app.py 1> .\demo_v2_stdout.log 2> .\demo_v2_stderr.log
        }

        if ($LASTEXITCODE -ne 0) {
            throw "后端进程异常退出，退出码: $LASTEXITCODE"
        }
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

if ($NoRedirect) {
    Invoke-BackendProcess -ResolvedPythonPath $PythonPath -DisableRedirect
}
else {
    Invoke-BackendProcess -ResolvedPythonPath $PythonPath
}
