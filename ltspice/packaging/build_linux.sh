#!/usr/bin/env bash
# Build a single-file Linux executable for the donor-native LTspice generator.
#
# Run this from any directory.  The first optional argument is the directory
# that will receive `progen-ltspice`; it defaults to the repository's ignored
# `dist/progen-ltspice-linux-x86_64` directory.
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="${1:-"${repository_root}/dist/progen-ltspice-linux-x86_64"}"
pyinstaller_bin="${PYINSTALLER_BIN:-pyinstaller}"

if ! command -v "${pyinstaller_bin}" >/dev/null 2>&1; then
    echo "PyInstaller was not found: ${pyinstaller_bin}" >&2
    echo "Install it into the build Python, or set PYINSTALLER_BIN to its executable path." >&2
    exit 2
fi

mkdir -p "${output_dir}"
rm -rf "${output_dir}/build" "${output_dir}/spec" "${output_dir}/progen-ltspice"

"${pyinstaller_bin}" \
    --noconfirm \
    --clean \
    --onefile \
    --name progen-ltspice \
    --paths "${repository_root}" \
    --add-data "${repository_root}/ltspice/catalogues:ltspice/catalogues" \
    --add-data "${repository_root}/ltspice/pipeline/ltspice_component_catalogue.json:ltspice/pipeline" \
    --add-data "${repository_root}/ltspice/pipeline/ltspice_model_map.json:ltspice/pipeline" \
    --add-data "${repository_root}/ltspice/pipeline/ltspice_pin_map.json:ltspice/pipeline" \
    --add-data "${repository_root}/ltspice/pipeline/ltspice_symbol_map.json:ltspice/pipeline" \
    --add-data "${repository_root}/kicad/pipeline/catelogues:kicad/pipeline/catelogues" \
    --distpath "${output_dir}" \
    --workpath "${output_dir}/build" \
    --specpath "${output_dir}/spec" \
    "${repository_root}/ltspice/packaging/progen_ltspice_entry.py"

echo "Built ${output_dir}/progen-ltspice"
