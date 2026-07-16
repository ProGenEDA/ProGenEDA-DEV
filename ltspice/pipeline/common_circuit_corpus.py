"""Curated donor-native common-circuit corpus.

This module is intentionally a *canonical JSON source* producer, not a
parallel ASC writer.  Each recipe uses only the active donor-native LTspice
families (R, C, L, voltage/current sources, ``Misc\\\\signal``, and ground),
declares every physical pin in ``nets``, and carries an exact
``expected_netlist`` copy.  The normal native adapter remains the one and only
authority for placement, direct-wire routing, and ASC generation.

The corpus is useful for three different checks:

* a named, non-random regression population for the placer and router;
* a repeatable set of user-facing examples which can be generated into one
  folder per circuit; and
* a deliberately bounded statement of what can be built with the currently
  donor-observed component catalogue.  It does not pretend that an op-amp,
  diode, switch, transistor, or vendor model has been implemented.

Run ``python -m ltspice.pipeline.common_circuit_corpus OUTPUT`` to write one
``circuit.json`` and one ``accuracy_check.txt`` inside each of 100 named
folders.  The output contains exactly 100 JSON circuit documents.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
import tempfile
import zipfile
from typing import Any


CORPUS_SCHEMA = "progen-ltspice-common-circuit-corpus/v1"
CANONICAL_SCHEMA = "progen-kicad-circuit-ir/v1"
EXPECTED_SCHEMA = "progeneda-expected-netlist/v1"
CORPUS_SIZE = 100

_PINS_BY_KIND: dict[str, tuple[str, ...]] = {
    "R": ("1", "2"),
    "C": ("1", "2"),
    "L": ("1", "2"),
    "VDC": ("1", "2"),
    "VSIN": ("1", "2"),
    "VPULSE": ("1", "2"),
    "MISC_SIGNAL": ("1", "2"),
    "IDC": ("1", "2"),
    "GND": ("1",),
}
_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")

Element = Mapping[str, Any]
NetRows = Sequence[tuple[str, Sequence[str]]]
RecipeFactory = Callable[["CircuitSpec"], tuple[list[dict[str, Any]], NetRows]]


@dataclass(frozen=True)
class CircuitSpec:
    """One stable, named common-circuit recipe descriptor."""

    circuit_id: str
    title: str
    category: str
    description: str
    expected_behavior: str
    directives: tuple[str, ...]
    factory: RecipeFactory


def _element(
    ref: str,
    kind: str,
    value: str | None = None,
    *,
    parameters: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"ref": ref, "kind": kind}
    if value is not None:
        result["value"] = value
    if parameters:
        result["parameters"] = dict(parameters)
    return result


def _ground() -> dict[str, Any]:
    return _element("G1", "GND", "0")


def _source(
    kind: str,
    value: str | None,
    *,
    ref: str | None = None,
    parameters: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    default_ref = "I1" if kind == "IDC" else "V1"
    return _element(ref or default_ref, kind, value, parameters=parameters)


def _document(spec: CircuitSpec, components: list[dict[str, Any]], nets: NetRows) -> dict[str, Any]:
    """Turn a small topology recipe into strict shared canonical JSON.

    The builder deliberately derives the component ``pins`` objects from the
    wire topology rather than permitting two independently editable
    connectivity descriptions.  That makes a malformed recipe fail here,
    before it reaches the donor-native adapter.
    """

    component_by_ref: dict[str, dict[str, Any]] = {}
    required_endpoints: set[str] = set()
    for component in components:
        ref = str(component.get("ref") or "")
        kind = str(component.get("kind") or "")
        if not ref or ref in component_by_ref:
            raise ValueError(f"{spec.circuit_id}: repeated or missing component reference {ref!r}.")
        if kind not in _PINS_BY_KIND:
            raise ValueError(f"{spec.circuit_id}: unsupported corpus kind {kind!r}.")
        component_by_ref[ref] = component
        required_endpoints.update(f"{ref}.{pin}" for pin in _PINS_BY_KIND[kind])

    endpoint_to_net: dict[str, str] = {}
    canonical_nets: dict[str, list[str]] = {}
    for net_name, raw_members in nets:
        if not net_name or net_name in canonical_nets:
            raise ValueError(f"{spec.circuit_id}: repeated or missing net name {net_name!r}.")
        members = [str(member) for member in raw_members]
        if not members:
            raise ValueError(f"{spec.circuit_id}: net {net_name!r} has no members.")
        if len(set(members)) != len(members):
            raise ValueError(f"{spec.circuit_id}: net {net_name!r} repeats an endpoint.")
        for endpoint in members:
            if endpoint not in required_endpoints:
                raise ValueError(f"{spec.circuit_id}: {endpoint!r} is not a native component pin.")
            if endpoint in endpoint_to_net:
                raise ValueError(
                    f"{spec.circuit_id}: {endpoint!r} belongs to both "
                    f"{endpoint_to_net[endpoint]!r} and {net_name!r}."
                )
            endpoint_to_net[endpoint] = net_name
        canonical_nets[net_name] = members
    if set(endpoint_to_net) != required_endpoints:
        missing = sorted(required_endpoints - set(endpoint_to_net))
        extra = sorted(set(endpoint_to_net) - required_endpoints)
        raise ValueError(f"{spec.circuit_id}: incomplete pins; missing={missing}, extra={extra}.")

    prepared_components: list[dict[str, Any]] = []
    for component in components:
        ref = str(component["ref"])
        kind = str(component["kind"])
        prepared = deepcopy(component)
        prepared["pins"] = {
            pin: endpoint_to_net[f"{ref}.{pin}"]
            for pin in _PINS_BY_KIND[kind]
        }
        prepared_components.append(prepared)

    expected_nets = [
        {"name": name, "members": list(members), "member_count": len(members)}
        for name, members in canonical_nets.items()
    ]
    return {
        "schema_version": CANONICAL_SCHEMA,
        "circuit_id": spec.circuit_id,
        "project": {"name": _slug(spec.title), "analysis": list(spec.directives)},
        "components": prepared_components,
        "nets": canonical_nets,
        "expected_netlist": {
            "schema": EXPECTED_SCHEMA,
            "source": "common_circuit_corpus",
            "nets": expected_nets,
            "important_nets": ["GND"],
        },
        "spice_directives": list(spec.directives),
        "routing": {"mode": "wire"},
        "common_circuit_corpus": {
            "schema": CORPUS_SCHEMA,
            "title": spec.title,
            "category": spec.category,
            "description": spec.description,
            "expected_behavior": spec.expected_behavior,
            "source_limit": "active donor-native R/C/L/V/I/Misc\\\\signal/GND catalogue only",
            "direct_wire_requirement": "All ordinary connectivity must be emitted as physical WIRE records.",
        },
    }


def _slug(value: str) -> str:
    result = _SLUG_NON_ALNUM.sub("-", value.casefold()).strip("-")
    return result or "common-circuit"


def _series_factory(
    chain: Sequence[Element],
    *,
    source_kind: str = "VDC",
    source_value: str | None = "5",
    source_parameters: Mapping[str, str] | None = None,
    source_ref: str | None = None,
) -> RecipeFactory:
    """One source, an ordered series path, and a physical ground return."""

    if not chain:
        raise ValueError("A series circuit needs at least one path element.")

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        source = _source(source_kind, source_value, ref=source_ref, parameters=source_parameters)
        components = [source, *[deepcopy(dict(item)) for item in chain], _ground()]
        nets: list[tuple[str, Sequence[str]]] = []
        previous = f"{source['ref']}.1"
        for index, item in enumerate(chain):
            ref = str(item["ref"])
            net = f"N{index}"
            nets.append((net, (previous, f"{ref}.1")))
            previous = f"{ref}.2"
        nets.append(("GND", (f"{source['ref']}.2", previous, "G1.1")))
        return components, nets

    return build


def _parallel_factory(
    branches: Sequence[Element],
    *,
    source_kind: str = "VDC",
    source_value: str | None = "5",
    source_parameters: Mapping[str, str] | None = None,
    source_ref: str | None = None,
) -> RecipeFactory:
    """One source driving a named group of parallel two-terminal branches."""

    if not branches:
        raise ValueError("A parallel circuit needs at least one branch.")

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        source = _source(source_kind, source_value, ref=source_ref, parameters=source_parameters)
        copied = [deepcopy(dict(item)) for item in branches]
        components = [source, *copied, _ground()]
        input_members = [f"{source['ref']}.1", *(f"{item['ref']}.1" for item in copied)]
        ground_members = [f"{source['ref']}.2", *(f"{item['ref']}.2" for item in copied), "G1.1"]
        return components, (("IN", tuple(input_members)), ("GND", tuple(ground_members)))

    return build


def _ladder_factory(
    series: Sequence[Element],
    shunts: Sequence[tuple[int, Element]],
    *,
    source_kind: str = "VDC",
    source_value: str | None = "5",
    source_parameters: Mapping[str, str] | None = None,
    source_ref: str | None = None,
) -> RecipeFactory:
    """A source-fed ladder with selected shunts from each numbered node."""

    if not series:
        raise ValueError("A ladder needs at least one series element.")
    if any(node < 0 or node > len(series) for node, _item in shunts):
        raise ValueError("A ladder shunt refers to an unavailable node.")

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        source = _source(source_kind, source_value, ref=source_ref, parameters=source_parameters)
        serial = [deepcopy(dict(item)) for item in series]
        branch_by_node: dict[int, list[dict[str, Any]]] = {}
        for node, item in shunts:
            branch_by_node.setdefault(node, []).append(deepcopy(dict(item)))
        components = [source, *serial]
        for node in sorted(branch_by_node):
            components.extend(branch_by_node[node])
        components.append(_ground())
        nets: list[tuple[str, Sequence[str]]] = []
        for node in range(len(serial) + 1):
            members: list[str] = []
            if node == 0:
                members.append(f"{source['ref']}.1")
            else:
                members.append(f"{serial[node - 1]['ref']}.2")
            if node < len(serial):
                members.append(f"{serial[node]['ref']}.1")
            members.extend(f"{item['ref']}.1" for item in branch_by_node.get(node, []))
            nets.append((f"N{node}", tuple(members)))
        ground_members = [f"{source['ref']}.2"]
        ground_members.extend(
            f"{item['ref']}.2"
            for node in sorted(branch_by_node)
            for item in branch_by_node[node]
        )
        ground_members.append("G1.1")
        nets.append(("GND", tuple(ground_members)))
        return components, tuple(nets)

    return build


def _bridge_factory(
    *,
    source_kind: str = "VDC",
    source_value: str | None = "5",
    source_parameters: Mapping[str, str] | None = None,
    values: tuple[str, str, str, str] = ("1k", "1k", "1k", "1k"),
    load: Element | None = None,
) -> RecipeFactory:
    """A real four-arm Wheatstone-style bridge, optionally output-loaded."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        source = _source(source_kind, source_value, parameters=source_parameters)
        r1, r2, r3, r4 = (_element(f"R{index}", "R", value) for index, value in enumerate(values, 1))
        components = [source, r1, r2, r3, r4]
        if load is not None:
            components.append(deepcopy(dict(load)))
        components.append(_ground())
        left = ["R1.2", "R2.1"]
        right = ["R3.2", "R4.1"]
        if load is not None:
            left.append(f"{load['ref']}.1")
            right.append(f"{load['ref']}.2")
        return components, (
            ("SUPPLY", (f"{source['ref']}.1", "R1.1", "R3.1")),
            ("LEFT", tuple(left)),
            ("RIGHT", tuple(right)),
            ("GND", (f"{source['ref']}.2", "R2.2", "R4.2", "G1.1")),
        )

    return build


def _summer_factory(
    *,
    source_a_kind: str = "VDC",
    source_a_value: str | None = "2",
    source_b_kind: str = "VDC",
    source_b_value: str | None = "3",
    load_value: str = "1k",
) -> RecipeFactory:
    """Two independent sources coupled into a passive resistive summer."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        v1 = _source(source_a_kind, source_a_value, ref="V1")
        v2 = _source(source_b_kind, source_b_value, ref="V2")
        r1 = _element("R1", "R", "10k")
        r2 = _element("R2", "R", "10k")
        r3 = _element("R3", "R", load_value)
        return [v1, v2, r1, r2, r3, _ground()], (
            ("IN_A", ("V1.1", "R1.1")),
            ("IN_B", ("V2.1", "R2.1")),
            ("OUT", ("R1.2", "R2.2", "R3.1")),
            ("GND", ("V1.2", "V2.2", "R3.2", "G1.1")),
        )

    return build


def _r2r_factory() -> RecipeFactory:
    """A three-bit passive R-2R DAC ladder with source-driven input bits."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        components = [
            _source("VDC", "5", ref="V1"),
            _source("VDC", "0", ref="V2"),
            _source("VDC", "5", ref="V3"),
            _element("R1", "R", "10k"),
            _element("R2", "R", "10k"),
            _element("R3", "R", "10k"),
            _element("R4", "R", "20k"),
            _element("R5", "R", "20k"),
            _element("R6", "R", "20k"),
            _element("R7", "R", "1Meg"),
            _ground(),
        ]
        return components, (
            ("BIT0", ("V1.1", "R1.1")),
            ("BIT1", ("V2.1", "R2.1")),
            ("BIT2", ("V3.1", "R3.1")),
            ("OUT", ("R1.2", "R4.1", "R7.1")),
            ("N1", ("R2.2", "R4.2", "R5.1")),
            ("N2", ("R3.2", "R5.2", "R6.1")),
            ("GND", ("V1.2", "V2.2", "V3.2", "R6.2", "R7.2", "G1.1")),
        )

    return build


def _rc_snubber_factory() -> RecipeFactory:
    """A genuine *series* RC snubber branch across a pulse-driven node."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        components = [
            _source("VPULSE", "PULSE(0 10 0 1u 1u 1m 2m)"),
            _element("R1", "R", "100"), _element("C1", "C", "100n"),
            _element("R2", "R", "1k"), _ground(),
        ]
        return components, (
            ("IN", ("V1.1", "R1.1", "R2.1")),
            ("SNUB", ("R1.2", "C1.1")),
            ("GND", ("V1.2", "C1.2", "R2.2", "G1.1")),
        )

    return build


def _capacitor_bank_discharge_factory() -> RecipeFactory:
    """A capacitive bank behind source resistance and a physical bleed path."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        components = [
            _source("VPULSE", "PULSE(0 5 0 1u 1u 2m 20m)"),
            _element("R1", "R", "100"),
            _element("C1", "C", "10u"), _element("C2", "C", "10u"),
            _element("C3", "C", "10u"), _element("R2", "R", "1k"), _ground(),
        ]
        return components, (
            ("IN", ("V1.1", "R1.1")),
            ("BANK", ("R1.2", "C1.1", "C2.1", "C3.1", "R2.1")),
            ("GND", ("V1.2", "C1.2", "C2.2", "C3.2", "R2.2", "G1.1")),
        )

    return build


def _rlc_band_stop_factory() -> RecipeFactory:
    """A feed resistor with a shunt *series* LC trap and load resistor."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        components = [
            _source("MISC_SIGNAL", None, parameters={"ac": "1"}),
            _element("R1", "R", "100"), _element("L1", "L", "10m"),
            _element("C1", "C", "100n"), _element("R2", "R", "1k"), _ground(),
        ]
        return components, (
            ("IN", ("V1.1", "R1.1")),
            ("OUT", ("R1.2", "L1.1", "R2.1")),
            ("TRAP", ("L1.2", "C1.1")),
            ("GND", ("V1.2", "C1.2", "R2.2", "G1.1")),
        )

    return build


def _twin_t_factory() -> RecipeFactory:
    """Passive Twin-T notch filter: R-T and C-T paths in parallel."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        components = [
            _source("MISC_SIGNAL", None, parameters={"ac": "1"}),
            _element("R1", "R", "10k"), _element("R2", "R", "10k"),
            _element("C1", "C", "20n"),
            _element("C2", "C", "10n"), _element("C3", "C", "10n"),
            _element("R3", "R", "5k"), _element("R4", "R", "100k"),
            _ground(),
        ]
        return components, (
            ("IN", ("V1.1", "R1.1", "C2.1")),
            ("TOP", ("R1.2", "R2.1", "C1.1")),
            ("BOTTOM", ("C2.2", "C3.1", "R3.1")),
            ("OUT", ("R2.2", "C3.2", "R4.1")),
            ("GND", ("V1.2", "C1.2", "R3.2", "R4.2", "G1.1")),
        )

    return build


def _wien_factory() -> RecipeFactory:
    """The passive lead-lag Wien bridge network, without an unavailable amp."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        components = [
            _source("MISC_SIGNAL", None, parameters={"ac": "1"}),
            _element("C1", "C", "10n"), _element("R1", "R", "10k"),
            _element("R2", "R", "10k"), _element("C2", "C", "10n"),
            _element("R3", "R", "100k"), _ground(),
        ]
        return components, (
            ("IN", ("V1.1", "C1.1")),
            ("LEAD", ("C1.2", "R1.1")),
            ("OUT", ("R1.2", "R2.1", "C2.1", "R3.1")),
            ("GND", ("V1.2", "R2.2", "C2.2", "R3.2", "G1.1")),
        )

    return build


def _bias_coupling_factory() -> RecipeFactory:
    """An AC-coupled signal into a DC-biased resistor load."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        components = [
            _source("VDC", "2.5", ref="V1"),
            _source("VSIN", "SINE(0 1 1k)", ref="V2"),
            _element("C1", "C", "1u"), _element("R1", "R", "100k"),
            _element("R2", "R", "100k"), _element("R3", "R", "10k"),
            _ground(),
        ]
        return components, (
            ("BIAS", ("V1.1", "R1.1")),
            ("AC_IN", ("V2.1", "C1.1")),
            ("OUT", ("C1.2", "R1.2", "R2.1", "R3.1")),
            ("GND", ("V1.2", "V2.2", "R2.2", "R3.2", "G1.1")),
        )

    return build


def _complex_test_bench_factory() -> RecipeFactory:
    """A multi-stage passive RLC test network used as the corpus stress case."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        components = [
            _source("VPULSE", "PULSE(0 5 0 1u 1u 2m 4m)"),
            _element("R1", "R", "10"), _element("L1", "L", "1m"),
            _element("C1", "C", "10u"), _element("R2", "R", "100"),
            _element("L2", "L", "2m"), _element("C2", "C", "4.7u"),
            _element("R3", "R", "1k"), _element("C3", "C", "100n"),
            _element("L3", "L", "470u"), _element("R4", "R", "100"),
            _element("C4", "C", "1u"), _element("R5", "R", "10k"),
            _ground(),
        ]
        return components, (
            ("N0", ("V1.1", "R1.1")),
            ("N1", ("R1.2", "L1.1", "C1.1")),
            ("N2", ("L1.2", "R2.1", "C2.1")),
            ("N3", ("R2.2", "L2.1", "R3.1")),
            ("N4", ("L2.2", "C3.1", "L3.1")),
            ("N5", ("R3.2", "L3.2", "R4.1", "R5.1")),
            ("N6", ("R4.2", "C4.1")),
            ("GND", ("V1.2", "C1.2", "C2.2", "C3.2", "C4.2", "R5.2", "G1.1")),
        )

    return build


def _spec(
    number: int,
    slug: str,
    title: str,
    category: str,
    description: str,
    expected_behavior: str,
    directives: Sequence[str],
    factory: RecipeFactory,
) -> CircuitSpec:
    return CircuitSpec(
        circuit_id=f"COMMON_{number:03d}_{slug.upper()}",
        title=title,
        category=category,
        description=description,
        expected_behavior=expected_behavior,
        directives=tuple(directives),
        factory=factory,
    )


def _specifications() -> tuple[CircuitSpec, ...]:
    """The ordered 100-circuit corpus.

    Names intentionally describe known passive/source circuits or test
    fixtures.  Variants are kept when their source mode, network purpose, or
    topology materially differs; they are not generated as random component
    piles.
    """

    op = (".op",)
    # The shared deterministic directive validator normalizes scale suffixes
    # case-sensitively before LTspice sees them; use lowercase ``meg`` rather
    # than the ambiguous display spelling ``Meg``.
    ac = (".ac dec 20 10 1meg",)
    tran = (".tran 10u 20m",)
    # ``uic`` is part of the currently allowlisted `.tran` grammar whereas
    # LTspice's `startup` modifier is deliberately not accepted by the shared
    # JSON validator yet.
    pulse_tran = (".tran 10u 20m uic",)
    s = _spec
    e = _element
    return (
        # Resistive networks (1-20)
        s(1, "voltage_divider", "Voltage Divider", "resistive", "Two series resistors divide a DC source.", "The middle node settles to the standard divider ratio.", op, _series_factory((e("R1", "R", "10k"), e("R2", "R", "10k")))),
        s(2, "loaded_voltage_divider", "Loaded Voltage Divider", "resistive", "A divider whose output has a parallel load resistor.", "The load lowers the unloaded divider voltage.", op, _ladder_factory((e("R1", "R", "10k"),), ((1, e("R2", "R", "10k")), (1, e("R3", "R", "10k"))))),
        s(3, "potentiometer_wiper", "Potentiometer Wiper Equivalent", "resistive", "Two split resistance sections and a high-value wiper load.", "The wiper node is adjustable by changing the two split resistances.", op, _ladder_factory((e("R1", "R", "7.5k"),), ((1, e("R2", "R", "2.5k")), (1, e("R3", "R", "1Meg"))))),
        s(4, "pull_up_network", "Resistive Pull-Up Network", "resistive", "A positive rail feeds an input through a pull-up resistor.", "The input is held high through the pull-up and loaded by its return resistance.", op, _ladder_factory((e("R1", "R", "10k"),), ((1, e("R2", "R", "100k")),))),
        s(5, "pull_down_network", "Resistive Pull-Down Network", "resistive", "A driven input has a defined return through a pull-down resistor.", "The node is biased low when its upstream drive is removed.", op, _ladder_factory((e("R1", "R", "1k"),), ((1, e("R2", "R", "10k")),))),
        s(6, "series_resistor_network", "Series Resistor Network", "resistive", "Three resistors in one current path.", "The same DC current flows through all three resistors.", op, _series_factory((e("R1", "R", "1k"), e("R2", "R", "2.2k"), e("R3", "R", "4.7k")))),
        s(7, "parallel_resistor_network", "Parallel Resistor Network", "resistive", "Three shunt resistors across one DC source.", "Branch currents add and the equivalent resistance is below every branch resistance.", op, _parallel_factory((e("R1", "R", "1k"), e("R2", "R", "2.2k"), e("R3", "R", "4.7k")))),
        s(8, "series_parallel_resistor_network", "Series-Parallel Resistor Network", "resistive", "A series feed resistor followed by two shunt branches.", "The input sees a series resistance plus a parallel load equivalent.", op, _ladder_factory((e("R1", "R", "1k"), e("R4", "R", "330")), ((1, e("R2", "R", "2.2k")), (1, e("R3", "R", "4.7k")), (2, e("R5", "R", "1k"))))),
        s(9, "current_to_voltage_shunt", "Current-to-Voltage Shunt", "resistive", "A DC current source drives a precision shunt resistor.", "The shunt voltage equals current times resistance.", op, _parallel_factory((e("R1", "R", "1k"),), source_kind="IDC", source_value="1m")),
        s(10, "current_divider", "Current Divider", "resistive", "A current source feeds two parallel resistive paths.", "The source current divides inversely with branch resistance.", op, _parallel_factory((e("R1", "R", "1k"), e("R2", "R", "3k")), source_kind="IDC", source_value="4m")),
        s(11, "thevenin_test_network", "Thevenin Equivalent Test Network", "resistive", "A source divider and output load used to inspect its Thevenin behavior.", "Changing the load demonstrates output sag from source resistance.", op, _ladder_factory((e("R1", "R", "1k"),), ((1, e("R2", "R", "1k")), (1, e("R3", "R", "1k"))))),
        s(12, "norton_test_network", "Norton Equivalent Test Network", "resistive", "A current source with internal shunt resistance and load.", "The load current follows Norton current division.", op, _parallel_factory((e("R1", "R", "1k"), e("R2", "R", "1k")), source_kind="IDC", source_value="2m")),
        s(13, "l_pad_attenuator", "L-Pad Attenuator", "resistive", "One series and one shunt resistance form an L attenuation pad.", "The output is attenuated while the shunt establishes a load.", ac, _ladder_factory((e("R1", "R", "470"),), ((1, e("R2", "R", "150")), (1, e("R3", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(14, "t_pad_attenuator", "T-Pad Attenuator", "resistive", "A two-series-one-shunt T attenuation pad.", "The output attenuates through the symmetric pad network.", ac, _ladder_factory((e("R1", "R", "220"), e("R3", "R", "220")), ((1, e("R2", "R", "100")), (2, e("R4", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(15, "pi_pad_attenuator", "Pi-Pad Attenuator", "resistive", "Input and output shunts surround a series pad resistor.", "The pad attenuates while presenting shunt impedances at both ports.", ac, _ladder_factory((e("R2", "R", "330"),), ((0, e("R1", "R", "150")), (1, e("R3", "R", "150")), (1, e("R4", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(16, "wheatstone_bridge", "Wheatstone Bridge", "resistive", "Four resistive arms create two differential midpoint nodes.", "Equal arm ratios give near-zero differential bridge output.", op, _bridge_factory()),
        s(17, "balanced_bridge_sensor", "Balanced Bridge Sensor Network", "resistive", "A slightly unbalanced bridge with a high-resistance differential sense load.", "A small arm change creates a measurable LEFT-to-RIGHT differential voltage.", op, _bridge_factory(values=("1k", "1k", "1.01k", "1k"), load=e("R5", "R", "1Meg"))),
        s(18, "r_2r_ladder_dac", "Three-Bit R-2R Ladder DAC", "resistive", "Three source-driven bit inputs feed a passive R-2R conversion ladder.", "The OUT node is the weighted analog combination of the three bit sources.", op, _r2r_factory()),
        s(19, "resistive_summing_network", "Resistive Summing Network", "resistive", "Two DC inputs combine through equal summing resistors.", "OUT is a resistance-weighted average of the two input sources.", op, _summer_factory()),
        s(20, "dual_source_resistive_mixer", "Dual-Source Resistive Mixer", "resistive", "Two sinusoidal inputs combine through a passive resistor mixer.", "OUT contains both source frequencies with passive attenuation.", tran, _summer_factory(source_a_kind="VSIN", source_a_value="SINE(0 1 1k)", source_b_kind="VSIN", source_b_value="SINE(0 1 2k)")),

        # RC networks (21-44)
        s(21, "rc_low_pass", "First-Order RC Low-Pass Filter", "RC filter", "Series R and shunt C form the canonical low-pass.", "OUT rolls off above 1/(2*pi*R*C).", ac, _ladder_factory((e("R1", "R", "1k"),), ((1, e("C1", "C", "100n")),), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(22, "rc_high_pass", "First-Order RC High-Pass Filter", "RC filter", "Series C and shunt R form the canonical high-pass.", "OUT rejects low frequency content below 1/(2*pi*R*C).", ac, _ladder_factory((e("C1", "C", "100n"),), ((1, e("R1", "R", "1k")),), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(23, "rc_integrator", "Passive RC Integrator", "RC timing", "A low-pass RC chosen so the input frequency is above its corner.", "At sufficiently high frequency the capacitor voltage approximates an input integral.", tran, _ladder_factory((e("R1", "R", "10k"),), ((1, e("C1", "C", "1u")),), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 1m 2m)")),
        s(24, "rc_differentiator", "Passive RC Differentiator", "RC timing", "A high-pass RC driven by a pulse waveform.", "Short output pulses appear around input edges when the time constant is small.", tran, _ladder_factory((e("C1", "C", "10n"),), ((1, e("R1", "R", "10k")),), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 2m 4m)")),
        s(25, "rc_charge_timing", "RC Charge Timing Network", "RC timing", "A pulse source charges a capacitor through a resistor.", "The capacitor follows an exponential charge curve during each pulse.", pulse_tran, _ladder_factory((e("R1", "R", "10k"),), ((1, e("C1", "C", "1u")),), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(26, "rc_discharge_timing", "RC Discharge Timing Network", "RC timing", "A pulsed source and resistor provide a controlled capacitor discharge path.", "The capacitor discharges exponentially through the resistor after the input falls.", pulse_tran, _ladder_factory((e("R1", "R", "4.7k"),), ((1, e("C1", "C", "4.7u")),), source_kind="VPULSE", source_value="PULSE(5 0 0 1u 1u 5m 10m)")),
        s(27, "rc_delay", "RC Delay Network", "RC timing", "A pulse input feeds a delayed analog node through R and C.", "OUT crosses a threshold later than the driving edge.", pulse_tran, _ladder_factory((e("R1", "R", "22k"),), ((1, e("C1", "C", "470n")),), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(28, "rc_debouncer", "RC Debouncer Filter", "RC timing", "A pulse input passes through a slow RC low-pass.", "Fast input transitions are smoothed into a monotonic analog edge.", pulse_tran, _ladder_factory((e("R1", "R", "47k"),), ((1, e("C1", "C", "100n")),), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 200u 500u)")),
        s(29, "rc_snubber", "RC Snubber Network", "RC network", "A genuine series R-C snubber branch is placed across a pulsed source/load node.", "The series branch absorbs high-frequency energy and reduces transient ringing in the test network.", pulse_tran, _rc_snubber_factory()),
        s(30, "capacitive_divider", "Capacitive Voltage Divider", "RC network", "Two series capacitors divide an AC input.", "The midpoint AC voltage follows the inverse-capacitance divider ratio.", ac, _series_factory((e("C1", "C", "100n"), e("C2", "C", "100n")), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(31, "ac_coupling", "AC Coupling Network", "RC filter", "A series coupling capacitor feeds a resistive load.", "DC is blocked while AC above the high-pass corner reaches the load.", tran, _ladder_factory((e("C1", "C", "1u"),), ((1, e("R1", "R", "10k")),), source_kind="VSIN", source_value="SINE(0 1 1k)")),
        s(32, "rc_lag_compensator", "RC Lag Compensator Network", "RC filter", "A passive low-pass lag section with a defined output load.", "The phase lags and magnitude falls above the pole frequency.", ac, _ladder_factory((e("R1", "R", "10k"),), ((1, e("C1", "C", "10n")), (1, e("R2", "R", "100k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(33, "rc_lead_compensator", "RC Lead Compensator Network", "RC filter", "A passive high-pass lead section with a defined load.", "The output leads the low-frequency input response around its corner.", ac, _ladder_factory((e("C1", "C", "10n"),), ((1, e("R1", "R", "10k")), (1, e("R2", "R", "100k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(34, "two_stage_rc_low_pass", "Two-Stage RC Low-Pass Filter", "RC filter", "Two cascaded resistor-capacitor low-pass sections.", "The cascade has a steeper high-frequency roll-off than one RC section.", ac, _ladder_factory((e("R1", "R", "1k"), e("R2", "R", "1k")), ((1, e("C1", "C", "100n")), (2, e("C2", "C", "100n"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(35, "two_stage_rc_high_pass", "Two-Stage RC High-Pass Filter", "RC filter", "Two cascaded capacitor-resistor high-pass sections.", "The cascade rejects low frequencies more strongly than one section.", ac, _ladder_factory((e("C1", "C", "100n"), e("C2", "C", "100n")), ((1, e("R1", "R", "1k")), (2, e("R2", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(36, "rc_band_pass_cascade", "RC Band-Pass Cascade", "RC filter", "A high-pass section feeds a low-pass section.", "Only a middle frequency range passes between the two RC corners.", ac, _ladder_factory((e("C1", "C", "100n"), e("R2", "R", "1k")), ((1, e("R1", "R", "10k")), (2, e("C2", "C", "10n"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(37, "twin_t_notch", "Twin-T Notch Filter", "RC filter", "Parallel R-T and C-T paths create a passive notch.", "A deep attenuation occurs near the matched Twin-T notch frequency.", ac, _twin_t_factory()),
        s(38, "wien_bridge", "Wien Bridge Lead-Lag Network", "RC filter", "The passive Wien bridge frequency-selective network.", "Its lead-lag path has a characteristic phase and gain near its center frequency.", ac, _wien_factory()),
        s(39, "three_section_rc_phase_shift", "Three-Section RC Phase-Shift Network", "RC filter", "Three cascaded high-pass RC sections used in phase-shift oscillator feedback paths.", "The passive network approaches a large phase shift across its design band.", ac, _ladder_factory((e("C1", "C", "10n"), e("C2", "C", "10n"), e("C3", "C", "10n")), ((1, e("R1", "R", "10k")), (2, e("R2", "R", "10k")), (3, e("R3", "R", "10k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(40, "three_section_rc_delay", "Three-Section RC Delay Line", "RC timing", "Three cascaded low-pass timing sections.", "Each later node has additional smoothing and delay.", pulse_tran, _ladder_factory((e("R1", "R", "10k"), e("R2", "R", "10k"), e("R3", "R", "10k")), ((1, e("C1", "C", "100n")), (2, e("C2", "C", "100n")), (3, e("C3", "C", "100n"))), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(41, "rc_anti_alias_ladder", "Three-Section RC Anti-Alias Ladder", "RC filter", "A three-pole passive RC low-pass test filter.", "High-frequency inputs are strongly attenuated before a hypothetical sampler.", ac, _ladder_factory((e("R1", "R", "1k"), e("R2", "R", "1k"), e("R3", "R", "1k")), ((1, e("C1", "C", "47n")), (2, e("C2", "C", "47n")), (3, e("C3", "C", "47n")), (3, e("R4", "R", "10k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(42, "rc_smoothing_filter", "RC Smoothing Filter", "RC network", "A source resistor and capacitor reservoir/load branch.", "The output capacitor reduces ripple in the source test waveform.", tran, _ladder_factory((e("R1", "R", "100"),), ((1, e("C1", "C", "100u")), (1, e("R2", "R", "1k"))), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(43, "capacitor_bank_discharge", "Capacitor Bank Discharge Network", "RC network", "Three parallel capacitors behind source resistance discharge through a bleed resistor.", "Stored energy and discharge time scale with the combined capacitance and bleed resistance.", tran, _capacitor_bank_discharge_factory()),
        s(44, "capacitive_sensor_bridge", "Capacitive Sensor Bridge", "RC network", "A capacitive analogue of a bridge with two midpoint nodes.", "A capacitance mismatch produces a differential AC midpoint response.", ac, _capacitive_bridge_factory()),

        # RL, LC, and RLC networks (45-70)
        s(45, "rl_high_pass", "First-Order RL High-Pass Filter", "RL filter", "A series resistor and shunt inductor test section.", "The node across the inductor rises with frequency around the RL corner.", ac, _ladder_factory((e("R1", "R", "100"),), ((1, e("L1", "L", "10m")),), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(46, "rl_low_pass", "First-Order RL Low-Pass Filter", "RL filter", "A series inductor and shunt resistor test section.", "The node across the shunt resistor falls with frequency around the RL corner.", ac, _ladder_factory((e("L1", "L", "10m"),), ((1, e("R1", "R", "100")),), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(47, "rl_inductive_delay", "Pulse-Driven RL Inductive Delay Network", "RL timing", "A series RL section driven by a pulse source.", "Inductor current rises and decays with the RL time constant.", tran, _series_factory((e("R1", "R", "100"), e("L1", "L", "10m")), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 2m 4m)")),
        s(48, "rl_edge_response", "Pulse-Driven RL Edge-Response Network", "RL timing", "A pulse-driven inductive/resistive path with reversed element order.", "Rapid input transitions produce the expected inductive edge response.", tran, _series_factory((e("L1", "L", "10m"), e("R1", "R", "100")), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 2m 4m)")),
        s(49, "rl_step_response", "RL Step Response Network", "RL timing", "A pulsed voltage source feeds a series resistor and inductor.", "Inductor current rises and falls exponentially with the RL time constant.", pulse_tran, _series_factory((e("R1", "R", "100"), e("L1", "L", "10m")), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(50, "rl_current_limiter", "RL Current-Limiter Test Network", "RL network", "A source feeds a resistive-inductive load path.", "The inductor limits the rate of current change into the load resistance.", tran, _series_factory((e("R1", "R", "10"), e("L1", "L", "1m"), e("R2", "R", "100")), source_kind="VPULSE", source_value="PULSE(0 10 0 1u 1u 5m 10m)")),
        s(51, "series_rlc_resonance", "Series RLC Resonant Circuit", "RLC filter", "R, L, and C form one series resonance path.", "Source current peaks near the series resonance frequency.", ac, _series_factory((e("R1", "R", "10"), e("L1", "L", "10m"), e("C1", "C", "100n")), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(52, "parallel_rlc_resonance", "Parallel RLC Resonant Circuit", "RLC filter", "R, L, and C are all shunt branches across an AC source.", "Input impedance peaks near parallel resonance when losses are low.", ac, _parallel_factory((e("R1", "R", "10k"), e("L1", "L", "10m"), e("C1", "C", "100n")), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(53, "rlc_band_pass", "Series RLC Band-Pass Filter", "RLC filter", "A series RLC chain provides a resonant pass path.", "The load path response is largest around series resonance.", ac, _series_factory((e("C1", "C", "100n"), e("L1", "L", "10m"), e("R1", "R", "100")), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(54, "rlc_band_stop", "RLC Band-Stop Filter", "RLC filter", "A series feed resistor drives a shunt series-LC trap branch and load.", "The shunt series LC path suppresses output near its resonance.", ac, _rlc_band_stop_factory()),
        s(55, "rlc_low_pass", "RLC Low-Pass Filter", "RLC filter", "A series inductor with shunt capacitor and load creates a low-pass section.", "The output remains strongest below the LC corner frequency.", ac, _ladder_factory((e("L1", "L", "10m"),), ((1, e("C1", "C", "100n")), (1, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(56, "rlc_high_pass", "RLC High-Pass Filter", "RLC filter", "A series capacitor feeds a shunt inductive/load node.", "The output rises above the high-pass corner with inductor-defined loading.", ac, _ladder_factory((e("C1", "C", "100n"),), ((1, e("L1", "L", "10m")), (1, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(57, "rlc_damping", "RLC Damping Network", "RLC network", "A resistor is included with an LC transient path.", "The resistor reduces the Q and damps ringing after a pulse edge.", tran, _series_factory((e("R1", "R", "100"), e("L1", "L", "1m"), e("C1", "C", "1u")), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 1m 4m)")),
        s(58, "lc_tank", "LC Tank Circuit", "LC network", "An inductor and capacitor are shunt-connected with a loss resistor.", "Energy exchanges between L and C near the tank resonant frequency.", ac, _parallel_factory((e("L1", "L", "10m"), e("C1", "C", "100n"), e("R1", "R", "100k")), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(59, "lc_low_pass_l_section", "LC Low-Pass L-Section Filter", "LC filter", "A series inductor and shunt capacitor form a passive L section.", "The load voltage is low-pass filtered by the LC section.", ac, _ladder_factory((e("L1", "L", "10m"),), ((1, e("C1", "C", "100n")), (1, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(60, "lc_high_pass_l_section", "LC High-Pass L-Section Filter", "LC filter", "A series capacitor and shunt inductor form a high-pass L section.", "The load voltage is attenuated below the LC high-pass corner.", ac, _ladder_factory((e("C1", "C", "100n"),), ((1, e("L1", "L", "10m")), (1, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(61, "lc_pi_filter", "LC Pi Filter", "LC filter", "Input/output capacitors surround a series inductor.", "The pi network provides stronger ripple attenuation than one L section.", ac, _ladder_factory((e("L1", "L", "10m"),), ((0, e("C1", "C", "100n")), (1, e("C2", "C", "100n")), (1, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(62, "lc_t_filter", "LC T Filter", "LC filter", "Two series inductors surround a shunt capacitor.", "The T section filters ripple across both series arms.", ac, _ladder_factory((e("L1", "L", "5m"), e("L2", "L", "5m")), ((1, e("C1", "C", "100n")), (2, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(63, "lcl_filter", "LCL Filter", "LC filter", "Two inductors and a central shunt capacitor form an LCL network.", "The third-order section strongly attenuates high-frequency source content.", ac, _ladder_factory((e("L1", "L", "2m"), e("L2", "L", "2m")), ((1, e("C1", "C", "1u")), (2, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(64, "dual_section_clc_filter", "Dual-Section CLC Power Filter", "LC filter", "A C-L-C-L-C cascade models a two-section pi filter.", "The multiple reactive stages give strong conducted-ripple attenuation.", ac, _ladder_factory((e("L1", "L", "2m"), e("L2", "L", "2m")), ((0, e("C1", "C", "1u")), (1, e("C2", "C", "1u")), (2, e("C3", "C", "1u")), (2, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(65, "lc_ladder_low_pass", "Three-Section LC Ladder Low-Pass Filter", "LC filter", "Three series inductors and three shunt capacitors form a ladder filter.", "The ladder produces a steeper low-pass transition than a single section.", ac, _ladder_factory((e("L1", "L", "1m"), e("L2", "L", "1m"), e("L3", "L", "1m")), ((1, e("C1", "C", "100n")), (2, e("C2", "C", "100n")), (3, e("C3", "C", "100n")), (3, e("R1", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(66, "rlc_ladder_band_pass", "RLC Ladder Band-Pass Filter", "RLC filter", "A reactive ladder with resistive damping and load.", "A finite frequency band reaches the output more readily than far-off frequencies.", ac, _ladder_factory((e("C1", "C", "100n"), e("L1", "L", "10m"), e("C2", "C", "100n")), ((1, e("R1", "R", "1k")), (2, e("R2", "R", "1k")), (3, e("R3", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(67, "rlc_resonant_load", "RLC Resonant Load Network", "RLC network", "A source resistor feeds a parallel RLC load.", "The source sees a frequency-dependent resonant load impedance.", ac, _ladder_factory((e("R1", "R", "100"),), ((1, e("L1", "L", "10m")), (1, e("C1", "C", "100n")), (1, e("R2", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(68, "damped_lc_ringing", "Damped LC Ringing Network", "RLC timing", "A pulse drives a series R-L path into a shunt capacitor.", "The output shows damped LC ringing after a fast pulse edge.", tran, _ladder_factory((e("R1", "R", "22"), e("L1", "L", "1m")), ((2, e("C1", "C", "1u")), (2, e("R2", "R", "1k"))), source_kind="VPULSE", source_value="PULSE(0 5 0 100n 100n 100u 2m)")),
        s(69, "tuned_rlc_load", "Tuned RLC Load Network", "RLC network", "A series/shunt RLC network used to inspect frequency-dependent load transformation.", "The load transfer is frequency-selective around the tuned LC region.", ac, _ladder_factory((e("C1", "C", "100n"), e("L1", "L", "10m"), e("R1", "R", "100")), ((1, e("R2", "R", "1k")), (3, e("C2", "C", "10n")), (3, e("R3", "R", "1k"))), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(70, "rlc_transient_pulse", "RLC Transient Pulse Network", "RLC timing", "A pulse source drives a loaded RLC ladder.", "The response combines charge, inductive delay, and resistive damping.", tran, _ladder_factory((e("R1", "R", "47"), e("L1", "L", "1m"), e("R2", "R", "100")), ((1, e("C1", "C", "1u")), (2, e("C2", "C", "100n")), (3, e("R3", "R", "1k"))), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 2m 5m)")),

        # Source-driven circuits and test fixtures (71-100)
        s(71, "dc_battery_load", "DC Battery and Resistive Load", "source test", "A DC voltage source feeds a single load resistor.", "The source current equals voltage divided by load resistance.", op, _series_factory((e("R1", "R", "100"),), source_kind="VDC", source_value="12")),
        s(72, "dc_current_limited_load", "DC Source with Current-Limited Load", "source test", "A DC source uses a series resistor before its load.", "The series resistor limits load current and drops voltage under load.", op, _series_factory((e("R1", "R", "100"), e("R2", "R", "100")), source_kind="VDC", source_value="12")),
        s(73, "source_impedance_fixture", "Voltage Source Impedance Test Fixture", "source test", "A source resistance is explicitly separated from the output load.", "Output voltage falls predictably as the load resistance is reduced.", op, _ladder_factory((e("R1", "R", "50"),), ((1, e("R2", "R", "50")),), source_kind="VDC", source_value="5")),
        s(74, "current_source_resistive_load", "Current Source Resistive Load", "source test", "A current source drives one resistive load.", "Load voltage equals programmed current times resistance.", op, _parallel_factory((e("R1", "R", "2k"),), source_kind="IDC", source_value="1m")),
        s(75, "current_source_rc_load", "Current Source RC Load", "source test", "A current source drives parallel resistance and capacitance.", "The capacitor alters the transient and AC response of the current-driven node.", tran, _parallel_factory((e("R1", "R", "10k"), e("C1", "C", "1u")), source_kind="IDC", source_value="1m")),
        s(76, "current_source_rl_load", "Current Source RL Load", "source test", "A DC current source drives a parallel resistance/inductance load.", "The DC operating point exposes the current path established by the resistive and inductive branches.", op, _parallel_factory((e("R1", "R", "1k"), e("L1", "L", "10m")), source_kind="IDC", source_value="1m")),
        s(77, "current_source_rlc_load", "Current Source RLC Transient Load", "source test", "A DC current source drives a resistive/reactive parallel load for transient inspection.", "The resistor provides a DC return while L and C determine the transient energy storage behavior.", tran, _parallel_factory((e("R1", "R", "10k"), e("L1", "L", "10m"), e("C1", "C", "100n")), source_kind="IDC", source_value="1m")),
        s(78, "sine_resistive_load", "Sine Source Resistive Load", "source test", "A sine voltage source drives a pure resistor.", "Voltage and current are in phase at the programmed sine frequency.", tran, _series_factory((e("R1", "R", "1k"),), source_kind="VSIN", source_value="SINE(0 2 1k)")),
        s(79, "sine_rc_low_pass", "Sine-Driven RC Low-Pass", "source test", "A sine source drives a first-order RC low-pass network.", "Changing frequency shows the expected amplitude roll-off and phase lag.", tran, _ladder_factory((e("R1", "R", "1k"),), ((1, e("C1", "C", "100n")),), source_kind="VSIN", source_value="SINE(0 1 1k)")),
        s(80, "sine_rl_low_pass", "Sine-Driven RL Low-Pass", "source test", "A sine source drives a series inductor and resistive output.", "Output across the resistor falls with frequency above the RL corner.", tran, _ladder_factory((e("L1", "L", "10m"),), ((1, e("R1", "R", "100")),), source_kind="VSIN", source_value="SINE(0 1 1k)")),
        s(81, "sine_series_resonance", "Sine-Driven Series Resonance", "source test", "A sine source drives a series RLC branch.", "Branch current is greatest around the tuned resonance.", tran, _series_factory((e("R1", "R", "10"), e("L1", "L", "10m"), e("C1", "C", "100n")), source_kind="VSIN", source_value="SINE(0 1 5k)")),
        s(82, "pulse_rc_step", "Pulse-Driven RC Step Response", "source test", "A pulse input is filtered by a first-order RC section.", "The output exponentially follows rising and falling source edges.", pulse_tran, _ladder_factory((e("R1", "R", "10k"),), ((1, e("C1", "C", "1u")),), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(83, "pulse_rl_step", "Pulse-Driven RL Step Response", "source test", "A pulse input drives a series RL branch.", "Inductor current follows an exponential transient at each edge.", pulse_tran, _series_factory((e("R1", "R", "100"), e("L1", "L", "10m")), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(84, "pulse_rlc_step", "Pulse-Driven RLC Step Response", "source test", "A fast pulse excites a damped RLC branch.", "The response can overshoot and ring depending on R, L, and C.", pulse_tran, _series_factory((e("R1", "R", "47"), e("L1", "L", "1m"), e("C1", "C", "1u")), source_kind="VPULSE", source_value="PULSE(0 5 0 100n 100n 1m 4m)")),
        s(85, "ac_small_signal_resistor", "AC Small-Signal Resistive Load", "source test", "A donor-observed Misc signal source drives a resistor for AC sweep.", "The resistor has a flat magnitude and zero reactive phase response.", ac, _parallel_factory((e("R1", "R", "1k"),), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(86, "ac_small_signal_rc", "AC Small-Signal RC Low-Pass", "source test", "A small-signal source drives the basic RC low-pass transfer network.", "The AC sweep reveals its single-pole response.", ac, _ladder_factory((e("R1", "R", "1k"),), ((1, e("C1", "C", "100n")),), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(87, "ac_small_signal_rl", "AC Small-Signal RL Low-Pass", "source test", "A small-signal source drives the basic RL low-pass transfer network.", "The AC sweep reveals the RL frequency-dependent divider response.", ac, _ladder_factory((e("L1", "L", "10m"),), ((1, e("R1", "R", "100")),), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(88, "ac_small_signal_series_resonance", "AC Small-Signal Series Resonance", "source test", "A small-signal AC source drives a series RLC sweep fixture.", "The sweep exposes the series-resonant peak.", ac, _series_factory((e("R1", "R", "10"), e("L1", "L", "10m"), e("C1", "C", "100n")), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(89, "ac_small_signal_parallel_resonance", "AC Small-Signal Parallel Resonance", "source test", "A small-signal AC source drives a parallel RLC sweep fixture.", "The sweep exposes the parallel-resonant impedance peak.", ac, _parallel_factory((e("R1", "R", "10k"), e("L1", "L", "10m"), e("C1", "C", "100n")), source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(90, "ac_wheatstone_excitation", "AC Wheatstone Bridge Excitation", "source test", "A balanced resistor bridge is excited by the stock AC signal symbol.", "The two bridge midpoints match when the four arm ratios match.", ac, _bridge_factory(source_kind="MISC_SIGNAL", source_value=None, source_parameters={"ac": "1"})),
        s(91, "dc_bias_ac_coupling", "DC-Bias AC-Coupling Network", "source test", "A sine input is capacitor-coupled into a separate DC bias network.", "OUT is an AC signal centered around the DC bias condition.", tran, _bias_coupling_factory()),
        s(92, "two_tone_resistive_summer", "Two-Tone Resistive Summer", "source test", "Two different sine frequencies combine through equal resistors.", "OUT contains both tones without nonlinear mixing products.", tran, _summer_factory(source_a_kind="VSIN", source_a_value="SINE(0 1 1k)", source_b_kind="VSIN", source_b_value="SINE(0 1 3k)")),
        s(93, "pulse_rc_timing", "Pulse-Driven RC Timing Network", "source test", "A pulse source feeds a long RC time constant.", "The capacitor node produces a repeatable analog timing ramp.", pulse_tran, _ladder_factory((e("R1", "R", "100k"),), ((1, e("C1", "C", "100n")),), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 2m 10m)")),
        s(94, "pulse_rl_current_ramp", "Pulse-Driven RL Current Ramp", "source test", "A pulse source drives a low-resistance series RL path.", "Inductor current ramps according to the applied voltage and inductance.", pulse_tran, _series_factory((e("R1", "R", "10"), e("L1", "L", "10m")), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(95, "capacitive_load_step", "Capacitive Load Step Response", "source test", "A pulsed source drives a capacitive load through source resistance.", "The load voltage slews according to the RC time constant.", pulse_tran, _ladder_factory((e("R1", "R", "10"),), ((1, e("C1", "C", "100u")),), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 5m 10m)")),
        s(96, "inductive_load_step", "Inductive Load Step Response", "source test", "A pulsed source drives an inductive load with winding resistance.", "Current ramps gradually rather than stepping instantaneously.", pulse_tran, _series_factory((e("R1", "R", "10"), e("L1", "L", "10m"), e("R2", "R", "10")), source_kind="VPULSE", source_value="PULSE(0 12 0 1u 1u 5m 10m)")),
        s(97, "rlc_startup_transient", "RLC Startup Transient Network", "source test", "A DC step surrogate excites a loaded RLC network.", "Startup shows the damped natural response of the reactive network.", pulse_tran, _ladder_factory((e("R1", "R", "22"), e("L1", "L", "1m")), ((2, e("C1", "C", "10u")), (2, e("R2", "R", "1k"))), source_kind="VPULSE", source_value="PULSE(0 5 0 1u 1u 20m 40m)")),
        s(98, "voltage_load_regulation", "Voltage-Source Load-Regulation Test", "source test", "A finite source resistance feeds a resistive/capacitive output load.", "The output changes with load current and the capacitor affects transients.", tran, _ladder_factory((e("R1", "R", "10"),), ((1, e("R2", "R", "100")), (1, e("C1", "C", "100u"))), source_kind="VPULSE", source_value="PULSE(0 12 0 1u 1u 5m 10m)")),
        s(99, "current_source_compliance", "Current-Source Compliance Test Network", "source test", "A current source drives a resistor-capacitor load within a simple DC/transient test fixture.", "The required source voltage changes with the resistive load while the capacitor changes startup behavior.", tran, _parallel_factory((e("R1", "R", "10k"), e("C1", "C", "10n")), source_kind="IDC", source_value="1m")),
        s(100, "passive_rlc_test_bench", "Passive RLC Test Bench Network", "integration test", "A multi-stage pulse-driven passive RLC network for placement and routing stress.", "The generated schematic should remain physically wired, readable, and free of component/wire collisions.", tran, _complex_test_bench_factory()),
    )


def _capacitive_bridge_factory() -> RecipeFactory:
    """Delay creation until after all core factories are defined."""

    def build(_spec: CircuitSpec) -> tuple[list[dict[str, Any]], NetRows]:
        source = _source("MISC_SIGNAL", None, parameters={"ac": "1"})
        components = [
            source,
            _element("C1", "C", "100p"), _element("C2", "C", "100p"),
            _element("C3", "C", "105p"), _element("C4", "C", "100p"),
            _element("R1", "R", "1Meg"), _ground(),
        ]
        return components, (
            ("SUPPLY", ("V1.1", "C1.1", "C3.1")),
            ("LEFT", ("C1.2", "C2.1", "R1.1")),
            ("RIGHT", ("C3.2", "C4.1", "R1.2")),
            ("GND", ("V1.2", "C2.2", "C4.2", "G1.1")),
        )

    return build


def _complexity_score(circuit: Mapping[str, Any]) -> int:
    components = list(circuit.get("components", []))
    nets = circuit.get("nets", {})
    non_ground_nets = [members for name, members in nets.items() if str(name).upper() not in {"0", "GND", "GROUND"}]
    fanout = max((len(members) for members in nets.values()), default=0)
    types = {str(component.get("kind")) for component in components}
    reactive = sum(str(component.get("kind")) in {"C", "L"} for component in components)
    # Stable, explainable weighting: more components, branches, component
    # classes, and reactive stages are harder to place and inspect.
    return len(components) * 10 + len(non_ground_nets) * 4 + fanout * 2 + len(types) * 3 + reactive


def build_common_circuit_corpus() -> dict[str, dict[str, Any]]:
    """Return exactly 100 deterministic, strict shared-JSON circuit documents."""

    specs = _specifications()
    if len(specs) != CORPUS_SIZE:
        raise AssertionError(f"The common circuit corpus must have {CORPUS_SIZE} entries, got {len(specs)}.")
    documents: dict[str, dict[str, Any]] = {}
    source_order: dict[str, int] = {}
    for position, spec in enumerate(specs, 1):
        if spec.circuit_id in documents:
            raise AssertionError(f"Repeated corpus circuit id {spec.circuit_id}.")
        components, nets = spec.factory(spec)
        document = _document(spec, components, nets)
        document["common_circuit_corpus"]["corpus_position"] = position
        document["common_circuit_corpus"]["complexity_score"] = _complexity_score(document)
        documents[spec.circuit_id] = document
        source_order[spec.circuit_id] = position
    ranked = sorted(
        documents,
        key=lambda circuit_id: (-int(documents[circuit_id]["common_circuit_corpus"]["complexity_score"]), source_order[circuit_id]),
    )
    for rank, circuit_id in enumerate(ranked, 1):
        documents[circuit_id]["common_circuit_corpus"]["complexity_rank"] = rank
        documents[circuit_id]["common_circuit_corpus"]["top_10_complex"] = rank <= 10
    return documents


def top_complex_circuits(limit: int = 10) -> list[dict[str, Any]]:
    """Return concise metadata for the corpus's deterministic complexity top-N."""

    if limit < 1:
        raise ValueError("limit must be positive.")
    corpus = build_common_circuit_corpus()
    ranked = sorted(corpus.values(), key=lambda item: int(item["common_circuit_corpus"]["complexity_rank"]))
    return [
        {
            "circuit_id": item["circuit_id"],
            "title": item["common_circuit_corpus"]["title"],
            "complexity_rank": item["common_circuit_corpus"]["complexity_rank"],
            "complexity_score": item["common_circuit_corpus"]["complexity_score"],
            "component_count": len(item["components"]),
        }
        for item in ranked[:limit]
    ]


def accuracy_check_text(circuit: Mapping[str, Any]) -> str:
    """Human-readable deterministic acceptance checklist for one fixture."""

    metadata = circuit["common_circuit_corpus"]
    directives = "\n".join(f"  - {item}" for item in circuit.get("spice_directives", [])) or "  - (none)"
    return "\n".join(
        (
            f"Circuit: {metadata['title']}",
            f"ID: {circuit['circuit_id']}",
            f"Category: {metadata['category']}",
            f"Description: {metadata['description']}",
            "",
            "Expected electrical behavior:",
            f"  {metadata['expected_behavior']}",
            "",
            "Requested LTspice directives:",
            directives,
            "",
            "Deterministic preflight checks (must all pass):",
            "  1. The donor-native adapter accepts circuit.json.",
            "  2. expected_netlist has exactly the same named endpoint sets as nets.",
            "  3. Every current-catalogue component pin belongs to exactly one net.",
            "  4. The generated ASC contains stock symbols and physical WIRE records only.",
            "  5. LTspice opens the ASC without a symbol/load error; inspect the named behavior with the listed directive.",
            "",
            "Scope note: this is a component-limited passive/source test fixture. It is not a claim of an unavailable active-device implementation.",
            "",
        )
    )


def corpus_index_markdown(corpus: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    """Render a stable, text-only index without adding a 101st JSON file."""

    documents = corpus or build_common_circuit_corpus()
    ordered = sorted(documents.values(), key=lambda item: int(item["common_circuit_corpus"]["corpus_position"]))
    lines = [
        "# Common donor-native LTspice circuit corpus",
        "",
        "This bundle contains 100 canonical shared-JSON circuits. Each folder has one `circuit.json` and one `accuracy_check.txt`.",
        "",
        "| # | Circuit | Category | Components | Complexity rank |",
        "| ---: | --- | --- | ---: | ---: |",
    ]
    for item in ordered:
        data = item["common_circuit_corpus"]
        lines.append(
            f"| {data['corpus_position']} | {data['title']} | {data['category']} | "
            f"{len(item['components'])} | {data['complexity_rank']} |"
        )
    lines.extend(("", "The complexity rank is deterministic placement/routing review priority, not a statement of electrical superiority.", ""))
    return "\n".join(lines)


def write_common_circuit_corpus(directory: str | Path) -> list[Path]:
    """Write 100 foldered fixture documents into a new or empty directory.

    The safety rule mirrors the native progression matrix: an existing,
    non-empty evidence directory is never overwritten.  Exactly 100 JSON
    files are written, one per circuit; the index deliberately remains Markdown.
    """

    target = Path(directory)
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"Corpus output directory must be empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    corpus = build_common_circuit_corpus()
    ordered = sorted(corpus.values(), key=lambda item: int(item["common_circuit_corpus"]["corpus_position"]))
    written: list[Path] = []
    for circuit in ordered:
        metadata = circuit["common_circuit_corpus"]
        folder = target / f"{int(metadata['corpus_position']):03d}_{_slug(str(metadata['title']))}"
        folder.mkdir()
        json_path = folder / "circuit.json"
        json_path.write_text(json.dumps(circuit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (folder / "accuracy_check.txt").write_text(accuracy_check_text(circuit), encoding="utf-8")
        written.append(json_path)
    (target / "CORPUS_INDEX.md").write_text(corpus_index_markdown(corpus), encoding="utf-8")
    if len(written) != CORPUS_SIZE:
        raise AssertionError(f"Expected {CORPUS_SIZE} JSON documents, wrote {len(written)}.")
    return written


def write_common_circuit_zip(directory: str | Path, archive: str | Path) -> Path:
    """Write the foldered corpus then package it as a ZIP for hand-off."""

    target = Path(directory)
    write_common_circuit_corpus(target)
    archive_path = Path(archive)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        raise ValueError(f"Refusing to overwrite existing corpus archive: {archive_path}")
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(target.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(target))
    return archive_path


def validate_common_circuit_corpus(*, route: bool = False, canonicalize: bool = True) -> dict[str, Any]:
    """Pass every corpus document through the active shared/native path.

    By default each document first passes through the shared JSON
    canonicalizer used by the actual executable, then through the active
    donor-native adapter.  ``route=True`` additionally invokes the normal
    placer and direct-wire router.  Imports are deliberately local so this
    source producer has no import-time coupling to an executable or GUI
    installation.
    """

    from ltspice.pipeline.native_canonical_adapter import adapt_canonical_native_circuit
    from ltspice.pipeline.input_adapter import canonicalize_source

    corpus = build_common_circuit_corpus()
    failures: list[dict[str, str]] = []
    routed = 0
    canonicalized = 0
    with tempfile.TemporaryDirectory(prefix="progeneda-common-circuit-validation-") as temporary:
        temporary_root = Path(temporary)
        for circuit_id, circuit in corpus.items():
            try:
                active_circuit: Mapping[str, Any] = circuit
                if canonicalize:
                    source = temporary_root / f"{circuit_id}.json"
                    source.write_text(json.dumps(circuit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    active_circuit, _shared_report, _original = canonicalize_source(source, routing_mode="wire")
                    canonicalized += 1
                native, adapter_report = adapt_canonical_native_circuit(active_circuit)
                if not adapter_report.get("expected_netlist_checked"):
                    raise AssertionError("adapter did not assert expected_netlist parity")
                if route:
                    from ltspice.pipeline.native_placer import place_native_components
                    from ltspice.pipeline.native_wire_router import route_native_wires

                    placement, placement_report = place_native_components(native)
                    if not placement_report.get("ok"):
                        raise AssertionError(f"placement failed: {placement_report}")
                    _routes, routing_report = route_native_wires(native, placement)
                    if not routing_report.get("ok"):
                        raise AssertionError(f"routing failed: {routing_report}")
                    routed += 1
            except Exception as exc:  # report all corpus failures for development triage
                failures.append({"circuit_id": circuit_id, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "schema": CORPUS_SCHEMA,
        "ok": not failures,
        "circuit_count": len(corpus),
        "shared_canonicalized": canonicalized,
        "adapter_validated": len(corpus) - len(failures),
        "routed": routed,
        "failures": failures,
        "top_10_complex": top_complex_circuits(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the 100-circuit donor-native common-circuit corpus.")
    parser.add_argument("output", type=Path, help="New or empty folder for the 100 named circuit folders.")
    parser.add_argument("--zip", dest="archive", type=Path, help="Optional new ZIP archive path.")
    parser.add_argument("--validate", action="store_true", help="Validate every emitted JSON through the active adapter.")
    parser.add_argument("--route", action="store_true", help="With --validate, also run placer and direct-wire router for all circuits.")
    args = parser.parse_args()
    if args.route and not args.validate:
        parser.error("--route requires --validate")
    if args.archive:
        archive = write_common_circuit_zip(args.output, args.archive)
        written = sorted(args.output.rglob("circuit.json"))
    else:
        written = write_common_circuit_corpus(args.output)
        archive = None
    validation = validate_common_circuit_corpus(route=args.route) if args.validate else None
    result: dict[str, Any] = {
        "schema": CORPUS_SCHEMA,
        "output": str(args.output.resolve()),
        "json_circuit_count": len(written),
        "archive": str(archive.resolve()) if archive else None,
        "top_10_complex": top_complex_circuits(),
    }
    if validation is not None:
        result["validation"] = validation
        if not validation["ok"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            raise SystemExit(1)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    main()
