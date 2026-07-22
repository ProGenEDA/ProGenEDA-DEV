"""Conservative canonical-JSON repair for the direct Altium pipeline.

The fixer repairs representation, not electrical intent.  It only derives a
top-level net list from explicit component pins, resolves known pin aliases,
and adds missing audited source pins as named ``GUESS_TERMINAL_*`` singleton
nets.  It never joins a guessed pin to a real user net.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .pipeline_contracts import PipelineError
from .source_catalogue import SourceCatalogue, SourceCatalogueError, load_source_catalogue


FIXER_SCHEMA = "progen-altium-input-fixer/v1"
_UNSAFE_TEXT = re.compile(r"[|\r\n\x00]")
_SAFE_REFERENCE = re.compile(r"[^A-Za-z0-9_.+-]+")
_ROUTING_MODES = {"wire", "terminal", "combination"}


class InputFixError(PipelineError):
    """A loose input cannot be repaired without guessing electrical intent."""


@dataclass(frozen=True)
class FixedInput:
    fixed: dict[str, Any]
    report: dict[str, Any]


def _load(value: Path | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    path = Path(value).expanduser().resolve()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputFixError(f"Cannot read Altium input JSON {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InputFixError("Altium input must be one JSON object.")
    return parsed


def _clean_text(value: Any, fallback: str, *, field: str, changes: list[dict[str, str]]) -> str:
    text = str(value or "").strip() or fallback
    fixed = _UNSAFE_TEXT.sub("_", text)
    if fixed != text:
        changes.append({"field": field, "from": text, "to": fixed, "reason": "native_record_delimiter"})
    return fixed


def _reference(value: Any, index: int, changes: list[dict[str, str]]) -> str:
    text = _clean_text(value, f"X{index}", field=f"components[{index - 1}].ref", changes=changes)
    fixed = _SAFE_REFERENCE.sub("_", text).strip("_.") or f"X{index}"
    if fixed != text:
        changes.append({"field": f"components[{index - 1}].ref", "from": text, "to": fixed, "reason": "safe_reference"})
    return fixed


def _component_items(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidate = raw.get("components")
    if candidate is None:
        candidate = raw.get("parts", raw.get("devices"))
    if isinstance(candidate, Mapping):
        candidate = list(candidate.values())
    if not isinstance(candidate, list) or not candidate:
        raise InputFixError("Input needs a non-empty components/parts/devices list.")
    if not all(isinstance(item, Mapping) for item in candidate):
        raise InputFixError("Every component must be a JSON object.")
    return list(candidate)


def _pin_items(value: Any) -> list[tuple[str, str]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [(str(pin), str(net)) for pin, net in value.items()]
    if isinstance(value, list):
        result: list[tuple[str, str]] = []
        for item in value:
            if not isinstance(item, Mapping):
                raise InputFixError("Component pin lists must contain JSON objects.")
            pin = item.get("pin") or item.get("number") or item.get("name")
            net = item.get("net") or item.get("node")
            result.append((str(pin or ""), str(net or "")))
        return result
    raise InputFixError("Component pins must be an object or list when present.")


def repair_input(
    value: Path | str | Mapping[str, Any],
    *,
    catalogue: SourceCatalogue | None = None,
    routing_mode: str | None = None,
) -> FixedInput:
    """Repair safe structural omissions and return one canonical input object."""

    raw = _load(value)
    source = catalogue or load_source_catalogue()
    changes: list[dict[str, str]] = []
    components: list[dict[str, Any]] = []
    references: set[str] = set()
    guessed_nets: list[str] = []

    for index, item in enumerate(_component_items(raw), start=1):
        kind = _clean_text(
            item.get("kind")
            or item.get("type")
            or item.get("component")
            or item.get("family")
            or item.get("name"),
            "",
            field=f"components[{index - 1}].kind",
            changes=changes,
        )
        if not kind:
            raise InputFixError(f"Component {index} has no kind/type/component field.")
        try:
            template = source.resolve(kind)
        except SourceCatalogueError as exc:
            raise InputFixError(str(exc)) from exc
        reference = _reference(
            item.get("ref") or item.get("reference") or item.get("designator") or item.get("id"),
            index,
            changes,
        )
        if reference in references:
            raise InputFixError(f"Component reference {reference!r} is duplicated; it cannot be repaired safely.")
        references.add(reference)
        identifier = _clean_text(item.get("id"), reference, field=f"components[{index - 1}].id", changes=changes)
        value_text = _clean_text(
            item.get("value") or item.get("label"),
            template.library_reference,
            field=f"components[{index - 1}].value",
            changes=changes,
        )

        pins: dict[str, str] = {}
        native_seen: dict[str, str] = {}
        raw_pins = item.get("pins", item.get("connections"))
        for supplied_pin, raw_net in _pin_items(raw_pins):
            pin = supplied_pin.strip()
            net = _clean_text(raw_net, "", field=f"{reference}.{pin or '?'}", changes=changes)
            if not pin or not net:
                raise InputFixError(f"{reference} has a pin entry without both a pin and a net.")
            try:
                native_pin = template.resolve_pin(pin)
            except SourceCatalogueError as exc:
                raise InputFixError(str(exc)) from exc
            prior = native_seen.setdefault(native_pin, net)
            if prior != net:
                raise InputFixError(
                    f"{reference} assigns aliases of source pin {native_pin!r} to two nets: {prior!r}, {net!r}."
                )
            if pin in pins and pins[pin] != net:
                raise InputFixError(f"{reference}.{pin} is assigned to two nets.")
            pins[pin] = net

        for native_pin in sorted(template.pins):
            if native_pin in native_seen:
                continue
            guessed = f"GUESS_TERMINAL_{reference}_{native_pin}"
            pins[native_pin] = guessed
            guessed_nets.append(guessed)
            changes.append(
                {
                    "field": f"{reference}.{native_pin}",
                    "from": "",
                    "to": guessed,
                    "reason": "missing_source_pin_terminalized",
                }
            )

        components.append(
            {
                "id": identifier,
                "ref": reference,
                "kind": kind,
                "value": value_text,
                "role": _clean_text(item.get("role"), "", field=f"{reference}.role", changes=changes),
                "block": _clean_text(item.get("block"), "main", field=f"{reference}.block", changes=changes),
                "pins": dict(sorted(pins.items())),
            }
        )

    routing = raw.get("routing") if isinstance(raw.get("routing"), Mapping) else {}
    requested_mode = routing_mode or routing.get("mode") or raw.get("routing_mode") or "combination"
    mode = str(requested_mode).strip().casefold()
    if mode not in _ROUTING_MODES:
        changes.append({"field": "routing.mode", "from": str(requested_mode), "to": "combination", "reason": "default_supported_mode"})
        mode = "combination"

    project_raw = raw.get("project") if isinstance(raw.get("project"), Mapping) else {}
    name = _clean_text(project_raw.get("name") or raw.get("name") or raw.get("circuit_id"), "altium_project", field="project.name", changes=changes)
    title = _clean_text(project_raw.get("title") or raw.get("circuit_name"), name, field="project.title", changes=changes)
    nets: dict[str, list[str]] = {}
    for component in components:
        for pin, net in component["pins"].items():
            nets.setdefault(net, []).append(f"{component['ref']}.{pin}")
    canonical_nets = {net: sorted(members) for net, members in sorted(nets.items())}

    fixed = {
        "schema_version": "progen-altium-circuit-ir/v1",
        "project": {"name": name, "title": title, "target": "altium"},
        "routing": {"mode": mode},
        "components": components,
        "nets": [{"name": net, "members": members} for net, members in canonical_nets.items()],
        "expected_netlist": canonical_nets,
        "input_fixer": {
            "schema": FIXER_SCHEMA,
            "change_count": len(changes),
            "guessed_net_count": len(guessed_nets),
            "guessed_terminal_nets": sorted(guessed_nets),
        },
    }
    report = {
        "schema": FIXER_SCHEMA,
        "passed": True,
        "change_count": len(changes),
        "guessed_net_count": len(guessed_nets),
        "guessed_terminal_nets": sorted(guessed_nets),
        "changes": changes,
    }
    return FixedInput(fixed=fixed, report=report)
