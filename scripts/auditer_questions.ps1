param(
    [string]$Nom = ('audit_' + (Get-Date -Format 'yyyyMMdd_HHmmss')),
    [string]$Questions = '',
    [switch]$Reprendre
)
$ErrorActionPreference = 'Stop'
$racineProjet = Split-Path -Parent $PSScriptRoot
$pythonProjet = Join-Path $racineProjet '.venv\Scripts\python.exe'
$argumentsAudit = @('-u', '-X', 'utf8', 'scripts/audit_questions.py', '--name', $Nom, '--mode', 'full')
if ($Questions) { $argumentsAudit += @('--input', $Questions) }
if ($Reprendre) { $argumentsAudit += '--resume' }
Push-Location -LiteralPath $racineProjet
try {
    & $pythonProjet @argumentsAudit
    if ($LASTEXITCODE -ne 0) { throw "L'audit a échoué ; consultez le message précédent." }
    Write-Host "Rapport : $(Join-Path $racineProjet "reports\question_audits\$Nom\rapport.html")"
} finally { Pop-Location }
