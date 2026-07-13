param(
  [string]$OutputDir = "dist/fc-backend",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $root $OutputDir
$backend = Join-Path $root "backend"

if (Test-Path -LiteralPath $output) {
  $resolvedOutput = (Resolve-Path -LiteralPath $output).Path
  if (-not $resolvedOutput.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to delete outside project root: $resolvedOutput"
  }
  Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $output | Out-Null
Copy-Item -LiteralPath (Join-Path $backend "app") -Destination $output -Recurse
Copy-Item -LiteralPath (Join-Path $backend "bootstrap") -Destination $output
Copy-Item -LiteralPath (Join-Path $backend "requirements-prod.txt") -Destination $output

if (-not $SkipInstall) {
  py -m pip install -r (Join-Path $backend "requirements-prod.txt") -t $output --upgrade
}

Write-Host "FC package prepared at $output"

