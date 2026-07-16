"""Deterministic donor-native placement and mix fixture matrix.

The matrix is deliberately generated from the shared CircuitIR shape rather
than handcrafted ASC snippets.  It makes the evidence order explicit: each
stock family is exercised at 1/2/3/5/10/20 target instances, then the caller
can emit bounded mixed cases.  It is a development/evidence producer, not a
second user circuit format and not a claim that every fixture has already had
its own GUI screenshot review.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Iterable


PLACEMENT_PROGRESSION = (1, 2, 3, 5, 10, 20)
FAMILY_IDS = (
    "RESISTOR",
    "CAPACITOR",
    "INDUCTOR",
    "VOLTAGE_SOURCE",
    "CURRENT_SOURCE",
    "SIGNAL_SOURCE",
)
MATRIX_SCHEMA = "progen-ltspice-donor-native-fixture-matrix/v1"


def _expected(nets: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "schema": "progeneda-expected-netlist/v1",
        "source": "donor_native_fixture_matrix",
        "nets": [
            {"name": name, "members": list(members), "member_count": len(members)}
            for name, members in nets.items()
        ],
        "important_nets": ["GND"],
    }


def _base(circuit_id: str, components: list[dict[str, Any]], nets: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": circuit_id,
        "project": {"name": circuit_id.lower(), "analysis": [".ac dec 1 1k 10k"]},
        "components": components,
        "nets": nets,
        "expected_netlist": _expected(nets),
        "routing": {"mode": "wire"},
        "generation_notes": {
            "source": "donor_native_fixture_matrix",
            "fixture_only": True,
            "requires_gui_evidence_before_catalogue_promotion": True,
        },
    }


def _passive_fixture(family: str, count: int) -> dict[str, Any]:
    kind = {"RESISTOR": "R", "CAPACITOR": "C", "INDUCTOR": "L"}[family]
    prefix = {"RESISTOR": "R", "CAPACITOR": "C", "INDUCTOR": "L"}[family]
    values = {"RESISTOR": "1k", "CAPACITOR": "1u", "INDUCTOR": "1m"}
    components: list[dict[str, Any]] = [
        {"ref": "V1", "kind": "VDC", "value": "1", "pins": {"1": "N0", "2": "GND"}},
        {"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
    ]
    nets: dict[str, list[str]] = {"GND": ["V1.2", "G1.1"]}
    if family == "CAPACITOR":
        nets["N0"] = ["V1.1"]
        for index in range(1, count + 1):
            ref = f"{prefix}{index}"
            components.append({"ref": ref, "kind": kind, "value": values[family], "pins": {"1": "N0", "2": "GND"}})
            nets["N0"].append(f"{ref}.1")
            nets["GND"].append(f"{ref}.2")
    else:
        nets["N0"] = ["V1.1"]
        for index in range(1, count + 1):
            ref = f"{prefix}{index}"
            left = f"N{index - 1}"
            right = "GND" if index == count else f"N{index}"
            components.append({"ref": ref, "kind": kind, "value": values[family], "pins": {"1": left, "2": right}})
            nets.setdefault(left, []).append(f"{ref}.1")
            nets.setdefault(right, []).append(f"{ref}.2")
    return _base(f"NATIVE_{family}_{count}", components, nets)


def _source_fixture(family: str, count: int) -> dict[str, Any]:
    source_kind = {
        "VOLTAGE_SOURCE": "VDC",
        "CURRENT_SOURCE": "IDC",
        "SIGNAL_SOURCE": "MISC_SIGNAL",
    }[family]
    components: list[dict[str, Any]] = [{"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}}]
    nets: dict[str, list[str]] = {"GND": ["G1.1"]}
    for index in range(1, count + 1):
        node = f"N{index}"
        source: dict[str, Any] = {"ref": f"V{index}" if family != "CURRENT_SOURCE" else f"I{index}", "kind": source_kind, "pins": {"1": node, "2": "GND"}}
        if family == "VOLTAGE_SOURCE":
            source["value"] = "1"
        elif family == "CURRENT_SOURCE":
            source["value"] = "1m"
        else:
            source["parameters"] = {"ac": "1"}
        source_ref = str(source["ref"])
        load = {"ref": f"R{index}", "kind": "R", "value": "1k", "pins": {"1": node, "2": "GND"}}
        components.extend((source, load))
        nets[node] = [f"{source_ref}.1", f"R{index}.1"]
        nets["GND"].extend((f"{source_ref}.2", f"R{index}.2"))
    return _base(f"NATIVE_{family}_{count}", components, nets)


def build_family_fixture(family: str, count: int) -> dict[str, Any]:
    """Build one physical-wire CircuitIR case for a donor-observed family."""

    normalized = str(family).strip().upper()
    if normalized not in FAMILY_IDS:
        raise ValueError(f"Unknown donor-native fixture family {family!r}.")
    if count not in PLACEMENT_PROGRESSION:
        raise ValueError(f"Fixture count {count} is outside the required progression {PLACEMENT_PROGRESSION!r}.")
    fixture = _passive_fixture(normalized, count) if normalized in {"RESISTOR", "CAPACITOR", "INDUCTOR"} else _source_fixture(normalized, count)
    if len(fixture["components"]) > 43:
        raise AssertionError("A fixture exceeded the donor-native 43-component development cap.")
    return fixture


def build_progression_matrix(
    families: Iterable[str] = FAMILY_IDS,
    counts: Iterable[int] = PLACEMENT_PROGRESSION,
) -> dict[str, dict[str, Any]]:
    """Return the full bounded family placement matrix keyed by circuit id."""

    requested_counts = tuple(int(count) for count in counts)
    if requested_counts != PLACEMENT_PROGRESSION:
        raise ValueError(f"The donor-native matrix must retain the full progression {PLACEMENT_PROGRESSION!r}.")
    fixtures: dict[str, dict[str, Any]] = {}
    for family in families:
        for count in requested_counts:
            fixture = build_family_fixture(family, count)
            fixtures[str(fixture["circuit_id"])] = fixture
    return fixtures


def write_progression_matrix(directory: str | Path) -> list[Path]:
    """Write shared-JSON fixture sources for later generator/GUI evidence runs."""

    target = Path(directory)
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"Fixture output directory must be empty to preserve evidence: {target}")
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for circuit_id, fixture in build_progression_matrix().items():
        path = target / f"{circuit_id.lower()}.json"
        path.write_text(json.dumps(deepcopy(fixture), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the donor-native 1/2/3/5/10/20 shared-JSON fixture matrix.")
    parser.add_argument("output", type=Path, help="Empty or new directory for the 36 canonical JSON fixture sources.")
    args = parser.parse_args()
    written = write_progression_matrix(args.output)
    print(
        json.dumps(
            {
                "schema": MATRIX_SCHEMA,
                "output": str(args.output.resolve()),
                "fixture_count": len(written),
                "progression": list(PLACEMENT_PROGRESSION),
                "families": list(FAMILY_IDS),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":  # pragma: no cover
    main()
