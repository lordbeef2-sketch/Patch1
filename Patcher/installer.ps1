#!/usr/bin/env pwsh

param(
  [string]$InstallRoot = "",
  [string]$PythonExe = "",
  [switch]$PatchOnly,
  [switch]$InstallOnly,
  [switch]$Force,
  [switch]$ValidateOnly,
  [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info([string]$msg) { Write-Host "[installer] $msg" -ForegroundColor Cyan }
function Ok([string]$msg) { Write-Host "[installer] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "[installer] $msg" -ForegroundColor Yellow }
function Fail([string]$msg) { Write-Host "[installer] $msg" -ForegroundColor Red; exit 1 }

function Get-PatcherConfigPath([string]$Root) {
  return Join-Path $Root "local.settings.json"
}

function Load-PatcherConfig([string]$Root) {
  $configPath = Get-PatcherConfigPath -Root $Root
  if (-not (Test-Path $configPath)) {
    return [pscustomobject]@{}
  }

  try {
    $raw = Get-Content -Path $configPath -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
      return [pscustomobject]@{}
    }
    return ($raw | ConvertFrom-Json)
  } catch {
    Warn ("Ignoring unreadable config file: {0}" -f $configPath)
    return [pscustomobject]@{}
  }
}

function Get-ConfigValue($Config, [string]$Name) {
  if ($null -eq $Config) {
    return $null
  }

  $property = $Config.PSObject.Properties[$Name]
  if ($null -eq $property) {
    return $null
  }

  return $property.Value
}

function Save-PatcherConfig([string]$Root, [hashtable]$Updates) {
  $configPath = Get-PatcherConfigPath -Root $Root
  $merged = [ordered]@{}
  $existing = Load-PatcherConfig -Root $Root

  foreach ($prop in $existing.PSObject.Properties) {
    $merged[$prop.Name] = $prop.Value
  }

  foreach ($key in $Updates.Keys) {
    $value = $Updates[$key]
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
      $merged.Remove($key) | Out-Null
      continue
    }
    $merged[$key] = $value
  }

  $merged["updated_at"] = (Get-Date).ToString("o")
  $merged | ConvertTo-Json | Set-Content -Path $configPath -Encoding UTF8
  return $configPath
}

function Get-DefaultLangflowRoot([string]$PatcherRoot) {
  $leaf = Split-Path -Leaf $PatcherRoot
  if ($leaf -ieq "patcher") {
    return (Split-Path -Parent $PatcherRoot)
  }
  return $PatcherRoot
}

function Test-SamePath([string]$Left, [string]$Right) {
  if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) {
    return $false
  }

  $leftFull = [System.IO.Path]::GetFullPath($Left).TrimEnd('\', '/')
  $rightFull = [System.IO.Path]::GetFullPath($Right).TrimEnd('\', '/')
  return $leftFull.Equals($rightFull, [System.StringComparison]::OrdinalIgnoreCase)
}

function Resolve-RequestedLangflowRoot([string]$RequestedRoot, [string]$SavedRoot, [string]$PatcherRoot) {
  $defaultRoot = Get-DefaultLangflowRoot -PatcherRoot $PatcherRoot
  $candidate = $RequestedRoot

  if ([string]::IsNullOrWhiteSpace($candidate) -and -not [string]::IsNullOrWhiteSpace($SavedRoot)) {
    $candidate = $SavedRoot
  }

  if (-not [string]::IsNullOrWhiteSpace($candidate)) {
    $expanded = [Environment]::ExpandEnvironmentVariables($candidate.Trim())
    if (-not [System.IO.Path]::IsPathRooted($expanded)) {
      $expanded = Join-Path (Get-Location).Path $expanded
    }

    if (Test-SamePath -Left $expanded -Right $PatcherRoot) {
      Warn ("Langflow target points at the patcher folder ({0}); using parent folder instead: {1}" -f $PatcherRoot, $defaultRoot)
      return $defaultRoot
    }

    return $candidate
  }

  return $defaultRoot
}

function Resolve-InstallRoot([string]$RequestedRoot, [string]$DefaultRoot) {
  if ([string]::IsNullOrWhiteSpace($RequestedRoot)) {
    return (Resolve-Path -LiteralPath $DefaultRoot).Path
  }

  $expanded = [Environment]::ExpandEnvironmentVariables($RequestedRoot.Trim())
  if (-not [System.IO.Path]::IsPathRooted($expanded)) {
    $expanded = Join-Path (Get-Location).Path $expanded
  }

  if (-not (Test-Path $expanded)) {
    New-Item -ItemType Directory -Path $expanded -Force | Out-Null
  }

  return (Resolve-Path -LiteralPath $expanded).Path
}

function Get-RelativePath([string]$root, [string]$path) {
  $resolvedRoot = [System.IO.Path]::GetFullPath($root)
  $resolvedPath = [System.IO.Path]::GetFullPath($path)

  if (
    -not $resolvedRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar) -and
    -not $resolvedRoot.EndsWith([System.IO.Path]::AltDirectorySeparatorChar)
  ) {
    $resolvedRoot = $resolvedRoot + [System.IO.Path]::DirectorySeparatorChar
  }

  $rootUri = [System.Uri]::new($resolvedRoot)
  $pathUri = [System.Uri]::new($resolvedPath)
  $relativeUri = $rootUri.MakeRelativeUri($pathUri)
  return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace("/", [System.IO.Path]::DirectorySeparatorChar)
}

function Assert-PathWithinRoot([string]$path, [string]$root) {
  $resolvedPath = [System.IO.Path]::GetFullPath($path)
  $resolvedRoot = [System.IO.Path]::GetFullPath($root)
  if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Fail "Refusing to modify path outside target root: $resolvedPath"
  }
}

function Get-FileSha256([string]$path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-DirectoryFingerprint([string]$root) {
  if (-not (Test-Path $root)) {
    return ""
  }

  $entries = New-Object System.Collections.Generic.List[string]
  foreach ($file in Get-ChildItem -Path $root -Recurse -File | Sort-Object FullName) {
    $relativePath = (Get-RelativePath -root $root -path $file.FullName).Replace("\", "/")
    $fileHash = Get-FileSha256 $file.FullName
    $entries.Add("$relativePath|$fileHash")
  }

  $combined = [string]::Join("`n", $entries)
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($combined)
  $stream = [System.IO.MemoryStream]::new($bytes)
  try {
    return (Get-FileHash -InputStream $stream -Algorithm SHA256).Hash.ToLowerInvariant()
  } finally {
    $stream.Dispose()
  }
}

function Read-InstallState([string]$path) {
  if (-not (Test-Path $path)) {
    return $null
  }

  try {
    return Get-Content -Path $path -Raw | ConvertFrom-Json
  } catch {
    Warn "Install state file is invalid at $path. Reapplying patch."
    return $null
  }
}

function Write-InstallState(
  [string]$path,
  [string]$installRoot,
  [string]$pythonPath,
  [string]$pythonVersion,
  [string]$langflowVersion,
  [string]$langflowRoot,
  [string]$lfxRoot,
  [string]$payloadFingerprint,
  [string]$installerFingerprint
) {
  $state = [ordered]@{
    stateVersion = 4
    installRoot = $installRoot
    pythonPath = $pythonPath
    pythonVersion = $pythonVersion
    langflowVersion = $langflowVersion
    langflowRoot = $langflowRoot
    lfxRoot = $lfxRoot
    payloadFingerprint = $payloadFingerprint
    installerFingerprint = $installerFingerprint
    updatedAt = (Get-Date).ToString("o")
  }

  $state | ConvertTo-Json | Set-Content -Path $path -NoNewline
}

function Resolve-UvCommand {
  $uvCmd = Get-Command uv -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($uvCmd -and -not [string]::IsNullOrWhiteSpace([string]$uvCmd.Source)) {
    return [string]$uvCmd.Source
  }

  Fail "uv is required for LangPatcher install. Install uv or place uv.exe on PATH, then rerun."
}

function Get-LocalVenvPython([string]$Root) {
  $candidate = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path $candidate) {
    return (Resolve-Path -LiteralPath $candidate).Path
  }
  return ""
}

function Test-LangflowInstalled([string]$PythonPath) {
  if ([string]::IsNullOrWhiteSpace($PythonPath) -or -not (Test-Path $PythonPath)) {
    return $false
  }

  $script = @'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("langflow") and importlib.util.find_spec("lfx") else 1)
'@

  $script | & $PythonPath - 1>$null 2>$null
  return ($LASTEXITCODE -eq 0)
}

function Use-PythonRuntimePath([string]$PythonPath) {
  $script = @'
import json
import pathlib
import sys

paths = []
for value in [pathlib.Path(sys.executable).resolve().parent, pathlib.Path(sys.base_prefix).resolve(), pathlib.Path(sys.base_prefix).resolve() / "DLLs"]:
    if value.exists():
        paths.append(str(value))
print(json.dumps(paths))
'@

  try {
    $json = $script | & $PythonPath -
    if ($LASTEXITCODE -ne 0 -or -not $json) {
      return
    }
    $paths = (($json -join "`n") | ConvertFrom-Json)
  } catch {
    return
  }

  $existing = @($env:PATH -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $ordered = [System.Collections.Generic.List[string]]::new()
  foreach ($path in @($paths)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$path) -and (Test-Path ([string]$path))) {
      $ordered.Add([string]$path) | Out-Null
    }
  }
  foreach ($path in $existing) {
    $alreadyAdded = $false
    foreach ($prefix in $ordered) {
      if ($prefix -ieq $path) {
        $alreadyAdded = $true
        break
      }
    }
    if (-not $alreadyAdded) {
      $ordered.Add($path) | Out-Null
    }
  }

  $env:PATH = [string]::Join(';', $ordered)
}

function Get-PythonVersion([string]$PythonPath) {
  $pythonVersionOutput = & $PythonPath -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
  if ($LASTEXITCODE -ne 0 -or $null -eq $pythonVersionOutput) {
    return ""
  }

  return ([string]::Join("`n", @($pythonVersionOutput))).Trim()
}

function Get-InstalledPackageLayout([string]$PythonPath) {
  $script = @'
import importlib.metadata as metadata
import importlib.util
import json

payload = {"installed": False}

langflow_spec = importlib.util.find_spec("langflow")
lfx_spec = importlib.util.find_spec("lfx")

if langflow_spec is not None and lfx_spec is not None:
    payload = {
        "installed": True,
        "langflowVersion": metadata.version("langflow"),
        "langflowRoot": langflow_spec.submodule_search_locations[0],
        "lfxRoot": lfx_spec.submodule_search_locations[0],
    }

print(json.dumps(payload))
'@

  $layoutOutput = $script | & $PythonPath -
  if ($LASTEXITCODE -ne 0 -or $null -eq $layoutOutput) {
    Fail ("Unable to inspect the installed Langflow package using {0}." -f $PythonPath)
  }

  try {
    $layout = (([string]::Join("`n", @($layoutOutput))).Trim()) | ConvertFrom-Json
  } catch {
    Fail ("Langflow inspection returned unreadable data for {0}." -f $PythonPath)
  }

  if (-not $layout.installed) {
    Fail ("Langflow is not installed in the local environment: {0}" -f $PythonPath)
  }

  return $layout
}

function Ensure-LocalLangflowEnvironment([string]$Root, [string]$RequestedPython, [switch]$ForceInstall) {
  $uvPath = Resolve-UvCommand
  $venvPython = Get-LocalVenvPython -Root $Root
  $venvPath = Join-Path $Root ".venv"

  if ([string]::IsNullOrWhiteSpace($venvPython)) {
    Info ("Creating folder-local Python environment at {0} with Python 3.11" -f $venvPath)
    $venvArgs = @("--native-tls", "venv", $venvPath, "--python")
    if ([string]::IsNullOrWhiteSpace($RequestedPython)) {
      $venvArgs += "3.11"
    } else {
      $venvArgs += $RequestedPython
    }
    & $uvPath @venvArgs
    if ($LASTEXITCODE -ne 0) {
      Fail "Failed to create local .venv with uv."
    }

    $venvPython = Get-LocalVenvPython -Root $Root
    if ([string]::IsNullOrWhiteSpace($venvPython)) {
      Fail "uv completed, but .venv\Scripts\python.exe was not found."
    }
  } else {
    Info ("Reusing local Python environment at {0}" -f $venvPath)
  }

  if ((-not $ForceInstall) -and (Test-LangflowInstalled -PythonPath $venvPython)) {
    Ok "Langflow is already installed in the local environment. Skipping install."
    return $venvPython
  }

  Info "Installing Langflow into the local environment"
  & $uvPath --native-tls pip install --python $venvPython langflow -U
  if ($LASTEXITCODE -ne 0) {
    Fail "Langflow installation failed."
  }

  if (-not (Test-LangflowInstalled -PythonPath $venvPython)) {
    Fail "Langflow install completed, but langflow/lfx are not importable from the local environment."
  }

  Ok "Langflow is installed in the local environment"
  return $venvPython
}

function Copy-Tree([string]$sourceRoot, [string]$destinationRoot) {
  if (-not (Test-Path $sourceRoot)) {
    Fail "Missing payload directory: $sourceRoot"
  }

  if (-not (Test-Path $destinationRoot)) {
    New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
  }

  $copied = 0
  foreach ($file in Get-ChildItem -Path $sourceRoot -Recurse -File | Sort-Object FullName) {
    $relativePath = Get-RelativePath -root $sourceRoot -path $file.FullName
    $destinationPath = Join-Path $destinationRoot $relativePath
    $destinationDir = Split-Path -Parent $destinationPath

    Assert-PathWithinRoot -path $destinationPath -root $destinationRoot

    if (-not (Test-Path $destinationDir)) {
      New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    }

    Copy-Item -Path $file.FullName -Destination $destinationPath -Force
    $copied++
  }

  return $copied
}

function Install-FrontendBundle([string]$bundlePath, [string]$destinationRoot) {
  if (-not (Test-Path $bundlePath)) {
    Fail "Missing built frontend bundle: $bundlePath"
  }

  if (-not (Test-Path $destinationRoot)) {
    New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
  }

  $extractRoot = Join-Path $env:TEMP ("langpatcher-frontend-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null

  try {
    Expand-Archive -LiteralPath $bundlePath -DestinationPath $extractRoot -Force

    Assert-PathWithinRoot -path $destinationRoot -root $destinationRoot
    Get-ChildItem -Path $destinationRoot -Force | Remove-Item -Recurse -Force
    Copy-Item -Path (Join-Path $extractRoot "*") -Destination $destinationRoot -Recurse -Force
  } finally {
    if (Test-Path $extractRoot) {
      Remove-Item -Recurse -Force $extractRoot
    }
  }

  return (Get-ChildItem -Path $destinationRoot -Recurse -File | Measure-Object).Count
}

function Ensure-EnvSetting([string]$envFile, [string]$key, [string]$value) {
  $line = "$key=$value"

  if (Test-Path $envFile) {
    $envContent = Get-Content -Path $envFile -Raw
    if ($envContent -match "(?m)^\s*$key\s*=") {
      $updated = [regex]::Replace($envContent, "(?m)^\s*$key\s*=.*$", $line)
      Set-Content -Path $envFile -Value $updated -NoNewline
      return
    }

    $trimmed = $envContent.TrimEnd("`r", "`n")
    if ($trimmed.Length -gt 0) {
      $trimmed = $trimmed + "`r`n"
    }
    Set-Content -Path $envFile -Value ($trimmed + $line + "`r`n") -NoNewline
    return
  }

  Set-Content -Path $envFile -Value ($line + "`r`n") -NoNewline
}

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigRoot = $ScriptRoot
$SavedConfig = Load-PatcherConfig -Root $ConfigRoot
$SavedLangflowTarget = Get-ConfigValue -Config $SavedConfig -Name "langflow_target"
$ResolvedRequestedRoot = Resolve-RequestedLangflowRoot -RequestedRoot $InstallRoot -SavedRoot $SavedLangflowTarget -PatcherRoot $ScriptRoot
$Root = Resolve-InstallRoot -RequestedRoot $ResolvedRequestedRoot -DefaultRoot (Get-DefaultLangflowRoot -PatcherRoot $ScriptRoot)
$PayloadRoot = Join-Path $ScriptRoot "patcher_payload"
$BackendPayloadRoot = Join-Path $PayloadRoot "src\backend\base\langflow"
$LfxPayloadRoot = Join-Path $PayloadRoot "src\lfx\src\lfx"
$FrontendBundlePath = Join-Path $PayloadRoot "frontend_build.zip"
$StateFile = Join-Path $Root "langpatcher-state.json"
$EnvFile = Join-Path $Root ".env"

if (-not (Test-Path $PayloadRoot)) {
  Fail "Missing payload directory: $PayloadRoot"
}

$PayloadFingerprint = Get-DirectoryFingerprint $PayloadRoot
$InstallerFingerprint = Get-FileSha256 $MyInvocation.MyCommand.Path
$localPython = Get-LocalVenvPython -Root $Root

if ($ValidateOnly) {
  Write-Host "VALIDATION_OK"
  Write-Host ("Patcher root: {0}" -f $ConfigRoot)
  Write-Host ("Langflow target: {0}" -f $Root)
  Write-Host ("Local Python: {0}" -f $(if ($localPython) { $localPython } else { "<missing>" }))
  Write-Host ("Langflow installed: {0}" -f $(if ($localPython -and (Test-LangflowInstalled -PythonPath $localPython)) { "yes" } else { "no" }))
  exit 0
}

if ($PatchOnly) {
  if ([string]::IsNullOrWhiteSpace($localPython)) {
    Fail ("Missing local .venv at {0}. Run Install first." -f $Root)
  }
  $PythonPath = $localPython
} else {
  $PythonPath = Ensure-LocalLangflowEnvironment -Root $Root -RequestedPython $PythonExe -ForceInstall:$Force
}

Use-PythonRuntimePath -PythonPath $PythonPath

if ($InstallOnly) {
  Save-PatcherConfig -Root $ConfigRoot -Updates @{
    langflow_target = $Root
    python_exe = $PythonPath
  } | Out-Null
  Ok "Install completed. Patch was skipped because -InstallOnly was used."
  exit 0
}

$PythonVersion = Get-PythonVersion -PythonPath $PythonPath
$Layout = Get-InstalledPackageLayout -PythonPath $PythonPath
$InstalledLangflowVersion = [string]$Layout.langflowVersion
$LangflowRoot = [string]$Layout.langflowRoot
$LfxRoot = [string]$Layout.lfxRoot
$InstallState = Read-InstallState $StateFile

Info ("Using Python: {0}" -f $PythonPath)
Ok ("Using Python {0} in local environment" -f $PythonVersion)
Info ("Detected Langflow {0}: {1}" -f $InstalledLangflowVersion, $LangflowRoot)

$HasMatchingPatchedInstall = (
  -not $Force -and
  $null -ne $InstallState -and
  $InstallState.pythonPath -eq $PythonPath -and
  $InstallState.pythonVersion -eq $PythonVersion -and
  $InstallState.langflowVersion -eq $InstalledLangflowVersion -and
  $InstallState.langflowRoot -eq $LangflowRoot -and
  $InstallState.lfxRoot -eq $LfxRoot -and
  $InstallState.payloadFingerprint -eq $PayloadFingerprint -and
  $InstallState.installerFingerprint -eq $InstallerFingerprint -and
  (Test-Path $LangflowRoot) -and
  (Test-Path $LfxRoot)
)

if ($HasMatchingPatchedInstall) {
  Ok "LangPatcher is already applied for Langflow $InstalledLangflowVersion. Skipping patch."
  Write-Host "Run: .\launcher.ps1" -ForegroundColor White
  exit 0
}

Info "Applying backend patch files to $LangflowRoot"
$backendCopied = Copy-Tree -sourceRoot $BackendPayloadRoot -destinationRoot $LangflowRoot
Ok "Copied $backendCopied backend files"

Info "Applying LFX patch files to $LfxRoot"
$lfxCopied = Copy-Tree -sourceRoot $LfxPayloadRoot -destinationRoot $LfxRoot
Ok "Copied $lfxCopied LFX files"

$InstalledFrontendRoot = Join-Path $LangflowRoot "frontend"
Info "Replacing built frontend assets in $InstalledFrontendRoot"
$frontendFiles = Install-FrontendBundle -bundlePath $FrontendBundlePath -destinationRoot $InstalledFrontendRoot
Ok "Installed $frontendFiles frontend files"

Info "Ensuring LANGFLOW_AUTO_LOGIN=false in $EnvFile"
Ensure-EnvSetting -envFile $EnvFile -key "LANGFLOW_AUTO_LOGIN" -value "false"
Ok "Configured .env with LANGFLOW_AUTO_LOGIN=false"

Info "Ensuring LANGPATCHER_LOCAL_ONLY=true in $EnvFile"
Ensure-EnvSetting -envFile $EnvFile -key "LANGPATCHER_LOCAL_ONLY" -value "true"
Ok "Configured .env with LANGPATCHER_LOCAL_ONLY=true"

Write-InstallState `
  -path $StateFile `
  -installRoot $Root `
  -pythonPath $PythonPath `
  -pythonVersion $PythonVersion `
  -langflowVersion $InstalledLangflowVersion `
  -langflowRoot $LangflowRoot `
  -lfxRoot $LfxRoot `
  -payloadFingerprint $PayloadFingerprint `
  -installerFingerprint $InstallerFingerprint

$configPath = Save-PatcherConfig -Root $ConfigRoot -Updates @{
  langflow_target = $Root
  python_exe = $PythonPath
}

Ok "Patch completed."
Ok ("Saved local patcher defaults to {0}" -f $configPath)
Write-Host ""
Write-Host "Next:" -ForegroundColor White
Write-Host "  1. Use the GUI Launch button or run .\launcher.ps1." -ForegroundColor White
Write-Host "  2. Browse to http://127.0.0.1:7860 unless you changed host/port." -ForegroundColor White
