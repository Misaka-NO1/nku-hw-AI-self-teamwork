param([int]$Port = 8012)
$ErrorActionPreference = 'Stop'
$demoRepo = Split-Path $PSScriptRoot -Parent
$demoPython = Join-Path $demoRepo 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) { throw 'Create backend/.venv and install backend/requirements.lock first.' }
if (-not (Test-Path -LiteralPath (Join-Path $demoRepo 'node_modules'))) { throw 'Run pnpm install --frozen-lockfile at the repository root first.' }
$demoPreviousBase = $env:VITE_API_BASE_URL
$demoPreviousPublicOnly = $env:VITE_PUBLIC_CONTENT_ONLY
Push-Location $demoRepo
try {
    # Same-origin local site; no MCP bearer or user identity enters the frontend.
    $env:VITE_API_BASE_URL = '/'
    $env:VITE_PUBLIC_CONTENT_ONLY = 'false'
    # Invoke installed binaries directly: avoid pnpm automatically reinstalling
    # dependencies when the machine's pnpm version differs from packageManager.
    Push-Location (Join-Path $demoRepo 'frontend')
    try {
        node node_modules/typescript/bin/tsc --noEmit
        if ($LASTEXITCODE -ne 0) { throw 'Frontend type check failed.' }
        node node_modules/vite/bin/vite.js build --outDir dist-demo
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed; no server was started.' }
    } finally { Pop-Location }
    & $demoPython backend/scripts/run_demo_site.py --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Local demo server exited with an error (check for a busy port).' }
} finally {
    $env:VITE_API_BASE_URL = $demoPreviousBase
    $env:VITE_PUBLIC_CONTENT_ONLY = $demoPreviousPublicOnly
    Pop-Location
}
