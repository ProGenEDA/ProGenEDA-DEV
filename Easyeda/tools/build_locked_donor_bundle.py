"""Build the compact exact-source donor bundle shipped with the backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sqlite3

from Easyeda.catalogue import CATALOGUE
from Easyeda.donor_source import EasyedaDonorSource, sha256_file


TABLES = ("devices", "attributes", "components", "resources")


def _create_table(
    target: sqlite3.Connection,
    source: sqlite3.Connection,
    table: str,
) -> None:
    row = source.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if row is None or not row[0]:
        raise RuntimeError(f"Source library has no table schema for {table}.")
    target.execute(str(row[0]))


def _insert(target: sqlite3.Connection, table: str, row: dict[str, object]) -> None:
    columns = ", ".join(f'"{name}"' for name in row)
    placeholders = ", ".join("?" for _ in row)
    target.execute(
        f'INSERT OR REPLACE INTO "{table}" ({columns}) VALUES ({placeholders})',
        tuple(row.values()),
    )


def build(source_pack: Path, output: Path) -> dict[str, object]:
    source = EasyedaDonorSource(source_pack)
    paths = source.materialize()
    packets = [source.resolve(entry) for entry in CATALOGUE.values()]
    packets.extend(
        (
            source.resolve_terminal_port(direction="in"),
            source.resolve_terminal_port(direction="out"),
        )
    )
    output.mkdir(parents=True, exist_ok=True)
    library_path = output / "easyeda-std.elib"
    template_path = output / "blank_template.eprj"
    if library_path.exists():
        library_path.unlink()

    with sqlite3.connect(paths.library_path) as schema_source:
        with sqlite3.connect(library_path) as target:
            for table in TABLES:
                _create_table(target, schema_source, table)
            seen_devices: set[str] = set()
            seen_components: set[str] = set()
            seen_resources: set[str] = set()
            for packet in packets:
                device_uuid = str(packet.device["uuid"])
                if device_uuid not in seen_devices:
                    _insert(target, "devices", packet.device)
                    for attribute in packet.attributes:
                        _insert(target, "attributes", attribute)
                    seen_devices.add(device_uuid)
                for component in (packet.symbol, packet.footprint):
                    if component is None:
                        continue
                    component_uuid = str(component["uuid"])
                    if component_uuid not in seen_components:
                        _insert(target, "components", component)
                        seen_components.add(component_uuid)
                for resource in packet.resources:
                    resource_hash = str(resource.get("hash") or resource.get("uuid") or "")
                    if resource_hash and resource_hash not in seen_resources:
                        _insert(target, "resources", resource)
                        seen_resources.add(resource_hash)
            target.execute(
                "CREATE INDEX devices_title_lookup ON devices(lower(title), lower(display_title))"
            )
            target.execute("CREATE INDEX attributes_device_lookup ON attributes(device_uuid)")
            target.execute("CREATE INDEX components_uuid_lookup ON components(uuid)")
            target.execute("CREATE INDEX resources_hash_lookup ON resources(hash)")
            target.commit()
            integrity = target.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise RuntimeError(f"Locked donor database integrity failed: {integrity!r}")

    shutil.copyfile(paths.template_path, template_path)
    manifest = {
        "schema": "progen-easyeda-locked-donor-bundle/v2",
        "catalogue_components": len(CATALOGUE),
        "native_terminal_ports": 2,
        "device_rows": len(seen_devices),
        "component_rows": len(seen_components),
        "resource_rows": len(seen_resources),
        "source_library_sha256": sha256_file(paths.library_path),
        "source_template_sha256": sha256_file(paths.template_path),
        "locked_library_sha256": sha256_file(library_path),
        "locked_template_sha256": sha256_file(template_path),
        "library_path": str(library_path),
        "template_path": str(template_path),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_pack", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Easyeda/donors/locked_catalogue_v2"),
    )
    args = parser.parse_args()
    print(json.dumps(build(args.source_pack, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
