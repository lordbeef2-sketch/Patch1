\
param(
  [int]$Port = 8081,
  [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$PATCHER_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$ENV_ROOT = (Resolve-Path (Join-Path $PATCHER_ROOT '..')).Path

$owuiExeCandidates = @(
  (Join-Path $ENV_ROOT 'Scripts/open-webui.exe'),
  (Join-Path $ENV_ROOT 'env/Scripts/open-webui.exe')
)
$owuiExe = $owuiExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $owuiExe) {
  throw "Open WebUI CLI not found under: $ENV_ROOT"
}

$commandText = "$owuiExe serve --port $Port"
if ($ValidateOnly) {
  Write-Host "VALIDATION_OK"
  Write-Host "OWUI env root: $ENV_ROOT"
  Write-Host "Port: $Port"
  Write-Host "Command: $commandText"
  exit 0
}

Push-Location $ENV_ROOT
try {
  Write-Host "Starting Open WebUI from $ENV_ROOT on port $Port" -ForegroundColor Cyan
  & $owuiExe serve --port $Port
} finally {
  Pop-Location
}
