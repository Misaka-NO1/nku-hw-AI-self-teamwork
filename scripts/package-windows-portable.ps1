param(
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [string]$Version = 'v0.2.0-jinnan-windows-preview',
  [string]$NodeExecutable = (Get-Command node -ErrorAction Stop).Source
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$nodeVersion = (& $NodeExecutable -p 'process.versions.node').Trim()
$nodePlatform = (& $NodeExecutable -p "process.platform + '-' + process.arch").Trim()
if ($nodePlatform -ne 'win32-x64') { throw "Expected win32-x64 Node.js; found $nodePlatform" }
if ($nodeVersion -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid Node.js version: $nodeVersion" }

$source = Join-Path $repo 'frontend/src/features/scenic/three-preview'
$three = Join-Path $source 'node_modules/three'
$launcher = Join-Path $PSScriptRoot 'windows-portable'
if (!(Test-Path (Join-Path $three 'build/three.module.js'))) { throw 'Install the preview dependencies before packaging.' }
$tracked = @(& git -C $repo ls-files -- 'frontend/src/features/scenic/three-preview' 'frontend/public/assets/scenic')
if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate tracked release files.' }
$photoFiles = @($tracked | Where-Object { $_ -like 'frontend/public/assets/scenic/*.webp' })
if ($photoFiles.Count -ne 91) { throw 'Expected exactly 91 tracked public scenic photos.' }

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$name = "Nankai-Jinnan-Map-Windows-$Version"
$bundle = Join-Path $OutputDirectory $name
$zip = Join-Path $OutputDirectory "$name.zip"
if ((Test-Path $bundle) -or (Test-Path $zip)) { throw "Output already exists: $name" }

New-Item -ItemType Directory -Path (Join-Path $bundle 'runtime') -Force | Out-Null
Copy-Item -LiteralPath $NodeExecutable -Destination (Join-Path $bundle 'runtime/node.exe')
Copy-Item -LiteralPath (Join-Path $launcher 'start-map.mjs') -Destination (Join-Path $bundle 'start-map.mjs')
Copy-Item -LiteralPath (Join-Path $launcher '启动地图.cmd') -Destination (Join-Path $bundle '启动地图.cmd')
Copy-Item -LiteralPath (Join-Path $launcher '使用说明.txt') -Destination (Join-Path $bundle '使用说明.txt')

$license = "https://raw.githubusercontent.com/nodejs/node/v$nodeVersion/LICENSE"
Invoke-WebRequest -Uri $license -OutFile (Join-Path $bundle 'runtime/NODE-LICENSE.txt')

$relative = 'frontend/src/features/scenic/three-preview'
$target = Join-Path $bundle $relative
foreach ($file in $tracked) {
  if ($file -eq "$relative/three-0.180.0.tgz") { continue }
  $destination = Join-Path $bundle $file
  New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $repo $file) -Destination $destination
}
New-Item -ItemType Directory -Path (Join-Path $target 'node_modules') -Force | Out-Null
Copy-Item -LiteralPath $three -Destination (Join-Path $target 'node_modules/three') -Recurse -Force

Compress-Archive -LiteralPath $bundle -DestinationPath $zip -CompressionLevel Optimal
Write-Output $zip
