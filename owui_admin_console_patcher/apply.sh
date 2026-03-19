#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

pick_python() {
	if [[ -n "${OWUI_PYTHON:-}" ]] && [[ -x "${OWUI_PYTHON}" ]]; then
		echo "${OWUI_PYTHON}"
		return 0
	fi

	if command -v open-webui >/dev/null 2>&1; then
		local owui_bin
		owui_bin="$(command -v open-webui)"
		local owui_dir
		owui_dir="$(cd "$(dirname "$owui_bin")" && pwd)"
		if [[ -x "$owui_dir/python" ]]; then
			echo "$owui_dir/python"
			return 0
		fi
	fi

	if command -v python3 >/dev/null 2>&1; then
		command -v python3
		return 0
	fi

	if command -v python >/dev/null 2>&1; then
		command -v python
		return 0
	fi

	return 1
}

find_site_packages() {
	local py="$1"
	"$py" - <<'PY'
import site

candidates = []
try:
		candidates.extend(site.getsitepackages())
except Exception:
		pass
try:
		candidates.append(site.getusersitepackages())
except Exception:
		pass

seen = set()
for p in candidates:
		if p and p not in seen:
				seen.add(p)
				print(p)
PY
}

PYTHON_BIN="$(pick_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
	echo "Could not find a usable Python interpreter. Set OWUI_PYTHON to the Open WebUI environment python." >&2
	exit 2
fi

cmd="apply"
rest=()
if [[ $# -gt 0 ]]; then
	case "$1" in
		apply|status|logo)
			cmd="$1"
			shift
			;;
	esac
fi
rest=("$@")

SITE_PACKAGES=""
while IFS= read -r sp; do
	[[ -z "$sp" ]] && continue
	if [[ -f "$sp/open_webui/__init__.py" ]]; then
		SITE_PACKAGES="$sp"
		break
	fi
done < <(find_site_packages "$PYTHON_BIN")

if [[ -n "$SITE_PACKAGES" ]]; then
	"$PYTHON_BIN" ./patch_openwebui.py --site-packages "$SITE_PACKAGES" "$cmd" "${rest[@]}"
else
	"$PYTHON_BIN" ./patch_openwebui.py "$cmd" "${rest[@]}"
fi
