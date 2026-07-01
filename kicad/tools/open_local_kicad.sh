#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KICAD_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APPDIR="${KICAD_DIR}/.local/AppDir"
LAUNCHER="${APPDIR}/bin/kicad"
DESKTOP_ID="progen-local-kicad.desktop"
MIME_TYPE="application/x-kicad-project"

usage() {
  cat <<'EOF'
Usage:
  open_local_kicad.sh [project.kicad_pro]
  open_local_kicad.sh --install-desktop

Environment:
  KICAD_LOCAL_RENDERING=safe    default; force XWayland/software GL for stability
  KICAD_LOCAL_RENDERING=native  use desktop/GPU defaults
EOF
}

desktop_quote() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "${value}"
}

install_desktop_association() {
  local data_home="${XDG_DATA_HOME:-${HOME}/.local/share}"
  local apps_dir="${data_home}/applications"
  local mime_dir="${data_home}/mime/packages"
  local desktop_path="${apps_dir}/${DESKTOP_ID}"
  local mime_path="${mime_dir}/progen-kicad-project.xml"
  local exec_path icon_path

  exec_path="$(desktop_quote "${SCRIPT_DIR}/open_local_kicad.sh")"
  icon_path="${APPDIR}/kicad.png"

  mkdir -p "${apps_dir}" "${mime_dir}"

  cat >"${desktop_path}" <<EOF
[Desktop Entry]
Type=Application
Name=KiCad 10 Local
GenericName=EDA Suite
Comment=Open KiCad projects with the bundled KiCad 10.0.4 AppImage
Exec=${exec_path} %f
Icon=${icon_path}
Terminal=false
Categories=Science;Electronics;
MimeType=${MIME_TYPE};
StartupWMClass=kicad
NoDisplay=false
EOF

  cat >"${mime_path}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="${MIME_TYPE}">
    <comment>KiCad project</comment>
    <glob pattern="*.kicad_pro"/>
  </mime-type>
</mime-info>
EOF

  if command -v xdg-mime >/dev/null 2>&1; then
    xdg-mime install --mode user "${mime_path}" >/dev/null 2>&1 || true
    xdg-mime default "${DESKTOP_ID}" "${MIME_TYPE}"
  fi

  if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database "${data_home}/mime" >/dev/null 2>&1 || true
  fi

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${apps_dir}" >/dev/null 2>&1 || true
  fi

  echo "Installed desktop entry: ${desktop_path}"
  echo "Installed MIME rule: ${mime_path}"
  echo "Default for ${MIME_TYPE}: ${DESKTOP_ID}"
}

case "${1:-}" in
  --help|-h)
    usage
    exit 0
    ;;
  --install-desktop)
    install_desktop_association
    exit 0
    ;;
esac

if [[ ! -x "${LAUNCHER}" ]]; then
  echo "Local KiCad binary was not found at: ${LAUNCHER}" >&2
  echo "Expected KiCad to be installed under kicad/.local/AppDir." >&2
  exit 1
fi

export SHARUN_DIR="${APPDIR}"
export APPDIR="${APPDIR}"
export KICAD_STOCK_DATA_HOME="${APPDIR}/share/kicad"
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1

case "${KICAD_LOCAL_RENDERING:-safe}" in
  safe)
    if [[ -n "${DISPLAY:-}" ]]; then
      export GDK_BACKEND="${KICAD_LOCAL_GDK_BACKEND:-x11}"
    fi
    export GSK_RENDERER="${KICAD_LOCAL_GSK_RENDERER:-cairo}"
    export GDK_RENDERING="${KICAD_LOCAL_GDK_RENDERING:-cairo}"
    export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
    export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"
    ;;
  native)
    ;;
  *)
    echo "Unsupported KICAD_LOCAL_RENDERING=${KICAD_LOCAL_RENDERING}" >&2
    echo "Use 'safe' or 'native'." >&2
    exit 2
    ;;
esac

unset GTK_PATH
unset QT_PLUGIN_PATH
unset QT_QPA_PLATFORM_PLUGIN_PATH
unset LD_PRELOAD
unset SHARUN_ALLOW_LD_PRELOAD

if [[ -d "${APPDIR}/shared/lib/webkit2gtk-4.1" ]]; then
  ln -sfn "${APPDIR}/shared/lib/webkit2gtk-4.1" /tmp/.kicad-wk-helpers
fi

exec "${LAUNCHER}" "$@"
