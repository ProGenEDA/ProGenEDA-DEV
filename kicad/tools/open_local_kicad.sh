#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KICAD_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APPDIR="${KICAD_DIR}/.local/AppDir"

if [[ ! -x "${APPDIR}/bin/kicad" ]]; then
  echo "Local KiCad binary was not found at: ${APPDIR}/bin/kicad" >&2
  echo "Expected KiCad to be installed under kicad/.local/AppDir." >&2
  exit 1
fi

export SHARUN_DIR="${APPDIR}"
export APPDIR="${APPDIR}"
export KICAD_STOCK_DATA_HOME="${APPDIR}/share/kicad"
export GIO_MODULE_DIR="${APPDIR}/shared/lib/gio/modules"
export GIO_EXTRA_MODULES=""
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export SHARUN_ALLOW_LD_PRELOAD=1
export LD_PRELOAD="${APPDIR}/shared/lib/jsc-stack-fix.so${LD_PRELOAD:+:${LD_PRELOAD}}"
export XDG_DATA_DIRS="${APPDIR}/share${XDG_DATA_DIRS:+:${XDG_DATA_DIRS}}"
export GDK_PIXBUF_MODULE_FILE="${APPDIR}/shared/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache"
export PYTHONHOME="${APPDIR}/shared"
export PYTHONPATH="${APPDIR}/shared/lib/python3.11/dist-packages:${APPDIR}/shared/lib/python3.11/site-packages${PYTHONPATH:+:${PYTHONPATH}}"

if [[ -d "${APPDIR}/shared/lib/webkit2gtk-4.1" ]]; then
  ln -sfn "${APPDIR}/shared/lib/webkit2gtk-4.1" /tmp/.kicad-wk-helpers
fi

exec "${APPDIR}/bin/kicad" "$@"
