"""Temporary capacitor V10 diagnostics from the manual two-terminal-cap donor.

V9 proved that unique visual indexes were not enough: only T01 opened, and
T03 rendered a partial chain. The user then supplied a Proteus-made two
terminal-attached capacitor project. This script treats that donor as the
authority for terminal-capacitor object order:

    header, all output terminals, then input/cap/wire/wire groups.

The first generated cases are byte-exact guards. Later cases mutate only
coordinates, labels/values, and count after the exact donor shape is verified.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR_2026_05_30 = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-30"
for path in (REPO_ROOT / "src", TOOL_DIR_2026_05_30):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generate_capacitor_v4_temp as v4
import generate_capacitor_v5_cap3_temp as v5
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "capacitor_v10_manual_donor_temp_2026_05_31"

OUT_SIZE = 104
IN_SIZE = 103
CAP_SIZE = 366
WIRE_SIZE = 50
TRIMMED_WIRE_SIZE = 49
CAP_BASE_X = -6096000
MANUAL_Y_STEP = 1524000
SAFE_Y_STEP = 2540000


@dataclass(frozen=True)
class ManualCapTemplates:
    header: bytes
    outputs: tuple[bytes, bytes]
    inputs: tuple[bytes, bytes]
    caps: tuple[bytes, bytes]
    wire_lefts: tuple[bytes, bytes]
    wire_rights: tuple[bytes, bytes]
    first_trimmed_wire_right: bytes
    donor_chunk: bytes
    donor_cdb: bytes


@dataclass(frozen=True)
class TerminalCapSpec:
    ref: str
    value: str
    left: str
    right: str
    x: int
    y: int
    cdb_flag: int = 0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def s32(data: bytes, offset: int) -> int:
    return struct.unpack("<i", data[offset : offset + 4])[0]


def manual_suffixes(index: int) -> tuple[int, int]:
    """Return input/output suffixes from the manual donor's observed family."""

    step = 0x0238
    in_suffix = 0x011A + (index - 1) * step
    out_suffix = 0x00E8 + (index - 1) * step
    return in_suffix & 0xFFFF, out_suffix & 0xFFFF


def load_manual_templates(manual_project: Path) -> ManualCapTemplates:
    donor_chunk = _extract_object_chunk(read_internal_file(manual_project, "ROOT.DSN"))
    donor_cdb = read_internal_file(manual_project, "ROOT.CDB")
    expected_len = (
        1
        + 2 * OUT_SIZE
        + IN_SIZE
        + CAP_SIZE
        + WIRE_SIZE
        + TRIMMED_WIRE_SIZE
        + IN_SIZE
        + CAP_SIZE
        + WIRE_SIZE
        + WIRE_SIZE
    )
    if len(donor_chunk) != expected_len:
        raise RuntimeError(f"Manual donor object chunk length {len(donor_chunk)} != {expected_len}.")
    if donor_chunk[0] != 0 or donor_chunk[-1] != 0xFF:
        raise RuntimeError("Manual donor object chunk does not have the expected start/final bytes.")

    cursor = 0
    header = donor_chunk[cursor : cursor + 1]
    cursor += 1
    out1 = donor_chunk[cursor : cursor + OUT_SIZE]
    cursor += OUT_SIZE
    out2 = donor_chunk[cursor : cursor + OUT_SIZE]
    cursor += OUT_SIZE
    in1 = donor_chunk[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    cap1 = donor_chunk[cursor : cursor + CAP_SIZE]
    cursor += CAP_SIZE
    wire1a = donor_chunk[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    wire1b_trim = donor_chunk[cursor : cursor + TRIMMED_WIRE_SIZE]
    cursor += TRIMMED_WIRE_SIZE
    in2 = donor_chunk[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    cap2 = donor_chunk[cursor : cursor + CAP_SIZE]
    cursor += CAP_SIZE
    wire2a = donor_chunk[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    wire2b = donor_chunk[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    if cursor != len(donor_chunk):
        raise RuntimeError("Manual donor split cursor did not end at object chunk boundary.")

    rebuilt = header + out1 + out2 + in1 + cap1 + wire1a + wire1b_trim + in2 + cap2 + wire2a + wire2b
    if rebuilt != donor_chunk:
        raise RuntimeError("Manual donor split/rebuild is not byte-exact.")
    if (wire1b_trim + b"\x00").count(b"WIRE") != 1:
        raise RuntimeError("Manual donor trimmed wire did not preserve the expected WIRE record marker.")

    return ManualCapTemplates(
        header=header,
        outputs=(out1, out2),
        inputs=(in1, in2),
        caps=(cap1, cap2),
        wire_lefts=(wire1a, wire2a),
        wire_rights=(wire1b_trim + b"\x00", wire2b),
        first_trimmed_wire_right=wire1b_trim,
        donor_chunk=donor_chunk,
        donor_cdb=donor_cdb,
    )


def patch_cap_record(template: bytes, spec: TerminalCapSpec, index: int, dx: int, dy: int, in_suffix: int, out_suffix: int) -> bytes:
    record = bytearray(v4.patch_cap(template, spec.ref, spec.value, dx, dy, in_suffix, out_suffix, final=False))
    record[344] = index
    record[-1] = 0x00
    return bytes(record)


def build_terminal_cap_chunk(templates: ManualCapTemplates, specs: list[TerminalCapSpec]) -> tuple[bytes, list[dict[str, Any]]]:
    outputs: list[bytes] = []
    groups: list[bytes] = []
    maps: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        template_index = (index - 1) % 2
        in_suffix, out_suffix = manual_suffixes(index)
        cap_template = templates.caps[template_index]
        dx = spec.x - s32(cap_template, 332)
        dy = spec.y - s32(cap_template, 336)
        input_record = v4.patch_input(templates.inputs[template_index], spec.left, dx, dy, in_suffix)
        output_record = v4.patch_output(templates.outputs[template_index], spec.right, dx, dy, out_suffix)
        cap_record = patch_cap_record(cap_template, spec, index, dx, dy, in_suffix, out_suffix)
        wire_left = v4.patch_wire(templates.wire_lefts[template_index], dx, dy, final=False)
        wire_right_full = v4.patch_wire(templates.wire_rights[template_index], dx, dy, final=index == len(specs))
        wire_right = wire_right_full if index == len(specs) else wire_right_full[:-1]
        outputs.append(output_record)
        groups.extend([input_record, cap_record, wire_left, wire_right])
        maps.append(
            {
                "idx": index,
                "ref": spec.ref,
                "value": spec.value,
                "left": spec.left,
                "right": spec.right,
                "x": spec.x,
                "y": spec.y,
                "in_suffix": f"{in_suffix:04x}",
                "out_suffix": f"{out_suffix:04x}",
                "cap_visual_index_byte_344": index,
                "wire_right_len": len(wire_right),
            }
        )
    chunk = templates.header + b"".join(outputs) + b"".join(groups)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        raise RuntimeError("Built manual-order chunk has invalid start/final bytes.")
    return chunk, maps


def build_cap_cdb(specs: list[TerminalCapSpec]) -> bytes:
    return v5.build_cap_cdb([v5.FreeCap(spec.ref, spec.value, spec.x, spec.y, spec.cdb_flag) for spec in specs])


def validate_manual_order_chunk(chunk: bytes, cap_count: int, *, exact_hash: str | None = None) -> list[str]:
    issues: list[str] = []
    expected_len = 1 + cap_count * OUT_SIZE + cap_count * (IN_SIZE + CAP_SIZE + WIRE_SIZE) + (cap_count - 1) * TRIMMED_WIRE_SIZE + WIRE_SIZE
    if len(chunk) != expected_len:
        issues.append(f"object chunk length {len(chunk)} != {expected_len}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if exact_hash and sha256_bytes(chunk) != exact_hash:
        issues.append("object chunk does not match exact manual donor hash")
    expected_counts = {
        "$TEROUTPUT": cap_count,
        "$TERINPUT": cap_count,
        "CAPACITOR": cap_count,
        "CAP10": cap_count,
        "WIRE": cap_count * 2,
    }
    for marker, expected in expected_counts.items():
        actual = chunk.count(marker.encode("ascii"))
        if actual != expected:
            issues.append(f"{marker} count {actual} != {expected}")
    first_input = chunk.find(b"$TERINPUT")
    first_output = chunk.find(b"$TEROUTPUT")
    first_cap = chunk.find(b"COMPONENT ID")
    if first_output < 0 or first_input < 0 or not first_output < first_input < first_cap:
        issues.append("manual object order is not outputs-first then input/cap groups")
    return issues


def write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    validations: dict[str, Any],
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = build_dsn(
        read_internal_file(base_project, "ROOT.DSN"),
        read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)

    issues = list(validations.get("static_issues", []))
    if _extract_object_chunk(dsn) != object_chunk:
        issues.append("rebuilt ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_capacitor_v10_manual_donor_not_locked",
        "description": description,
        "base_project": base_project.name,
        "donor_header_project": donor_project.name,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "object_chunk": {
                "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
                "$TERINPUT": object_chunk.count(b"$TERINPUT"),
                "CAPACITOR": object_chunk.count(b"CAPACITOR"),
                "CAP10": object_chunk.count(b"CAP10"),
                "WIRE": object_chunk.count(b"WIRE"),
                "1nF": object_chunk.count(b"1nF"),
                "1uF": object_chunk.count(b"1uF"),
            },
            "root_cdb": {
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP": cdb.count(b"CAP"),
                "CAP10": cdb.count(b"CAP10"),
                "1nF": cdb.count(b"1nF"),
                "1uF": cdb.count(b"1uF"),
            },
        },
        "section_pointer_values": pointers,
        "validations": validations,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: sha256_file(output_path),
            cdb_path.name: sha256_file(cdb_path),
            dsn_path.name: sha256_file(dsn_path),
            "object_chunk": sha256_bytes(object_chunk),
            "ROOT.CDB": sha256_bytes(cdb),
        },
        "output_files": [output_path.name, cdb_path.name, dsn_path.name, "manifest.json", "README_TEST_FIRST.txt"],
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n"
        f"{description}\n\n"
        f"Project: {output_path.name}\n"
        f"Static validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    base = registry.get("e001_empty").path
    manual = registry.get("cap2_with_terminals_manual").path
    templates = load_manual_templates(manual)
    manual_hash = sha256_bytes(templates.donor_chunk)
    generated_manual_cdb = build_cap_cdb(
        [
            TerminalCapSpec("C1", "1nF", "N1", "N2", CAP_BASE_X, 3048000),
            TerminalCapSpec("C2", "1nF", "N3", "N4", CAP_BASE_X, 1524000),
        ]
    )
    if generated_manual_cdb != templates.donor_cdb:
        raise RuntimeError("Generated manual two-cap ROOT.CDB does not match the manual donor.")

    cases: list[dict[str, Any]] = []
    cases.append(
        write_case(
            case_id="CAP_V10_T01_EXACT_MANUAL_DONOR_TRANSPLANT",
            description="Exact manual two-terminal-cap object chunk and exact manual ROOT.CDB rebuilt from E001.",
            base_project=base,
            donor_project=manual,
            object_chunk=templates.donor_chunk,
            cdb=templates.donor_cdb,
            validations={
                "manual_project_sha256": sha256_file(manual),
                "manual_object_chunk_sha256": manual_hash,
                "manual_root_cdb_sha256": sha256_bytes(templates.donor_cdb),
                "static_issues": validate_manual_order_chunk(templates.donor_chunk, 2, exact_hash=manual_hash),
            },
        )
    )

    rebuilt_chunk = templates.header + templates.outputs[0] + templates.outputs[1] + templates.inputs[0] + templates.caps[0] + templates.wire_lefts[0] + templates.first_trimmed_wire_right + templates.inputs[1] + templates.caps[1] + templates.wire_lefts[1] + templates.wire_rights[1]
    if rebuilt_chunk != templates.donor_chunk:
        raise RuntimeError("Manual split/rebuilt chunk is not exact.")
    cases.append(
        write_case(
            case_id="CAP_V10_T02_REBUILT_MANUAL_EXACT",
            description="Manual donor split into records and reassembled byte-exact, with generated byte-exact two-cap ROOT.CDB.",
            base_project=base,
            donor_project=manual,
            object_chunk=rebuilt_chunk,
            cdb=generated_manual_cdb,
            validations={
                "split_rebuild_exact_to_manual": True,
                "generated_root_cdb_exact_to_manual": True,
                "static_issues": validate_manual_order_chunk(rebuilt_chunk, 2, exact_hash=manual_hash),
            },
        )
    )

    translated_specs = [
        TerminalCapSpec("C1", "1nF", "N1", "N2", -4318000, 2540000),
        TerminalCapSpec("C2", "1nF", "N3", "N4", -4318000, 0),
    ]
    translated_chunk, translated_maps = build_terminal_cap_chunk(templates, translated_specs)
    cases.append(
        write_case(
            case_id="CAP_V10_T03_TRANSLATED_MANUAL_ORDER",
            description="Two generated terminal-attached capacitors in manual order, translated to a safer vertical spacing.",
            base_project=base,
            donor_project=manual,
            object_chunk=translated_chunk,
            cdb=build_cap_cdb(translated_specs),
            validations={"topology": translated_maps, "static_issues": validate_manual_order_chunk(translated_chunk, 2)},
        )
    )

    renamed_specs = [
        TerminalCapSpec("C3", "1uF", "N5", "N6", -1778000, 2540000),
        TerminalCapSpec("C4", "1uF", "N7", "N8", -1778000, 0),
    ]
    renamed_chunk, renamed_maps = build_terminal_cap_chunk(templates, renamed_specs)
    cases.append(
        write_case(
            case_id="CAP_V10_T04_RENAMED_VALUE_MANUAL_ORDER",
            description="Two generated terminal-attached capacitors in manual order with new refs, terminal labels, and 1uF values.",
            base_project=base,
            donor_project=manual,
            object_chunk=renamed_chunk,
            cdb=build_cap_cdb(renamed_specs),
            validations={"topology": renamed_maps, "static_issues": validate_manual_order_chunk(renamed_chunk, 2)},
        )
    )

    three_specs = [
        TerminalCapSpec("C1", "1nF", "N1", "N2", -6858000, 3048000),
        TerminalCapSpec("C2", "1nF", "N3", "N4", -4318000, 3048000),
        TerminalCapSpec("C3", "1nF", "N5", "N6", -1778000, 3048000),
    ]
    three_chunk, three_maps = build_terminal_cap_chunk(templates, three_specs)
    cases.append(
        write_case(
            case_id="CAP_V10_T05_THREE_TERMINAL_CAPS_MANUAL_ORDER",
            description="Three generated terminal-attached capacitors using the same outputs-first manual order and extrapolated suffixes.",
            base_project=base,
            donor_project=manual,
            object_chunk=three_chunk,
            cdb=build_cap_cdb(three_specs),
            validations={"topology": three_maps, "static_issues": validate_manual_order_chunk(three_chunk, 3)},
        )
    )

    summary = {
        "case": "CAPACITOR_V10_MANUAL_DONOR_TEMP_2026_05_31",
        "status": "temporary_diagnostic_not_locked",
        "trigger": "User reported V9 T01 worked, V9 T03 only rendered a partial dangling chain, and supplied CAp2withterm.pdsprj as the manual authority.",
        "manual_donor": {
            "fixture_id": "cap2_with_terminals_manual",
            "project_sha256": sha256_file(manual),
            "object_chunk_len": len(templates.donor_chunk),
            "object_chunk_sha256": manual_hash,
            "root_cdb_len": len(templates.donor_cdb),
            "root_cdb_sha256": sha256_bytes(templates.donor_cdb),
            "observed_order": [
                "header",
                "$TEROUTPUT N2",
                "$TEROUTPUT N4",
                "$TERINPUT N1",
                "C1 capacitor",
                "C1 left wire",
                "C1 right wire trimmed to 49 bytes",
                "$TERINPUT N3",
                "C2 capacitor",
                "C2 left wire",
                "C2 right wire with final FF",
            ],
        },
        "hypothesis": "Terminal-attached capacitor duplication must use the manual donor's outputs-first ordering and trimmed non-final right-wire record.",
        "test_order": [case["case_id"] for case in cases],
        "decision_rule": [
            "T01 should open if manual donor transplant from E001 is sound.",
            "T02 should open if record splitting/reassembly is sound.",
            "If T03 opens, manual-order coordinate translation is safe.",
            "If T04 opens, same-length ref/label/value mutation is safe for two terminal-attached capacitors.",
            "Test T05 after T03/T04 to see whether the manual-order method scales beyond the donor count.",
        ],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V10 manual-donor diagnostics.\n\n"
        "Open in order:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n\nReport which cases open and any exact Proteus error text.\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
