#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_ROOT="$(cd "$HERE/.." && pwd)"
SITE_PACKAGES="$ENV_ROOT/lib/site-packages"
[ -d "$SITE_PACKAGES" ] || SITE_PACKAGES="$ENV_ROOT/Lib/site-packages"
conda run -p "$ENV_ROOT" python "$HERE/tools/patch_openwebui.py" --site-packages "$SITE_PACKAGES" status
