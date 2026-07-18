"""One public, Proteus-only application pipeline for the Windows executable.

The module deliberately composes existing shared stages.  It never owns
component placement, terminal grammar, WIRE synthesis, or value mutation
logic; those remain in their canonical modules.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .component_placer import ComponentPlacerBlocked, RawPlacementResult, generate_component_placement_project
from .component_catalog import load_component_catalog
from .component_terminal_placer import (
    ACCEPTED_TERMINAL_FAMILY_ORDER,
    TOTALMIX_BLOCKED_FAMILIES,
    attach_catalogue_pin_bidir_terminals_to_project,
    attach_component_bidir_terminals_to_project,
    attach_mixed_component_and_catalogue_bidir_terminals_to_project,
)
from .component_value_changer import (
    ProjectValuePropertiesEditResult,
    ValuePropertiesEditorError,
    edit_project_values_and_properties,
)


class ProteusApplicationError(RuntimeError):
    """Raised when the executable cannot safely complete the requested flow."""


# The frozen native route covers the user-accepted two-pin families.  These
# four catalogue-backed families have their own accepted pin geometry and
# native terminal/WIRE units in the shared placer.  Keeping the sets separate
# means a native-only request retains its frozen serializer while a mixed PDF
# circuit takes the one shared native-plus-catalogue route.
EXECUTABLE_NATIVE_TERMINAL_FAMILIES = (
    frozenset(ACCEPTED_TERMINAL_FAMILY_ORDER)
    - frozenset(TOTALMIX_BLOCKED_FAMILIES)
)
EXECUTABLE_GATE_TERMINAL_FAMILIES = frozenset(
    {
        "74HC00",
        "74HC02",
        "74HC04",
        "74HC08",
        "74HC32",
        "74HC86",
        "74HC266",
    }
)
EXECUTABLE_GATE_PACKAGE_LIMITS = {
    "74HC00": 8,
    "74HC02": 4,
    "74HC04": 10,
    "74HC08": 10,
    "74HC32": 10,
    "74HC86": 10,
    "74HC266": 10,
}
EXECUTABLE_CATALOGUE_TERMINAL_FAMILIES = frozenset(
    {
        "2N3904",
        "LM317T",
        "NMOSFET",
        "NPN",
        "PNP",
        "OPAMP",
        "POT-HG",
    }
) | EXECUTABLE_GATE_TERMINAL_FAMILIES
EXECUTABLE_TERMINAL_FAMILIES = (
    EXECUTABLE_NATIVE_TERMINAL_FAMILIES
    | EXECUTABLE_CATALOGUE_TERMINAL_FAMILIES
)
POST_TERMINAL_EDIT_KEYS = (
    "post_terminal_edits",
    "terminalized_edits",
    "value_properties",
)

# The generated project may intentionally have a descriptive filename and be
# stored under a dated evidence directory.  Never repeat that whole stem in a
# temporary work directory: Windows' legacy path ceiling otherwise prevents
# the component placer from writing its manifest before terminalization starts.
TEMPORARY_WORK_PREFIX = ".progen_"
WIRING_REQUEST_KEYS = ("connections", "wires", "nets", "netlist")
TERMINAL_LABEL_PROJECTION_KEY = "terminal_label_projection"
_PLACEMENT_INFRASTRUCTURE_KEYS = frozenset({"D20", "DISPLAY_ANODE_SENTINEL"})


@dataclass(frozen=True)
class ProteusApplicationResult:
    """Auditable result of a full executable-owned Proteus run."""

    output: Path
    report_path: Path
    placement: RawPlacementResult
    terminal_report: Mapping[str, Any] | None
    value_properties: ProjectValuePropertiesEditResult | None

    @property
    def valid(self) -> bool:
        return self.placement.valid and (
            self.terminal_report is None or bool(self.terminal_report.get("valid"))
        ) and (self.value_properties is None or self.value_properties.valid)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": "progen_proteus_application",
            "valid": self.valid,
            "output": str(self.output),
            "report_path": str(self.report_path),
            "placement": self.placement.as_dict(),
            "terminal_placer": dict(self.terminal_report) if self.terminal_report else None,
            "value_and_properties_editor": (
                self.value_properties.as_dict() if self.value_properties else None
            ),
        }


def _mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProteusApplicationError(f"{context} must be a JSON object.")
    return value


def _reject_unimplemented_wiring(payload: Mapping[str, Any]) -> None:
    requested = [key for key in WIRING_REQUEST_KEYS if payload.get(key)]
    if requested:
        raise ProteusApplicationError(
            "Physical wiring is not yet available in the Proteus executable "
            f"({', '.join(requested)} requested). The executable will not claim a routed circuit; "
            "generate terminalized components first or wait for the shared Wire Maker stage."
        )


def _post_terminal_edits(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    selected: Mapping[str, Any] | None = None
    selected_key: str | None = None
    for key in POST_TERMINAL_EDIT_KEYS:
        candidate = payload.get(key)
        if candidate is None:
            continue
        candidate_mapping = _mapping(candidate, context=key)
        if selected is not None and candidate_mapping != selected:
            raise ProteusApplicationError(
                f"Conflicting post-terminal edit objects: {selected_key!r} and {key!r}."
            )
        selected = candidate_mapping
        selected_key = key
    return selected


def _unsupported_terminal_families(placement: RawPlacementResult) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(group.family)
                for group in placement.selected_groups
                if str(group.family) not in EXECUTABLE_TERMINAL_FAMILIES
            }
        )
    )


def _reject_unproven_gate_mix(placement: RawPlacementResult) -> None:
    """Keep the executable on screenshot-proven gate stream shapes.

    A single gate family can scale through the shared catalogue writer.  A
    multi-family or gate-plus-non-gate catalogue stream can currently pass
    static checks while Proteus silently drops component packets, so it must
    fail clearly instead of producing a misleading project.
    """

    selected_families = {
        str(group.family)
        for group in placement.selected_groups
        if str(group.key) not in _PLACEMENT_INFRASTRUCTURE_KEYS
    }
    selected_gates = selected_families & EXECUTABLE_GATE_TERMINAL_FAMILIES
    if selected_gates and (
        len(selected_gates) != 1 or selected_families != selected_gates
    ):
        raise ProteusApplicationError(
            "The current executable gate bridge supports one gate family per "
            "project. Screenshot-backed Proteus tests proved the individual "
            "family route, but mixed gate-family and gate-plus-other-family "
            "streams can silently hide component packets. Split this trial "
            "request by gate family until the donor-derived mixed stream "
            "boundary is promoted."
        )
    if selected_gates:
        family = next(iter(selected_gates))
        package_count = sum(
            1
            for group in placement.selected_groups
            if str(group.family) == family
            and str(group.key) not in _PLACEMENT_INFRASTRUCTURE_KEYS
        )
        safe_limit = EXECUTABLE_GATE_PACKAGE_LIMITS[family]
        if package_count > safe_limit:
            raise ProteusApplicationError(
                f"{family} requests {package_count} package(s), above the "
                f"screenshot-proven executable ceiling of {safe_limit}. "
                "The placer may contain more donor packets, but the executable "
                "will not emit a project known to exceed its local Proteus "
                "cold-open evidence."
            )


def _terminal_label_overrides(
    payload: Mapping[str, Any],
    placement: RawPlacementResult,
) -> dict[str, dict[str, str]]:
    """Resolve canonical-node terminal labels onto newly placed component keys.

    The PDF corpus cannot know the current mega-donor instance keys (for
    example, canonical ``U1`` may be placed as ``U107``).  Its projection
    therefore supplies ordered source components within each family.  The
    component placer owns the current keys; this adapter joins the two by that
    family-local order and rejects any count mismatch rather than guessing.
    """

    raw_projection = payload.get(TERMINAL_LABEL_PROJECTION_KEY)
    if raw_projection is None:
        return {}
    projection = _mapping(
        raw_projection,
        context=TERMINAL_LABEL_PROJECTION_KEY,
    )
    if projection.get("schema_version") != "progen-proteus-terminal-label-projection/v1":
        raise ProteusApplicationError(
            "Unsupported terminal_label_projection schema; expected "
            "progen-proteus-terminal-label-projection/v1."
        )
    raw_families = _mapping(
        projection.get("families", {}),
        context="terminal_label_projection.families",
    )
    visible_groups_by_family: dict[str, list[Any]] = {}
    for group in placement.selected_groups:
        family = str(group.family)
        if str(group.key) in _PLACEMENT_INFRASTRUCTURE_KEYS:
            continue
        visible_groups_by_family.setdefault(family, []).append(group)

    overrides: dict[str, dict[str, str]] = {}
    for raw_family, raw_components in raw_families.items():
        family = str(raw_family)
        if not isinstance(raw_components, list):
            raise ProteusApplicationError(
                f"terminal_label_projection.families.{family} must be an array."
            )
        placed_groups = visible_groups_by_family.get(family, [])
        if len(placed_groups) != len(raw_components):
            raise ProteusApplicationError(
                "Terminal-label projection count mismatch for "
                f"{family}: {len(raw_components)} source component(s) but "
                f"{len(placed_groups)} placed component(s)."
            )
        for index, (group, raw_component) in enumerate(
            zip(placed_groups, raw_components, strict=True),
            start=1,
        ):
            component = _mapping(
                raw_component,
                context=(
                    f"terminal_label_projection.families.{family}[{index - 1}]"
                ),
            )
            raw_pins = _mapping(
                component.get("pins", {}),
                context=(
                    f"terminal_label_projection.families.{family}[{index - 1}].pins"
                ),
            )
            labels: dict[str, str] = {}
            for raw_pin, raw_label in raw_pins.items():
                if not isinstance(raw_label, str) or not raw_label:
                    raise ProteusApplicationError(
                        f"Terminal label for {family}[{index}].{raw_pin} must be a non-empty string."
                    )
                labels[str(raw_pin)] = raw_label
            if labels:
                overrides[str(group.key)] = labels
    return overrides


def _require_nonzero_terminal_wires(report: Mapping[str, Any]) -> None:
    checks = report.get("wire_path_contact_checks", ())
    if not isinstance(checks, list) or not checks:
        raise ProteusApplicationError(
            "Shared terminal placement did not provide terminal-to-pin WIRE checks."
        )
    zero_length = [
        f"{check.get('component_key', '?')}:{check.get('role', '?')}"
        for check in checks
        if not bool(check.get("wire_is_nonzero"))
    ]
    if zero_length:
        raise ProteusApplicationError(
            "Terminal placement produced zero-length terminal-to-pin WIRE(s): "
            + ", ".join(zero_length)
            + ". The executable refuses this output; do not force a component pin onto "
            "the terminal grid when the native route requires a short wire."
        )


def _catalogue_mixed_stream_mode(
    catalogue_terminal_families: tuple[str, ...],
) -> str:
    """Resolve a mixed-stream selection from catalogue-owned evidence.

    A family can require a combined stream because its clean solo packet uses
    a different terminal-leading grammar.  Keep that fact in the component
    catalogue so adding later families does not create a new terminal route or
    hard-coded donor dependency in the executable.
    """

    modes: set[str] = set()
    catalog = load_component_catalog()
    for family in catalogue_terminal_families:
        profile = catalog.get_profile(family)
        geometry = profile.proteus.get("pin_geometry", {}) if profile else {}
        if not isinstance(geometry, Mapping):
            continue
        raw_mode = geometry.get("executable_mixed_stream_mode")
        if raw_mode is not None:
            modes.add(str(raw_mode))
    if not modes:
        return "conservative"
    if len(modes) != 1:
        raise ProteusApplicationError(
            "The selected catalogue families require conflicting mixed terminal "
            f"stream modes: {sorted(modes)}."
        )
    return next(iter(modes))


def _write_application_report(
    output: Path,
    *,
    placement: RawPlacementResult,
    terminal_report: Mapping[str, Any] | None,
    value_properties: ProjectValuePropertiesEditResult | None,
) -> Path:
    report_path = output.with_name(output.name + ".progen_report.json")
    report = ProteusApplicationResult(
        output=output,
        report_path=report_path,
        placement=placement,
        terminal_report=terminal_report,
        value_properties=value_properties,
    )
    report_path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_path


def generate_proteus_project(
    payload: Mapping[str, Any],
    output: str | Path,
    *,
    terminalize: bool = True,
    allow_unterminalized: bool = False,
    control_strategy: str | None = None,
    donor_path: str | Path | None = None,
) -> ProteusApplicationResult:
    """Run placement -> shared terminal placer -> optional value/property edit.

    ``post_terminal_edits`` is intentionally separate from the component
    placement payload.  It receives the normal reference-based value-editor
    object and is applied only after terminal link addresses are final.
    """

    source_payload = _mapping(payload, context="generator input")
    _reject_unimplemented_wiring(source_payload)
    edits = _post_terminal_edits(source_payload)
    destination = Path(output)
    if destination.suffix.lower() != ".pdsprj":
        destination = destination.with_suffix(".pdsprj")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if edits and not terminalize:
        raise ProteusApplicationError(
            "post_terminal_edits requires terminalization; remove --no-terminals or omit the edits."
        )

    with tempfile.TemporaryDirectory(
        prefix=TEMPORARY_WORK_PREFIX,
        dir=destination.parent,
    ) as temporary_directory:
        work = Path(temporary_directory)
        bare = work / "placed_beautified.pdsprj"
        try:
            placement = generate_component_placement_project(
                dict(source_payload),
                bare,
                control_strategy=control_strategy,
                donor_path=donor_path,
                full_cdb=True,
            )
        except ComponentPlacerBlocked as exc:
            raise ProteusApplicationError(json.dumps(exc.report.as_dict(), sort_keys=True)) from exc
        except (ValueError, FileNotFoundError) as exc:
            raise ProteusApplicationError(str(exc)) from exc
        if not placement.valid:
            raise ProteusApplicationError(
                "Component placement failed validation: "
                + "; ".join(issue.message for issue in placement.errors)
            )
        _reject_unproven_gate_mix(placement)

        terminal_report: Mapping[str, Any] | None = None
        current = bare
        if terminalize:
            terminal_label_overrides = _terminal_label_overrides(
                source_payload,
                placement,
            )
            unsupported = _unsupported_terminal_families(placement)
            if unsupported and not allow_unterminalized:
                raise ProteusApplicationError(
                    "The shared executable only terminalizes the currently proven native families. "
                    "This request also contains unsupported/blocked families: "
                    f"{', '.join(unsupported)}. Use --allow-unterminalized only for a deliberate mixed control."
                )
            terminalized = work / "terminalized.pdsprj"
            native_terminal_families = tuple(
                family
                for family in ACCEPTED_TERMINAL_FAMILY_ORDER
                if family in EXECUTABLE_NATIVE_TERMINAL_FAMILIES
                and any(group.family == family for group in placement.selected_groups)
            )
            catalogue_terminal_families = tuple(
                sorted(
                    family
                    for family in EXECUTABLE_CATALOGUE_TERMINAL_FAMILIES
                    if any(group.family == family for group in placement.selected_groups)
                )
            )
            if not native_terminal_families and not catalogue_terminal_families:
                if not allow_unterminalized:
                    raise ProteusApplicationError(
                        "No selected component has a proven terminal route. Use --no-terminals for a placement-only project."
                    )
                shutil.copyfile(bare, terminalized)
                terminal_report = {
                    "stage": "terminal_placer",
                    "valid": True,
                    "attachment_policy": "explicit_allow_unterminalized_copy",
                    "eligible_families": [],
                    "skipped_families": list(unsupported),
                }
            else:
                try:
                    if native_terminal_families and catalogue_terminal_families:
                        terminal_report = (
                            attach_mixed_component_and_catalogue_bidir_terminals_to_project(
                                bare,
                                terminalized,
                                placement.selected_groups,
                                native_terminal_families=native_terminal_families,
                                catalogue_terminal_families=catalogue_terminal_families,
                                stream_mode=_catalogue_mixed_stream_mode(
                                    catalogue_terminal_families
                                ),
                                force_grid_contact_short_wires=True,
                                terminal_label_overrides=terminal_label_overrides,
                            )
                        )
                    elif catalogue_terminal_families:
                        # A catalogue-only circuit keeps its established
                        # homogeneous complete route.  The combined writer is
                        # intentionally only for a stream containing both
                        # accepted native and catalogue families.
                        terminal_report = attach_catalogue_pin_bidir_terminals_to_project(
                            bare,
                            terminalized,
                            placement.selected_groups,
                            terminal_families=catalogue_terminal_families,
                            use_donor_terminal_labels=False,
                            allow_progressive_scaling=True,
                            terminal_label_overrides=terminal_label_overrides,
                        )
                    else:
                        terminal_report = attach_component_bidir_terminals_to_project(
                            bare,
                            terminalized,
                            placement.selected_groups,
                            terminal_families=native_terminal_families,
                            terminal_label_overrides=terminal_label_overrides,
                        )
                except (ValueError, FileNotFoundError) as exc:
                    raise ProteusApplicationError(str(exc)) from exc
                if not terminal_report.get("valid"):
                    raise ProteusApplicationError(
                        "Shared terminal placement failed validation: "
                        + json.dumps(dict(terminal_report), sort_keys=True)
                    )
                _require_nonzero_terminal_wires(terminal_report)
            current = terminalized

        value_properties: ProjectValuePropertiesEditResult | None = None
        if edits:
            try:
                value_properties = edit_project_values_and_properties(current, destination, edits)
            except ValuePropertiesEditorError as exc:
                raise ProteusApplicationError(str(exc)) from exc
        else:
            shutil.copyfile(current, destination)

        report_path = _write_application_report(
            destination,
            placement=placement,
            terminal_report=terminal_report,
            value_properties=value_properties,
        )
    return ProteusApplicationResult(
        output=destination,
        report_path=report_path,
        placement=placement,
        terminal_report=terminal_report,
        value_properties=value_properties,
    )
