"""Conservative post-placement component value mutation.

The component placer selects complete donor packets. This stage edits only
family-proven visible value tokens inside those selected packets, and mirrors
the same same-length token change into matching CDB property rows when present.
It intentionally refuses variable-length edits until row-size rewriting is
proven per family.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, replace
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
