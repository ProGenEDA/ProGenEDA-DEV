"""Embedded component placement catalog for placer-only inputs.

The geometry metadata is local to the placer. The ``lib_id`` mappings point to
real KiCad symbols that the project writer resolves from KiCad library sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from kicad.generator.kicad_json_to_project import KIND_SPECS
from kicad.generator.orthogonal_router import Obstacle


@dataclass(frozen=True)
class PlacementSpec:
    kind: str
    name: str
    ref_prefix: str
    width: float
    height: float
    category: str
    source: str = "embedded_placement_catalog"
    lib_id: str | None = None


@dataclass(frozen=True)
class PlacedCatalogComponent:
    ref: str
    kind: str
    name: str
    at: tuple[float, float]
    rotation: float
    manual_position: bool
    spec: PlacementSpec


@dataclass(frozen=True)
class CatalogPlacementPlan:
    components: tuple[PlacedCatalogComponent, ...]
    obstacles: tuple[Obstacle, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "components": {
                c.ref: {
                    "kind": c.kind,
                    "name": c.name,
                    "at": list(c.at),
                    "rotation": c.rotation,
                    "manual": c.manual_position,
                    "category": c.spec.category,
                    "catalog_source": c.spec.source,
                    "lib_id": c.spec.lib_id,
                }
                for c in self.components
            },
            "obstacles": [
                {
                    "owner": obstacle.owner,
                    "left": obstacle.left,
                    "top": obstacle.top,
                    "right": obstacle.right,
                    "bottom": obstacle.bottom,
                }
                for obstacle in self.obstacles
            ],
        }


def normalize_kind(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip().upper())
    return re.sub(r"_+", "_", text).strip("_")


def _snap(value: float, grid: float = 1.27) -> float:
    return round(round(value / grid) * grid, 3)


def _spec(kind: str, name: str, ref_prefix: str, width: float, height: float, category: str) -> PlacementSpec:
    return PlacementSpec(normalize_kind(kind), name, ref_prefix, width, height, category)


_SPECS = [
    _spec("ARDUINO_NANO", "Arduino Nano", "A", 55.0, 60.0, "microcontroller_module"),
    _spec("LED_INDICATOR", "LED", "D", 5.0, 5.0, "indicator"),
    _spec("R_220", "220 ohm Resistor", "R", 7.0, 2.5, "resistor"),
    _spec("PUSH_BUTTON", "Push Button", "SW", 6.0, 6.0, "switch"),
    _spec("USB_C_CONNECTOR", "USB Type-C Connector", "J", 9.0, 7.0, "connector"),
    _spec("LM7805", "LM7805 Voltage Regulator", "U", 10.0, 8.0, "regulator"),
    _spec("D_1N4007", "1N4007 Diode", "D", 8.0, 3.0, "diode"),
    _spec("CP_100UF", "100uF Electrolytic Capacitor", "C", 6.0, 6.0, "capacitor"),
    _spec("C_100NF_CERAMIC", "100nF Ceramic Capacitor", "C", 4.0, 3.0, "capacitor"),
    _spec("DC_BARREL_JACK", "DC Barrel Jack", "J", 14.0, 11.0, "connector"),
    _spec("ESP32_WROOM", "ESP32-WROOM Module", "U", 45.0, 55.0, "wireless_module"),
    _spec("EN_PUSH_BUTTON", "EN Push Button", "SW", 6.0, 6.0, "switch"),
    _spec("BOOT_PUSH_BUTTON", "BOOT Push Button", "SW", 6.0, 6.0, "switch"),
    _spec("R_10K_PULLUP", "10k Pull-up Resistor", "R", 7.0, 2.5, "resistor"),
    _spec("CP2102", "CP2102 USB-UART IC", "U", 7.0, 7.0, "interface_ic"),
    _spec("IRLZ44N", "IRLZ44N MOSFET", "Q", 10.0, 8.0, "mosfet"),
    _spec("FLYBACK_DIODE", "Flyback Diode", "D", 8.0, 3.0, "diode"),
    _spec("DC_MOTOR", "DC Motor", "M", 18.0, 14.0, "motor"),
    _spec("SCREW_TERMINAL_2", "Screw Terminal 2-pin", "J", 10.0, 8.0, "terminal"),
    _spec("PWM_HEADER", "PWM Header", "J", 7.5, 3.0, "header"),
    _spec("RELAY_5V", "5V Relay", "K", 19.0, 15.0, "relay"),
    _spec("BC547", "BC547 NPN Transistor", "Q", 5.0, 4.0, "bjt"),
    _spec("RELAY_FLYBACK_DIODE", "Relay Flyback Diode", "D", 8.0, 3.0, "diode"),
    _spec("RELAY_INDICATOR_LED", "Indicator LED", "D", 5.0, 5.0, "indicator"),
    _spec("TERMINAL_BLOCK", "Terminal Block", "J", 12.0, 8.0, "terminal"),
    _spec("BME280", "BME280 Sensor", "U", 8.0, 8.0, "sensor"),
    _spec("R_4K7_PULLUP", "4.7k Pull-up Resistor", "R", 7.0, 2.5, "resistor"),
    _spec("JST_CONNECTOR", "JST Connector", "J", 8.0, 5.0, "connector"),
    _spec("DECOUPLING_CAPACITOR", "Decoupling Capacitor", "C", 4.0, 3.0, "capacitor"),
    _spec("PIN_HEADER", "Pin Header", "J", 10.0, 3.0, "header"),
    _spec("W25Q64", "W25Q64 Flash IC", "U", 22.0, 28.0, "memory_ic"),
    _spec("C_100NF_FLASH", "100nF Capacitor", "C", 4.0, 3.0, "capacitor"),
    _spec("SPI_HEADER_FLASH", "SPI Header", "J", 12.0, 3.0, "header"),
    _spec("CHIP_SELECT_JUMPER", "Chip Select Jumper", "JP", 5.0, 3.0, "jumper"),
    _spec("TEST_POINT", "Test Point", "TP", 2.5, 2.5, "testpoint"),
    _spec("CRYSTAL_16MHZ", "16MHz Crystal", "Y", 8.0, 4.0, "crystal"),
    _spec("C_22PF_X1", "22pF Capacitor x1", "C", 4.0, 3.0, "capacitor"),
    _spec("C_22PF_X2", "22pF Capacitor x2", "C", 4.0, 3.0, "capacitor"),
    _spec("GND_SYMBOL", "Ground Symbol", "#PWR", 5.0, 4.0, "power_symbol"),
    _spec("VCC_SYMBOL", "VCC Power Symbol", "#PWR", 5.0, 4.0, "power_symbol"),
    _spec("LM358", "LM358 Op-Amp", "U", 22.0, 30.0, "opamp"),
    _spec("FEEDBACK_RESISTOR", "Feedback Resistor", "R", 7.0, 2.5, "resistor"),
    _spec("INPUT_CAPACITOR", "Input Capacitor", "C", 4.0, 3.0, "capacitor"),
    _spec("POTENTIOMETER", "Potentiometer", "RV", 9.0, 9.0, "potentiometer"),
    _spec("AUDIO_JACK", "Audio Jack", "J", 11.0, 8.0, "connector"),
    _spec("LM2596", "LM2596", "U", 11.0, 9.0, "buck_converter"),
    _spec("POWER_INDUCTOR", "Power Inductor", "L", 9.0, 9.0, "inductor"),
    _spec("SCHOTTKY_DIODE_BUCK", "Schottky Diode", "D", 8.0, 4.0, "diode"),
    _spec("OUTPUT_CAPACITOR_BUCK", "Output Capacitor", "C", 6.0, 6.0, "capacitor"),
    _spec("INPUT_CAPACITOR_BUCK", "Input Capacitor", "C", 6.0, 6.0, "capacitor"),
    _spec("TP4056", "TP4056 Charger IC", "U", 7.0, 7.0, "charger_ic"),
    _spec("LI_ION_BATTERY_CONNECTOR", "Li-Ion Battery Connector", "J", 10.0, 6.0, "connector"),
    _spec("CHARGING_LED", "Charging LED", "D", 5.0, 5.0, "indicator"),
    _spec("MICRO_USB_CONNECTOR", "Micro USB Connector", "J", 14.0, 10.0, "connector"),
    _spec("PROTECTION_IC", "Protection IC", "U", 12.0, 8.0, "protection_ic"),
    _spec("CH340", "CH340 USB-UART", "U", 7.0, 7.0, "interface_ic"),
    _spec("USB_CONNECTOR_UART", "USB Connector", "J", 9.0, 7.0, "connector"),
    _spec("TX_HEADER", "TX Header", "J", 5.0, 3.0, "header"),
    _spec("RX_HEADER", "RX Header", "J", 5.0, 3.0, "header"),
    _spec("RESET_CAPACITOR", "Reset Capacitor", "C", 4.0, 3.0, "capacitor"),
    _spec("SSD1306_OLED", "SSD1306 OLED", "DS", 27.0, 27.0, "display"),
    _spec("I2C_HEADER", "I2C Header", "J", 10.0, 3.0, "header"),
    _spec("PULLUP_RESISTOR_OLED", "Pull-up Resistor", "R", 7.0, 2.5, "resistor"),
    _spec("POWER_LED", "Power LED", "D", 5.0, 5.0, "indicator"),
    _spec("MOUNTING_HOLE", "Mounting Hole", "H", 4.0, 4.0, "mechanical"),
    _spec("MICRO_SD_SOCKET", "Micro SD Socket", "J", 15.0, 14.0, "connector"),
    _spec("LEVEL_SHIFTER", "Level Shifter", "U", 10.0, 7.0, "interface_ic"),
    _spec("SPI_HEADER_SD", "SPI Header", "J", 12.0, 3.0, "header"),
    _spec("DECOUPLING_CAPACITOR_SD", "Decoupling Capacitor", "C", 4.0, 3.0, "capacitor"),
    _spec("CARD_DETECT_SWITCH", "Card Detect Switch", "SW", 6.0, 4.0, "switch"),
    _spec("PAM8403", "PAM8403 Amplifier", "U", 9.0, 8.0, "audio_ic"),
    _spec("SPEAKER", "Speaker", "LS", 18.0, 18.0, "speaker"),
    _spec("VOLUME_POTENTIOMETER", "Volume Potentiometer", "RV", 9.0, 9.0, "potentiometer"),
    _spec("AUDIO_INPUT_JACK", "Audio Input Jack", "J", 11.0, 8.0, "connector"),
    _spec("OUTPUT_FILTER_CAPACITOR", "Output Filter Capacitor", "C", 5.0, 4.0, "capacitor"),
    _spec("MCP2515", "MCP2515 CAN Controller", "U", 24.0, 34.0, "interface_ic"),
    _spec("TJA1050", "TJA1050 CAN Transceiver", "U", 22.0, 30.0, "interface_ic"),
    _spec("CAN_TERMINAL", "CAN Terminal", "J", 10.0, 8.0, "terminal"),
    _spec("R_120_CAN", "120 ohm Termination Resistor", "R", 7.0, 2.5, "resistor"),
    _spec("CRYSTAL_OSCILLATOR_CAN", "Crystal Oscillator", "Y", 8.0, 4.0, "crystal"),
    _spec("MAX485", "MAX485 Transceiver", "U", 22.0, 30.0, "interface_ic"),
    _spec("RS485_TERMINAL", "RS485 Terminal", "J", 10.0, 8.0, "terminal"),
    _spec("R_120_RS485", "120 ohm Termination Resistor", "R", 7.0, 2.5, "resistor"),
    _spec("TVS_DIODE_RS485", "TVS Protection Diode", "D", 6.0, 4.0, "protection"),
    _spec("HEADER_CONNECTOR", "Header Connector", "J", 10.0, 3.0, "header"),
    _spec("DS3231", "DS3231 RTC", "U", 24.0, 34.0, "rtc_ic"),
    _spec("COIN_CELL_HOLDER", "Coin Cell Holder", "BT", 20.0, 20.0, "battery_holder"),
    _spec("CR2032_BATTERY", "CR2032 Battery", "BT", 20.0, 20.0, "battery"),
    _spec("SDA_PULLUP", "SDA Pull-up", "R", 7.0, 2.5, "resistor"),
    _spec("SCL_PULLUP", "SCL Pull-up", "R", 7.0, 2.5, "resistor"),
    _spec("74HC595_SHIFT_REGISTER", "74HC595 Shift Register", "U", 24.0, 34.0, "logic_ic"),
    _spec("DIP_SWITCH", "DIP Switch", "SW", 10.0, 7.0, "switch"),
    _spec("LED_ARRAY", "LED Array", "D", 14.0, 6.0, "indicator"),
    _spec("RESISTOR_NETWORK", "Resistor Network", "RN", 12.0, 4.0, "resistor"),
    _spec("PROGRAMMING_HEADER", "Programming Header", "J", 12.0, 3.0, "header"),
    _spec("ACS712", "ACS712 Current Sensor", "U", 8.0, 8.0, "sensor"),
    _spec("LM393_COMPARATOR", "LM393 Comparator", "U", 8.0, 7.0, "comparator"),
    _spec("TRIMMER_POTENTIOMETER", "Trimmer Potentiometer", "RV", 7.0, 7.0, "potentiometer"),
    _spec("FUSE", "Fuse", "F", 8.0, 3.0, "protection"),
    _spec("POLYFUSE", "Polyfuse Resettable Fuse", "F", 8.0, 4.0, "protection"),
    _spec("RESISTOR", "Resistor", "R", 7.0, 2.5, "resistor"),
    _spec("CAPACITOR", "Capacitor", "C", 4.0, 3.0, "capacitor"),
    _spec("DIODE", "Diode", "D", 8.0, 3.0, "diode"),
    _spec("MOSFET", "MOSFET", "Q", 10.0, 8.0, "mosfet"),
    _spec("RELAY", "Relay", "K", 19.0, 15.0, "relay"),
    _spec("PWR_5V", "+5V Power Symbol", "#PWR", 10.0, 10.0, "power_symbol"),
    _spec("PWR_3V3", "+3V3 Power Symbol", "#PWR", 10.0, 10.0, "power_symbol"),
    _spec("UART_HEADER", "UART Header", "J", 10.0, 3.0, "header"),
    _spec("USB_CONNECTOR", "USB Connector", "J", 14.0, 10.0, "connector"),
]

PLACER_COMPONENT_SPECS: dict[str, PlacementSpec] = {spec.kind: spec for spec in _SPECS}

PLACER_KIND_LIB_IDS: dict[str, str] = {
    "ARDUINO_NANO": "MCU_Module:Arduino_Nano_v3.x",
    "LED_INDICATOR": "Device:LED",
    "R_220": "Device:R",
    "PUSH_BUTTON": "Switch:SW_Push",
    "USB_C_CONNECTOR": "Connector:USB_C_Receptacle_USB2.0_16P",
    "LM7805": "Regulator_Linear:LM7805_TO220",
    "D_1N4007": "Diode:1N4007",
    "CP_100UF": "Device:C_Polarized",
    "C_100NF_CERAMIC": "Device:C",
    "DC_BARREL_JACK": "Connector:Barrel_Jack",
    "ESP32_WROOM": "RF_Module:ESP32-WROOM-32",
    "EN_PUSH_BUTTON": "Switch:SW_Push",
    "BOOT_PUSH_BUTTON": "Switch:SW_Push",
    "R_10K_PULLUP": "Device:R",
    "CP2102": "Interface_USB:CP2102N-Axx-xQFN28",
    "IRLZ44N": "Transistor_FET:IRLZ44N",
    "FLYBACK_DIODE": "Device:D",
    "DC_MOTOR": "Motor:Motor_DC",
    "SCREW_TERMINAL_2": "Connector:Screw_Terminal_01x02",
    "PWM_HEADER": "Connector_Generic:Conn_01x04",
    "RELAY_5V": "Relay:Relay_SPDT",
    "BC547": "Transistor_BJT:BC547",
    "RELAY_FLYBACK_DIODE": "Device:D",
    "RELAY_INDICATOR_LED": "Device:LED",
    "TERMINAL_BLOCK": "Connector:Screw_Terminal_01x02",
    "BME280": "Sensor:BME280",
    "R_4K7_PULLUP": "Device:R",
    "JST_CONNECTOR": "Connector_Generic:Conn_01x04",
    "DECOUPLING_CAPACITOR": "Device:C",
    "PIN_HEADER": "Connector_Generic:Conn_01x08",
    "W25Q64": "Memory_Flash:W25Q32JVSS",
    "C_100NF_FLASH": "Device:C",
    "SPI_HEADER_FLASH": "Connector_Generic:Conn_01x08",
    "CHIP_SELECT_JUMPER": "Jumper:Jumper_2_Open",
    "TEST_POINT": "Connector:TestPoint",
    "CRYSTAL_16MHZ": "Device:Crystal",
    "C_22PF_X1": "Device:C",
    "C_22PF_X2": "Device:C",
    "GND_SYMBOL": "power:GND",
    "VCC_SYMBOL": "power:VCC",
    "LM358": "Amplifier_Operational:LM358",
    "FEEDBACK_RESISTOR": "Device:R",
    "INPUT_CAPACITOR": "Device:C",
    "POTENTIOMETER": "Device:R_Potentiometer",
    "AUDIO_JACK": "Connector_Audio:AudioJack3",
    "LM2596": "Regulator_Switching:LM2596S-ADJ",
    "POWER_INDUCTOR": "Device:L",
    "SCHOTTKY_DIODE_BUCK": "Device:D_Schottky",
    "OUTPUT_CAPACITOR_BUCK": "Device:C_Polarized",
    "INPUT_CAPACITOR_BUCK": "Device:C_Polarized",
    "TP4056": "Battery_Management:TP4056-42-ESOP8",
    "LI_ION_BATTERY_CONNECTOR": "Connector_Generic:Conn_01x02",
    "CHARGING_LED": "Device:LED",
    "MICRO_USB_CONNECTOR": "Connector:USB_B_Micro",
    "PROTECTION_IC": "Battery_Management:DW01A",
    "CH340": "Interface_USB:CH340G",
    "USB_CONNECTOR_UART": "Connector:USB_B_Micro",
    "TX_HEADER": "Connector_Generic:Conn_01x01",
    "RX_HEADER": "Connector_Generic:Conn_01x01",
    "RESET_CAPACITOR": "Device:C",
    "SSD1306_OLED": "Display_Graphic:OLED-128O064D",
    "I2C_HEADER": "Connector_Generic:Conn_01x04",
    "PULLUP_RESISTOR_OLED": "Device:R",
    "POWER_LED": "Device:LED",
    "MOUNTING_HOLE": "Mechanical:MountingHole",
    "MICRO_SD_SOCKET": "Connector:Micro_SD_Card_Det1",
    "LEVEL_SHIFTER": "Logic_LevelTranslator:TXS0108EPW",
    "SPI_HEADER_SD": "Connector_Generic:Conn_02x03_Odd_Even",
    "DECOUPLING_CAPACITOR_SD": "Device:C",
    "CARD_DETECT_SWITCH": "Switch:SW_SPST",
    "PAM8403": "Amplifier_Audio:PAM8403D",
    "SPEAKER": "Device:Speaker",
    "VOLUME_POTENTIOMETER": "Device:R_Potentiometer",
    "AUDIO_INPUT_JACK": "Connector_Audio:AudioJack3",
    "OUTPUT_FILTER_CAPACITOR": "Device:C",
    "MCP2515": "Interface_CAN_LIN:MCP2515-xSO",
    "TJA1050": "Interface_CAN_LIN:SN65HVD1050D",
    "CAN_TERMINAL": "Connector:Screw_Terminal_01x03",
    "R_120_CAN": "Device:R",
    "CRYSTAL_OSCILLATOR_CAN": "Device:Crystal",
    "MAX485": "Interface_UART:MAX485E",
    "RS485_TERMINAL": "Connector:Screw_Terminal_01x03",
    "R_120_RS485": "Device:R",
    "TVS_DIODE_RS485": "Device:D_TVS",
    "HEADER_CONNECTOR": "Connector_Generic:Conn_01x04",
    "DS3231": "Timer_RTC:DS3231M",
    "COIN_CELL_HOLDER": "Device:Battery_Cell",
    "CR2032_BATTERY": "Device:Battery_Cell",
    "SDA_PULLUP": "Device:R",
    "SCL_PULLUP": "Device:R",
    "74HC595_SHIFT_REGISTER": "74xx:74HC595",
    "DIP_SWITCH": "Switch:SW_DIP_x08",
    "LED_ARRAY": "Device:LED_ARGB",
    "RESISTOR_NETWORK": "Device:R_Network08",
    "PROGRAMMING_HEADER": "Connector_Generic:Conn_01x14",
    "ACS712": "Sensor_Current:ACS712xLCTR-20A",
    "LM393_COMPARATOR": "Comparator:LM393",
    "TRIMMER_POTENTIOMETER": "Device:R_Potentiometer_Trim",
    "FUSE": "Device:Fuse",
    "POLYFUSE": "Device:Polyfuse",
    "RESISTOR": "Device:R",
    "CAPACITOR": "Device:C",
    "DIODE": "Device:D",
    "MOSFET": "Transistor_FET:IRLZ44N",
    "RELAY": "Relay:Relay_SPDT",
    "PWR_5V": "power:+5V",
    "PWR_3V3": "power:+3V3",
    "UART_HEADER": "Connector_Generic:Conn_01x05",
    "USB_CONNECTOR": "Connector:USB_B_Micro",
}


def spec_from_generator_kind(kind: str) -> PlacementSpec | None:
    normalized = normalize_kind(kind)
    generator_spec = KIND_SPECS.get(normalized)
    if generator_spec is None:
        return None
    xs = [pin.x for pin in generator_spec.pins] + [-5.08, 5.08]
    ys = [pin.y for pin in generator_spec.pins] + [-3.81, 3.81]
    width = max(7.0, round(max(xs) - min(xs) + 3.0, 3))
    height = max(5.0, round(max(ys) - min(ys) + 3.0, 3))
    return PlacementSpec(
        kind=normalized,
        name=generator_spec.description,
        ref_prefix=generator_spec.ref_prefix,
        width=width,
        height=height,
        category="generator_kind",
        source="kicad.generator.kicad_json_to_project.KIND_SPECS",
        lib_id=generator_spec.lib_id,
    )


def resolve_placement_spec(kind: str) -> PlacementSpec | None:
    normalized = normalize_kind(kind)
    spec = PLACER_COMPONENT_SPECS.get(normalized)
    if spec is not None:
        return replace(spec, lib_id=PLACER_KIND_LIB_IDS.get(normalized))
    return spec_from_generator_kind(normalized)


def place_catalog_components(circuit: dict[str, Any], *, columns: int = 4, x_gap: float = 35.0, y_gap: float = 40.0) -> CatalogPlacementPlan:
    raw_components = circuit.get("components")
    if not isinstance(raw_components, list):
        raise ValueError("components must be an array")
    placed: list[PlacedCatalogComponent] = []
    obstacles: list[Obstacle] = []
    counts: dict[str, int] = {}
    cursor_y = 30.0
    row_height = 0.0
    cursor_x = 25.0

    for index, raw in enumerate(raw_components):
        if not isinstance(raw, dict):
            raise ValueError(f"component {index + 1} must be an object")
        kind = normalize_kind(str(raw.get("kind") or raw.get("name") or ""))
        spec = resolve_placement_spec(kind)
        if spec is None:
            raise ValueError(f"Unsupported placement kind: {kind}")
        counts[spec.ref_prefix] = counts.get(spec.ref_prefix, 0) + 1
        ref = str(raw.get("id") or raw.get("ref") or f"{spec.ref_prefix}{counts[spec.ref_prefix]}")
        manual = isinstance(raw.get("at"), list) and len(raw["at"]) == 2
        if manual:
            at = (float(raw["at"][0]), float(raw["at"][1]))
        else:
            col = index % columns
            if col == 0 and index:
                cursor_x = 25.0
                cursor_y += row_height + y_gap
                row_height = 0.0
            at = (_snap(cursor_x + spec.width / 2), _snap(cursor_y + spec.height / 2))
            cursor_x += spec.width + x_gap
            row_height = max(row_height, spec.height)
        rotation = float(raw.get("rotation", 0))
        placed.append(
            PlacedCatalogComponent(
                ref=ref,
                kind=spec.kind,
                name=str(raw.get("value") or raw.get("name") or spec.name),
                at=at,
                rotation=rotation,
                manual_position=manual,
                spec=spec,
            )
        )
        obstacles.append(
            Obstacle(
                ref,
                round(at[0] - spec.width / 2, 3),
                round(at[1] - spec.height / 2, 3),
                round(at[0] + spec.width / 2, 3),
                round(at[1] + spec.height / 2, 3),
            )
        )
    return CatalogPlacementPlan(tuple(placed), tuple(obstacles))
