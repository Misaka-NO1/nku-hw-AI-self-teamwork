[CmdletBinding()]
param(
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$appRoot = Join-Path $repoRoot 'backend/app'

if (-not $OutputPath) {
    $OutputPath = Join-Path $PSScriptRoot ('dist/nku-campus-mcp-probe-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.zip')
}
$outputFullPath = [IO.Path]::GetFullPath($OutputPath)
if (Test-Path -LiteralPath $outputFullPath) {
    throw "Package already exists; choose a new OutputPath: $outputFullPath"
}

$inputs = @(
    [pscustomobject]@{ Source = (Join-Path $PSScriptRoot 'Dockerfile'); Entry = 'Dockerfile' }
    [pscustomobject]@{ Source = (Join-Path $repoRoot 'backend/requirements.lock'); Entry = 'backend/requirements.lock' }
)
$appFiles = @(Get-ChildItem -LiteralPath $appRoot -Recurse -File -Filter '*.py' | Sort-Object FullName)
if ($appFiles.Count -eq 0) {
    throw 'No backend Python source files found.'
}
foreach ($file in $appFiles) {
    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to package a symbolic link: $($file.FullName)"
    }
    $relative = $file.FullName.Substring($repoRoot.Length + 1).Replace('\', '/')
    $inputs += [pscustomobject]@{ Source = $file.FullName; Entry = $relative }
}

foreach ($inputFile in $inputs) {
    if (-not (Test-Path -LiteralPath $inputFile.Source -PathType Leaf)) {
        throw "Missing package input: $($inputFile.Source)"
    }
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$outputDirectory = [IO.Path]::GetDirectoryName($outputFullPath)
[IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
$archive = [IO.Compression.ZipFile]::Open($outputFullPath, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($inputFile in $inputs) {
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive,
            $inputFile.Source,
            $inputFile.Entry,
            [IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
} finally {
    $archive.Dispose()
}

$sha256 = (Get-FileHash -LiteralPath $outputFullPath -Algorithm SHA256).Hash
Write-Output "PACKAGE_READY $outputFullPath"
Write-Output "ENTRIES $($inputs.Count)"
Write-Output "SHA256 $sha256"
