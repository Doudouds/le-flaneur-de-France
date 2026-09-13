param(
    [Parameter(Mandatory=$true)][string]$SourceCsv,
    [string]$PythonExecutable
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonExecutable) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) { $PythonExecutable = $pythonCommand.Source }
    else { $PythonExecutable = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
}
if (-not (Test-Path -LiteralPath $PythonExecutable)) { throw 'Python 3.11+ introuvable. Renseigner -PythonExecutable.' }
& $PythonExecutable (Join-Path $PSScriptRoot 'build_monuments_db.py') --input $SourceCsv
if ($LASTEXITCODE -ne 0) { throw 'La génération de la base a échoué.' }
& $PythonExecutable -m unittest discover -s $PSScriptRoot -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Les tests du pipeline ont échoué.' }
