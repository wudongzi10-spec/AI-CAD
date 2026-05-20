param(
    [string]$PythonPath = $env:FREECAD_PYTHON_PATH,
    [switch]$NoRedirect
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $ProjectRoot "scripts\Start-AiCadBackend.ps1"

if ($NoRedirect) {
    & $StartScript -ProjectRoot $ProjectRoot -PythonPath $PythonPath -NoRedirect
}
else {
    & $StartScript -ProjectRoot $ProjectRoot -PythonPath $PythonPath -StdoutLog "demo_v2_stdout.log" -StderrLog "demo_v2_stderr.log"
}
