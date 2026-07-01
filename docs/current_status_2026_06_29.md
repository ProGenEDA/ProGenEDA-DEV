# Current Status - 2026-07-01

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
  - accepted `REALIND/v2` attachment using the accepted sequential
    six-inductor donor structure;
  - accepted `CAP-ELEC/v3` attachment using the accepted sequential
    eight-electrolytic-capacitor donor structure;
  - accepted `VSOURCE/v4` and `CSOURCE/v4` attachment using the accepted
    bidirectional V3 source roles, body links, and wire geometry;
  - a temporary short-wire-only mixed candidate that keeps the beautified
    component stream and Ctrl+S-normalized T01 terminal order intact, adds
    family-derived wires, and preserves unsupported component packets;
  - rejected old V2 bounding-box side-anchor logic retained only as negative
    evidence.
- Logical wiring plans and same-net groups.

## Not Yet Promoted

- Mixed-family append-overlay ordering pending Proteus acceptance.
- Donor-derived short-wire emission for every family/pin.
- Arbitrary Proteus wiring and junction synthesis.
- General power/ground terminal placement on the unified component route.
- Variable-length value/property editing.
- VSINE and VPULSE model-property editing.

## Active Test

The current user test packs are:

- `experiments/VALUE_CHANGER_PROBE_V2_SAFE_VALUES_TEMP_2026_06_26.zip`
- `experiments/TERMINAL_PLACER_BIDIR_PROBE_V2_ALL_FAMILIES_TEMP_2026_06_26.zip`
- `experiments/TERMINAL_PLACER_CAP_ELEC_ATTACHMENT_V3_TEMP_2026_06_30.zip`
- `experiments/TERMINAL_PLACER_VSOURCE_ATTACHMENT_V4_TEMP_2026_06_30.zip`
- `experiments/TERMINAL_PLACER_CSOURCE_ATTACHMENT_V4_TEMP_2026_06_30.zip`
- `experiments/TERMINAL_PLACER_SHORT_WIRE_V6_TEMP_2026_07_01.zip`

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
pin records, and preserves 49-byte non-final and 50-byte final right wires. The
user confirmed its 1x/3x/15x Proteus pack worked on 2026-06-30:
`experiments/TERMINAL_PLACER_REALIND_ATTACHMENT_V2_TEMP_2026_06_30.zip`.

The old generic CAP-ELEC terminal probes are rejected because their terminals
were visible but unattached. `CAP-ELEC/v3` instead follows the accepted
eight-component donor: repeated right-terminal/left-terminal/component/
left-wire/right-wire groups; pins 508000 units from the body; terminal symbols
another 254000 units outward; donor-native suffix progression; zero-length
records at both pins; 49-byte non-final right wires; and a 50-byte final right
wire. The user confirmed its 1x/3x/15x pack worked on 2026-06-30:
`experiments/TERMINAL_PLACER_CAP_ELEC_ATTACHMENT_V3_TEMP_2026_06_30.zip`.

`VSOURCE/v4` and `CSOURCE/v4` reuse the manually accepted bidirectional V3
source method: input roles use 180 degrees, output roles use 0 degrees, source
body link fields are patched with the same endpoint suffixes, and two
zero-length source-native wire records end at the actual pins. VSOURCE
preserves output/input order; CSOURCE preserves input/output order. Both use
the accepted `0x0080` per-source suffix step and handle dynamic reference
lengths such as `I9` to `I10`. The user confirmed both 1x/3x/15x packs worked
on 2026-06-30:

- `experiments/TERMINAL_PLACER_VSOURCE_ATTACHMENT_V4_TEMP_2026_06_30.zip`
- `experiments/TERMINAL_PLACER_CSOURCE_ATTACHMENT_V4_TEMP_2026_06_30.zip`

Repository-wide donor scanning did not find terminalized attachment evidence
for DIODE, the named diode variants, LED-RED, FUSE, or VPULSE. VSINE has an
accepted special single non-final source unit, but not a proven general
1x/3x/15x ordering. These families remain unsupported in the shared terminal
dispatcher; no passive/source pattern is guessed for them.

`MIXED/selective-v1` is rejected. The user reported that its mixed pack failed
in Proteus. It rebuilt independently accepted family blocks and therefore did
not preserve the object order of the older all-family files.

The user clarified that the older V2 all-family files did open and render:
their terminals were present beside components but floated because no
attachment links or wires were emitted. That establishes one useful ordering
constraint without establishing attachment:

```text
beautified component stream -> appended terminals
```

`MIXED/append-overlay-v3-temp` retains that component-first ordering. It
patches accepted family link fields in the existing component packets, then
appends terminal records and donor-derived zero-length attachment wires. The
learned RESISTOR/v3, CAP/v2, REALIND/v2, CAP-ELEC/v3, VSOURCE/v4, and
CSOURCE/v4 geometry/suffix rules are reused inside the one shared terminal
module. DIODE, NPN, and 74HC08 remain byte-identical and receive no terminals.

The V3 diagnostic pack contains:

- T00: exact-copy bare control with separated IC/non-IC layout bands;
- T01: historical opening-order control with 12 floating appended terminals;
- T02: full six-family attachment overlay with 12 terminals and 12 wires;
- T03: passive-only attachment overlay with 8 terminals and 8 wires;
- T04: source-only attachment overlay with 4 terminals and 4 wires.

The user rejected V3 as a mixed attachment method. T02-T04 were described as
terrible. T01 was the only close case: its component-first append-only order
placed terminals correctly near the pins, but the resistor remained
unattached. The user then clarified the missing invariant: Proteus requires a
small `WIRE` record between each terminal and component pin. Direct coordinate
contact without a wire is not attachment.

The T01/V3 comparison also exposes two independent differences:

- T01 retains RESISTOR/CAP/REALIND/CAP-ELEC/VSOURCE/CSOURCE terminal order;
- rejected T02 reordered the array source-first and simultaneously changed
  component links, terminal active flags, and wire presence.

V5 confirmed the short-wire geometry but still produced Bad Object Record.
The user supplied a Proteus Ctrl+S repair of its isolated resistor case. The
binary diff proves two exact writer faults:

- inactive appended terminal suffix/link tails must be `00 00 00 00`;
- a terminal-only stream keeps the full last terminal record and appends a
  separate final `FF` sentinel.

Proteus Ctrl+S also removed both old resistor wire records. The repaired
terminal-only output generated with these rules is now object-chunk identical
to the supplied Ctrl+S project.

`MIXED/short-wire-v6-temp` is the only active mixed attachment method. It uses
Ctrl+S-normalized T01 terminal placement, labels, and orientation, then adds
donor-derived short wires without component-link patches or active-terminal
suffixes. RESISTOR uses two 254,000-unit wires from terminal contacts to pins.
CAP, REALIND, CAP-ELEC, VSOURCE, and CSOURCE use their accepted zero-length
pin-coincident wire records. DIODE, NPN, and 74HC08 remain byte-preserved and
terminal-free.

The V6 pack contains the exact saved repair, a generated object-identical
terminal-only control, resistor 1x/3x/15x, and full mixed
1x/3x/15x short-wire projects. All eight cases pass static record, endpoint,
orientation, suffix-tail, preservation, and layout checks. Proteus testing is
required for the short-wire outputs.

The packet beautifier now places IC and non-IC families in separate vertical
bands when they coexist. The lower band begins at least 5,080,000 internal
units below the maximum parsed IC coordinate. This corrects the reported
74HC08/non-IC visual overlap; Proteus confirmation remains pending.

## Verification Baseline

- focused component placer suite: 53 passed;
- compileall: passed;
- value V2: 7/7 static-valid;
- terminal V2: 3/3 marker-valid but rejected as unattached in Proteus;
- resistor-specific V3 attachment: Proteus-accepted and locked.
- capacitor-specific V1 attachment: invalidated by donor audit.
- capacitor-specific V2 attachment: Proteus-accepted and locked.
- inductor-specific V1 attachment: user-rejected and disabled.
- inductor-specific V2 attachment: Proteus-accepted and locked.
- electrolytic-capacitor-specific V3 attachment: Proteus-accepted and locked.
- DC-voltage-source-specific V4 attachment: Proteus-accepted and locked.
- DC-current-source-specific V4 attachment: Proteus-accepted and locked.
- mixed selective V1: user-rejected.
- mixed append-overlay V3: rejected; only T01 supplied useful placement/order
  evidence.
- mixed wire-ablation V5: rejected with Bad Object Record.
- mixed short-wire V6: 8/8 static-valid; terminal-only control matches the
  user Ctrl+S repair exactly; short-wire Proteus tests pending.
- mixed IC/non-IC bands: focused static regression passed; pending visual test.

## Next Engineering Step

Test the V6 pack in T00 through T07 order, prioritizing T01 and T02. Continue donor collection using
`docs/complete_component_donor_request.md`; the next handler batch remains the
unsupported two-pin families, with no cross-family pattern guessing.
