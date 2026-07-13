param(
  [string]$OutputDir = "dist/fc-backend",
  [string]$PythonVersion = "3.10"
)

# Build an Aliyun FC (custom.debian10) deployment package on Windows.
#
# custom.debian10 ships CPython 3.10 under /var/fc/lang/python3.10. Native
# dependencies (pydantic-core, httptools, watchfiles, ...) ship as compiled
# wheels whose ABI is tied to the interpreter version. We therefore cross-download
# manylinux cp310 wheels via pip's --platform / --python-version / --only-binary
# flags instead of building against the local Windows interpreter. This produces a
# package that imports cleanly on the FC Linux runtime.

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

$pyTag = $PythonVersion.Replace(".", "")
Write-Host "Cross-downloading manylinux cp$pyTag wheels for Aliyun FC (Python $PythonVersion)..."

# --only-binary=:all: forces wheels (never sdist), so nothing is compiled against
# the local interpreter. Multiple --platform tags cover the manylinux variants the
# FC runtime accepts.
py -m pip install `
  -r (Join-Path $backend "requirements-prod.txt") `
  --target $output `
  --python-version $PythonVersion `
  --implementation cp `
  --abi "cp$pyTag" `
  --platform manylinux2014_x86_64 `
  --platform manylinux_2_17_x86_64 `
  --platform manylinux_2_28_x86_64 `
  --only-binary=:all: `
  --upgrade

if ($LASTEXITCODE -ne 0) {
  throw "pip cross-download failed with exit code $LASTEXITCODE"
}

# pip evaluates dependency environment markers (e.g. `python_version < "3.11"`)
# against the HOST interpreter, not --python-version. Running this build on
# Python 3.13 therefore silently drops backports that the 3.10 runtime needs:
#   - exceptiongroup: required by anyio when python_version < "3.11"
#   - async-timeout:  required by redis when python_full_version < "3.11.3"
# Install them explicitly so the package imports on the FC Python 3.10 runtime.
$backports = @("exceptiongroup>=1.2.0", "async-timeout>=4.0.3")
Write-Host "Adding Python<3.11 backports that pip skips on this host: $($backports -join ', ')"
py -m pip install `
  @backports `
  --target $output `
  --python-version $PythonVersion `
  --implementation cp `
  --abi "cp$pyTag" `
  --platform manylinux2014_x86_64 `
  --platform manylinux_2_17_x86_64 `
  --platform manylinux_2_28_x86_64 `
  --only-binary=:all: `
  --upgrade

if ($LASTEXITCODE -ne 0) {
  throw "pip backport download failed with exit code $LASTEXITCODE"
}

# Strip bytecode caches and dist-info that are not needed at runtime to shrink the package.
Get-ChildItem -LiteralPath $output -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "FC package prepared at $output"
Write-Host "Contents:"
Get-ChildItem -LiteralPath $output -Name | Select-Object -First 40 | ForEach-Object { Write-Host "  $_" }
