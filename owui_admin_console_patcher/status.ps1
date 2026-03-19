$ErrorActionPreference = 'Stop'

function Get-OwuiTarget {
  $pythonCandidates = @()

  if ($env:OWUI_PYTHON) {
    $pythonCandidates += $env:OWUI_PYTHON
  }

  foreach ($cmdName in @('open-webui', 'open-webui.exe')) {
    $owuiCmd = Get-Command $cmdName -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($owuiCmd) {
      $cmdDir = Split-Path -Parent $owuiCmd.Source
      $adjacentPython = Join-Path $cmdDir 'python.exe'
      if (Test-Path $adjacentPython) {
        $pythonCandidates += $adjacentPython
      }
    }
  }

  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($pythonCmd) {
    $pythonCandidates += $pythonCmd.Source
  }

  $pythonCandidates = @($pythonCandidates | Where-Object { $_ } | Select-Object -Unique)

  foreach ($pythonExe in $pythonCandidates) {
    try {
      $sitePackagesRaw = & $pythonExe -c "import site; c=[]
try:
  c.extend(site.getsitepackages())
except Exception:
  pass
try:
  c.append(site.getusersitepackages())
except Exception:
  pass
seen=set()
for p in c:
  if p and p not in seen:
    seen.add(p)
    print(p)"

      if (-not $sitePackagesRaw) {
        continue
      }

      $sitePackages = @($sitePackagesRaw | Where-Object { $_ })
      foreach ($sp in $sitePackages) {
        if (-not $sp) {
          continue
        }

        $probe = Join-Path $sp 'open_webui\__init__.py'
        if (Test-Path $probe) {
          return [pscustomobject]@{ Python = [string]$pythonExe; SitePackages = [string]$sp }
        }
      }
    } catch {
      continue
    }
  }

  if ($pythonCandidates.Count -gt 0) {
    return [pscustomobject]@{ Python = [string]$pythonCandidates[0]; SitePackages = $null }
  }

  throw 'Could not find a usable Python interpreter. Set OWUI_PYTHON to the Open WebUI environment python.'
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $here
try {
  $target = Get-OwuiTarget
  $pythonExe = [string]$target.Python
  if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    throw 'Resolved Python interpreter path is empty.'
  }

  if ($target.SitePackages) {
    & $pythonExe .\patch_openwebui.py --site-packages ([string]$target.SitePackages) status @args
  } else {
    & $pythonExe .\patch_openwebui.py status @args
  }
} finally {
  Pop-Location
}
