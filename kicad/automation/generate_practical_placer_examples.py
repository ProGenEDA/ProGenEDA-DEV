#!/usr/bin/env python3
"""Generate reusable partial-CircuitIR placer example packs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import slugify


CircuitSpec = tuple[str, str, tuple[tuple[str, str], ...]]
CountSpec = tuple[str, str, int]
CountCircuitSpec = tuple[str, str, str, tuple[CountSpec, ...]]


CIRCUITS: tuple[CircuitSpec, ...] = (
    (
        "C01",
        "Arduino LED Blink",
        (
            ("ARDUINO_NANO", "Arduino Nano"),
            ("LED_INDICATOR", "LED"),
            ("R_220", "220 ohm Resistor"),
            ("PUSH_BUTTON", "Push Button"),
            ("USB_C_CONNECTOR", "USB Type-C Connector"),
        ),
    ),
    (
        "C02",
        "5V Power Supply",
        (
            ("LM7805", "LM7805 Voltage Regulator"),
            ("D_1N4007", "1N4007 Diode"),
            ("CP_100UF", "100uF Electrolytic Capacitor"),
            ("C_100NF_CERAMIC", "100nF Ceramic Capacitor"),
            ("DC_BARREL_JACK", "DC Barrel Jack"),
        ),
    ),
    (
        "C03",
        "ESP32 WiFi Board",
        (
            ("ESP32_WROOM", "ESP32-WROOM Module"),
            ("EN_PUSH_BUTTON", "EN Push Button"),
            ("BOOT_PUSH_BUTTON", "BOOT Push Button"),
            ("R_10K_PULLUP", "10k Pull-up Resistor"),
            ("CP2102", "CP2102 USB-UART IC"),
        ),
    ),
    (
        "C04",
        "MOSFET Motor Driver",
        (
            ("IRLZ44N", "IRLZ44N MOSFET"),
            ("FLYBACK_DIODE", "Flyback Diode"),
            ("DC_MOTOR", "DC Motor"),
            ("SCREW_TERMINAL_2", "Screw Terminal 2-pin"),
            ("PWM_HEADER", "PWM Header"),
        ),
    ),
    (
        "C05",
        "Relay Switching",
        (
            ("RELAY_5V", "5V Relay"),
            ("BC547", "BC547 NPN Transistor"),
            ("RELAY_FLYBACK_DIODE", "Relay Flyback Diode"),
            ("RELAY_INDICATOR_LED", "Indicator LED"),
            ("TERMINAL_BLOCK", "Terminal Block"),
        ),
    ),
    (
        "C06",
        "I2C Sensor",
        (
            ("BME280", "BME280 Sensor"),
            ("R_4K7_PULLUP", "4.7k Pull-up Resistor"),
            ("JST_CONNECTOR", "JST Connector"),
            ("DECOUPLING_CAPACITOR", "Decoupling Capacitor"),
            ("PIN_HEADER", "Pin Header"),
        ),
    ),
    (
        "C07",
        "SPI Flash",
        (
            ("W25Q64", "W25Q64 Flash IC"),
            ("C_100NF_FLASH", "100nF Capacitor"),
            ("SPI_HEADER_FLASH", "SPI Header"),
            ("CHIP_SELECT_JUMPER", "Chip Select Jumper"),
            ("TEST_POINT", "Test Point"),
        ),
    ),
    (
        "C08",
        "Crystal Oscillator",
        (
            ("CRYSTAL_16MHZ", "16MHz Crystal"),
            ("C_22PF_X1", "22pF Capacitor x1"),
            ("C_22PF_X2", "22pF Capacitor x2"),
            ("GND_SYMBOL", "Ground Symbol"),
            ("VCC_SYMBOL", "VCC Power Symbol"),
        ),
    ),
    (
        "C09",
        "Op-Amp Amplifier",
        (
            ("LM358", "LM358 Op-Amp"),
            ("FEEDBACK_RESISTOR", "Feedback Resistor"),
            ("INPUT_CAPACITOR", "Input Capacitor"),
            ("POTENTIOMETER", "Potentiometer"),
            ("AUDIO_JACK", "Audio Jack"),
        ),
    ),
    (
        "C10",
        "Buck Converter",
        (
            ("LM2596", "LM2596"),
            ("POWER_INDUCTOR", "Power Inductor"),
            ("SCHOTTKY_DIODE_BUCK", "Schottky Diode"),
            ("OUTPUT_CAPACITOR_BUCK", "Output Capacitor"),
            ("INPUT_CAPACITOR_BUCK", "Input Capacitor"),
        ),
    ),
    (
        "C11",
        "Battery Charger",
        (
            ("TP4056", "TP4056 Charger IC"),
            ("LI_ION_BATTERY_CONNECTOR", "Li-Ion Battery Connector"),
            ("CHARGING_LED", "Charging LED"),
            ("MICRO_USB_CONNECTOR", "Micro USB Connector"),
            ("PROTECTION_IC", "Protection IC"),
        ),
    ),
    (
        "C12",
        "UART Interface",
        (
            ("CH340", "CH340 USB-UART"),
            ("USB_CONNECTOR_UART", "USB Connector"),
            ("TX_HEADER", "TX Header"),
            ("RX_HEADER", "RX Header"),
            ("RESET_CAPACITOR", "Reset Capacitor"),
        ),
    ),
    (
        "C13",
        "OLED Display",
        (
            ("SSD1306_OLED", "SSD1306 OLED"),
            ("I2C_HEADER", "I2C Header"),
            ("PULLUP_RESISTOR_OLED", "Pull-up Resistor"),
            ("POWER_LED", "Power LED"),
            ("MOUNTING_HOLE", "Mounting Hole"),
        ),
    ),
    (
        "C14",
        "SD Card Interface",
        (
            ("MICRO_SD_SOCKET", "Micro SD Socket"),
            ("LEVEL_SHIFTER", "Level Shifter"),
            ("SPI_HEADER_SD", "SPI Header"),
            ("DECOUPLING_CAPACITOR_SD", "Decoupling Capacitor"),
            ("CARD_DETECT_SWITCH", "Card Detect Switch"),
        ),
    ),
    (
        "C15",
        "Audio Amplifier",
        (
            ("PAM8403", "PAM8403 Amplifier"),
            ("SPEAKER", "Speaker"),
            ("VOLUME_POTENTIOMETER", "Volume Potentiometer"),
            ("AUDIO_INPUT_JACK", "Audio Input Jack"),
            ("OUTPUT_FILTER_CAPACITOR", "Output Filter Capacitor"),
        ),
    ),
    (
        "C16",
        "CAN Bus",
        (
            ("MCP2515", "MCP2515 CAN Controller"),
            ("TJA1050", "TJA1050 CAN Transceiver"),
            ("CAN_TERMINAL", "CAN Terminal"),
            ("R_120_CAN", "120 ohm Termination Resistor"),
            ("CRYSTAL_OSCILLATOR_CAN", "Crystal Oscillator"),
        ),
    ),
    (
        "C17",
        "RS485 Communication",
        (
            ("MAX485", "MAX485 Transceiver"),
            ("RS485_TERMINAL", "RS485 Terminal"),
            ("R_120_RS485", "120 ohm Termination Resistor"),
            ("TVS_DIODE_RS485", "TVS Protection Diode"),
            ("HEADER_CONNECTOR", "Header Connector"),
        ),
    ),
    (
        "C18",
        "RTC Clock",
        (
            ("DS3231", "DS3231 RTC"),
            ("COIN_CELL_HOLDER", "Coin Cell Holder"),
            ("CR2032_BATTERY", "CR2032 Battery"),
            ("SDA_PULLUP", "SDA Pull-up"),
            ("SCL_PULLUP", "SCL Pull-up"),
        ),
    ),
    (
        "C19",
        "Logic Interface",
        (
            ("74HC595_SHIFT_REGISTER", "74HC595 Shift Register"),
            ("DIP_SWITCH", "DIP Switch"),
            ("LED_ARRAY", "LED Array"),
            ("RESISTOR_NETWORK", "Resistor Network"),
            ("PROGRAMMING_HEADER", "Programming Header"),
        ),
    ),
    (
        "C20",
        "Sensor Input Board",
        (
            ("ACS712", "ACS712 Current Sensor"),
            ("LM393_COMPARATOR", "LM393 Comparator"),
            ("TRIMMER_POTENTIOMETER", "Trimmer Potentiometer"),
            ("FUSE", "Fuse"),
            ("POLYFUSE", "Polyfuse Resettable Fuse"),
        ),
    ),
)


STRESS_CIRCUITS: tuple[CountCircuitSpec, ...] = (
    (
        "T01",
        "Small Beginner Board",
        "small clean placement test",
        (
            ("ARDUINO_NANO", "Arduino Nano", 1),
            ("LED_INDICATOR", "LED", 3),
            ("R_220", "220 ohm Resistor", 3),
            ("PUSH_BUTTON", "Push Button", 2),
            ("R_10K_PULLUP", "10k Resistor", 2),
            ("PIN_HEADER", "Pin Header", 2),
            ("GND_SYMBOL", "GND", 3),
            ("PWR_5V", "+5V", 2),
        ),
    ),
    (
        "T02",
        "Power Supply Cluster",
        "power-left-to-right placement",
        (
            ("LM7805", "LM7805 Voltage Regulator", 1),
            ("D_1N4007", "1N4007 Diode", 1),
            ("CP_100UF", "100uF Electrolytic Capacitor", 2),
            ("C_100NF_CERAMIC", "100nF Ceramic Capacitor", 3),
            ("DC_BARREL_JACK", "DC Barrel Jack", 1),
            ("LED_INDICATOR", "LED", 1),
            ("RESISTOR", "Resistor", 1),
            ("SCREW_TERMINAL_2", "Screw Terminal", 1),
            ("FUSE", "Fuse", 1),
            ("GND_SYMBOL", "GND", 4),
            ("PWR_5V", "+5V", 3),
        ),
    ),
    (
        "T03",
        "ESP32 Support Board",
        "big module plus support parts and many nets",
        (
            ("ESP32_WROOM", "ESP32-WROOM", 1),
            ("CP2102", "CP2102", 1),
            ("USB_C_CONNECTOR", "USB Type-C Connector", 1),
            ("EN_PUSH_BUTTON", "EN Push Button", 1),
            ("BOOT_PUSH_BUTTON", "BOOT Push Button", 1),
            ("R_10K_PULLUP", "10k Resistor", 4),
            ("C_100NF_CERAMIC", "100nF Capacitor", 5),
            ("LED_INDICATOR", "LED", 2),
            ("RESISTOR", "Resistor", 2),
            ("PIN_HEADER", "Pin Header", 4),
            ("GND_SYMBOL", "GND", 6),
            ("PWR_3V3", "+3V3", 4),
        ),
    ),
    (
        "T04",
        "Motor Relay Driver Mixed Board",
        "repeated driver blocks and connector-heavy layout",
        (
            ("IRLZ44N", "IRLZ44N MOSFET", 2),
            ("BC547", "BC547 Transistor", 2),
            ("RELAY_5V", "5V Relay", 2),
            ("FLYBACK_DIODE", "Flyback Diode", 4),
            ("DC_MOTOR", "DC Motor", 1),
            ("SCREW_TERMINAL_2", "Screw Terminal 2-pin", 4),
            ("PWM_HEADER", "PWM Header", 2),
            ("LED_INDICATOR", "LED", 4),
            ("RESISTOR", "Resistor", 6),
            ("GND_SYMBOL", "GND", 6),
            ("PWR_5V", "+5V", 4),
        ),
    ),
    (
        "T05",
        "I2C SPI Sensor Hub",
        "bus-style layout with repeated pullups, decoupling, and test points",
        (
            ("BME280", "BME280", 1),
            ("SSD1306_OLED", "SSD1306 OLED", 1),
            ("DS3231", "DS3231 RTC", 1),
            ("W25Q64", "W25Q64 Flash", 1),
            ("R_4K7_PULLUP", "4.7k Resistor", 4),
            ("C_100NF_CERAMIC", "100nF Capacitor", 6),
            ("JST_CONNECTOR", "JST Connector", 2),
            ("I2C_HEADER", "I2C Header", 2),
            ("SPI_HEADER_FLASH", "SPI Header", 1),
            ("COIN_CELL_HOLDER", "Coin Cell Holder", 1),
            ("CR2032_BATTERY", "CR2032 Battery", 1),
            ("TEST_POINT", "Test Point", 6),
            ("GND_SYMBOL", "GND", 8),
            ("PWR_3V3", "+3V3", 5),
        ),
    ),
    (
        "T06",
        "Communication Board",
        "IC clusters plus termination, protection, and connectors",
        (
            ("MCP2515", "MCP2515", 1),
            ("TJA1050", "TJA1050", 1),
            ("MAX485", "MAX485", 1),
            ("CAN_TERMINAL", "CAN Terminal", 1),
            ("RS485_TERMINAL", "RS485 Terminal", 1),
            ("R_120_CAN", "120 ohm Resistor", 2),
            ("TVS_DIODE_RS485", "TVS Diode", 2),
            ("CRYSTAL_16MHZ", "Crystal", 1),
            ("C_22PF_X1", "22pF Capacitor", 2),
            ("C_100NF_CERAMIC", "100nF Capacitor", 5),
            ("HEADER_CONNECTOR", "Header Connector", 3),
            ("CHIP_SELECT_JUMPER", "Jumper", 3),
            ("GND_SYMBOL", "GND", 8),
            ("PWR_5V", "+5V", 4),
        ),
    ),
    (
        "T07",
        "Audio Control Board",
        "analog-looking placement with many passives around ICs",
        (
            ("LM358", "LM358", 2),
            ("PAM8403", "PAM8403", 1),
            ("SPEAKER", "Speaker", 2),
            ("POTENTIOMETER", "Potentiometer", 3),
            ("AUDIO_JACK", "Audio Jack", 2),
            ("INPUT_CAPACITOR", "Input Capacitor", 4),
            ("OUTPUT_FILTER_CAPACITOR", "Output Filter Capacitor", 4),
            ("RESISTOR", "Resistor", 8),
            ("LED_INDICATOR", "LED", 2),
            ("GND_SYMBOL", "GND", 8),
            ("PWR_5V", "+5V", 4),
        ),
    ),
    (
        "T08",
        "Logic Display Board",
        "repeated ICs, rows, arrays, and symmetry",
        (
            ("74HC595_SHIFT_REGISTER", "74HC595", 3),
            ("DIP_SWITCH", "DIP Switch", 2),
            ("LED_ARRAY", "LED Array", 2),
            ("RESISTOR_NETWORK", "Resistor Network", 3),
            ("PROGRAMMING_HEADER", "Programming Header", 1),
            ("SPI_HEADER_FLASH", "SPI Header", 1),
            ("C_100NF_CERAMIC", "100nF Capacitor", 4),
            ("LED_INDICATOR", "LED", 8),
            ("RESISTOR", "Resistor", 8),
            ("GND_SYMBOL", "GND", 8),
            ("PWR_5V", "+5V", 4),
        ),
    ),
    (
        "T09",
        "Full Maker Controller Board",
        "real large schematic placement test",
        (
            ("ARDUINO_NANO", "Arduino Nano", 1),
            ("ESP32_WROOM", "ESP32-WROOM", 1),
            ("BME280", "BME280", 1),
            ("SSD1306_OLED", "SSD1306 OLED", 1),
            ("DS3231", "DS3231", 1),
            ("W25Q64", "W25Q64", 1),
            ("MOSFET", "MOSFET", 2),
            ("RELAY", "Relay", 1),
            ("BC547", "BC547", 1),
            ("LED_INDICATOR", "LED", 6),
            ("RESISTOR", "Resistor", 12),
            ("CAPACITOR", "Capacitor", 10),
            ("PUSH_BUTTON", "Push Button", 4),
            ("PIN_HEADER", "Pin Header", 6),
            ("JST_CONNECTOR", "JST Connector", 3),
            ("SCREW_TERMINAL_2", "Screw Terminal", 3),
            ("TEST_POINT", "Test Point", 8),
            ("GND_SYMBOL", "GND", 12),
            ("PWR_5V", "+5V", 6),
            ("PWR_3V3", "+3V3", 6),
        ),
    ),
    (
        "T10",
        "Near Limit Mixed Schematic",
        "serious placer stress test",
        (
            ("ARDUINO_NANO", "Arduino Nano", 1),
            ("ESP32_WROOM", "ESP32-WROOM", 1),
            ("LM7805", "LM7805", 1),
            ("CP2102", "CP2102", 1),
            ("CH340", "CH340", 1),
            ("BME280", "BME280", 1),
            ("SSD1306_OLED", "SSD1306 OLED", 1),
            ("DS3231", "DS3231", 1),
            ("W25Q64", "W25Q64", 2),
            ("74HC595_SHIFT_REGISTER", "74HC595", 4),
            ("LM358", "LM358", 2),
            ("MAX485", "MAX485", 1),
            ("MCP2515", "MCP2515", 1),
            ("TJA1050", "TJA1050", 1),
            ("MOSFET", "MOSFET", 4),
            ("BC547", "BC547", 4),
            ("RELAY", "Relay", 2),
            ("LED_INDICATOR", "LED", 16),
            ("RESISTOR", "Resistor", 32),
            ("CAPACITOR", "Capacitor", 24),
            ("DIODE", "Diode", 8),
            ("PUSH_BUTTON", "Push Button", 6),
            ("POTENTIOMETER", "Potentiometer", 3),
            ("PIN_HEADER", "Pin Header", 6),
            ("JST_CONNECTOR", "JST Connector", 4),
            ("SCREW_TERMINAL_2", "Screw Terminal", 4),
            ("HEADER_CONNECTOR", "Header Connector", 3),
            ("I2C_HEADER", "I2C Header", 1),
            ("SPI_HEADER_FLASH", "SPI Header", 1),
            ("USB_CONNECTOR", "USB Connector", 1),
            ("TEST_POINT", "Test Point", 16),
            ("GND_SYMBOL", "GND", 12),
            ("PWR_5V", "+5V", 10),
            ("PWR_3V3", "+3V3", 10),
        ),
    ),
    (
        "LIMA",
        "Limit A Passive Flood",
        "repeated small-symbol density",
        (
            ("RESISTOR", "Resistor", 100),
            ("CAPACITOR", "Capacitor", 100),
            ("GND_SYMBOL", "GND", 25),
            ("PWR_5V", "+5V", 25),
        ),
    ),
    (
        "LIMB",
        "Limit B IC Wall",
        "many medium ICs plus decoupling",
        (
            ("74HC595_SHIFT_REGISTER", "74HC595", 20),
            ("LM358", "LM358", 20),
            ("W25Q64", "W25Q64", 20),
            ("MAX485", "MAX485", 10),
            ("MCP2515", "MCP2515", 5),
            ("TJA1050", "TJA1050", 5),
            ("C_100NF_CERAMIC", "100nF Capacitor", 80),
            ("GND_SYMBOL", "GND", 40),
            ("PWR_5V", "+5V", 40),
        ),
    ),
    (
        "LIMC",
        "Limit C Connector Hell",
        "edge-style connector placement",
        (
            ("PIN_HEADER", "Pin Header", 40),
            ("JST_CONNECTOR", "JST Connector", 30),
            ("SCREW_TERMINAL_2", "Screw Terminal", 30),
            ("UART_HEADER", "UART Header", 20),
            ("SPI_HEADER_FLASH", "SPI Header", 20),
            ("I2C_HEADER", "I2C Header", 20),
            ("TEST_POINT", "Test Point", 60),
            ("MOUNTING_HOLE", "Mounting Hole", 20),
        ),
    ),
    (
        "LIMD",
        "Limit D Mixed Large Symbols",
        "large-symbol collision and out-of-sheet test",
        (
            ("ARDUINO_NANO", "Arduino Nano", 5),
            ("ESP32_WROOM", "ESP32-WROOM", 5),
            ("SSD1306_OLED", "SSD1306 OLED", 10),
            ("PAM8403", "PAM8403", 10),
            ("RELAY", "Relay", 10),
            ("DC_MOTOR", "DC Motor", 10),
            ("MICRO_SD_SOCKET", "Micro SD Socket", 10),
            ("USB_CONNECTOR", "USB Connector", 10),
            ("DC_BARREL_JACK", "DC Barrel Jack", 10),
            ("TERMINAL_BLOCK", "Terminal Block", 20),
            ("GND_SYMBOL", "GND", 40),
            ("PWR_5V", "+5V", 40),
        ),
    ),
)


def _progressive_mix(size: int) -> tuple[CountSpec, ...]:
    counts = {
        "passives": int(size * 0.40),
        "ics": int(size * 0.20),
        "connectors": int(size * 0.20),
        "power": int(size * 0.10),
    }
    counts["misc"] = size - sum(counts.values())
    buckets: list[CountSpec] = []

    def add_cycle(total: int, choices: tuple[tuple[str, str], ...]) -> None:
        per_kind = [0 for _ in choices]
        for index in range(total):
            per_kind[index % len(choices)] += 1
        for (kind, value), count in zip(choices, per_kind):
            if count:
                buckets.append((kind, value, count))

    add_cycle(counts["passives"], (("RESISTOR", "Resistor"), ("CAPACITOR", "Capacitor")))
    add_cycle(
        counts["ics"],
        (
            ("ARDUINO_NANO", "Arduino Nano"),
            ("ESP32_WROOM", "ESP32-WROOM"),
            ("LM358", "LM358"),
            ("W25Q64", "W25Q64"),
            ("74HC595_SHIFT_REGISTER", "74HC595"),
            ("MAX485", "MAX485"),
        ),
    )
    add_cycle(
        counts["connectors"],
        (
            ("PIN_HEADER", "Pin Header"),
            ("JST_CONNECTOR", "JST Connector"),
            ("SCREW_TERMINAL_2", "Screw Terminal"),
            ("HEADER_CONNECTOR", "Header Connector"),
        ),
    )
    add_cycle(counts["power"], (("GND_SYMBOL", "GND"), ("PWR_5V", "+5V"), ("PWR_3V3", "+3V3")))
    add_cycle(
        counts["misc"],
        (
            ("PUSH_BUTTON", "Push Button"),
            ("TEST_POINT", "Test Point"),
            ("LED_INDICATOR", "LED"),
            ("POTENTIOMETER", "Potentiometer"),
        ),
    )
    return tuple(buckets)


LIMIT_E_CIRCUITS: tuple[CountCircuitSpec, ...] = tuple(
    (
        f"LIME{size:03d}",
        f"Limit E Progressive Scaling {size}",
        "balanced progressive scaling test",
        _progressive_mix(size),
    )
    for size in (25, 50, 75, 100, 150, 200, 300, 400)
)


def build_circuit(cid: str, title: str, components: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    return build_count_circuit(
        cid,
        title,
        "real KiCad symbol placement coverage before beautifier and routing stages are enabled",
        tuple((kind, name, 1) for kind, name in components),
    )


def build_count_circuit(cid: str, title: str, purpose: str, components: tuple[CountSpec, ...]) -> dict[str, Any]:
    expanded: list[dict[str, str]] = []
    for kind, value, count in components:
        for _ in range(count):
            expanded.append({"id": f"X{len(expanded) + 1}", "kind": kind, "value": value})
    return {
        "schema_version": "progen-kicad-placer-ir/v0.2",
        "compatible_schema": "progen-kicad-circuit-ir/v1",
        "pipeline_stage": "component_placement_only",
        "project": {
            "name": f"{cid.lower()}_{slugify(title).lower()}",
            "title": title,
            "analysis": [],
        },
        "components": expanded,
        "nets": {},
        "constraints": {
            "placement": {"mode": "auto"},
            "routing": "deferred_to_wire_or_terminal_stage",
            "values": "display_only_until_value_editor_stage",
        },
        "notes": [
            "Partial CircuitIR-shaped placer input. Component id/kind/value/project/nets match the full CircuitIR shape as closely as this stage can support.",
            "Pins and net membership are intentionally omitted until the wire planner, terminal placer, and value editor stages own those decisions.",
            f"Purpose: {purpose}.",
        ],
    }


def suite_specs(suite: str) -> tuple[CountCircuitSpec, ...]:
    if suite == "baseline":
        return tuple(
            (cid, title, "100-component accepted baseline", tuple((kind, name, 1) for kind, name in components))
            for cid, title, components in CIRCUITS
        )
    if suite == "stress":
        return STRESS_CIRCUITS + LIMIT_E_CIRCUITS
    if suite == "all":
        return suite_specs("baseline") + suite_specs("stress")
    raise ValueError(f"Unknown suite {suite!r}")


def generate(out_dir: Path, *, suite: str = "baseline", clean: bool = False) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.glob("*.json")) and not clean:
        raise FileExistsError(f"Refusing to overwrite existing placer input pack: {out_dir}")
    if clean and out_dir.exists():
        raise FileExistsError(f"Refusing to clean existing placer input pack: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for cid, title, purpose, components in suite_specs(suite):
        circuit = build_count_circuit(cid, title, purpose, components)
        file_name = f"{cid}_{slugify(title).lower()}.json"
        path = out_dir / file_name
        path.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
        results.append({"id": cid, "title": title, "file": str(path), "component_count": len(circuit["components"])})
    manifest = {
        "schema": "progen-kicad-practical-placer-pack/v0.2",
        "suite": suite,
        "input_schema": "progen-kicad-placer-ir/v0.2",
        "compatible_schema": "progen-kicad-circuit-ir/v1",
        "circuit_count": len(results),
        "component_count": sum(item["component_count"] for item in results),
        "results": results,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate practical component-only placer examples.")
    parser.add_argument("--outdir", default="kicad/examples/placer_pack")
    parser.add_argument("--suite", choices=("baseline", "stress", "all"), default="baseline")
    parser.add_argument("--keep", action="store_true", help="Deprecated: generation is record-preserving and never deletes existing JSON files.")
    args = parser.parse_args()
    manifest = generate(Path(args.outdir), suite=args.suite, clean=False)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
