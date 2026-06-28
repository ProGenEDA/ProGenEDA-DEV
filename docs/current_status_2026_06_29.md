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
- All-family `$TERBIDIR` record placement with left=180 degrees and right=0.
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

The terminal pack is a side-anchor diagnostic. It emits no wire records and
must not be treated as attachment proof.

## Verification Baseline

- focused component placer suite: 36 passed;
- compileall: passed;
- value V2: 7/7 static-valid;
- terminal V2: 3/3 base-valid and terminal-marker-valid;
- Proteus user acceptance remains pending for V2.

## Next Engineering Step

Use accepted terminalized donors to learn per-family pin anchors and complete
terminal-plus-short-wire fragments. Start with two-pin passives, then sources,
controls/transistors, displays, combinational packages, and native IC packages.
Do not infer all pin anchors from a component bounding box.
