from pathlib import Path
import json
import sqlite3
import subprocess

import pytest

from Easyeda.catalogue import CATALOGUE
from Easyeda.donor_source import EasyedaDonorSource
from Easyeda.pipeline import generate_project


SOURCE = Path("/home/zaruka/.local/opt/easyeda-pro")
EXAMPLE = Path(__file__).parents[1] / "examples" / "regulated_5v_supply.json"
ALL_40 = Path(__file__).parents[1] / "examples" / "all_40_components.json"


pytestmark = pytest.mark.skipif(not SOURCE.exists(), reason="Installed EasyEDA donor source is unavailable.")


def test_all_catalogue_entries_resolve_to_source_payloads() -> None:
    source = EasyedaDonorSource(SOURCE)
    packets = [source.resolve(entry) for entry in CATALOGUE.values()]
    assert len(packets) == 59
    assert all(packet.device and packet.symbol and packet.pins for packet in packets)
    assert all(packet.footprint is not None for packet in packets if packet.kind not in {"GND", "VCC"})


def test_regulated_supply_generates_valid_schematic_and_pcb(tmp_path: Path) -> None:
    result = generate_project(EXAMPLE, source_pack=SOURCE, output_root=tmp_path)
    assert result["passed"] is True
    assert result["pcb_ready"] is True
    project = Path(result["project_path"])
    assert project.suffix == ".eprj"
    assert project.is_file()
    assert project.stat().st_size < 20_000_000
    report = json.loads(Path(result["validation_report"]).read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["errors"] == []
    with sqlite3.connect(project) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT count(*) FROM documents WHERE docType = 1").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM documents WHERE docType = 3").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM components").fetchone()[0] < 30
        project_uuid, branch_uuid = connection.execute(
            "SELECT uuid, branch_uuid FROM projects"
        ).fetchone()
        assert branch_uuid
        assert connection.execute(
            "SELECT DISTINCT project_uuid FROM project_members"
        ).fetchall() == [(project_uuid,)]
        assert connection.execute("SELECT count(*) FROM coppers").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM texts").fetchone() == (0,)


def test_terminal_mode_uses_native_ports_and_validates(tmp_path: Path) -> None:
    result = generate_project(
        EXAMPLE,
        source_pack=SOURCE,
        output_root=tmp_path,
        routing_mode="terminal",
    )
    assert result["passed"] is True
    assert result["terminal_net_count"] == result["net_count"]
    routing = json.loads((Path(result["run_directory"]) / "routing.json").read_text(encoding="utf-8"))
    assert all(net["terminalized"] for net in routing["nets"])


def test_combination_mode_routes_power_to_one_shared_terminal_per_net(
    tmp_path: Path,
) -> None:
    result = generate_project(EXAMPLE, source_pack=SOURCE, output_root=tmp_path)
    assert result["passed"] is True
    routing = json.loads(
        (Path(result["run_directory"]) / "routing.json").read_text(encoding="utf-8")
    )
    power_nets = {
        net["name"]: net
        for net in routing["nets"]
        if net["name"] in {"GND", "+5V"}
    }
    assert set(power_nets) == {"GND", "+5V"}
    assert all(net["reason"] == "shared_power_terminal" for net in power_nets.values())
    assert all(net["segments"] for net in power_nets.values())
    manifest = json.loads(
        (Path(result["run_directory"]) / "donor_manifest.json").read_text(encoding="utf-8")
    )
    terminal_instances = manifest["terminal_instances"]
    assert [terminal["net"] for terminal in terminal_instances] == ["GND", "+5V"]


def test_strict_wire_mode_physically_routes_every_net(tmp_path: Path) -> None:
    result = generate_project(
        EXAMPLE,
        source_pack=SOURCE,
        output_root=tmp_path,
        routing_mode="wire",
    )
    assert result["passed"] is True
    assert result["terminal_net_count"] == 0
    assert result["wire_net_count"] == result["net_count"]


def test_all_40_source_symbols_generate_in_one_project(tmp_path: Path) -> None:
    result = generate_project(ALL_40, source_pack=SOURCE, output_root=tmp_path)
    assert result["passed"] is True
    assert result["component_count"] == 40
    assert result["pcb_ready"] is False
    assert result["pcb_reason"] == "basic_pcb_component_limit_32"


def test_executable_ndjson_reports_real_pipeline_stages(tmp_path: Path) -> None:
    process = subprocess.run(
        [
            str(Path(__file__).parents[1] / "dist" / "progen-easyeda"),
            "run",
            str(EXAMPLE),
            "--output-root",
            str(tmp_path),
            "--events",
            "ndjson",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=90,
    )
    assert process.returncode == 0, process.stderr
    events = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    stages = [event["stage"] for event in events if event.get("event") == "stage"]
    assert stages == [
        "fix_and_validate_input",
        "normalize_values",
        "resolve_donor_catalogue",
        "place_components",
        "route_schematic",
        "write_native_eprj",
        "validate_native_eprj",
        "package_artifacts",
    ]
    assert events[-1]["event"] == "complete"
    assert events[-1]["summary"]["passed"] is True


def test_rtc_logger_native_terminal_stays_within_compact_bounds(tmp_path: Path) -> None:
    source = (
        Path(__file__).parents[1]
        / "qualification"
        / "corpora"
        / "2026_07_17_full_pin_300_v1"
        / "q21_rtc_logger_module_automation_v08.json"
    )
    result = generate_project(source, source_pack=SOURCE, output_root=tmp_path)

    assert result["passed"] is True
    report = json.loads(
        Path(result["validation_report"]).read_text(encoding="utf-8")
    )
    assert report["checks"]["geometry_errors"] == []
