"""Metadata-only terminal planning for catalogue pins.

This module starts the IC/three-pin work without emitting Proteus binary
records.  It consumes the node-name map and catalogue pin descriptors, then
classifies which endpoints are already on an accepted two-pin route and which
need new backend pin-coordinate evidence.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any, Mapping

from .component_catalog import ComponentCatalog, load_component_catalog
from .node_name_mapping import build_node_name_mapping


def _pin_count_class(pin_count: int) -> str:
    if pin_count == 2:
        return "two_pin"
    if pin_count == 3:
        return "three_pin"
    return "multi_pin"


def _terminal_status(terminal_support: str, pin_class: str) -> tuple[bool, str]:
    if terminal_support == "accepted_two_pin_v12" and pin_class == "two_pin":
        return True, "accepted_two_pin_v12"
    return (
        False,
        "needs_backend_pin_coordinate_evidence_before_binary_terminal_emission",
    )


def pin_terminal_test_label(pin: str, role: str) -> str:
    """Return a deterministic human-test label such as PIN2RESET."""

    pin_token = re.sub(r"[^A-Z0-9]", "", str(pin).upper()) or "X"
    role_token = re.sub(r"[^A-Z0-9]", "", str(role).upper())
    if not role_token or role_token == "UNKNOWN":
        return f"PIN{pin_token}"
    return f"PIN{pin_token}{role_token}"


def build_pin_terminal_plan(
    payload: Mapping[str, Any],
    *,
    catalog: ComponentCatalog | None = None,
    node_name_mapping: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return normalized terminal work items for every visible endpoint."""

    component_catalog = catalog or load_component_catalog()
    node_map = (
        node_name_mapping
        if node_name_mapping is not None
        else build_node_name_mapping(payload, catalog=component_catalog)
    )
    plans: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    families: Counter[str] = Counter()
    classes: Counter[str] = Counter()

    for node in node_map.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        terminal_label = str(node.get("terminal_label", ""))
        node_name = str(node.get("node", ""))
        for endpoint in node.get("endpoints", []):
            if not isinstance(endpoint, Mapping):
                continue
            part = str(endpoint["part"])
            profile = component_catalog.profile(part)
            pin_count = len(profile.pin_names(include_hidden=True))
            pin_class = _pin_count_class(pin_count)
            families[part] += 1
            classes[pin_class] += 1
            terminal_ready, status = _terminal_status(
                profile.terminal_support,
                pin_class,
            )
            item = {
                "component": str(endpoint["component"]),
                "part": part,
                "pin": str(endpoint["pin"]),
                "raw_pin": str(endpoint.get("raw_pin", endpoint["pin"])),
                "node": node_name,
                "terminal_label": terminal_label,
                "role": str(endpoint.get("role", "unknown")),
                "electrical_type": str(endpoint.get("electrical_type", "unknown")),
                "subpart": endpoint.get("subpart"),
                "hidden": bool(endpoint.get("hidden", False)),
                "pin_count": pin_count,
                "pin_class": pin_class,
                "terminal_support": profile.terminal_support,
                "terminal_emit_ready": terminal_ready,
                "status": status,
            }
            item["test_terminal_label"] = pin_terminal_test_label(
                str(item["pin"]),
                str(item["role"]),
            )
            if item["hidden"]:
                hidden.append(item)
            else:
                plans.append(item)

    blocked = [item for item in plans if not item["terminal_emit_ready"]]
    return {
        "stage": "pin_terminal_planner",
        "valid": bool(node_map.get("valid", False)),
        "binary_emission": {
            "applied": False,
            "reason": (
                "This stage is metadata-only. Three-pin and IC terminals need "
                "backend pin-coordinate evidence before Proteus records are emitted."
            ),
        },
        "node_name_mapping_valid": bool(node_map.get("valid", False)),
        "node_count": int(node_map.get("node_count", 0)),
        "visible_terminal_plan_count": len(plans),
        "hidden_endpoint_count": len(hidden),
        "terminal_emit_ready_count": len(plans) - len(blocked),
        "blocked_terminal_count": len(blocked),
        "family_endpoint_counts": dict(sorted(families.items())),
        "pin_class_counts": dict(sorted(classes.items())),
        "terminal_plans": plans,
        "hidden_endpoints": hidden,
        "blocked_terminals": blocked,
        "errors": list(node_map.get("errors", [])),
    }
