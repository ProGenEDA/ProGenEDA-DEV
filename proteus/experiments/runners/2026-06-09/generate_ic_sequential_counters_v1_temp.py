"""Generate sequential counter/divider IC diagnostics for the first donor batch.

This experiment is intentionally separate from the locked combinational IC
route. Sequential/counter IC pins use donor-native bidirectional terminals for
this phase because user testing showed that this family is safer when visible
pin endpoints all use the same terminal record class.
"""

from __future__ import annotations

import json
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "proteus" / "active" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.bidirectional import BIDIR_MARKER  # noqa: E402
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes, _u32  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_sequential_counters_v1_temp_2026_06_09"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_SEQUENTIAL_COUNTERS_V1_TEMP_2026_06_09.zip"
DONOR_ROOT = REPO / "proteus" / "active" / "evidence" / "donors" / "sequential_counters"

MARKERS = (
    b"7490",
    b"74HC90",
    b"74HC160",
    b"74HC161",
    b"74HC163",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERBIDIR",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"COMPONENT ID",
    b"COMPONENT VALUE",
    b"RESISTOR",
    b"CAPACITOR",
    b"CAP10",
    b"REALIND",
    b"VSOURCE",
    b"CSOURCE",
    b"VSINE",
    b"LOGICSTATE",
    b"LOGICPROBE",
)


@dataclass(frozen=True)
class CounterFamily:
    key: str
    user_name: str
    proteus_device: str
    single: str
    two: str
    four: str
    four_rlc: str
    notes: str = ""

    def donor(self, kind: str) -> Path:
        filename = {
            "single": self.single,
            "two": self.two,
            "four": self.four,
            "four_rlc": self.four_rlc,
        }[kind]
        return DONOR_ROOT / filename


FAMILIES = (
    CounterFamily(
        "7490",
        "74HC90",
        "7490",
        "7490.pdsprj",
        "2_7490.pdsprj",
        "4_7490.pdsprj",
        "4_7490withRLC.pdsprj",
        "User-facing 74HC90 is normalized to the observed Proteus device marker 7490.",
    ),
    CounterFamily(
        "74hc160",
        "74HC160",
        "74HC160",
        "74HC160.pdsprj",
        "2_74HC160.pdsprj",
        "4_74HC160.pdsprj",
        "4_74HC160withRLC.pdsprj",
    ),
    CounterFamily(
        "74hc161",
        "74HC161",
        "74HC161",
        "74HC161.pdsprj",
        "2_74HC161.pdsprj",
        "4_74HC161.pdsprj",
        "4_74HC161withRLC.pdsprj",
    ),
    CounterFamily(
        "74hc163",
        "74HC163",
        "74HC163",
        "74HC163.pdsprj",
        "2_74HC163.pdsprj",
        "4_74HC163.pdsprj",
        "4_74HC163withRLC.pdsprj",
    ),
)


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def _device_section(dsn: bytes) -> bytes:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = dsn.rfind(marker, 0, first)
    if first < 0 or insert < 0:
        raise ValueError("ROOT.DSN does not contain the expected device section.")
    return dsn[insert + len(marker) : first]


def build_dsn_with_device_section(
    base_dsn: bytes,
    donor_dsn: bytes,
    object_chunk: bytes,
    device_section: bytes,
) -> tuple[bytes, dict[str, int]]:
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise ValueError("Base or donor ROOT.DSN does not match the accepted section model.")
    insert += len(marker)
    dev = bytearray(device_section)
    first_header = donor_dsn[donor_first : donor_obj + len(b"OBJECT DATA")]
    tail = bytearray(base_dsn[e0_second:])
    first_isis = insert + len(dev)
    second_isis = first_isis + len(first_header) + len(object_chunk)
    second_obj = second_isis + tail.find(b"OBJECT DATA")
    object_data_pointer = second_obj + 13
    if len(dev) >= 4:
        dev[-4:] = _u32(object_data_pointer)
    cct = tail.find(b"CCT000")
    if cct != -1:
        tail[cct + len(b"CCT000") + 2 : cct + len(b"CCT000") + 6] = _u32(first_isis)
    default = tail.find(b"__DEFAULT__\x00\x00")
    if default != -1:
        tail[default + len(b"__DEFAULT__\x00\x00") : default + len(b"__DEFAULT__\x00\x00") + 4] = _u32(
            second_isis
        )
    dsn = bytes(bytearray(base_dsn[:insert]) + dev + first_header + bytearray(object_chunk) + tail)
    return dsn, {
        "insert": insert,
        "first_isis": first_isis,
        "second_isis": second_isis,
        "second_object_data": second_obj,
        "object_data_pointer": object_data_pointer,
    }


def bidir_events(chunk: bytes) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    position = 0
    while True:
        marker = chunk.find(BIDIR_MARKER, position)
        if marker < 0:
            return events
        start = marker - 14
        if start < 0 or chunk[start] != 0x10:
            raise ValueError(f"Invalid bidirectional terminal start at marker {marker}.")
        label_length = chunk[start + 30]
        size = 101 + label_length
        record = chunk[start : start + size]
        label = record[31 : 31 + label_length].decode("ascii", errors="replace")
        symbol_x, symbol_y = struct.unpack("<ii", record[1:9])
        angle = struct.unpack("<I", record[9:13])[0]
        suffix = struct.unpack("<H", record[-4:-2])[0]
        events.append(
            {
                "start": start,
                "size": size,
                "label": label,
                "symbol_x": symbol_x,
                "symbol_y": symbol_y,
                "angle_tenths": angle,
                "suffix": f"{suffix:04x}",
                "active_link": record[-2],
            }
        )
        position = marker + 1


def rebuild_bidir_record(record: bytes, new_label: str) -> bytes:
    raw = new_label.encode("ascii")
    if not raw or len(raw) > 255:
        raise ValueError(f"Invalid bidirectional terminal label {new_label!r}.")
    old_length = record[30]
    old_label_offset = 31 + old_length
    old_label_coords = record[old_label_offset : old_label_offset + 8]
    rebuilt = bytearray(record[:30] + bytes([len(raw)]) + raw + record[31 + old_length :])
    new_label_offset = 31 + len(raw)
    rebuilt[new_label_offset : new_label_offset + 8] = old_label_coords
    return bytes(rebuilt)


def patch_bidir_labels(
    chunk: bytes,
    replacements_by_index: dict[int, str],
) -> tuple[bytes, list[dict[str, object]]]:
    events = bidir_events(chunk)
    out = bytearray(chunk)
    mutations: list[dict[str, object]] = []
    for index, event in reversed(list(enumerate(events))):
        new_label = replacements_by_index.get(index)
        if new_label is None:
            continue
        start = int(event["start"])
        size = int(event["size"])
        old_record = chunk[start : start + size]
        new_record = rebuild_bidir_record(old_record, new_label)
        out[start : start + size] = new_record
        mutations.append(
            {
                "index": index,
                "old": event["label"],
                "new": new_label,
                "old_size": size,
                "new_size": len(new_record),
            }
        )
    out[-1] = 0xFF
    return bytes(out), sorted(mutations, key=lambda item: int(item["index"]))


PIN_PATTERN = re.compile(r"^(?:(?P<before>.*?)\s*)?PIN\s*(?P<pin>\d+)(?:\s*(?P<after>.*))?$", re.IGNORECASE)


def parse_pin_label(label: str) -> dict[str, str]:
    normalized = " ".join(label.replace("(", "").replace(")", "").split())
    match = PIN_PATTERN.match(normalized)
    if not match:
        return {"signal": normalized, "pin": "", "normalized": normalized}
    before = (match.group("before") or "").strip()
    after = (match.group("after") or "").strip()
    signal = before or after
    return {"signal": signal, "pin": match.group("pin"), "normalized": normalized}


def learned_pin_map(family: CounterFamily) -> dict[str, object]:
    donor = family.donor("single")
    chunk = _extract_object_chunk(read_internal_file(donor, "ROOT.DSN"))
    terminals: list[dict[str, object]] = []
    for index, event in enumerate(bidir_events(chunk)):
        parsed = parse_pin_label(str(event["label"]))
        terminals.append(
            {
                "index": index,
                "label": event["label"],
                "signal": parsed["signal"],
                "pin": parsed["pin"],
                "angle_tenths": event["angle_tenths"],
                "side": "left" if event["angle_tenths"] == 1800 else "right",
                "suffix": event["suffix"],
            }
        )
    return {
        "family": family.user_name,
        "proteus_device": family.proteus_device,
        "notes": family.notes,
        "terminal_policy": "sequential counter visible pins use donor-native $TERBIDIR records",
        "terminals": terminals,
        "pin_aliases": {
            item["pin"]: item["signal"]
            for item in terminals
            if item["pin"] and item["signal"]
        },
        "signal_aliases": {
            str(item["signal"]).upper().replace(" ", ""): item["pin"]
            for item in terminals
            if item["pin"] and item["signal"]
        },
    }


def sequential_labels(family: CounterFamily, donor_kind: str) -> tuple[dict[int, str], list[dict[str, object]]]:
    chunk = _extract_object_chunk(read_internal_file(family.donor(donor_kind), "ROOT.DSN"))
    single_count = len(bidir_events(_extract_object_chunk(read_internal_file(family.donor("single"), "ROOT.DSN"))))
    events = bidir_events(chunk)
    replacements: dict[int, str] = {}
    plan: list[dict[str, object]] = []
    for index, event in enumerate(events):
        chip_index = index // single_count
        pin_index = index % single_count
        parsed = parse_pin_label(str(event["label"]))
        pin = parsed["pin"] or f"X{pin_index:02d}"
        signal = parsed["signal"] or f"P{pin_index:02d}"
        safe_signal = re.sub(r"[^A-Za-z0-9]", "", signal.upper())[:4] or "PIN"
        new = f"U{chip_index + 1}{safe_signal}{pin}"
        replacements[index] = new
        plan.append(
            {
                "terminal_index": index,
                "chip_index": chip_index + 1,
                "old_label": event["label"],
                "new_label": new,
                "signal": signal,
                "pin": pin,
            }
        )
    return replacements, plan


def chain_labels(family: CounterFamily, donor_kind: str) -> tuple[dict[int, str], list[dict[str, object]]]:
    replacements, plan = sequential_labels(family, donor_kind)
    if family.key == "7490":
        output_names = {"Q0": "Q0", "Q1": "Q1", "Q2": "Q2", "Q3": "Q3"}
        clock_names = {"CKA": "CKA"}
    else:
        output_names = {"Q0": "Q0", "Q1": "Q1", "Q2": "Q2", "Q3": "Q3", "RCO": "RCO"}
        clock_names = {"CLK": "CLK"}
    for item in plan:
        chip_index = int(item["chip_index"])
        signal = str(item["signal"]).upper().replace(" ", "")
        if chip_index < 4 and signal in output_names and signal in {"Q3", "RCO"}:
            replacements[int(item["terminal_index"])] = f"CH{chip_index}{signal}"
            item["new_label"] = replacements[int(item["terminal_index"])]
            item["chain_role"] = "source_to_next_counter"
        if chip_index > 1 and signal in clock_names:
            replacements[int(item["terminal_index"])] = f"CH{chip_index - 1}Q3"
            item["new_label"] = replacements[int(item["terminal_index"])]
            item["chain_role"] = "clock_from_previous_counter"
    return replacements, plan


def static_issues(output: Path, family: CounterFamily, mutations: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(family.proteus_device.encode("ascii")) == 0:
        issues.append(f"expected device marker {family.proteus_device} missing")
    if cdb.count(family.proteus_device.encode("ascii")) == 0:
        issues.append(f"expected CDB device marker {family.proteus_device} missing")
    if chunk.count(b"$TERINPUT") or chunk.count(b"$TEROUTPUT"):
        issues.append("sequential counter object chunk should not contain ordinary input/output terminal records")
    if not chunk.count(b"$TERBIDIR"):
        issues.append("sequential counter output has no bidirectional terminals")
    if chunk.count(b"VSOURCE") or chunk.count(b"CSOURCE") or chunk.count(b"VSINE"):
        issues.append("unexpected source marker in sequential IC diagnostic")
    for mutation in mutations:
        if chunk.count(str(mutation["new"]).encode("ascii")) == 0:
            issues.append(f"mutated label {mutation['new']} not present")
    return issues


def write_case(
    case_id: str,
    family: CounterFamily,
    donor_kind: str,
    description: str,
    *,
    exact_repack: bool = False,
    replacements: dict[int, str] | None = None,
    label_plan: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    donor = family.donor(donor_kind)
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    mutations: list[dict[str, object]] = []
    pointers: dict[str, int] = {}
    if exact_repack:
        write_project_from_parts(
            donor,
            output,
            {
                "PROJECT.XML": patch_project_xml_version(read_internal_file(donor, "PROJECT.XML"), PROTEUS_813),
                "ROOT.DSN": patch_root_dsn_version(donor_dsn, PROTEUS_813),
                "ROOT.CDB": donor_cdb,
            },
        )
        method = "deterministic_exact_donor_repack"
    else:
        registry = FixtureRegistry.load()
        base = registry.get("e001_empty")
        base_dsn = read_internal_file(base.path, "ROOT.DSN")
        chunk = _extract_object_chunk(donor_dsn)
        if replacements:
            chunk, mutations = patch_bidir_labels(chunk, replacements)
        dsn, pointers = build_dsn_with_device_section(base_dsn, donor_dsn, chunk, _device_section(donor_dsn))
        dsn = patch_root_dsn_version(dsn, PROTEUS_813)
        write_project_from_parts(
            base.path,
            output,
            {
                "PROJECT.XML": patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813),
                "ROOT.DSN": dsn,
                "ROOT.CDB": donor_cdb,
            },
        )
        method = "donor_object_cdb_device_section_inserted_into_e001"

    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    manifest = {
        "case_id": case_id,
        "description": description,
        "method": method,
        "status": "temporary_pending_user_proteus_testing",
        "family": family.user_name,
        "proteus_device": family.proteus_device,
        "donor_kind": donor_kind,
        "donor": str(donor.relative_to(REPO)),
        "family_notes": family.notes,
        "terminal_policy": "all visible sequential counter IC pins use $TERBIDIR",
        "section_pointers": pointers,
        "label_plan": label_plan or [],
        "mutations": mutations,
        "container": {
            **{
                key: (str(value) if key == "path" else value)
                for key, value in inspect_pdsprj(output).__dict__.items()
            }
        },
        "marker_counts": marker_counts(chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "object_chunk_size": len(chunk),
        "static_validation_issues": static_issues(output, family, mutations),
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(bidir_events(chunk), indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 9, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    missing = [str(family.donor(kind)) for family in FAMILIES for kind in ("single", "two", "four", "four_rlc") if not family.donor(kind).exists()]
    if missing:
        raise FileNotFoundError("\n".join(missing))
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    manifests: list[dict[str, object]] = []
    pin_maps = [learned_pin_map(family) for family in FAMILIES]
    (OUT_ROOT / "learned_pin_maps.json").write_text(json.dumps(pin_maps, indent=2) + "\n", encoding="utf-8")

    for family in FAMILIES:
        prefix = family.user_name.replace("74HC90", "7490")
        manifests.append(
            write_case(
                f"T00_{prefix}_SINGLE_EXACT_REPACK",
                family,
                "single",
                "Exact deterministic repack of the user donor.",
                exact_repack=True,
            )
        )
        manifests.append(
            write_case(
                f"T01_{prefix}_SINGLE_E001_TRANSPLANT",
                family,
                "single",
                "Single counter object chunk, CDB, and device section inserted into E001 unchanged.",
            )
        )
        replacements, plan = sequential_labels(family, "single")
        manifests.append(
            write_case(
                f"T02_{prefix}_SINGLE_LABEL_MUTATION",
                family,
                "single",
                "Single counter with every bidirectional pin terminal relabelled from learned pin metadata.",
                replacements=replacements,
                label_plan=plan,
            )
        )
        replacements, plan = sequential_labels(family, "two")
        manifests.append(
            write_case(
                f"T03_{prefix}_2X_UNIQUE_LABELS",
                family,
                "two",
                "Two same-family counters with unique generated labels per package and pin.",
                replacements=replacements,
                label_plan=plan,
            )
        )
        replacements, plan = chain_labels(family, "four")
        manifests.append(
            write_case(
                f"T04_{prefix}_4X_CHAIN_LABELS",
                family,
                "four",
                "Four same-family counters with same-name bidirectional labels linking selected outputs to later clock pins.",
                replacements=replacements,
                label_plan=plan,
            )
        )
        replacements, plan = chain_labels(family, "four_rlc")
        manifests.append(
            write_case(
                f"T05_{prefix}_4X_CHAIN_RCL_LOAD",
                family,
                "four_rlc",
                "Four same-family counters with R/C/L load donor material preserved and counter pin labels generated.",
                replacements=replacements,
                label_plan=plan,
            )
        )

    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_SEQUENTIAL_COUNTERS_V1_TEMP_2026_06_09",
        "purpose": "First sequential/counter-only donor-learning pack for 7490/74HC90, 74HC160, 74HC161, and 74HC163.",
        "status": "temporary_pending_user_proteus_testing",
        "terminal_policy": "All visible sequential counter IC pins use $TERBIDIR. This does not alter the locked combinational IC policy.",
        "families": [family.user_name for family in FAMILIES],
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "learned_pin_maps": "learned_pin_maps.json",
        "archive": str(ARCHIVE_PATH.relative_to(REPO)),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "archive_sha256": archive_hash, "static_issue_cases": summary_issues}, indent=2))


if __name__ == "__main__":
    main()
