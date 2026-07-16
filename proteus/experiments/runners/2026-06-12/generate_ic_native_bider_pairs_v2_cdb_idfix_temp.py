"""Generate native IC pair and small-mix cases with bidirectional terminals.

This pack follows the user result for IC_NATIVE_QUAD_MIX_V1:

- Q000-Q009 worked and simulated, but those donor-native mix controls had no
  bider pins on several cases.
- Q010 and onward 4060/4520-adjacent pair controls are rejected for now.

The goal here is not to promote production support. It is to create a testable
temporary pack where each component comes from its own terminal-bearing native
solo donor, refs are remapped with same-length U refs, and at least one
same-name bider net connects each pair.

V2 adds a strict binary ROOT.CDB identity pass. Reusing multiple single donors
can leave pin/property rows with the same hidden object IDs even after visible
U refs are changed. Proteus reports those as duplicate part references such as
``U2 [U1]`` or duplicate ``X000000...`` rows during simulation. This pass keeps
the donor rows intact except for the known little-endian object-ID fields.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from itertools import combinations
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "proteus" / "active" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PAIRWISE_V2_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-10" / "generate_ic_pairwise_34_v2_temp.py"
CDB_V2_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_mixed_ic_cross_donor_v2_metadata_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_native_bider_pairs_v2_cdb_idfix_temp_2026_06_12"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "IC_NATIVE_BIDER_PAIRS_V2_CDB_IDFIX_TEMP_2026_06_12.zip"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load helper module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pairwise = _load_module("ic_pairwise_34_v2_for_native_bider_pairs", PAIRWISE_V2_SCRIPT)
cdb_v2 = _load_module("mixed_ic_cdb_v2_for_native_bider_pairs", CDB_V2_SCRIPT)

from proteusgen.cdb import package_ref  # noqa: E402
from proteusgen.ic_native import (  # noqa: E402
    NativeRegistry,
    _extract_object_chunk,
    bidir_events,
    device_section,
    marker_counts,
    parse_pin_label,
    patch_bidir_labels,
    read_internal_file,
)
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402
from proteusgen.pdsprj import inspect_pdsprj, write_project_from_parts  # noqa: E402


CORE_PARTS = (
    "7490",
    "74HC160",
    "74HC161",
    "74HC163",
    "74HC192",
    "74HC193",
    "4017",
    "4020",
    "74HC4024",
    "74HC4040",
    "4518",
    "74HC74",
    "74HC76",
    "74HC174",
    "74HC273",
    "4027",
    "74HC85",
    "74HC283",
    "74HC157",
    "74HC47",
    "74HC165",
    "74HC595",
    "NE555",
    "LM741",
)

EXCLUDED_MODEL_FOLLOWUP = {"74HC4060", "74HC4520"}

MIX_CASES = (
    (
        "M000_TIMING_CHAIN_NE555_7490_4017_4020",
        ("NE555", "7490", "4017", "4020"),
        "NE555 output drives 7490, then 7490/4017/4020 cascade-style bider nets.",
    ),
    (
        "M001_SYNC_COUNTER_CHAIN_160_161_163_192",
        ("74HC160", "74HC161", "74HC163", "74HC192"),
        "Synchronous counter chain using output-to-clock/load bider nets.",
    ),
    (
        "M002_UPDOWN_AND_DECODER_193_47_283_85",
        ("74HC193", "74HC47", "74HC283", "74HC85"),
        "Up/down counter, display-driver, adder, and comparator coexistence with shared bider nets.",
    ),
    (
        "M003_SHIFT_AND_REGISTER_595_165_74_273",
        ("74HC595", "74HC165", "74HC74", "74HC273"),
        "Shift-register and flip-flop/register mix with shared serial/control bider nets.",
    ),
)


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _safe(text: str, limit: int = 96) -> str:
    out = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip()).strip("._")
    return out[:limit] or "case"


def refs_in(data: bytes) -> list[str]:
    return sorted(
        set(match.group().decode("ascii") for match in re.finditer(rb"U\d+(?::[A-Z])?", data)),
        key=lambda item: (int(item[1:].split(":")[0]), item),
    )


def package_refs_in(data: bytes) -> list[str]:
    refs: list[str] = []
    for ref in refs_in(data):
        pkg = package_ref(ref)
        if pkg not in refs:
            refs.append(pkg)
    return refs


def donor_for_part(registry: NativeRegistry, part: str) -> Path:
    component = registry.components[part]
    donor = component.donors.get("single")
    if donor is None:
        raise ValueError(f"{part} has no single donor")
    return donor


def cdb_package_refs(path: Path) -> list[str]:
    return pairwise.split_cdb_generic(read_internal_file(path, "ROOT.CDB")).pin_package_refs()


def ref_map_for_slot(existing_refs: set[str], incoming_refs: list[str], slot: int) -> dict[str, str]:
    """Map incoming U refs to same-length free refs, preferring U{slot}."""

    mapping: dict[str, str] = {}
    for old_ref in incoming_refs:
        pkg = package_ref(old_ref)
        if pkg in mapping:
            continue
        preferred = f"U{slot}"
        candidates = [preferred] + [f"U{index}" for index in range(1, 10)]
        for candidate in candidates:
            if len(candidate) == len(pkg) and candidate not in existing_refs and candidate not in mapping.values():
                mapping[pkg] = candidate
                existing_refs.add(candidate)
                break
        else:
            raise ValueError(f"Could not remap {pkg!r} into a same-length free U ref")
    return mapping


def patch_refs(data: bytes, ref_map: dict[str, str]) -> bytes:
    if not ref_map:
        return data

    def repl(match: re.Match[bytes]) -> bytes:
        old = match.group().decode("ascii")
        pkg = package_ref(old)
        mapped_pkg = ref_map.get(pkg, pkg)
        return (mapped_pkg + old[len(pkg) :]).encode("ascii")

    return re.sub(rb"U\d+(?::[A-Z])?", repl, data)


def parsed_cdb_after_ref_map(path: Path, ref_map: dict[str, str]):
    cdb = patch_refs(read_internal_file(path, "ROOT.CDB"), ref_map)
    return pairwise.split_cdb_generic(cdb)


def _u32_at(row: bytes, offset: int) -> int | None:
    if len(row) < offset + 4:
        return None
    return int.from_bytes(row[offset : offset + 4], "little")


def _patch_u32(row: bytes, offset: int, value: int) -> bytes:
    if len(row) < offset + 4:
        return row
    out = bytearray(row)
    out[offset : offset + 4] = value.to_bytes(4, "little")
    return bytes(out)


def _duplicates(values: list[int]) -> list[int]:
    seen: set[int] = set()
    dupes: set[int] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def renumber_duplicate_cdb_ids(pin_rows, property_rows):
    pin_primary = [_u32_at(row, 0) for _ref, row in pin_rows]
    pin_secondary = [_u32_at(row, 12) for _ref, row in pin_rows if len(row) >= 16]
    property_ids = [_u32_at(row, 0) for _ref, row, _original_is_last in property_rows]
    before = {
        "pin_primary_ids": [item for item in pin_primary if item is not None],
        "pin_secondary_ids": [item for item in pin_secondary if item is not None],
        "property_ids": [item for item in property_ids if item is not None],
    }
    duplicate_summary = {
        "pin_primary": _duplicates(before["pin_primary_ids"]),
        "pin_secondary": _duplicates(before["pin_secondary_ids"]),
        "property": _duplicates(before["property_ids"]),
    }
    needs_renumber = any(duplicate_summary.values())
    if not needs_renumber:
        return pin_rows, property_rows, {
            "mode": "preserved_unique_cdb_ids",
            "before": before,
            "after": before,
            "duplicates_before": duplicate_summary,
            "row_plan": [],
        }

    new_pin_rows = []
    package_ids: dict[str, int] = {}
    row_plan: list[dict[str, object]] = []
    for new_id, (ref, row) in enumerate(pin_rows, start=1):
        old_primary = _u32_at(row, 0)
        old_secondary = _u32_at(row, 12) if len(row) >= 16 else None
        new_row = _patch_u32(row, 0, new_id)
        if len(new_row) >= 16:
            new_row = _patch_u32(new_row, 12, new_id)
        new_pin_rows.append((ref, new_row))
        package_ids.setdefault(package_ref(ref), new_id)
        row_plan.append(
            {
                "row_type": "pin",
                "ref": ref,
                "old_primary_id": old_primary,
                "old_secondary_id": old_secondary,
                "new_id": new_id,
                "changed": old_primary != new_id or (old_secondary is not None and old_secondary != new_id),
            }
        )

    new_property_rows = []
    used_property_ids: set[int] = set()
    next_property_id = 1
    for ref, row, original_is_last in property_rows:
        old_id = _u32_at(row, 0)
        new_id = package_ids.get(package_ref(ref))
        if new_id is None or new_id in used_property_ids:
            while next_property_id in used_property_ids:
                next_property_id += 1
            new_id = next_property_id
        used_property_ids.add(new_id)
        new_property_rows.append((ref, _patch_u32(row, 0, new_id), original_is_last))
        row_plan.append(
            {
                "row_type": "property",
                "ref": ref,
                "old_id": old_id,
                "new_id": new_id,
                "changed": old_id != new_id,
            }
        )

    after = {
        "pin_primary_ids": [_u32_at(row, 0) for _ref, row in new_pin_rows],
        "pin_secondary_ids": [_u32_at(row, 12) for _ref, row in new_pin_rows if len(row) >= 16],
        "property_ids": [_u32_at(row, 0) for _ref, row, _original_is_last in new_property_rows],
    }
    return new_pin_rows, new_property_rows, {
        "mode": "renumbered_duplicate_cdb_ids",
        "before": before,
        "after": after,
        "duplicates_before": duplicate_summary,
        "row_plan": row_plan,
    }


def build_cdb_many(parts) -> tuple[bytes, dict[str, object]]:
    parsed = [part["cdb"] for part in parts]
    template = parsed[0]
    pin_rows = []
    property_rows = []
    for item in parsed:
        pin_rows.extend(item.pin_rows)
        property_rows.extend(item.property_rows)
    pin_rows, property_rows, id_plan = renumber_duplicate_cdb_ids(pin_rows, property_rows)

    prefix = bytearray(template.prefix)
    prefix.extend(len(pin_rows).to_bytes(4, "little"))
    property_payloads: list[bytes] = []
    for index, (_ref, row, original_is_last) in enumerate(property_rows):
        if original_is_last and index != len(property_rows) - 1:
            if len(row) < 4:
                raise ValueError("Cannot trim donor-final CDB property row shorter than 4 bytes.")
            property_payloads.append(row[:-4])
        else:
            property_payloads.append(row)
    cdb = bytes(prefix) + b"".join(row for _ref, row in pin_rows) + template.between_sections + b"".join(property_payloads) + template.suffix
    return cdb, {
        "pin_refs": [ref for ref, _row in pin_rows],
        "property_refs": [ref for ref, _row, _original_is_last in property_rows],
        "count": len(pin_rows),
        "cdb_id_plan": id_plan,
    }


def classify_event(event) -> str:
    parsed = parse_pin_label(event.label)
    signal = (parsed["signal"] or "").upper()
    if event.angle_tenths == 0 and (
        signal.startswith("Q")
        or signal in {"CO", "RCO", "TCU", "TCD", "SO", "S0", "S1", "S2", "S3", "C4"}
        or signal.startswith("S")
    ):
        return "output"
    if event.angle_tenths == 0 and parsed["pin"] == "6":
        return "output"
    if event.angle_tenths == 1800:
        return "input"
    return "other"


def first_index(events, role: str) -> int:
    for event in events:
        if classify_event(event) == role:
            return event.index
    for event in events:
        if role == "output" and event.angle_tenths == 0:
            return event.index
        if role == "input" and event.angle_tenths == 1800:
            return event.index
    return events[0].index


def label_for_terminal(ref: str, part: str, event, serial: int) -> str:
    parsed = parse_pin_label(event.label)
    pin = parsed["pin"] or f"{serial:02d}"
    ref_suffix = re.sub(r"[^0-9]", "", ref) or "X"
    return f"R{ref_suffix}P{pin}T{serial:02d}"


def net_labels_for_chunk(ref: str, part: str, shared: dict[int, str]) -> tuple[dict[int, str], list[dict[str, object]]]:
    events = shared.pop("__events__")  # type: ignore[arg-type]
    replacements: dict[int, str] = {}
    plan: list[dict[str, object]] = []
    used: set[str] = set()
    for serial, event in enumerate(events):
        if event.index in shared:
            label = shared[event.index]
            source = "shared_same_name_net"
        else:
            label = label_for_terminal(ref, part, event, serial)
            source = "generated_pin_terminal"
        while label in used:
            label = f"{label}_{serial}"
        used.add(label)
        replacements[event.index] = label
        parsed = parse_pin_label(event.label)
        plan.append(
            {
                "ref": ref,
                "part": part,
                "terminal_index": event.index,
                "old_label": event.label,
                "new_label": label,
                "signal": parsed["signal"],
                "pin": parsed["pin"],
                "role": classify_event(event),
                "source": source,
            }
        )
    return replacements, plan


def component_packet(registry: NativeRegistry, part: str, slot: int, shared_by_index: dict[int, str], dx: int, dy: int, used_refs: set[str]):
    donor = donor_for_part(registry, part)
    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_chunk = _extract_object_chunk(donor_dsn)
    donor_events = bidir_events(donor_chunk)
    if not donor_events:
        raise ValueError(f"{part} donor has no $TERBIDIR anchors")
    incoming_refs = cdb_package_refs(donor)
    ref_map = ref_map_for_slot(used_refs, incoming_refs, slot)
    ref = next(iter(ref_map.values()), f"U{slot}")

    chunk = patch_refs(donor_chunk, ref_map)
    replacements, terminal_plan = net_labels_for_chunk(ref, part, {"__events__": donor_events, **shared_by_index})
    chunk, mutations = patch_bidir_labels(chunk, replacements)
    if dx or dy:
        chunk, translate_plan = pairwise.translate_chunk(chunk, dx, dy)
    else:
        translate_plan = {"dx": 0, "dy": 0, "coordinate_pair_count": 0}
    cdb = parsed_cdb_after_ref_map(donor, ref_map)
    return {
        "part": part,
        "ref": ref,
        "donor": donor,
        "donor_dsn": donor_dsn,
        "chunk": chunk,
        "cdb": cdb,
        "ref_map": ref_map,
        "terminal_plan": terminal_plan,
        "mutations": mutations,
        "translate_plan": translate_plan,
        "marker": registry.components[part].marker,
        "device_section": device_section(donor_dsn),
    }


def shared_net_plan(registry: NativeRegistry, parts: tuple[str, ...], case_index: int) -> list[dict[int, str]]:
    plans: list[dict[int, str]] = []
    for index, part in enumerate(parts):
        donor = donor_for_part(registry, part)
        events = bidir_events(_extract_object_chunk(read_internal_file(donor, "ROOT.DSN")))
        plan: dict[int, str] = {}
        if index < len(parts) - 1:
            plan[first_index(events, "output")] = f"N{case_index:03d}_{index}"
        if index > 0:
            plan[first_index(events, "input")] = f"N{case_index:03d}_{index - 1}"
        plans.append(plan)
    return plans


def build_case(case_id: str, parts: tuple[str, ...], description: str, phase: str, case_index: int) -> dict[str, object]:
    registry = NativeRegistry.load()
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    used_refs: set[str] = set()
    shared_plans = shared_net_plan(registry, parts, case_index)
    packets = []
    x_step = 7_620_000
    y_step = 4_064_000
    for index, (part, shared) in enumerate(zip(parts, shared_plans, strict=True)):
        dx = index * x_step
        dy = (index // 4) * -y_step
        packets.append(component_packet(registry, part, index + 1, shared, dx, dy, used_refs))

    object_chunk = b"\x00" + b"".join(packet["chunk"][1:-1] for packet in packets) + b"\xff"
    cdb, cdb_plan = build_cdb_many(packets)

    sections: list[dict[str, object]] = []
    seen_sections: set[str] = set()
    for packet in packets:
        section = bytearray(packet["device_section"])
        digest = _sha256_bytes(section)
        if digest in seen_sections:
            continue
        seen_sections.add(digest)
        sections.append(
            {
                "donor_key": packet["part"],
                "donor": str(packet["donor"].relative_to(REPO)),
                "section": section,
                "old_tail_pointer": int.from_bytes(section[-4:], "little") if len(section) >= 4 else None,
                "size": len(section),
            }
        )

    base = FixtureRegistry.load().get("e001_empty")
    dsn, pointers = cdb_v2.build_dsn_with_multi_device_sections(
        read_internal_file(base.path, "ROOT.DSN"),
        packets[0]["donor_dsn"],
        object_chunk,
        sections,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    issues = static_issues(output, packets, parts)
    manifest = {
        "case_id": case_id,
        "description": description,
        "phase": phase,
        "method": "native_single_donor_packets_with_bider_same_name_net_chain",
        "status": "temporary_pending_user_proteus_testing",
        "excluded_policy": "74HC4060 and 74HC4520 are excluded from this pack after Q010 onward user rejection.",
        "parts": parts,
        "shared_same_name_nets": sorted({entry["new_label"] for packet in packets for entry in packet["terminal_plan"] if entry["source"] == "shared_same_name_net"}),
        "packets": [
            {
                "part": packet["part"],
                "ref": packet["ref"],
                "donor": str(packet["donor"].relative_to(REPO)),
                "marker": packet["marker"],
                "ref_map": packet["ref_map"],
                "terminal_plan": packet["terminal_plan"],
                "mutations": packet["mutations"],
                "translate_plan": packet["translate_plan"],
            }
            for packet in packets
        ],
        "cdb_plan": cdb_plan,
        "section_pointers": pointers,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": marker_counts(chunk, [registry.components[part].marker for part in parts]),
        "cdb_marker_counts": marker_counts(cdb, [registry.components[part].marker for part in parts]),
        "terminal_counts": {
            "$TERBIDIR": chunk.count(b"$TERBIDIR"),
            "$TERINPUT": chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": chunk.count(b"$TEROUTPUT"),
            "WIRE": chunk.count(b"WIRE"),
        },
        "object_refs": refs_in(chunk),
        "cdb_refs": refs_in(cdb),
        "static_validation_issues": issues,
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(
        json.dumps([event.as_dict() | parse_pin_label(event.label) for event in bidir_events(chunk)], indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def static_issues(output: Path, packets: list[dict[str, object]], parts: tuple[str, ...]) -> list[str]:
    issues: list[str] = []
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
        return issues
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(b"$TERINPUT") or chunk.count(b"$TEROUTPUT"):
        issues.append("native bider pair pack should not emit ordinary input/output terminals")
    if chunk.count(b"$TERBIDIR") == 0:
        issues.append("no bidirectional terminals emitted")
    object_packages = set(package_refs_in(chunk))
    cdb_packages = set(package_refs_in(cdb))
    missing = sorted(object_packages - cdb_packages, key=lambda item: int(item[1:]))
    if missing:
        issues.append(f"object refs missing CDB rows: {missing}")
    if len(object_packages) != len(packets):
        issues.append(f"expected {len(packets)} object package refs, found {sorted(object_packages)}")
    if len(cdb_packages) != len(packets):
        issues.append(f"expected {len(packets)} CDB package refs, found {sorted(cdb_packages)}")
    try:
        parsed = pairwise.split_cdb_generic(cdb)
        pin_primary = [_u32_at(row, 0) for _ref, row in parsed.pin_rows if _u32_at(row, 0) is not None]
        pin_secondary = [_u32_at(row, 12) for _ref, row in parsed.pin_rows if _u32_at(row, 12) is not None]
        property_ids = [_u32_at(row, 0) for _ref, row, _original_is_last in parsed.property_rows if _u32_at(row, 0) is not None]
        for label, values in (
            ("CDB pin primary IDs", pin_primary),
            ("CDB pin secondary IDs", pin_secondary),
            ("CDB property IDs", property_ids),
        ):
            duplicate_values = _duplicates(values)
            if duplicate_values:
                issues.append(f"duplicate {label}: {duplicate_values}")
    except Exception as exc:  # noqa: BLE001 - static validation should report parse failures without hiding other checks.
        issues.append(f"CDB duplicate-id validation failed: {exc}")
    for packet in packets:
        marker = str(packet["marker"]).encode("ascii")
        if marker not in chunk and marker not in cdb:
            issues.append(f"marker {packet['marker']} for {packet['part']} is missing")
    for packet in packets:
        for entry in packet["terminal_plan"]:
            label = str(entry["new_label"]).encode("ascii")
            if label not in chunk:
                issues.append(f"label {entry['new_label']} missing after mutation")
    shared_counts = {}
    for packet in packets:
        for entry in packet["terminal_plan"]:
            if entry["source"] == "shared_same_name_net":
                label = str(entry["new_label"])
                shared_counts[label] = shared_counts.get(label, 0) + 1
    for label, count in shared_counts.items():
        if count != 2:
            issues.append(f"shared net {label} appears in terminal plan {count} times, expected 2")
    return issues


def case_specs() -> list[tuple[str, tuple[str, ...], str, str]]:
    registry = NativeRegistry.load()
    manual_pairs = set(registry.pair_donors)
    specs: list[tuple[str, tuple[str, ...], str, str]] = []
    pair_index = 0
    for left, right in combinations(CORE_PARTS, 2):
        if left in EXCLUDED_MODEL_FOLLOWUP or right in EXCLUDED_MODEL_FOLLOWUP:
            continue
        phase = "manual_pair_rebuilt_with_bider" if tuple(sorted((left, right))) in manual_pairs else "missing_pair_generated_with_bider"
        case_id = f"P{pair_index:03d}_{_safe(left, 24)}_{_safe(right, 24)}_BIDER_CHAIN"
        description = f"{left} and {right} generated from terminal-bearing solo native donors with one same-name bider connection."
        specs.append((case_id, (left, right), description, phase))
        pair_index += 1
    for mix_index, (case_id, parts, description) in enumerate(MIX_CASES):
        specs.append((case_id, parts, description, "four_component_bider_mix"))
    return specs


def write_archive() -> str:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
            info.date_time = (2026, 6, 12, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            zf.writestr(info, file_path.read_bytes())
    return str(ARCHIVE)


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests: list[dict[str, object]] = []
    blocks: list[dict[str, object]] = []
    for index, (case_id, parts, description, phase) in enumerate(case_specs()):
        try:
            manifests.append(build_case(case_id, parts, description, phase, index))
        except Exception as exc:  # noqa: BLE001 - every blocked case is written into the temporary summary.
            blocks.append({"case_id": case_id, "parts": parts, "phase": phase, "error": repr(exc)})

    static_issue_cases = {
        str(item["case_id"]): item.get("static_validation_issues", [])
        for item in manifests
        if item.get("static_validation_issues")
    }
    phase_counts: dict[str, int] = {}
    for item in manifests:
        phase = str(item["phase"])
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
    archive = write_archive()
    summary = {
        "pack": "IC_NATIVE_BIDER_PAIRS_V2_CDB_IDFIX_TEMP_2026_06_12",
        "case_count": len(manifests) + len(blocks),
        "generated_case_count": len(manifests),
        "blocked_cases": blocks,
        "phase_counts": phase_counts,
        "excluded_model_followup_parts": sorted(EXCLUDED_MODEL_FOLLOWUP),
        "static_issue_cases": static_issue_cases,
        "archive": archive,
        "archive_sha256": _sha256_bytes(ARCHIVE.read_bytes()),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not blocks and not static_issue_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
