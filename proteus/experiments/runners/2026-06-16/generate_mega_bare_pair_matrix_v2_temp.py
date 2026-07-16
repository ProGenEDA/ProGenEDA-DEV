"""Generate the corrected no-terminal two-family pair matrix.

This replaces the over-large V1 three-family matrix for user testing. Each
unordered component-family pair appears exactly once. Each family gets one
deterministic count selected from 1, 3, 5, 15, and 23, bounded by donor
availability and current safety caps.

7-segment displays are excluded from this broad matrix because mixed display
case G11 failed in the prior pack; displays are handled in the focused V3 pack.
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn

HELPER_PATH = ROOT / "proteus/experiments/runners/2026-06-16/generate_mega_bare_separation_v1_temp.py"
OUT_DIR = ROOT / "experiments/mega_bare_pair_matrix_v2_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/MEGA_BARE_PAIR_MATRIX_V2_TEMP_2026_06_16.zip"
MEGA_NO_SOURCE = (
    ROOT
    / "proteus/archive/donors/manual_downloads_20260616/mega_component_placer/Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)

COUNT_CHOICES = (1, 3, 5, 15, 23)
SOURCE_FAMILIES = {"VSOURCE", "CSOURCE", "VSINE"}
EXCLUDED_FROM_PAIR_MATRIX = {"7SEG-COM-ANODE"}
MAX_SAFE_COUNTS = {
    # User reported 4027x03 worked while x5/x15/x23 failed in the broad matrix.
    # The focused V3 pack separately tests a new cloned high-count 4027 method.
    "4027": 3,
}

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


def choose_count(pair: tuple[str, str], family: str, available: int) -> int:
    cap = min(available, MAX_SAFE_COUNTS.get(family, available))
    digest = hashlib.sha256(("|".join(pair) + "::" + family).encode("ascii")).digest()
    start = digest[0] % len(COUNT_CHOICES)
    ordered = COUNT_CHOICES[start:] + COUNT_CHOICES[:start]
    for count in ordered:
        if count <= cap:
            return count
    return 1


def marker_counts(data: bytes) -> dict[str, int]:
    markers = (
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


def write_case(case_id: str, state, selected, counts: dict[str, int], description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    object_chunk, finalization = load_helper_cached.object_chunk_for(selected)
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
        "object_chunk_size": len(final_chunk),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "marker_counts": marker_counts(final_chunk),
        "pointers": pointers,
        "finalization": finalization,
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

    families = tuple(sorted((set(mega.counts()) - EXCLUDED_FROM_PAIR_MATRIX) | SOURCE_FAMILIES))
    cases: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for index, pair in enumerate(itertools.combinations(families, 2)):
        state = source if any(family in SOURCE_FAMILIES for family in pair) else mega
        counts = {family: choose_count(pair, family, len(state.groups_by_family.get(family, ()))) for family in pair}
        name = "__".join(f"{safe_name(family)}x{counts[family]:02d}" for family in pair)
        case_id = f"P{index:04d}_{name}"
        try:
            selected = helper.select_groups(state, counts)
            cases.append(write_case(case_id, state, selected, counts, f"Two-family no-terminal pair: {pair[0]} and {pair[1]}."))
        except Exception as exc:
            failures.append({"case_id": case_id, "pair": list(pair), "requested_counts": counts, "error": str(exc)})

    return {
        "experiment": "mega_bare_pair_matrix_v2_temp_2026_06_16",
        "purpose": "Corrected one-case-per-unordered-two-family no-terminal pair matrix.",
        "interpretation": "Each pair appears exactly once. Each side receives one deterministic count from 1, 3, 5, 15, 23, bounded by donor availability and known temporary safety caps.",
        "count_choices": list(COUNT_CHOICES),
        "excluded_from_pair_matrix": sorted(EXCLUDED_FROM_PAIR_MATRIX),
        "max_safe_counts": MAX_SAFE_COUNTS,
        "family_count": len(families),
        "families": list(families),
        "pair_case_count": len(cases),
        "failure_count": len(failures),
        "failures": failures,
        "donor_counts": {
            "mega_no_source": mega.counts(),
            "15xsemimega_with_source": source.counts(),
        },
        "cases": cases,
    }


def main() -> None:
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": summary["pair_case_count"], "failures": summary["failure_count"], "zip_sha256": sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
