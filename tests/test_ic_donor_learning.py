import hashlib
import json
from pathlib import Path

from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk
from proteusgen.templates import repository_root


def chunk_for(path: Path) -> bytes:
    return _extract_object_chunk(read_internal_file(path, "ROOT.DSN"))


def test_hc08_all4_donor_uses_ordinary_io_terminals() -> None:
    donor = repository_root() / "proteus_ic" / "donors" / "74hc08" / "IC_HC08_M01_ALL4_IO.pdsprj"
    chunk = chunk_for(donor)
    assert chunk.count(b"74HC08") == 12
    assert chunk.count(b"$TERINPUT") == 8
    assert chunk.count(b"$TEROUTPUT") == 4
    assert chunk.count(b"$TERBIDIR") == 0
    assert chunk.count(b"WIRE") == 12


def test_hc08_two_package_donor_has_two_package_rows() -> None:
    donor = repository_root() / "proteus_ic" / "donors" / "74hc08" / "IC_HC08_M02_TWO_PACKAGES_IO.pdsprj"
    cdb = read_internal_file(donor, "ROOT.CDB")
    assert b"U1:A" in cdb
    assert b"U2:A" in cdb
    assert cdb.count(b"74HC08") == 4


def test_hc32_all4_donor_is_real_hc32() -> None:
    donor = repository_root() / "proteus_ic" / "donors" / "74hc32" / "IC_HC32_M02_ALL4_IO.pdsprj"
    chunk = chunk_for(donor)
    cdb = read_internal_file(donor, "ROOT.CDB")
    assert chunk.count(b"74HC32") == 12
    assert chunk.count(b"74HC08") == 0
    assert cdb.count(b"74HC32") == 2
    assert b"{MODFILE=74OR2.MDF}" in cdb


def test_hc32_single_gate_file_is_rejected_as_hc32_evidence() -> None:
    donor = repository_root() / "proteus_ic" / "donors" / "74hc32" / "IC_HC32_M01_ONE_GATE_IO.pdsprj"
    chunk = chunk_for(donor)
    cdb = read_internal_file(donor, "ROOT.CDB")
    assert chunk.count(b"74HC32") == 0
    assert chunk.count(b"74HC08") == 3
    assert b"{MODFILE=74AND2.MDF}" in cdb


def test_rcl_load_donor_is_diagnostic_only_due_to_bidir_terminals() -> None:
    donor = repository_root() / "proteus_ic" / "donors" / "74hc08" / "IC_HC08_M04_RCL_LOAD.pdsprj"
    chunk = chunk_for(donor)
    assert chunk.count(b"74HC08") == 3
    assert chunk.count(b"$TERBIDIR") == 7
    assert chunk.count(b"$TERINPUT") == 2
    assert chunk.count(b"$TEROUTPUT") == 1


def test_ic_v1_generated_pack_manifests_are_static_clean() -> None:
    root = repository_root() / "experiments" / "ic_hc08_hc32_v1_temp_2026_06_07"
    summary = json.loads((root / "summary_manifest.json").read_text(encoding="utf-8"))
    assert summary["do_not_promote"] is True
    assert len(summary["cases"]) == 11
    assert summary["known_donor_findings"]["hc08_m04"].startswith("Diagnostic only")
    for case in summary["cases"]:
        assert case["static_validation_issues"] == []
    assert summary["cases"][8]["case_id"] == "T08_HC08_M04_RCL_LOAD_DIAGNOSTIC_E001_TRANSPLANT"
    assert summary["cases"][8]["allow_bidir"] is True


def test_ic_v1_archive_hash_is_deterministic() -> None:
    root = repository_root()
    archive = root / "experiments" / "IC_HC08_HC32_V1_TEMP_2026_06_07.zip"
    summary = json.loads(
        (root / "experiments" / "ic_hc08_hc32_v1_temp_2026_06_07" / "summary_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert digest == summary["archive_sha256"]
    assert digest == "03b3d62a5e744cfe51e82460463c9f2db3ac9b04eb43850cb3060c7745e82d6f"
