"""Permanent, donor-only EasyEDA component catalogue.

This module deliberately contains selectors and logical facts only.  It never
contains copied EasyEDA symbol, device, footprint, or library payload data.
Those records stay in an authorized source pack and are copied at generation
time by :mod:`Easyeda.donor_source`.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


CATALOGUE_VERSION = "progen-easyeda-donor-catalogue/v2"


@dataclass(frozen=True)
class DonorSelector:
    """Ordered exact source-title candidates for one logical component."""

    titles: tuple[str, ...]
    terminal: bool = False
    pcb_required: bool = True


@dataclass(frozen=True)
class CatalogueEntry:
    """A logical component only becomes usable after its donor resolves."""

    kind: str
    aliases: tuple[str, ...]
    reference_prefix: str
    selector: DonorSelector
    category: str
    value_rule: str
    default_value: str


def _entry(
    kind: str,
    aliases: tuple[str, ...],
    reference_prefix: str,
    *titles: str,
    category: str,
    terminal: bool = False,
    pcb_required: bool = True,
    value_rule: str = "display_text",
    default_value: str | None = None,
) -> CatalogueEntry:
    return CatalogueEntry(
        kind=kind,
        aliases=aliases,
        reference_prefix=reference_prefix,
        selector=DonorSelector(titles=titles, terminal=terminal, pcb_required=pcb_required),
        category=category,
        value_rule=value_rule,
        default_value=default_value or kind,
    )


# These are source selection keys, not visual definitions.  A selector may have
# more than one proven package alternative, but the resolved title and hashes
# are recorded per generated project and locked in the support report.
CATALOGUE: dict[str, CatalogueEntry] = {
    # Basic ten.
    "R": _entry(
        "R",
        ("RES", "RESISTOR", "R_220", "R_10K_PULLUP", "R_4K7_PULLUP", "R_120"),
        "R",
        "mfr-25jt-52-10k",
        category="basic",
        value_rule="positive_number",
        default_value="10k",
    ),
    "R_POT": _entry("R_POT", ("POT", "POTENTIOMETER", "TRIMMER"), "R", "3296w-1-103_c330432", "3296w-1-101lf", category="basic", value_rule="positive_number", default_value="10k"),
    "C": _entry(
        "C",
        ("CAP", "CAPACITOR", "C_100NF_CERAMIC", "DECOUPLING_CAPACITOR"),
        "C",
        "fn43n104j500egg",
        category="basic",
        value_rule="positive_number",
        default_value="100n",
    ),
    "CAP_ELEC": _entry(
        "CAP_ELEC",
        ("CP", "C_POL", "ELECTROLYTIC_CAPACITOR", "CP_100UF"),
        "C",
        "ca45a-b-6.3v-100uf-k",
        category="basic",
        value_rule="positive_number",
        default_value="100u",
    ),
    "L": _entry("L", ("IND", "INDUCTOR", "REALIND"), "L", "ckcs5040-47uh/m", category="basic", value_rule="positive_number", default_value="47u"),
    "DIODE": _entry("DIODE", ("D", "DIODE_GENERIC", "FLYBACK_DIODE", "TVS_DIODE"), "D", "d_1n4007", "1n4148tr", category="basic"),
    "1N4007": _entry("1N4007", ("D_1N4007", "1N4007_DIODE"), "D", "1n4007rlg", "1n4007w", "d_1n4007", category="basic"),
    "1N4148": _entry("1N4148", ("D_1N4148",), "D", "1n4148tr", "1n4148w-tp", "1n4148wt_c511874", category="basic"),
    "LED": _entry("LED", ("LED_GENERIC", "LED_INDICATOR", "POWER_LED"), "LED", "204-10sdrd/s530-a3-l", "led-th_bd4.2-p2.54-fd", category="basic"),
    "SPST_SWITCH": _entry(
        "SPST_SWITCH",
        ("SWITCH", "SPST", "SW", "PUSH_BUTTON"),
        "SW",
        "key_th_3.5x6x4.3",
        category="basic",
    ),
    # Lab and digital twenty.
    "NPN": _entry("NPN", ("2N3904", "Q_NPN"), "Q", "2n3904", "2n3904ta", category="lab_digital"),
    "PNP": _entry("PNP", ("2N3906", "Q_PNP"), "Q", "2n3906", category="lab_digital"),
    "NMOS": _entry("NMOS", ("2N7000", "MOSFET"), "Q", "2n7000", "2n7000_c232838", category="lab_digital"),
    "LM7805": _entry("LM7805", ("L7805", "7805"), "U", "lm7805s/tr", "lm7805l-ta3-t", category="lab_digital"),
    "LM317": _entry("LM317", (), "U", "lm317g-aa3-r", "lm317btg", category="lab_digital"),
    "BRIDGE_RECTIFIER": _entry("BRIDGE_RECTIFIER", ("BRIDGE",), "BR", "gbu406", category="lab_digital"),
    "TRANSFORMER": _entry("TRANSFORMER", ("XFMR",), "T", "hpt225a-g", "zmpt112", category="lab_digital"),
    "FUSE": _entry("FUSE", (), "F", "fuse-smd_5-20mm", "250v 20a 玻璃管保险丝", category="lab_digital"),
    "TERMINAL_BLOCK": _entry(
        "TERMINAL_BLOCK",
        ("TERMINAL", "SCREW_TERMINAL", "SCREW_TERMINAL_2"),
        "J",
        "wj2edgv-5.08-2p",
        category="lab_digital",
    ),
    "PIN_HEADER": _entry("PIN_HEADER", ("HEADER", "HEADER_CONNECTOR"), "J", "header-male-2.54_1x4", "2.54-1*2p母", category="lab_digital"),
    "GND": _entry("GND", ("GROUND",), "#PWR", "ground-gnd", category="lab_digital", terminal=True, pcb_required=False, value_rule="fixed_terminal", default_value="GND"),
    "VCC": _entry("VCC", ("+5V", "POWER", "POWER_VCC"), "#PWR", "power-vcc", category="lab_digital", terminal=True, pcb_required=False, value_rule="fixed_terminal", default_value="VCC"),
    "LM358": _entry("LM358", (), "U", "lm358adr", "lm358n_c434570", category="lab_digital"),
    "NE555": _entry("NE555", ("555",), "U", "ne555dr", "ne555l-d08-t", category="lab_digital"),
    "74HC00": _entry("74HC00", (), "U", "sn74hc00n", "74hc00d,653", category="lab_digital"),
    "74HC04": _entry("74HC04", (), "U", "sn74hc04n", "74hc04d,653", category="lab_digital"),
    "74HC08": _entry("74HC08", (), "U", "sn74hc08n", "74hc08d,653", category="lab_digital"),
    "74HC32": _entry("74HC32", (), "U", "74hc32d,653", category="lab_digital"),
    "74HC74": _entry("74HC74", (), "U", "sn74hc74n", "74hc74d,653", category="lab_digital"),
    "74HC595": _entry("74HC595", (), "U", "sn74hc595n", "74hc595pw,118", category="lab_digital"),
    # Embedded ten.
    "ESP32_WROOM": _entry("ESP32_WROOM", ("ESP32", "ESP32_WROOM_32"), "U", "esp32-wroom-32", category="embedded"),
    "ESP12F": _entry("ESP12F", ("ESP8266", "ESP_12F"), "U", "esp-12f(esp8266mod)", category="embedded"),
    "ATMEGA328P": _entry("ATMEGA328P", ("ATMEGA328",), "U", "atmega328p-au", "atmega328p-pu", category="embedded"),
    "STM32F103C8T6": _entry("STM32F103C8T6", ("STM32F103",), "U", "stm32f103c8t6", category="embedded"),
    "CP2102": _entry("CP2102", (), "U", "cp2102-gmr", category="embedded"),
    "CH340": _entry("CH340", (), "U", "ch340e", "ch340t", category="embedded"),
    "BME280": _entry("BME280", (), "U", "bme280", category="embedded"),
    "DS3231": _entry("DS3231", (), "U", "ds3231sn#t&r", "ds3231mz+trl", category="embedded"),
    "W25Q64": _entry("W25Q64", (), "U", "w25q64jvzeiq", "w25q64fwssiq", category="embedded"),
    "SSD1306": _entry("SSD1306", ("OLED", "OLED_SSD1306"), "DS", "0.96oled模块_4p", "0.96oled_4p", category="embedded"),
    # Audited physical expansion. Selectors are exact source-device titles;
    # native symbol and footprint records remain in donor databases.
    "TEST_POINT": _entry("TEST_POINT", ("TESTPOINT", "TP"), "TP", "5010-Testpointred", category="pcb_utility"),
    "MOUNTING_HOLE_NPTH": _entry("MOUNTING_HOLE_NPTH", ("NPTH", "NPTH_HOLE"), "H", "NPTH_4.4", category="pcb_utility"),
    "MOUNTING_HOLE_PTH": _entry("MOUNTING_HOLE_PTH", ("PTH_HOLE", "SCREW_HOLE_M3"), "H", "Screw-Hole-M3", category="pcb_utility"),
    "HEADER_1X2": _entry("HEADER_1X2", ("PIN_HEADER_1X2",), "J", "hdr-m_2.54_1x2p", category="pcb_utility"),
    "HEADER_1X6": _entry("HEADER_1X6", ("PIN_HEADER_1X6", "UART_HEADER"), "J", "hdr-m_2.54_1x6p", category="pcb_utility"),
    "HEADER_2X3": _entry("HEADER_2X3", ("AVR_ISP_HEADER",), "J", "hdr-m_2.54_2x3", category="pcb_utility"),
    "HEADER_2X5_1P27": _entry("HEADER_2X5_1P27", ("SWD_HEADER", "HEADER_2X5_1_27"), "J", "1.27_2x5_3.6THR", category="pcb_utility"),
    "USB_C_RECEPTACLE": _entry("USB_C_RECEPTACLE", ("USB_C", "TYPE_C_RECEPTACLE"), "J", "type-c-31-m-12", category="power_usb"),
    "AP2112K_3V3": _entry("AP2112K_3V3", ("AP2112K",), "U", "ap2112k-3.3trg1", category="power_usb"),
    "USBLC6_2SC6": _entry("USBLC6_2SC6", ("USBLC6",), "U", "usblc6-2sc6", category="power_usb"),
    "PTC_FUSE": _entry("PTC_FUSE", ("POLYFUSE", "RESETTABLE_FUSE"), "F", "ResettableFuse-500mA", category="power_usb", value_rule="positive_number", default_value="500mA"),
    "FERRITE_BEAD": _entry("FERRITE_BEAD", ("FB", "FERRITE"), "FB", "直插磁珠", category="power_usb", value_rule="positive_number", default_value="100"),
    "SN65HVD230": _entry("SN65HVD230", ("CAN_TRANSCEIVER",), "U", "sn65hvd230dr", category="communications"),
    "SM24CANB": _entry("SM24CANB", ("CAN_TVS",), "D", "SM24CANB-02HTG", category="communications"),
    "MAX485": _entry("MAX485", ("RS485_TRANSCEIVER",), "U", "max485esa+t", category="communications"),
    "AT24C256": _entry("AT24C256", ("I2C_EEPROM",), "U", "at24c256c-sshl-t", category="i2c"),
    "PCF8574": _entry("PCF8574", ("I2C_GPIO",), "U", "pcf8574t", category="i2c"),
    "PCA9685": _entry("PCA9685", ("I2C_PWM",), "U", "PCA9685PW,118", category="i2c"),
    "ADS1115": _entry("ADS1115", ("I2C_ADC",), "U", "ads1115idgsr", category="i2c"),
}


def _token(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().upper()).strip("_")


_ALIASES: dict[str, str] = {}
for _kind, _entry_value in CATALOGUE.items():
    _ALIASES[_token(_kind)] = _kind
    for _alias in _entry_value.aliases:
        _ALIASES[_token(_alias)] = _kind


def normalize_kind(value: object) -> str:
    """Return the locked logical kind or raise a useful source-boundary error."""

    token = _token(value)
    try:
        return _ALIASES[token]
    except KeyError as exc:
        raise ValueError(f"EasyEDA donor catalogue has no supported component for {value!r}.") from exc


def get_entry(value: object) -> CatalogueEntry:
    return CATALOGUE[normalize_kind(value)]


def supported_kinds() -> list[str]:
    return sorted(CATALOGUE)


def catalogue_summary() -> dict[str, object]:
    categories: dict[str, list[str]] = {}
    for kind, entry in CATALOGUE.items():
        categories.setdefault(entry.category, []).append(kind)
    return {
        "schema": CATALOGUE_VERSION,
        "component_count": len(CATALOGUE),
        "categories": {name: sorted(kinds) for name, kinds in sorted(categories.items())},
        "components": {
            kind: {
                "aliases": list(entry.aliases),
                "reference_prefix": entry.reference_prefix,
                "category": entry.category,
                "donor_titles": list(entry.selector.titles),
                "terminal": entry.selector.terminal,
                "pcb_required": entry.selector.pcb_required,
                "value_rule": entry.value_rule,
                "default_value": entry.default_value,
            }
            for kind, entry in sorted(CATALOGUE.items())
        },
        "limits": {
            "max_input_components": 80,
            "basic_pcb_physical_components": 32,
        },
        "routing_modes": ["wire", "terminal", "combination"],
        "default_routing_mode": "combination",
        "donor_only": True,
        "fallback_symbols": "forbidden",
    }
