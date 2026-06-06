from __future__ import annotations

import json
from pathlib import Path

from proteusgen.pdsprj import inspect_pdsprj, read_internal_file
from proteusgen.source_driven import (
    GENERATOR_TARGET,
    SCHEMA_VERSION,
    generate_source_driven_project_from_payload,
    validate_source_driven_payload,
)


def payload(kind: str = "dc_voltage") -> dict:
    if kind == "ac_voltage":
        positive, negative, ref, value = "AV", "A0", "V1", "VSINE"
    elif kind == "dc_current":
        positive, negative, ref, value = "DI", "I0", "I1", "1A"
    else:
        positive, negative, ref, value = "DV", "D0", "V1", "10V"
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_target": GENERATOR_TARGET,
        "project": {
            "name": "SOURCE_TEST",
            "output_basename": "SOURCE_TEST",
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
        "groups": [{"mode": "RCL", "start": positive, "end": negative}],
        "sources": [
            {
                "kind": kind,
                "ref": ref,
                "value": value,
                "positive": positive,
                "negative": negative,
            }
        ],
        "component_values": {"R1": "10k", "C1": "1uF", "L1": "5mH"},
    }


def test_source_validation_rejects_ac_current() -> None:
    case = payload()
    case["sources"][0]["kind"] = "ac_current"
    report = validate_source_driven_payload(case)
    assert not report.valid
    assert "AC current" in " ".join(report.errors)


def test_source_validation_requires_source_nets_in_groups() -> None:
    case = payload()
    case["groups"] = [{"mode": "R", "start": "N1", "end": "N2"}]
    report = validate_source_driven_payload(case)
    assert not report.valid
    assert "positive net" in " ".join(report.errors)


def test_generate_dc_voltage_source_project(tmp_path: Path) -> None:
    result = generate_source_driven_project_from_payload(payload(), tmp_path)
    info = inspect_pdsprj(result.output_path)
    assert info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails
    chunk = result.chunk_path.read_bytes()
    assert b"VSOURCE" in chunk
    assert b"$TERPOWER" not in chunk
    assert b"$TERGROUND" not in chunk
    assert result.manifest["static_validation_issues"] == []


def test_generate_dc_current_source_project(tmp_path: Path) -> None:
    result = generate_source_driven_project_from_payload(payload("dc_current"), tmp_path)
    assert b"CSOURCE" in result.chunk_path.read_bytes()
    assert result.manifest["static_validation_issues"] == []


def test_generate_ac_voltage_source_project(tmp_path: Path) -> None:
    result = generate_source_driven_project_from_payload(payload("ac_voltage"), tmp_path)
    chunk = result.chunk_path.read_bytes()
    assert b"VSINE" in chunk
    assert b"\x02AV" in chunk and b"\x02A0" in chunk
    assert result.manifest["static_validation_issues"] == []
    assert b"VSINE" in read_internal_file(result.output_path, "ROOT.CDB")


def test_source_example_is_valid() -> None:
    example = Path(__file__).parents[1] / "examples" / "source_driven_default_dcv.json"
    report = validate_source_driven_payload(json.loads(example.read_text(encoding="utf-8")))
    assert report.valid
