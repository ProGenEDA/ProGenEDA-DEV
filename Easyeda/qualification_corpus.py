"""Build a locked 300-circuit full-pin EasyEDA qualification corpus."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .catalogue import CATALOGUE, get_entry
from .donor_source import DonorPacket, EasyedaDonorSource, bundled_source_pack


CORPUS_SCHEMA = "progen-easyeda-qualification-corpus/v1"
CONNECTOR_KINDS = {
    "TERMINAL_BLOCK",
    "PIN_HEADER",
    "TEST_POINT",
    "HEADER_1X2",
    "HEADER_1X6",
    "HEADER_2X3",
    "HEADER_2X5_1P27",
}
GROUND_TOKENS = ("GND", "VSS", "VSSA", "VSSD", "GROUND")
POWER_TOKENS = (
    "VCC",
    "VDD",
    "VDDA",
    "VDDD",
    "VDDIO",
    "VBAT",
    "VBUS",
    "VIN",
    "REGIN",
    "3V3",
    "5V",
)


@dataclass(frozen=True)
class Archetype:
    slug: str
    title: str
    purpose: str
    supply: str
    kinds: tuple[str, ...]
    source_basis: str


ARCHETYPES = (
    Archetype("esp32_environment_logger", "ESP32 Environmental Data Logger", "Wi-Fi environmental sensing with RTC, display, and local flash.", "+3V3", ("ESP32_WROOM", "BME280", "DS3231", "W25Q64", "SSD1306", "AT24C256", "C", "C", "R", "R", "SPST_SWITCH", "LED"), "Espressif ESP32 reference design"),
    Archetype("esp32_can_gateway", "ESP32 CAN Telemetry Gateway", "Wi-Fi to CAN telemetry and diagnostics gateway.", "+3V3", ("ESP32_WROOM", "SN65HVD230", "SM24CANB", "R", "R", "C", "C", "TERMINAL_BLOCK", "LED", "SPST_SWITCH"), "Espressif and TI CAN reference structures"),
    Archetype("esp32_rs485_modbus", "ESP32 RS485 Modbus Node", "Networked Modbus sensor and actuator endpoint.", "+3V3", ("ESP32_WROOM", "MAX485", "BME280", "R", "R", "C", "C", "TERMINAL_BLOCK", "LED", "SPST_SWITCH"), "Espressif and RS485 application circuits"),
    Archetype("esp32_oled_panel", "ESP32 OLED Control Panel", "Human-interface panel with OLED, GPIO expansion, and RTC.", "+3V3", ("ESP32_WROOM", "SSD1306", "PCF8574", "DS3231", "R", "R", "C", "C", "SPST_SWITCH", "SPST_SWITCH", "LED"), "Espressif reference design and I2C peripheral practice"),
    Archetype("esp32_pwm_controller", "ESP32 Multi-channel PWM Controller", "Networked LED or servo PWM controller with analog feedback.", "+3V3", ("ESP32_WROOM", "PCA9685", "ADS1115", "PCF8574", "R", "R", "C", "C", "TERMINAL_BLOCK", "LED"), "Espressif and I2C controller reference practice"),
    Archetype("atmega_usb_controller", "ATmega USB Serial Controller", "ATmega328P controller with USB-UART programming interface.", "+5V", ("ATMEGA328P", "CP2102", "USB_C_RECEPTACLE", "USBLC6_2SC6", "PTC_FUSE", "C", "C", "R", "R", "LED", "SPST_SWITCH"), "Microcontroller development-board practice"),
    Archetype("atmega_logic_sequencer", "ATmega Logic Sequencer", "Programmable shift-register sequencer and digital trainer.", "+5V", ("ATMEGA328P", "74HC595", "74HC74", "74HC04", "R", "R", "C", "C", "LED", "LED", "SPST_SWITCH"), "Digital laboratory trainer circuits"),
    Archetype("stm32_can_controller", "STM32 CAN Control Node", "STM32 control node with protected CAN physical layer.", "+3V3", ("STM32F103C8T6", "SN65HVD230", "SM24CANB", "W25Q64", "R", "R", "C", "C", "TERMINAL_BLOCK", "HEADER_2X3", "LED"), "ST evaluation boards and TI CAN practice"),
    Archetype("stm32_rs485_controller", "STM32 RS485 Industrial Controller", "Industrial RS485 controller with nonvolatile configuration.", "+3V3", ("STM32F103C8T6", "MAX485", "AT24C256", "R", "R", "C", "C", "TERMINAL_BLOCK", "HEADER_2X3", "LED"), "ST evaluation boards and RS485 application circuits"),
    Archetype("stm32_data_acquisition", "STM32 Precision Data Acquisition Unit", "Multi-channel precision acquisition with RTC and storage.", "+3V3", ("STM32F103C8T6", "ADS1115", "DS3231", "W25Q64", "LM358", "R", "R", "C", "C", "HEADER_2X3", "LED"), "ST evaluation board data-acquisition structures"),
    Archetype("dual_mcu_bridge", "Multi-MCU Communications Bridge", "ESP32, ESP8266, and STM32 co-processor bridge with CAN and shared storage.", "+3V3", ("ESP32_WROOM", "ESP12F", "STM32F103C8T6", "SN65HVD230", "W25Q64", "AT24C256", "R", "R", "C", "C", "HEADER_2X3"), "Espressif and ST development-board structures"),
    Archetype("usb_c_3v3_power", "USB-C Protected 3V3 Power Module", "USB-C input, ESD protection, resettable fuse, filtering, and 3.3 V regulation.", "+3V3", ("USB_C_RECEPTACLE", "USBLC6_2SC6", "PTC_FUSE", "FERRITE_BEAD", "AP2112K_3V3", "CAP_ELEC", "C", "C", "R", "LED", "TERMINAL_BLOCK"), "USB-C power-input reference practice"),
    Archetype("cp2102_usb_uart", "CP2102 USB UART Adapter", "Protected USB-C to UART adapter with status indication.", "+3V3", ("USB_C_RECEPTACLE", "USBLC6_2SC6", "PTC_FUSE", "AP2112K_3V3", "CP2102", "C", "C", "R", "LED", "HEADER_1X6"), "USB-UART adapter reference practice"),
    Archetype("ch340_usb_uart", "CH340 USB UART Adapter", "5 V USB-C serial adapter with protected data lines.", "+5V", ("USB_C_RECEPTACLE", "USBLC6_2SC6", "PTC_FUSE", "CH340", "C", "C", "R", "LED", "HEADER_1X6"), "USB-UART adapter reference practice"),
    Archetype("can_transceiver_tester", "CAN Physical Layer Tester", "Protected CAN transceiver test fixture with termination and breakout.", "+3V3", ("SN65HVD230", "SM24CANB", "R", "R", "C", "TERMINAL_BLOCK", "HEADER_1X6", "TEST_POINT", "TEST_POINT", "LED"), "TI CAN interface practice"),
    Archetype("rs485_transceiver_tester", "RS485 Physical Layer Tester", "RS485 transceiver fixture with termination, bias, and test access.", "+5V", ("MAX485", "R", "R", "R", "C", "TERMINAL_BLOCK", "HEADER_1X6", "TEST_POINT", "TEST_POINT", "LED"), "RS485 application circuits"),
    Archetype("i2c_eeprom_module", "I2C EEPROM Memory Module", "Address-selectable I2C EEPROM module with write protection.", "+3V3", ("AT24C256", "R", "R", "R", "R", "C", "HEADER_1X6", "SPST_SWITCH", "LED"), "I2C EEPROM application circuit"),
    Archetype("i2c_gpio_module", "I2C GPIO Expansion Module", "16-line-style GPIO expansion and protected field breakout.", "+3V3", ("PCF8574", "R", "R", "C", "HEADER_1X6", "HEADER_2X5_1P27", "LED", "SPST_SWITCH"), "I2C GPIO expander application circuit"),
    Archetype("pwm_servo_module", "I2C PWM Servo Module", "Multi-channel PWM output module with filtered supply input.", "+5V", ("PCA9685", "FERRITE_BEAD", "PTC_FUSE", "CAP_ELEC", "C", "R", "R", "TERMINAL_BLOCK", "HEADER_2X5_1P27", "LED"), "PWM controller application circuit"),
    Archetype("precision_adc_frontend", "Precision ADC Sensor Front End", "Buffered precision ADC front end with adjustable threshold.", "+3V3", ("ADS1115", "LM358", "R_POT", "R", "R", "C", "C", "HEADER_1X6", "TEST_POINT", "LED"), "Precision ADC and op-amp front-end practice"),
    Archetype("rtc_logger_module", "RTC and Flash Logger Module", "Battery-backed timekeeping with SPI and I2C nonvolatile storage.", "+3V3", ("DS3231", "W25Q64", "AT24C256", "R", "R", "C", "C", "HEADER_2X5_1P27", "TEST_POINT", "LED"), "RTC and memory application circuits"),
    Archetype("spi_flash_module", "SPI Flash Breakout and Programmer", "SPI flash memory breakout with protected programming header.", "+3V3", ("W25Q64", "R", "R", "R", "C", "HEADER_2X3", "HEADER_1X6", "TEST_POINT", "LED"), "SPI memory application circuit"),
    Archetype("shift_register_display", "Shift Register LED Display Driver", "Cascaded logic and shift-register LED output trainer.", "+5V", ("74HC595", "74HC595", "74HC04", "74HC08", "R", "R", "R", "C", "C", "LED", "LED", "LED"), "Digital logic laboratory circuits"),
    Archetype("ne555_pulse_generator", "NE555 Adjustable Pulse Generator", "Adjustable astable pulse source with buffered logic output.", "+5V", ("NE555", "R_POT", "R", "R", "C", "CAP_ELEC", "74HC04", "LED", "SPST_SWITCH", "HEADER_1X6"), "NE555 laboratory application circuit"),
    Archetype("dual_opamp_conditioner", "Dual Op-Amp Sensor Conditioner", "Two-stage adjustable analog signal conditioner.", "+5V", ("LM358", "LM358", "R_POT", "R_POT", "R", "R", "R", "R", "C", "C", "HEADER_1X6", "TEST_POINT"), "Op-amp laboratory circuits"),
    Archetype("regulated_5v_supply", "Protected Regulated 5V Supply", "Reverse-protected linear 5 V supply with fuse and status LED.", "+5V", ("TERMINAL_BLOCK", "HEADER_1X2", "FUSE", "1N4007", "LM7805", "CAP_ELEC", "C", "R", "LED", "TERMINAL_BLOCK", "TEST_POINT"), "Linear regulator power-supply practice"),
    Archetype("adjustable_supply", "Adjustable LM317 Bench Supply", "Rectified adjustable linear supply with current protection.", "+5V", ("TERMINAL_BLOCK", "FUSE", "BRIDGE_RECTIFIER", "LM317", "R_POT", "R", "CAP_ELEC", "C", "1N4148", "LED", "TERMINAL_BLOCK"), "Adjustable regulator application circuit"),
    Archetype("transformer_rectifier_supply", "Transformer Rectifier Supply", "Isolated transformer, bridge rectifier, filtering, and protected output.", "+5V", ("TRANSFORMER", "BRIDGE_RECTIFIER", "FUSE", "CAP_ELEC", "CAP_ELEC", "L", "1N4007", "R", "LED", "TERMINAL_BLOCK"), "Isolated supply reference practice"),
    Archetype("transistor_driver_board", "Mixed Transistor Load Driver", "NPN, PNP, and MOSFET driver laboratory board with clamp protection.", "+5V", ("NPN", "PNP", "NMOS", "DIODE", "1N4148", "R", "R", "R", "LED", "SPST_SWITCH", "TERMINAL_BLOCK"), "Discrete electronics laboratory circuits"),
    Archetype("digital_logic_trainer", "Combinational and Sequential Logic Trainer", "Multi-family digital logic trainer with clock, gates, flip-flops, and general breakout.", "+5V", ("74HC00", "74HC32", "74HC04", "74HC08", "74HC32", "74HC74", "NE555", "R", "R", "C", "LED", "SPST_SWITCH", "PIN_HEADER"), "Digital logic laboratory circuits"),
)


VARIANT_PROFILES = (
    ("education", "teaching and bench measurement"),
    ("prototype", "rapid firmware and hardware prototyping"),
    ("field", "field wiring and service access"),
    ("compact", "compact embedded integration"),
    ("diagnostic", "diagnostic test points and status indication"),
    ("industrial", "industrial control cabinet integration"),
    ("instrument", "laboratory instrumentation"),
    ("automation", "automation and telemetry"),
    ("development", "development-board expansion"),
    ("validation", "production validation fixture"),
)


def _pin_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.upper().lstrip("/"))


def _is_ground(name: str) -> bool:
    token = _pin_token(name)
    return any(value in token for value in GROUND_TOKENS) or token in {"EP", "PAD"}


def _is_power(name: str) -> bool:
    token = _pin_token(name)
    return any(value in token for value in POWER_TOKENS)


def _is_nc(name: str) -> bool:
    token = _pin_token(name)
    return token in {"NC", "DNC", "RES", "RESERVED"} or token.startswith("NC")


def _default_value(kind: str, variant: int) -> str:
    values = {
        "R": ("220", "1k", "4.7k", "10k", "120"),
        "R_POT": ("10k", "50k", "100k"),
        "C": ("100nF", "1uF", "10nF", "22pF"),
        "CAP_ELEC": ("47uF", "100uF", "220uF"),
        "L": ("47uH", "100uH"),
        "PTC_FUSE": ("500mA", "750mA"),
        "FERRITE_BEAD": ("100", "600"),
    }
    offered = values.get(kind)
    if offered:
        return offered[(variant - 1) % len(offered)]
    return get_entry(kind).default_value


def _known_pin_net(
    kind: str,
    pin_number: str,
    pin_name: str,
    *,
    supply: str,
    reference: str,
) -> str | None:
    token = _pin_token(pin_name)
    if _is_ground(pin_name):
        return "GND"
    if _is_nc(pin_name):
        return f"NC_{reference}_{pin_number}"
    if kind == "USB_C_RECEPTACLE":
        if pin_number == "0":
            return "GND"
        if "VBUS" in token:
            return "USB_VBUS"
        if token in {"DP1", "DP2"}:
            return "USB_DP"
        if token in {"DN1", "DN2"}:
            return "USB_DM"
        if token.startswith("CC"):
            return f"USB_{token}"
        if token.startswith("SBU"):
            return f"NC_{reference}_{pin_number}"
    if kind == "AP2112K_3V3":
        return {
            "VIN": "+5V",
            "EN": "+5V",
            "VOUT": "+3V3",
            "GND": "GND",
            "NC": f"NC_{reference}_{pin_number}",
        }.get(token)
    if kind == "USBLC6_2SC6":
        return {
            "1": "USB_DP",
            "2": "GND",
            "3": "USB_DM",
            "4": "USB_DM",
            "5": "USB_VBUS",
            "6": "USB_DP",
        }.get(pin_number)
    if _is_power(pin_name):
        if any(value in token for value in ("VBUS", "5V")):
            return "+5V"
        if "3V3" in token:
            return "+3V3"
        return supply
    buses = (
        ("SDA", "I2C_SDA"),
        ("SCL", "I2C_SCL"),
        ("CANH", "CAN_H"),
        ("CANL", "CAN_L"),
        ("TXD", "UART_TX"),
        ("RXD", "UART_RX"),
        ("UD+", "USB_DP"),
        ("D+", "USB_DP"),
        ("UD-", "USB_DM"),
        ("D-", "USB_DM"),
        ("SCK", "SPI_CLK"),
        ("CLK", "SPI_CLK"),
        ("MOSI", "SPI_MOSI"),
        ("MISO", "SPI_MISO"),
    )
    for marker, net in buses:
        if marker.replace("+", "P").replace("-", "M") in token.replace("+", "P").replace("-", "M"):
            return net
    if kind == "SN65HVD230":
        return {
            "D": "CAN_TX",
            "R": "CAN_RX",
            "CANH": "CAN_H",
            "CANL": "CAN_L",
            "VREF": "CAN_VREF",
            "RS": "CAN_SLOPE",
        }.get(token)
    if kind == "MAX485":
        return {
            "RO": "RS485_RX",
            "RE": "RS485_ENABLE",
            "DE": "RS485_ENABLE",
            "DI": "RS485_TX",
            "A": "RS485_A",
            "B": "RS485_B",
        }.get(token)
    return None


def _assign_common_component(
    component: dict[str, Any],
    packet: DonorPacket,
    *,
    supply: str,
) -> dict[str, str]:
    kind = component["kind"]
    reference = component["ref"]
    numbers = list(dict.fromkeys(pin.number for pin in packet.pins))
    if kind in {"C", "CAP_ELEC"} and len(numbers) >= 2:
        return {numbers[0]: supply, numbers[1]: "GND"}
    if kind == "R" and len(numbers) >= 2:
        return {numbers[0]: supply, numbers[1]: "GND"}
    if kind == "LED" and len(numbers) >= 2:
        return {numbers[0]: supply, numbers[1]: "GND"}
    if kind == "SPST_SWITCH" and len(numbers) >= 2:
        return {numbers[0]: f"SWITCH_{reference}", numbers[1]: "GND"}
    if kind in {"TERMINAL_BLOCK", "HEADER_1X2"} and len(numbers) >= 2:
        return {numbers[0]: supply, numbers[1]: "GND"}
    if kind == "PTC_FUSE" and len(numbers) >= 2:
        return {numbers[0]: "USB_VBUS", numbers[1]: "+5V_FUSED"}
    if kind == "FERRITE_BEAD" and len(numbers) >= 2:
        return {numbers[0]: "+5V_FUSED", numbers[1]: "+5V"}
    if kind == "FUSE" and len(numbers) >= 2:
        return {numbers[0]: "VIN_RAW", numbers[1]: "VIN_FUSED"}
    if kind == "1N4007" and len(numbers) >= 2:
        return {numbers[0]: "VIN_PROTECTED", numbers[1]: "VIN_FUSED"}
    if kind == "L" and len(numbers) >= 2:
        return {numbers[0]: supply, numbers[1]: f"FILTERED_{supply}"}
    if kind == "LM7805":
        return {"1": "VIN_PROTECTED", "2": "GND", "3": "+5V", "4": "GND"}
    if kind == "LM317":
        return {"1": "LM317_ADJ", "2": supply, "3": "VIN_FUSED", "4": supply}
    if kind == "BRIDGE_RECTIFIER":
        return {"1": "AC_IN_A", "2": "VIN_RAW", "3": "AC_IN_B", "4": "GND"}
    if kind == "TRANSFORMER":
        return {
            numbers[0]: "AC_PRIMARY_A",
            numbers[1]: "AC_PRIMARY_B",
            numbers[2]: "AC_IN_A",
            numbers[3]: "AC_IN_B",
        }
    if kind == "MOUNTING_HOLE_PTH":
        return {numbers[0]: "GND"}
    if kind == "MOUNTING_HOLE_NPTH":
        return {numbers[0]: f"NC_CHASSIS_{reference}"}
    if kind == "TEST_POINT":
        return {}
    return {
        pin.number: net
        for pin in packet.pins
        if (net := _known_pin_net(kind, pin.number, pin.name, supply=supply, reference=reference))
    }


def _make_components(
    archetype: Archetype,
    variant: int,
    source: EasyedaDonorSource,
) -> tuple[list[dict[str, Any]], dict[str, DonorPacket]]:
    counters: Counter[str] = Counter()
    components: list[dict[str, Any]] = []
    packets: dict[str, DonorPacket] = {}

    def append(kind: str, *, role: str, block: str) -> dict[str, Any]:
        entry = get_entry(kind)
        counters[entry.reference_prefix] += 1
        reference = f"{entry.reference_prefix}{counters[entry.reference_prefix]}"
        component = {
            "id": reference,
            "ref": reference,
            "kind": kind,
            "value": _default_value(kind, variant),
            "role": role,
            "block": block,
            "pins": {},
        }
        components.append(component)
        packets[reference] = source.resolve(entry)
        return component

    for kind in archetype.kinds:
        append(kind, role="functional", block=archetype.slug)
    append("MOUNTING_HOLE_PTH", role="mechanical_ground", block="mechanical")
    append("MOUNTING_HOLE_NPTH", role="mechanical", block="mechanical")

    assignments: dict[str, dict[str, str]] = {}
    for component in components:
        assignments[component["ref"]] = _assign_common_component(
            component,
            packets[component["ref"]],
            supply=archetype.supply,
        )

    def net_members() -> Counter[str]:
        return Counter(
            net
            for values in assignments.values()
            for net in values.values()
        )

    connector_slots: list[tuple[str, str]] = []
    pending: list[tuple[str, str]] = []
    for component in components:
        reference = component["ref"]
        packet = packets[reference]
        unique = list(dict.fromkeys(pin.number for pin in packet.pins))
        for number in unique:
            if number in assignments[reference]:
                continue
            if component["kind"] in CONNECTOR_KINDS:
                connector_slots.append((reference, number))
            else:
                assignments[reference][number] = f"IO_{reference}_{number}"
                pending.append((reference, number))

    singleton_nets = [
        net
        for net, count in net_members().items()
        if count == 1 and not net.startswith("NC_")
    ]
    required_slots = len(singleton_nets)
    while len(connector_slots) < required_slots:
        header = append(
            "HEADER_2X5_1P27",
            role="full_pin_breakout",
            block="expansion",
        )
        assignments[header["ref"]] = {}
        for pin in dict.fromkeys(
            descriptor.number for descriptor in packets[header["ref"]].pins
        ):
            connector_slots.append((header["ref"], pin))
    if len(components) > 32:
        raise RuntimeError(
            f"{archetype.slug} variant {variant} requires {len(components)} physical components."
        )

    for net, (reference, number) in zip(singleton_nets, connector_slots):
        assignments[reference][number] = net
    for reference, number in connector_slots[len(singleton_nets):]:
        assignments[reference][number] = "GND"

    for component in components:
        reference = component["ref"]
        packet = packets[reference]
        unique_numbers = set(pin.number for pin in packet.pins)
        if set(assignments[reference]) != unique_numbers:
            missing = sorted(unique_numbers - set(assignments[reference]))
            raise RuntimeError(f"{reference} remains unaccounted: {missing}")
        component["pins"] = dict(sorted(assignments[reference].items()))

    dynamic_headers = {
        component["ref"]: component
        for component in components
        if component["role"] == "full_pin_breakout"
    }
    if dynamic_headers:
        source_by_net: dict[str, list[str]] = {}
        for component in components:
            if component["ref"] in dynamic_headers:
                continue
            for net in component["pins"].values():
                source_by_net.setdefault(net, []).append(component["ref"])
        anchored: dict[str, list[dict[str, Any]]] = {}
        for reference, header in dynamic_headers.items():
            candidates = [
                source_reference
                for net in header["pins"].values()
                for source_reference in source_by_net.get(net, [])
            ]
            anchor = Counter(candidates).most_common(1)[0][0] if candidates else components[0]["ref"]
            anchored.setdefault(anchor, []).append(header)
        reordered: list[dict[str, Any]] = []
        for component in components:
            if component["ref"] in dynamic_headers:
                continue
            reordered.append(component)
            reordered.extend(anchored.get(component["ref"], []))
        components = reordered
    return components, packets


def build_circuit(
    archetype: Archetype,
    variant: int,
    source: EasyedaDonorSource,
) -> dict[str, Any]:
    profile, profile_purpose = VARIANT_PROFILES[variant - 1]
    components, _ = _make_components(archetype, variant, source)
    nets: dict[str, list[str]] = {}
    for component in components:
        for pin, net in component["pins"].items():
            nets.setdefault(net, []).append(f"{component['ref']}.{pin}")
    name = f"q{ARCHETYPES.index(archetype) + 1:02d}_{archetype.slug}_{profile}_v{variant:02d}"
    return {
        "schema_version": "progen-easyeda-circuit-ir/v1",
        "project": {
            "name": name,
            "title": f"{archetype.title} - {profile.title()} Variant",
            "target": "easyeda_pro",
        },
        "routing": {"mode": "combination"},
        "purpose": f"{archetype.purpose} Optimized for {profile_purpose}.",
        "qualification": {
            "schema": CORPUS_SCHEMA,
            "archetype": archetype.slug,
            "variant": variant,
            "profile": profile,
            "source_basis": archetype.source_basis,
            "require_complete_pin_coverage": True,
            "require_pcb_when_routable": True,
        },
        "components": components,
        "nets": [
            {"name": net, "members": sorted(members)}
            for net, members in sorted(nets.items())
        ],
        "expected_netlist": {
            net: sorted(members)
            for net, members in sorted(nets.items())
        },
    }


def build_corpus(output: Path, source: EasyedaDonorSource) -> dict[str, Any]:
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    covered: set[str] = set()
    for archetype in ARCHETYPES:
        for variant in range(1, 11):
            circuit = build_circuit(archetype, variant, source)
            path = output / f"{circuit['project']['name']}.json"
            path.write_text(
                json.dumps(circuit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            kinds = {component["kind"] for component in circuit["components"]}
            covered.update(kinds)
            records.append(
                {
                    "name": circuit["project"]["name"],
                    "title": circuit["project"]["title"],
                    "purpose": circuit["purpose"],
                    "path": path.name,
                    "component_count": len(circuit["components"]),
                    "net_count": len(circuit["nets"]),
                    "kinds": sorted(kinds),
                }
            )
    physical = {
        kind
        for kind, entry in CATALOGUE.items()
        if entry.selector.pcb_required
    }
    manifest = {
        "schema": CORPUS_SCHEMA,
        "circuit_count": len(records),
        "archetype_count": len(ARCHETYPES),
        "variants_per_archetype": 10,
        "covered_physical_kinds": sorted(covered & physical),
        "missing_physical_kinds": sorted(physical - covered),
        "records": records,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if len(records) != 300:
        raise RuntimeError(f"Qualification corpus must contain 300 circuits, got {len(records)}.")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-pack", type=Path)
    args = parser.parse_args()
    source = EasyedaDonorSource(args.source_pack or bundled_source_pack())
    print(
        json.dumps(
            build_corpus(args.output, source),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
