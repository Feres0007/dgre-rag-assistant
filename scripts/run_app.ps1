$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Environnement Python absent. Voir README.md.' }
$sourceRoot = Join-Path $projectRoot 'src'
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($previousPythonPath) { $sourceRoot + [IO.Path]::PathSeparator + $previousPythonPath } else { $sourceRoot }
try {
    & $pythonPath -m streamlit run (Join-Path $projectRoot 'app/streamlit_app.py') @args
    $appExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
exit $appExitCode
