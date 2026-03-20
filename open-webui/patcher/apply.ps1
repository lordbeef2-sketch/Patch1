$ErrorActionPreference = 'Stop'
function Test-HasArg {
  param([object[]]$InputArgs,[string[]]$Names)
  foreach ($item in $InputArgs) {
    if ($Names -contains ([string]$item)) { return $true }
  }
  return $false
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$envRoot = (Resolve-Path (Join-Path $here '..')).Path
$sitePackages = Join-Path $envRoot 'Lib\site-packages'
if (-not (Test-Path $sitePackages)) { $sitePackages = Join-Path $envRoot 'lib\site-packages' }
if (-not (Test-Path $sitePackages)) { throw "Expected site-packages not found: $envRoot" }

$condaCmd = Get-Command conda -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $condaCmd) { throw 'Conda not found in PATH.' }

Push-Location $here
try {
  $cmd = 'apply'
  $rest = @()
  if ($args.Count -gt 0) {
    $first = [string]$args[0]
    if ($first -in @('apply', 'status', 'logo')) {
      $cmd = $first
      if ($args.Count -gt 1) { $rest = $args[1..($args.Count - 1)] }
    } else {
      $rest = $args
    }
  }

  if ($cmd -eq 'apply') {
    $hasDryRun = Test-HasArg -InputArgs $rest -Names @('--dry-run')
    $hasYes = Test-HasArg -InputArgs $rest -Names @('--yes')
    if (-not $hasDryRun -and -not $hasYes) {
      $answer = (Read-Host 'Proceed with apply? This may overwrite patched files if they differ. [y/N]').Trim().ToLowerInvariant()
      if (@('y', 'yes') -notcontains $answer) {
        Write-Host 'Apply canceled.'
        return
      }
      $rest += '--yes'
    }
  }

  & $condaCmd.Source run -p $envRoot python .\tools\patch_openwebui.py --site-packages $sitePackages $cmd @rest
} finally {
  Pop-Location
}
