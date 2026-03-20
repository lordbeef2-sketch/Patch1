\
$ErrorActionPreference = 'Stop'
$PATCHER_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$ENV_ROOT = (Resolve-Path (Join-Path $PATCHER_ROOT '..')).Path
$SITE_PACKAGES = Join-Path $ENV_ROOT 'Lib\site-packages'
if (-not (Test-Path $SITE_PACKAGES)) {
  $SITE_PACKAGES = Join-Path $ENV_ROOT 'lib\site-packages'
}
if (-not (Test-Path $SITE_PACKAGES)) {
  throw "Expected site-packages not found under: $ENV_ROOT"
}

$CONDA = Get-Command conda -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $CONDA) {
  throw 'Conda not found in PATH.'
}

$PATCH_SCRIPT = Join-Path $PATCHER_ROOT 'tools\patch_openwebui.py'
if (-not (Test-Path $PATCH_SCRIPT)) {
  throw "Missing patch script: $PATCH_SCRIPT"
}

Push-Location $PATCHER_ROOT
try {
  & $CONDA.Source run -p $ENV_ROOT python $PATCH_SCRIPT --site-packages $SITE_PACKAGES apply --yes
  if ($LASTEXITCODE -ne 0) {
    throw "OWUI patch failed."
  }
} finally {
  Pop-Location
}
