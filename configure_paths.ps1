param(
  [string]$LangflowRoot,
  [string]$OwuiRoot
)

$ErrorActionPreference = 'Stop'

function Resolve-InputPath {
  param(
    [string]$Label,
    [string]$Provided,
    [string]$Current
  )

  if ($Provided -and $Provided.Trim()) {
    return (Resolve-Path -Path $Provided).Path
  }

  $defaultHint = if ($Current) { " [$Current]" } else { "" }
  $answer = Read-Host "Enter $Label root folder$defaultHint"
  if (-not $answer -or -not $answer.Trim()) {
    if ($Current) {
      return $Current
    }
    throw "No $Label root provided."
  }

  return (Resolve-Path -Path $answer).Path
}

function Assert-PathExists {
  param(
    [string]$PathToCheck,
    [string]$Message
  )

  if (-not (Test-Path -Path $PathToCheck)) {
    throw $Message
  }
}

$configPath = Join-Path $PSScriptRoot '.patcher-paths.json'
$currentConfig = $null
if (Test-Path $configPath) {
  try {
    $currentConfig = Get-Content -Path $configPath -Raw | ConvertFrom-Json
  } catch {
    Write-Warning "Existing config is invalid JSON. It will be replaced."
  }
}

$langflowCurrent = if ($currentConfig) { [string]$currentConfig.langflowRoot } else { '' }
$owuiCurrent = if ($currentConfig) { [string]$currentConfig.owuiRoot } else { '' }

$langflowRootResolved = Resolve-InputPath -Label 'Langflow' -Provided $LangflowRoot -Current $langflowCurrent
$owuiRootResolved = Resolve-InputPath -Label 'Open WebUI' -Provided $OwuiRoot -Current $owuiCurrent

Assert-PathExists -PathToCheck $langflowRootResolved -Message "Langflow root does not exist: $langflowRootResolved"
Assert-PathExists -PathToCheck $owuiRootResolved -Message "Open WebUI root does not exist: $owuiRootResolved"

$langflowPython = Join-Path $langflowRootResolved '.venv/Scripts/python.exe'
$owuiPythonCandidates = @(
  (Join-Path $owuiRootResolved 'env/Scripts/python.exe'),
  (Join-Path $owuiRootResolved 'Scripts/python.exe'),
  (Join-Path $owuiRootResolved 'python.exe')
)
$owuiExeCandidates = @(
  (Join-Path $owuiRootResolved 'env/Scripts/open-webui.exe'),
  (Join-Path $owuiRootResolved 'Scripts/open-webui.exe')
)

$owuiPython = $owuiPythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$owuiExe = $owuiExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not (Test-Path $langflowPython)) {
  Write-Warning "Langflow venv python not found at $langflowPython"
}
if (-not $owuiPython) {
  Write-Warning "OWUI python not found in expected locations (env/Scripts, Scripts, or root)."
}
if (-not $owuiExe) {
  Write-Warning "OWUI CLI not found in expected locations (env/Scripts or Scripts)."
}

$config = [ordered]@{
  langflowRoot = $langflowRootResolved
  owuiRoot = $owuiRootResolved
  langflowDefaultPort = 7860
  owuiDefaultPort = 8081
  updatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
}

$config | ConvertTo-Json -Depth 5 | Set-Content -Path $configPath -Encoding UTF8
Write-Host "Saved path config to $configPath" -ForegroundColor Green
Write-Host "Langflow root: $langflowRootResolved"
Write-Host "OWUI root: $owuiRootResolved"
