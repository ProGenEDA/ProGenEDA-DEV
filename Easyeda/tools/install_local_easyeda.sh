#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-/shared/easyeda-pro-linux-x64-3.2.149/easyeda-pro}"
INSTALL_DIR="${HOME}/.local/opt/easyeda-pro"
BIN_DIR="${HOME}/.local/bin"
APPLICATION_DIR="${HOME}/.local/share/applications"
MIME_DIR="${HOME}/.local/share/mime/packages"
test -x "${SOURCE_DIR}/easyeda-pro"
mkdir -p "${INSTALL_DIR}" "${BIN_DIR}" "${APPLICATION_DIR}" "${MIME_DIR}"
cp -R "${SOURCE_DIR}/." "${INSTALL_DIR}/"

if command -v nix >/dev/null 2>&1 && [[ -e /etc/NIXOS ]]; then
    LIBRARY_PATH="$(
        nix-instantiate --eval --strict -E '
          with import <nixpkgs> {};
          lib.makeLibraryPath [
            glib nss nspr dbus atk at-spi2-atk cups gtk3 pango cairo
            libx11 libxcomposite libxdamage libxext libxfixes libxrandr
            mesa libgbm libglvnd libdrm expat libxcb libxkbcommon wayland
            systemd alsa-lib stdenv.cc.cc.lib fontconfig freetype
          ]
        ' | tr -d '"'
    )"
    LOADER="$(
        nix-instantiate --eval --strict -E \
          'with import <nixpkgs> {}; stdenv.cc.bintools.dynamicLinker' |
          tr -d '"'
    )"
    RPATH="\$ORIGIN:${LIBRARY_PATH}"
    nix --extra-experimental-features "nix-command flakes" shell \
        nixpkgs#patchelf -c patchelf \
        --set-interpreter "${LOADER}" \
        --set-rpath "${RPATH}" \
        "${INSTALL_DIR}/easyeda-pro"
    nix --extra-experimental-features "nix-command flakes" shell \
        nixpkgs#patchelf -c patchelf \
        --set-interpreter "${LOADER}" \
        --set-rpath "${RPATH}" \
        "${INSTALL_DIR}/chrome_crashpad_handler"

    cat >"${BIN_DIR}/easyeda-pro" <<EOF
#!/usr/bin/env bash
set -euo pipefail
unset ELECTRON_RUN_AS_NODE ELECTRON_NO_ATTACH_CONSOLE
export LD_LIBRARY_PATH="${LIBRARY_PATH}\${LD_LIBRARY_PATH:+:\${LD_LIBRARY_PATH}}"
exec "${INSTALL_DIR}/easyeda-pro" --no-sandbox --gtk-version=3 "\$@"
EOF
else
    cat >"${BIN_DIR}/easyeda-pro" <<EOF
#!/usr/bin/env bash
set -euo pipefail
unset ELECTRON_RUN_AS_NODE ELECTRON_NO_ATTACH_CONSOLE
exec "${INSTALL_DIR}/easyeda-pro" --no-sandbox --gtk-version=3 "\$@"
EOF
fi
chmod 0755 "${BIN_DIR}/easyeda-pro"

cat >"${MIME_DIR}/easyeda-pro.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-easyeda-project">
    <comment>EasyEDA Pro project</comment>
    <glob pattern="*.eprj"/>
  </mime-type>
</mime-info>
EOF

cat >"${APPLICATION_DIR}/easyeda-pro.desktop" <<EOF
[Desktop Entry]
Categories=Development;Electronics;
Comment=A Simple and Powerful Electronic Circuit Design Tool
Exec=${BIN_DIR}/easyeda-pro %f
Keywords=PCB;EasyEDA;EDA
Icon=${INSTALL_DIR}/icon/icon_128x128.png
GenericName=EasyEDA Pro
Name=EasyEDA Pro
Type=Application
MimeType=application/x-easyeda-project;
EOF

if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database "${HOME}/.local/share/mime"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPLICATION_DIR}"
fi
if command -v xdg-mime >/dev/null 2>&1; then
    xdg-mime default easyeda-pro.desktop application/x-easyeda-project
fi

echo "EasyEDA Pro installed at ${INSTALL_DIR}."
echo ".eprj default application: $(xdg-mime query default application/x-easyeda-project 2>/dev/null || true)"
