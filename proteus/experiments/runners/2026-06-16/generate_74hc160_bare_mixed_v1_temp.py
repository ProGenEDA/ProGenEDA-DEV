"""Generate focused bare-component 74HC160 placement tests.

V4 master-sheet testing showed the full-CDB packet-selection route works, but
74HC160 cases accidentally included intervening combinational/RLC records. The
cause was packet boundaries ending at the next *sequential* packet rather than
the next object packet. This experiment uses stricter component-body boundaries
and emits bare components only:

    ROOT.DSN object stream = 00 + selected component body records + FF
    no $TER* terminal records
    no WIRE records
    full donor ROOT.CDB preserved byte-for-byte

This is intentionally a placement-only probe for the new component placer plan.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.component_placer import parse_component_placer_cdb
from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


DONOR = ROOT / "proteus/active/evidence/donors/manual_downloads_20260615/component_placer/16x_seq_combo_mega_donor.pdsprj"
OUT_DIR = ROOT / "experiments/74hc160_bare_mixed_v1_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/74HC160_BARE_MIXED_V1_TEMP_2026_06_16.zip"

FAMILY_MARKERS = (
    "74HC160",
    "74HC266",
    "74HC86",
    "74HC32",
    "74HC08",
    "74HC02",
    "74HC00",
    "RESISTOR",
    "REALIND",
    "CAP",
)
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")
WIRE_MARKER = b"WIRE"
BODY_START_RE = re.compile(rb"\xff[\x02-\x07]((?:U\d+(?::[A-Z])?)|(?:R\d+)|(?:C\d+)|(?:L\d+))")


@dataclass(frozen=True)
class BodySpan:
    ref: str
    family: str
    start: int
    end: int
    data: bytes

    def as_dict(self) -> dict[str, object]:
        return {
            "ref": self.ref,
            "family": self.family,
            "start": self.start,
            "end": self.end,
            "size": len(self.data),
            "sha256": sha256_bytes(self.data),
        }


@dataclass(frozen=True)
class ComponentGroup:
    key: str
    family: str
    spans: tuple[BodySpan, ...]

    @property
    def start(self) -> int:
        return min(span.start for span in self.spans)

    @property
    def data(self) -> bytes:
        return b"".join(span.data for span in sorted(self.spans, key=lambda item: item.start))

    def as_dict(self) -> dict[str, object]:
        data = self.data
        return {
            "key": self.key,
            "family": self.family,
            "start": self.start,
            "span_count": len(self.spans),
            "size": len(data),
            "refs": [span.ref for span in sorted(self.spans, key=lambda item: item.start)],
            "sha256": sha256_bytes(data),
        }


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    description: str
    counts: dict[str, int]
    selected: tuple[ComponentGroup, ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def terminal_starts(chunk: bytes) -> list[int]:
    starts: set[int] = set()
    for marker in TERM_MARKERS:
        pos = 0
        while True:
            found = chunk.find(marker, pos)
            if found < 0:
                break
            starts.add(max(0, found - 14))
            pos = found + 1
    return sorted(starts)


def wire_starts(chunk: bytes) -> list[int]:
    starts: list[int] = []
    pos = 0
    while True:
        found = chunk.find(WIRE_MARKER, pos)
        if found < 0:
            break
        starts.append(max(0, found - 14))
        pos = found + 1
    return starts


def detect_body_starts(chunk: bytes) -> list[tuple[int, str]]:
    starts: list[tuple[int, str]] = []
    for match in BODY_START_RE.finditer(chunk):
        start = match.start()
        window = chunk[start : start + 130]
        if b"COMPONENT ID" not in window:
            continue
        ref = match.group(1).decode("ascii", "ignore")
        starts.append((start, ref))
    return starts


def family_for_body(data: bytes) -> str | None:
    hits = [family for family in FAMILY_MARKERS if family.encode("ascii") in data]
    return hits[0] if hits else None


def package_key(ref: str) -> str:
    if ref.startswith("U"):
        return ref.split(":", 1)[0]
    return ref


def analyze_bare_groups(chunk: bytes) -> dict[str, list[ComponentGroup]]:
    body_starts = detect_body_starts(chunk)
    breakpoints = sorted({start for start, _ref in body_starts} | set(terminal_starts(chunk)) | set(wire_starts(chunk)) | {len(chunk) - 1})
    spans: list[BodySpan] = []
    for start, ref in body_starts:
        end_candidates = [point for point in breakpoints if point > start]
        if not end_candidates:
            continue
        end = end_candidates[0]
        data = chunk[start:end]
        family = family_for_body(data)
        if family is None:
            continue
        if any(marker in data for marker in TERM_MARKERS) or WIRE_MARKER in data:
            raise ValueError(f"Body span for {ref} contains terminal/wire bytes; boundary detector is wrong.")
        spans.append(BodySpan(ref=ref, family=family, start=start, end=end, data=data))

    grouped_spans: dict[str, list[BodySpan]] = defaultdict(list)
    for span in spans:
        grouped_spans[package_key(span.ref)].append(span)

    by_family: dict[str, list[ComponentGroup]] = defaultdict(list)
    for key, items in grouped_spans.items():
        families = Counter(span.family for span in items)
        if len(families) != 1:
            raise ValueError(f"Component group {key} mixes families: {dict(families)}")
        family = next(iter(families))
        group = ComponentGroup(key=key, family=family, spans=tuple(sorted(items, key=lambda item: item.start)))
        by_family[family].append(group)

    for family in by_family:
        by_family[family].sort(key=lambda group: group.start)
    return dict(by_family)


def select(groups: dict[str, list[ComponentGroup]], counts: dict[str, int]) -> tuple[ComponentGroup, ...]:
    selected: list[ComponentGroup] = []
    for family, count in counts.items():
        available = groups.get(family, [])
        if len(available) < count:
            raise ValueError(f"Need {count} {family} groups, only found {len(available)}.")
        selected.extend(available[:count])
    return tuple(sorted(selected, key=lambda group: group.start))


def case_specs(groups: dict[str, list[ComponentGroup]]) -> list[CaseSpec]:
    raw_cases = [
        ("B00_74HC160_1X_BARE", "One bare 74HC160 body-only placement.", {"74HC160": 1}),
        ("B01_74HC160_3X_BARE", "Three bare 74HC160 body-only placements.", {"74HC160": 3}),
        ("B02_74HC160_5X_BARE", "Five bare 74HC160 body-only placements.", {"74HC160": 5}),
        (
            "B03_MIX5_160_HC08_R_C_L_BARE",
            "Five component families: 2x 74HC160, 2x 74HC08 packages, 4x resistor, 3x capacitor, 2x inductor.",
            {"74HC160": 2, "74HC08": 2, "RESISTOR": 4, "CAP": 3, "REALIND": 2},
        ),
        (
            "B04_MIX5_160_HC32_HC00_R_C_BARE",
            "Five component families: 4x 74HC160, 3x 74HC32 packages, 2x 74HC00 packages, 5x resistor, 2x capacitor.",
            {"74HC160": 4, "74HC32": 3, "74HC00": 2, "RESISTOR": 5, "CAP": 2},
        ),
        (
            "B05_MIX5_160_HC86_HC266_L_C_BARE",
            "Five component families: 5x 74HC160, 2x 74HC86 packages, 2x 74HC266 packages, 4x inductor, 4x capacitor.",
            {"74HC160": 5, "74HC86": 2, "74HC266": 2, "REALIND": 4, "CAP": 4},
        ),
        (
            "B06_MIX5_160_HC02_HC08_R_L_BARE",
            "Five component families: 7x 74HC160, 3x 74HC02 packages, 1x 74HC08 package, 8x resistor, 3x inductor.",
            {"74HC160": 7, "74HC02": 3, "74HC08": 1, "RESISTOR": 8, "REALIND": 3},
        ),
        (
            "B07_MIX5_160_HC32_HC86_R_C_BARE",
            "Five component families: 9x 74HC160, 2x 74HC32 packages, 2x 74HC86 packages, 6x resistor, 6x capacitor.",
            {"74HC160": 9, "74HC32": 2, "74HC86": 2, "RESISTOR": 6, "CAP": 6},
        ),
    ]
    return [CaseSpec(case_id, description, counts, select(groups, counts)) for case_id, description, counts in raw_cases]


def marker_counts(data: bytes) -> dict[str, int]:
    markers = FAMILY_MARKERS + ("$TERBIDIR", "$TERINPUT", "$TEROUTPUT", "$TERPOWER", "$TERGROUND", "WIRE")
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def write_case(case: CaseSpec, donor_dsn: bytes, donor_cdb: bytes) -> dict[str, object]:
    case_dir = OUT_DIR / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    object_records = b"".join(group.data for group in case.selected)
    object_chunk = b"\x00" + object_records + b"\xff"
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(DONOR, output, {"ROOT.DSN": dsn, "ROOT.CDB": donor_cdb}, compression=ZIP_DEFLATED)

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_cdb = read_internal_file(output, "ROOT.CDB")
    final_chunk = _extract_object_chunk(final_dsn)
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk does not match planned bare object chunk")
    if final_cdb != donor_cdb:
        errors.append("ROOT.CDB was not preserved byte-for-byte")
    if any(marker in final_chunk for marker in TERM_MARKERS):
        errors.append("terminal records remain in bare-component output")
    if WIRE_MARKER in final_chunk:
        errors.append("wire records remain in bare-component output")
    found_counts = Counter(group.family for group in case.selected)
    if dict(found_counts) != case.counts:
        errors.append("selected family counts do not match requested counts")

    parsed_cdb = parse_component_placer_cdb(final_cdb)
    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "requested_counts": case.counts,
        "selected_counts": dict(found_counts),
        "selected_components": [group.as_dict() for group in case.selected],
        "placement_policy": "bare component body records only; no terminals and no wires",
        "cdb_policy": "full 16x master ROOT.CDB preserved byte-for-byte",
        "cdb_summary": {
            "pin_row_count": len(parsed_cdb.pin_rows),
            "property_row_count": len(parsed_cdb.property_rows),
            "pin_package_ref_count": len(set(parsed_cdb.pin_package_refs())),
            "property_package_ref_count": len(set(parsed_cdb.property_package_refs())),
        },
        "section_pointers": pointers,
        "marker_counts": marker_counts(final_chunk),
        "object_chunk_size": len(final_chunk),
        "valid_static": not errors,
        "errors": errors,
        "hashes": {
            "project": sha256_file(output),
            "ROOT.DSN": sha256_bytes(final_dsn),
            "ROOT.CDB": sha256_bytes(final_cdb),
            "object_chunk": sha256_bytes(final_chunk),
        },
        "project": str(output.relative_to(OUT_DIR)),
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def copy_control() -> dict[str, object]:
    case_id = "C00_16X_MASTER_EXACT_DONOR_COPY"
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(DONOR, output)
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    manifest = {
        "case_id": case_id,
        "description": "Exact 16x master donor copy control.",
        "type": "exact_donor_copy",
        "valid_static": True,
        "hashes": {
            "project": sha256_file(output),
            "ROOT.DSN": sha256_bytes(dsn),
            "ROOT.CDB": sha256_bytes(cdb),
            "object_chunk": sha256_bytes(_extract_object_chunk(dsn)),
        },
        "project": str(output.relative_to(OUT_DIR)),
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    with ZipFile(ZIP_OUT, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_DIR.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(OUT_DIR.parent).as_posix())
            info.date_time = (2026, 6, 16, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, file_path.read_bytes())
    return sha256_file(ZIP_OUT)


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    donor_dsn = read_internal_file(DONOR, "ROOT.DSN")
    donor_cdb = read_internal_file(DONOR, "ROOT.CDB")
    donor_chunk = _extract_object_chunk(donor_dsn)
    rebuilt_dsn, _ = build_dsn(donor_dsn, donor_dsn, donor_chunk)
    if rebuilt_dsn != donor_dsn:
        raise ValueError("16x master donor DSN is not byte-stable under build_dsn.")

    groups = analyze_bare_groups(donor_chunk)
    inventory = {
        family: {
            "component_group_count": len(items),
            "first_groups": [group.as_dict() for group in items[:5]],
        }
        for family, items in sorted(groups.items())
    }
    cases = case_specs(groups)
    controls = [copy_control()]
    manifests = [write_case(case, donor_dsn, donor_cdb) for case in cases]
    static_issue_cases = {manifest["case_id"]: manifest["errors"] for manifest in manifests if manifest["errors"]}
    summary = {
        "experiment": "74hc160_bare_mixed_v1_temp_2026_06_16",
        "status": "static generated; awaiting user Proteus confirmation",
        "purpose": "Focused 74HC160 correction plus bare mixed component placement tests.",
        "donor": str(DONOR.relative_to(ROOT)),
        "root_cause_fixed": "74HC160 packet boundaries now stop at the next object boundary, not the next sequential-family packet.",
        "bare_policy": "component body records only; no $TER* terminal records and no WIRE records",
        "cdb_policy": "full master ROOT.CDB preserved byte-for-byte",
        "case_count": len(manifests),
        "control_count": len(controls),
        "static_issue_cases": static_issue_cases,
        "inventory": inventory,
        "controls": controls,
        "donor_hashes": {
            "project": sha256_file(DONOR),
            "ROOT.DSN": sha256_bytes(donor_dsn),
            "ROOT.CDB": sha256_bytes(donor_cdb),
            "object_chunk": sha256_bytes(donor_chunk),
        },
    }
    (OUT_DIR / "donor_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "README.txt").write_text(
        "74HC160 bare mixed V1 pack.\n"
        "Test C00 first. B00-B07 are generated bare-component cases with no terminals and no wires.\n"
        "This pack fixes the prior 74HC160 over-capture by using strict object body boundaries.\n",
        encoding="utf-8",
    )
    archive_hash = write_archive()
    summary["archive"] = str(ZIP_OUT.relative_to(ROOT))
    summary["archive_sha256"] = archive_hash
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "case_count": len(manifests), "static_issue_cases": static_issue_cases, "archive_sha256": archive_hash}, indent=2, sort_keys=True))
    return 0 if not static_issue_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
