param([ValidateSet('pilot','all')][string]$Scope='all')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath=Join-Path $projectRoot '.venv/Scripts/python.exe'
& $pythonPath -m dgre_rag.cli register
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonPath -m dgre_rag.cli extract --scope $Scope
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonPath -m dgre_rag.cli validate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonPath -m dgre_rag.cli publish --label $Scope
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonPath -m dgre_rag.cli index
exit $LASTEXITCODE
