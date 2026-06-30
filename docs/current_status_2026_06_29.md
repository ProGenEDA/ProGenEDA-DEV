# Current Status - 2026-06-30

## Active Architecture

Progen's active Proteus route is removal-only donor mutation. Complete native
component packets are selected from trusted mega donors. Component creation by
freehand byte synthesis is not part of the component placer.

```text
validated request
  -> donor selection
  -> packet placement
  -> packet/output validation
  -> packet coordinate beautification
  -> routing decision
  -> terminal placement or wire-planner/beautifier loop
  -> wire emission where selected
  -> value mutation
  -> final validation
```

## Accepted

- Locked resistor, passive, RCL, source-driven, bidirectional, and
  combinational routes remain available.
- Mega-donor component placement supports the inventory recorded in
  `proteus_ic/registry/mega_component_support_20260618.json`.
- Family-registered coordinate mutation works for accepted non-IC and IC
  placement packs.
- IC footprint shelf allocation prevents treating multi-gate packages as one
  small symbol.
- Exact requested counts are used for `SWITCH` and `POT-HG`.
- D20 display infrastructure is preserved and not counted as a requested diode.
- Generated-output validation checks counts, refs, CDB policy, coordinate
  parser use, overlaps, and immutable infrastructure.

## Experimental

- Same-length value mutation for resistor, capacitor, electrolytic capacitor,
  inductor, potentiometer, DC voltage, and DC current.
- Shared `$TERBIDIR` placement now has:
  - accepted `RESISTOR/v3` attachment with donor-derived short wires;
  - accepted `CAP/v2` attachment using the accepted capacitor-native object
    order, suffix progression, pin geometry, and wire-record lengths;
  - static-valid `REALIND/v2` attachment using the accepted sequential
    six-inductor donor structure;
  - rejected old V2 bounding-box side-anchor logic retained only as negative
    evidence.
- Logical wiring plans and same-net groups.

## Not Yet Promoted

- Electrically attached generated bidirectional terminals.
- Donor-derived short-wire emission for every family/pin.
- Arbitrary Proteus wiring and junction synthesis.
- General power/ground terminal placement on the unified component route.
- Variable-length value/property editing.
- VSINE and VPULSE model-property editing.

## Active Test

The current user test packs are:

- `experiments/VALUE_CHANGER_PROBE_V2_SAFE_VALUES_TEMP_2026_06_26.zip`
- `experiments/TERMINAL_PLACER_BIDIR_PROBE_V2_ALL_FAMILIES_TEMP_2026_06_26.zip`
- `experiments/TERMINAL_PLACER_REALIND_ATTACHMENT_V2_TEMP_2026_06_30.zip`

The terminal V2 pack was rejected by user testing on 2026-06-29: its
bounding-box side anchors were not correctly placed or electrically attached.
It emits no wire records and must not be treated as attachment proof.

Terminal development now proceeds component by component in the existing
unified terminal placer. The first focused `RESISTOR/v3` handler patches
terminal suffixes into resistor pin-link fields and emits donor-derived short
wires. Its 1x/3x/15x pack passed Proteus testing on 2026-06-29 and is locked.
See
`experiments/terminal_placer_resistor_attachment_v3_temp_2026_06_29/README.md`.

The old `CAP/v1` pack is invalidated. It used resistor-style terminal ordering,
placed terminal symbols 508000 units beyond the pins, emitted 254000-length
wires, and did not preserve the accepted capacitor right-wire trimming.

`CAP/v2` is the accepted capacitor handler. It preserves the accepted
manual capacitor route: right-terminal array first; repeated left-terminal,
component, left-wire, and right-wire groups; donor-native suffix progression;
pins 508000 units from the body; terminal symbols another 254000 units outward;
zero-length attachment records at the pins; 49-byte non-final right wires; and
a 50-byte final right wire. The user confirmed its 1x/3x/15x Proteus pack
worked on 2026-06-30:
`experiments/TERMINAL_PLACER_CAPACITOR_ATTACHMENT_V2_TEMP_2026_06_30.zip`.

`REALIND/v1` is rejected. The user reported the generated inductor output was
faulty. It remains negative evidence and must not be restored.

`REALIND/v2` was re-researched from the accepted six-inductor donor. It emits
sequential left-terminal/right-terminal/component/left-wire/right-wire groups,
uses pins 762000 units from the body, places terminal symbols another 254000
units outward, patches the donor-native suffix progression, emits zero-length
pin records, and preserves 49-byte non-final and 50-byte final right wires. Its
1x/3x/15x pack is static-valid and awaiting Proteus testing:
`experiments/TERMINAL_PLACER_REALIND_ATTACHMENT_V2_TEMP_2026_06_30.zip`.

## Verification Baseline

- focused component placer suite: 43 passed;
- compileall: passed;
- value V2: 7/7 static-valid;
- terminal V2: 3/3 marker-valid but rejected as unattached in Proteus;
- resistor-specific V3 attachment: Proteus-accepted and locked.
- capacitor-specific V1 attachment: invalidated by donor audit.
- capacitor-specific V2 attachment: Proteus-accepted and locked.
- inductor-specific V1 attachment: user-rejected and disabled.
- inductor-specific V2 attachment: static-valid, pending user Proteus test.

## Next Engineering Step

Test REALIND/v2 in Proteus. Do not start another family until REALIND open,
render, attachment, and simulation results are recorded. Continue through the
one shared `component_terminal_placer.py` module only.
