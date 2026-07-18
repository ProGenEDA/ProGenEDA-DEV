"""Build the versioned EasyEDA Pro newwebsite integration handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import zipfile


WEBSITE_PATHS = (
    "README.md",
    "api.env.easyeda.example",
    "apps/api/src/config.mjs",
    "apps/api/src/server.mjs",
    "apps/api/src/services/artifact-naming.mjs",
    "apps/api/src/services/circuit-generation-service.mjs",
    "apps/api/src/services/circuit-service.mjs",
    "apps/api/src/services/easyeda-executable-service.mjs",
    "apps/api/src/services/easyeda-json-editor-service.mjs",
    "apps/api/src/services/easyeda-main-json-planner-service.mjs",
    "apps/api/src/services/example-circuit-library-service.mjs",
    "apps/api/src/services/prompt-guide-service.mjs",
    "docs/COMPONENT_CATALOG.md",
    "docs/EASYEDA_INTEGRATION.md",
    "docs/FRONTEND.md",
    "package.json",
    "packages/component-registry/registries/EA-A.json",
    "public/assets/easyeda-pro.png",
    "public/get-help.txt",
    "scripts/prerender-public-pages.mjs",
    "scripts/test-easyeda-integration.mjs",
    "scripts/test-easyeda-website-corpus.mjs",
    "src/backend/generationClient.ts",
    "src/contentPages.tsx",
    "src/generation/AnimatedDarkGeneratePage.tsx",
    "src/generation/HistoryPage.tsx",
    "src/generation/KiCadJsonLab.tsx",
    "src/generation/NonAnimatedDarkWorkspace.tsx",
    "src/generation/SupportedComponentsPage.tsx",
    "src/generation/easyedaSupportedComponents.json",
    "src/landing/LandingPage.tsx",
    "src/landing/landingContent.ts",
    "vendor/easyeda",
)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def copy_entry(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--website-staging", type=Path, required=True)
    parser.add_argument("--website-baseline", type=Path, required=True)
    parser.add_argument("--qualification-report", type=Path, required=True)
    parser.add_argument("--corpus-audit", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Easyeda/release/newwebsite_easyeda_handoff_2026_07_17"),
    )
    parser.add_argument(
        "--zip",
        dest="zip_path",
        type=Path,
        default=Path("Easyeda/release/newwebsite-easyeda-handoff-2026_07_17.zip"),
    )
    args = parser.parse_args()

    output = args.output.resolve()
    release_root = (Path.cwd() / "Easyeda" / "release").resolve()
    if release_root not in output.parents:
        raise SystemExit("Output must be inside Easyeda/release.")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    template = Path("Easyeda/release_templates/newwebsite_easyeda").resolve()
    for source in template.iterdir():
        copy_entry(source, output / source.name)
    (output / "apply_handoff.py").chmod(
        (output / "apply_handoff.py").stat().st_mode | stat.S_IXUSR
    )

    overlay = output / "website_files"
    for relative in WEBSITE_PATHS:
        source = args.website_staging.resolve() / relative
        if not source.exists():
            raise SystemExit(f"Missing staged website path: {source}")
        copy_entry(source, overlay / relative)

    evidence = output / "evidence"
    evidence.mkdir()
    shutil.copy2(args.qualification_report, evidence / "qualification_report.json")
    shutil.copy2(args.corpus_audit, evidence / "corpus_audit.json")

    baseline_files: dict[str, str | None] = {}
    overlay_hashes: dict[str, str] = {}
    for source in sorted(path for path in overlay.rglob("*") if path.is_file()):
        relative = source.relative_to(overlay).as_posix()
        baseline_source = args.website_baseline.resolve() / relative
        baseline_files[relative] = digest(baseline_source) if baseline_source.is_file() else None
        overlay_hashes[relative] = digest(source)
    baseline_payload = {
        "schema": "progen-easyeda-newwebsite-baseline/v1",
        "website_commit": "a236ecdb509fbdba7322d4f62360e9f4435b9225",
        "files": baseline_files,
    }
    (output / "baseline_hashes.json").write_text(
        json.dumps(baseline_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    qualification = json.loads(args.qualification_report.read_text(encoding="utf-8"))
    corpus_audit = json.loads(args.corpus_audit.read_text(encoding="utf-8"))
    manifest = {
        "schema": "progen-easyeda-newwebsite-handoff/v1",
        "release_date": "2026-07-17",
        "website_commit": baseline_payload["website_commit"],
        "catalogue": "progen-easyeda-catalogue/v2",
        "executable_sha256": overlay_hashes["vendor/easyeda/progen-easyeda"],
        "website_file_count": len(overlay_hashes),
        "corpus": {
            "inputs": corpus_audit["circuit_count"],
            "archetypes": corpus_audit["archetype_count"],
            "profiles": corpus_audit["variant_profile_count"],
            "logical_kinds": corpus_audit["covered_kind_count"],
            "component_instances": corpus_audit["total_component_instances"],
            "nets": corpus_audit["total_nets"],
        },
        "qualification": {
            key: qualification[key]
            for key in (
                "input_count",
                "passed_count",
                "failed_count",
                "pcb_ready_count",
                "pcb_withheld_count",
                "average_seconds",
                "max_seconds",
                "elapsed_seconds",
            )
        },
        "overlay_sha256": overlay_hashes,
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    zip_path = args.zip_path.resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source in sorted(path for path in output.rglob("*") if path.is_file()):
            archive.write(source, Path(output.name) / source.relative_to(output))
    print(output)
    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
