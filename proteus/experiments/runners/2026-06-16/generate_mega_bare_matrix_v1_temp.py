"""Generate the large no-terminal mega bare-placement matrix.

User request:
- Same-family counts: 1, 3, 5, 15, and 23 of every supported family.
- All possible 3-family combinations, with each family count chosen
  deterministically from 1, 3, 5, 15, and 23.
- No terminals; this is for the new component-placer training path.

This script keeps the locked routed generators untouched. It uses the
user-confirmed mega no-terminal final-record rule for normal component packets,
adds VSINE to the source inventory, and uses the verified standalone
common-anode display record relationship for 7-segment display repeats.
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn

HELPER_PATH = ROOT / "proteus/experiments/runners/2026-06-16/generate_mega_bare_separation_v1_temp.py"
OUT_DIR = ROOT / "experiments/mega_bare_matrix_v1_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/MEGA_BARE_MATRIX_V1_TEMP_2026_06_16.zip"

MEGA_NO_SOURCE = (
    ROOT
    / "proteus/archive/donors/manual_downloads_20260616/mega_component_placer/Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)
DISPLAY_ANODE_SINGLE = ROOT / "proteus/active/evidence/donors/manual_downloads_20260611/squence/7segcomanode.pdsprj"
DISPLAY_ANODE_DOUBLE = ROOT / "proteus/active/evidence/donors/manual_downloads_20260611/squence/27segcomanode.pdsprj"

COUNT_CHOICES = (1, 3, 5, 15, 23)
SOURCE_FAMILIES = {"VSOURCE", "CSOURCE", "VSINE"}
DISPLAY_FAMILY = "__STANDALONE_DISPLAY_NOT_USED_IN_MATRIX__"

SHORT = {
    "RESISTOR": "R",
    "CAP": "C",
    "REALIND": "L",
    "CAP-ELEC": "CE",
    "DIODE": "DIO",
    "LM741": "741",
    "NE555": "555",
    "NPN": "NPN",
    "PNP": "PNP",
    "VSOURCE": "VDC",
    "CSOURCE": "IDC",
    "VSINE": "VAC",
    "7SEG-COM-ANODE": "7SA",
    DISPLAY_FAMILY: "7SA",
}


def load_helper():
    spec = importlib.util.spec_from_file_location("mega_bare_v1", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper script: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mega_bare_v1"] = module
    spec.loader.exec_module(module)
    module.OUT_DIR = OUT_DIR
    module.FAMILY_MARKERS = tuple(sorted(set(module.FAMILY_MARKERS + ("VSINE",)), key=len, reverse=True))
    return module


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def zip_dir(src: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with ZipFile(output, "w") as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            info = ZipInfo(path.relative_to(src).as_posix())
            info.compress_type = ZIP_DEFLATED
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o600 << 16
            zf.writestr(info, path.read_bytes())


def safe_name(family: str) -> str:
    return SHORT.get(family, family).replace("-", "").replace("_", "")


def marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "7SEGCOMA",
        "VSOURCE",
        "CSOURCE",
        "VSINE",
        "RESISTOR",
        "CAP",
        "REALIND",
        "CAP-ELEC",
        "DIODE",
        "LM741",
        "NE555",
        "NPN",
        "PNP",
        "7447",
        "7490",
        "4511",
        "4027",
        "74HC",
        "$TERBIDIR",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERPOWER",
        "$TERGROUND",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def display_record_parts() -> tuple[bytes, bytes]:
    final_record = _extract_object_chunk(read_internal_file(DISPLAY_ANODE_SINGLE, "ROOT.DSN"))
    double_chunk = _extract_object_chunk(read_internal_file(DISPLAY_ANODE_DOUBLE, "ROOT.DSN"))
    middle_record = final_record[:-2]
    if double_chunk != middle_record + final_record:
        raise ValueError("7seg common-anode single/double donor relationship changed; refusing display synthesis.")
    return middle_record, final_record


def display_records(count: int) -> bytes:
    middle, final = display_record_parts()
    return middle * (count - 1) + final


def choose_count(combo: tuple[str, ...], family: str, available: int) -> int:
    digest = hashlib.sha256(("|".join(combo) + "::" + family).encode("ascii")).digest()
    start = digest[0] % len(COUNT_CHOICES)
    ordered = COUNT_CHOICES[start:] + COUNT_CHOICES[:start]
    for count in ordered:
        if count <= available:
            return count
    return 1


def host_for(helper, mega_state, source_state, display_state, families: tuple[str, ...]):
    if any(family in SOURCE_FAMILIES for family in families):
        return source_state
    if all(family == DISPLAY_FAMILY for family in families):
        return display_state
    return mega_state


def available_count(state, family: str) -> int:
    if family == DISPLAY_FAMILY:
        return 10_000
    return len(state.groups_by_family.get(family, ()))


def selected_normal_groups(helper, state, counts: dict[str, int]):
    normal_counts = {family: count for family, count in counts.items() if family != DISPLAY_FAMILY}
    if not normal_counts:
        return ()
    return helper.select_groups(state, normal_counts)


def object_chunk_for_selection(helper, selected, display_count: int) -> bytes:
    if display_count <= 0:
        return helper.object_chunk_for(selected)[0]
    display = display_records(display_count)
    if not selected:
        return display
    ordered = tuple(sorted(selected, key=lambda item: item.start))
    if any(group.source_is_final for group in ordered):
        raise ValueError("Refusing to append display after a donor-final normal group.")
    return b"\x00\x00" + b"".join(group.data for group in ordered) + display


def write_case(case_id: str, state, selected, display_count: int, counts: dict[str, int], description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    object_chunk = object_chunk_for_selection(load_helper_cached, selected, display_count)
    dsn, pointers = build_dsn(state.dsn, state.dsn, object_chunk)
    write_project_from_parts(state.path, output, {"ROOT.DSN": dsn, "ROOT.CDB": state.cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    final_cdb = read_internal_file(output, "ROOT.CDB")
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs from requested chunk")
    if final_cdb != state.cdb:
        errors.append("ROOT.CDB differs from host donor")
    if any(term in final_chunk for term in (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")):
        errors.append("terminal marker present")
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "host": str(state.path.relative_to(ROOT)),
        "description": description,
        "requested_counts": counts,
        "normal_group_count": len(selected),
        "display_count": display_count,
        "object_chunk_size": len(final_chunk),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "marker_counts": marker_counts(final_chunk),
        "pointers": pointers,
        "errors": errors,
    }


load_helper_cached = None


def build_cases() -> dict[str, object]:
    global load_helper_cached
    helper = load_helper()
    load_helper_cached = helper
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    mega = helper.load_donor(MEGA_NO_SOURCE)
    source = helper.load_donor(helper.FIFTEEN_X_WITH_SOURCE)
    display_state = SimpleNamespace(
        path=DISPLAY_ANODE_SINGLE,
        dsn=read_internal_file(DISPLAY_ANODE_SINGLE, "ROOT.DSN"),
        cdb=read_internal_file(DISPLAY_ANODE_SINGLE, "ROOT.CDB"),
        groups_by_family={},
        counts=lambda: {DISPLAY_FAMILY: "synthetic_from_single_and_double_display_donors"},
    )

    normal_families = sorted(mega.counts())
    families = tuple(sorted(normal_families + sorted(SOURCE_FAMILIES)))

    cases: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    def add_case(case_id: str, requested: dict[str, int], description: str) -> None:
        fams = tuple(sorted(requested))
        state = host_for(helper, mega, source, display_state, fams)
        bounded: dict[str, int] = {}
        for family, count in requested.items():
            bounded[family] = min(count, available_count(state, family))
        try:
            selected = selected_normal_groups(helper, state, bounded)
            display_count = bounded.get(DISPLAY_FAMILY, 0)
            cases.append(write_case(case_id, state, selected, display_count, bounded, description))
        except Exception as exc:  # keep matrix generation moving and report exact failed recipe
            failures.append({"case_id": case_id, "requested_counts": requested, "error": str(exc)})

    index = 0
    for family in families:
        for count in COUNT_CHOICES:
            case_id = f"S{index:04d}_{safe_name(family)}x{count:02d}"
            add_case(case_id, {family: count}, f"Same-family no-terminal placement: {count} x {family}.")
            index += 1

    triple_index = 0
    for combo in itertools.combinations(families, 3):
        state = host_for(helper, mega, source, display_state, combo)
        counts = {family: choose_count(combo, family, available_count(state, family)) for family in combo}
        name = "_".join(f"{safe_name(family)}x{counts[family]:02d}" for family in combo)
        case_id = f"T{triple_index:04d}_{name}"
        add_case(case_id, counts, f"Three-family no-terminal placement combination: {', '.join(combo)}.")
        triple_index += 1

    return {
        "experiment": "mega_bare_matrix_v1_temp_2026_06_16",
        "purpose": "Same-family 1/3/5/15/23 and all unordered three-family no-terminal placement combinations.",
        "interpretation": "The user clarification is implemented as all unordered 3-component-family combinations; each family count is deterministically selected from 1, 3, 5, 15, 23.",
        "count_choices": list(COUNT_CHOICES),
        "family_count": len(families),
        "families": list(families),
        "same_family_case_count": len(families) * len(COUNT_CHOICES),
        "triple_case_count": triple_index,
        "case_count": len(cases),
        "failure_count": len(failures),
        "failures": failures,
        "donor_counts": {
            "mega_no_source": mega.counts(),
            "15xsemimega_with_source": source.counts(),
            "display_anode_single": display_state.counts(),
        },
        "source_donors": {
            "mega_no_source": str(MEGA_NO_SOURCE.relative_to(ROOT)),
            "15xsemimega_with_source": str(helper.FIFTEEN_X_WITH_SOURCE.relative_to(ROOT)),
            "display_anode_single": str(DISPLAY_ANODE_SINGLE.relative_to(ROOT)),
        },
        "cases": cases,
    }


def main() -> None:
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(
        json.dumps(
            {
                "out_dir": str(OUT_DIR),
                "zip": str(ZIP_OUT),
                "cases": summary["case_count"],
                "failures": summary["failure_count"],
                "zip_sha256": sha256_file(ZIP_OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
