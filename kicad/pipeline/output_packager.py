"""Output artifact packager for generated KiCad projects.

The generator emits many internal records while building a project. This module
creates the final two-artifact boundary expected by the web product:

* a user-downloadable project archive
* a private internal metadata bundle

The packager is intentionally I/O and metadata focused. It does not run routing,
placement, or validation algorithms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
OUTPUT_ARTIFACT_SCHEMA = "progen-kicad-output-artifacts/v0.1"
INTERNAL_BUNDLE_SCHEMA = "progen-kicad-internal-bundle/v0.1"
SERIAL_SERVICE = "KC"
SERIAL_TABLE_VERSION = "A"
USER_PROJECT_ZIP_NAME = "PROGEN_KICAD_PROJECT.zip"
INTERNAL_BUNDLE_ZIP_NAME = "internal_bundle.zip"


def _json_load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, indent=2, sort_keys=True).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_base62(value: int, width: int = 2) -> str:
    if not isinstance(value, int) or value < 0:
        raise ValueError("Base62 value must be a non-negative integer")
    current = value
    encoded = ""
    while True:
        encoded = BASE62_ALPHABET[current % len(BASE62_ALPHABET)] + encoded
        current //= len(BASE62_ALPHABET)
        if current <= 0:
            break
    if len(encoded) > width:
        raise ValueError(f"Base62 value {value} exceeds width {width}")
    return encoded.rjust(width, BASE62_ALPHABET[0])


def _supported_kind_codes() -> dict[str, str]:
    catalogue_path = Path(__file__).resolve().parent / "catelogues" / "component_catalogue.json"
    catalogue = _json_load(catalogue_path)
    components = catalogue.get("components", {})
    if not isinstance(components, dict):
        raise ValueError(f"{catalogue_path} has no components object")
    names: set[str] = set()
    for canonical, spec in components.items():
        names.add(str(canonical).upper())
        if isinstance(spec, dict):
            for alias in spec.get("aliases", []):
                names.add(str(alias).upper())
    return {name: encode_base62(index, 2) for index, name in enumerate(sorted(names))}


def component_summary_from_circuit(circuit: dict[str, Any]) -> dict[str, int]:
    summary: Counter[str] = Counter()
    for component in circuit.get("components", []):
        if not isinstance(component, dict):
            continue
        kind = str(component.get("kind") or component.get("type") or "").strip()
        if kind:
            summary[kind] += 1
    return dict(sorted(summary.items()))


def _component_code(kind: str, kind_codes: dict[str, str]) -> str:
    key = kind.upper()
    if key in kind_codes:
        return kind_codes[key]
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    # Reserve high code space for unknown future components; metadata stores
    # the real kind name so database import can replace this with a registry
    # code later.
    value = 62 * 62 - 1 - int.from_bytes(digest[:2], "big") % 256
    return encode_base62(value, 2)


def _canonical_bom_code(component_summary: dict[str, int], kind_codes: dict[str, str]) -> str:
    tokens = []
    for kind, count in sorted(component_summary.items(), key=lambda item: _component_code(item[0], kind_codes)):
        tokens.append(f"{_component_code(kind, kind_codes)}{encode_base62(int(count), 2)}")
    return "".join(tokens)


def _compress_canonical_bom_code(canonical: str) -> str:
    tokens = [canonical[index : index + 4] for index in range(0, len(canonical), 4)]
    groups: dict[str, list[str]] = {}
    for token in tokens:
        if len(token) != 4:
            raise ValueError("Canonical BOM token length must be four")
        groups.setdefault(token[0], []).append(token[1:])
    return "".join(f"{prefix}+{''.join(items)}+" for prefix, items in sorted(groups.items()))


def build_kicad_serial(circuit: dict[str, Any]) -> dict[str, Any]:
    component_summary = component_summary_from_circuit(circuit)
    kind_codes = _supported_kind_codes()
    canonical = _canonical_bom_code(component_summary, kind_codes)
    compressed = _compress_canonical_bom_code(canonical)
    seed = "|".join(
        [
            str(circuit.get("circuit_id") or ""),
            str(circuit.get("project", {}).get("name") or ""),
            canonical,
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    suffix = "".join(BASE62_ALPHABET[byte % len(BASE62_ALPHABET)] for byte in digest[:4])
    serial = f"{SERIAL_SERVICE}-{SERIAL_TABLE_VERSION}-{compressed}-{suffix}"
    used_code_map = {
        kind: _component_code(kind, kind_codes)
        for kind in component_summary
    }
    return {
        "serial": serial,
        "service": SERIAL_SERVICE,
        "table_version": SERIAL_TABLE_VERSION,
        "canonical_bom_code": canonical,
        "compressed_bom_code": compressed,
        "suffix": suffix,
        "component_summary": component_summary,
        "component_code_map": dict(sorted(used_code_map.items())),
        "compatibility_note": "Serial shape follows the website service/table/compressed-BOM/suffix model; KC registry import must keep component codes append-only.",
    }


def _write_zip(zip_path: Path, entries: list[tuple[str, bytes]]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name.replace("\\", "/").lstrip("/"), content)


def _project_export_entries(project_dir: Path) -> tuple[list[tuple[str, bytes]], str]:
    allowed_suffixes = {".kicad_pro", ".kicad_sch", ".kicad_pcb", ".kicad_sym"}
    allowed_names = {"sym-lib-table", "fp-lib-table"}
    entries: list[tuple[str, bytes]] = []
    main_project_file = ""
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in allowed_suffixes and path.name not in allowed_names:
            continue
        if path.suffix == ".kicad_pro" and not main_project_file:
            main_project_file = str(path.relative_to(project_dir))
        entries.append((f"project/{path.relative_to(project_dir)}", path.read_bytes()))
    if not entries:
        raise ValueError(f"No KiCad project files found in {project_dir}")
    if not main_project_file:
        raise ValueError(f"No .kicad_pro file found in {project_dir}")
    return entries, main_project_file


def _variant_metadata(wire_plan: dict[str, Any]) -> dict[str, Any]:
    selection = wire_plan.get("arrangement_selection", {})
    if not isinstance(selection, dict):
        selection = {}
    selected = str(selection.get("selected_variant") or selection.get("mode") or "accepted")
    raw_variants = selection.get("variants")
    variants: list[dict[str, Any]] = []
    if isinstance(raw_variants, list) and raw_variants:
        for index, item in enumerate(raw_variants):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or f"variant_{index + 1}")
            variants.append(
                {
                    "index": index,
                    "name": name,
                    "accepted": name == selected,
                    "score": item.get("score", {}),
                    "coordinate_edit_count": item.get("coordinate_edit_count"),
                    "elapsed_seconds": item.get("elapsed_seconds"),
                    "error": item.get("error"),
                    "coordinate_plan": item.get("coordinate_plan", {}),
                }
            )
    if not variants:
        variants.append(
            {
                "index": 0,
                "name": selected,
                "accepted": True,
                "score": selection.get("selected_score", selection.get("score", {})),
                "coordinate_edit_count": None,
                "elapsed_seconds": selection.get("elapsed_seconds"),
                "error": selection.get("error"),
                "coordinate_plan": wire_plan.get("coordinate_plan", {}),
            }
        )
    if not any(item["accepted"] for item in variants):
        variants[0]["accepted"] = True
    return {
        "schema": "progen-kicad-arrangement-variant-metadata/v0.1",
        "accepted_variant": next(item["name"] for item in variants if item["accepted"]),
        "variant_count": len(variants),
        "selection": selection,
        "variants": variants,
    }


def package_generated_project(
    *,
    run_dir: Path,
    circuit_id: str,
    project_dir: Path,
    final_json_path: Path,
    placement_input_path: Path,
    routing_input_path: Path,
    wire_plan_path: Path,
    project_manifest_path: Path,
    run_manifest_path: Path,
    component_body_report_path: Path | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create user/export and internal/private artifacts for one generated project."""

    circuit = _json_load(final_json_path)
    wire_plan = _json_load(wire_plan_path)
    serial_info = build_kicad_serial(circuit)
    serial = serial_info["serial"]
    outputs_dir = run_dir / "outputs" / str(circuit_id).lower()
    user_project_zip = outputs_dir / "user_project" / USER_PROJECT_ZIP_NAME
    internal_bundle_zip = outputs_dir / "internal" / INTERNAL_BUNDLE_ZIP_NAME
    output_manifest_path = outputs_dir / "output_manifest.json"

    project_entries, main_project_file = _project_export_entries(project_dir)
    _write_zip(user_project_zip, project_entries)
    user_project_bytes = user_project_zip.read_bytes()
    user_sha = sha256_bytes(user_project_bytes)

    variant_metadata = _variant_metadata(wire_plan)
    generated_json_entries: list[tuple[str, bytes]] = []
    for source in (
        final_json_path,
        placement_input_path,
        routing_input_path,
        wire_plan_path,
        project_manifest_path,
        run_manifest_path,
        component_body_report_path,
    ):
        if source is None or not source.exists():
            continue
        generated_json_entries.append((f"all_generated_json/{source.relative_to(run_dir)}", source.read_bytes()))

    metadata = {
        "schema": OUTPUT_ARTIFACT_SCHEMA,
        "circuit_id": circuit_id,
        "serial": serial,
        "serial_info": serial_info,
        "version": version,
        "backend": "kicad",
        "storage_contract": {
            "user_downloadable": "Only the project archive is returned to the user or public serial download route.",
            "internal_only": "Internal bundle is backend/database only and must never be served by public serial routes.",
        },
        "user_project": {
            "artifact_type": "export_project_file",
            "storage_visibility": "user_downloadable",
            "path": str(user_project_zip.relative_to(run_dir)),
            "file_name": user_project_zip.name,
            "main_project_file": f"project/{main_project_file}",
            "mime_type": "application/zip",
            "size_bytes": user_project_zip.stat().st_size,
            "sha256": user_sha,
        },
        "internal_bundle": {
            "artifact_type": "internal_generation_bundle",
            "storage_visibility": "internal_only",
            "path": str(internal_bundle_zip.relative_to(run_dir)),
            "file_name": internal_bundle_zip.name,
            "mime_type": "application/zip",
            "version": version,
        },
        "database_record_hint": {
            "serial_registry": {
                "serial": serial,
                "service": serial_info["service"],
                "table_version": serial_info["table_version"],
            },
            "artifacts": [
                {
                    "artifact_type": "export_project_file",
                    "storage_visibility": "user_downloadable",
                    "path": str(user_project_zip.relative_to(run_dir)),
                    "sha256": user_sha,
                },
                {
                    "artifact_type": "internal_generation_bundle",
                    "storage_visibility": "internal_only",
                    "path": str(internal_bundle_zip.relative_to(run_dir)),
                },
            ],
        },
        "retained_variants": {
            "accepted_variant": variant_metadata["accepted_variant"],
            "variant_count": variant_metadata["variant_count"],
            "bundle_path": "internal/arrangement-variants.json",
        },
        "source_paths": {
            "final_json": str(final_json_path.relative_to(run_dir)),
            "placement_input": str(placement_input_path.relative_to(run_dir)),
            "routing_input": str(routing_input_path.relative_to(run_dir)),
            "wire_plan": str(wire_plan_path.relative_to(run_dir)),
            "project_manifest": str(project_manifest_path.relative_to(run_dir)),
            "run_manifest": str(run_manifest_path.relative_to(run_dir)),
        },
    }

    internal_entries: list[tuple[str, bytes]] = [
        ("internal/output-metadata.json", _json_bytes(metadata)),
        ("internal/main-input.json", final_json_path.read_bytes()),
        ("internal/placement-input.json", placement_input_path.read_bytes()),
        ("internal/routing-input.json", routing_input_path.read_bytes()),
        ("internal/wire-plan.json", wire_plan_path.read_bytes()),
        ("internal/project-manifest.json", project_manifest_path.read_bytes()),
        ("internal/run-manifest.json", run_manifest_path.read_bytes()),
        ("internal/arrangement-variants.json", _json_bytes(variant_metadata)),
        ("internal/component-summary.json", _json_bytes(serial_info["component_summary"])),
        (f"export/{SERIAL_SERVICE}/{user_project_zip.name}", user_project_bytes),
        *generated_json_entries,
    ]
    if component_body_report_path and component_body_report_path.exists():
        internal_entries.append(("internal/component-body-overlap-report.json", component_body_report_path.read_bytes()))

    _write_zip(internal_bundle_zip, internal_entries)
    metadata["internal_bundle"]["size_bytes"] = internal_bundle_zip.stat().st_size
    metadata["internal_bundle"]["sha256"] = sha256_file(internal_bundle_zip)
    output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_manifest_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def package_project_run(run_dir: Path) -> dict[str, Any]:
    run_manifest_path = run_dir / "run_manifest.json"
    run_manifest = _json_load(run_manifest_path)
    artifacts: list[dict[str, Any]] = []
    for result in run_manifest.get("results", []):
        if not isinstance(result, dict):
            continue
        cid = str(result.get("circuit_id") or "")
        if not cid:
            continue
        final_json_rel = result.get("final_json") or _find_first_matching(run_dir / "final_json", cid, ".json")
        placement_rel = result.get("placement_input") or _find_first_matching(run_dir / "placement_inputs", cid, ".json")
        routing_rel = result.get("routing_input") or _find_first_matching(run_dir / "routing_inputs", cid, ".json")
        wire_rel = result.get("wire_plan") or _find_first_matching(run_dir / "wire_plans", cid, ".json")
        project_dir = run_dir / str(result["project_dir"])
        body_report = project_dir / "component_body_overlap_report.json"
        artifact_metadata = package_generated_project(
            run_dir=run_dir,
            circuit_id=cid,
            project_dir=project_dir,
            final_json_path=run_dir / str(final_json_rel),
            placement_input_path=run_dir / str(placement_rel),
            routing_input_path=run_dir / str(routing_rel),
            wire_plan_path=run_dir / str(wire_rel),
            project_manifest_path=project_dir / "manifest.json",
            run_manifest_path=run_manifest_path,
            component_body_report_path=body_report if body_report.exists() else None,
        )
        result["output_artifacts"] = {
            "serial": artifact_metadata["serial"],
            "user_project": artifact_metadata["user_project"],
            "internal_bundle": artifact_metadata["internal_bundle"],
            "retained_variants": artifact_metadata["retained_variants"],
        }
        project_manifest_path = project_dir / "manifest.json"
        project_manifest = _json_load(project_manifest_path)
        project_manifest["output_artifacts"] = result["output_artifacts"]
        project_manifest_path.write_text(json.dumps(project_manifest, indent=2), encoding="utf-8")
        artifacts.append(artifact_metadata)
    run_manifest["output_artifact_contract"] = {
        "schema": "progen-kicad-run-output-artifacts/v0.1",
        "user_visible_artifact": "user_project",
        "internal_only_artifact": "internal_bundle",
        "artifact_count": len(artifacts),
    }
    run_manifest["output_artifacts"] = artifacts
    run_manifest_path.write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    return {"schema": "progen-kicad-output-packager-run/v0.1", "run_dir": str(run_dir), "artifact_count": len(artifacts), "artifacts": artifacts}


def _find_first_matching(root: Path, circuit_id: str, suffix: str) -> str:
    matches = sorted(root.glob(f"{circuit_id}*{suffix}"))
    if not matches:
        matches = sorted(root.glob(f"{circuit_id.lower()}*{suffix}"))
    if not matches:
        raise FileNotFoundError(f"No {suffix} file for circuit {circuit_id} under {root}")
    return str(matches[0].relative_to(root.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Package generated KiCad run outputs into export/internal artifacts.")
    parser.add_argument("run_dir", help="Generated KiCad project run folder with run_manifest.json.")
    args = parser.parse_args()
    print(json.dumps(package_project_run(Path(args.run_dir)), indent=2))


if __name__ == "__main__":
    main()
