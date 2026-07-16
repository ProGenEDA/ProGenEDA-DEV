"""Generate a focused one-IC 7490/74HC90 native test pack.

This intentionally avoids all cross-donor mixing. Every case uses only
Proteus-created 7490 donors so failures can be attributed to one operation:
exact rezip, whole-donor E001 transplant, or bidirectional terminal label
mutation.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_7490_focused_v1_temp_2026_06_12"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "IC_7490_FOCUSED_V1_TEMP_2026_06_12.zip"

from proteusgen.ic_native import NativeRegistry, generate_ic_native_project_from_payload, read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def donor_locator(kind: str) -> str:
    registry = NativeRegistry.load()
    path = registry.component("7490").donors[kind]
    return str(path.relative_to(registry.root)).replace("\\", "/")


def components(count: int) -> list[dict[str, object]]:
    return [{"ref": f"U{index}", "part": "74HC90"} for index in range(1, count + 1)]


def exact_case(case_id: str, kind: str, title: str) -> dict[str, object]:
    return {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": case_id,
        "title": title,
        "donor": donor_locator(kind),
        "exact_rezip": True,
        "components": components({"single": 1, "two": 2, "four": 4, "four_rlc": 4}[kind]),
    }


def transplant_unchanged_case(case_id: str, kind: str, title: str) -> dict[str, object]:
    return {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": case_id,
        "title": title,
        "donor": donor_locator(kind),
    }


def generated_label_case(case_id: str, count: int, title: str) -> dict[str, object]:
    return {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": case_id,
        "title": title,
        "components": components(count),
    }


def single_explicit_case() -> dict[str, object]:
    return {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T03_7490_SINGLE_EXPLICIT_PIN_LABELS",
        "title": "7490 single donor with explicit bider labels on every pin",
        "components": [
            {
                "ref": "U1",
                "part": "74HC90",
                "connections": {
                    "CKA": "CLK_A",
                    "CKB": "CLK_B",
                    "R01": "RST_01",
                    "R02": "RST_02",
                    "R91": "RST_91",
                    "R92": "RST_92",
                    "Q0": "QA",
                    "Q1": "QB",
                    "Q2": "QC",
                    "Q3": "QD",
                },
            }
        ],
    }


def chain_case(case_id: str, count: int, title: str) -> dict[str, object]:
    items = components(count)
    for index, item in enumerate(items, start=1):
        connections = {
            "CKA": f"CLK{index}",
            "CKB": f"CKB{index}",
            "R01": f"RST{index}A",
            "R02": f"RST{index}B",
            "R91": f"RST{index}C",
            "R92": f"RST{index}D",
            "Q0": f"Q{index}A",
            "Q1": f"Q{index}B",
            "Q2": f"Q{index}C",
            "Q3": f"Q{index}D",
        }
        if index > 1:
            connections["CKA"] = f"CHAIN{index - 1}"
        if index < count:
            connections["Q0"] = f"CHAIN{index}"
        item["connections"] = connections
    return {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": case_id,
        "title": title,
        "components": items,
    }


CASES = [
    exact_case("T00_7490_SINGLE_EXACT_REZIP", "single", "Exact rezip of the single 7490 donor"),
    transplant_unchanged_case("T01_7490_SINGLE_E001_UNCHANGED", "single", "Single 7490 donor inserted into E001 with no label mutation"),
    generated_label_case("T02_7490_SINGLE_GENERATED_LABELS", 1, "Single 7490 donor with generated unique bider labels"),
    single_explicit_case(),
    exact_case("T04_7490_2X_EXACT_REZIP", "two", "Exact rezip of the 2x 7490 donor"),
    transplant_unchanged_case("T05_7490_2X_E001_UNCHANGED", "two", "2x 7490 donor inserted into E001 with no label mutation"),
    generated_label_case("T06_7490_2X_GENERATED_LABELS", 2, "2x 7490 donor with generated unique bider labels"),
    chain_case("T07_7490_2X_Q0_TO_CKA_CHAIN", 2, "2x 7490 donor with U1 Q0 sharing a bider net with U2 CKA"),
    exact_case("T08_7490_4X_EXACT_REZIP", "four", "Exact rezip of the 4x 7490 donor"),
    transplant_unchanged_case("T09_7490_4X_E001_UNCHANGED", "four", "4x 7490 donor inserted into E001 with no label mutation"),
    generated_label_case("T10_7490_4X_GENERATED_LABELS", 4, "4x 7490 donor with generated unique bider labels"),
    chain_case("T11_7490_4X_Q0_TO_CKA_CHAIN", 4, "4x 7490 donor with chained Q0 to next CKA same-name bider nets"),
    exact_case("T12_7490_4X_RLC_EXACT_REZIP", "four_rlc", "Exact rezip of the 4x 7490 with RLC donor"),
    transplant_unchanged_case("T13_7490_4X_RLC_E001_UNCHANGED", "four_rlc", "4x 7490 with RLC donor inserted into E001 with no label mutation"),
]


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
    blocked: list[dict[str, object]] = []
    for payload in CASES:
        case_id = str(payload["case_id"])
        case_dir = OUT_ROOT / case_id
        try:
            result = generate_ic_native_project_from_payload(payload, case_dir)
            dsn = read_internal_file(result.output_path, "ROOT.DSN")
            cdb = read_internal_file(result.output_path, "ROOT.CDB")
            chunk = _extract_object_chunk(dsn)
            manifest = dict(result.manifest)
            manifest["pack_case_notes"] = {
                "focus": "7490 only",
                "operation": payload.get("title"),
                "no_cross_donor_cdb_synthesis": True,
                "terminal_bidir_count": chunk.count(b"$TERBIDIR"),
                "root_cdb_sha256": _sha256_bytes(cdb),
            }
            result.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifests.append(manifest)
        except Exception as exc:  # noqa: BLE001 - blocked cases are explicit in the temp pack summary.
            blocked.append({"case_id": case_id, "error": repr(exc), "payload": payload})

    static_issue_cases = {
        str(item["case_id"]): item.get("static_validation_issues", [])
        for item in manifests
        if item.get("static_validation_issues")
    }
    archive = write_archive()
    summary = {
        "pack": "IC_7490_FOCUSED_V1_TEMP_2026_06_12",
        "generated_case_count": len(manifests),
        "blocked_cases": blocked,
        "static_issue_cases": static_issue_cases,
        "cases": [item["case_id"] for item in manifests],
        "archive": archive,
        "archive_sha256": _sha256_bytes(Path(archive).read_bytes()),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
