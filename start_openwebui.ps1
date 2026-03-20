param(
  [string]$OwuiRoot,
  [int]$Port,
  [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'

$configPath = Join-Path $PSScriptRoot '.patcher-paths.json'
$config = $null
if (Test-Path $configPath) {
  $config = Get-Content -Path $configPath -Raw | ConvertFrom-Json
}

if (-not $OwuiRoot -and $config) {
  $OwuiRoot = [string]$config.owuiRoot
}
if (-not $Port) {
  if ($config -and $config.owuiDefaultPort) {
    $Port = [int]$config.owuiDefaultPort
  } else {
    $Port = 8081
  }
}

if (-not $OwuiRoot) {
  throw "Open WebUI root is not configured. Run .\\configure_paths.ps1 first."
}

$owuiRootResolved = (Resolve-Path -Path $OwuiRoot).Path
$owuiExeCandidates = @(
  (Join-Path $owuiRootResolved 'env/Scripts/open-webui.exe'),
  (Join-Path $owuiRootResolved 'Scripts/open-webui.exe')
)
$owuiExe = $owuiExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $owuiExe) {
  throw "Open WebUI CLI not found in expected locations (env/Scripts or Scripts) under: $owuiRootResolved"
}

$commandText = "$owuiExe serve --port $Port"
if ($ValidateOnly) {
  Write-Host "VALIDATION_OK"
  Write-Host "OWUI root: $owuiRootResolved"
  Write-Host "Port: $Port"
  Write-Host "Command: $commandText"
  exit 0
}

Push-Location $owuiRootResolved
try {
  Write-Host "Starting Open WebUI from $owuiRootResolved on port $Port" -ForegroundColor Cyan
  & $owuiExe serve --port $Port
} finally {
  Pop-Location
}
