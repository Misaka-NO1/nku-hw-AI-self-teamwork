[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BaselinePackage,
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$BaselineSha256,
    [Parameter(Mandatory)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'
$taskRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$taskDist = [IO.Path]::GetFullPath((Join-Path $taskRepo 'dist')) + [IO.Path]::DirectorySeparatorChar
$taskInput = (Resolve-Path -LiteralPath $BaselinePackage).Path
$taskOutput = [IO.Path]::GetFullPath($OutputPath)
if (-not $taskInput.StartsWith($taskDist, [StringComparison]::OrdinalIgnoreCase) -or
    -not $taskOutput.StartsWith($taskDist, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Variant packages must remain within this repository dist directory.'
}
if (Test-Path -LiteralPath $taskOutput) { throw 'Existing packages are never overwritten.' }
if ((Get-FileHash -LiteralPath $taskInput -Algorithm SHA256).Hash -ne $BaselineSha256) {
    throw 'Baseline package digest mismatch.'
}
$taskReplacement = 'backend/app/core/genios_identity.py'
$taskSource = Join-Path $taskRepo $taskReplacement
$taskBytes = [IO.File]::ReadAllBytes($taskSource)
$taskText = [Text.Encoding]::UTF8.GetString($taskBytes)
if ($taskText -match 'Bearer [A-Za-z0-9_-]{32,}|-----BEGIN .*PRIVATE KEY-----') {
    throw 'Potential credential in replacement source; no matched value is disclosed.'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$taskOriginal = [IO.Compression.ZipFile]::OpenRead($taskInput)
try {
    if (-not $taskOriginal.GetEntry($taskReplacement)) { throw 'Replacement entry missing.' }
    $taskManifestReader = [IO.StreamReader]::new($taskOriginal.GetEntry('package-manifest.json').Open())
    try { $taskManifest = $taskManifestReader.ReadToEnd() | ConvertFrom-Json -AsHashtable }
    finally { $taskManifestReader.Dispose() }
    $taskManifest[$taskReplacement] = (Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash.ToLowerInvariant()
    $taskVariant = [IO.Compression.ZipFile]::Open($taskOutput, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($taskEntry in $taskOriginal.Entries) {
            if ($taskEntry.FullName -match '(^|/)\.\.?(/|$)|\\|^/') { throw 'Unsafe archive path.' }
            $taskNewEntry = $taskVariant.CreateEntry($taskEntry.FullName, [IO.Compression.CompressionLevel]::Optimal)
            $taskDestination = $taskNewEntry.Open()
            try {
                if ($taskEntry.FullName -eq $taskReplacement) {
                    $taskDestination.Write($taskBytes, 0, $taskBytes.Length)
                } elseif ($taskEntry.FullName -eq 'package-manifest.json') {
                    $taskManifestBytes = [Text.Encoding]::UTF8.GetBytes(($taskManifest | ConvertTo-Json -Depth 8))
                    $taskDestination.Write($taskManifestBytes, 0, $taskManifestBytes.Length)
                } else {
                    $taskSourceStream = $taskEntry.Open()
                    try { $taskSourceStream.CopyTo($taskDestination) } finally { $taskSourceStream.Dispose() }
                }
            } finally { $taskDestination.Dispose() }
        }
    } finally { $taskVariant.Dispose() }
    Write-Output "ENTRIES $($taskOriginal.Entries.Count)"
} finally { $taskOriginal.Dispose() }
Write-Output "PACKAGE_READY $taskOutput"
Write-Output "SHA256 $((Get-FileHash -LiteralPath $taskOutput -Algorithm SHA256).Hash.ToLowerInvariant())"
