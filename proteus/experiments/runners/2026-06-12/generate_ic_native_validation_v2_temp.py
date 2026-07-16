"""Generate the registry-driven native IC/display validation pack.

This pack is intentionally broad but conservative:

- every unique donor in the native registry is exact-rezipped as a control;
- every supported component with a single donor is generated into E001;
- every known manual pair donor is generated as a pair control;
- unsupported compositions are checked as blocked negative controls.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "proteus" / "active" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.ic_native import (  # noqa: E402
    IcNativeGenerationBlocked,
    NativeRegistry,
    generate_ic_native_project_from_payload,
)

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_native_validation_v2_temp_2026_06_12"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "IC_NATIVE_VALIDATION_V2_TEMP_2026_06_12.zip"


def _safe(text: str) -> str:
    out = "".join(ch if ch.isalnum() else "_" for ch in text)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")[:80] or "case"


def _rel(path: Path) -> str:
    registry = NativeRegistry.load()
    try:
        return path.relative_to(registry.root).as_posix()
    except ValueError:
        return path.relative_to(REPO).as_posix()


def exact_donor_cases(registry: NativeRegistry) -> list[dict[str, object]]:
    seen: set[Path] = set()
    cases: list[dict[str, object]] = []
    for component in registry.components.values():
        for kind, donor in component.donors.items():
            if donor in seen:
                continue
            seen.add(donor)
            cases.append(
                {
                    "phase": "exact_donor_control",
                    "payload": {
                        "schema": "ic-native-circuit-ir/v0.1",
                        "case_id": f"E{len(cases):03d}_{_safe(component.key)}_{_safe(kind)}_EXACT",
                        "title": f"Exact donor control: {component.key} {kind}",
                        "donor": _rel(donor),
                        "exact_rezip": True,
                    },
                }
            )
    for pair, donor in sorted(registry.pair_donors.items()):
        if donor in seen:
            continue
        seen.add(donor)
        cases.append(
            {
                "phase": "exact_pair_donor_control",
                "payload": {
                    "schema": "ic-native-circuit-ir/v0.1",
                    "case_id": f"E{len(cases):03d}_{_safe(pair[0])}_{_safe(pair[1])}_PAIR_EXACT",
                    "title": f"Exact pair donor control: {pair[0]} + {pair[1]}",
                    "donor": _rel(donor),
                    "exact_rezip": True,
                },
            }
        )
    return cases


def solo_generation_cases(registry: NativeRegistry) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for index, component in enumerate(registry.components.values()):
        if "single" not in component.donors:
            continue
        cases.append(
            {
                "phase": "solo_generated_into_e001",
                "payload": {
                    "schema": "ic-native-circuit-ir/v0.1",
                    "case_id": f"S{index:03d}_{_safe(component.key)}_SINGLE_NATIVE",
                    "title": f"Generated native single: {component.key}",
                    "components": [{"ref": "U1" if not component.key.startswith("7SEG") else "D1", "part": component.key}],
                },
            }
        )
    return cases


def pair_generation_cases(registry: NativeRegistry) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for index, (pair, _donor) in enumerate(sorted(registry.pair_donors.items())):
        cases.append(
            {
                "phase": "manual_pair_generated_into_e001",
                "payload": {
                    "schema": "ic-native-circuit-ir/v0.1",
                    "case_id": f"P{index:03d}_{_safe(pair[0])}_{_safe(pair[1])}_PAIR_NATIVE",
                    "title": f"Generated manual pair control: {pair[0]} + {pair[1]}",
                    "components": [{"ref": "U1", "part": pair[0]}, {"ref": "U2", "part": pair[1]}],
                },
            }
        )
    return cases


def blocked_negative_cases() -> list[dict[str, object]]:
    return [
        {
            "phase": "blocked_negative_control",
            "expect_blocked": True,
            "payload": {
                "schema": "ic-native-circuit-ir/v0.1",
                "case_id": "B000_UNSUPPORTED_74HC153",
                "components": [{"ref": "U1", "part": "74HC153"}],
            },
        },
        {
            "phase": "blocked_negative_control",
            "expect_blocked": True,
            "payload": {
                "schema": "ic-native-circuit-ir/v0.1",
                "case_id": "B001_UNSUPPORTED_CROSS_DONOR_TRIPLE",
                "components": [
                    {"ref": "U1", "part": "74HC160"},
                    {"ref": "U2", "part": "74HC165"},
                    {"ref": "U3", "part": "LM741"},
                ],
            },
        },
        {
            "phase": "blocked_negative_control",
            "expect_blocked": True,
            "payload": {
                "schema": "ic-native-circuit-ir/v0.1",
                "case_id": "B002_NO_TERMINAL_PAIR_WITH_EXPLICIT_CONNECTION",
                "components": [
                    {"ref": "U1", "part": "74HC90", "connections": {"CLK": "CLK0"}},
                    {"ref": "U2", "part": "4017"},
                ],
            },
        },
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
    registry = NativeRegistry.load()
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    case_specs = (
        exact_donor_cases(registry)
        + solo_generation_cases(registry)
        + pair_generation_cases(registry)
        + blocked_negative_cases()
    )
    manifests: list[dict[str, object]] = []
    unexpected_blocks: list[dict[str, object]] = []
    unexpected_successes: list[dict[str, object]] = []
    for spec in case_specs:
        payload = dict(spec["payload"])  # shallow copy is enough here
        case_dir = OUT_ROOT / str(payload["case_id"])
        expect_blocked = bool(spec.get("expect_blocked"))
        try:
            result = generate_ic_native_project_from_payload(payload, case_dir)
            manifest = {"phase": spec["phase"], **result.manifest}
            manifests.append(manifest)
            if expect_blocked:
                unexpected_successes.append(manifest)
        except IcNativeGenerationBlocked as exc:
            blocked = {
                "phase": spec["phase"],
                "case_id": payload["case_id"],
                "blocked": True,
                "expected_blocked": expect_blocked,
                "report": exc.report.as_dict(),
            }
            manifests.append(blocked)
            if not expect_blocked:
                unexpected_blocks.append(blocked)

    static_issue_cases = {
        str(item["case_id"]): item.get("static_validation_issues", [])
        for item in manifests
        if item.get("static_validation_issues")
    }
    marker_warning_cases = {
        str(item["case_id"]): item.get("marker_expectation_warnings", [])
        for item in manifests
        if item.get("marker_expectation_warnings")
    }
    phase_counts: dict[str, int] = {}
    for item in manifests:
        phase_counts[str(item["phase"])] = phase_counts.get(str(item["phase"]), 0) + 1

    summary = {
        "pack": "IC_NATIVE_VALIDATION_V2_TEMP_2026_06_12",
        "case_count": len(case_specs),
        "phase_counts": phase_counts,
        "unexpected_blocks": unexpected_blocks,
        "unexpected_successes": unexpected_successes,
        "static_issue_cases": static_issue_cases,
        "marker_warning_cases": marker_warning_cases,
        "archive": write_archive(),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "case_inputs.json").write_text(json.dumps(case_specs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not unexpected_blocks and not unexpected_successes and not static_issue_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
