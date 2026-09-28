[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $repoRoot 'backend'
$pythonPath = Join-Path $backendRoot '.venv/Scripts/python.exe'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Missing backend/.venv. Follow backend/README.md to install Python 3.12 and requirements.lock first.'
}

Push-Location -LiteralPath $backendRoot
try {
    & $pythonPath -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
    & $pythonPath -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Backend regression failed.' }
    & $pythonPath (Join-Path $backendRoot 'scripts/check_local_stack.py')
    if ($LASTEXITCODE -ne 0) { throw 'Local REST/MCP integration failed.' }
    Write-Host 'LOCAL_PASS. Cloud deployment and NK-GeniOS calls are NOT verified.'
} finally {
    Pop-Location
}
