"""Compare an LTspice-exported netlist against the generated native contract.

The static ASC parser proves that the files we wrote agree with our own native
format reader.  This module adds a separate boundary check when the authorized
LTspice executable exports a ``.net`` file: the executable's instance pin
order and node partition must still match the generated circuit.  Node names
are deliberately compared by connectivity rather than by spelling because
LTspice assigns names such as ``N001`` to safe direct-wire nets without a
visible label.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .component_selector import SelectedComponent
from .ltspice_wire_maker import WirePlan


ORACLE_NETLIST_SCHEMA = "progen-ltspice-oracle-netlist-validator/v0.1"


@dataclass(frozen=True)
class OracleNetlistInstance:
    """One top-level-looking SPICE instance line from an exported netlist."""

    name: str
    tokens: tuple[str, ...]
    line_number: int
    text: str


def _logical_lines(text: str) -> Iterable[tuple[int, str]]:
    """Yield comments-free logical SPICE lines, joining ``+`` continuations."""

    pending: str | None = None
    pending_line = 0
    for line_number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("*"):
            continue
        if stripped.startswith("+"):
            if pending is not None:
                pending += " " + stripped[1:].strip()
            continue
        if pending is not None:
            yield pending_line, pending
        pending = stripped
        pending_line = line_number
    if pending is not None:
        yield pending_line, pending


def parse_oracle_netlist(text: str) -> list[OracleNetlistInstance]:
    """Parse stable instance-token facts without pretending to be a full SPICE parser."""

    instances: list[OracleNetlistInstance] = []
    for line_number, line in _logical_lines(text):
        if line.startswith("."):
            continue
        tokens = tuple(token for token in re.split(r"\s+", line) if token)
        if not tokens or not re.match(r"^[A-Za-z]", tokens[0]):
            continue
        instances.append(OracleNetlistInstance(tokens[0], tokens, line_number, line))
    return instances


def _expected_instance_name(component: SelectedComponent) -> str:
    """Return LTspice's prefix-governed netlist identity for an ASC InstName."""

    # ``SelectedComponent`` owns the exact evidence identity because LTspice
    # uses a section-sign separator for a Prefix that differs from InstName:
    # an ASC ``InstName Q1`` with symbol Prefix ``X`` netlists as ``X§Q1``,
    # not the tempting but wrong ``XQ1``.  Recompute neither spelling here nor
    # assume references happen to begin with their electrical Prefix.
    return component.native_netlist_name.upper()


def _ordered_pin_numbers(component: SelectedComponent) -> tuple[str, ...]:
    """LTspice serializes nodes in numeric SpiceOrder, not display geometry order."""

    return tuple(
        pin.number
        for pin in sorted(
            component.profile.pins,
            key=lambda pin: (0, int(pin.number)) if pin.number.isdecimal() else (1, pin.number),
        )
    )


def validate_oracle_netlist(
    netlist_text: str,
    *,
    selected: Iterable[SelectedComponent],
    wire_plan: WirePlan,
) -> dict[str, object]:
    """Validate executable netlisting preserves each expected native net.

    Only selected component instances are examined, so implementation details
    inside a project-local ``.subckt`` cannot be mistaken for top-level user
    devices.  Every selected non-pseudo component must occur exactly once and
    expose the expected number of nodes.  Those nodes are then compared as an
    endpoint partition against the wire-plan contract.
    """

    expected_components = [item for item in selected if not item.profile.is_pseudo_component]
    parsed = parse_oracle_netlist(netlist_text)
    by_name: dict[str, list[OracleNetlistInstance]] = {}
    for instance in parsed:
        by_name.setdefault(instance.name.upper(), []).append(instance)

    errors: list[str] = []
    endpoint_nodes: dict[str, str] = {}
    component_instances: dict[str, dict[str, object]] = {}
    for component in expected_components:
        expected_name = _expected_instance_name(component)
        matches = by_name.get(expected_name, [])
        if not matches:
            errors.append(
                f"LTspice exported no instance for {component.ref} (expected native instance {expected_name})."
            )
            continue
        if len(matches) != 1:
            errors.append(f"LTspice exported {len(matches)} instances named {expected_name}; expected exactly one for {component.ref}.")
            continue
        instance = matches[0]
        expected_prefix = component.profile.electrical_prefix.upper()
        if expected_prefix and not instance.name.upper().startswith(expected_prefix):
            errors.append(
                f"LTspice instance {instance.name} for {component.ref} does not use expected Prefix {expected_prefix}."
            )
        pin_numbers = _ordered_pin_numbers(component)
        node_tokens = instance.tokens[1 : 1 + len(pin_numbers)]
        if len(node_tokens) != len(pin_numbers):
            errors.append(
                f"LTspice instance {instance.name} has {len(node_tokens)} node(s); {component.ref}/{component.kind} requires {len(pin_numbers)}."
            )
            continue
        nodes_by_pin = dict(zip(pin_numbers, node_tokens, strict=True))
        for pin, node in nodes_by_pin.items():
            endpoint_nodes[f"{component.ref}.{pin}"] = node
        component_instances[component.ref] = {
            "native_instance": instance.name,
            "line_number": instance.line_number,
            "nodes_by_spice_order": nodes_by_pin,
        }

    expected_endpoints = {
        endpoint
        for members in wire_plan.expected_native_nets.values()
        for endpoint in members
    }
    actual_endpoints = set(endpoint_nodes)
    missing = sorted(expected_endpoints - actual_endpoints)
    unexpected = sorted(actual_endpoints - expected_endpoints)
    if missing:
        errors.append(f"LTspice netlist is missing expected endpoint(s): {', '.join(missing)}.")
    if unexpected:
        errors.append(f"LTspice netlist exposed endpoint(s) outside the wire plan: {', '.join(unexpected)}.")

    node_owner: dict[str, str] = {}
    native_nets: dict[str, dict[str, object]] = {}
    for logical_net, members in wire_plan.expected_native_nets.items():
        # SPICE node names are case-insensitive. Preserve the first spelling
        # for evidence, but compare the endpoint partition by normalized name
        # so an oracle that varies case cannot look like a split circuit.
        available_by_node = {
            endpoint_nodes[member].upper(): endpoint_nodes[member]
            for member in members
            if member in endpoint_nodes
        }
        if len(available_by_node) > 1:
            errors.append(
                f"LTspice split expected net {logical_net!r} across node(s): {', '.join(sorted(available_by_node.values()))}."
            )
        if not available_by_node:
            continue
        normalized_node, node = next(iter(available_by_node.items()))
        owner = node_owner.setdefault(normalized_node, logical_net)
        if owner != logical_net:
            errors.append(
                f"LTspice merged expected nets {owner!r} and {logical_net!r} onto node {node!r}."
            )
        native_nets[logical_net] = {"node": node, "members": list(members)}

    return {
        "schema": ORACLE_NETLIST_SCHEMA,
        "stage": "ltspice_exported_netlist_validator",
        "ok": not errors,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "component_instances": component_instances,
        "native_nets": native_nets,
        "parsed_instance_count": len(parsed),
    }
