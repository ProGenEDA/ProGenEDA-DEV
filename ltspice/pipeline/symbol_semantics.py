"""Pure LTspice symbol-property semantics shared by writer and validator.

This module owns no files and retains no writer state.  It converts the
profile-approved structured source fields into the native LTspice attribute
contract so the emitter and independent on-disk validator have one explicit,
testable definition of what a safe component instance means.
"""

from __future__ import annotations

from .component_placer import PlacedComponent
from .value_editor import spice_line_from_parameters


def expected_symbol_attributes(item: PlacedComponent) -> dict[str, str]:
    """Return every semantic ASC ``SYMATTR`` expected for one placed symbol."""

    profile = item.component.profile
    parameters = dict(item.component.parameters)
    value = item.component.value
    value2: str | None = None
    if profile.value_rule == "source_expression":
        waveform_fields = ("pulse", "sine", "exp", "sffm", "pwl")
        waveform = next((parameters[name] for name in waveform_fields if name in parameters), None)
        if waveform is not None:
            value = waveform
        elif "dc" in parameters:
            value = parameters["dc"]
        if "ac" in parameters:
            value2 = f"AC {parameters['ac']}"
        for name in (*waveform_fields, "dc", "ac"):
            parameters.pop(name, None)
    attributes = {"INSTNAME": item.component.ref, "VALUE": value}
    if value2:
        attributes["VALUE2"] = value2
    spice_line = spice_line_from_parameters(profile, parameters)
    if spice_line:
        attributes["SPICELINE"] = spice_line
    return attributes
