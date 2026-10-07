param(
    [Parameter(Mandatory=$true)][ValidateSet('public', 'identity')][string]$Profile,
    [Parameter(Mandatory=$true)][string]$GeniosUrl,
    [Parameter(Mandatory=$true)][string]$PublicContentOrigin,
    [Parameter(Mandatory=$true)][string]$TimetableOrigin
)
$ErrorActionPreference = 'Stop'
$visualRepo = Split-Path $PSScriptRoot -Parent
foreach ($visualOrigin in @($PublicContentOrigin, $TimetableOrigin)) {
    $visualUri = [Uri]$visualOrigin
    if (-not $visualUri.IsAbsoluteUri -or $visualUri.Scheme -notin @('http','https') -or $visualUri.UserInfo -or $visualUri.Query -or $visualUri.Fragment) {
        throw 'Use a public service origin without credentials, query or fragment.'
    }
}
$visualVariables = @('VITE_API_BASE_URL','VITE_PUBLIC_CONTENT_ONLY','VITE_IDENTITY_PILOT','VITE_GENIOS_AGENT_URL','VITE_PUBLIC_CONTENT_ORIGIN','VITE_TIMETABLE_ORIGIN')
$visualPrevious = @{}
foreach ($visualName in $visualVariables) { $visualPrevious[$visualName] = [Environment]::GetEnvironmentVariable($visualName, 'Process') }
Push-Location (Join-Path $visualRepo 'frontend')
try {
    # Both deployed sites expose /api/v1 on the same origin. Empty is NOT valid.
    $env:VITE_API_BASE_URL = '/'
    $env:VITE_PUBLIC_CONTENT_ONLY = if ($Profile -eq 'public') { 'true' } else { 'false' }
    $env:VITE_IDENTITY_PILOT = if ($Profile -eq 'identity') { 'true' } else { 'false' }
    $env:VITE_GENIOS_AGENT_URL = $GeniosUrl
    $env:VITE_PUBLIC_CONTENT_ORIGIN = $PublicContentOrigin
    $env:VITE_TIMETABLE_ORIGIN = $TimetableOrigin
    $visualOutput = if ($Profile -eq 'identity') { 'dist-identity' } else { 'dist' }
    node node_modules/typescript/bin/tsc --noEmit
    if ($LASTEXITCODE -ne 0) { throw 'Type check failed.' }
    node node_modules/vite/bin/vite.js build --outDir $visualOutput
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
} finally {
    foreach ($visualName in $visualVariables) { [Environment]::SetEnvironmentVariable($visualName, $visualPrevious[$visualName], 'Process') }
    Pop-Location
}
