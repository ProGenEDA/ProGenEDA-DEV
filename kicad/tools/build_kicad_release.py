#!/usr/bin/env python3
"""Build the portable KiCad executable and website integration handoff.

The KiCad generator reads JSON/data files through normal filesystem paths, so
the release artifact is a portable executable folder zipped for transport
instead of a zipapp. The launcher sets PYTHONPATH to the bundled ``lib`` folder
and executes the canonical pipeline module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Match kicad.pipeline.output_packager and the current website decoder, which
# uppercases component codes during lookup. Uppercase Base36 avoids collisions.
BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_DATE_LABEL = "2026_07_10"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_text(command: list[str], cwd: Path) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode_base62(value: int, width: int = 2) -> str:
    if value < 0:
        raise ValueError("value must be non-negative")
    encoded = ""
    current = value
    while True:
        encoded = BASE62_ALPHABET[current % len(BASE62_ALPHABET)] + encoded
        current //= len(BASE62_ALPHABET)
        if current == 0:
            break
    if len(encoded) > width:
        raise ValueError(f"value {value} exceeds base62 width {width}")
    return encoded.rjust(width, BASE62_ALPHABET[0])


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def component_registry_from_catalogue(catalogue_path: Path) -> dict[str, Any]:
    catalogue = load_json(catalogue_path)
    components = catalogue.get("components", {})
    if not isinstance(components, dict):
        raise ValueError(f"{catalogue_path} has no components object")

    names: set[str] = set()
    groups: dict[str, list[str]] = {}
    for canonical, spec in components.items():
        canonical_name = str(canonical).upper()
        names.add(canonical_name)
        category = str(spec.get("category") or "other") if isinstance(spec, dict) else "other"
        groups.setdefault(category, []).append(canonical_name)
        if isinstance(spec, dict):
            for alias in spec.get("aliases", []):
                alias_name = str(alias).upper()
                names.add(alias_name)
                groups.setdefault(category, []).append(alias_name)

    sorted_names = sorted(names)
    return {
        "service": "KC",
        "version": "A",
        "base62Alphabet": BASE62_ALPHABET,
        "source": {
            "repo_path": "kicad/pipeline/catelogues/component_catalogue.json",
            "rule": "Codes are assigned exactly like kicad.pipeline.output_packager._supported_kind_codes: sorted upper-case canonical names and aliases, using website-compatible uppercase Base36.",
            "append_only_required": True,
        },
        "components": {
            encode_base62(index, 2): name
            for index, name in enumerate(sorted_names)
        },
        "groups": {
            category: sorted(set(parts))
            for category, parts in sorted(groups.items())
        },
    }


def copy_runtime_tree(root: Path, target: Path) -> None:
    package_root = target / "lib" / "kicad"
    package_root.mkdir(parents=True)
    shutil.copy2(root / "kicad" / "__init__.py", package_root / "__init__.py")

    for relative in [
        "generator",
        "pipeline",
        "rules",
        "source_pack",
    ]:
        source = root / "kicad" / relative
        destination = package_root / relative
        shutil.copytree(source, destination, ignore=ignore_runtime_files)


def ignore_runtime_files(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    path = Path(directory)
    for name in names:
        if name in {"__pycache__", ".pytest_cache", "target", ".mypy_cache"}:
            ignored.add(name)
        elif name.endswith((".pyc", ".pyo", ".tmp", ".log")):
            ignored.add(name)
        elif path.name == "routing" and name == "rust_core":
            ignored.add(name)
    return ignored


def write_executable_folder(root: Path, build_dir: Path, date_label: str) -> dict[str, Any]:
    executable_dir = build_dir / "progen-kicad-portable"
    if executable_dir.exists():
        shutil.rmtree(executable_dir)
    executable_dir.mkdir(parents=True)
    copy_runtime_tree(root, executable_dir)

    launcher = executable_dir / "progen-kicad"
    launcher.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        "HERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
        "export PYTHONPATH=\"$HERE/lib${PYTHONPATH:+:$PYTHONPATH}\"\n"
        "if [[ -d \"$HERE/rust-site\" ]]; then\n"
        "  export PYTHONPATH=\"$HERE/rust-site:$PYTHONPATH\"\n"
        "fi\n"
        "exec \"${PYTHON:-python3}\" -m kicad.pipeline.progen_kicad_executable \"$@\"\n",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    install_rust = executable_dir / "install-rust-core.sh"
    install_rust.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        "HERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
        "WHEEL=\"$(find \"$HERE/rust-wheels\" -maxdepth 1 -type f -name 'progen_routing_core-*.whl' | head -n 1 || true)\"\n"
        "if [[ -z \"$WHEEL\" ]]; then\n"
        "  echo 'No progen_routing_core wheel found in rust-wheels/.' >&2\n"
        "  exit 1\n"
        "fi\n"
        "mkdir -p \"$HERE/rust-site\"\n"
        "\"${PYTHON:-python3}\" -m pip install --upgrade --target \"$HERE/rust-site\" \"$WHEEL\"\n"
        "\"${PYTHON:-python3}\" - <<'PY'\n"
        "import importlib.util\n"
        "raise SystemExit(0 if importlib.util.find_spec('progen_routing_core') else 1)\n"
        "PY\n",
        encoding="utf-8",
    )
    install_rust.chmod(install_rust.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    rust_wheels = executable_dir / "rust-wheels"
    rust_wheels.mkdir()
    source_wheel_dir = root / "kicad" / "pipeline" / "routing" / "rust_core" / "target" / "wheels"
    copied_wheels: list[str] = []
    if source_wheel_dir.exists():
        for wheel in sorted(source_wheel_dir.glob("progen_routing_core-*.whl")):
            shutil.copy2(wheel, rust_wheels / wheel.name)
            copied_wheels.append(wheel.name)

    readme = executable_dir / "README.md"
    readme.write_text(
        textwrap.dedent(
            f"""\
            # ProGenEDA KiCad Portable Executable

            Built: {date_label}

            Run:

            ```bash
            ./progen-kicad run path/to/main.json --output-root /tmp/progen-kicad-out --routing-mode combination
            ```

            The executable is a portable folder, not a zipapp, because the KiCad
            pipeline intentionally reads bundled KiCad source/catalogue files by
            filesystem path.

            Rust routing core:

            - The Python pipeline works without the Rust extension and falls back
              to the verified Python router.
            - To enable the bundled CPython wheel on a compatible Linux/Python
              host, run `./install-rust-core.sh` once inside this folder.
            - The launcher automatically adds `rust-site/` to `PYTHONPATH`.

            Website contract:

            - Input: canonical ProGenEDA main JSON or a folder of main JSON files.
            - Default mode: `combination`.
            - User artifact: `PROGEN_KICAD_PROJECT.zip`.
            - Internal artifact: `internal_bundle.zip` containing every JSON,
              validation report, retained route/placement variants, and the
              generated project export under `export/KC/`.
            """
        ),
        encoding="utf-8",
    )

    return {
        "path": str(executable_dir),
        "launcher": str(launcher.relative_to(executable_dir)),
        "rust_wheels": copied_wheels,
    }


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive_name = path.relative_to(source_dir.parent).as_posix()
                info = zipfile.ZipInfo.from_file(path, archive_name)
                info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
                with path.open("rb") as handle:
                    archive.writestr(info, handle.read(), compress_type=zipfile.ZIP_DEFLATED)


def write_website_files(root: Path, handoff_dir: Path, registry: dict[str, Any]) -> None:
    website_files = handoff_dir / "website_files"
    registry_dir = website_files / "packages" / "component-registry" / "registries"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "KC-A.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")

    services_dir = website_files / "apps" / "api" / "src" / "services"
    services_dir.mkdir(parents=True, exist_ok=True)
    (services_dir / "kicad-executable-service.mjs").write_text(KICAD_ADAPTER_MJS, encoding="utf-8")

    frontend_dir = website_files / "src" / "generation"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    supported_parts = {
        "service": "KC",
        "version": "A",
        "groups": registry["groups"],
        "totalSupportedWords": len(registry["components"]),
        "note": "Generated from KiCad component catalogue canonical names plus aliases.",
    }
    (frontend_dir / "kicadSupportedComponents.json").write_text(
        json.dumps(supported_parts, indent=2),
        encoding="utf-8",
    )

    docs_dir = website_files / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "KICAD_WEBSITE_INTEGRATION.md").write_text(WEBSITE_INTEGRATION_MD, encoding="utf-8")
    (website_files / "api.env.kicad.example").write_text(API_ENV_EXAMPLE, encoding="utf-8")

    example_dir = handoff_dir / "examples"
    example_dir.mkdir(parents=True, exist_ok=True)
    sample = root / "kicad" / "examples" / "ee215_diode_iv.json"
    if sample.exists():
        shutil.copy2(sample, example_dir / sample.name)


def write_audit_docs(handoff_dir: Path, registry: dict[str, Any]) -> None:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "README.md").write_text(
        HANDOFF_README_MD.format(component_count=len(registry["components"])),
        encoding="utf-8",
    )
    (handoff_dir / "NEWEBSITE_KICAD_AUDIT.md").write_text(NEWEBSITE_AUDIT_MD, encoding="utf-8")
    (handoff_dir / "IMPLEMENTATION_CHECKLIST.md").write_text(IMPLEMENTATION_CHECKLIST_MD, encoding="utf-8")


def write_build_manifest(
    *,
    root: Path,
    release_root: Path,
    executable_zip: Path,
    handoff_zip: Path,
    registry: dict[str, Any],
    date_label: str,
) -> dict[str, Any]:
    try:
        git_commit = run_text(["git", "rev-parse", "HEAD"], root)
    except Exception:
        git_commit = "unknown"
    manifest = {
        "schema": "progen-kicad-release-build/v0.1",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "date_label": date_label,
        "git_commit": git_commit,
        "artifacts": {
            "portable_executable_zip": {
                "path": str(executable_zip.relative_to(root)),
                "size_bytes": executable_zip.stat().st_size,
                "sha256": sha256_file(executable_zip),
            },
            "newwebsite_handoff_zip": {
                "path": str(handoff_zip.relative_to(root)),
                "size_bytes": handoff_zip.stat().st_size,
                "sha256": sha256_file(handoff_zip),
            },
        },
        "kicad_registry": {
            "service": "KC",
            "version": "A",
            "component_word_count": len(registry["components"]),
            "group_count": len(registry["groups"]),
        },
        "verification": {
            "run_executable_help": f"unzip {executable_zip.name} && ./progen-kicad-portable/progen-kicad --help",
            "smoke_command": "./progen-kicad-portable/progen-kicad run examples/ee215_diode_iv.json --output-root /tmp/progen-kicad-smoke --routing-mode combination",
        },
    }
    manifest_path = release_root / f"kicad_release_manifest_{date_label}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


KICAD_ADAPTER_MJS = """\
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function runProcess(command, args, options = {}) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: { ...process.env, ...(options.env || {}) },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) {
        resolveRun({ stdout, stderr });
        return;
      }
      const error = new Error(stderr || stdout || `KiCad executable exited ${code}.`);
      error.statusCode = 422;
      error.stdout = stdout;
      error.stderr = stderr;
      reject(error);
    });
  });
}

function parseLastJson(stdout) {
  const text = String(stdout || '').trim();
  const start = text.lastIndexOf('\\n{');
  const jsonText = start >= 0 ? text.slice(start + 1) : text;
  return JSON.parse(jsonText);
}

function firstGeneratedProject(summary) {
  const generation = summary?.generation;
  const results = generation?.results || [];
  const first = results.find((item) => item?.output_artifacts?.user_project);
  if (!first) throw new Error('KiCad executable did not return a user project artifact.');
  return {
    generationRunDir: generation.run_dir,
    result: first,
    userProject: first.output_artifacts.user_project,
    internalBundle: first.output_artifacts.internal_bundle,
    serial: first.output_artifacts.serial,
  };
}

export async function generateWithKiCadExecutable({
  mainJson,
  prompt = '',
  config,
  routingMode = 'combination',
  terminalSmoke = false,
}) {
  if (!mainJson || typeof mainJson !== 'object') {
    const error = new Error('KiCad generation requires canonical mainJson.');
    error.statusCode = 400;
    throw error;
  }

  const executablePath = config.kicadExecutablePath || process.env.PROGEN_KICAD_EXECUTABLE_PATH;
  if (!executablePath) {
    const error = new Error('PROGEN_KICAD_EXECUTABLE_PATH is not configured.');
    error.statusCode = 500;
    throw error;
  }

  const workRoot = resolve(config.kicadWorkDir || process.env.PROGEN_KICAD_WORK_DIR || join(tmpdir(), 'progen-kicad-website-runs'));
  const tempDir = await mkdtemp(join(tmpdir(), 'progen-kicad-input-'));
  const inputPath = join(tempDir, 'main.json');
  await writeFile(inputPath, JSON.stringify(mainJson, null, 2), 'utf8');

  const args = [
    'run',
    inputPath,
    '--output-root',
    workRoot,
    '--label',
    'website_kicad',
    '--routing-mode',
    routingMode,
  ];
  if (terminalSmoke) args.push('--terminal-smoke');

  const command = executablePath.endsWith('.py') ? (process.env.PYTHON || 'python3') : executablePath;
  const commandArgs = executablePath.endsWith('.py') ? [executablePath, ...args] : args;
  const { stdout, stderr } = await runProcess(command, commandArgs);
  const summary = parseLastJson(stdout);
  const project = firstGeneratedProject(summary);
  const exportPath = resolve(project.generationRunDir, project.userProject.path);
  const internalPath = resolve(project.generationRunDir, project.internalBundle.path);
  const exportBuffer = await readFile(exportPath);
  const internalBuffer = await readFile(internalPath);

  return {
    exportBuffer,
    fileName: project.userProject.file_name,
    componentSummary: summary.generation.output_artifacts?.[0]?.serial_info?.component_summary
      || project.result.component_summary
      || {},
    serialInfo: summary.generation.output_artifacts?.[0]?.serial_info || null,
    internalCircuit: {
      schemaVersion: 'progen-kicad-executable-adapter/v0.1',
      service: 'KC',
      prompt,
      executableSummary: summary,
      internalBundleBase64: internalBuffer.toString('base64'),
      exportFileName: project.userProject.file_name,
    },
    validationReport: {
      status: 'passed',
      checks: [
        'kicad_input_json_fixed',
        'kicad_generation_completed',
        'kicad_local_netlist_passed',
        'kicad_final_validation_passed',
      ],
      executableRunDir: summary.run_dir,
      stderr,
    },
    modelRouting: {
      provider: 'progen-kicad',
      model: 'deterministic-executable',
      adapter: 'progen-kicad-executable',
    },
    generationMetadata: {
      temporary: false,
      routingMode,
      generatedAt: new Date().toISOString(),
      executableRunDir: summary.run_dir,
    },
    providerUsage: {
      inputTokens: null,
      outputTokens: null,
      totalTokens: null,
      source: 'deterministic-executable',
    },
  };
}
"""


API_ENV_EXAMPLE = """\
# Append these to newwebsite/api.env when enabling KiCad generation.
PROGEN_KICAD_EXECUTABLE_PATH=/absolute/path/to/progen-kicad-portable/progen-kicad
PROGEN_KICAD_WORK_DIR=/absolute/path/to/newwebsite/local-data/temp-artifacts/kicad-runs
"""


HANDOFF_README_MD = """\
# KiCad Website Integration Handoff

This package contains the KiCad generator executable and the files/notes needed
to add KiCad support to `newwebsite`.

Artifacts in this release:

- `../progen-kicad-portable-2026_07_10.zip`: portable KiCad executable folder.
- `website_files/packages/component-registry/registries/KC-A.json`: KiCad serial
  registry with {component_count} supported component words.
- `website_files/apps/api/src/services/kicad-executable-service.mjs`: Node adapter
  for invoking the executable from the website API.
- `website_files/src/generation/kicadSupportedComponents.json`: frontend-ready
  KiCad supported component groups.
- `NEWEBSITE_KICAD_AUDIT.md`: exact Proteus-only points found in the website.
- `IMPLEMENTATION_CHECKLIST.md`: ordered implementation steps.

The current KiCad schematic pipeline is ready for the supported combination and
terminal flows. The website still needs integration work because its generation
UI and temporary backend bridge currently force Proteus.
"""


NEWEBSITE_AUDIT_MD = """\
# newwebsite KiCad Integration Audit

Analyzed folder: `/home/zaruka/Documents/newwebsite`

## Already service-aware

- `apps/api/src/server.mjs` accepts `targetService` and whitelists `KC`.
- `apps/api/src/services/circuit-service.mjs` already maps `KC` to `KiCad`.
- `packages/serial-system/index.mjs` parses generic `<SERVICE>-<TABLE>-...`
  serials and can load service-specific registries.

## Proteus-only or Proteus-shaped points to change

- `packages/component-registry/registries/PR-A.json` is the only registry. Add
  `KC-A.json` from this handoff. KiCad uses uppercase Base36 component codes so
  the current website decoder does not collide lowercase Base62 codes.
- `src/temp/legacyGeneratorClient.ts` posts `targetService: 'PR'` and assumes
  `.pdsprj` fallback names. Add a selected target service and use `KC` when the
  user chooses KiCad.
- `apps/api/src/services/temp-generator-service.mjs` always calls the temporary
  Proteus bridge and does not pass `service`. Route `service === 'KC'` to the
  provided `generateWithKiCadExecutable` adapter.
- `packages/storage-adapter/local-storage-service.mjs` stores internal export
  copies under `export/PR/${exportFileName}`. Change that to
  `export/${service}/${exportFileName}`.
- `apps/api/src/server.mjs` returns `fileName: 'project.pdsprj'` from
  `POST /api/circuits/:serial/download`. Use the actual artifact file name.
- `src/generation/SupportedComponentsPage.tsx` is hardcoded with Proteus-era
  groups and copy. Add service tabs or a service filter and load the KiCad
  groups from `kicadSupportedComponents.json`.
- `src/generation/AnimatedDarkGeneratePage.tsx` locks KiCad in the target menu
  and visible copy says Proteus-ready. Unlock KiCad and pass the selected EDA to
  `generateWithTempLegacy`.
- `src/generation/NonAnimatedDarkWorkspace.tsx` has `.pdsprj` and Proteus status
  copy. Make it service/file-extension aware.
- `src/generation/HistoryPage.tsx` has a Proteus-only insight label and an empty
  KiCad logo path. The service filter already includes KiCad.
- Docs (`docs/RUNBOOK.md`, `docs/BACKEND.md`, `docs/ARCHITECTURE.md`,
  `docs/IMPLEMENTATION_AUDIT.md`) describe only PR-A/Proteus export examples.

## Generator boundary

The KiCad executable takes canonical ProGenEDA main JSON, not a raw natural
language prompt. The website therefore needs either:

1. a prompt-to-main-json route before invoking the KiCad adapter, or
2. an API payload that already includes `mainJson` for KiCad requests.

After `mainJson` exists, the executable fixes/validates it, generates KiCad
projects, creates user/internal artifacts, and writes validation manifests.
"""


IMPLEMENTATION_CHECKLIST_MD = """\
# Website KiCad Implementation Checklist

1. Copy `website_files/packages/component-registry/registries/KC-A.json` into
   `newwebsite/packages/component-registry/registries/KC-A.json`.
2. Copy `website_files/apps/api/src/services/kicad-executable-service.mjs` into
   `newwebsite/apps/api/src/services/kicad-executable-service.mjs`.
3. Add the `api.env.kicad.example` variables to `newwebsite/api.env`.
4. Update `apps/api/src/config.mjs` with `kicadExecutablePath` and `kicadWorkDir`.
5. In `apps/api/src/services/temp-generator-service.mjs`, route `service === 'KC'`
   to `generateWithKiCadExecutable({ mainJson, prompt, config })`.
6. Extend `/api/generate` to accept or obtain `mainJson` when `targetService` is
   `KC`. Keep natural prompt generation blocked until prompt-to-main-json is
   wired.
7. In `packages/storage-adapter/local-storage-service.mjs`, change internal
   bundle export path from `export/PR/...` to `export/${service}/...`.
8. In `apps/api/src/server.mjs`, return the stored artifact file name for
   `POST /api/circuits/:serial/download`.
9. Update `src/temp/legacyGeneratorClient.ts` to accept a selected service and
   stop hardcoding `targetService: 'PR'`.
10. Unlock KiCad in `src/generation/AnimatedDarkGeneratePage.tsx` and pass the
    selected service through the client.
11. Make download modal/shared serial/workspace copy service-aware; KiCad
    downloads are `PROGEN_KICAD_PROJECT.zip`.
12. Replace or extend `SupportedComponentsPage.tsx` with service tabs and import
    `kicadSupportedComponents.json` for the KiCad component menu.
13. Update docs/runbook examples with `KC-A` serial examples and `.zip` KiCad
    project exports.
14. Smoke test:

    ```bash
    ./progen-kicad-portable/progen-kicad run examples/ee215_diode_iv.json \\
      --output-root /tmp/progen-kicad-smoke \\
      --routing-mode combination
    ```

15. Website smoke test:

    - POST `/api/generate` with `targetService: "KC"` and canonical `mainJson`.
    - Confirm DB service is `KC`.
    - Confirm serial starts with `KC-A-`.
    - Confirm export artifact is `PROGEN_KICAD_PROJECT.zip`.
    - Confirm internal bundle contains `export/KC/PROGEN_KICAD_PROJECT.zip`.
"""


WEBSITE_INTEGRATION_MD = """\
# KiCad Website Integration Contract

The KiCad generator is deterministic after it receives canonical main JSON.

## API input

For the first KiCad website integration, use:

```json
{
  "prompt": "optional original user prompt",
  "targetService": "KC",
  "mainJson": {
    "circuit_id": "demo",
    "components": [],
    "nets": [],
    "routing": { "mode": "combination" }
  }
}
```

Do not call the KiCad executable with only a natural-language prompt. The prompt
enhancer/final JSON compiler is a separate upstream stage.

## Executable output

The executable prints a JSON run manifest. For each generated circuit:

- `output_artifacts.serial`
- `output_artifacts.user_project.path`
- `output_artifacts.user_project.file_name`
- `output_artifacts.internal_bundle.path`

The website should store the user project zip as the public export artifact and
store the internal bundle privately.

## Serial registry

Install `KC-A.json` next to `PR-A.json`. KiCad serials use:

```text
KC-A-<COMPRESSED_BOM_CODE>-<SUFFIX4>
```

`KC-A` codes must remain append-only once public serials exist.
"""


def build_release(release_root: Path, date_label: str) -> dict[str, Any]:
    root = repo_root()
    release_root = release_root.resolve()
    release_root.mkdir(parents=True, exist_ok=True)
    build_root = release_root / ".build" / date_label
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)

    registry = component_registry_from_catalogue(
        root / "kicad" / "pipeline" / "catelogues" / "component_catalogue.json"
    )

    executable_info = write_executable_folder(root, build_root, date_label)
    executable_zip = release_root / f"progen-kicad-portable-{date_label}.zip"
    zip_directory(Path(executable_info["path"]), executable_zip)

    handoff_dir = release_root / f"newwebsite_kicad_handoff_{date_label}"
    if handoff_dir.exists():
        shutil.rmtree(handoff_dir)
    write_audit_docs(handoff_dir, registry)
    write_website_files(root, handoff_dir, registry)
    handoff_zip = release_root / f"newwebsite-kicad-handoff-{date_label}.zip"
    zip_directory(handoff_dir, handoff_zip)

    manifest = write_build_manifest(
        root=root,
        release_root=release_root,
        executable_zip=executable_zip,
        handoff_zip=handoff_zip,
        registry=registry,
        date_label=date_label,
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build KiCad executable and newwebsite handoff artifacts.")
    parser.add_argument("--release-root", type=Path, default=repo_root() / "kicad" / "release")
    parser.add_argument("--date-label", default=DEFAULT_DATE_LABEL)
    args = parser.parse_args()

    manifest = build_release(args.release_root, args.date_label)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="progen-kicad-release-"):
        main()
