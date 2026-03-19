$ErrorActionPreference = 'Stop'

$callerCwd = (Get-Location).Path
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $here
try {
  if ($args.Count -lt 1) {
    throw 'Usage: .\logo.ps1 <path-to-logo.png | path-to-logo-pack.zip | path-to-logo-pack-dir> [--dry-run]'
  }

  $sourcePathInput = [string]$args[0]
  $sourcePath = $sourcePathInput
  if (-not [System.IO.Path]::IsPathRooted($sourcePathInput)) {
    $sourcePath = Join-Path $callerCwd $sourcePathInput
  }

  $resolvedSource = Resolve-Path -LiteralPath $sourcePath -ErrorAction SilentlyContinue
  if (-not $resolvedSource) {
    throw "Logo source not found: $sourcePathInput"
  }

  $resolvedSourcePath = $resolvedSource.Path
  $isDirectory = Test-Path -LiteralPath $resolvedSourcePath -PathType Container
  $extension = [System.IO.Path]::GetExtension($resolvedSourcePath).ToLowerInvariant()

  $rest = @()
  if ($args.Count -gt 1) {
    $rest = $args[1..($args.Count - 1)]
  }

  if ($isDirectory -or $extension -eq '.zip') {
    .\apply.ps1 logo --pack $resolvedSourcePath @rest
  } elseif ($extension -eq '.png') {
    .\apply.ps1 logo --image $resolvedSourcePath @rest
  } else {
    throw 'Logo source must be a .png image, a .zip logo pack, or a logo-pack directory.'
  }
} finally {
  Pop-Location
}
