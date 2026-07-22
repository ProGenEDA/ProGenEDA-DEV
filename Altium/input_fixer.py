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

from .naming import normalize_project_stem
from .pipeline_contracts import PipelineError
from .source_catalogue import SourceCatalogue, SourceCatalogueError, SourceTemplate, load_source_catalogue


FIXER_SCHEMA = "progen-altium-input-fixer/v2"
_UNSAFE_TEXT = re.compile(r"[|\r\n\x00]")
_SAFE_REFERENCE = re.compile(r"[^A-Za-z0-9_-]+")
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


def _net_items(value: Any, *, field: str) -> list[tuple[str, list[str]]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, list):
        collected: list[tuple[Any, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise InputFixError(f"{field}[{index}] must be a JSON object.")
            collected.append(
                (
                    item.get("name") or item.get("net"),
                    item.get("members") or item.get("nodes") or item.get("connections") or [],
                )
            )
        items = collected
    else:
        raise InputFixError(f"{field} must be an object or list when present.")

    result: list[tuple[str, list[str]]] = []
    for raw_name, raw_members in items:
        if isinstance(raw_members, Mapping):
            raw_members = raw_members.get("members", raw_members.get("nodes", []))
        if isinstance(raw_members, str):
            raw_members = [raw_members]
        if not isinstance(raw_members, list):
            raise InputFixError(f"{field} net {raw_name!r} members must be a list.")
        name = str(raw_name or "").strip()
        members = [str(member).strip() for member in raw_members if str(member).strip()]
        if not name:
            raise InputFixError(f"{field} contains a net without a name.")
        result.append((name, members))
    return result


def _net_name(
    value: Any,
    *,
    field: str,
    changes: list[dict[str, str]],
    origins: dict[str, str],
) -> str:
    original = str(value or "").strip()
    fixed = _clean_text(original, "", field=field, changes=changes)
    if not fixed:
        raise InputFixError(f"{field} has an empty net name.")
    prior = origins.setdefault(fixed, original)
    if prior != original:
        raise InputFixError(
            f"Distinct net names {prior!r} and {original!r} normalize to the same native name {fixed!r}."
        )
    return fixed


def _resolve_endpoint(
    value: str,
    *,
    field: str,
    drafts_by_reference: Mapping[str, dict[str, Any]],
    reference_aliases: Mapping[str, str],
) -> tuple[dict[str, Any], str, str]:
    if "." not in value:
        raise InputFixError(f"{field} endpoint {value!r} must use REFERENCE.PIN syntax.")
    raw_reference, raw_pin = value.rsplit(".", 1)
    reference = reference_aliases.get(raw_reference, raw_reference)
    draft = drafts_by_reference.get(reference)
    if draft is None:
        raise InputFixError(f"{field} references unknown component {raw_reference!r}.")
    template: SourceTemplate = draft["template"]
    try:
        native_pin = template.resolve_pin(raw_pin)
    except SourceCatalogueError as exc:
        raise InputFixError(str(exc)) from exc
    exposed_pin = draft["native_to_pin"].get(native_pin, native_pin)
    return draft, native_pin, f"{reference}.{exposed_pin}"


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
    drafts: list[dict[str, Any]] = []
    drafts_by_reference: dict[str, dict[str, Any]] = {}
    reference_aliases: dict[str, str] = {}
    references: set[str] = set()
    guessed_nets: list[str] = []
    net_origins: dict[str, str] = {}

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
        raw_reference = item.get("ref") or item.get("reference") or item.get("designator") or item.get("id")
        reference = _reference(
            raw_reference,
            index,
            changes,
        )
        if reference in references:
            raise InputFixError(f"Component reference {reference!r} is duplicated; it cannot be repaired safely.")
        references.add(reference)
        raw_reference_text = str(raw_reference or reference).strip()
        for alias in {raw_reference_text, reference}:
            prior_alias = reference_aliases.setdefault(alias, reference)
            if prior_alias != reference:
                raise InputFixError(f"Component reference alias {alias!r} is ambiguous.")
        identifier = _clean_text(item.get("id"), reference, field=f"components[{index - 1}].id", changes=changes)
        value_text = _clean_text(
            item.get("value") or item.get("label"),
            template.library_reference,
            field=f"components[{index - 1}].value",
            changes=changes,
        )

        pins: dict[str, str] = {}
        native_seen: dict[str, str] = {}
        native_to_pin: dict[str, str] = {}
        raw_pins = item.get("pins", item.get("connections"))
        for supplied_pin, raw_net in _pin_items(raw_pins):
            pin = supplied_pin.strip()
            if not pin:
                raise InputFixError(f"{reference} has a pin entry without both a pin and a net.")
            net = _net_name(
                raw_net,
                field=f"{reference}.{pin}",
                changes=changes,
                origins=net_origins,
            )
            try:
                native_pin = template.resolve_pin(pin)
            except SourceCatalogueError as exc:
                raise InputFixError(str(exc)) from exc
            prior = native_seen.setdefault(native_pin, net)
            if prior != net:
                raise InputFixError(
                    f"{reference} assigns aliases of source pin {native_pin!r} to two nets: {prior!r}, {net!r}."
                )
            prior_logical_pin = native_to_pin.get(native_pin)
            if prior_logical_pin is not None:
                changes.append(
                    {
                        "field": f"{reference}.{pin}",
                        "from": pin,
                        "to": prior_logical_pin,
                        "reason": "duplicate_source_pin_alias_merged",
                    }
                )
                continue
            if pin in pins and pins[pin] != net:
                raise InputFixError(f"{reference}.{pin} is assigned to two nets.")
            pins[pin] = net
            native_to_pin[native_pin] = pin

        draft = {
            "template": template,
            "native_to_net": native_seen,
            "native_to_pin": native_to_pin,
            "component": {
                "id": identifier,
                "ref": reference,
                "kind": kind,
                "value": value_text,
                "role": _clean_text(item.get("role"), "", field=f"{reference}.role", changes=changes),
                "block": _clean_text(item.get("block"), "main", field=f"{reference}.block", changes=changes),
                "pins": pins,
            },
        }
        drafts.append(draft)
        drafts_by_reference[reference] = draft

    declared_endpoint_nets: dict[str, str] = {}

    def apply_declarations(entries: list[tuple[str, list[str]]], field: str) -> dict[str, set[str]]:
        declared: dict[str, set[str]] = {}
        for net_index, (raw_net, members) in enumerate(entries):
            net = _net_name(
                raw_net,
                field=f"{field}[{net_index}].name",
                changes=changes,
                origins=net_origins,
            )
            for member_index, member in enumerate(members):
                draft, native_pin, endpoint = _resolve_endpoint(
                    member,
                    field=f"{field}[{net_index}].members[{member_index}]",
                    drafts_by_reference=drafts_by_reference,
                    reference_aliases=reference_aliases,
                )
                existing = draft["native_to_net"].get(native_pin)
                if existing is not None and existing != net:
                    if field == "expected_netlist":
                        raise InputFixError(
                            f"expected_netlist disagrees with component pin assignment "
                            f"{endpoint} -> {existing!r}; it requested {net!r}."
                        )
                    raise InputFixError(
                        f"{field} net {net!r} conflicts with component pin assignment "
                        f"{endpoint} -> {existing!r}."
                    )
                prior_declared = declared_endpoint_nets.setdefault(endpoint, net)
                if prior_declared != net:
                    raise InputFixError(
                        f"{field} assigns endpoint {endpoint!r} to both {prior_declared!r} and {net!r}."
                    )
                if existing is None:
                    exposed_pin = endpoint.rsplit(".", 1)[1]
                    draft["native_to_net"][native_pin] = net
                    draft["native_to_pin"][native_pin] = exposed_pin
                    draft["component"]["pins"][exposed_pin] = net
                    changes.append(
                        {
                            "field": endpoint,
                            "from": "",
                            "to": net,
                            "reason": f"filled_from_{field}",
                        }
                    )
                declared.setdefault(net, set()).add(endpoint)
        return declared

    declared_nets = apply_declarations(_net_items(raw.get("nets"), field="nets"), "nets")
    declared_expected = apply_declarations(
        _net_items(raw.get("expected_netlist"), field="expected_netlist"),
        "expected_netlist",
    )

    for draft in drafts:
        template: SourceTemplate = draft["template"]
        reference = draft["component"]["ref"]
        for native_pin in sorted(template.pins):
            if native_pin in draft["native_to_net"]:
                continue
            guessed = f"GUESS_TERMINAL_{reference}_{native_pin}"
            draft["component"]["pins"][native_pin] = guessed
            draft["native_to_pin"][native_pin] = native_pin
            draft["native_to_net"][native_pin] = guessed
            net_origins[guessed] = guessed
            guessed_nets.append(guessed)
            changes.append(
                {
                    "field": f"{reference}.{native_pin}",
                    "from": "",
                    "to": guessed,
                    "reason": "missing_source_pin_terminalized",
                }
            )

    components = []
    for draft in drafts:
        component = draft["component"]
        component["pins"] = dict(sorted(component["pins"].items()))
        components.append(component)

    routing = raw.get("routing") if isinstance(raw.get("routing"), Mapping) else {}
    requested_mode = routing_mode or routing.get("mode") or raw.get("routing_mode") or "combination"
    mode = str(requested_mode).strip().casefold()
    if mode not in _ROUTING_MODES:
        changes.append({"field": "routing.mode", "from": str(requested_mode), "to": "combination", "reason": "default_supported_mode"})
        mode = "combination"

    project_raw = raw.get("project") if isinstance(raw.get("project"), Mapping) else {}
    raw_name = _clean_text(
        project_raw.get("name") or raw.get("name") or raw.get("circuit_id"),
        "altium_project",
        field="project.name",
        changes=changes,
    )
    name = normalize_project_stem(raw_name)
    if name != raw_name:
        changes.append(
            {"field": "project.name", "from": raw_name, "to": name, "reason": "safe_native_project_stem"}
        )
    title = _clean_text(project_raw.get("title") or raw.get("circuit_name"), name, field="project.title", changes=changes)
    nets: dict[str, list[str]] = {}
    for component in components:
        for pin, net in component["pins"].items():
            nets.setdefault(net, []).append(f"{component['ref']}.{pin}")
    canonical_nets = {net: sorted(members) for net, members in sorted(nets.items())}

    for field, declarations in (("nets", declared_nets), ("expected_netlist", declared_expected)):
        for net, members in declarations.items():
            actual = set(canonical_nets.get(net, ()))
            if members != actual:
                phrase = "expected_netlist disagrees" if field == "expected_netlist" else "nets disagree"
                raise InputFixError(
                    f"{phrase} with component pin assignments for {net!r}: "
                    f"{sorted(members)} != {sorted(actual)}."
                )

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
