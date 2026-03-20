param(
  [string]$LangflowRoot,
  [int]$Port,
  [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'

$configPath = Join-Path $PSScriptRoot '.patcher-paths.json'
$config = $null
if (Test-Path $configPath) {
  $config = Get-Content -Path $configPath -Raw | ConvertFrom-Json
}

if (-not $LangflowRoot -and $config) {
  $LangflowRoot = [string]$config.langflowRoot
}
if (-not $Port) {
  if ($config -and $config.langflowDefaultPort) {
    $Port = [int]$config.langflowDefaultPort
  } else {
    $Port = 7860
  }
}

if (-not $LangflowRoot) {
  throw "Langflow root is not configured. Run .\\configure_paths.ps1 first."
}

$langflowRootResolved = (Resolve-Path -Path $LangflowRoot).Path
$pythonExe = Join-Path $langflowRootResolved '.venv/Scripts/python.exe'
if (-not (Test-Path $pythonExe)) {
  throw "Langflow python not found: $pythonExe"
}

$commandText = "$pythonExe -m langflow run"
if ($ValidateOnly) {
  Write-Host "VALIDATION_OK"
  Write-Host "Langflow root: $langflowRootResolved"
  Write-Host "Port: $Port"
  Write-Host "Command: $commandText"
  exit 0
}

Push-Location $langflowRootResolved
try {
  $env:LANGFLOW_PORT = [string]$Port
  Write-Host "Starting Langflow from $langflowRootResolved on port $Port" -ForegroundColor Cyan
  & $pythonExe -m langflow run
} finally {
  Pop-Location
}
