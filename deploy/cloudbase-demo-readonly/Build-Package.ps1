[CmdletBinding()]
param([string]$OutputPath, [switch]$PlatformCompat)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$gitHead = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $gitHead -notmatch '^[0-9a-f]{40}$') { throw 'Cannot identify source commit.' }
$buildId = 'cloudbase-demo-readonly-' + (Get-Date -Format 'yyyyMMdd') + '-' + $gitHead.Substring(0, 8)
if ($PlatformCompat) { $buildId += '-platform-compat' }
if (-not $OutputPath) { $OutputPath = Join-Path $PSScriptRoot ('dist/' + $buildId + '-' + (Get-Date -Format 'HHmmss') + '.zip') }
$outputFullPath = [IO.Path]::GetFullPath($OutputPath)
if (Test-Path -LiteralPath $outputFullPath) { throw 'Choose a new output path; existing packages are not overwritten.' }

$inputs = @(
    [pscustomobject]@{ Source = (Join-Path $PSScriptRoot 'Dockerfile'); Entry = 'Dockerfile' }
    [pscustomobject]@{ Source = (Join-Path $repoRoot 'backend/requirements.lock'); Entry = 'backend/requirements.lock' }
)
$appRoot = Join-Path $repoRoot 'backend/app'
foreach ($file in @(Get-ChildItem -LiteralPath $appRoot -Recurse -File -Filter '*.py' | Sort-Object FullName)) {
    $relative = $file.FullName.Substring($repoRoot.Length + 1).Replace('\', '/')
    $inputs += [pscustomobject]@{ Source = $file.FullName; Entry = $relative }
}
$resources = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'package-files.json') -Raw | ConvertFrom-Json
foreach ($name in $resources) {
    if ($name -notmatch '^(contracts|fixtures|knowledge)/[A-Za-z0-9_./-]+$' -or $name.Contains('..')) { throw 'Invalid resource allowlist path.' }
    $inputs += [pscustomobject]@{ Source = (Join-Path $repoRoot $name); Entry = $name }
}
$records = @()
foreach ($item in $inputs) {
    if (-not (Test-Path -LiteralPath $item.Source -PathType Leaf)) { throw 'A required package file is missing.' }
    $file = Get-Item -LiteralPath $item.Source
    $taskParent = $file.Directory
    while ($taskParent -and $taskParent.FullName.Length -ge $repoRoot.Length) {
        if (($taskParent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Package source directory cannot be a symbolic link.' }
        $taskParent = $taskParent.Parent
    }
    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Package source cannot be a symbolic link.' }
    if ($file.Length -gt 5000000) { throw 'Unexpectedly large package input.' }
    $content = Get-Content -LiteralPath $item.Source -Raw
    if ($content -match 'Bearer [A-Za-z0-9_-]{32,}|MCP_SERVICE_TOKEN=[A-Za-z0-9_-]{32,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----') {
        throw 'Potential credential detected. Matched values will not be shown.'
    }
    $records += [ordered]@{ path = $item.Entry; sha256 = (Get-FileHash -LiteralPath $item.Source -Algorithm SHA256).Hash.ToLowerInvariant(); size = $file.Length }
}
$sourcePaths = @($inputs | ForEach-Object { $_.Source.Substring($repoRoot.Length + 1).Replace('\', '/') })
$dirtyIncludedFiles = @(& git -C $repoRoot status --porcelain -- $sourcePaths)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect package source status.' }
$manifest = [ordered]@{
    format = 'nku-domain-bundle/v1'; git_head = $gitHead; build_id = $buildId
    included_source_dirty = ($dirtyIncludedFiles.Count -gt 0)
    auth_mode = 'demo_fixture'; personal_uploads = $false
    tools = @('health_probe', 'validate_timetable', 'query_free_time', 'check_time_plan', 'search_scenic_spots', 'search_study_materials', 'audit_degree_progress')
    files = $records
}
if ($PlatformCompat) {
    $manifest.tools += @($manifest.tools | Where-Object { $_ -ne 'health_probe' } | ForEach-Object { 'platform_' + $_ })
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputFullPath)) | Out-Null
$archive = [IO.Compression.ZipFile]::Open($outputFullPath, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($item in $inputs) {
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $item.Source, $item.Entry, [IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
    $manifestEntry = $archive.CreateEntry('domain-bundle-manifest.json')
    $writer = [IO.StreamWriter]::new($manifestEntry.Open(), [Text.UTF8Encoding]::new($false))
    try { $writer.Write(($manifest | ConvertTo-Json -Depth 8)) } finally { $writer.Dispose() }
} finally { $archive.Dispose() }
Write-Output "PACKAGE_READY $outputFullPath"
Write-Output "BUILD_ID $buildId"
Write-Output "ENTRIES $($inputs.Count + 1)"
Write-Output "SHA256 $((Get-FileHash -LiteralPath $outputFullPath -Algorithm SHA256).Hash)"
Write-Output "INCLUDED_SOURCE_DIRTY $($manifest.included_source_dirty)"
