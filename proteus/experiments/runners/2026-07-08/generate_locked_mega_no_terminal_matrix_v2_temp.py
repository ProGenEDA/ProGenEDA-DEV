"""Regenerate focused no-terminal locked-mega component placer evidence.

This is intentionally a component-placer evidence runner, not a terminal
placement script.  It calls the shared component placer, preserves ROOT.CDB
byte-for-byte via ``full_cdb=True``, and writes Proteus-openable controls for
the display-row and mixed-layout fixes.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / "proteus" / "active" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "proteus" / "active" / "src"))

from proteusgen.component_placer import (  # noqa: E402
    NEW_COMPONENT_MEGA_DONOR,
    generate_component_placement_project,
)
from proteusgen.pdsprj import read_internal_file  # noqa: E402


OUT_DIR = ROOT / "proteus" / "experiments" / "runs" / "locked_mega_no_terminal_matrix_v2_temp_2026_07_08"
ARCHIVE = ROOT / "proteus" / "experiments" / "runs" / "LOCKED_MEGA_NO_TERMINAL_MATRIX_V2_TEMP_2026_07_08"
DONOR = ROOT / NEW_COMPONENT_MEGA_DONOR


SUPPORTED_FAMILIES = (
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "2N3904",
    "2N4401",
    "2N7000",
    "7SEG-COM-AN-RED",
    "7SEG-COM-CAT-BLUE",
    "40EPS08",
    "74HC00",
    "74HC02",
    "74HC04",
    "74HC08",
    "74HC32",
    "74HC74",
    "74HC76",
    "74HC85",
    "74HC86",
    "74HC151",
    "74HC157",
    "74HC160",
    "74HC174",
    "74HC192",
    "74HC266",
    "74HC283",
    "4027",
    "4511",
    "7447",
    "7490",
    "BRIDGE",
    "BS170",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "CAP",
    "CAP-ELEC",
    "CSOURCE",
    "DIODE",
    "FUSE",
    "LED-RED",
    "LM317T",
    "LM741",
    "NE555",
    "NMOSFET",
    "NPN",
    "OPAMP",
    "PNP",
    "POT-HG",
    "REALIND",
    "RESISTOR",
    "SWITCH",
    "TRAN-2P2S",
    "VPULSE",
    "VSINE",
    "VSOURCE",
)


COUNT_LIMITS = {
    "74HC00": 8,
    "74HC02": 12,
    "74HC04": 15,
    "74HC08": 15,
    "74HC74": 19,
}


@dataclass(frozen=True)
class Case:
    folder: str
    name: str
    components: dict[str, int]


def _payload(components: dict[str, int]) -> dict[str, Any]:
    return {
        "donor": str(DONOR),
        "components": components,
        "layout": {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        },
    }


def _case_slug(text: str) -> str:
    return (
        text.replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace(":", "")
    )


def _cases() -> list[Case]:
    cases: list[Case] = []
    for family in ("7SEG-COM-AN-RED", "7SEG-COM-CAT-BLUE"):
        for count in (1, 3, 9, 15, 20):
            cases.append(
                Case(
                    "01_display_solo_scaling",
                    f"{family}_{count}x",
                    {family: count},
                )
            )
    for family in ("4027", "74HC266"):
        cases.append(
            Case(
                "02_multipart_native_packet_controls",
                f"{family}_3x_no_terminal",
                {family: 3},
            )
        )
    cases.append(
        Case(
            "02_multipart_native_packet_controls",
            "4027_74HC266_3x_each_no_terminal",
            {"4027": 3, "74HC266": 3},
        )
    )
    for count in (1, 3, 8):
        cases.append(
            Case(
                "09_mixed_all_uniform",
                f"all_{count}x_each",
                {family: count for family in SUPPORTED_FAMILIES},
            )
        )
    cases.append(
        Case(
            "10_mixed_all_capped",
            "all_min20_or_available_each",
            {
                family: min(20, COUNT_LIMITS.get(family, 20))
                for family in SUPPORTED_FAMILIES
            },
        )
    )
    cases.append(
        Case(
            "11_display_control_prefix_probe",
            "display_with_switch_pothg_3x_each",
            {"7SEG-COM-AN-RED": 3, "7SEG-COM-CAT-BLUE": 3, "SWITCH": 3, "POT-HG": 3},
        )
    )
    return cases


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    donor_cdb = read_internal_file(DONOR, "ROOT.CDB")
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(_cases(), start=1):
        case_id = f"V2C{index:04d}_{_case_slug(case.name)}"
        folder = OUT_DIR / case.folder
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / f"{case_id}.pdsprj"
        payload = _payload(case.components)
        _write_json(folder / f"{case_id}.input.json", payload)
        row: dict[str, Any] = {
            "case_id": case_id,
            "kind": case.folder,
            "name": case.name,
            "components": case.components,
            "output": str(output.relative_to(ROOT)),
        }
        try:
            result = generate_component_placement_project(payload, output, full_cdb=True)
            output_cdb = read_internal_file(output, "ROOT.CDB")
            generated_report = result.validation_reports.get(
                "generated_output_validator",
                {},
            )
            row.update(
                {
                    "status": "ok" if result.valid else "invalid",
                    "valid": result.valid,
                    "root_cdb_preserved": output_cdb == donor_cdb,
                    "request": result.request,
                    "errors": [item.as_dict() for item in result.errors],
                    "warnings": [item.as_dict() for item in result.warnings],
                    "generated_output_validator": generated_report,
                }
            )
        except Exception as exc:  # pragma: no cover - experiment report path
            row.update({"status": "failed", "error": str(exc)})
        rows.append(row)

    _write_json(OUT_DIR / "manifest.json", rows)
    ok = sum(1 for row in rows if row["status"] == "ok")
    invalid = sum(1 for row in rows if row["status"] == "invalid")
    failed = sum(1 for row in rows if row["status"] == "failed")
    readme_lines = [
        "# Locked mega no-terminal matrix V2 - 2026-07-08",
        "",
        "Component placer only. No terminal placer was run.",
        "",
        f"Locked donor: `{NEW_COMPONENT_MEGA_DONOR.as_posix()}`",
        "",
        "ROOT.CDB policy: full donor ROOT.CDB is preserved byte-for-byte.",
        "",
        "This V2 pack focuses on the user-reported display bad-object and mixed-layout overlap cases:",
        "",
        "- common-anode output filenames now use `7SEG-COM-AN-RED` terminology;",
        "- display DSN final rows use the Proteus-saved `00 FF` tail;",
        "- display-containing mixed designs keep the display-compatible `00 00` object chunk prefix;",
        "- display rows start after actual previous layout bboxes, not after a count-derived slot;",
        "- visual layout margins are deliberately larger than the true parsed bboxes;",
        "- multipart A/B/C native packets are spread by parsed-coordinate subpart clusters.",
        "",
        f"Rows: {len(rows)}",
        f"Generated OK: {ok}",
        f"Invalid generated outputs: {invalid}",
        f"Failed during generation: {failed}",
        "",
        "## Results",
        "",
        "| Case | Kind | Name | Status | CDB preserved | Output/Error |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        detail = row.get("output") if row["status"] != "failed" else row.get("error", "")
        readme_lines.append(
            "| `{case_id}` | `{kind}` | `{name}` | `{status}` | `{cdb}` | {detail} |".format(
                case_id=row["case_id"],
                kind=row["kind"],
                name=row["name"],
                status=row["status"],
                cdb=row.get("root_cdb_preserved", "n/a"),
                detail=detail,
            )
        )
    (OUT_DIR / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    archive_path = Path(shutil.make_archive(str(ARCHIVE), "zip", OUT_DIR.parent, OUT_DIR.name))
    print(OUT_DIR.relative_to(ROOT))
    print(archive_path.relative_to(ROOT))
    print(f"ok={ok} invalid={invalid} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
