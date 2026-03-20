#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info([string]$msg) { Write-Host "[patcher] $msg" -ForegroundColor Cyan }
function Ok([string]$msg) { Write-Host "[patcher] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "[patcher] $msg" -ForegroundColor Yellow }
function Fail([string]$msg) { Write-Host "[patcher] $msg" -ForegroundColor Red; exit 1 }

$PatcherRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $PatcherRoot
Set-Location $Root

$payloadRoot = Join-Path $PatcherRoot "payload"
if (-not (Test-Path $payloadRoot)) {
  Fail "Missing payload directory: $payloadRoot"
}

$files = @(
  "src/backend/base/langflow/api/v1/sso.py",
  "src/backend/base/langflow/api/v1/admin_settings.py",
  "src/backend/base/langflow/api/v1/__init__.py",
  "src/backend/base/langflow/api/v1/flows.py",
  "src/backend/base/langflow/api/v1/flow_version.py",
  "src/backend/tests/unit/api/v1/test_flows.py",
  "src/backend/base/langflow/api/router.py",
  "src/backend/base/langflow/main.py",
  "src/lfx/src/lfx/services/settings/base.py",
  "src/lfx/src/lfx/_assets/component_index.json",
  "src/lfx/src/lfx/base/models/model_utils.py",
  "src/lfx/src/lfx/base/models/unified_models.py",
  "src/lfx/src/lfx/base/models/model_metadata.py",
  "src/lfx/src/lfx/components/processing/data_operations.py",
  "src/lfx/src/lfx/components/processing/parse_json_data.py",
  "src/lfx/src/lfx/components/input_output/openwebui_chat_pushback.py",
  "src/lfx/src/lfx/components/input_output/__init__.py",
  "src/frontend/src/pages/SettingsPage/pages/GeneralPage/components/SsoSettingsCard/index.tsx",
  "src/frontend/src/pages/SettingsPage/pages/OAuthSSOPage/index.tsx",
  "src/frontend/src/pages/SettingsPage/pages/SAMLSSOPage/index.tsx",
  "src/frontend/src/pages/SettingsPage/pages/HTTPSPage/index.tsx",
  "src/frontend/src/pages/SettingsPage/index.tsx",
  "src/frontend/src/routes.tsx",
  "src/frontend/src/pages/SettingsPage/pages/GeneralPage/index.tsx",
  "src/frontend/src/pages/SettingsPage/pages/GeneralPage/components/AuthSecuritySettingsCard/index.tsx",
  "src/frontend/src/pages/AppInitPage/index.tsx",
  "src/frontend/src/pages/FlowPage/index.tsx",
  "src/frontend/src/pages/MainPage/pages/empty-page.tsx",
  "src/frontend/src/controllers/API/index.ts",
  "src/frontend/src/pages/FlowPage/components/UpdateAllComponents/index.tsx",
  "src/frontend/src/CustomNodes/GenericNode/index.tsx",
  "src/frontend/src/controllers/API/helpers/constants.ts",
  "src/frontend/src/controllers/API/queries/auth/use-get-sso-config.ts",
  "src/frontend/src/controllers/API/queries/auth/use-get-sso-providers.ts",
  "src/frontend/src/controllers/API/queries/auth/use-put-sso-config.ts",
  "src/frontend/src/controllers/API/queries/auth/use-get-saml-metadata.ts",
  "src/frontend/src/controllers/API/queries/auth/use-get-https-settings.ts",
  "src/frontend/src/controllers/API/queries/auth/use-put-https-settings.ts",
  "src/frontend/src/controllers/API/queries/auth/use-post-https-file-upload.ts",
  "src/frontend/src/controllers/API/queries/auth/use-get-sso-settings.ts",
  "src/frontend/src/controllers/API/queries/auth/use-put-sso-settings.ts",
  "src/frontend/src/controllers/API/queries/auth/index.ts",
  "src/frontend/src/components/core/appHeaderComponent/components/AccountMenu/index.tsx",
  "src/frontend/src/components/core/appHeaderComponent/components/langflow-counts.tsx",
  "src/frontend/src/components/core/folderSidebarComponent/components/sideBarFolderButtons/components/get-started-progress.tsx",
  "src/frontend/src/components/core/folderSidebarComponent/components/sideBarFolderButtons/components/header-buttons.tsx",
  "src/frontend/src/customization/components/custom-get-started-progress.tsx",
  "src/frontend/src/constants/constants.ts"
)

$authSecurityCardFallback = @'
import type { ConfigResponse } from "@/controllers/API/queries/config/use-get-config";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type AuthSecuritySettingsCardProps = {
  config: ConfigResponse;
};

export default function AuthSecuritySettingsCard({
  config,
}: AuthSecuritySettingsCardProps): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Authentication Security</CardTitle>
        <CardDescription>
          Current authentication and account policy values loaded from server
          settings.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
          <div className="rounded-md border p-3">
            <p className="text-muted-foreground">Public Sign Up</p>
            <p className="font-medium">
              {config.enable_public_signup ? "Enabled" : "Disabled"}
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-muted-foreground">Password Minimum Length</p>
            <p className="font-medium">{config.password_min_length}</p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-muted-foreground">
              Password Character Classes
            </p>
            <p className="font-medium">{config.password_min_character_classes}</p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-muted-foreground">Login Max Attempts</p>
            <p className="font-medium">{config.login_max_attempts}</p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-muted-foreground">Login Attempt Window</p>
            <p className="font-medium">
              {config.login_attempt_window_seconds} seconds
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-muted-foreground">Lockout Duration</p>
            <p className="font-medium">{config.login_lockout_seconds} seconds</p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-muted-foreground">SSO Feature Flag</p>
            <p className="font-medium">
              {config.sso_enabled ? "Enabled" : "Disabled"}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
'@

$getSSOProvidersFallback = @'
import type { useQueryFunctionType } from "@/types/api";
import type { SSOConfigResponseType } from "./use-get-sso-config";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetSSOProviders: useQueryFunctionType<
  undefined,
  SSOConfigResponseType[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const getSSOProvidersFn = async () => {
    const response = await api.get<SSOConfigResponseType[]>(
      `${getURL("SSO")}/providers`,
    );
    return response.data;
  };

  return query(["useGetSSOProviders"], getSSOProvidersFn, {
    refetchOnWindowFocus: false,
    ...options,
  });
};
'@

Info "Restoring feature files from patcher_payload"
$restored = 0
foreach ($rel in $files) {
  $src = Join-Path $payloadRoot $rel
  $dst = Join-Path $Root $rel
  $dstDir = Split-Path -Parent $dst
  if (-not (Test-Path $dstDir)) {
    New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
  }

  if (-not (Test-Path $src)) {
    if ($rel -eq "src/frontend/src/pages/SettingsPage/pages/GeneralPage/components/AuthSecuritySettingsCard/index.tsx") {
      if (-not (Test-Path $dst)) {
        Warn "Payload missing AuthSecuritySettingsCard. Creating fallback component at $rel"
        Set-Content -Path $dst -Value $authSecurityCardFallback -NoNewline
      } else {
        Warn "Payload missing AuthSecuritySettingsCard. Keeping existing file at $rel"
      }
      $restored++
      continue
    }
    if ($rel -eq "src/frontend/src/controllers/API/queries/auth/use-get-sso-providers.ts") {
      if (-not (Test-Path $dst)) {
        Warn "Payload missing use-get-sso-providers. Creating fallback hook at $rel"
        Set-Content -Path $dst -Value $getSSOProvidersFallback -NoNewline
      } else {
        Warn "Payload missing use-get-sso-providers. Keeping existing file at $rel"
      }
      $restored++
      continue
    }
    Fail "Missing payload file: $src"
  }

  Copy-Item -Path $src -Destination $dst -Force
  $restored++
}
Ok "Restored $restored files"

Info "Ensuring LANGFLOW_AUTO_LOGIN=false in .env"
$envFile = Join-Path $Root ".env"
$autoLoginLine = "LANGFLOW_AUTO_LOGIN=false"
if (Test-Path $envFile) {
  $envContent = Get-Content -Path $envFile -Raw
  if ([regex]::IsMatch($envContent, "(?m)^\s*LANGFLOW_AUTO_LOGIN\s*=")) {
    $updated = [regex]::Replace(
      $envContent,
      "(?m)^\s*LANGFLOW_AUTO_LOGIN\s*=.*$",
      $autoLoginLine
    )
    Set-Content -Path $envFile -Value $updated -NoNewline
  } else {
    $trimmed = $envContent.TrimEnd("`r", "`n")
    if ($trimmed.Length -gt 0) {
      $trimmed = $trimmed + "`r`n"
    }
    Set-Content -Path $envFile -Value ($trimmed + $autoLoginLine + "`r`n") -NoNewline
  }
} else {
  Set-Content -Path $envFile -Value ($autoLoginLine + "`r`n") -NoNewline
}
Ok "Configured .env with LANGFLOW_AUTO_LOGIN=false"

# Validate that every export in auth/index.ts points to an existing file.
$authIndexPath = Join-Path $Root "src/frontend/src/controllers/API/queries/auth/index.ts"
if (Test-Path $authIndexPath) {
  $authIndex = Get-Content -Path $authIndexPath -Raw
  $exportRefs = [regex]::Matches($authIndex, 'export \* from "\./([^"]+)";')
  $missing = @()
  foreach ($m in $exportRefs) {
    $name = $m.Groups[1].Value
    $candidate = Join-Path $Root ("src/frontend/src/controllers/API/queries/auth/{0}.ts" -f $name)
    if (-not (Test-Path $candidate)) {
      $missing += $candidate
    }
  }
  if ($missing.Count -gt 0) {
    $list = ($missing | ForEach-Object { " - $_" }) -join "`n"
    Fail "Missing auth query files referenced by auth/index.ts:`n$list"
  }
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
  Info "Syncing Python dependencies with uv"
  uv sync
  if ($LASTEXITCODE -ne 0) {
    Fail "uv sync failed"
  }
} else {
  Warn "uv not found; skipping Python dependency sync"
}

Info "Installing frontend dependencies"
Push-Location "src/frontend"
npm install
if ($LASTEXITCODE -ne 0) {
  Fail "npm install failed"
}

Info "Building frontend"
npm run build
if ($LASTEXITCODE -ne 0) {
  Fail "npm run build failed"
}
Pop-Location

Info "Syncing build output to backend static frontend"
$frontendDest = Join-Path $Root "src/backend/base/langflow/frontend"
if (-not (Test-Path $frontendDest)) {
  New-Item -ItemType Directory -Path $frontendDest -Force | Out-Null
}

Get-ChildItem -Path $frontendDest -Force | Remove-Item -Recurse -Force
Copy-Item -Path "src/frontend/build/*" -Destination $frontendDest -Recurse -Force

Ok "Patch + reinstall completed."
Write-Host "Run: uv run langflow run" -ForegroundColor White