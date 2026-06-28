#!/usr/bin/env python3
"""Generate deterministic KiCad projects for the C01-C55 target pack.

This pack is deliberately offline and template-driven.  It exercises the
source-guided KiCad writer, the broad project-local symbol registry, and the
orthogonal router without depending on Groq or GUI automation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kicad.generator.kicad_json_to_project import KIND_SPECS, slugify, write_project_from_json  # noqa: E402


Circuit = dict[str, Any]
Component = dict[str, Any]


def c(ref: str, kind: str, pins: dict[str, str], value: str | None = None) -> Component:
    item: Component = {"id": ref, "kind": kind, "pins": pins}
    if value is not None:
        item["value"] = value
    return item


def tp(ref: str, net: str) -> Component:
    return c(ref, "TESTPOINT", {"1": net}, net)


def gnd() -> Component:
    return c("GND1", "GND", {"1": "GND"}, "GND")


def vdc(ref: str = "V1", net: str = "VCC", value: str = "5") -> Component:
    return c(ref, "VDC", {"1": net, "2": "GND"}, value)


def idc(ref: str, net: str, value: str = "1m") -> Component:
    return c(ref, "IDC", {"1": net, "2": "GND"}, value)


def vsin(ref: str, net: str, value: str = "SIN(0 1 1k)") -> Component:
    return c(ref, "VSIN", {"1": net, "2": "GND"}, value)


def rc_reset(prefix: str, net: str, drive_net: str = "VCC") -> list[Component]:
    return [
        c(f"R{prefix}", "R", {"1": drive_net, "2": net}, "10k"),
        c(f"C{prefix}", "C", {"1": net, "2": "GND"}, "100n"),
    ]


def led_load(prefix: str, net: str) -> list[Component]:
    return [
        c(f"R{prefix}", "R", {"1": net, "2": f"{net}_LED"}, "330"),
        c(f"D{prefix}", "LED", {"1": f"{net}_LED", "2": "GND"}, "LED"),
    ]


def clock_source(prefix: str, net: str, value: str = "PULSE(0 5 0 1u 1u 500u 1m)") -> list[Component]:
    return [
        c(f"VCLK{prefix}", "VPULSE", {"1": net, "2": "GND"}, value),
        c(f"RCLK{prefix}", "R", {"1": net, "2": "GND"}, "100k"),
    ]


def infer_nets(components: list[Component]) -> dict[str, str]:
    nets: dict[str, str] = {}
    for item in components:
        for net in item.get("pins", {}).values():
            nets.setdefault(str(net), f"{net} node")
    return nets


def circuit(cid: str, title: str, components: list[Component], analysis: list[str] | None = None) -> Circuit:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {
            "name": f"{cid}_{slugify(title).lower()}",
            "title": title,
            "analysis": analysis or [".tran 1u 20m", ".save all"],
        },
        "components": components,
        "nets": infer_nets(components),
        "notes": [
            "Generated offline from kicad/targets/proteus_generator_circuit_test_set_ocr.md.",
            "Broad components use project-local symbols unless the source pack contains an exact mined symbol.",
        ],
    }


def base(*extra: Component, source: Component | None = None) -> list[Component]:
    return [source or vdc(), gnd(), *extra]


def bcd_inputs(prefix: str, nets: tuple[str, str, str, str] = ("A", "B", "C", "D")) -> list[Component]:
    return [tp(f"TP{prefix}{index}", net) for index, net in enumerate(nets, 1)]


def output_bank(prefix: str, nets: list[str]) -> list[Component]:
    parts: list[Component] = []
    for index, net in enumerate(nets, 1):
        parts.extend(led_load(f"{prefix}{index}", net))
    return parts


def display_segments(prefix: str) -> list[Component]:
    return output_bank(prefix, [f"SEG_{name}" for name in ("A", "B", "C", "D", "E", "F", "G")])


def c01() -> Circuit:
    parts = base(
        c("U1", "74HC00", {"1": "STOP", "2": "LATCH_QB", "3": "LATCH_Q", "4": "RESET_N", "5": "LATCH_Q", "6": "LATCH_QB", "7": "GND", "14": "VCC"}, "74HC00"),
        c("SW1", "SW_PUSH", {"1": "STOP", "2": "GND"}, "STOP"),
        c("SW2", "SW_PUSH", {"1": "RESET_N", "2": "GND"}, "RESET"),
        c("R1", "R", {"1": "VCC", "2": "STOP"}, "10k"),
        c("R2", "R", {"1": "VCC", "2": "RESET_N"}, "10k"),
        tp("TP1", "LATCH_Q"),
        *led_load("1", "LATCH_Q"),
    )
    return circuit("C01", "Emergency stop latch with manual reset", parts)


def c02() -> Circuit:
    parts = base(
        c("U1", "74HC76", {"1": "CLK", "2": "J", "3": "K", "4": "RESET_N", "5": "Q", "6": "QB", "16": "VCC", "8": "GND"}, "74HC76"),
        tp("TP1", "J"),
        tp("TP2", "K"),
        *clock_source("1", "CLK"),
        *rc_reset("1", "RESET_N"),
        *led_load("1", "Q"),
    )
    return circuit("C02", "JK toggle fan-mode selector", parts)


def c03() -> Circuit:
    parts = base(
        c("U1", "74HC76", {"1": "CLK", "2": "VCC", "3": "VCC", "4": "RESET_N", "5": "DIV2", "6": "DIV2_N", "9": "DIV2", "10": "VCC", "11": "VCC", "12": "RESET_N", "13": "DIV4", "14": "DIV4_N", "16": "VCC", "8": "GND"}, "74HC76"),
        *clock_source("1", "CLK", "PULSE(0 5 0 1u 1u 1m 2m)"),
        *rc_reset("1", "RESET_N"),
        *led_load("1", "DIV2"),
        *led_load("2", "DIV4"),
    )
    return circuit("C03", "Dual JK divider for alarm beeper", parts)


def c04() -> Circuit:
    pins = {"1": "CLK", "9": "CLR_N", "16": "VCC", "8": "GND"}
    for i in range(6):
        pins[str(i + 2)] = f"S{i + 1}"
        pins[str(i + 10)] = f"Q{i + 1}"
    parts = base(
        c("U1", "74HC174", pins, "74HC174"),
        *clock_source("1", "CLK"),
        *rc_reset("1", "CLR_N"),
        *[tp(f"TPS{i}", f"S{i}") for i in range(1, 7)],
        *output_bank("4", [f"Q{i}" for i in range(1, 7)]),
    )
    return circuit("C04", "Six-sensor event capture register", parts)


def c05() -> Circuit:
    pins = {"1": "CLR_N", "11": "CLK", "20": "VCC", "10": "GND"}
    for i in range(8):
        pins[str(i + 2)] = f"D{i}"
        pins[str(i + 12)] = f"Q{i}"
    parts = base(
        c("U1", "74HC273", pins, "74HC273"),
        *clock_source("1", "CLK"),
        *rc_reset("1", "CLR_N"),
        *[tp(f"TPD{i}", f"D{i}") for i in range(8)],
        *output_bank("5", [f"Q{i}" for i in range(8)]),
    )
    return circuit("C05", "Eight-bit output latch for appliance control", parts)


def c06() -> Circuit:
    parts = base(
        c("U1", "74HC595", {"1": "QB", "2": "QC", "3": "QD", "4": "QE", "5": "QF", "6": "QG", "7": "QH", "8": "GND", "9": "QH_SER", "10": "CLR_N", "11": "SRCLK", "12": "RCLK", "13": "OE_N", "14": "SER", "15": "QA", "16": "VCC"}, "74HC595"),
        tp("TPSER", "SER"),
        *clock_source("S", "SRCLK"),
        *clock_source("R", "RCLK", "PULSE(0 5 0 1u 1u 4m 8m)"),
        *rc_reset("1", "CLR_N"),
        c("ROE", "R", {"1": "OE_N", "2": "GND"}, "10k"),
        *output_bank("6", ["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"]),
    )
    return circuit("C06", "Serial LED pattern output expander", parts)


def c07() -> Circuit:
    pins = {"1": "PL_N", "2": "CLK", "7": "QH", "8": "GND", "9": "QH_N", "10": "SER", "15": "CLK_INH", "16": "VCC"}
    for index, name in enumerate("ABCDEFGH", 3):
        pins[str(index)] = f"SW_{name}"
    parts = base(
        c("U1", "74HC165", pins, "74HC165"),
        *clock_source("1", "CLK"),
        c("RINH", "R", {"1": "CLK_INH", "2": "GND"}, "10k"),
        tp("TPSER", "SER"),
        *[c(f"SW{name}", "SW_PUSH", {"1": f"SW_{name}", "2": "VCC"}, f"SW{name}") for name in "ABCDEFGH"],
        *[c(f"RP{name}", "R", {"1": f"SW_{name}", "2": "GND"}, "10k") for name in "ABCDEFGH"],
        *led_load("7", "QH"),
    )
    return circuit("C07", "Parallel switch input serializer", parts)


def c08() -> Circuit:
    parts = base(
        c("U1", "74HC595", {"8": "GND", "10": "CLR_N", "11": "CLK", "12": "LATCH", "13": "GND", "14": "SER_IN", "15": "QA", "16": "VCC"}, "74HC595"),
        c("U2", "74HC165", {"1": "LOAD_N", "2": "CLK", "3": "QA", "4": "QB", "5": "QC", "6": "QD", "7": "SER_OUT", "8": "GND", "10": "SER_IN", "15": "GND", "16": "VCC"}, "74HC165"),
        *clock_source("1", "CLK"),
        *clock_source("2", "LATCH", "PULSE(0 5 0 1u 1u 8m 16m)"),
        *rc_reset("1", "CLR_N"),
        *rc_reset("2", "LOAD_N"),
        tp("TPIN", "SER_IN"),
        *led_load("8", "SER_OUT"),
    )
    return circuit("C08", "Serial-in parallel-out to parallel-in loopback tester", parts)


def c09() -> Circuit:
    parts = base(
        c("U1", "74HC595", {"8": "GND", "10": "CLR_N", "11": "SRCLK", "12": "RCLK", "13": "GND", "14": "SER", "15": "QA", "16": "VCC", "1": "QB", "2": "QC", "3": "QD"}, "74HC595"),
        c("U2", "74HC273", {"1": "CLR_N", "2": "QA", "3": "QB", "4": "QC", "5": "QD", "10": "GND", "11": "STORE", "12": "LQ0", "13": "LQ1", "14": "LQ2", "15": "LQ3", "20": "VCC"}, "74HC273"),
        tp("TPSER", "SER"),
        *clock_source("S", "SRCLK"),
        *clock_source("R", "RCLK"),
        *clock_source("T", "STORE", "PULSE(0 5 0 1u 1u 10m 20m)"),
        *rc_reset("1", "CLR_N"),
        *output_bank("9", ["LQ0", "LQ1", "LQ2", "LQ3"]),
    )
    return circuit("C09", "Register-stored output bank with serial update", parts)


def c10() -> Circuit:
    parts = base(
        c("U1", "74HC165", {"1": "LOAD_N", "2": "CLK", "3": "ALARM_A", "4": "ALARM_B", "5": "ALARM_C", "7": "SER_DATA", "8": "GND", "15": "GND", "16": "VCC"}, "74HC165"),
        c("U2", "74HC273", {"1": "CLR_N", "2": "SER_DATA", "3": "ALARM_A", "4": "ALARM_B", "5": "ALARM_C", "10": "GND", "11": "STORE", "12": "LATCHED", "20": "VCC"}, "74HC273"),
        *clock_source("1", "CLK"),
        *clock_source("2", "STORE"),
        *rc_reset("1", "LOAD_N"),
        *rc_reset("2", "CLR_N"),
        *output_bank("10", ["LATCHED", "ALARM_A", "ALARM_B", "ALARM_C"]),
    )
    return circuit("C10", "Input snapshot and stored alarm output", parts)


def c11() -> Circuit:
    parts = base(
        c("U1", "7490", {"1": "CLK", "2": "RESET", "3": "RESET", "7": "GND", "11": "QA", "12": "QB", "9": "QC", "8": "QD", "14": "VCC"}, "7490"),
        c("U2", "4511", {"1": "QB", "2": "QC", "6": "QD", "7": "QA", "8": "GND", "9": "SEG_E", "10": "SEG_D", "11": "SEG_C", "12": "SEG_B", "13": "SEG_A", "14": "SEG_G", "15": "SEG_F", "16": "VCC"}, "4511"),
        *clock_source("1", "CLK"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
        *display_segments("11"),
    )
    return circuit("C11", "Single-digit decimal event counter", parts)


def c12() -> Circuit:
    parts = base(
        c("U1", "74HC192", {"1": "QB", "2": "QA", "3": "DOWN_CLK", "4": "UP_CLK", "5": "QC", "6": "QD", "7": "GND", "8": "VCC", "9": "LOAD_N", "10": "CLR", "11": "P0", "12": "P1", "13": "P2", "14": "P3", "15": "BORROW", "16": "CARRY"}, "74HC192"),
        *clock_source("U", "UP_CLK"),
        *clock_source("D", "DOWN_CLK", "PULSE(0 5 0 1u 1u 4m 8m)"),
        *rc_reset("1", "LOAD_N"),
        c("RCLR", "R", {"1": "CLR", "2": "GND"}, "10k"),
        *bcd_inputs("12", ("P0", "P1", "P2", "P3")),
        *output_bank("12", ["QA", "QB", "QC", "QD", "CARRY"]),
    )
    return circuit("C12", "Presettable production batch counter", parts)


def c13() -> Circuit:
    parts = base(
        c("U1", "74HC163", {"1": "CLR_N", "2": "CLK", "3": "D0", "4": "D1", "5": "D2", "6": "D3", "7": "ENP", "8": "GND", "9": "LOAD_N", "10": "ENT", "11": "Q3", "12": "Q2", "13": "Q1", "14": "Q0", "15": "RCO", "16": "VCC"}, "74HC163"),
        *clock_source("1", "CLK"),
        *rc_reset("1", "CLR_N"),
        c("REN1", "R", {"1": "ENP", "2": "VCC"}, "10k"),
        c("REN2", "R", {"1": "ENT", "2": "VCC"}, "10k"),
        *rc_reset("2", "LOAD_N"),
        *output_bank("13", ["Q0", "Q1", "Q2", "Q3", "RCO"]),
    )
    return circuit("C13", "Four-bit synchronous binary counter monitor", parts)


def c14() -> Circuit:
    parts = base(
        c("U1", "74HC163", {"1": "CLR_N", "2": "CLK", "7": "VCC", "8": "GND", "9": "LOAD_N", "10": "VCC", "11": "Q3", "12": "Q2", "13": "Q1", "14": "Q0", "15": "RCO", "16": "VCC"}, "74HC163"),
        c("U2", "74HC00", {"1": "Q3", "2": "Q1", "3": "CLR_DECODE", "7": "GND", "14": "VCC"}, "74HC00"),
        c("U3", "74HC04", {"1": "CLR_DECODE", "2": "CLR_N", "7": "GND", "14": "VCC"}, "74HC04"),
        *clock_source("1", "CLK"),
        c("RLOAD", "R", {"1": "LOAD_N", "2": "VCC"}, "10k"),
        *output_bank("14", ["Q0", "Q1", "Q2", "Q3"]),
    )
    return circuit("C14", "Modulo-N controller with synchronous clear", parts)


def c15() -> Circuit:
    parts = base(
        c("U1", "74HC193", {"1": "QB", "2": "QA", "3": "DOWN", "4": "UP", "5": "QC", "6": "QD", "7": "GND", "8": "VCC", "9": "LOAD_N", "10": "CLR", "15": "BORROW", "16": "CARRY"}, "74HC193"),
        c("U2", "4511", {"1": "QB", "2": "QC", "6": "QD", "7": "QA", "8": "GND", "9": "SEG_E", "10": "SEG_D", "11": "SEG_C", "12": "SEG_B", "13": "SEG_A", "14": "SEG_G", "15": "SEG_F", "16": "VCC"}, "4511"),
        *clock_source("U", "UP"),
        *clock_source("D", "DOWN"),
        c("RLOAD", "R", {"1": "LOAD_N", "2": "VCC"}, "10k"),
        c("RCLR", "R", {"1": "CLR", "2": "GND"}, "10k"),
        *display_segments("15"),
    )
    return circuit("C15", "Up/down people counter display driver", parts)


def c16() -> Circuit:
    parts = base(
        c("U1", "74HC193", {"1": "QB", "2": "QA", "3": "DOWN", "4": "UP", "5": "QC", "6": "QD", "7": "GND", "8": "VCC", "9": "LOAD_N", "10": "CLR", "15": "BORROW", "16": "CARRY"}, "74HC193"),
        c("U2", "74HC85", {"1": "QB", "2": "QA", "3": "QC", "4": "QD", "5": "LIM0", "6": "LIM1", "7": "LIM2", "8": "GND", "9": "LIM3", "10": "EQ", "11": "GT", "12": "LT", "16": "VCC"}, "74HC85"),
        *clock_source("U", "UP"),
        *clock_source("D", "DOWN"),
        c("RLOAD", "R", {"1": "LOAD_N", "2": "VCC"}, "10k"),
        c("RCLR", "R", {"1": "CLR", "2": "GND"}, "10k"),
        *bcd_inputs("16", ("LIM0", "LIM1", "LIM2", "LIM3")),
        *output_bank("16", ["EQ", "GT", "LT"]),
    )
    return circuit("C16", "Bidirectional position counter with limit compare", parts)


def c17() -> Circuit:
    parts = base(
        c("U1", "4017", {"1": "Q5", "2": "Q1", "3": "Q0", "4": "Q2", "5": "Q6", "6": "Q7", "7": "Q3", "8": "GND", "9": "Q8", "10": "Q4", "11": "Q9", "12": "CARRY", "13": "CLK_INH", "14": "CLK", "15": "RESET", "16": "VCC"}, "4017"),
        *clock_source("1", "CLK"),
        c("RINH", "R", {"1": "CLK_INH", "2": "GND"}, "10k"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
        *output_bank("17", [f"Q{i}" for i in range(10)]),
    )
    return circuit("C17", "One-of-ten step sequencer", parts)


def divider(kind: str, cid: str, title: str, outputs: list[str], pins: dict[str, str]) -> Circuit:
    parts = base(
        c("U1", kind, pins, kind),
        *clock_source("1", "CLK"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
        *output_bank(cid, outputs),
    )
    return circuit(cid, title, parts)


def c18() -> Circuit:
    pins = {"1": "Q12", "2": "Q11", "3": "Q10", "4": "Q9", "5": "Q8", "6": "Q7", "7": "Q6", "8": "GND", "9": "Q5", "10": "Q4", "11": "CLK", "12": "RESET", "13": "Q3", "14": "Q2", "15": "Q1", "16": "VCC"}
    return divider("4020", "C18", "Long-period divider for slow status beacon", ["Q8", "Q10", "Q12"], pins)


def c19() -> Circuit:
    pins = {"1": "CLK", "2": "RESET", "3": "Q1", "4": "Q2", "5": "Q3", "6": "Q4", "7": "GND", "8": "Q5", "9": "Q6", "10": "Q7", "14": "VCC"}
    return divider("4024", "C19", "Audio-rate divider for tone selection", ["Q3", "Q5", "Q7"], pins)


def c20() -> Circuit:
    pins = {"1": "Q11", "2": "Q12", "3": "Q13", "4": "Q6", "5": "Q5", "6": "Q7", "7": "Q4", "8": "GND", "9": "Q3", "10": "Q2", "11": "CLK", "12": "RESET", "13": "Q1", "14": "Q8", "15": "Q9", "16": "VCC"}
    return divider("4040", "C20", "Multi-second delay counter", ["Q8", "Q11", "Q13"], pins)


def c21() -> Circuit:
    parts = base(
        c("U1", "4060", {"1": "Q12", "2": "Q13", "3": "Q14", "4": "Q6", "5": "Q5", "6": "Q7", "7": "Q4", "8": "GND", "9": "OSC_IN", "10": "OSC_OUT", "11": "OSC_RC", "12": "RESET", "13": "Q9", "14": "Q8", "15": "Q10", "16": "VCC"}, "4060"),
        c("R1", "R", {"1": "OSC_OUT", "2": "OSC_RC"}, "1M"),
        c("C1", "C", {"1": "OSC_RC", "2": "GND"}, "100p"),
        c("C2", "C", {"1": "OSC_IN", "2": "GND"}, "100p"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
        *output_bank("21", ["Q12", "Q13", "Q14"]),
    )
    return circuit("C21", "Crystal-style oscillator divider using 4060", parts)


def c22() -> Circuit:
    parts = base(
        c("U1", "4518", {"1": "CLK_A", "2": "EN_A", "3": "QA0", "4": "QA1", "5": "QA2", "6": "QA3", "7": "RESET_A", "8": "GND", "9": "RESET_B", "10": "QB3", "11": "QB2", "12": "QB1", "13": "QB0", "14": "EN_B", "15": "CLK_B", "16": "VCC"}, "4518"),
        *clock_source("A", "CLK_A"),
        *clock_source("B", "CLK_B"),
        c("REN1", "R", {"1": "EN_A", "2": "VCC"}, "10k"),
        c("REN2", "R", {"1": "EN_B", "2": "VCC"}, "10k"),
        c("RRA", "R", {"1": "RESET_A", "2": "GND"}, "10k"),
        c("RRB", "R", {"1": "RESET_B", "2": "GND"}, "10k"),
        *output_bank("22", ["QA0", "QA1", "QA2", "QA3", "QB0", "QB1", "QB2", "QB3"]),
    )
    return circuit("C22", "Dual BCD pulse counter", parts)


def c23() -> Circuit:
    parts = base(
        c("U1", "4520", {"1": "CLK_A", "2": "EN_A", "3": "QA0", "4": "QA1", "5": "QA2", "6": "QA3", "7": "RESET_A", "8": "GND", "9": "RESET_B", "10": "QB3", "11": "QB2", "12": "QB1", "13": "QB0", "14": "EN_B", "15": "CLK_B", "16": "VCC"}, "4520"),
        *clock_source("A", "CLK_A"),
        *clock_source("B", "CLK_B"),
        c("REN1", "R", {"1": "EN_A", "2": "VCC"}, "10k"),
        c("REN2", "R", {"1": "EN_B", "2": "VCC"}, "10k"),
        c("RRA", "R", {"1": "RESET_A", "2": "GND"}, "10k"),
        c("RRB", "R", {"1": "RESET_B", "2": "GND"}, "10k"),
        *output_bank("23", ["QA0", "QA1", "QA2", "QA3", "QB0", "QB1", "QB2", "QB3"]),
    )
    return circuit("C23", "Dual binary event divider", parts)


def display_driver(cid: str, title: str, kind: str) -> Circuit:
    parts = base(
        c("U1", kind, {"1": "B", "2": "C", "6": "D", "7": "A", "8": "GND", "9": "SEG_E", "10": "SEG_D", "11": "SEG_C", "12": "SEG_B", "13": "SEG_A", "14": "SEG_G", "15": "SEG_F", "16": "VCC"}, kind),
        *bcd_inputs(cid, ("A", "B", "C", "D")),
        *display_segments(cid),
    )
    return circuit(cid, title, parts)


def c24() -> Circuit:
    return display_driver("C24", "Seven-segment BCD display using 4511", "4511")


def c25() -> Circuit:
    return display_driver("C25", "Common-anode BCD display driver", "74HC47")


def c26() -> Circuit:
    return display_driver("C26", "Segment display driver with active-high outputs", "74HC48")


def c27() -> Circuit:
    parts = base(
        c("U1", "74HC157", {"1": "SEL", "2": "A0", "3": "B0", "4": "Y0", "5": "A1", "6": "B1", "7": "Y1", "8": "GND", "9": "Y2", "10": "B2", "11": "A2", "12": "Y3", "13": "B3", "14": "A3", "15": "EN_N", "16": "VCC"}, "74HC157"),
        tp("TPSEL", "SEL"),
        c("REN", "R", {"1": "EN_N", "2": "GND"}, "10k"),
        *[tp(f"TPA{i}", f"A{i}") for i in range(4)],
        *[tp(f"TPB{i}", f"B{i}") for i in range(4)],
        *output_bank("27", [f"Y{i}" for i in range(4)]),
    )
    return circuit("C27", "Two-source sensor bus selector", parts)


def c28() -> Circuit:
    parts = base(
        c("U1", "74HC151", {"1": "D3", "2": "D2", "3": "D1", "4": "D0", "5": "Y", "6": "Y_N", "7": "EN_N", "8": "GND", "9": "S2", "10": "S1", "11": "S0", "12": "D7", "13": "D6", "14": "D5", "15": "D4", "16": "VCC"}, "74HC151"),
        *[tp(f"TPD{i}", f"D{i}") for i in range(8)],
        *bcd_inputs("28", ("S0", "S1", "S2", "EN_N")),
        c("REN", "R", {"1": "EN_N", "2": "GND"}, "10k"),
        *led_load("28", "Y"),
    )
    return circuit("C28", "Eight-channel alarm selector", parts)


def c29() -> Circuit:
    parts = base(
        c("U1", "74HC153", {"1": "EN1_N", "2": "S1", "3": "A3", "4": "A2", "5": "A1", "6": "A0", "7": "Y1", "8": "GND", "9": "Y2", "10": "B0", "11": "B1", "12": "B2", "13": "B3", "14": "S0", "15": "EN2_N", "16": "VCC"}, "74HC153"),
        *[tp(f"TPA{i}", f"A{i}") for i in range(4)],
        *[tp(f"TPB{i}", f"B{i}") for i in range(4)],
        tp("TPS0", "S0"),
        tp("TPS1", "S1"),
        c("REN1", "R", {"1": "EN1_N", "2": "GND"}, "10k"),
        c("REN2", "R", {"1": "EN2_N", "2": "GND"}, "10k"),
        *output_bank("29", ["Y1", "Y2"]),
    )
    return circuit("C29", "Dual four-input data selector", parts)


def c30() -> Circuit:
    parts = base(
        c("U1", "4051", {"1": "CH4", "2": "CH6", "3": "COMMON", "4": "CH7", "5": "CH5", "6": "EN_N", "7": "VEE", "8": "GND", "9": "S2", "10": "S1", "11": "S0", "12": "CH3", "13": "CH0", "14": "CH1", "15": "CH2", "16": "VCC"}, "4051"),
        *[c(f"RS{i}", "R", {"1": f"CH{i}", "2": "GND"}, f"{i + 1}k") for i in range(8)],
        c("ROUT", "R", {"1": "COMMON", "2": "GND"}, "10k"),
        *bcd_inputs("30", ("S0", "S1", "S2", "EN_N")),
    )
    return circuit("C30", "Eight-channel analog sensor scanner", parts)


def c31() -> Circuit:
    parts = base(
        c("U1", "74HC85", {"1": "A1", "2": "B1", "3": "A2", "4": "B2", "5": "A3", "6": "B3", "7": "LT_IN", "8": "GND", "9": "EQ_IN", "10": "GT_IN", "11": "GT", "12": "EQ", "13": "LT", "14": "B0", "15": "A0", "16": "VCC"}, "74HC85"),
        *bcd_inputs("31A", ("A0", "A1", "A2", "A3")),
        *bcd_inputs("31B", ("B0", "B1", "B2", "B3")),
        c("REQ", "R", {"1": "EQ_IN", "2": "VCC"}, "10k"),
        c("RLT", "R", {"1": "LT_IN", "2": "GND"}, "10k"),
        c("RGT", "R", {"1": "GT_IN", "2": "GND"}, "10k"),
        *output_bank("31", ["EQ", "GT", "LT"]),
    )
    return circuit("C31", "Four-bit password equality checker", parts)


def c32() -> Circuit:
    parts = base(
        c("U1", "4063", {"1": "A1", "2": "B1", "3": "A2", "4": "B2", "5": "A3", "6": "B3", "7": "LT_IN", "8": "GND", "9": "EQ_IN", "10": "GT_IN", "11": "GT", "12": "EQ", "13": "LT", "14": "B0", "15": "A0", "16": "VCC"}, "4063"),
        *bcd_inputs("32A", ("A0", "A1", "A2", "A3")),
        *bcd_inputs("32B", ("B0", "B1", "B2", "B3")),
        c("REQ", "R", {"1": "EQ_IN", "2": "VCC"}, "10k"),
        c("RLT", "R", {"1": "LT_IN", "2": "GND"}, "10k"),
        c("RGT", "R", {"1": "GT_IN", "2": "GND"}, "10k"),
        *output_bank("32", ["EQ", "GT", "LT"]),
    )
    return circuit("C32", "Cascadable magnitude comparator block", parts)


def adder(cid: str, title: str, kind: str) -> Circuit:
    parts = base(
        c("U1", kind, {"1": "A1", "2": "B1", "3": "S1", "4": "A2", "5": "B2", "6": "S2", "7": "GND", "8": "CIN", "9": "COUT", "10": "S3", "11": "B3", "12": "A3", "13": "S4", "14": "B4", "15": "A4", "16": "VCC"}, kind),
        *bcd_inputs(cid + "A", ("A1", "A2", "A3", "A4")),
        *bcd_inputs(cid + "B", ("B1", "B2", "B3", "B4")),
        tp("TPCIN", "CIN"),
        *output_bank(cid, ["S1", "S2", "S3", "S4", "COUT"]),
    )
    return circuit(cid, title, parts)


def c33() -> Circuit:
    return adder("C33", "Four-bit adder with carry indicator", "74HC283")


def c34() -> Circuit:
    return adder("C34", "CMOS adder for small calculator input", "4008")


def c35() -> Circuit:
    parts = base(
        c("U1", "74HC08", {"1": "DOOR_OK", "2": "GUARD_OK", "3": "SAFE_OK", "7": "GND", "14": "VCC"}, "74HC08"),
        c("U2", "74HC32", {"1": "SAFE_OK", "2": "OVERRIDE", "3": "MOTOR_ENABLE", "7": "GND", "14": "VCC"}, "74HC32"),
        c("U3", "74HC04", {"1": "FAULT", "2": "FAULT_N", "7": "GND", "14": "VCC"}, "74HC04"),
        *[tp(f"TP{name}", name) for name in ("DOOR_OK", "GUARD_OK", "OVERRIDE", "FAULT")],
        *led_load("35", "MOTOR_ENABLE"),
    )
    return circuit("C35", "Generic safety interlock logic", parts)


def c36() -> Circuit:
    parts = base(
        c("U1", "74HC86", {"1": "A", "2": "B", "3": "PARITY", "4": "C", "5": "D", "6": "PARITY2", "7": "GND", "14": "VCC"}, "74HC86"),
        c("U2", "74HC266", {"1": "PARITY", "2": "PARITY2", "3": "AGREE", "7": "GND", "14": "VCC"}, "74HC266"),
        *bcd_inputs("36", ("A", "B", "C", "D")),
        *output_bank("36", ["PARITY", "AGREE"]),
    )
    return circuit("C36", "Parity and agreement checker", parts)


def c37() -> Circuit:
    parts = base(
        c("U1", "74HC00", {"1": "OPEN_CMD", "2": "CLOSED_LIMIT", "3": "OPEN_DRV_N", "4": "CLOSE_CMD", "5": "OPEN_LIMIT", "6": "CLOSE_DRV_N", "7": "GND", "14": "VCC"}, "74HC00"),
        c("U2", "74HC08", {"1": "OPEN_DRV_N", "2": "FAULT_N", "3": "OPEN_DRV", "4": "CLOSE_DRV_N", "5": "FAULT_N", "6": "CLOSE_DRV", "7": "GND", "14": "VCC"}, "74HC08"),
        c("U3", "74HC04", {"1": "FAULT", "2": "FAULT_N", "7": "GND", "14": "VCC"}, "74HC04"),
        *[tp(f"TP{name}", name) for name in ("OPEN_CMD", "CLOSE_CMD", "OPEN_LIMIT", "CLOSED_LIMIT", "FAULT")],
        *output_bank("37", ["OPEN_DRV", "CLOSE_DRV"]),
    )
    return circuit("C37", "Garage door direction controller", parts)


def c38() -> Circuit:
    parts = base(
        c("U1", "4017", {"3": "Q0", "2": "Q1", "4": "Q2", "7": "Q3", "8": "GND", "13": "GND", "14": "CLK", "15": "RESET", "16": "VCC"}, "4017"),
        c("U2", "74HC00", {"1": "Q3", "2": "Q1", "3": "RESET", "7": "GND", "14": "VCC"}, "74HC00"),
        *clock_source("1", "CLK"),
        *output_bank("38", ["Q0", "Q1", "Q2"]),
    )
    return circuit("C38", "Digital traffic-light stepper", parts)


def c39() -> Circuit:
    parts = base(
        c("U1", "7490", {"1": "CLK", "2": "RESET", "3": "RESET", "7": "GND", "8": "QD", "9": "QC", "11": "QA", "12": "QB", "14": "VCC"}, "7490"),
        c("U2", "74HC273", {"1": "CLR_N", "2": "QA", "3": "QB", "4": "QC", "5": "QD", "10": "GND", "11": "ROLL", "12": "LQA", "13": "LQB", "14": "LQC", "15": "LQD", "20": "VCC"}, "74HC273"),
        *clock_source("1", "CLK"),
        *clock_source("2", "ROLL"),
        *rc_reset("1", "CLR_N"),
        *output_bank("39", ["LQA", "LQB", "LQC", "LQD"]),
    )
    return circuit("C39", "Digital dice counter latch", parts)


def c40() -> Circuit:
    parts = base(
        c("U1", "4024", {"1": "CLK", "2": "RESET", "3": "Q1", "4": "Q2", "5": "Q3", "6": "Q4", "7": "GND", "8": "Q5", "9": "Q6", "10": "Q7", "14": "VCC"}, "4024"),
        c("U2", "74HC175", {"1": "CLR_N", "2": "Q1", "3": "LQ1", "4": "Q2", "5": "LQ2", "6": "Q3", "7": "LQ3", "8": "GND", "9": "CLK_LATCH", "16": "VCC"}, "74HC175"),
        *clock_source("1", "CLK"),
        *clock_source("2", "CLK_LATCH"),
        *rc_reset("1", "CLR_N"),
        *output_bank("40", ["LQ1", "LQ2", "LQ3"]),
    )
    return circuit("C40", "Frequency divider and sample latch", parts)


def c41() -> Circuit:
    parts = base(
        c("U1", "74HC86", {"1": "ENC_A", "2": "ENC_B", "3": "DIR", "7": "GND", "14": "VCC"}, "74HC86"),
        c("U2", "74HC193", {"1": "QB", "2": "QA", "3": "DOWN", "4": "UP", "5": "QC", "6": "QD", "7": "GND", "8": "VCC", "9": "VCC", "10": "GND"}, "74HC193"),
        c("U3", "74HC08", {"1": "ENC_A", "2": "DIR", "3": "UP", "4": "ENC_A", "5": "DIR_N", "6": "DOWN", "7": "GND", "14": "VCC"}, "74HC08"),
        c("U4", "74HC04", {"1": "DIR", "2": "DIR_N", "7": "GND", "14": "VCC"}, "74HC04"),
        tp("TPA", "ENC_A"),
        tp("TPB", "ENC_B"),
        *output_bank("41", ["QA", "QB", "QC", "QD"]),
    )
    return circuit("C41", "Rotary encoder up/down counter", parts)


def c42() -> Circuit:
    parts = base(
        c("U1", "74HC165", {"1": "LOAD_N", "2": "CLK", "7": "SER_KEY", "8": "GND", "15": "GND", "16": "VCC"}, "74HC165"),
        c("U2", "74HC85", {"1": "K1", "2": "P1", "3": "K2", "4": "P2", "5": "K3", "6": "P3", "7": "GND", "8": "GND", "9": "VCC", "10": "GND", "11": "GT", "12": "UNLOCK", "13": "LT", "14": "P0", "15": "K0", "16": "VCC"}, "74HC85"),
        *clock_source("1", "CLK"),
        *rc_reset("1", "LOAD_N"),
        *[tp(f"TPK{i}", f"K{i}") for i in range(4)],
        *[c(f"RP{i}", "R", {"1": f"P{i}", "2": "VCC" if i in {1, 3} else "GND"}, "10k") for i in range(4)],
        *led_load("42", "UNLOCK"),
    )
    return circuit("C42", "Small digital lock with serial key input", parts)


def c43() -> Circuit:
    parts = base(
        c("U1", "74HC163", {"1": "RESET_N", "2": "CLK", "7": "VCC", "8": "GND", "9": "VCC", "10": "VCC", "11": "Q3", "12": "Q2", "13": "Q1", "14": "Q0", "15": "RCO", "16": "VCC"}, "74HC163"),
        c("U2", "74HC04", {"1": "POR", "2": "RESET_N", "7": "GND", "14": "VCC"}, "74HC04"),
        c("R1", "R", {"1": "VCC", "2": "POR"}, "100k"),
        c("C1", "C", {"1": "POR", "2": "GND"}, "1u"),
        *clock_source("1", "CLK"),
        *output_bank("43", ["Q0", "Q1", "Q2", "Q3"]),
    )
    return circuit("C43", "Power-on reset delay for synchronous counter", parts)


def c44() -> Circuit:
    parts = base(
        c("U1", "4013", {"1": "Q", "2": "QB", "3": "TOUCH_EDGE", "4": "RESET", "5": "D", "6": "SET", "7": "GND", "14": "VCC"}, "4013"),
        c("C1", "C", {"1": "TOUCH", "2": "GND"}, "10n"),
        c("R1", "R", {"1": "TOUCH", "2": "VCC"}, "1M"),
        c("C2", "C", {"1": "TOUCH_EDGE", "2": "TOUCH"}, "100n"),
        c("R2", "R", {"1": "TOUCH_EDGE", "2": "GND"}, "100k"),
        c("RD", "R", {"1": "D", "2": "VCC"}, "10k"),
        c("RS", "R", {"1": "SET", "2": "GND"}, "10k"),
        c("RR", "R", {"1": "RESET", "2": "GND"}, "10k"),
        *led_load("44", "Q"),
    )
    return circuit("C44", "Capacitive touch latch", parts)


def c45() -> Circuit:
    parts = base(
        c("U1", "LM393", {"1": "BEAM_LOW", "2": "IR_REF", "3": "IR_SENSE", "4": "GND", "8": "VCC"}, "LM393"),
        c("U2", "4518", {"1": "BEAM_LOW", "2": "VCC", "3": "QA0", "4": "QA1", "5": "QA2", "6": "QA3", "7": "RESET", "8": "GND", "16": "VCC"}, "4518"),
        c("R1", "R", {"1": "VCC", "2": "IR_SENSE"}, "10k"),
        c("D1", "LED", {"1": "IR_SENSE", "2": "GND"}, "IR LED"),
        c("R2", "R", {"1": "VCC", "2": "IR_REF"}, "47k"),
        c("R3", "R", {"1": "IR_REF", "2": "GND"}, "10k"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
        *output_bank("45", ["QA0", "QA1", "QA2", "QA3"]),
    )
    return circuit("C45", "IR beam break counter", parts)


def c46() -> Circuit:
    parts = base(
        c("U1", "4017", {"3": "F0", "2": "F1", "4": "F2", "7": "F3", "8": "GND", "13": "GND", "14": "CLK", "15": "RESET", "16": "VCC"}, "4017"),
        c("U2", "4063", {"1": "F0", "2": "REQ0", "3": "F1", "4": "REQ1", "5": "F2", "6": "REQ2", "7": "GND", "8": "GND", "9": "VCC", "10": "GND", "11": "ABOVE", "12": "AT_FLOOR", "13": "BELOW", "14": "REQ3", "15": "F3", "16": "VCC"}, "4063"),
        *clock_source("1", "CLK"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
        *bcd_inputs("46", ("REQ0", "REQ1", "REQ2", "REQ3")),
        *output_bank("46", ["AT_FLOOR", "ABOVE", "BELOW"]),
    )
    return circuit("C46", "Elevator floor sequencer with compare", parts)


def c47() -> Circuit:
    parts = base(
        c("U1", "4017", {"3": "Q0", "2": "Q1", "4": "Q2", "7": "Q3", "8": "GND", "13": "GND", "14": "CLK", "15": "RESET", "16": "VCC"}, "4017"),
        *clock_source("1", "CLK"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
    )
    for i in range(4):
        parts.extend([c(f"Q{i+1}", "NPN", {"1": f"Q{i}", "2": f"LED_DRV{i}", "3": "GND"}, "2N3904"), *led_load(f"47{i}", f"LED_DRV{i}")])
    return circuit("C47", "Running light with transistor output stages", parts)


def c48() -> Circuit:
    parts = base(
        c("U1", "74HC595", {"8": "GND", "10": "CLR_N", "11": "CLK", "12": "LATCH", "13": "OE_N", "14": "SER", "15": "QA", "1": "QB", "2": "QC", "3": "QD", "16": "VCC"}, "74HC595"),
        c("Q1", "PNP", {"1": "OE_N", "2": "VCC", "3": "LED_SUPPLY"}, "2N3906"),
        tp("TPSER", "SER"),
        *clock_source("1", "CLK"),
        *clock_source("2", "LATCH"),
        *rc_reset("1", "CLR_N"),
        c("ROE", "R", {"1": "OE_N", "2": "GND"}, "10k"),
        *[c(f"R48{i}", "R", {"1": "LED_SUPPLY", "2": f"LED{i}"}, "330") for i in range(4)],
        *[c(f"D48{i}", "LED", {"1": f"LED{i}", "2": net}, "LED") for i, net in enumerate(["QA", "QB", "QC", "QD"])],
    )
    return circuit("C48", "Shift-register LED bank with high-side enable", parts)


def c49() -> Circuit:
    parts = base(
        c("U1", "LM741", {"2": "THRESH", "3": "SENSE", "4": "GND", "6": "RESET", "7": "VCC"}, "LM741"),
        c("U2", "74HC163", {"1": "RESET", "2": "CLK", "7": "VCC", "8": "GND", "9": "VCC", "10": "VCC", "11": "Q3", "12": "Q2", "13": "Q1", "14": "Q0", "16": "VCC"}, "74HC163"),
        c("R1", "R", {"1": "VCC", "2": "SENSE"}, "10k"),
        c("C1", "C", {"1": "SENSE", "2": "GND"}, "1u"),
        c("R2", "R", {"1": "VCC", "2": "THRESH"}, "47k"),
        c("R3", "R", {"1": "THRESH", "2": "GND"}, "10k"),
        *clock_source("1", "CLK"),
        *output_bank("49", ["Q0", "Q1", "Q2", "Q3"]),
    )
    return circuit("C49", "Op-amp threshold controlled counter reset", parts)


def c50() -> Circuit:
    parts = base(
        c("U1", "4040", {"1": "Q11", "2": "Q12", "3": "ALARM_RAW", "8": "GND", "11": "CLK", "12": "RESET", "16": "VCC"}, "4040"),
        c("U2", "74HC00", {"1": "ALARM_RAW", "2": "ENABLE", "3": "ALARM", "7": "GND", "14": "VCC"}, "74HC00"),
        *clock_source("1", "CLK"),
        tp("TPEN", "ENABLE"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
        *led_load("50", "ALARM"),
    )
    return circuit("C50", "Ripple divider alarm timer", parts)


def c51() -> Circuit:
    parts = base(
        c("U1", "74HC192", {"1": "QB", "2": "QA", "3": "DOWN", "4": "UP", "5": "QC", "6": "QD", "7": "GND", "8": "VCC", "9": "LOAD_N", "10": "CLR", "11": "P0", "12": "P1", "13": "P2", "14": "P3", "15": "BORROW", "16": "CARRY"}, "74HC192"),
        c("U2", "4511", {"1": "QB", "2": "QC", "6": "QD", "7": "QA", "8": "GND", "9": "SEG_E", "10": "SEG_D", "11": "SEG_C", "12": "SEG_B", "13": "SEG_A", "14": "SEG_G", "15": "SEG_F", "16": "VCC"}, "4511"),
        *clock_source("1", "DOWN"),
        c("RUP", "R", {"1": "UP", "2": "VCC"}, "10k"),
        *rc_reset("1", "LOAD_N"),
        c("RCLR", "R", {"1": "CLR", "2": "GND"}, "10k"),
        *bcd_inputs("51", ("P0", "P1", "P2", "P3")),
        *display_segments("51"),
    )
    return circuit("C51", "Parallel load countdown timer", parts)


def c52() -> Circuit:
    parts = base(
        c("U1", "74HC193", {"1": "QB", "2": "QA", "3": "DOWN", "4": "UP", "5": "QC", "6": "QD", "7": "GND", "8": "VCC", "9": "LOAD_N", "10": "CLR", "15": "BORROW", "16": "CARRY"}, "74HC193"),
        c("U2", "74HC85", {"1": "QB", "2": "LIM1", "3": "QC", "4": "LIM2", "5": "QD", "6": "LIM3", "7": "GND", "8": "GND", "9": "VCC", "10": "GND", "11": "GT", "12": "EQ", "13": "LT", "14": "LIM0", "15": "QA", "16": "VCC"}, "74HC85"),
        *clock_source("U", "UP"),
        *clock_source("D", "DOWN"),
        c("RLOAD", "R", {"1": "LOAD_N", "2": "VCC"}, "10k"),
        c("RCLR", "R", {"1": "CLR", "2": "GND"}, "10k"),
        *bcd_inputs("52", ("LIM0", "LIM1", "LIM2", "LIM3")),
        *output_bank("52", ["EQ", "GT", "LT"]),
    )
    return circuit("C52", "Binary up/down service counter", parts)


def c53() -> Circuit:
    parts = base(
        c("U1", "4060", {"1": "Q12", "2": "Q13", "3": "Q14", "8": "GND", "9": "OSC_IN", "10": "OSC_OUT", "11": "OSC_RC", "12": "RESET", "16": "VCC"}, "4060"),
        c("U2", "74HC08", {"1": "Q14", "2": "ENABLE", "3": "WATCHDOG_OK", "7": "GND", "14": "VCC"}, "74HC08"),
        c("R1", "R", {"1": "OSC_OUT", "2": "OSC_RC"}, "1M"),
        c("C1", "C", {"1": "OSC_RC", "2": "GND"}, "100p"),
        c("RRESET", "R", {"1": "RESET", "2": "GND"}, "10k"),
        tp("TPEN", "ENABLE"),
        *led_load("53", "WATCHDOG_OK"),
    )
    return circuit("C53", "Oscillator-divider watchdog enable", parts)


def c54() -> Circuit:
    parts = base(
        c("U1", "74HC165", {"1": "LOAD_N", "2": "CLK", "7": "SER_DATA", "8": "GND", "15": "GND", "16": "VCC"}, "74HC165"),
        c("U2", "74HC595", {"8": "GND", "10": "CLR_N", "11": "CLK", "12": "STORE", "13": "GND", "14": "SER_DATA", "15": "LOG0", "1": "LOG1", "2": "LOG2", "3": "LOG3", "16": "VCC"}, "74HC595"),
        *clock_source("1", "CLK"),
        *clock_source("2", "STORE"),
        *rc_reset("1", "LOAD_N"),
        *rc_reset("2", "CLR_N"),
        *output_bank("54", ["LOG0", "LOG1", "LOG2", "LOG3"]),
    )
    return circuit("C54", "Shift-register input logger", parts)


def c55() -> Circuit:
    parts = base(
        c("U1", "74HC08", {"1": "A", "2": "B", "3": "AB", "7": "GND", "14": "VCC"}, "74HC08"),
        c("U2", "74HC32", {"1": "AB", "2": "ENABLE", "3": "COUNT_EN", "7": "GND", "14": "VCC"}, "74HC32"),
        c("U3", "74HC163", {"1": "CLR_N", "2": "CLK", "7": "COUNT_EN", "8": "GND", "9": "VCC", "10": "COUNT_EN", "11": "Q3", "12": "Q2", "13": "Q1", "14": "Q0", "15": "RCO", "16": "VCC"}, "74HC163"),
        *clock_source("1", "CLK"),
        *rc_reset("1", "CLR_N"),
        *[tp(f"TP{name}", name) for name in ("A", "B", "ENABLE")],
        *output_bank("55", ["Q0", "Q1", "Q2", "Q3", "RCO"]),
    )
    return circuit("C55", "Combinational control feeding synchronous counter", parts)


TARGET_BUILDERS: list[Callable[[], Circuit]] = [
    c01, c02, c03, c04, c05, c06, c07, c08, c09, c10,
    c11, c12, c13, c14, c15, c16, c17, c18, c19, c20,
    c21, c22, c23, c24, c25, c26, c27, c28, c29, c30,
    c31, c32, c33, c34, c35, c36, c37, c38, c39, c40,
    c41, c42, c43, c44, c45, c46, c47, c48, c49, c50,
    c51, c52, c53, c54, c55,
]


def target_id(circuit_obj: Circuit) -> str:
    name = str(circuit_obj.get("project", {}).get("name", ""))
    match = re.match(r"^(C\d{2})", name, re.I)
    if not match:
        raise ValueError(f"Target project name must start with Cxx: {name}")
    return match.group(1).upper()


def validate_targets(circuits: list[Circuit]) -> None:
    ids = [target_id(item) for item in circuits]
    expected = [f"C{i:02d}" for i in range(1, 56)]
    if ids != expected:
        raise ValueError(f"Target IDs mismatch. Expected {expected}, got {ids}")
    supported = set(KIND_SPECS)
    for item in circuits:
        for comp in item["components"]:
            kind = str(comp["kind"]).upper()
            if kind not in supported:
                raise ValueError(f"{target_id(item)} uses unsupported kind {kind}")
            if not comp.get("pins"):
                raise ValueError(f"{target_id(item)} component {comp.get('id')} has no pins")


def generate(outdir: Path, *, clean: bool) -> dict[str, Any]:
    circuits = [builder() for builder in TARGET_BUILDERS]
    validate_targets(circuits)
    run_id = outdir.name
    if clean and outdir.exists():
        import shutil

        shutil.rmtree(outdir)
    json_dir = outdir / "json"
    project_dir = outdir / "projects"
    json_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    failures = 0
    for item in circuits:
        cid = target_id(item)
        name = slugify(item["project"]["name"])
        input_path = json_dir / f"{name}.json"
        input_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
        try:
            manifest = write_project_from_json(item, project_dir / name)
            ok = bool(manifest.get("static_checks", {}).get("ok"))
            if not ok:
                failures += 1
            results.append(
                {
                    "id": cid,
                    "name": name,
                    "ok": ok,
                    "component_count": manifest.get("component_count"),
                    "wire_count": manifest.get("static_checks", {}).get("wire_count"),
                    "router_warning_count": len(manifest.get("static_checks", {}).get("router_warnings", [])),
                    "open_this": str((project_dir / name / manifest["open_this"]).relative_to(outdir)),
                    "manifest": str((project_dir / name / "manifest.json").relative_to(outdir)),
                    "input": str(input_path.relative_to(outdir)),
                }
            )
        except Exception as exc:
            failures += 1
            results.append({"id": cid, "name": name, "ok": False, "error": str(exc), "input": str(input_path.relative_to(outdir))})

    run_manifest = {
        "run_id": run_id,
        "generated_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "schema_version": "progen-kicad-target-pack/v1",
        "target_count": len(circuits),
        "ok_count": sum(1 for row in results if row.get("ok")),
        "failure_count": failures,
        "results": results,
        "supported_kinds": sorted(KIND_SPECS),
    }
    (outdir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    return run_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KiCad C01-C55 target-pack projects.")
    default_out = REPO_ROOT / "kicad" / "experiments" / "runs" / (
        "local_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_target_pack_c01_c55"
    )
    parser.add_argument("--outdir", type=Path, default=default_out)
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args(argv)
    manifest = generate(args.outdir, clean=not args.no_clean)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
