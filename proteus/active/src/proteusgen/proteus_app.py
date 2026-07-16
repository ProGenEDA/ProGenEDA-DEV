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
from .component_terminal_placer import (
    ACCEPTED_TERMINAL_FAMILY_ORDER,
    TOTALMIX_BLOCKED_FAMILIES,
    attach_component_bidir_terminals_to_project,
)
from .component_value_changer import (
    ProjectValuePropertiesEditResult,
    ValuePropertiesEditorError,
    edit_project_values_and_properties,
)


class ProteusApplicationError(RuntimeError):
    """Raised when the executable cannot safely complete the requested flow."""


# These families are the active native two-pin route.  FUSE and SWITCH remain
# deliberately blocked from mixed terminal emission; adding a new family must
# happen through the shared terminal placer and its donor-backed catalogue
# evidence, never through this application wrapper.
EXECUTABLE_TERMINAL_FAMILIES = frozenset(ACCEPTED_TERMINAL_FAMILY_ORDER) - frozenset(
    TOTALMIX_BLOCKED_FAMILIES
)
POST_TERMINAL_EDIT_KEYS = (
    "post_terminal_edits",
    "terminalized_edits",
    "value_properties",
)
WIRING_REQUEST_KEYS = ("connections", "wires", "nets", "netlist")


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
        prefix=f".{destination.stem}_progen_",
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

        terminal_report: Mapping[str, Any] | None = None
        current = bare
        if terminalize:
            unsupported = _unsupported_terminal_families(placement)
            if unsupported and not allow_unterminalized:
                raise ProteusApplicationError(
                    "The shared executable only terminalizes the currently proven native families. "
                    "This request also contains unsupported/blocked families: "
                    f"{', '.join(unsupported)}. Use --allow-unterminalized only for a deliberate mixed control."
                )
            terminalized = work / "terminalized.pdsprj"
            terminal_families = tuple(
                family
                for family in ACCEPTED_TERMINAL_FAMILY_ORDER
                if family in EXECUTABLE_TERMINAL_FAMILIES
                and any(group.family == family for group in placement.selected_groups)
            )
            if not terminal_families:
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
                    terminal_report = attach_component_bidir_terminals_to_project(
                        bare,
                        terminalized,
                        placement.selected_groups,
                        terminal_families=terminal_families,
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
