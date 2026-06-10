"""Generate pairwise IC-mixing diagnostics from the exact-rezip source set.

This is intentionally a temporary diagnostic generator. It builds every
unordered pair from the 34 IC-only source cases selected after user feedback:

- old T018 74HC4060 is excluded because user testing rejected it;
- old T020 74HC4520 is excluded because user testing rejected it;
- T037 74HC4060+RLC is excluded from this IC-only pair matrix;
- refreshed 74HC4520 T038-T041 are kept out until exact-rezip testing passes.

The emitted projects use conservative edits only:

- complete donor object chunks are kept;
- the second donor's U refs are remapped to unused U refs of identical length;
- only same-length terminal label edits are made on the second donor;
- the second donor is translated to the right by known terminal/wire/body
  coordinate fields;
- ROOT.CDB is rebuilt from parsed donor rows with the same-length ref map;
- full donor device sections are preserved and tail pointers are patched.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import package_ref


REPO = Path(__file__).resolve().parents[3]
EXACT_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-10" / "generate_ic_exact_rezip_all_families_temp.py"
CDB_V2_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_v2_metadata_temp.py"
OUT_ROOT = REPO / "experiments" / "ic_pairwise_34_v1_temp_2026_06_10"
ARCHIVE_PATH = REPO / "experiments" / "IC_PAIRWISE_34_V1_TEMP_2026_06_10.zip"

PAIRWISE_SOURCE_EXCLUDED = {
    "T018_74HC4060_REPO_SINGLE_EXACT_REZIP",
    "T020_74HC4520_EXACT_REZIP",
    "T037_74HC4060_REFRESH_4X_RLC_EXACT_REZIP",
    "T038_74HC4520_REFRESH_SINGLE_EXACT_REZIP",
    "T039_74HC4520_REFRESH_2X_EXACT_REZIP",
    "T040_74HC4520_REFRESH_4X_EXACT_REZIP",
    "T041_74HC4520_REFRESH_4X_RLC_EXACT_REZIP",
}

EXPECTED_SOURCE_COUNT = 34
SECOND_DONOR_DX = 7_620_000
SECOND_DONOR_DY = 0
COUNT_OFFSET = 92
PIN_ROW_HEADER_SIZE = 16
PIN_ROW_FOOTER_SIZE = 12
PROPERTY_ROW_HEADER_SIZE = 20

COMPONENT_MARKERS = (
    "74HC00",
    "74HC02",
    "74HC04",
    "74HC08",
    "74HC32",
    "74HC86",
    "74HC266",
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
    "74HC4060",
    "4518",
    "74HC74",
    "74HC76",
    "74HC174",
    "74HC273",
    "4027",
    "74HC85",
    "74HC283",
    "74HC157",
    "7447",
    "74HC165",
    "74HC595",
    "NE555",
    "LM741",
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


exact = _load_module("ic_exact_rezip_for_pairwise_34", EXACT_SCRIPT)
cdb_v2 = _load_module("mixed_ic_cdb_v2_for_pairwise_34", CDB_V2_SCRIPT)
seq = exact.seq


@dataclass(frozen=True)
class PairSource:
    source_index: int
    case_id: str
    family: str
    donor: Path
    proteus_marker: str
    notes: str

    @property
    def short_id(self) -> str:
        return f"S{self.source_index:02d}"

    def as_dict(self) -> dict[str, object]:
        return {
            "source_index": self.source_index,
            "short_id": self.short_id,
            "case_id": self.case_id,
            "family": self.family,
            "donor": str(self.donor.relative_to(REPO)),
            "proteus_marker": self.proteus_marker,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class PairCase:
    case_id: str
    left: PairSource
    right: PairSource


@dataclass(frozen=True)
class GenericCdb:
    prefix: bytes
    pin_rows: tuple[tuple[str, bytes], ...]
    between_sections: bytes
    property_rows: tuple[tuple[str, bytes], ...]
    suffix: bytes = b""

    @property
    def count(self) -> int:
        return len(self.pin_rows)

    def pin_package_refs(self) -> list[str]:
        refs: list[str] = []
        for ref, _row in self.pin_rows:
            pkg = package_ref(ref)
            if pkg not in refs:
                refs.append(pkg)
        return refs

    def property_package_refs(self) -> list[str]:
        refs: list[str] = []
        for ref, _row in self.property_rows:
            pkg = package_ref(ref)
            if pkg not in refs:
                refs.append(pkg)
        return refs


def _read_u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise ValueError("Unexpected end of CDB while reading u32.")
    return int.from_bytes(data[offset : offset + 4], "little")


def _read_lp_ascii(data: bytes, offset: int) -> tuple[str, int]:
    if offset >= len(data):
        raise ValueError("Unexpected end of CDB while reading string length.")
    length = data[offset]
    start = offset + 1
    end = start + length
    if end > len(data):
        raise ValueError("Unexpected end of CDB while reading string body.")
    return data[start:end].decode("ascii", errors="replace"), end


def _skip_lp_ascii(data: bytes, offset: int) -> int:
    _value, end = _read_lp_ascii(data, offset)
    return end


def split_cdb_generic(data: bytes) -> GenericCdb:
    """Split CDB rows while allowing subpart pin rows and package property rows."""

    if len(data) < COUNT_OFFSET + 4:
        raise ValueError("ROOT.CDB is too short.")
    count = _read_u32(data, COUNT_OFFSET)
    pos = COUNT_OFFSET + 4
    pin_rows: list[tuple[str, bytes]] = []
    for _index in range(count):
        row_start = pos
        pos += PIN_ROW_HEADER_SIZE
        ref, pos = _read_lp_ascii(data, pos)
        pin_count = _read_u32(data, pos)
        pos += 4
        for _pin_index in range(pin_count):
            pos = _skip_lp_ascii(data, pos)
            pos = _skip_lp_ascii(data, pos)
        pos += PIN_ROW_FOOTER_SIZE
        if pos > len(data):
            raise ValueError("Unexpected end of CDB while reading pin row.")
        pin_rows.append((ref, data[row_start:pos]))

    pin_end = pos
    property_starts: list[tuple[int, str]] = []
    for match in re.finditer(rb"U\d+(?::[A-Z])?", data[pin_end:]):
        ref_start = pin_end + match.start()
        length_pos = ref_start - 1
        row_start = length_pos - PROPERTY_ROW_HEADER_SIZE
        raw = match.group()
        if row_start >= pin_end and data[length_pos] == len(raw):
            property_starts.append((row_start, raw.decode("ascii")))

    unique_starts: list[tuple[int, str]] = []
    seen_offsets: set[int] = set()
    for row_start, ref in sorted(property_starts):
        if row_start not in seen_offsets:
            seen_offsets.add(row_start)
            unique_starts.append((row_start, ref))
    if not unique_starts:
        raise ValueError("Could not locate CDB property row.")

    between = data[pin_end : unique_starts[0][0]]
    property_rows: list[tuple[str, bytes]] = []
    for index, (row_start, ref) in enumerate(unique_starts):
        row_end = unique_starts[index + 1][0] if index + 1 < len(unique_starts) else len(data)
        property_rows.append((ref, data[row_start:row_end]))

    return GenericCdb(
        prefix=data[:COUNT_OFFSET],
        pin_rows=tuple(pin_rows),
        between_sections=between,
        property_rows=tuple(property_rows),
    )


def build_cdb_from_generic_rows(template: GenericCdb, left: GenericCdb, right: GenericCdb) -> bytes:
    pin_rows = list(left.pin_rows) + list(right.pin_rows)
    property_rows = list(left.property_rows) + list(right.property_rows)
    prefix = bytearray(template.prefix)
    prefix.extend(len(pin_rows).to_bytes(4, "little"))
    return (
        bytes(prefix)
        + b"".join(row for _ref, row in pin_rows)
        + template.between_sections
        + b"".join(row for _ref, row in property_rows)
        + template.suffix
    )


def pair_sources() -> tuple[PairSource, ...]:
    selected = [
        item
        for item in exact.CASES
        if item.case_id not in PAIRWISE_SOURCE_EXCLUDED
    ]
    if len(selected) != EXPECTED_SOURCE_COUNT:
        raise RuntimeError(
            f"Pairwise source set should contain {EXPECTED_SOURCE_COUNT} cases, got {len(selected)}"
        )
    return tuple(
        PairSource(
            source_index=index + 1,
            case_id=item.case_id,
            family=item.family,
            donor=item.donor,
            proteus_marker=item.proteus_marker,
            notes=item.notes,
        )
        for index, item in enumerate(selected)
    )


SOURCES = pair_sources()
CASES = tuple(
    PairCase(
        case_id=f"P{index:03d}_{left.short_id}_{right.short_id}",
        left=left,
        right=right,
    )
    for index, (left, right) in enumerate(combinations(SOURCES, 2), start=1)
)


def _s32(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _put_s32(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = int(value).to_bytes(4, "little", signed=True)


def _add_s32(data: bytearray, offset: int, delta: int) -> None:
    _put_s32(data, offset, _s32(data, offset) + delta)


def refs_in(data: bytes) -> list[str]:
    return sorted(
        set(match.group().decode("ascii") for match in re.finditer(rb"U\d+", data)),
        key=lambda item: int(item[1:]),
    )


def cdb_package_refs(path: Path) -> list[str]:
    return split_cdb_generic(seq.read_internal_file(path, "ROOT.CDB")).pin_package_refs()


def same_length_ref_map(existing_refs: list[str], incoming_refs: list[str]) -> dict[str, str]:
    used = set(existing_refs)
    mapping: dict[str, str] = {}
    for old_ref in incoming_refs:
        if old_ref not in used and old_ref not in mapping:
            mapping[old_ref] = old_ref
            used.add(old_ref)
            continue
        if len(old_ref) != 2:
            raise ValueError(f"Cannot same-length remap non-single-digit ref {old_ref!r}")
        for candidate_index in range(1, 10):
            candidate = f"U{candidate_index}"
            if candidate not in used and candidate not in mapping.values():
                mapping[old_ref] = candidate
                used.add(candidate)
                break
        else:
            raise ValueError(f"Could not find same-length free U ref for {old_ref!r}")
    return mapping


def patch_refs(data: bytes, ref_map: dict[str, str]) -> bytes:
    if not ref_map:
        return data

    def repl(match: re.Match[bytes]) -> bytes:
        old = match.group().decode("ascii")
        return ref_map.get(old, old).encode("ascii")

    return re.sub(rb"U\d+", repl, data)


def _label_for(length: int, index: int) -> str:
    if length == 1:
        alphabet = "NOPQRSTUVWXYZABCDEFGHIJKLM"
        return alphabet[index % len(alphabet)]
    if length == 2:
        return f"{chr(ord('N') + (index // 10) % 13)}{index % 10}"
    prefix = chr(ord("N") + (index // (10 ** (length - 1))) % 13)
    digits = f"{index % (10 ** (length - 1)):0{length - 1}d}"
    return (prefix + digits)[:length]


def patch_second_terminal_labels(chunk: bytes) -> tuple[bytes, list[dict[str, object]]]:
    out = bytearray(chunk)
    label_maps: dict[int, dict[str, str]] = {}
    events: list[dict[str, object]] = []
    serial_by_length: dict[int, int] = {}
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True), (b"$TERBIDIR", False)):
        pos = 0
        while True:
            marker_pos = bytes(out).find(marker, pos)
            if marker_pos < 0:
                break
            length_pos = marker_pos + (17 if output_terminal else 16)
            label_pos = marker_pos + (18 if output_terminal else 17)
            length = out[length_pos]
            old = bytes(out[label_pos : label_pos + length]).decode("ascii", errors="replace")
            if old:
                per_length = label_maps.setdefault(length, {})
                if old not in per_length:
                    serial = serial_by_length.get(length, 0)
                    per_length[old] = _label_for(length, serial)
                    serial_by_length[length] = serial + 1
                new = per_length[old]
                raw = new.encode("ascii")
                if len(raw) != length:
                    raise ValueError(f"Terminal label remap changed length: {old!r}->{new!r}")
                out[label_pos : label_pos + length] = raw
                events.append(
                    {
                        "terminal_marker": marker.decode("ascii"),
                        "offset": marker_pos,
                        "old": old,
                        "new": new,
                    }
                )
            pos = marker_pos + 1
    return bytes(out), events


def _coord_pairs_for_terminal_records(chunk: bytes) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True), (b"$TERBIDIR", False)):
        pos = 0
        while True:
            marker_pos = chunk.find(marker, pos)
            if marker_pos < 0:
                break
            start = marker_pos - 14
            if start >= 0:
                pairs.append((start + 1, start + 5))
                length_pos = marker_pos + (17 if output_terminal else 16)
                label_pos = marker_pos + (18 if output_terminal else 17)
                if length_pos < len(chunk):
                    label_length = chunk[length_pos]
                    label_coord = label_pos + label_length
                    if label_coord + 8 <= len(chunk):
                        pairs.append((label_coord, label_coord + 4))
            pos = marker_pos + 1
    return pairs


def _coord_pairs_for_wires(chunk: bytes) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    pos = 0
    while True:
        marker = chunk.find(b"WIRE", pos)
        if marker < 0:
            return pairs
        coord = marker + 9
        if coord + 16 <= len(chunk):
            pairs.append((coord, coord + 4))
            pairs.append((coord + 8, coord + 12))
        pos = marker + 1


def _coord_pairs_for_bodies(chunk: bytes) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for marker in COMPONENT_MARKERS:
        raw_marker = marker.encode("ascii")
        needle = bytes([len(raw_marker)]) + raw_marker
        pos = 0
        while True:
            found = chunk.find(needle, pos)
            if found < 0:
                break
            if found >= 2 and chunk[found - 1] == 0 and chunk[found - 2] != 0xFF:
                x_offset = found + len(needle)
                y_offset = x_offset + 4
                if y_offset + 4 <= len(chunk):
                    pairs.append((x_offset, y_offset))
            pos = found + 1
    return pairs


def translate_chunk(chunk: bytes, dx: int, dy: int) -> tuple[bytes, dict[str, object]]:
    out = bytearray(chunk)
    pairs = _coord_pairs_for_terminal_records(chunk) + _coord_pairs_for_wires(chunk) + _coord_pairs_for_bodies(chunk)
    seen: set[tuple[int, int]] = set()
    unique_pairs = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            unique_pairs.append(pair)
    for x_offset, y_offset in unique_pairs:
        _add_s32(out, x_offset, dx)
        _add_s32(out, y_offset, dy)
    return bytes(out), {"dx": dx, "dy": dy, "coordinate_pair_count": len(unique_pairs)}


def payload(chunk: bytes) -> bytes:
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        raise ValueError("Object chunk boundary is not 00...FF")
    return chunk[1:-1]


def device_sections_for(left: PairSource, right: PairSource) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    seen_hashes: set[str] = set()
    for item in (left, right):
        dsn = seq.read_internal_file(item.donor, "ROOT.DSN")
        section = bytearray(seq._device_section(dsn))
        section_hash = seq._sha256_bytes(section)
        if section_hash in seen_hashes:
            continue
        seen_hashes.add(section_hash)
        sections.append(
            {
                "donor_key": item.case_id,
                "donor": str(item.donor.relative_to(REPO)),
                "section": section,
                "old_tail_pointer": int.from_bytes(section[-4:], "little") if len(section) >= 4 else None,
                "size": len(section),
            }
        )
    return sections


def cdb_for_pair(left: PairSource, right: PairSource, ref_map: dict[str, str]) -> tuple[bytes, dict[str, object]]:
    left_parsed = split_cdb_generic(seq.read_internal_file(left.donor, "ROOT.CDB"))
    right_parsed = split_cdb_generic(patch_refs(seq.read_internal_file(right.donor, "ROOT.CDB"), ref_map))
    cdb = build_cdb_from_generic_rows(left_parsed, left_parsed, right_parsed)
    return cdb, {
        "left_pin_refs": [ref for ref, _row in left_parsed.pin_rows],
        "right_pin_refs_after_map": [ref for ref, _row in right_parsed.pin_rows],
        "left_property_refs": [ref for ref, _row in left_parsed.property_rows],
        "right_property_refs_after_map": [ref for ref, _row in right_parsed.property_rows],
        "combined_pin_refs": [ref for ref, _row in left_parsed.pin_rows + right_parsed.pin_rows],
        "combined_property_refs": [ref for ref, _row in left_parsed.property_rows + right_parsed.property_rows],
        "combined_count": left_parsed.count + right_parsed.count,
    }


def static_issues(output: Path, left: PairSource, right: PairSource, ref_map: dict[str, str]) -> list[str]:
    issues: list[str] = []
    info = seq.inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    for marker in (left.proteus_marker, right.proteus_marker):
        raw = marker.encode("ascii")
        if raw not in chunk:
            issues.append(f"expected DSN marker {marker} missing")
    object_refs = refs_in(chunk)
    cdb_reference_set = refs_in(cdb)
    if len(object_refs) != len(set(object_refs)):
        issues.append(f"duplicate object refs after remap: {object_refs}")
    if len(cdb_reference_set) != len(set(cdb_reference_set)):
        issues.append(f"duplicate CDB refs after remap: {cdb_reference_set}")
    missing = sorted(set(object_refs) - set(cdb_reference_set), key=lambda item: int(item[1:]))
    if missing:
        issues.append(f"object refs missing from CDB: {missing}")
    for old, new in ref_map.items():
        if len(old) != len(new):
            issues.append(f"ref remap changed byte length: {old}->{new}")
    try:
        parsed = split_cdb_generic(cdb)
        if parsed.count != len(parsed.pin_rows):
            issues.append("CDB parsed count does not match pin rows")
        property_refs = set(parsed.property_package_refs())
        missing_property_refs = sorted(
            set(package_ref(ref) for ref, _row in parsed.pin_rows) - property_refs,
            key=lambda item: int(item[1:]),
        )
        if missing_property_refs:
            issues.append(f"CDB pin package refs missing property rows: {missing_property_refs}")
    except Exception as exc:
        issues.append(f"CDB parse failed: {exc}")
    return issues


def write_case(case: PairCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"

    left_dsn = seq.read_internal_file(case.left.donor, "ROOT.DSN")
    right_dsn = seq.read_internal_file(case.right.donor, "ROOT.DSN")
    left_chunk = seq._extract_object_chunk(left_dsn)
    right_chunk = seq._extract_object_chunk(right_dsn)
    ref_map = same_length_ref_map(cdb_package_refs(case.left.donor), cdb_package_refs(case.right.donor))
    right_chunk = patch_refs(right_chunk, ref_map)
    right_chunk, terminal_label_plan = patch_second_terminal_labels(right_chunk)
    right_chunk, translation_plan = translate_chunk(right_chunk, SECOND_DONOR_DX, SECOND_DONOR_DY)
    object_chunk = b"\x00" + payload(left_chunk) + payload(right_chunk) + b"\xff"
    cdb, cdb_plan = cdb_for_pair(case.left, case.right, ref_map)
    sections = device_sections_for(case.left, case.right)

    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    dsn, pointers = cdb_v2.build_dsn_with_multi_device_sections(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        left_dsn,
        object_chunk,
        sections,
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    device_section = seq._device_section(dsn)
    manifest = {
        "case_id": case.case_id,
        "description": f"Pairwise IC diagnostic: {case.left.family} with {case.right.family}.",
        "method": "pairwise_exact_source_concat_same_length_ref_remap_full_device_sections",
        "status": "temporary_pending_user_proteus_testing",
        "left": case.left.as_dict(),
        "right": case.right.as_dict(),
        "ref_map_right": ref_map,
        "terminal_label_plan_right": terminal_label_plan,
        "translation_plan_right": translation_plan,
        "cdb_plan": cdb_plan,
        "device_section_count": len(sections),
        "device_sections": [
            {
                "donor_key": item["donor_key"],
                "donor": item["donor"],
                "size": item["size"],
                "old_tail_pointer": item["old_tail_pointer"],
            }
            for item in sections
        ],
        "section_pointers": pointers,
        "object_refs": refs_in(chunk),
        "cdb_refs": refs_in(cdb),
        "marker_counts": {
            marker: chunk.count(marker.encode("ascii"))
            for marker in sorted({case.left.proteus_marker, case.right.proteus_marker})
        },
        "cdb_marker_counts": {
            marker: cdb.count(marker.encode("ascii"))
            for marker in sorted({case.left.proteus_marker, case.right.proteus_marker})
        },
        "terminal_counts": {
            "$TERINPUT": chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": chunk.count(b"$TEROUTPUT"),
            "$TERBIDIR": chunk.count(b"$TERBIDIR"),
            "WIRE": chunk.count(b"WIRE"),
        },
        "object_chunk_size": len(chunk),
        "device_section_size": len(device_section),
        "static_validation_issues": static_issues(output, case.left, case.right, ref_map),
        "output_hashes": {
            "project": seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(chunk),
            "device_section": seq._sha256_bytes(device_section),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 10, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifests = [write_case(case) for case in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_PAIRWISE_34_V1_TEMP_2026_06_10",
        "purpose": "Pairwise diagnostics for every unordered combination of the 34 IC-only exact-rezip source cases.",
        "status": "temporary_pending_user_proteus_testing",
        "source_count": len(SOURCES),
        "pair_count": len(CASES),
        "source_exclusions": sorted(PAIRWISE_SOURCE_EXCLUDED),
        "sources": [source.as_dict() for source in SOURCES],
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "archive": str(ARCHIVE_PATH.relative_to(REPO)),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_ROOT),
                "archive": str(ARCHIVE_PATH),
                "archive_sha256": archive_hash,
                "source_count": len(SOURCES),
                "pair_count": len(CASES),
                "static_issue_case_count": len(summary_issues),
                "static_issue_cases_sample": list(summary_issues)[:10],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
