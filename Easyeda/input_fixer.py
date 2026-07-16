"""Deterministic repair and full-pin accounting for EasyEDA circuit JSON."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .catalogue import get_entry, normalize_kind
from .donor_source import DonorPacket, EasyedaDonorSource
from .ir import MAX_COMPONENTS, ROUTING_MODES, CircuitInputError, resolve_pin


FIXER_SCHEMA = "progen-easyeda-input-fixer/v1"


class InputFixError(CircuitInputError):
    """The input cannot be repaired without inventing unsupported meaning."""


@dataclass(frozen=True)
class InputFixResult:
    fixed: dict[str, Any]
    report: dict[str, Any]


_COMMENT_OR_STRING = re.compile(
    r'("(?:\\.|[^"\\])*")|(/\*.*?\*/|//[^\r\n]*)',
    flags=re.DOTALL,
)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_NET_SAFE = re.compile(r"[^A-Za-z0-9_.+/#-]+")
_PIN_SAFE = re.compile(r"[^A-Za-z0-9_.+/#-]+")


def _strip_json_comments(text: str) -> str:
    return _COMMENT_OR_STRING.sub(
        lambda match: match.group(1) if match.group(1) is not None else "",
        text,
    )


def _parse_input(value: Path | str | Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    changes: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        return deepcopy(dict(value)), changes
    path = Path(value).expanduser().resolve()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise InputFixError(f"Cannot read circuit JSON {path}: {exc}") from exc
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        repaired = _TRAILING_COMMA.sub(r"\1", _strip_json_comments(text))
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError as exc:
            raise InputFixError(f"Cannot repair circuit JSON {path}: {exc}") from exc
        changes.append(
            {
                "code": "REPAIRED_JSON_SYNTAX",
                "path": "$",
                "detail": "Removed JSON comments and/or trailing commas.",
                "confidence": "high",
            }
        )
    if not isinstance(parsed, dict):
        raise InputFixError("Circuit input must be one JSON object.")
    return parsed, changes


def _slug(value: object, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.+-]+", "_", str(value or "").strip()).strip("_.")
    return text or fallback


def _safe_net(value: object, fallback: str) -> str:
    text = _NET_SAFE.sub("_", str(value or "").strip()).strip("_")
    return text or fallback


def _safe_pin(value: object) -> str:
    return _PIN_SAFE.sub("_", str(value or "").strip()).strip("_")


def _component_list(raw: Mapping[str, Any], changes: list[dict[str, Any]]) -> list[Any]:
    value = raw.get("components", raw.get("parts", raw.get("devices")))
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, Mapping):
        result: list[Any] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                copied = dict(item)
                copied.setdefault("ref", str(key))
                result.append(copied)
            else:
                result.append({"ref": str(key), "kind": item})
        changes.append(
            {
                "code": "COMPONENT_MAP_TO_LIST",
                "path": "$.components",
                "detail": "Converted a reference-keyed component object to the canonical list.",
                "confidence": "high",
            }
        )
        return result
    raise InputFixError("Circuit input needs a non-empty components list or object.")


def _pin_items(raw: Mapping[str, Any]) -> list[tuple[object, object]]:
    value = raw.get("pins", raw.get("connections", raw.get("nodes", {})))
    if value in (None, ""):
        return []
    if isinstance(value, Mapping):
        return list(value.items())
    if isinstance(value, list):
        result: list[tuple[object, object]] = []
        for item in value:
            if isinstance(item, Mapping):
                result.append(
                    (
                        item.get("pin", item.get("number", item.get("name"))),
                        item.get("net", item.get("node", item.get("connection"))),
                    )
                )
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                result.append((item[0], item[1]))
        return result
    raise InputFixError("Component pins/connections must be an object or list.")


def _top_level_endpoint_hints(raw: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    values = (raw.get("nets"), raw.get("expected_netlist"))
    for value in values:
        if isinstance(value, Mapping):
            iterable = value.items()
        elif isinstance(value, list):
            iterable = []
            for item in value:
                if not isinstance(item, Mapping):
                    continue
                iterable.append(
                    (
                        item.get("name", item.get("net")),
                        item.get("members", item.get("nodes", item.get("connections", []))),
                    )
                )
        else:
            continue
        for name, members in iterable:
            if isinstance(members, Mapping):
                members = members.get("members", members.get("nodes", []))
            if isinstance(members, str):
                members = [members]
            if not isinstance(members, list):
                continue
            net = _safe_net(name, "UNNAMED")
            for endpoint in members:
                token = str(endpoint or "").strip()
                if token:
                    result.setdefault(token, net)
    return result


def _unique_reference(
    offered: object,
    prefix: str,
    index: int,
    used: set[str],
) -> tuple[str, bool]:
    base = _slug(offered, f"{prefix}{index}")
    if base not in used:
        used.add(base)
        return base, False
    suffix = 2
    while f"{base}_{suffix}" in used:
        suffix += 1
    value = f"{base}_{suffix}"
    used.add(value)
    return value, True


def _resolve_packets(
    source: EasyedaDonorSource,
    kinds: set[str],
) -> dict[str, DonorPacket]:
    workers = min(8, max(1, len(kinds)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="easyeda-fixer") as executor:
        futures = {
            kind: executor.submit(source.resolve, get_entry(kind))
            for kind in sorted(kinds)
        }
        return {kind: future.result() for kind, future in futures.items()}


def _guess_net(reference: str, pin_number: str, pin_name: str) -> tuple[str, str]:
    token = re.sub(r"[^A-Z0-9]+", "_", pin_name.upper()).strip("_")
    if token in {"NC", "DNC", "N_C", "RES", "RESERVED"} or token.startswith("NC"):
        role = "NC"
    elif any(name in token for name in ("GND", "VSS", "VSSA", "VSSD")):
        role = "GROUND"
    elif token in {"EP", "PAD", "EXPOSED_PAD"}:
        role = "GROUND_PAD"
    elif any(
        name in token
        for name in ("VCC", "VDD", "VDDA", "VDDD", "VBAT", "AVCC", "VIN", "VBUS", "3V3", "5V")
    ):
        role = "POWER"
    else:
        role = "UNUSED"
    return (
        _safe_net(f"GUESS_{role}_{reference}_{pin_number}", "GUESS_UNUSED"),
        role.lower(),
    )


def repair_circuit_input(
    value: Path | str | Mapping[str, Any],
    source: EasyedaDonorSource,
    *,
    complete_unbound_pins: bool = True,
) -> InputFixResult:
    """Return canonical, donor-resolved JSON and a transparent repair report."""

    raw, changes = _parse_input(value)
    project_raw = raw.get("project") if isinstance(raw.get("project"), Mapping) else {}
    project_name = _slug(
        project_raw.get("name")
        or raw.get("circuit_id")
        or raw.get("name")
        or raw.get("title"),
        "easyeda_project",
    )
    project_title = str(
        project_raw.get("title")
        or raw.get("circuit_name")
        or raw.get("title")
        or project_name
    ).strip() or project_name
    routing_raw = raw.get("routing") if isinstance(raw.get("routing"), Mapping) else {}
    routing_mode = str(
        routing_raw.get("mode") or raw.get("routing_mode") or "combination"
    ).strip().lower()
    if routing_mode not in ROUTING_MODES:
        changes.append(
            {
                "code": "DEFAULTED_ROUTING_MODE",
                "path": "$.routing.mode",
                "before": routing_mode,
                "after": "combination",
                "confidence": "high",
            }
        )
        routing_mode = "combination"

    raw_components = _component_list(raw, changes)
    if not raw_components:
        raise InputFixError("Circuit input needs at least one component.")
    if len(raw_components) > MAX_COMPONENTS:
        raise InputFixError(
            f"EasyEDA supports at most {MAX_COMPONENTS} input components; "
            f"received {len(raw_components)}."
        )

    hints = _top_level_endpoint_hints(raw)
    provisional: list[dict[str, Any]] = []
    used_refs: set[str] = set()
    used_ids: set[str] = set()
    kinds: set[str] = set()
    original_to_reference: dict[str, str] = {}
    for index, item in enumerate(raw_components, start=1):
        if not isinstance(item, Mapping):
            raise InputFixError(f"Component {index} must be an object.")
        offered_kind = next(
            (
                item.get(key)
                for key in ("kind", "type", "component", "family", "name")
                if item.get(key)
            ),
            None,
        )
        try:
            kind = normalize_kind(offered_kind)
        except ValueError as exc:
            raise InputFixError(str(exc)) from exc
        entry = get_entry(kind)
        offered_ref = item.get("ref", item.get("reference", item.get("designator")))
        reference, duplicate_ref = _unique_reference(
            offered_ref,
            entry.reference_prefix,
            index,
            used_refs,
        )
        original_ref = str(offered_ref or reference).strip()
        original_to_reference.setdefault(original_ref, reference)
        if duplicate_ref:
            changes.append(
                {
                    "code": "DEDUPLICATED_REFERENCE",
                    "path": f"$.components[{index - 1}].ref",
                    "before": original_ref,
                    "after": reference,
                    "confidence": "high",
                }
            )
        identifier, duplicate_id = _unique_reference(
            item.get("id") or reference,
            entry.reference_prefix,
            index,
            used_ids,
        )
        if duplicate_id:
            changes.append(
                {
                    "code": "DEDUPLICATED_ID",
                    "path": f"$.components[{index - 1}].id",
                    "after": identifier,
                    "confidence": "high",
                }
            )
        pin_items = _pin_items(item)
        if kind == "GND" and not pin_items:
            pin_items = [("1", "GND")]
        elif kind == "VCC" and not pin_items:
            pin_items = [("1", item.get("net") or item.get("value") or "VCC")]
        provisional.append(
            {
                "id": identifier,
                "ref": reference,
                "kind": kind,
                "value": str(item.get("value") or entry.default_value),
                "role": str(item.get("role") or ""),
                "block": str(item.get("block") or "main"),
                "_pin_items": pin_items,
            }
        )
        kinds.add(kind)

    packets = _resolve_packets(source, kinds)
    components: list[dict[str, Any]] = []
    guessed_nets: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    for index, component in enumerate(provisional):
        packet = packets[component["kind"]]
        reference = component["ref"]
        mapped_by_number: dict[str, str] = {}
        input_pin_names: dict[str, str] = {}
        for pin, net in component.pop("_pin_items"):
            pin_text = _safe_pin(pin)
            if not pin_text:
                continue
            endpoint_hint = hints.get(f"{reference}.{pin_text}")
            if endpoint_hint is None:
                original_reference = next(
                    (
                        original
                        for original, fixed_reference in original_to_reference.items()
                        if fixed_reference == reference
                    ),
                    reference,
                )
                endpoint_hint = hints.get(f"{original_reference}.{pin_text}")
            inferred_net = net or endpoint_hint
            net_text = _safe_net(
                inferred_net,
                f"GUESS_UNUSED_{reference}_{pin_text}",
            )
            try:
                descriptor = resolve_pin(packet, pin_text)
            except CircuitInputError as exc:
                raise InputFixError(
                    f"Component {reference} has unsupported pin {pin_text!r}: {exc}"
                ) from exc
            previous = mapped_by_number.get(descriptor.number)
            if previous is not None and previous != net_text:
                raise InputFixError(
                    f"Component {reference} electrical pin {descriptor.number} is assigned "
                    f"to both {previous!r} and {net_text!r}."
                )
            mapped_by_number[descriptor.number] = net_text
            input_pin_names[descriptor.number] = pin_text
            if not inferred_net:
                guessed_nets.append(
                    {
                        "net": net_text,
                        "endpoint": f"{reference}.{descriptor.number}",
                        "pin_name": descriptor.name,
                        "role": "empty_binding",
                        "routing": "terminal",
                        "confidence": "conservative",
                    }
                )
                changes.append(
                    {
                        "code": "REPAIRED_EMPTY_PIN_NET",
                        "path": f"$.components[{index}].pins.{descriptor.number}",
                        "after": net_text,
                        "confidence": "conservative",
                    }
                )

        unique_source_pins: dict[str, Any] = {}
        for descriptor in packet.pins:
            unique_source_pins.setdefault(descriptor.number, descriptor)
        missing_before = [
            number for number in unique_source_pins if number not in mapped_by_number
        ]
        if complete_unbound_pins:
            for number in missing_before:
                descriptor = unique_source_pins[number]
                net, role = _guess_net(reference, number, descriptor.name)
                mapped_by_number[number] = net
                guessed_nets.append(
                    {
                        "net": net,
                        "endpoint": f"{reference}.{number}",
                        "pin_name": descriptor.name,
                        "role": role,
                        "routing": "terminal",
                        "confidence": "conservative",
                    }
                )
                changes.append(
                    {
                        "code": "ACCOUNTED_UNBOUND_SOURCE_PIN",
                        "path": f"$.components[{index}].pins.{number}",
                        "after": net,
                        "detail": f"{reference} source pin {number}:{descriptor.name}",
                        "confidence": "conservative",
                    }
                )
        component["pins"] = dict(
            sorted(
                mapped_by_number.items(),
                key=lambda item: (not item[0].isdigit(), int(item[0]) if item[0].isdigit() else item[0]),
            )
        )
        components.append(component)
        coverage.append(
            {
                "reference": reference,
                "kind": component["kind"],
                "raw_symbol_pin_count": len(packet.pins),
                "unique_electrical_pin_count": len(unique_source_pins),
                "input_bound_pin_count": len(input_pin_names),
                "missing_before_fix": missing_before,
                "missing_after_fix": [
                    number for number in unique_source_pins if number not in mapped_by_number
                ],
                "complete": set(mapped_by_number) == set(unique_source_pins),
            }
        )

    nets: dict[str, list[str]] = {}
    for component in components:
        for pin, net in component["pins"].items():
            nets.setdefault(net, []).append(f"{component['ref']}.{pin}")
    net_rows = [
        {"name": name, "members": sorted(members)}
        for name, members in sorted(nets.items())
    ]
    fixed = {
        "schema_version": "progen-easyeda-circuit-ir/v1",
        "project": {
            "name": project_name,
            "title": project_title,
            "target": "easyeda_pro",
        },
        "routing": {"mode": routing_mode},
        "components": components,
        "nets": net_rows,
        "expected_netlist": {
            row["name"]: list(row["members"])
            for row in net_rows
        },
        "input_fixer": {
            "schema": FIXER_SCHEMA,
            "complete_unbound_pins": complete_unbound_pins,
            "guessed_net_count": len(guessed_nets),
            "guessed_nets": guessed_nets,
        },
    }
    report = {
        "schema": FIXER_SCHEMA,
        "passed": all(item["complete"] for item in coverage),
        "component_count": len(components),
        "net_count": len(nets),
        "complete_unbound_pins": complete_unbound_pins,
        "change_count": len(changes),
        "changes": changes,
        "guessed_net_count": len(guessed_nets),
        "guessed_nets": guessed_nets,
        "pin_coverage": coverage,
        "errors": [],
    }
    return InputFixResult(fixed=fixed, report=report)
