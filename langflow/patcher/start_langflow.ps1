param(
  [int]$Port = 7860,
  [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'

$PATCHER_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$LANGFLOW_ROOT = (Resolve-Path (Join-Path $PATCHER_ROOT '..')).Path
$pythonExe = Join-Path $LANGFLOW_ROOT '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
  throw "Langflow python not found: $pythonExe"
}

$commandText = "$pythonExe -m langflow run"
if ($ValidateOnly) {
  Write-Host "VALIDATION_OK"
  Write-Host "Langflow root: $LANGFLOW_ROOT"
  Write-Host "Port: $Port"
  Write-Host "Command: $commandText"
  exit 0
}

Push-Location $LANGFLOW_ROOT
try {
  $env:LANGFLOW_PORT = [string]$Port
  Write-Host "Starting Langflow from $LANGFLOW_ROOT on port $Port" -ForegroundColor Cyan
  & $pythonExe -m langflow run
} finally {
  Pop-Location
}
