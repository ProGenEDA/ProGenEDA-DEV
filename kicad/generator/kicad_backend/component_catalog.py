from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentSpec:
    kind: str
    lib_id: str
    pins: tuple[str, ...]
    pin_local: dict[str, tuple[float, float]]
    sim_device: str | None = None
    default_value: str | None = None
    symbol_status: str = "cataloged_needs_symbol_cache"
    notes: str = ""


TWO_PIN_VERTICAL = {"1": (0.0, 3.81), "2": (0.0, -3.81)}
SOURCE_VERTICAL = {"1": (0.0, 5.08), "2": (0.0, -5.08)}
POWER_PIN = {"1": (0.0, 0.0)}
THREE_PIN_BCE = {"1": (-5.08, 0.0), "2": (0.0, 2.54), "3": (0.0, -2.54)}
THREE_PIN_GDS = {"1": (-5.08, 0.0), "2": (0.0, 2.54), "3": (0.0, -2.54)}
OPAMP_5PIN = {"1": (-5.08, -2.54), "2": (-5.08, 2.54), "3": (5.08, 0.0), "4": (0.0, -5.08), "5": (0.0, 5.08)}
DIP14_LOGIC = {str(i): (0.0, 0.0) for i in range(1, 15)}
DIP16_LOGIC = {str(i): (0.0, 0.0) for i in range(1, 17)}
CONN_2 = {"1": (0.0, -1.27), "2": (0.0, 1.27)}
CONN_3 = {"1": (0.0, -2.54), "2": (0.0, 0.0), "3": (0.0, 2.54)}
CONN_4 = {"1": (0.0, -3.81), "2": (0.0, -1.27), "3": (0.0, 1.27), "4": (0.0, 3.81)}
CONN_6 = {str(i): (0.0, (i-3.5)*1.27) for i in range(1, 7)}
CONN_8 = {str(i): (0.0, (i-4.5)*1.27) for i in range(1, 9)}

# V7 has a broad catalog but only the first five lib IDs have verified embedded
# symbol-cache blocks from KiCad source fixtures. Others are intentionally marked
# as cataloged until we collect verified symbol-cache donors.
COMPONENT_CATALOG: dict[str, ComponentSpec] = {
    # verified embedded smoke-test set
    "GND": ComponentSpec("GND", "power:GND", ("1",), POWER_PIN, None, "GND", "verified_embedded"),
    "R": ComponentSpec("R", "Device:R", ("1", "2"), TWO_PIN_VERTICAL, "R", "1k", "verified_embedded"),
    "L": ComponentSpec("L", "Device:L", ("1", "2"), TWO_PIN_VERTICAL, "L", "10m", "verified_embedded"),
    "VDC": ComponentSpec("VDC", "Simulation_SPICE:VDC", ("1", "2"), SOURCE_VERTICAL, "V", "5", "verified_embedded"),
    "VSIN": ComponentSpec("VSIN", "Simulation_SPICE:VSIN", ("1", "2"), SOURCE_VERTICAL, "V", "VSIN", "verified_embedded"),

    # passives and protection
    "C": ComponentSpec("C", "Device:C", ("1", "2"), TWO_PIN_VERTICAL, "C", "100n"),
    "CP": ComponentSpec("CP", "Device:CP", ("1", "2"), TWO_PIN_VERTICAL, "C", "10u"),
    "C_POL": ComponentSpec("C_POL", "Device:CP", ("1", "2"), TWO_PIN_VERTICAL, "C", "10u"),
    "R_POT": ComponentSpec("R_POT", "Device:R_Potentiometer", ("1", "2", "3"), {"1": (0, 3.81), "2": (0, -3.81), "3": (-5.08, 0)}, "R", "10k"),
    "FERRITE": ComponentSpec("FERRITE", "Device:Ferrite_Bead", ("1", "2"), TWO_PIN_VERTICAL, "L", "FB"),
    "FUSE": ComponentSpec("FUSE", "Device:Fuse", ("1", "2"), TWO_PIN_VERTICAL, None, "Fuse"),
    "PTC": ComponentSpec("PTC", "Device:Polyfuse", ("1", "2"), TWO_PIN_VERTICAL, None, "PTC"),
    "MOV": ComponentSpec("MOV", "Device:Varistor", ("1", "2"), TWO_PIN_VERTICAL, None, "MOV"),
    "TVS": ComponentSpec("TVS", "Device:D_TVS", ("1", "2"), TWO_PIN_VERTICAL, "D", "TVS"),

    # diodes and LEDs
    "D": ComponentSpec("D", "Device:D", ("1", "2"), TWO_PIN_VERTICAL, "D", "1N4148"),
    "DIODE": ComponentSpec("DIODE", "Device:D", ("1", "2"), TWO_PIN_VERTICAL, "D", "1N4148"),
    "LED": ComponentSpec("LED", "Device:LED", ("1", "2"), TWO_PIN_VERTICAL, "D", "LED"),
    "ZENER": ComponentSpec("ZENER", "Device:D_Zener", ("1", "2"), TWO_PIN_VERTICAL, "D", "5V1"),
    "SCHOTTKY": ComponentSpec("SCHOTTKY", "Device:D_Schottky", ("1", "2"), TWO_PIN_VERTICAL, "D", "1N5819"),
    "BRIDGE": ComponentSpec("BRIDGE", "Device:D_Bridge_+-AA", ("1", "2", "3", "4"), CONN_4, None, "Bridge"),

    # independent sources
    "VPULSE": ComponentSpec("VPULSE", "Simulation_SPICE:VPULSE", ("1", "2"), SOURCE_VERTICAL, "V", "VPULSE"),
    "VAC": ComponentSpec("VAC", "Simulation_SPICE:VSIN", ("1", "2"), SOURCE_VERTICAL, "V", "VAC"),
    "IDC": ComponentSpec("IDC", "Simulation_SPICE:IDC", ("1", "2"), SOURCE_VERTICAL, "I", "1m"),
    "ISIN": ComponentSpec("ISIN", "Simulation_SPICE:ISIN", ("1", "2"), SOURCE_VERTICAL, "I", "ISIN"),
    "IPULSE": ComponentSpec("IPULSE", "Simulation_SPICE:IPULSE", ("1", "2"), SOURCE_VERTICAL, "I", "IPULSE"),

    # transistor/FET stage
    "NPN": ComponentSpec("NPN", "Device:Q_NPN_BCE", ("1", "2", "3"), THREE_PIN_BCE, "Q", "2N3904"),
    "PNP": ComponentSpec("PNP", "Device:Q_PNP_BCE", ("1", "2", "3"), THREE_PIN_BCE, "Q", "2N3906"),
    "NMOS": ComponentSpec("NMOS", "Device:Q_NMOS_GDS", ("1", "2", "3"), THREE_PIN_GDS, "M", "NMOS"),
    "PMOS": ComponentSpec("PMOS", "Device:Q_PMOS_GDS", ("1", "2", "3"), THREE_PIN_GDS, "M", "PMOS"),
    "JFET_N": ComponentSpec("JFET_N", "Device:Q_NJFET_DSG", ("1", "2", "3"), THREE_PIN_GDS, "J", "J310"),
    "JFET_P": ComponentSpec("JFET_P", "Device:Q_PJFET_DSG", ("1", "2", "3"), THREE_PIN_GDS, "J", "PJFET"),

    # analog ICs/regulators
    "OPAMP": ComponentSpec("OPAMP", "Amplifier_Operational:LM741", ("1", "2", "3", "4", "5"), OPAMP_5PIN, None, "LM741"),
    "LM741": ComponentSpec("LM741", "Amplifier_Operational:LM741", ("1", "2", "3", "4", "5"), OPAMP_5PIN, None, "LM741"),
    "LM358": ComponentSpec("LM358", "Amplifier_Operational:LM358", tuple(str(i) for i in range(1, 9)), CONN_8, None, "LM358"),
    "LM393": ComponentSpec("LM393", "Comparator:LM393", tuple(str(i) for i in range(1, 9)), CONN_8, None, "LM393"),
    "NE555": ComponentSpec("NE555", "Timer:NE555", tuple(str(i) for i in range(1, 9)), CONN_8, None, "NE555"),
    "L7805": ComponentSpec("L7805", "Regulator_Linear:L7805", ("1", "2", "3"), CONN_3, None, "L7805"),
    "LM317": ComponentSpec("LM317", "Regulator_Linear:LM317_TO-220", ("1", "2", "3"), CONN_3, None, "LM317"),

    # logic ICs commonly used in the DLD/project track
    "74HC00": ComponentSpec("74HC00", "74xx:74HC00", tuple(str(i) for i in range(1, 15)), DIP14_LOGIC, None, "74HC00"),
    "74HC04": ComponentSpec("74HC04", "74xx:74HC04", tuple(str(i) for i in range(1, 15)), DIP14_LOGIC, None, "74HC04"),
    "74HC08": ComponentSpec("74HC08", "74xx:74HC08", tuple(str(i) for i in range(1, 15)), DIP14_LOGIC, None, "74HC08"),
    "74HC32": ComponentSpec("74HC32", "74xx:74HC32", tuple(str(i) for i in range(1, 15)), DIP14_LOGIC, None, "74HC32"),
    "74HC86": ComponentSpec("74HC86", "74xx:74HC86", tuple(str(i) for i in range(1, 15)), DIP14_LOGIC, None, "74HC86"),
    "74HC74": ComponentSpec("74HC74", "74xx:74HC74", tuple(str(i) for i in range(1, 15)), DIP14_LOGIC, None, "74HC74"),
    "74HC76": ComponentSpec("74HC76", "74xx:74HC76", tuple(str(i) for i in range(1, 17)), DIP16_LOGIC, None, "74HC76"),
    "74HC90": ComponentSpec("74HC90", "74xx:74HC90", tuple(str(i) for i in range(1, 15)), DIP14_LOGIC, None, "74HC90"),
    "74HC157": ComponentSpec("74HC157", "74xx:74HC157", tuple(str(i) for i in range(1, 17)), DIP16_LOGIC, None, "74HC157"),
    "74HC192": ComponentSpec("74HC192", "74xx:74HC192", tuple(str(i) for i in range(1, 17)), DIP16_LOGIC, None, "74HC192"),
    "4511": ComponentSpec("4511", "4xxx:4511", tuple(str(i) for i in range(1, 17)), DIP16_LOGIC, None, "4511"),
    "4017": ComponentSpec("4017", "4xxx:4017", tuple(str(i) for i in range(1, 17)), DIP16_LOGIC, None, "4017"),

    # connectors, labels and test helpers
    "CONN_2": ComponentSpec("CONN_2", "Connector:Conn_01x02_Pin", ("1", "2"), CONN_2, None, "Conn_01x02"),
    "CONN_3": ComponentSpec("CONN_3", "Connector:Conn_01x03_Pin", ("1", "2", "3"), CONN_3, None, "Conn_01x03"),
    "CONN_4": ComponentSpec("CONN_4", "Connector:Conn_01x04_Pin", ("1", "2", "3", "4"), CONN_4, None, "Conn_01x04"),
    "CONN_6": ComponentSpec("CONN_6", "Connector:Conn_01x06_Pin", tuple(str(i) for i in range(1, 7)), CONN_6, None, "Conn_01x06"),
    "CONN_8": ComponentSpec("CONN_8", "Connector:Conn_01x08_Pin", tuple(str(i) for i in range(1, 9)), CONN_8, None, "Conn_01x08"),
    "TESTPOINT": ComponentSpec("TESTPOINT", "Connector:TestPoint", ("1",), POWER_PIN, None, "TP"),
    "+5V": ComponentSpec("+5V", "power:+5V", ("1",), POWER_PIN, None, "+5V"),
    "+3V3": ComponentSpec("+3V3", "power:+3V3", ("1",), POWER_PIN, None, "+3V3"),
    "VCC": ComponentSpec("VCC", "power:VCC", ("1",), POWER_PIN, None, "VCC"),
    "GNDA": ComponentSpec("GNDA", "power:GNDA", ("1",), POWER_PIN, None, "GNDA"),
}

ALIASES = {
    "RESISTOR": "R", "CAP": "C", "CAPACITOR": "C", "ELECTROLYTIC": "CP", "INDUCTOR": "L",
    "GROUND": "GND", "DCV": "VDC", "SINE": "VSIN", "PULSE": "VPULSE",
    "Q_NPN": "NPN", "Q_PNP": "PNP", "MOS_N": "NMOS", "MOS_P": "PMOS",
}

VERIFIED_EMBEDDED_LIB_IDS = {spec.lib_id for spec in COMPONENT_CATALOG.values() if spec.symbol_status == "verified_embedded"}


def normalize_kind(kind: str) -> str:
    k = kind.strip().upper()
    return ALIASES.get(k, k)


def get_spec(kind: str) -> ComponentSpec:
    k = normalize_kind(kind)
    if k not in COMPONENT_CATALOG:
        raise KeyError(k)
    return COMPONENT_CATALOG[k]


def supported_kinds() -> list[str]:
    return sorted(COMPONENT_CATALOG)


def catalog_summary() -> dict[str, object]:
    verified = sorted(k for k, s in COMPONENT_CATALOG.items() if s.symbol_status == "verified_embedded")
    cataloged = sorted(k for k, s in COMPONENT_CATALOG.items() if s.symbol_status != "verified_embedded")
    return {
        "total_component_kinds": len(COMPONENT_CATALOG),
        "verified_embedded_kinds": verified,
        "cataloged_needs_symbol_cache_kinds": cataloged,
        "verified_embedded_lib_ids": sorted(VERIFIED_EMBEDDED_LIB_IDS),
    }
