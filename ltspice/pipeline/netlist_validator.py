"""Compare independently parsed LTspice connectivity with canonical nets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable

from .component_placer import PlacedComponent
from .directive_validator import DirectiveValidationError, validate_analysis_references, validate_analysis_directives
from .geometry import Point
from .ltspice_asc_parser import AscParseError, extract_connectivity, parse_asc, resolve_document_pins
from .ltspice_asc_writer import MODEL_LIBRARY_NAME
from .symbol_semantics import expected_symbol_attributes
from .ltspice_wire_maker import WirePlan


NETLIST_VALIDATOR_SCHEMA = "progen-ltspice-native-netlist-validator/v0.1"


@dataclass(frozen=True)
class ModelDefinition:
    name: str
    kind: str
    pins: tuple[str, ...]
    digest: str


def _definition_digest(lines: list[str]) -> str:
    normalized = "\n".join(line.rstrip() for line in lines).strip() + "\n"
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()


def _parse_model_definitions(text: str, *, source: str) -> dict[str, ModelDefinition]:
    """Parse the constrained project-local model library into exact definitions."""

    lines = text.splitlines()
    definitions: dict[str, ModelDefinition] = {}
    index = 0
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        index += 1
        if not stripped or stripped.startswith("*"):
            continue
        lower = stripped.lower()
        if lower.startswith(".model"):
            match = re.fullmatch(r"\.model\s+([^\s]+)\s+([^\s(]+)\s*\(.*\)\s*", stripped, flags=re.IGNORECASE)
            if not match:
                raise ValueError(f"{source}: malformed .model card {raw!r}.")
            name = match.group(1)
            definition = ModelDefinition(name=name, kind="model", pins=(), digest=_definition_digest([raw]))
        elif lower.startswith(".subckt"):
            parts = stripped.split()
            if len(parts) < 3:
                raise ValueError(f"{source}: .subckt requires a name and at least one external pin.")
            name = parts[1]
            pin_tokens: list[str] = []
            for token in parts[2:]:
                if token.lower().startswith("params:"):
                    break
                pin_tokens.append(token)
            body = [raw]
            ended = False
            while index < len(lines):
                child = lines[index]
                body.append(child)
                index += 1
                child_parts = child.strip().split()
                if child_parts and child_parts[0].lower() == ".ends":
                    if len(child_parts) > 1 and child_parts[1].lower() != name.lower():
                        raise ValueError(f"{source}: .ends {child_parts[1]!r} does not close .subckt {name!r}.")
                    ended = True
                    break
            if not ended:
                raise ValueError(f"{source}: .subckt {name!r} has no .ends card.")
            definition = ModelDefinition(name=name, kind="subckt", pins=tuple(pin_tokens), digest=_definition_digest(body))
        else:
            raise ValueError(f"{source}: unsupported project-local model-library card {raw!r}.")
        key = definition.name.upper()
        if key in definitions:
            raise ValueError(f"{source}: duplicate model/subcircuit definition {definition.name!r}.")
        definitions[key] = definition
    return definitions


def _model_report(definitions: dict[str, ModelDefinition]) -> dict[str, dict[str, Any]]:
    return {
        item.name: {"kind": item.kind, "pins": list(item.pins), "body_sha256": item.digest}
        for item in sorted(definitions.values(), key=lambda value: value.name.upper())
    }


def _expected_endpoint_sets(plan: WirePlan) -> dict[str, set[str]]:
    expected = {net: set(members) for net, members in plan.expected_native_nets.items()}
    for anchor in plan.virtual_anchors:
        expected.setdefault(anchor.logical_net, set()).add(anchor.endpoint)
    return expected


def _directive_texts(document: Any) -> list[str]:
    values: list[str] = []
    for item in document.texts:
        text = str(item.get("text") or "")
        if text.startswith("!"):
            values.append(text[1:].strip())
    return values


def _wire_geometry_errors(document: Any) -> list[str]:
    errors: list[str] = []
    wires = document.wires
    from .geometry import segment_intersection

    for index, first in enumerate(wires):
        if not (first.is_horizontal or first.is_vertical):
            errors.append(f"WIRE {index + 1} is non-orthogonal.")
        for other_index, second in enumerate(wires[index + 1 :], index + 2):
            crossing = segment_intersection(first, second)
            if crossing is None:
                continue
            first_end = crossing in {first.start, first.end}
            second_end = crossing in {second.start, second.end}
            if not first_end and not second_end:
                errors.append(
                    f"Ambiguous wire crossing between WIRE {index + 1} and WIRE {other_index} at ({crossing.x},{crossing.y})."
                )
    return errors


def _sheet_bounds_errors(document: Any, resolved: dict[str, Any]) -> list[str]:
    if document.sheet is None:
        return ["ASC has no SHEET bounds."]
    _number, width, height = document.sheet
    points: list[tuple[str, Any]] = []
    points.extend((f"SYMBOL {item.ref or item.name}", item.origin) for item in document.symbols)
    points.extend((f"resolved pin {endpoint}", pin.point) for endpoint, pin in resolved.items())
    for index, wire in enumerate(document.wires, 1):
        points.extend(((f"WIRE {index} start", wire.start), (f"WIRE {index} end", wire.end)))
    points.extend((f"FLAG {item.name}", item.point) for item in document.flags)
    points.extend(("TEXT", Point(int(item["point"]["x"]), int(item["point"]["y"]))) for item in document.texts)
    errors: list[str] = []
    for label, point in points:
        if point.x < 0 or point.y < 0 or point.x > width or point.y > height:
            errors.append(f"{label} at ({point.x},{point.y}) lies outside SHEET bounds 0..{width},0..{height}.")
    return errors


def _validate_directives(
    document: Any,
    *,
    needs_models: bool,
    requested_directives: Iterable[str],
    component_refs: Iterable[str],
    sweepable_refs: Iterable[str],
    net_names: Iterable[str],
    errors: list[str],
) -> list[str]:
    directives = _directive_texts(document)
    try:
        normalized, _repairs = validate_analysis_directives(requested_directives)
        validate_analysis_references(
            requested_directives,
            component_refs=component_refs,
            sweepable_refs=sweepable_refs,
            net_names=net_names,
        )
    except DirectiveValidationError as exc:
        errors.append(f"Requested analysis directive is unsafe or unsupported: {exc}")
        return directives
    expected = ([f".include {MODEL_LIBRARY_NAME}"] if needs_models else []) + normalized
    if directives != expected:
        errors.append(f"Native directives mismatch: expected {expected!r}, parsed {directives!r}.")
    return directives


def _validate_model_library(
    *,
    model_path: Path,
    physical: list[PlacedComponent],
    errors: list[str],
    warnings: list[str],
) -> dict[str, dict[str, Any]]:
    expected: dict[str, ModelDefinition] = {}
    component_by_model: dict[str, list[PlacedComponent]] = {}
    for item in physical:
        component = item.component
        profile = component.profile
        if not component.model_text:
            continue
        try:
            definitions = _parse_model_definitions(component.model_text, source=f"selected model {component.value}")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        key = component.value.upper()
        expected_main = definitions.get(key)
        if expected_main is None:
            errors.append(f"Selected model {component.value!r} has no matching model/subcircuit header.")
        for name, definition in definitions.items():
            existing = expected.get(name)
            if existing is not None and existing != definition:
                errors.append(f"Selected catalogue models conflict on nested definition {definition.name!r}.")
            expected[name] = definition
        component_by_model.setdefault(key, []).append(item)
        if component.model_accuracy and "approximation" in component.model_accuracy.lower():
            warnings.append(f"{profile.kind}: {component.model_accuracy}.")
    if not expected:
        if model_path.exists():
            warnings.append("Unused project-local model library is present.")
        return {}
    if not model_path.is_file():
        errors.append(f"Missing required project-local model library {MODEL_LIBRARY_NAME}.")
        return {}
    try:
        actual = _parse_model_definitions(model_path.read_text(encoding="ascii", errors="strict"), source=str(model_path))
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
        return {}
    expected_names = set(expected)
    actual_names = set(actual)
    if actual_names != expected_names:
        errors.append(
            f"Model library definitions mismatch: expected {sorted(expected_names)}, parsed {sorted(actual_names)}."
        )
    for name, definition in expected.items():
        parsed = actual.get(name)
        if parsed is None:
            continue
        if parsed != definition:
            errors.append(f"Model definition {definition.name!r} header or body digest differs from the selected catalogue model.")
    for model_name, items in component_by_model.items():
        definition = actual.get(model_name)
        if definition is None:
            continue
        expected_pin_count = len(items[0].component.profile.pins)
        if definition.kind == "subckt" and len(definition.pins) != expected_pin_count:
            errors.append(
                f"Subcircuit {definition.name!r} exposes {len(definition.pins)} pins, expected {expected_pin_count} for {items[0].component.profile.kind}."
            )
    return _model_report(actual)


def validate_native_netlist(
    *,
    asc_path: Path,
    project_dir: Path,
    placed: Iterable[PlacedComponent],
    wire_plan: WirePlan,
    requested_directives: Iterable[str] = (),
    component_refs: Iterable[str] = (),
    sweepable_refs: Iterable[str] = (),
    net_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate ASC/ASY/model files from disk, never writer in-memory state."""

    errors: list[str] = []
    warnings: list[str] = []
    placed_list = list(placed)
    physical = [item for item in placed_list if not item.component.profile.is_pseudo_component]
    try:
        document = parse_asc(asc_path)
        resolved, parsed_symbols = resolve_document_pins(document, project_dir=project_dir)
        connectivity = extract_connectivity(
            document,
            project_dir=project_dir,
            virtual_anchors=[item.as_dict() for item in wire_plan.virtual_anchors],
        )
    except (AscParseError, OSError, ValueError) as exc:
        return {
            "schema": NETLIST_VALIDATOR_SCHEMA,
            "stage": "ltspice_native_netlist_validator",
            "ok": False,
            "errors": [str(exc)],
            "warnings": [],
        }

    actual_by_ref = {symbol.ref: symbol for symbol in document.symbols}
    expected_by_ref = {item.component.ref: item for item in physical}
    missing_refs = sorted(set(expected_by_ref) - set(actual_by_ref))
    extra_refs = sorted(set(actual_by_ref) - set(expected_by_ref))
    if missing_refs:
        errors.append("Missing native symbols: " + ", ".join(missing_refs))
    if extra_refs:
        errors.append("Unexpected native symbols: " + ", ".join(extra_refs))
    for ref in sorted(set(expected_by_ref) & set(actual_by_ref)):
        expected = expected_by_ref[ref]
        actual = actual_by_ref[ref]
        expected_attributes = expected_symbol_attributes(expected)
        if actual.attributes != expected_attributes:
            errors.append(
                f"{ref} semantic SYMATTR mismatch: expected {expected_attributes!r}, parsed {actual.attributes!r}."
            )
        profile = expected.component.profile
        parsed = parsed_symbols.get(actual.name)
        if parsed is None:
            errors.append(f"{ref} could not resolve emitted symbol {actual.name!r}.")
            continue
        if parsed.attributes.get("PREFIX") != profile.electrical_prefix:
            errors.append(
                f"{ref} symbol prefix mismatch: expected {profile.electrical_prefix!r}, parsed {parsed.attributes.get('PREFIX')!r}."
            )
        parsed_by_order = {pin.spice_order: pin for pin in parsed.pins}
        for profile_pin in profile.pins:
            parsed_pin = parsed_by_order.get(profile_pin.number)
            if parsed_pin is None:
                errors.append(f"{ref} symbol misses SpiceOrder {profile_pin.number}.")
                continue
            if (parsed_pin.point.x, parsed_pin.point.y) != (profile_pin.x, profile_pin.y):
                errors.append(
                    f"{ref}.{profile_pin.number} local pin geometry mismatch: expected ({profile_pin.x},{profile_pin.y}), "
                    f"parsed ({parsed_pin.point.x},{parsed_pin.point.y})."
                )
            if parsed_pin.name != profile_pin.name:
                warnings.append(
                    f"{ref}.{profile_pin.number} display PinName is {parsed_pin.name!r}, expected profile label {profile_pin.name!r}; "
                    "SpiceOrder remains the electrical contract."
                )
        for profile_pin in profile.pins:
            endpoint = f"{ref}.{profile_pin.number}"
            if endpoint not in resolved:
                errors.append(f"{ref} does not expose resolved native endpoint {endpoint}.")

    needs_models = [item.component for item in physical if item.component.model_text]
    _validate_directives(
        document,
        needs_models=bool(needs_models),
        requested_directives=requested_directives,
        component_refs=component_refs,
        sweepable_refs=sweepable_refs,
        net_names=net_names,
        errors=errors,
    )
    model_path = project_dir / MODEL_LIBRARY_NAME
    model_definitions = _validate_model_library(model_path=model_path, physical=physical, errors=errors, warnings=warnings)

    expected_sets = _expected_endpoint_sets(wire_plan)
    endpoint_groups = {key: set(value) for key, value in connectivity.get("endpoint_groups", {}).items()}
    group_to_net: dict[frozenset[str], str] = {}
    for net, expected in expected_sets.items():
        if not expected:
            continue
        missing = sorted(endpoint for endpoint in expected if endpoint not in endpoint_groups)
        if missing:
            errors.append(f"{net} has unresolved native endpoints: {', '.join(missing)}.")
            continue
        roots = {frozenset(endpoint_groups[endpoint]) for endpoint in expected}
        if len(roots) != 1:
            errors.append(f"{net} is split across multiple native connected components.")
            continue
        actual = next(iter(roots))
        if actual != expected:
            errors.append(
                f"{net} membership mismatch: expected {sorted(expected)}, parsed {sorted(actual)}."
            )
        previous = group_to_net.setdefault(actual, net)
        if previous != net:
            errors.append(f"Expected nets {previous!r} and {net!r} are accidentally merged.")
    expected_all = set().union(*expected_sets.values()) if expected_sets else set()
    actual_all = set(endpoint_groups)
    orphaned = sorted(actual_all - expected_all)
    if orphaned:
        errors.append("Native pins are absent from canonical expected nets: " + ", ".join(orphaned))

    for logical_net, native_label in wire_plan.label_map.items():
        planned_flags = [flag for flag in wire_plan.flags if flag.logical_net == logical_net]
        if not planned_flags:
            continue
        actual_members = set(connectivity.get("flag_members", {}).get(native_label, []))
        if actual_members != expected_sets.get(logical_net, set()):
            errors.append(
                f"FLAG label {native_label!r} for {logical_net!r} resolves {sorted(actual_members)}, "
                f"expected {sorted(expected_sets.get(logical_net, set()))}."
            )
    errors.extend(_wire_geometry_errors(document))
    errors.extend(_sheet_bounds_errors(document, resolved))
    return {
        "schema": NETLIST_VALIDATOR_SCHEMA,
        "stage": "ltspice_native_netlist_validator",
        "ok": not errors,
        "asc_path": str(asc_path),
        "component_count": len(document.symbols),
        "expected_native_component_count": len(physical),
        "expected_nets": {name: sorted(items) for name, items in expected_sets.items()},
        "actual_component_groups": connectivity.get("component_groups", []),
        "flag_members": connectivity.get("flag_members", {}),
        "model_definitions": model_definitions,
        "errors": errors,
        "warnings": sorted(set(warnings)),
        "parser": connectivity,
    }
