# Open WebUI Admin Console Patcher

This folder contains a small, self-contained patcher that adds an **admin-only** log console to Open WebUI:

- `GET /admin/console` (HTML)
- `GET /admin/console/app.js` (JS)
- `GET /admin/console/stream` (log stream)

It reuses Open WebUI auth (admin required) and streams server logs + stdout/stderr.

## How to use (any OS)

1) Copy this whole folder (`owui_admin_console_patcher/`) to the machine/env that runs Open WebUI.

2) Run the patcher using the *same Python environment that runs Open WebUI*.

If you’re using a virtualenv/conda env, activate it first so `python` points at the same env as `open-webui`.

- Status:

`python patch_openwebui.py status`

- Apply:

`python patch_openwebui.py apply`

By default, `apply` asks for a `y/n` confirmation before writing changes. Use `--yes` to skip the prompt:

`python patch_openwebui.py apply --yes`

- Replace logo assets:

`python patch_openwebui.py logo --image /path/to/logo.png`

- Replace from logo pack (.zip or directory):

`python patch_openwebui.py logo --pack /path/to/logo-pack.zip`

### Convenience wrappers

- Windows PowerShell:
	- `./status.ps1`
	- `./apply.ps1`
	- `./logo.ps1 /path/to/logo.png`
	- `./logo.ps1 /path/to/logo-pack.zip`
- Linux/macOS:
	- `./status.sh`
	- `./apply.sh`
	- `./logo.sh /path/to/logo.png`
	- `./logo.sh /path/to/logo-pack.zip`

Wrappers are portable and try to auto-detect the Open WebUI environment by:
- preferring an explicit `OWUI_PYTHON` interpreter
- otherwise using Python adjacent to the discovered `open-webui` launcher
- otherwise falling back to `python`/`python3`

They pass `--site-packages` explicitly when detected, to avoid patching the wrong install.

Logo replacement supports either a single PNG (`--image`) or a logo pack zip/directory (`--pack`).
It also updates the default UI branding text to `IMCE AI Interface Aide`.

3) Restart Open WebUI.

## If you can’t import `open_webui`

Run with an explicit path:

- If you know `site-packages`:

`python patch_openwebui.py --site-packages /path/to/site-packages apply`

- If you know the `open_webui` package directory:

`python patch_openwebui.py --open-webui-dir /path/to/site-packages/open_webui apply`

## Backups

Each `apply` creates a timestamped backup under `owui_admin_console_patcher/backups/`.

## Notes

- Upgrading Open WebUI may overwrite patched files; just re-run `apply` after upgrade.
- The patcher is **idempotent** (safe to re-run).
