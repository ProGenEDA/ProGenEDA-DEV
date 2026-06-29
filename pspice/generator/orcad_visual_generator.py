#!/usr/bin/env python3
"""
OrCAD / PSpice visual project generator scaffold.

This is intentionally committed as a durable repo script, not a throwaway sandbox file.

Current phase:
- validate CircuitIR JSON
- create repeatable project package folders
- inventory user-created OrCAD donor projects
- write manifests and hashes

Native OrCAD `.opj/.dsn` visual writing is deliberately not guessed yet. It will be implemented
only after donor projects or a verified OrCAD-supported automation path is available.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable

SUPPORTED_COMPONENT_TYPES = {
    "RESISTOR",
    "CAPACITOR",
    "INDUCTOR",
    "DIODE",
    "ZENER_DIODE",
    "LED",
    "DC_VOLTAGE_SOURCE",
    "AC_VOLTAGE_SOURCE",
    "PULSE_VOLTAGE_SOURCE",
    "GROUND",
    "BJT_NPN",
    "BJT_PNP",
    "NMOS",
    "PMOS",
}

SUPPORTED_ANALYSES = {"OP", "DC", "TRAN", "AC"}


@dataclasses.dataclass(frozen=True)
class Component:
    ref: str
    type: str
    nodes: tuple[str, ...]
    value: str | None = None
    model: str | None = None
    properties: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class AnalysisRequest:
    type: str
    parameters: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class CircuitIR:
    schema_version: str
    project_name: str
    components: tuple[Component, ...]
    analyses: tuple[AnalysisRequest, ...]
    probes: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]


class ValidationError(Exception):
    pass


class NativeBackendNotReadyError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_ref(ref: str) -> str:
    if not isinstance(ref, str) or not ref.strip():
        raise ValidationError("component ref must be a non-empty string")
    return ref.strip().upper()


def normalize_node(node: str) -> str:
    if not isinstance(node, str) or not node.strip():
        raise ValidationError("node name must be a non-empty string")
    n = node.strip().upper()
    if n in {"GND", "GROUND"}:
        return "0"
    return n


def parse_component(raw: dict[str, Any]) -> Component:
    if not isinstance(raw, dict):
        raise ValidationError("component entry must be an object")
    ref = normalize_ref(raw.get("ref", ""))
    ctype = str(raw.get("type", "")).strip().upper()
    if ctype not in SUPPORTED_COMPONENT_TYPES:
        raise ValidationError(f"unsupported component type for {ref}: {ctype}")

    nodes_raw = raw.get("nodes", [])
    if ctype == "GROUND" and not nodes_raw:
        nodes_raw = ["0"]
    if not isinstance(nodes_raw, list):
        raise ValidationError(f"nodes for {ref} must be a list")
    nodes = tuple(normalize_node(str(n)) for n in nodes_raw)

    expected_min_nodes = 1 if ctype == "GROUND" else 2
    if len(nodes) < expected_min_nodes:
        raise ValidationError(f"{ref} requires at least {expected_min_nodes} node(s)")

    props = dict(raw.get("properties", {})) if isinstance(raw.get("properties", {}), dict) else {}
    return Component(
        ref=ref,
        type=ctype,
        nodes=nodes,
        value=raw.get("value"),
        model=raw.get("model"),
        properties=props,
    )


def parse_analysis(raw: dict[str, Any]) -> AnalysisRequest:
    if not isinstance(raw, dict):
        raise ValidationError("analysis entry must be an object")
    atype = str(raw.get("type", "")).strip().upper()
    if atype not in SUPPORTED_ANALYSES:
        raise ValidationError(f"unsupported analysis type: {atype}")
    params = raw.get("parameters", {})
    if not isinstance(params, dict):
        raise ValidationError(f"analysis parameters for {atype} must be an object")
    return AnalysisRequest(type=atype, parameters=dict(params))


def parse_circuit_ir(data: dict[str, Any]) -> CircuitIR:
    if not isinstance(data, dict):
        raise ValidationError("CircuitIR root must be an object")

    schema_version = str(data.get("schema_version", "orcad-pspice-visual-ir/v0.1"))
    project_name = str(data.get("project_name", "generated_orcad_project")).strip()
    if not project_name:
        raise ValidationError("project_name must be non-empty")

    components_raw = data.get("components", [])
    if not isinstance(components_raw, list) or not components_raw:
        raise ValidationError("components must be a non-empty list")

    components = tuple(parse_component(c) for c in components_raw)
    refs = [c.ref for c in components]
    if len(refs) != len(set(refs)):
        raise ValidationError("component refs must be unique")

    analyses = tuple(parse_analysis(a) for a in data.get("analyses", []))
    probes_raw = data.get("probes", [])
    if not isinstance(probes_raw, list):
        raise ValidationError("probes must be a list")

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValidationError("metadata must be an object")

    return CircuitIR(
        schema_version=schema_version,
        project_name=project_name,
        components=components,
        analyses=analyses,
        probes=tuple(dict(p) for p in probes_raw if isinstance(p, dict)),
        metadata=dict(metadata),
    )


def circuit_to_jsonable(circuit: CircuitIR) -> dict[str, Any]:
    return {
        "schema_version": circuit.schema_version,
        "project_name": circuit.project_name,
        "components": [dataclasses.asdict(c) for c in circuit.components],
        "analyses": [dataclasses.asdict(a) for a in circuit.analyses],
        "probes": list(circuit.probes),
        "metadata": circuit.metadata,
    }


def component_summary(circuit: CircuitIR) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in circuit.components:
        counts[c.type] = counts.get(c.type, 0) + 1
    return counts


def net_summary(circuit: CircuitIR) -> dict[str, Any]:
    nets: dict[str, list[str]] = {}
    for c in circuit.components:
        for n in c.nodes:
            nets.setdefault(n, []).append(c.ref)
    return {
        "net_count": len(nets),
        "nets": {k: sorted(v) for k, v in sorted(nets.items())},
    }


def iter_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
    elif path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file():
                yield p


def inventory_donor_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)

    files = []
    for f in iter_files(path):
        rel = f.relative_to(path) if path.is_dir() else Path(f.name)
        files.append(
            {
                "path": str(rel).replace(os.sep, "/"),
                "size_bytes": f.stat().st_size,
                "sha256": sha256_file(f),
                "suffix": f.suffix.lower(),
            }
        )

    return {
        "created_at": utc_now_iso(),
        "source_path": str(path),
        "is_zip": zipfile.is_zipfile(path) if path.is_file() else False,
        "file_count": len(files),
        "files": files,
    }


def create_project_package(circuit: CircuitIR, out_dir: Path, donor_inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    normalized = circuit_to_jsonable(circuit)
    write_json(out_dir / "input.normalized.circuit.json", normalized)

    manifest = {
        "created_at": utc_now_iso(),
        "backend_name": "orcad_pspice_visual_project_generator",
        "backend_status": "scaffold_native_writer_pending_donors_or_verified_automation",
        "project_name": circuit.project_name,
        "input_json_sha256": sha256_bytes(json.dumps(normalized, sort_keys=True).encode("utf-8")),
        "component_counts": component_summary(circuit),
        "net_summary": net_summary(circuit),
        "analysis_count": len(circuit.analyses),
        "probe_count": len(circuit.probes),
        "native_output_status": "not_generated_yet",
        "native_output_reason": "OrCAD native visual writer is gated until donor projects or a verified OrCAD automation path is supplied.",
        "donor_inventory_attached": donor_inventory is not None,
        "donor_inventory": donor_inventory,
        "known_limitations": [
            "This scaffold validates and packages CircuitIR but does not yet write .opj/.dsn visual files.",
            "Do not treat debug netlists as the product output.",
            "The native writer must be implemented from OrCAD-saved donors or vendor-supported automation.",
        ],
    }
    write_json(out_dir / "manifest.json", manifest)

    readme = f"""# Generated OrCAD/PSpice Visual Project Package Scaffold

Project: `{circuit.project_name}`

This package was produced by the repo generator scaffold. It has validated the CircuitIR and created a manifest, but native OrCAD `.opj/.dsn` output is not enabled yet.

Next required input: user-created OrCAD donor projects or a verified OrCAD Capture automation path.

Files:

```text
input.normalized.circuit.json
manifest.json
README_OPEN_FIRST.txt
```

Component counts:

```json
{json.dumps(component_summary(circuit), indent=2, sort_keys=True)}
```
"""
    write_text(out_dir / "README_OPEN_FIRST.txt", readme)
    return manifest


def require_native_backend_ready() -> None:
    raise NativeBackendNotReadyError(
        "Native OrCAD .opj/.dsn generation is intentionally not implemented yet. "
        "Supply manual OrCAD donor projects or a verified Capture automation path first."
    )


def cmd_validate(args: argparse.Namespace) -> int:
    circuit = parse_circuit_ir(read_json(Path(args.input_json)))
    print(json.dumps({"status": "ok", "project_name": circuit.project_name, "component_counts": component_summary(circuit), "net_summary": net_summary(circuit)}, indent=2))
    return 0


def cmd_inventory(args: argparse.Namespace) -> int:
    inventory = inventory_donor_path(Path(args.donor_path))
    if args.out_json:
        write_json(Path(args.out_json), inventory)
    print(json.dumps({"status": "ok", "file_count": inventory["file_count"], "out_json": args.out_json}, indent=2))
    return 0


def cmd_package(args: argparse.Namespace) -> int:
    circuit = parse_circuit_ir(read_json(Path(args.input_json)))
    donor_inventory = None
    if args.donor_path:
        donor_inventory = inventory_donor_path(Path(args.donor_path))
    manifest = create_project_package(circuit, Path(args.out_dir), donor_inventory)
    print(json.dumps({"status": "ok", "out_dir": args.out_dir, "manifest_sha256": sha256_file(Path(args.out_dir) / "manifest.json"), "project_name": manifest["project_name"]}, indent=2))
    return 0


def cmd_generate_native(args: argparse.Namespace) -> int:
    circuit = parse_circuit_ir(read_json(Path(args.input_json)))
    _ = circuit
    require_native_backend_ready()
    return 1


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OrCAD/PSpice visual project generator scaffold")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate CircuitIR JSON")
    v.add_argument("input_json")
    v.set_defaults(func=cmd_validate)

    inv = sub.add_parser("inventory-donor", help="Inventory a donor project folder or zip")
    inv.add_argument("donor_path")
    inv.add_argument("--out-json", default=None)
    inv.set_defaults(func=cmd_inventory)

    pkg = sub.add_parser("package", help="Create a scaffold output package with manifest")
    pkg.add_argument("input_json")
    pkg.add_argument("out_dir")
    pkg.add_argument("--donor-path", default=None)
    pkg.set_defaults(func=cmd_package)

    gen = sub.add_parser("generate-native", help="Future native .opj/.dsn generation entrypoint")
    gen.add_argument("input_json")
    gen.add_argument("out_dir")
    gen.add_argument("--donor-path", required=False)
    gen.set_defaults(func=cmd_generate_native)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValidationError, NativeBackendNotReadyError, FileNotFoundError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
