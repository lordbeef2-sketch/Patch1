\
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$envRoot = (Resolve-Path (Join-Path $here '..')).Path
$sitePackages = Join-Path $envRoot 'Lib\site-packages'
if (-not (Test-Path $sitePackages)) { $sitePackages = Join-Path $envRoot 'lib\site-packages' }
if (-not (Test-Path $sitePackages)) { throw "Expected site-packages not found: $envRoot" }
$condaCmd = Get-Command conda -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $condaCmd) { throw 'Conda not found in PATH.' }

Push-Location $here
try {
  & $condaCmd.Source run -p $envRoot python .\tools\patch_openwebui.py --site-packages $sitePackages logo @args
} finally {
  Pop-Location
}
