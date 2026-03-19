#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ $# -lt 1 ]]; then
  echo "Usage: ./logo.sh <path-to-logo.png | path-to-logo-pack.zip | path-to-logo-pack-dir> [--dry-run]" >&2
  exit 2
fi

source_path="$1"
shift

if [[ -d "$source_path" || "${source_path,,}" == *.zip ]]; then
  ./apply.sh logo --pack "$source_path" "$@"
elif [[ "${source_path,,}" == *.png ]]; then
  ./apply.sh logo --image "$source_path" "$@"
else
  echo "Logo source must be a .png image, a .zip logo pack, or a logo-pack directory." >&2
  exit 2
fi
