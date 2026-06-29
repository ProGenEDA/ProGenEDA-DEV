# Current Status - 2026-06-29

## Active Architecture

Progen's active Proteus route is removal-only donor mutation. Complete native
component packets are selected from trusted mega donors. Component creation by
freehand byte synthesis is not part of the component placer.

```text
validated request
  -> donor selection
  -> packet placement
  -> packet/output validation
  -> value mutation
  -> wiring intent
  -> packet coordinate beautification
  -> terminal/wire stages
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
  - static-valid `CAP/v1` attachment with family-specific tail-link patching
    and short-wire emission;
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

The terminal V2 pack was rejected by user testing on 2026-06-29: its
bounding-box side anchors were not correctly placed or electrically attached.
It emits no wire records and must not be treated as attachment proof.

Terminal development now proceeds component by component in the existing
unified terminal placer. The first focused `RESISTOR/v3` handler patches
terminal suffixes into resistor pin-link fields and emits donor-derived short
wires. Its 1x/3x/15x pack passed Proteus testing on 2026-06-29 and is locked.
See
`experiments/terminal_placer_resistor_attachment_v3_temp_2026_06_29/README.md`.

The next focused family is `CAP/v1`. It uses the same shared terminal module,
but with capacitor-specific body-center pin derivation and dynamic tail-link
offsets so longer refs such as `C14` still patch correctly. Its static pack is
ready for manual Proteus testing:
`experiments/TERMINAL_PLACER_CAPACITOR_ATTACHMENT_V1_TEMP_2026_06_29.zip`.

## Verification Baseline

- focused component placer suite: 41 passed;
- compileall: passed;
- value V2: 7/7 static-valid;
- terminal V2: 3/3 marker-valid but rejected as unattached in Proteus;
- resistor-specific V3 attachment: Proteus-accepted and locked.
- capacitor-specific V1 attachment: static-valid, pending user Proteus test.

## Next Engineering Step

Use accepted terminalized donors to learn per-family pin anchors and complete
terminal-plus-short-wire fragments. Start with two-pin passives, then sources,
controls/transistors, displays, combinational packages, and native IC packages.
Do not infer all pin anchors from a component bounding box.
