"""Shared value and properties editor for placed or terminalized projects.

The component placer selects complete donor packets. This stage edits only
family-proven visible value tokens inside those selected packets, and mirrors
the same same-length token change into matching CDB property rows when present.
It intentionally refuses variable-length edits until row-size rewriting is
proven per family.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .cdb import CdbPropertyRow, package_ref


PROVEN_VISIBLE_VALUE_TOKENS: dict[str, str] = {
    "RESISTOR": "10k",
    "CAP": "1uF",
    "CAP-ELEC": "1uF",
    "REALIND": "5mH",
    "POT-HG": "1k",
    "VSOURCE": "1V",
    "CSOURCE": "1A",
}
VISIBLE_VALUE_TOKEN_CANDIDATES: dict[str, tuple[str, ...]] = {
    "RESISTOR": ("10k",),
    "CAP": ("1uF", "1nF"),
    "CAP-ELEC": ("1uF",),
    "REALIND": ("5mH", "1mH"),
    "POT-HG": ("1k",),
    "VSOURCE": ("1V",),
    "CSOURCE": ("1A",),
}

UNPROVEN_VALUE_FAMILIES = {"VSINE", "VPULSE"}

# The post-terminal editor deliberately mutates only numeric values with the
# same byte width.  A component's `COMPONENT ID` field contains the visible
# numeric value (for example `10k` or `1uF`), whereas `COMPONENT VALUE` names
# the device model.  This distinction keeps model/package names immutable.
VISIBLE_NUMERIC_VALUE_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[RkMmunp]\d*)?(?:[AFHV])?$"
)
NUMERIC_PROPERTY_VALUE_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:[A-Za-z]+)?$"
)
IMMUTABLE_PROPERTY_NAMES = frozenset(
    {
        "DCPATH",
        "ITFMOD",
        "MODEL",
        "MODDLL",
        "MODFILE",
        "PACKAGE",
        "PRIMITIVE",
        "PRIMTYPE",
        "SPICELIB",
        "SPICEMODEL",
        "SPICEPINS",
    }
)
VALUE_PROPERTY_VALUE_ALIASES = frozenset(
    {"VALUE", "RESISTANCE", "CAPACITANCE", "INDUCTANCE", "CURRENT"}
)

VALUE_PATTERNS: dict[str, re.Pattern[str]] = {
    # Keep the first production pass intentionally narrow. Same-length byte
    # mutation can still create syntactically bad values (for example "10u"),
    # so family validation must happen before touching donor bytes.
    "RESISTOR": re.compile(r"^[0-9][0-9]?[RkM]?[0-9]?$"),
    "CAP": re.compile(r"^[1-9][unp]F$"),
    "CAP-ELEC": re.compile(r"^[1-9][unp]F$"),
    "REALIND": re.compile(r"^[1-9][mun]H$"),
    "POT-HG": re.compile(r"^(?:[1-9][0-9]?|[1-9][kM])$"),
    "VSOURCE": re.compile(r"^[1-9]V$"),
    "CSOURCE": re.compile(r"^[1-9]A$"),
}


@dataclass(frozen=True)
class ValueMutation:
    family: str
    key: str
    refs: tuple[str, ...]
    old_value: str
    new_value: str
    packet_replacements: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "key": self.key,
            "refs": list(self.refs),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "packet_replacements": self.packet_replacements,
        }


@dataclass(frozen=True)
class ProjectValuePropertyMutation:
    """One same-length mutation made after terminal attachment."""

    family: str
    package: str
    field: str
    old_value: str
    new_value: str
    kind: str
    dsn_replacements: int
    cdb_replacements: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "package": self.package,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "kind": self.kind,
            "dsn_replacements": self.dsn_replacements,
            "cdb_replacements": self.cdb_replacements,
        }


@dataclass(frozen=True)
class ProjectValuePropertiesEditResult:
    """Result of a project-level value/property editing run."""

    source: Path
    output: Path
    report_path: Path
    mutations: tuple[ProjectValuePropertyMutation, ...]
    terminal_record_count: int
    wire_record_count: int

    @property
    def valid(self) -> bool:
        return bool(self.mutations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": "value_and_properties_editor",
            "valid": self.valid,
            "source": str(self.source),
            "output": str(self.output),
            "report_path": str(self.report_path),
            "same_length_only": True,
            "terminal_record_count": self.terminal_record_count,
            "wire_record_count": self.wire_record_count,
            "mutations": [mutation.as_dict() for mutation in self.mutations],
        }


class ValuePropertiesEditorError(ValueError):
    """Raised before writing a project when an edit is not donor-proven."""


def _payload_mapping(payload: Any) -> Mapping[str, Any]:
    return payload if isinstance(payload, Mapping) else {}


def _group_key(group: Any) -> str:
    return str(getattr(group, "key", ""))


def _group_family(group: Any) -> str:
    return str(getattr(group, "family", ""))


def _group_refs(group: Any) -> tuple[str, ...]:
    return tuple(str(ref) for ref in getattr(group, "refs", ()))


def _group_data(group: Any) -> bytes:
    data = getattr(group, "data", b"")
    return data if isinstance(data, bytes) else bytes(data)


def _component_items(payload: Any) -> tuple[tuple[str, Any], ...]:
    raw_components = _payload_mapping(payload).get("components", {})
    if isinstance(raw_components, Mapping):
        return tuple((str(family), spec) for family, spec in raw_components.items())
    if isinstance(raw_components, list):
        items: list[tuple[str, Any]] = []
        for spec in raw_components:
            if isinstance(spec, Mapping):
                family = spec.get("part") or spec.get("family") or spec.get("type") or spec.get("component")
                if family:
                    items.append((str(family), spec))
        return tuple(items)
    return ()


def _same_length_replace_once(data: bytes, old_values: tuple[str, ...], new: str) -> tuple[bytes, str, int]:
    new_bytes = new.encode("ascii")
    length_matches = tuple(old for old in old_values if len(old.encode("ascii")) == len(new_bytes))
    if not length_matches:
        raise ValueError(
            f"Value {new!r} does not match any proven token length in {old_values}; "
            "same-length value mutation only is currently proven."
        )
    for old in length_matches:
        old_bytes = old.encode("ascii")
        if old_bytes in data:
            return data.replace(old_bytes, new_bytes, 1), old, 1
    raise ValueError(f"Packet does not contain any expected value token from {length_matches!r}.")


def _validate_requested_value(family: str, value: str) -> None:
    pattern = VALUE_PATTERNS.get(family)
    if pattern is None:
        return
    if not pattern.fullmatch(value):
        raise ValueError(
            f"{family} value {value!r} is not in the proven compact value syntax for "
            "same-length byte mutation."
        )


def _requested_values_by_key(
    payload: Any,
    selected_groups: Iterable[Any],
    normalize_family: Callable[[str], str],
) -> dict[str, str]:
    groups = tuple(selected_groups)
    by_family: dict[str, deque[Any]] = defaultdict(deque)
    by_ref: dict[str, Any] = {}
    for group in groups:
        by_family[_group_family(group)].append(group)
        if _group_key(group):
            by_ref[_group_key(group)] = group
        for ref in _group_refs(group):
            by_ref.setdefault(ref, group)

    values: dict[str, str] = {}

    for raw_family, spec in _component_items(payload):
        if not isinstance(spec, Mapping):
            continue
        family = normalize_family(raw_family)
        family_groups = list(by_family.get(family, ()))
        if spec.get("values") is not None:
            raw_values = list(spec["values"]) if isinstance(spec["values"], list) else [spec["values"]]
            for group, value in zip(family_groups, raw_values, strict=False):
                values[_group_key(group)] = str(value)
        elif spec.get("value") is not None and family_groups:
            values[_group_key(family_groups[0])] = str(spec["value"])

    raw_values = _payload_mapping(payload).get("values", {})
    if isinstance(raw_values, Mapping):
        for target, value in raw_values.items():
            target_text = str(target)
            group = by_ref.get(target_text)
            values[_group_key(group) if group is not None else target_text] = str(value)

    return values


def apply_value_mutations_to_groups(
    payload: Any,
    selected_groups: Iterable[Any],
    normalize_family: Callable[[str], str],
) -> tuple[tuple[Any, ...], list[ValueMutation], dict[str, Any]]:
    groups = tuple(selected_groups)
    requested = _requested_values_by_key(payload, groups, normalize_family)
    mutations: list[ValueMutation] = []
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    patched_groups: list[Any] = []

    for group in groups:
        key = _group_key(group)
        family = _group_family(group)
        new_value = requested.get(key)
        if new_value is None:
            patched_groups.append(group)
            continue

        if family in UNPROVEN_VALUE_FAMILIES:
            errors.append(
                {
                    "code": "E_VALUE_FAMILY_UNPROVEN",
                    "message": f"{family} value/property mutation is not byte-proven yet.",
                    "severity": "error",
                }
            )
            patched_groups.append(group)
            continue

        old_values = VISIBLE_VALUE_TOKEN_CANDIDATES.get(family)
        if old_values is None:
            errors.append(
                {
                    "code": "E_VALUE_FAMILY_UNSUPPORTED",
                    "message": f"{family} does not have a proven visible value token.",
                    "severity": "error",
                }
            )
            patched_groups.append(group)
            continue

        try:
            _validate_requested_value(family, new_value)
            data, old_value, count = _same_length_replace_once(_group_data(group), old_values, new_value)
        except ValueError as exc:
            errors.append({"code": "E_VALUE_PATCH_REJECTED", "message": str(exc), "severity": "error"})
            patched_groups.append(group)
            continue

        mutations.append(
            ValueMutation(
                family=family,
                key=key,
                refs=_group_refs(group),
                old_value=old_value,
                new_value=new_value,
                packet_replacements=count,
            )
        )
        patched_groups.append(replace(group, data=data))

    return tuple(patched_groups), mutations, {
        "stage": "value_changer",
        "binary_mutation": {
            "applied": bool(mutations),
            "mode": "same_length_selected_packet_tokens",
            "families": sorted({mutation.family for mutation in mutations}),
        },
        "mutations": [mutation.as_dict() for mutation in mutations],
        "errors": errors,
        "warnings": warnings,
        "supported_families": sorted(PROVEN_VISIBLE_VALUE_TOKENS),
        "unproven_families": sorted(UNPROVEN_VALUE_FAMILIES),
    }


def patch_cdb_property_rows(parsed_cdb: Any, mutations: Iterable[ValueMutation]) -> tuple[bytes, dict[str, Any]]:
    mutation_by_ref: dict[str, ValueMutation] = {}
    for mutation in mutations:
        for ref in (mutation.key, *mutation.refs):
            if ref:
                mutation_by_ref[package_ref(ref)] = mutation

    property_rows: list[CdbPropertyRow] = []
    cdb_mutations: list[dict[str, Any]] = []
    for row in parsed_cdb.property_rows:
        row_package = package_ref(row.ref)
        mutation = mutation_by_ref.get(row_package)
        if mutation is None:
            property_rows.append(row)
            continue
        old = mutation.old_value.encode("ascii")
        new = mutation.new_value.encode("ascii")
        if len(old) != len(new):
            raise ValueError("CDB value patching requires same-length values.")
        replacement_count = row.data.count(old)
        if replacement_count:
            property_rows.append(replace(row, data=row.data.replace(old, new)))
            cdb_mutations.append(
                {
                    "ref": row.ref,
                    "family": mutation.family,
                    "old_value": mutation.old_value,
                    "new_value": mutation.new_value,
                    "replacement_count": replacement_count,
                }
            )
        else:
            property_rows.append(row)

    prefix = bytearray(parsed_cdb.prefix)
    prefix.extend(len(parsed_cdb.pin_rows).to_bytes(4, "little"))
    cdb = (
        bytes(prefix)
        + b"".join(row.data for row in parsed_cdb.pin_rows)
        + parsed_cdb.between_sections
        + b"".join(row.data for row in property_rows)
        + parsed_cdb.suffix
    )
    return cdb, {
        "stage": "value_changer_cdb_patch",
        "applied": bool(cdb_mutations),
        "mode": "same_length_selected_property_rows",
        "mutations": cdb_mutations,
    }


def _canonical_package_ref(value: str) -> str:
    return package_ref(value.strip()).upper()


def _visible_value_span(component_data: bytes, *, package: str) -> tuple[int, int, str]:
    """Locate the length-prefixed visible value immediately after COMPONENT ID."""

    marker = b"COMPONENT ID"
    marker_start = component_data.find(marker)
    if marker_start < 0:
        raise ValuePropertiesEditorError(
            f"{package} packet does not expose the donor COMPONENT ID value field."
        )
    field_marker = component_data.find(b"\xff", marker_start + len(marker))
    if field_marker < 0 or field_marker + 2 > len(component_data):
        raise ValuePropertiesEditorError(
            f"{package} packet has an incomplete COMPONENT ID value field."
        )
    value_length = component_data[field_marker + 1]
    value_start = field_marker + 2
    value_end = value_start + value_length
    if value_length == 0 or value_end > len(component_data):
        raise ValuePropertiesEditorError(
            f"{package} packet has an invalid COMPONENT ID value length."
        )
    try:
        value = component_data[value_start:value_end].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValuePropertiesEditorError(
            f"{package} visible value is not ASCII."
        ) from exc
    return value_start, value_end, value


def _property_assignment_span(
    component_data: bytes,
    *,
    package: str,
    field: str,
) -> tuple[int, int, str]:
    """Locate one donor-visible `{FIELD=value}` assignment in a packet."""

    prefix = b"{" + field.encode("ascii") + b"="
    start = component_data.find(prefix)
    if start < 0:
        raise ValuePropertiesEditorError(
            f"{package} does not expose a donor-backed {field} property in ROOT.DSN."
        )
    if component_data.find(prefix, start + 1) >= 0:
        raise ValuePropertiesEditorError(
            f"{package} has multiple {field} property assignments; the editor refuses ambiguity."
        )
    end = component_data.find(b"}", start + len(prefix))
    if end < 0:
        raise ValuePropertiesEditorError(
            f"{package} has an unterminated {field} property assignment."
        )
    try:
        value = component_data[start + len(prefix) : end].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValuePropertiesEditorError(
            f"{package} {field} property is not ASCII."
        ) from exc
    return start, end + 1, value


def _unique_subsequence_start(data: bytes, needle: bytes, *, context: str) -> int:
    start = data.find(needle)
    if start < 0:
        raise ValuePropertiesEditorError(f"{context} is absent from the project.")
    if data.find(needle, start + 1) >= 0:
        raise ValuePropertiesEditorError(f"{context} occurs more than once; edit target is ambiguous.")
    return start


def _replace_same_length(
    data: bytearray,
    *,
    start: int,
    old: bytes,
    new: bytes,
    context: str,
) -> None:
    if len(old) != len(new):
        raise ValuePropertiesEditorError(
            f"{context} requires a same-length replacement ({len(old)} != {len(new)})."
        )
    end = start + len(old)
    if data[start:end] != old:
        raise ValuePropertiesEditorError(f"{context} changed while preparing the atomic edit.")
    data[start:end] = new


def _catalogue_immutable_property_names() -> frozenset[str]:
    """Load the policy from the updateable catalogue with a safe fallback."""

    from .component_catalog import load_component_catalog

    try:
        raw_policy = load_component_catalog().proteus_value_editor_policy()
        raw_names = raw_policy.get("immutable_property_names", ())
        names = frozenset(str(name).upper() for name in raw_names)
    except Exception:
        names = frozenset()
    return names or IMMUTABLE_PROPERTY_NAMES


def _project_edit_requests(
    payload: Any,
    *,
    by_package: Mapping[str, Any],
    packages_by_family: Mapping[str, tuple[str, ...]],
) -> dict[tuple[str, str], tuple[str, str]]:
    """Normalize direct and placement-style value/property requests.

    The post-terminal form is intentionally reference based:

    ``{"values": {"R1": "47k"}, "properties": {"L1": {"ESR": "0.3"}}}``

    For pipeline continuity it also accepts the established placement payload
    form, such as ``{"components": {"RESISTOR": {"values": ["47k"]}}}``.
    """

    errors: list[str] = []
    requests: dict[tuple[str, str], tuple[str, str]] = {}

    def add(package_target: str, field: str, value: Any, source: str) -> None:
        package = _canonical_package_ref(package_target)
        if package not in by_package:
            errors.append(f"Unknown selected package {package_target!r} for {source}.")
            return
        canonical_field = field.strip().upper()
        family = str(getattr(by_package[package], "family", ""))
        if canonical_field in VALUE_PROPERTY_VALUE_ALIASES:
            canonical_field = "VALUE"
        elif canonical_field == "VOLTAGE" and family in {"VSOURCE", "VSINE", "VPULSE"}:
            canonical_field = "VALUE"
        if not canonical_field or not re.fullmatch(r"[A-Z][A-Z0-9_]*", canonical_field):
            errors.append(f"Invalid property field {field!r} for {package}.")
            return
        key = (package, canonical_field)
        new_value = str(value)
        previous = requests.get(key)
        if previous is not None and previous[0] != new_value:
            errors.append(
                f"Conflicting requested values for {package}.{canonical_field}: "
                f"{previous[0]!r} vs {new_value!r}."
            )
            return
        requests[key] = (new_value, source)

    raw_values = _payload_mapping(payload).get("values", {})
    if raw_values is not None and not isinstance(raw_values, Mapping):
        errors.append("values must be a mapping of package reference to value.")
    elif isinstance(raw_values, Mapping):
        for target, value in raw_values.items():
            add(str(target), "VALUE", value, "values")

    raw_properties = _payload_mapping(payload).get("properties", {})
    if raw_properties is not None and not isinstance(raw_properties, Mapping):
        errors.append("properties must be a mapping of package reference to field mapping.")
    elif isinstance(raw_properties, Mapping):
        for target, fields in raw_properties.items():
            if not isinstance(fields, Mapping):
                errors.append(f"properties[{target!r}] must be a field mapping.")
                continue
            for field, value in fields.items():
                add(str(target), str(field), value, f"properties.{target}")

    try:
        from .component_placer import normalize_component
    except ImportError as exc:  # pragma: no cover - only guards misuse during import cycles.
        raise ValuePropertiesEditorError("Component aliases are unavailable during value edit.") from exc

    for raw_family, spec in _component_items(payload):
        if not isinstance(spec, Mapping):
            continue
        try:
            family = normalize_component(raw_family)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        package_sequence = packages_by_family.get(family, ())
        if spec.get("value") is not None:
            if not package_sequence:
                errors.append(f"No selected {family} package exists for components.value.")
            else:
                add(package_sequence[0], "VALUE", spec["value"], "components.value")
        if spec.get("values") is not None:
            raw_sequence = spec["values"]
            value_sequence = (
                list(raw_sequence)
                if isinstance(raw_sequence, list)
                else [raw_sequence]
            )
            if len(value_sequence) > len(package_sequence):
                errors.append(
                    f"components.{raw_family}.values has {len(value_sequence)} values but only "
                    f"{len(package_sequence)} selected package(s)."
                )
            for package, value in zip(package_sequence, value_sequence, strict=False):
                add(package, "VALUE", value, "components.values")

    if errors:
        raise ValuePropertiesEditorError(" ".join(errors))
    if not requests:
        raise ValuePropertiesEditorError("No value or property edits were requested.")
    return requests


def edit_project_values_and_properties(
    project: str | Path,
    output: str | Path,
    payload: Any,
) -> ProjectValuePropertiesEditResult:
    """Edit numeric values/properties after terminal placement without rebasing.

    Every accepted mutation is same byte length in the selected component
    packet and matching CDB property row.  Consequently this stage preserves
    terminal/WIRE records and their final ROOT.DSN address-derived links.
    """

    from .component_placer import inspect_component_packets, parse_component_placer_cdb
    from .pdsprj import read_internal_file, write_project_from_parts
    from .resistor_v9 import _extract_object_chunk

    source = Path(project)
    destination = Path(output)
    if source.resolve() == destination.resolve():
        raise ValuePropertiesEditorError("The editor requires a distinct output project path.")

    dsn = read_internal_file(source, "ROOT.DSN")
    cdb = read_internal_file(source, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    chunk_start = _unique_subsequence_start(dsn, chunk, context="ROOT.DSN object stream")
    packets_by_family_raw = inspect_component_packets(source)
    by_package: dict[str, Any] = {}
    packages_by_family: dict[str, tuple[str, ...]] = {}
    for family, packets in packets_by_family_raw.items():
        ordered = tuple(sorted(packets, key=lambda packet: packet.raw_start))
        packages: list[str] = []
        for packet in ordered:
            package = _canonical_package_ref(packet.package)
            if package in by_package:
                raise ValuePropertiesEditorError(
                    f"ROOT.DSN exposes duplicate package {package}; project edit is ambiguous."
                )
            by_package[package] = packet
            packages.append(package)
        packages_by_family[family] = tuple(packages)

    requests = _project_edit_requests(
        payload,
        by_package=by_package,
        packages_by_family=packages_by_family,
    )
    parsed_cdb = parse_component_placer_cdb(cdb)
    cdb_rows: dict[str, Any] = {}
    for row in parsed_cdb.property_rows:
        package = _canonical_package_ref(row.ref)
        if package in cdb_rows:
            raise ValuePropertiesEditorError(
                f"ROOT.CDB exposes duplicate property rows for {package}."
            )
        cdb_rows[package] = row

    immutable_property_names = _catalogue_immutable_property_names()

    edited_dsn = bytearray(dsn)
    edited_cdb = bytearray(cdb)
    mutations: list[ProjectValuePropertyMutation] = []
    errors: list[str] = []
    for (package, field), (new_value, _source_name) in requests.items():
        packet = by_package[package]
        family = str(packet.family)
        packet_data = chunk[packet.raw_start : packet.raw_end]
        row = cdb_rows.get(package)
        if row is None:
            errors.append(
                f"{package} has no matching ROOT.CDB property row; post-terminal edit is blocked."
            )
            continue
        try:
            row_start = _unique_subsequence_start(
                cdb,
                row.data,
                context=f"ROOT.CDB property row for {package}",
            )
            if field == "VALUE":
                local_start, local_end, old_value = _visible_value_span(
                    packet_data,
                    package=package,
                )
                if not VISIBLE_NUMERIC_VALUE_RE.fullmatch(old_value):
                    raise ValuePropertiesEditorError(
                        f"{package} ({family}) visible value {old_value!r} is a model/name, not a mutable numeric value."
                    )
                if not VISIBLE_NUMERIC_VALUE_RE.fullmatch(new_value):
                    raise ValuePropertiesEditorError(
                        f"{package} visible value {new_value!r} is not an accepted compact numeric Proteus value."
                    )
                old_bytes = old_value.encode("ascii")
                new_bytes = new_value.encode("ascii")
                cdb_local_start = _unique_subsequence_start(
                    row.data,
                    old_bytes,
                    context=f"ROOT.CDB visible value for {package}",
                )
                kind = "visible_value"
            else:
                if field in immutable_property_names:
                    raise ValuePropertiesEditorError(
                        f"{package}.{field} is a model/package/runtime-loader property and is immutable."
                    )
                local_start, local_end, old_value = _property_assignment_span(
                    packet_data,
                    package=package,
                    field=field,
                )
                if not NUMERIC_PROPERTY_VALUE_RE.fullmatch(old_value):
                    raise ValuePropertiesEditorError(
                        f"{package}.{field} value {old_value!r} is not a donor-proven numeric property."
                    )
                if not NUMERIC_PROPERTY_VALUE_RE.fullmatch(new_value):
                    raise ValuePropertiesEditorError(
                        f"{package}.{field} value {new_value!r} is not an accepted numeric property."
                    )
                old_bytes = f"{{{field}={old_value}}}".encode("ascii")
                new_bytes = f"{{{field}={new_value}}}".encode("ascii")
                cdb_local_start = _unique_subsequence_start(
                    row.data,
                    old_bytes,
                    context=f"ROOT.CDB property {package}.{field}",
                )
                kind = "property"
            _replace_same_length(
                edited_dsn,
                start=chunk_start + packet.raw_start + local_start,
                old=old_bytes,
                new=new_bytes,
                context=f"ROOT.DSN {package}.{field}",
            )
            _replace_same_length(
                edited_cdb,
                start=row_start + cdb_local_start,
                old=old_bytes,
                new=new_bytes,
                context=f"ROOT.CDB {package}.{field}",
            )
            mutations.append(
                ProjectValuePropertyMutation(
                    family=family,
                    package=package,
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                    kind=kind,
                    dsn_replacements=1,
                    cdb_replacements=1,
                )
            )
        except ValuePropertiesEditorError as exc:
            errors.append(str(exc))

    if errors:
        raise ValuePropertiesEditorError(" ".join(errors))
    if len(edited_dsn) != len(dsn) or len(edited_cdb) != len(cdb):
        raise ValuePropertiesEditorError("Value/property editor changed ROOT.DSN or ROOT.CDB length.")

    terminal_records_before = chunk.count(b"$TERBIDIR")
    wire_records_before = chunk.count(b"\x7fWIRE")
    edited_chunk = bytes(edited_dsn[chunk_start : chunk_start + len(chunk)])
    if (
        edited_chunk.count(b"$TERBIDIR") != terminal_records_before
        or edited_chunk.count(b"\x7fWIRE") != wire_records_before
    ):
        raise ValuePropertiesEditorError("Value/property edit altered terminal or WIRE record counts.")

    write_project_from_parts(
        source,
        destination,
        {"ROOT.DSN": bytes(edited_dsn), "ROOT.CDB": bytes(edited_cdb)},
    )
    written_dsn = read_internal_file(destination, "ROOT.DSN")
    written_cdb = read_internal_file(destination, "ROOT.CDB")
    if len(written_dsn) != len(dsn) or len(written_cdb) != len(cdb):
        raise ValuePropertiesEditorError("Written project changed ROOT.DSN or ROOT.CDB length.")
    written_chunk = _extract_object_chunk(written_dsn)
    if (
        written_chunk.count(b"$TERBIDIR") != terminal_records_before
        or written_chunk.count(b"\x7fWIRE") != wire_records_before
    ):
        raise ValuePropertiesEditorError("Written project altered terminal or WIRE record counts.")

    report_path = destination.with_name(destination.name + ".value_properties_report.json")
    result = ProjectValuePropertiesEditResult(
        source=source,
        output=destination,
        report_path=report_path,
        mutations=tuple(mutations),
        terminal_record_count=terminal_records_before,
        wire_record_count=wire_records_before,
    )
    report_path.write_text(json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8")
    return result


# More explicit alias for pipeline callers that want to state the stage in
# their own code without re-implementing binary mutation logic.
apply_value_and_properties_to_project = edit_project_values_and_properties
