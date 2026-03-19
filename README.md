# Patch1 - Langflow + Open WebUI patch bundles

This repository contains two patchers:

1. Langflow patcher (`patcher.ps1` + `patcher_payload/`)
2. Open WebUI admin console patcher (`owui_admin_console_patcher/`)

This README documents all currently tracked changes that were added to this repository.

## Repository timeline

- `3b91a1b` - Add Langflow patcher and payload
- `a47bcb3` - Add OWUI admin console patcher bundle

## What each patcher does

### 1) Langflow patcher

Path: `patcher.ps1`

Primary behavior:

- Restores a curated set of backend, frontend, and LFX files from `patcher_payload/` into a Langflow checkout.
- Ensures `.env` contains `LANGFLOW_AUTO_LOGIN=false`.
- Validates auth query exports in `src/frontend/src/controllers/API/queries/auth/index.ts`.
- Runs dependency/install/build steps where available:
  - `uv sync`
  - frontend install/build sequence

Notable fallback behavior baked into script:

- If payload is missing `AuthSecuritySettingsCard/index.tsx`, it can generate a fallback component.
- If payload is missing `use-get-sso-providers.ts`, it can generate a fallback hook.

### 2) Open WebUI admin console patcher

Path: `owui_admin_console_patcher/patch_openwebui.py`

Primary behavior:

- Adds admin-only console endpoints to Open WebUI via payload patch files:
  - `/admin/console`
  - `/admin/console/app.js`
  - `/admin/console/stream`
- Supports:
  - `status`
  - `apply` (with optional `--yes`)
  - logo replacement by image (`--image`) or logo pack (`--pack`)
- Performs timestamped backups before patching.
- Validates/locates the target Open WebUI package safely.
- Keeps patching idempotent.

Branding constant included in patcher:

- `IMCE AI Interface Aide`

## Full change inventory

The sections below list all files introduced by each patcher commit.

---

## Commit `3b91a1b` (Langflow patcher and payload)

### Added files

- `.gitignore`
- `patcher.ps1`
- `patcher_payload/src/backend/base/langflow/api/router.py`
- `patcher_payload/src/backend/base/langflow/api/v1/__init__.py`
- `patcher_payload/src/backend/base/langflow/api/v1/admin_settings.py`
- `patcher_payload/src/backend/base/langflow/api/v1/flow_version.py`
- `patcher_payload/src/backend/base/langflow/api/v1/flows.py`
- `patcher_payload/src/backend/base/langflow/api/v1/sso.py`
- `patcher_payload/src/backend/base/langflow/main.py`
- `patcher_payload/src/backend/tests/unit/api/v1/test_flows.py`
- `patcher_payload/src/frontend/src/CustomNodes/GenericNode/index.tsx`
- `patcher_payload/src/frontend/src/components/core/appHeaderComponent/components/AccountMenu/index.tsx`
- `patcher_payload/src/frontend/src/components/core/appHeaderComponent/components/langflow-counts.tsx`
- `patcher_payload/src/frontend/src/components/core/folderSidebarComponent/components/sideBarFolderButtons/components/get-started-progress.tsx`
- `patcher_payload/src/frontend/src/components/core/folderSidebarComponent/components/sideBarFolderButtons/components/header-buttons.tsx`
- `patcher_payload/src/frontend/src/constants/constants.ts`
- `patcher_payload/src/frontend/src/controllers/API/helpers/constants.ts`
- `patcher_payload/src/frontend/src/controllers/API/index.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/index.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-get-https-settings.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-get-saml-metadata.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-get-sso-config.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-get-sso-providers.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-get-sso-settings.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-post-https-file-upload.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-put-https-settings.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-put-sso-config.ts`
- `patcher_payload/src/frontend/src/controllers/API/queries/auth/use-put-sso-settings.ts`
- `patcher_payload/src/frontend/src/customization/components/custom-get-started-progress.tsx`
- `patcher_payload/src/frontend/src/pages/AppInitPage/index.tsx`
- `patcher_payload/src/frontend/src/pages/FlowPage/components/UpdateAllComponents/index.tsx`
- `patcher_payload/src/frontend/src/pages/FlowPage/index.tsx`
- `patcher_payload/src/frontend/src/pages/MainPage/pages/empty-page.tsx`
- `patcher_payload/src/frontend/src/pages/SettingsPage/index.tsx`
- `patcher_payload/src/frontend/src/pages/SettingsPage/pages/GeneralPage/components/AuthSecuritySettingsCard/index.tsx`
- `patcher_payload/src/frontend/src/pages/SettingsPage/pages/GeneralPage/components/SsoSettingsCard/index.tsx`
- `patcher_payload/src/frontend/src/pages/SettingsPage/pages/GeneralPage/index.tsx`
- `patcher_payload/src/frontend/src/pages/SettingsPage/pages/HTTPSPage/index.tsx`
- `patcher_payload/src/frontend/src/pages/SettingsPage/pages/OAuthSSOPage/index.tsx`
- `patcher_payload/src/frontend/src/pages/SettingsPage/pages/SAMLSSOPage/index.tsx`
- `patcher_payload/src/frontend/src/routes.tsx`
- `patcher_payload/src/frontend/src/utils/styleUtils.ts`
- `patcher_payload/src/lfx/src/lfx/_assets/component_index.json`
- `patcher_payload/src/lfx/src/lfx/base/models/model_metadata.py`
- `patcher_payload/src/lfx/src/lfx/base/models/model_utils.py`
- `patcher_payload/src/lfx/src/lfx/base/models/unified_models.py`
- `patcher_payload/src/lfx/src/lfx/components/input_output/__init__.py`
- `patcher_payload/src/lfx/src/lfx/components/input_output/openwebui_chat_pushback.py`
- `patcher_payload/src/lfx/src/lfx/components/processing/data_operations.py`
- `patcher_payload/src/lfx/src/lfx/components/processing/parse_json_data.py`
- `patcher_payload/src/lfx/src/lfx/services/settings/base.py`

### Change scope summary

- Backend API additions for auth/SSO/admin settings and flow API surface.
- Frontend settings/auth page and API query wiring updates.
- LFX model and component updates, including Open WebUI chat pushback component registration.
- Payload test coverage seed for flow API (`test_flows.py`).

---

## Commit `a47bcb3` (OWUI admin console patcher bundle)

### Added files

- `owui_admin_console_patcher/README.md`
- `owui_admin_console_patcher/apply.ps1`
- `owui_admin_console_patcher/apply.sh`
- `owui_admin_console_patcher/backups/20260305-063208-owui-admin-console-v1/open_webui/main.py`
- `owui_admin_console_patcher/backups/20260305-100438-owui-admin-console-v1/open_webui/routers/admin_console.py`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/favicon.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/favicon.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/apple-touch-icon.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/apple-touch-icon.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/favicon-96x96.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/favicon-96x96.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/favicon-dark.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/favicon-dark.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/favicon.ico`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/favicon.ico.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/favicon.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/favicon.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/logo.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/logo.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/splash-dark.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/splash-dark.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/splash.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/splash.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/web-app-manifest-192x192.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/web-app-manifest-192x192.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/web-app-manifest-512x512.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/frontend/static/web-app-manifest-512x512.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/apple-touch-icon.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/apple-touch-icon.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/favicon-96x96.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/favicon-96x96.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/favicon-dark.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/favicon-dark.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/favicon.ico`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/favicon.ico.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/favicon.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/favicon.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/logo.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/logo.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/splash-dark.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/splash-dark.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/splash.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/splash.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/swagger-ui/favicon.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/swagger-ui/favicon.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/web-app-manifest-192x192.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/web-app-manifest-192x192.png.bak`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/web-app-manifest-512x512.png`
- `owui_admin_console_patcher/backups/20260305-102822-owui-admin-console-v1-logo/open_webui/static/web-app-manifest-512x512.png.bak`
- `owui_admin_console_patcher/backups/20260305-103239-owui-admin-console-v1-logo/open_webui/env.py`
- `owui_admin_console_patcher/backups/20260305-103239-owui-admin-console-v1-logo/open_webui/main.py`
- `owui_admin_console_patcher/backups/20260305-121053-owui-admin-console-v1/open_webui/main.py`
- `owui_admin_console_patcher/backups/20260319-082157-owui-admin-console-v1/open_webui/main.py`
- `owui_admin_console_patcher/logo.ps1`
- `owui_admin_console_patcher/logo.sh`
- `owui_admin_console_patcher/patch_openwebui.py`
- `owui_admin_console_patcher/payload/open_webui/routers/admin_console.py`
- `owui_admin_console_patcher/payload/open_webui/utils/console_stream.py`
- `owui_admin_console_patcher/status.ps1`
- `owui_admin_console_patcher/status.sh`

### Change scope summary

- OWUI admin console feature patch payload.
- Cross-platform apply/status/logo wrappers for PowerShell and shell.
- Embedded historical backup snapshots carried into repo.

---

## Operational notes

- Line-ending warnings were observed on some shell and backup files when committing on Windows (`LF` -> `CRLF` conversion warnings).
- Both patchers are now present in the same GitHub repository.

## Maintenance guidance

- If `patcher_payload/` changes in your active Langflow workspace, re-copy those changes into this repository and commit.
- If `owui_admin_console_patcher/` evolves in your OWUI workspace, re-copy and commit to keep this repo authoritative.
- Keep commit messages explicit about which patcher was updated.
