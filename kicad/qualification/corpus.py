"""Build the locked 400-circuit KiCad qualification corpus.

The corpus deliberately reuses the deterministic connected blocks owned by the
canonical KiCad compiler.  Forty distinct electrical archetypes are composed
from those blocks and each is emitted in ten named deployment/layout profiles.
No component pin or expected-net member is edited after compilation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from kicad.pipeline.final_circuit_builder import (
    _build_raw_proteus_alias_mixed_specs,
    _build_raw_proteus_alias_routed_specs,
    _build_raw_test_specs,
    _prefixed_raw_block,
    _raw_spec,
    compile_raw_circuit,
    validate_final_circuit,
)


CORPUS_SCHEMA = "progen-kicad-common-circuit-corpus/v1"


@dataclass(frozen=True)
class Archetype:
    slug: str
    title: str
    purpose: str
    blocks: tuple[str, ...]
    category: str


@dataclass(frozen=True)
class ApplicationProfile:
    slug: str
    title: str
    purpose: str
    layout_profile: str


APPLICATION_PROFILES = (
    ApplicationProfile("education", "Education Bench", "teaching, probing, and laboratory measurement", "square_loose"),
    ApplicationProfile("prototype", "Prototype", "rapid firmware and hardware prototyping", "square_compact"),
    ApplicationProfile("field", "Field Service", "field wiring, diagnosis, and service access", "loose_channels"),
    ApplicationProfile("compact", "Compact Embedded", "compact integration inside an embedded product", "square_compact"),
    ApplicationProfile("diagnostic", "Diagnostic Fixture", "diagnostic access and repeatable fault isolation", "wide_bus"),
    ApplicationProfile("industrial", "Industrial Control", "industrial control and cabinet integration", "tall_bus"),
    ApplicationProfile("instrument", "Bench Instrument", "laboratory instrumentation and measurement", "square_loose"),
    ApplicationProfile("automation", "Automation Node", "automation, telemetry, and remote control", "wide_bus"),
    ApplicationProfile("development", "Development Platform", "firmware development and peripheral expansion", "loose_channels"),
    ApplicationProfile("validation", "Production Validation", "manufacturing test and production validation", "tall_bus"),
)


ARCHETYPES = (
    Archetype("arduino_led_button_controller", "Arduino LED and Button Controller", "A compact Arduino Nano human-interface and GPIO controller.", ("T01",), "embedded"),
    Archetype("regulated_5v_linear_supply", "Regulated 5V Linear Supply", "A protected LM7805 supply with filtering, indication, and field connections.", ("T02",), "power"),
    Archetype("esp32_usb_uart_board", "ESP32 USB-UART Development Board", "An ESP32 controller with CP2102 programming, reset, boot, and expansion support.", ("T03",), "embedded"),
    Archetype("motor_relay_driver", "MOSFET and Relay Motor Driver", "Repeated MOSFET, transistor, relay, flyback, and load-interface channels.", ("T04",), "control"),
    Archetype("i2c_spi_sensor_hub", "I2C and SPI Sensor Hub", "A sensor, display, RTC, flash, and connector hub for embedded data acquisition.", ("T05",), "sensing"),
    Archetype("can_rs485_interface", "CAN and RS485 Communications Interface", "Protected CAN and RS485 physical interfaces with termination and headers.", ("T06",), "communications"),
    Archetype("stereo_audio_controller", "Stereo Audio Control Amplifier", "A PAM8403 audio output and LM358 analog-control signal chain.", ("T07",), "analog"),
    Archetype("shift_register_led_display", "Shift Register LED Display", "Cascaded 74HC595 logic, switch inputs, resistor networks, and LED outputs.", ("T08",), "digital"),
    Archetype("maker_controller", "Integrated Maker Controller", "A multi-peripheral Arduino and ESP32 controller for sensors, storage, and loads.", ("T09",), "embedded"),
    Archetype("arduino_field_motion_controller", "Arduino Field Motion Controller", "An Arduino operator interface with CAN, RS485, MOSFET, relay, and motor channels.", ("T01", "T04", "T06"), "automation"),
    Archetype("analog_power_lab", "Analog and Power Electronics Lab", "Sources, regulators, rectification, op-amps, timer, passives, and protection for analog laboratories.", ("M01",), "analog"),
    Archetype("logic_display_lab", "Digital Logic and Display Lab", "Common 74HC and CMOS logic with counters, decoders, and seven-segment displays.", ("M02",), "digital"),
    Archetype("mixed_embedded_lab", "Mixed Embedded Electronics Lab", "Embedded controllers combined with analog, logic, source, and protection families.", ("M03",), "education"),
    Archetype("adjustable_power_driver", "Adjustable Power and Load Driver", "An LM317 supply with protected switching and discrete MOSFET load control.", ("R01",), "power"),
    Archetype("counter_display_chain", "Counter and Seven-Segment Display Chain", "A wire-heavy clock, counter, decoder, and display signal chain.", ("R02",), "digital"),
    Archetype("rs485_sensor_node", "RS485 Embedded Sensor Node", "An Arduino and ESP32 sensor node with RS485, flash, display, and protection.", ("R03",), "communications"),
    Archetype("arduino_control_power_board", "Arduino Control and 5V Power Board", "A regulated Arduino control board with local buttons, indicators, and expansion.", ("T01", "T02"), "embedded"),
    Archetype("esp32_environment_station", "ESP32 Environmental Station", "An ESP32 programming core paired with a complete I2C and SPI sensor hub.", ("T03", "T05"), "sensing"),
    Archetype("esp32_industrial_gateway", "ESP32 Industrial Communications Gateway", "An ESP32 USB-programmable core with CAN and RS485 field interfaces.", ("T03", "T06"), "communications"),
    Archetype("remote_motor_controller", "Remote Motor and Relay Controller", "A CAN and RS485 connected multi-channel motor and relay controller.", ("T04", "T06"), "control"),
    Archetype("sensor_logic_display", "Sensor Hub with Logic Display", "I2C and SPI sensing with shift-register status and operator display outputs.", ("T05", "T08"), "sensing"),
    Archetype("communications_status_panel", "Communications Status Panel", "CAN and RS485 interfaces with a shift-register LED diagnostic panel.", ("T06", "T08"), "communications"),
    Archetype("arduino_audio_console", "Arduino Audio Control Console", "Arduino controls, user inputs, analog conditioning, and stereo amplification.", ("T01", "T07"), "analog"),
    Archetype("arduino_logic_trainer", "Arduino Digital Logic Trainer", "Arduino user controls combined with cascaded shift-register logic and displays.", ("T01", "T08"), "education"),
    Archetype("dual_regulator_power_bench", "Dual Regulator Power Bench", "Fixed and adjustable protected regulator sections with load-driver test access.", ("T02", "R01"), "power"),
    Archetype("arduino_counter_trainer", "Arduino Counter and Display Trainer", "Arduino controls driving a clocked counter, decoder, and display chain.", ("T01", "R02"), "education"),
    Archetype("networked_sensor_node", "Networked Sensor and Storage Node", "An RS485 embedded controller paired with RTC, display, and nonvolatile sensor storage.", ("T05", "R03"), "sensing"),
    Archetype("analog_power_workstation", "Analog Power Electronics Workstation", "A broad analog source and measurement board with an adjustable power-driver section.", ("M01", "R01"), "analog"),
    Archetype("digital_systems_trainer", "Digital Systems Trainer", "A broad logic-family trainer with a routed counter and seven-segment chain.", ("M02", "R02"), "education"),
    Archetype("wireless_mixed_signal_controller", "Wireless Mixed-Signal Controller", "An ESP32 USB core combined with mixed analog, protection, and logic functions.", ("M03", "T03"), "embedded"),
    Archetype("powered_maker_platform", "Powered Maker Development Platform", "An integrated maker controller with its own protected regulated supply.", ("T02", "T09"), "embedded"),
    Archetype("maker_field_gateway", "Maker CAN and RS485 Field Gateway", "An integrated maker controller with dual industrial communications interfaces.", ("T06", "T09"), "communications"),
    Archetype("maker_audio_instrument", "Maker Audio Instrument", "An integrated controller with analog audio processing and stereo power output.", ("T07", "T09"), "analog"),
    Archetype("maker_logic_console", "Maker Logic and Display Console", "An integrated controller with expanded digital logic and LED display channels.", ("T08", "T09"), "digital"),
    Archetype("esp32_sensor_actuator_controller", "ESP32 Sensor and Actuator Controller", "A complete ESP32 sensing, storage, motor, and relay control system.", ("T03", "T04", "T05"), "automation"),
    Archetype("regulated_multichannel_driver", "Regulated Multi-Channel Load Driver", "Fixed and adjustable supplies feeding repeated MOSFET and relay output channels.", ("T02", "T04", "R01"), "control"),
    Archetype("industrial_sensor_gateway", "Industrial Sensor Communications Gateway", "Sensor, storage, CAN, RS485, and protected embedded-control functions.", ("T05", "T06", "R03"), "communications"),
    Archetype("mixed_signal_teaching_console", "Mixed-Signal Teaching Console", "Arduino controls, analog audio, and a routed digital counter/display experiment.", ("T01", "T07", "R02"), "education"),
    Archetype("iot_sensor_display_controller", "IoT Sensor and Display Controller", "An ESP32 sensor hub with storage and expanded shift-register status displays.", ("T03", "T05", "T08"), "sensing"),
    Archetype("industrial_power_motion_controller", "Industrial Power and Motion Controller", "Regulated power, field communications, and repeated motor and relay outputs.", ("T02", "T04", "T06"), "automation"),
)


def _base_specs() -> dict[str, dict[str, Any]]:
    specs = (
        _build_raw_test_specs()
        + _build_raw_proteus_alias_mixed_specs()
        + _build_raw_proteus_alias_routed_specs()
    )
    return {str(spec["circuit_id"]): spec for spec in specs}


def _compose_raw(
    archetype: Archetype,
    profile: ApplicationProfile,
    *,
    archetype_index: int,
    profile_index: int,
) -> dict[str, Any]:
    bases = _base_specs()
    components: list[dict[str, Any]] = []
    nets: dict[str, list[str]] = defaultdict(list)
    blocks: list[dict[str, Any]] = []
    for block_index, block_id in enumerate(archetype.blocks, 1):
        source = bases[block_id]
        prefixed = _prefixed_raw_block(source, prefix=f"B{block_index}_", block_index=block_index)
        components.extend(prefixed["components"])
        for net, endpoints in prefixed["nets"].items():
            nets[str(net)].extend(str(endpoint) for endpoint in endpoints)
        blocks.append(
            {
                "id": f"B{block_index}",
                "name": str(source["name"]),
                "source_circuit_id": block_id,
                "component_count": len(prefixed["components"]),
                "net_count": len(prefixed["nets"]),
            }
        )
    circuit_id = f"KQ{archetype_index:02d}V{profile_index:02d}"
    raw = _raw_spec(
        circuit_id,
        f"{archetype.title} - {profile.title}",
        f"{archetype.purpose} Configured for {profile.purpose}.",
        components,
        dict(nets),
        blocks=blocks,
    )
    raw.update(
        {
            "source": "locked_kicad_common_400_qualification_corpus",
            "source_format": "canonical_connected_block_composition",
            "routing_mode": "combination",
            "routing_decision_source": "qualification_combination_default",
            "high_fanout_terminal_threshold": 6,
            "arrangement_style": "clustered_blocks_square_fill",
        }
    )
    return raw


def _electrical_fingerprint(circuit: dict[str, Any]) -> str:
    payload = {
        "components": [
            {
                "ref": item.get("ref"),
                "kind": item.get("kind"),
                "value": item.get("value"),
                "role": item.get("role"),
                "block": item.get("block"),
                "pins": item.get("pins"),
            }
            for item in circuit.get("components", [])
        ],
        "nets": circuit.get("nets", {}),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_circuit(
    archetype: Archetype,
    profile: ApplicationProfile,
    *,
    archetype_index: int,
    profile_index: int,
) -> dict[str, Any]:
    circuit = compile_raw_circuit(
        _compose_raw(
            archetype,
            profile,
            archetype_index=archetype_index,
            profile_index=profile_index,
        )
    )
    project_slug = f"kq{archetype_index:02d}_{archetype.slug}_{profile.slug}_v{profile_index:02d}"
    circuit["project"].update(
        {
            "name": project_slug,
            "title": f"{archetype.title} - {profile.title}",
            "purpose": circuit["purpose"],
            "target": "kicad_schematic_and_supported_pcb",
        }
    )
    circuit["qualification"] = {
        "schema": CORPUS_SCHEMA,
        "archetype_index": archetype_index,
        "archetype": archetype.slug,
        "category": archetype.category,
        "profile_index": profile_index,
        "profile": profile.slug,
        "source_blocks": list(archetype.blocks),
        "electrical_archetype_count": len(ARCHETYPES),
        "profiles_per_archetype": len(APPLICATION_PROFILES),
        "routing_mode": "combination",
    }
    circuit["generation_variation"] = {
        "enabled": True,
        "schema": "progen-kicad-generation-variation/v0.1",
        "source_circuit_id": circuit["circuit_id"],
        "variation_index": profile_index,
        "variation_total": len(APPLICATION_PROFILES),
        "profile": profile.layout_profile,
        "application_profile": profile.slug,
        "seed": 20260717 + archetype_index * 100 + profile_index,
        "disable_adaptive_cap": True,
    }
    circuit["validation"] = validate_final_circuit(circuit)
    return circuit


def build_corpus(output: Path) -> dict[str, Any]:
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    final_json = output / "final_json"
    final_json.mkdir()
    records: list[dict[str, Any]] = []
    covered_kinds: set[str] = set()
    fingerprints: dict[str, set[str]] = defaultdict(set)
    component_counts: list[int] = []
    net_counts: list[int] = []
    for archetype_index, archetype in enumerate(ARCHETYPES, 1):
        for profile_index, profile in enumerate(APPLICATION_PROFILES, 1):
            circuit = build_circuit(
                archetype,
                profile,
                archetype_index=archetype_index,
                profile_index=profile_index,
            )
            if circuit["validation"]["status"] != "pass":
                raise RuntimeError(
                    f"{circuit['circuit_id']} failed canonical validation: "
                    + "; ".join(circuit["validation"]["errors"])
                )
            filename = f"{circuit['project']['name']}.json"
            path = final_json / filename
            path.write_text(json.dumps(circuit, indent=2) + "\n", encoding="utf-8")
            kinds = {str(component["kind"]) for component in circuit["components"]}
            covered_kinds.update(kinds)
            fingerprint = _electrical_fingerprint(circuit)
            fingerprints[archetype.slug].add(fingerprint)
            component_counts.append(len(circuit["components"]))
            net_counts.append(len(circuit["nets"]))
            records.append(
                {
                    "circuit_id": circuit["circuit_id"],
                    "circuit_name": circuit["circuit_name"],
                    "archetype": archetype.slug,
                    "profile": profile.slug,
                    "category": archetype.category,
                    "source_blocks": list(archetype.blocks),
                    "component_count": len(circuit["components"]),
                    "net_count": len(circuit["nets"]),
                    "endpoint_count": circuit["validation"]["endpoint_count"],
                    "electrical_fingerprint": fingerprint,
                    "file": str(path.relative_to(output)),
                    "validation_status": circuit["validation"]["status"],
                }
            )

    archetype_counts = Counter(record["archetype"] for record in records)
    profile_counts = Counter(record["profile"] for record in records)
    ids = [record["circuit_id"] for record in records]
    manifest = {
        "schema": CORPUS_SCHEMA,
        "corpus_name": "KiCad 400 Common Circuit Qualification Corpus",
        "circuit_count": len(records),
        "electrical_archetype_count": len(ARCHETYPES),
        "profiles_per_archetype": len(APPLICATION_PROFILES),
        "all_canonical_json_valid": all(record["validation_status"] == "pass" for record in records),
        "all_circuit_ids_unique": len(ids) == len(set(ids)),
        "all_archetypes_have_ten_profiles": all(count == 10 for count in archetype_counts.values()),
        "all_profiles_have_forty_archetypes": all(count == 40 for count in profile_counts.values()),
        "unique_electrical_fingerprint_count": len({record["electrical_fingerprint"] for record in records}),
        "stable_topology_note": "Each archetype keeps one validated electrical topology across ten deployment/layout profiles; profiles do not silently change connectivity.",
        "routing_mode": "combination",
        "component_count": {
            "minimum": min(component_counts),
            "maximum": max(component_counts),
            "total": sum(component_counts),
        },
        "net_count": {
            "minimum": min(net_counts),
            "maximum": max(net_counts),
            "total": sum(net_counts),
        },
        "covered_component_kind_count": len(covered_kinds),
        "covered_component_kinds": sorted(covered_kinds),
        "categories": dict(sorted(Counter(item.category for item in ARCHETYPES).items())),
        "archetypes": [
            {
                "index": index,
                "slug": item.slug,
                "title": item.title,
                "purpose": item.purpose,
                "category": item.category,
                "source_blocks": list(item.blocks),
                "profile_count": archetype_counts[item.slug],
                "electrical_fingerprint_count": len(fingerprints[item.slug]),
            }
            for index, item in enumerate(ARCHETYPES, 1)
        ],
        "profiles": [
            {
                "index": index,
                "slug": item.slug,
                "title": item.title,
                "purpose": item.purpose,
                "layout_profile": item.layout_profile,
            }
            for index, item in enumerate(APPLICATION_PROFILES, 1)
        ],
        "records": records,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# KiCad 400 Common Circuit Qualification Corpus\n\n"
        "This immutable corpus contains 40 distinct connected electrical archetypes in ten named "
        "deployment/layout profiles, for 400 canonical KiCad main-JSON inputs. All component and net "
        "contracts are compiled by `kicad.pipeline.final_circuit_builder`; profile generation never "
        "hand-edits pins or expected-net members.\n\n"
        "The ten profiles intentionally preserve each archetype's electrical topology. They exercise "
        "repeatability, naming, immutable output, placement variation metadata, combination routing, "
        "artifact packaging, and optional PCB acceptance without pretending cosmetic profiles are 400 "
        "independent circuit theories. See `manifest.json` for every name, category, source block, count, "
        "and electrical fingerprint.\n\n"
        "Run the shipping executable qualification with:\n\n"
        "```bash\n"
        "python -m kicad.qualification.runner . --executable /path/to/progen-kicad "
        "--output-root /path/to/evidence --kicad-cli kicad/.local/AppDir/bin/kicad-cli\n"
        "```\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New immutable corpus directory; it must not already exist.")
    args = parser.parse_args()
    manifest = build_corpus(args.output)
    print(json.dumps({key: value for key, value in manifest.items() if key != "records"}, indent=2))
    ok = (
        manifest["circuit_count"] == 400
        and manifest["electrical_archetype_count"] == 40
        and manifest["all_canonical_json_valid"]
        and manifest["all_circuit_ids_unique"]
        and manifest["all_archetypes_have_ten_profiles"]
        and manifest["all_profiles_have_forty_archetypes"]
        and manifest["unique_electrical_fingerprint_count"] == 40
    )
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
